#!/usr/bin/env python3
"""
Find connections between event artists and favorite artists.

Loads event data, favorite artists, and similar artists graph,
then finds optimal paths connecting them using weighted Dijkstra search.
"""

import json
import logging
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import scipy.sparse as sp

from src.artist_connection_search import (
    build_sparse_graph,
    build_strength_lookup,
    find_optimal_paths,
)
from src.data_loader import load_artist_list, load_events, load_similar_artists_map
from src.models import ArtistPairConnections, ConnectionPath, Event

logger = logging.getLogger(__name__)


def extract_unique_artists(events: list[Event]) -> list[str]:
    """Extract unique artist names from events."""
    return sorted({artist.name for event in events for artist in event.artists})


def group_by_tier(connections: list) -> dict[str, list]:
    """Group connections by tier."""
    tiers = defaultdict(list)
    for conn in connections:
        tiers[conn.tier].append(conn)
    return dict(tiers)


def group_pairs_by_tier(
    grouped_connections: list[ArtistPairConnections],
) -> dict[str, list[ArtistPairConnections]]:
    """
    Group ArtistPairConnections by tier.

    Args:
        grouped_connections: List of ArtistPairConnections objects

    Returns:
        Dict mapping tier names to lists of ArtistPairConnections,
        sorted within each tier by best_avg_strength (descending)
    """
    tiers = defaultdict(list)

    # Group by tier (using first path's tier since all paths have same pair)
    for group in grouped_connections:
        tier = group.paths[0].tier
        tiers[tier].append(group)

    # Sort within each tier by best_avg_strength (descending)
    for tier in tiers:
        tiers[tier].sort(key=lambda g: g.best_avg_strength, reverse=True)

    return dict(tiers)


def calculate_stats(
    grouped_connections: list[ArtistPairConnections], tiers: dict
) -> dict:
    """
    Calculate summary statistics from grouped connections.

    Args:
        grouped_connections: List of ArtistPairConnections objects
        tiers: Dict mapping tier names to list of connections

    Returns:
        Dict with statistics
    """
    # Early exit if no connections
    if not grouped_connections:
        return {
            "total_connections": 0,
            "unique_event_artists_connected": 0,
            "unique_favorites_connected": 0,
            "avg_path_length": 0.0,
            "avg_path_score": 0.0,
            "tier_counts": {},
        }

    # Flatten all paths from grouped connections
    all_paths = [path for group in grouped_connections for path in group.paths]

    # Early exit if no paths (shouldn't happen, but defensive)
    if not all_paths:
        return {
            "total_connections": 0,
            "unique_event_artists_connected": 0,
            "unique_favorites_connected": 0,
            "avg_path_length": 0.0,
            "avg_path_score": 0.0,
            "tier_counts": {},
        }

    # Calculate statistics from flattened paths
    event_artists = {group.event_artist for group in grouped_connections}
    favorites = {group.favorite_artist for group in grouped_connections}
    avg_hops = sum(path.hops for path in all_paths) / len(all_paths)
    avg_score = sum(path.path_score for path in all_paths) / len(all_paths)

    return {
        "total_connections": len(all_paths),
        "unique_event_artists_connected": len(event_artists),
        "unique_favorites_connected": len(favorites),
        "avg_path_length": round(avg_hops, 2),
        "avg_path_score": round(avg_score, 2),
        "tier_counts": {tier: len(conns) for tier, conns in tiers.items()},
    }


def generate_markdown_report(tiers: dict, stats: dict, output_file: Path):
    """Generate markdown report of connections."""
    with open(output_file, "w", encoding="utf-8") as f:
        # Header
        f.write("# Event Artist Connection Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Summary stats
        f.write("## Summary\n\n")
        f.write(f"- **Total Connections:** {stats['total_connections']}\n")
        event_artists_count = stats["unique_event_artists_connected"]
        f.write(f"- **Event Artists Connected:** {event_artists_count}\n")
        favorites_count = stats["unique_favorites_connected"]
        f.write(f"- **Favorite Artists Connected:** {favorites_count}\n")
        f.write(f"- **Average Path Length:** {stats['avg_path_length']} hops\n")
        f.write(f"- **Average Path Score:** {stats['avg_path_score']}\n\n")

        # Tier breakdown
        f.write("## Breakdown by Similarity Tier\n\n")
        tier_order = [
            "Very Similar Artists",
            "Similar Artists",
            "Moderately Related Artists",
            "Distantly Related Artists",
        ]

        for tier in tier_order:
            count = stats.get("tier_counts", {}).get(tier, 0)
            stars = "⭐" * (5 - tier_order.index(tier))
            f.write(f"- {stars} **{tier}:** {count} connections\n")

        f.write("\n---\n\n")

        # Detailed connections by tier
        for tier in tier_order:
            tier_connections = tiers.get(tier, [])
            if not tier_connections:
                continue

            f.write(f"## {tier}\n\n")
            f.write(f"Found {len(tier_connections)} connections\n\n")

            # Group by event
            events = defaultdict(list)
            for conn in tier_connections:
                events[conn.event_name].append(conn)

            for event_name, event_conns in sorted(events.items()):
                f.write(f"### {event_name}\n\n")

                venue = event_conns[0].event_venue
                if venue:
                    f.write(f"**Venue:** {venue}\n\n")

                f.write(f"**URL:** {event_conns[0].event_url}\n\n")
                f.write(f"**Connections ({len(event_conns)}):**\n\n")

                # Sort by path score (best first)
                sorted_conns = sorted(
                    event_conns, key=lambda c: c.path_score, reverse=True
                )
                for conn in sorted_conns:
                    # Path display
                    path_str = " → ".join(conn.path)
                    f.write(f"- **{conn.favorite_artist}** (from your favorites)\n")
                    f.write(f"  - Path: `{path_str}`\n")
                    f.write(
                        f"  - Score: {conn.path_score:.2f} | "
                        f"Avg Strength: {conn.avg_strength:.2f} | "
                        f"Min: {conn.min_strength:.2f} | "
                        f"Max: {conn.max_strength:.2f}\n"
                    )
                    f.write(f"  - Hops: {conn.hops}\n\n")

                f.write("\n")

    logger.info("Markdown report saved to: %s", output_file)


def save_json_report(connections: list, stats: dict, output_file: Path):
    """Save JSON report of connections."""
    # Convert connections to dictionaries
    connections_data = [
        {
            "event_artist": c.event_artist,
            "favorite_artist": c.favorite_artist,
            "path": list(c.path),
            "path_strengths": list(c.path_strengths),
            "total_cost": c.total_cost,
            "path_score": c.path_score,
            "min_strength": c.min_strength,
            "max_strength": c.max_strength,
            "avg_strength": c.avg_strength,
            "hops": c.hops,
            "tier": c.tier,
            "event_name": c.event_name,
            "event_venue": c.event_venue,
            "event_url": c.event_url,
        }
        for c in connections
    ]

    report = {
        "timestamp": datetime.now().isoformat(),
        "stats": stats,
        "connections": connections_data,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info("JSON report saved to: %s", output_file)


def save_summary_json_report(
    top_five_by_hops: list[ArtistPairConnections],
    top_five_by_best_path_score: list[ArtistPairConnections],
    connections_by_tier: dict[str, list[ArtistPairConnections]],
    stats: dict,
    output_file: Path,
):
    """
    Save summary JSON report with top connections and tier groupings.

    Args:
        top_five_by_hops: Top 5 connections with shortest paths
        top_five_by_best_path_score: Top 5 connections with highest path scores
        connections_by_tier: Dict mapping tier names to grouped connections
        stats: Summary statistics
        output_file: Path to save JSON report
    """

    def serialize_pair(pair: ArtistPairConnections) -> dict:
        """Convert ArtistPairConnections to dict."""
        return {
            "event_artist": pair.event_artist,
            "favorite_artist": pair.favorite_artist,
            "event_name": pair.event_name,
            "event_venue": pair.event_venue,
            "event_url": pair.event_url,
            "best_path_score": pair.best_path_score,
            "best_avg_strength": pair.best_avg_strength,
            "hops": pair.paths[0].hops,
            "paths": [
                {
                    "path": list(path.path),
                    "path_strengths": list(path.path_strengths),
                    "total_cost": path.total_cost,
                    "path_score": path.path_score,
                    "min_strength": path.min_strength,
                    "max_strength": path.max_strength,
                    "avg_strength": path.avg_strength,
                    "hops": path.hops,
                    "tier": path.tier,
                }
                for path in pair.paths
            ],
        }

    report = {
        "timestamp": datetime.now().isoformat(),
        "stats": stats,
        "top_five_by_hops": [serialize_pair(pair) for pair in top_five_by_hops],
        "top_five_by_best_path_score": [
            serialize_pair(pair) for pair in top_five_by_best_path_score
        ],
        "connections": {
            tier: [serialize_pair(pair) for pair in pairs]
            for tier, pairs in connections_by_tier.items()
        },
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info("Summary JSON report saved to: %s", output_file)


def generate_summary_markdown_report(
    top_five_by_hops: list[ArtistPairConnections],
    top_five_by_best_path_score: list[ArtistPairConnections],
    connections_by_tier: dict[str, list[ArtistPairConnections]],
    stats: dict,
    output_file: Path,
):
    """
    Generate summary markdown report with top connections and tier groupings.

    Args:
        top_five_by_hops: Top 5 connections with shortest paths
        top_five_by_best_path_score: Top 5 connections with highest path scores
        connections_by_tier: Dict mapping tier names to grouped connections
        stats: Summary statistics
        output_file: Path to save markdown report
    """
    with open(output_file, "w", encoding="utf-8") as f:
        # Header
        f.write("# Event Artist Connection Summary\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Summary stats
        f.write("## Summary\n\n")
        f.write(f"- **Total Connections:** {stats['total_connections']}\n")
        event_artists_count = stats["unique_event_artists_connected"]
        f.write(f"- **Event Artists Connected:** {event_artists_count}\n")
        favorites_count = stats["unique_favorites_connected"]
        f.write(f"- **Favorite Artists Connected:** {favorites_count}\n")
        f.write(f"- **Average Path Length:** {stats['avg_path_length']} hops\n")
        f.write(f"- **Average Path Score:** {stats['avg_path_score']}\n\n")

        # Tier breakdown
        f.write("## Breakdown by Similarity Tier\n\n")
        tier_order = [
            "Very Similar Artists",
            "Similar Artists",
            "Moderately Related Artists",
            "Distantly Related Artists",
        ]

        for tier in tier_order:
            count = stats.get("tier_counts", {}).get(tier, 0)
            stars = "⭐" * (5 - tier_order.index(tier))
            f.write(f"- {stars} **{tier}:** {count} connections\n")

        f.write("\n---\n\n")

        # Top 5 Shortest Paths
        f.write("## Top 5 Shortest Paths\n\n")
        if top_five_by_hops:
            for i, pair in enumerate(top_five_by_hops, 1):
                f.write(f"### {i}. {pair.event_artist} → {pair.favorite_artist}\n\n")
                f.write(f"**Event:** {pair.event_name}")
                if pair.event_venue:
                    f.write(f" at {pair.event_venue}")
                f.write("\n\n")
                f.write(f"**URL:** {pair.event_url}\n\n")
                f.write(
                    f"**Best Path ({pair.paths[0].hops} hops, "
                    f"score: {pair.best_path_score:.2f}):**\n\n"
                )

                for path in pair.paths:
                    path_str = " → ".join(path.path)
                    f.write(f"- `{path_str}`\n")
                    f.write(
                        f"  - Score: {path.path_score:.2f} | "
                        f"Avg Strength: {path.avg_strength:.2f} | "
                        f"Min: {path.min_strength:.2f} | "
                        f"Max: {path.max_strength:.2f}\n"
                    )
                f.write("\n")
        else:
            f.write("No connections found.\n\n")

        f.write("---\n\n")

        # Top 5 Strongest Connections
        f.write("## Top 5 Strongest Connections\n\n")
        if top_five_by_best_path_score:
            for i, pair in enumerate(top_five_by_best_path_score, 1):
                f.write(f"### {i}. {pair.event_artist} → {pair.favorite_artist}\n\n")
                f.write(f"**Event:** {pair.event_name}")
                if pair.event_venue:
                    f.write(f" at {pair.event_venue}")
                f.write("\n\n")
                f.write(f"**URL:** {pair.event_url}\n\n")
                f.write(
                    f"**Best Path ({pair.paths[0].hops} hops, "
                    f"score: {pair.best_path_score:.2f}):**\n\n"
                )

                for path in pair.paths:
                    path_str = " → ".join(path.path)
                    f.write(f"- `{path_str}`\n")
                    f.write(
                        f"  - Score: {path.path_score:.2f} | "
                        f"Avg Strength: {path.avg_strength:.2f} | "
                        f"Min: {path.min_strength:.2f} | "
                        f"Max: {path.max_strength:.2f}\n"
                    )
                f.write("\n")
        else:
            f.write("No connections found.\n\n")

        f.write("---\n\n")

        # All Connections by Tier
        f.write("## All Connections by Tier\n\n")

        for tier in tier_order:
            tier_pairs = connections_by_tier.get(tier, [])
            if not tier_pairs:
                continue

            stars = "⭐" * (5 - tier_order.index(tier))
            f.write(f"### {stars} {tier}\n\n")
            f.write(f"Found {len(tier_pairs)} artist pairs\n\n")

            for pair in tier_pairs:
                f.write(f"#### {pair.event_artist} → {pair.favorite_artist}\n\n")
                f.write(f"**Event:** {pair.event_name}")
                if pair.event_venue:
                    f.write(f" at {pair.event_venue}")
                f.write("\n\n")
                f.write(f"**URL:** {pair.event_url}\n\n")
                f.write(f"**Top {len(pair.paths)} path(s):**\n\n")

                for path in pair.paths:
                    path_str = " → ".join(path.path)
                    f.write(f"- `{path_str}`\n")
                    f.write(
                        f"  - Score: {path.path_score:.2f} | "
                        f"Avg Strength: {path.avg_strength:.2f} | "
                        f"Hops: {path.hops}\n"
                    )
                f.write("\n")

    logger.info("Summary markdown report saved to: %s", output_file)


def git_commit_and_push(message: str, files: list[Path]):
    """Create a git commit and push."""
    try:
        # Add files
        subprocess.run(
            ["git", "add"] + [str(f) for f in files],
            check=True,
            capture_output=True,
        )

        # Commit
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            capture_output=True,
        )

        # Push
        subprocess.run(
            ["git", "push"],
            check=True,
            capture_output=True,
        )

        logger.info("✓ Git commit and push successful: %s", message)
    except subprocess.CalledProcessError as e:
        logger.warning("⚠ Git operation failed: %s", e)


def main():
    """Main function to find and report artist connections."""
    # Get parameters from command line
    if len(sys.argv) < 3:
        logger.error("Usage: python -m src.find_event_connections <events_file> <date>")
        sys.exit(1)

    events_file = Path(sys.argv[1])
    date_str = sys.argv[2]

    # Configure logging
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    log_file = output_dir / f"connection_search_{date_str}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )

    logger.info("=" * 60)
    logger.info("Starting artist connection search for %s", date_str)
    logger.info("=" * 60)

    # Step 1: Load data files
    logger.info("Step 1: Loading data files...")

    similar_artists_file = output_dir / "similar_artists_map.json"
    favorites_file = output_dir / "my_artists.json"

    similar_artists_map = load_similar_artists_map(similar_artists_file)
    logger.info("  ✓ Loaded similar artists map: %d artists", len(similar_artists_map))

    events = load_events(events_file)
    logger.info("  ✓ Loaded events: %d events", len(events))

    favorites = load_artist_list(favorites_file)
    logger.info("  ✓ Loaded favorites: %d artists", len(favorites))

    # Step 2: Extract event artists
    logger.info("Step 2: Extracting unique artists from events...")
    event_artists = extract_unique_artists(events)
    logger.info("  ✓ Found %d unique artists across events", len(event_artists))

    # Step 3: Build sparse graph and strength lookup
    logger.info("Step 3: Building sparse graph from similarity data...")
    graph: sp.csr_matrix
    artist_to_idx: dict[str, int]
    idx_to_artist: dict[int, str]
    graph, artist_to_idx, idx_to_artist = build_sparse_graph(similar_artists_map)
    logger.info(
        "  ✓ Graph built: %d nodes, %d edges", graph.shape[0], graph.nnz
    )

    logger.info("  Building strength lookup for fast path reconstruction...")
    strength_lookup = build_strength_lookup(similar_artists_map)
    logger.info("  ✓ Strength lookup built: %d edges", len(strength_lookup))

    # Step 4: Find connections
    logger.info("Step 4: Running Dijkstra search to find optimal paths...")
    grouped_connections = find_optimal_paths(
        graph,
        artist_to_idx,
        idx_to_artist,
        event_artists,
        favorites,
        strength_lookup,
        events,
        max_paths_per_pair=3,
    )

    # Count total paths
    total_paths = sum(len(group.paths) for group in grouped_connections)
    logger.info("  ✓ Found %d artist pairs with %d total paths",
                len(grouped_connections), total_paths)

    # Step 5a: Generate full detailed reports (backward compatible)
    logger.info("Step 5a: Generating full detailed reports...")

    # Flatten grouped connections for backward compatibility
    flat_connections = [
        path for group in grouped_connections for path in group.paths
    ]

    # Create full_reports subdirectory
    full_reports_dir = output_dir / "full_reports"
    full_reports_dir.mkdir(exist_ok=True)

    # Group by tier for full report
    tiers = group_by_tier(flat_connections)
    stats = calculate_stats(grouped_connections, tiers)

    for tier, count in stats.get("tier_counts", {}).items():
        logger.info("  - %s: %d", tier, count)

    # Generate full reports
    full_md_output = full_reports_dir / f"event_connections_{date_str}.md"
    generate_markdown_report(tiers, stats, full_md_output)

    full_json_output = full_reports_dir / f"event_connections_{date_str}.json"
    save_json_report(flat_connections, stats, full_json_output)

    logger.info("  ✓ Full reports generated in full_reports/")

    # Step 5b: Generate summary reports (new format)
    logger.info("Step 5b: Generating summary reports...")

    # Sort by hops (ascending), tie-break by best_avg_strength (descending)
    top_five_by_hops = sorted(
        grouped_connections,
        key=lambda g: (g.paths[0].hops, -g.best_avg_strength)
    )[:5]

    # Sort by best_path_score (descending)
    top_five_by_score = sorted(
        grouped_connections,
        key=lambda g: g.best_path_score,
        reverse=True
    )[:5]

    # Group by tier
    connections_by_tier = group_pairs_by_tier(grouped_connections)

    # Generate summary reports
    summary_md_output = output_dir / f"connections_summary_{date_str}.md"
    generate_summary_markdown_report(
        top_five_by_hops,
        top_five_by_score,
        connections_by_tier,
        stats,
        summary_md_output,
    )

    summary_json_output = output_dir / f"connections_summary_{date_str}.json"
    save_summary_json_report(
        top_five_by_hops,
        top_five_by_score,
        connections_by_tier,
        stats,
        summary_json_output,
    )

    logger.info("  ✓ Summary reports generated")

    # Commit all outputs
    all_outputs = [
        log_file,
        full_md_output,
        full_json_output,
        summary_md_output,
        summary_json_output,
    ]
    git_commit_and_push(f"Generated connection reports for {date_str}", all_outputs)

    # Final summary
    logger.info("=" * 60)
    logger.info("Artist connection search completed successfully")
    logger.info("Total artist pairs: %d", len(grouped_connections))
    logger.info("Total connections found: %d", stats["total_connections"])
    logger.info("Reports saved to:")
    logger.info("  Summary reports:")
    logger.info("    - %s", summary_md_output)
    logger.info("    - %s", summary_json_output)
    logger.info("  Full reports:")
    logger.info("    - %s", full_md_output)
    logger.info("    - %s", full_json_output)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
