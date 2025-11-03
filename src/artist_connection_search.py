"""Core search logic for finding connections between event artists and favorites."""

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra

from models import ConnectionPath


def build_sparse_graph(
    similar_artists_map: dict,
) -> tuple[sp.csr_matrix, dict[str, int], dict[int, str]]:
    """
    Convert similar_artists_map to sparse CSR matrix with costs.

    Args:
        similar_artists_map: Dict mapping artist names to their similar artists

    Returns:
        Tuple of (csr_matrix, artist_to_idx, idx_to_artist)
        - csr_matrix: Graph with costs (1/relationship_strength)
        - artist_to_idx: Maps artist name to matrix index
        - idx_to_artist: Maps matrix index to artist name
    """
    # Build complete artist index
    all_artists = set(similar_artists_map.keys())
    for artist_data in similar_artists_map.values():
        if artist_data.get("status") != "success":
            continue
        for similar_artist in artist_data.get("similar_artists", []):
            all_artists.add(similar_artist["name"])

    # Create bidirectional index mappings
    artist_to_idx = {artist: idx for idx, artist in enumerate(sorted(all_artists))}
    idx_to_artist = {idx: artist for artist, idx in artist_to_idx.items()}

    # Build edge lists
    rows = []
    cols = []
    costs = []

    for source_artist, artist_data in similar_artists_map.items():
        if artist_data.get("status") != "success":
            continue

        source_idx = artist_to_idx[source_artist]

        for similar_artist in artist_data.get("similar_artists", []):
            target_idx = artist_to_idx[similar_artist["name"]]
            strength = similar_artist["relationship_strength"]

            # Skip invalid strengths
            if strength <= 0:
                continue

            cost = 1.0 / strength
            rows.append(source_idx)
            cols.append(target_idx)
            costs.append(cost)

    # Create sparse matrix
    n = len(all_artists)
    graph = sp.csr_matrix((costs, (rows, cols)), shape=(n, n))

    return graph, artist_to_idx, idx_to_artist


def classify_tier(avg_strength: float) -> str:
    """Classify connection into tier based on average strength."""
    if avg_strength >= 7.0:
        return "Very Similar Artists"
    if avg_strength >= 5.0:
        return "Similar Artists"
    if avg_strength >= 3.0:
        return "Moderately Related Artists"
    return "Distantly Related Artists"


def find_relationship_strength(
    similar_artists_map: dict, source: str, target: str
) -> float | None:
    """Find relationship strength from source artist to target artist."""
    artist_data = similar_artists_map.get(source)
    if not artist_data or artist_data.get("status") != "success":
        return None

    for similar_artist in artist_data.get("similar_artists", []):
        if similar_artist["name"] == target:
            return similar_artist["relationship_strength"]

    return None


def reconstruct_path(
    predecessors: np.ndarray, source_idx: int, target_idx: int, idx_to_artist: dict
) -> list[str] | None:
    """Reconstruct path from source to target using predecessors array."""
    # Check if target is reachable
    if predecessors[source_idx, target_idx] == -9999:
        return None

    path = []
    current = target_idx

    while current != source_idx:
        path.append(idx_to_artist[current])
        current = predecessors[source_idx, current]
        if current == -9999:
            return None

    path.append(idx_to_artist[source_idx])
    return list(reversed(path))


def calculate_path_metrics(
    path: list[str], similar_artists_map: dict
) -> tuple[list[float], float, float, float, float] | None:
    """
    Calculate metrics for a path.

    Returns:
        Tuple of (path_strengths, total_cost, min_strength, max_strength, avg_strength)
        or None if path is invalid
    """
    strengths = []

    for i in range(len(path) - 1):
        source = path[i]
        target = path[i + 1]

        strength = find_relationship_strength(similar_artists_map, source, target)
        if strength is None:
            return None

        strengths.append(strength)

    # Early exit if no edges
    if not strengths:
        return None

    total_cost = sum(1.0 / s for s in strengths)
    min_strength = min(strengths)
    max_strength = max(strengths)
    avg_strength = sum(strengths) / len(strengths)

    return strengths, total_cost, min_strength, max_strength, avg_strength


def create_connection_path(
    path: list[str],
    path_metrics: tuple[list[float], float, float, float, float],
    event_name: str,
    event_venue: str | None,
    event_url: str,
) -> ConnectionPath:
    """Create a ConnectionPath object from path and metrics."""
    strengths, total_cost, min_strength, max_strength, avg_strength = path_metrics

    return ConnectionPath(
        event_artist=path[0],
        favorite_artist=path[-1],
        path=tuple(path),
        path_strengths=tuple(strengths),
        total_cost=total_cost,
        path_score=1.0 / total_cost,
        min_strength=min_strength,
        max_strength=max_strength,
        avg_strength=avg_strength,
        hops=len(path) - 1,
        tier=classify_tier(avg_strength),
        event_name=event_name,
        event_venue=event_venue,
        event_url=event_url,
    )


def find_optimal_paths(
    graph: sp.csr_matrix,
    artist_to_idx: dict[str, int],
    idx_to_artist: dict[int, str],
    source_artists: list[str],
    target_artists: list[str],
    similar_artists_map: dict,
    events: list[dict],
    max_paths_per_pair: int = 5,
) -> list[ConnectionPath]:
    """
    Find optimal paths from source artists to target artists.

    Args:
        graph: Sparse CSR matrix with edge costs
        artist_to_idx: Mapping from artist name to index
        idx_to_artist: Mapping from index to artist name
        source_artists: List of event artist names
        target_artists: List of favorite artist names
        similar_artists_map: Original artist similarity data
        events: List of event dictionaries
        max_paths_per_pair: Maximum paths to keep per event artist → favorite pair

    Returns:
        List of ConnectionPath objects, sorted by path_score (best first)
    """
    # Get indices for source artists that exist in graph
    source_indices = []
    source_idx_to_artist = {}
    for artist in source_artists:
        if artist in artist_to_idx:
            idx = artist_to_idx[artist]
            source_indices.append(idx)
            source_idx_to_artist[idx] = artist

    # Early exit if no valid sources
    if not source_indices:
        return []

    # Get indices for target artists that exist in graph
    target_indices = set()
    for artist in target_artists:
        if artist in artist_to_idx:
            target_indices.add(artist_to_idx[artist])

    # Early exit if no valid targets
    if not target_indices:
        return []

    # Run Dijkstra from all sources
    distances, predecessors = dijkstra(
        graph, indices=source_indices, return_predecessors=True
    )

    # Build event lookup for artist names
    event_lookup = {}
    for event in events:
        for artist_data in event["artists"]:
            artist_name = artist_data["name"]
            if artist_name not in event_lookup:
                event_lookup[artist_name] = {
                    "name": event["name"],
                    "venue": event.get("venue"),
                    "url": event["ticket_url"],
                }

    # Collect all connections
    connections = []

    for source_array_idx, source_idx in enumerate(source_indices):
        source_artist = source_idx_to_artist[source_idx]

        # Get event info
        event_info = event_lookup.get(source_artist)
        if not event_info:
            continue

        for target_idx in target_indices:
            # Check if target is reachable
            if distances[source_array_idx, target_idx] == np.inf:
                continue

            # Reconstruct path
            path = reconstruct_path(predecessors, source_array_idx, target_idx, idx_to_artist)
            if not path:
                continue

            # Calculate metrics
            metrics = calculate_path_metrics(path, similar_artists_map)
            if not metrics:
                continue

            # Create connection
            connection = create_connection_path(
                path,
                metrics,
                event_info["name"],
                event_info["venue"],
                event_info["url"],
            )
            connections.append(connection)

    # Sort by path_score (higher = better)
    connections.sort(key=lambda c: c.path_score, reverse=True)

    # Keep top max_paths_per_pair for each event artist → favorite pair
    seen_pairs = {}
    filtered_connections = []

    for conn in connections:
        pair_key = (conn.event_artist, conn.favorite_artist)
        count = seen_pairs.get(pair_key, 0)

        if count < max_paths_per_pair:
            filtered_connections.append(conn)
            seen_pairs[pair_key] = count + 1

    return filtered_connections
