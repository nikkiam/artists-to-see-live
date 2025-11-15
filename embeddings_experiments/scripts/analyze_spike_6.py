#!/usr/bin/env python3
"""
Analyze Spike 6 results comprehensively:
1. Load all 13 layers of similarities
2. Compare to Spike 5 results
3. Validate against music-map.com
4. Analyze layer performance across different artist pairings
"""

import json
from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class ArtistPair:
    """Artist pair with expected similarity."""
    artist1: str
    artist2: str
    description: str
    expected_similarity: str  # "LOW", "MEDIUM", "HIGH"


# Test artists with their genres
TEST_ARTISTS = {
    "deadmau5": "Progressive House",
    "Rezz": "Dark Techno",
    "TroyBoi": "Trap",
    "IMANU": "Neurofunk DnB",
    "PEEKABOO": "Bass Music",
    "Sabrina Carpenter": "Pop",
    "Vril": "Minimal Techno",
    "Calibre": "Liquid DnB",
}

# Expected LOW similarity pairs (different genres)
EXPECTED_LOW_PAIRS = [
    ArtistPair("Vril", "Sabrina Carpenter", "Minimal Techno ↔ Pop", "LOW"),
    ArtistPair("PEEKABOO", "Vril", "Bass ↔ Minimal", "LOW"),
    ArtistPair("TroyBoi", "Calibre", "Trap ↔ Liquid DnB", "LOW"),
    ArtistPair("IMANU", "Vril", "Neurofunk ↔ Minimal", "LOW"),
    ArtistPair("deadmau5", "Sabrina Carpenter", "Progressive House ↔ Pop", "LOW"),
]

# Expected HIGH similarity pairs (same/similar genres)
EXPECTED_HIGH_PAIRS = [
    ArtistPair("TroyBoi", "PEEKABOO", "Both Bass Music", "HIGH"),
    ArtistPair("deadmau5", "Rezz", "House ↔ Techno", "HIGH"),
    ArtistPair("IMANU", "Calibre", "Both DnB (different styles)", "MEDIUM"),
]


def load_spike_5_similarities() -> dict:
    """Load Spike 5 (chunked MERT) similarities."""
    path = Path(__file__).parent / "data" / "spike_5_similarities.json"
    with open(path) as f:
        data = json.load(f)

    # Convert to dict for easy lookup
    lookup = {}
    for pair in data["pairwise_similarities"]:
        key = tuple(sorted([pair["artist1"], pair["artist2"]]))
        lookup[key] = pair["cosine_similarity"]

    return lookup


def load_spike_6_layer_similarities() -> dict:
    """Load all 13 layers from Spike 6."""
    path = Path(__file__).parent / "data" / "spike_6_layer_similarities.json"
    with open(path) as f:
        return json.load(f)


def load_music_map_data() -> dict:
    """Load music-map.com similar artists data."""
    path = Path(__file__).parent.parent / "output" / "similar_artists_map.json"

    music_map = {}
    with open(path) as f:
        data = json.load(f)
        for artist_name, artist_data in data.items():
            if artist_data.get("status") == "success":
                similar = [s["name"] for s in artist_data.get("similar_artists", [])]
                music_map[artist_name] = similar

    return music_map


def get_similarity(pairs_dict: dict, artist1: str, artist2: str) -> float | None:
    """Get similarity from dict, handling both orderings."""
    key1 = tuple(sorted([artist1, artist2]))
    return pairs_dict.get(key1)


def analyze_layer_performance(layer_data: list) -> dict:
    """Analyze a single layer's performance."""
    pairs = layer_data  # layer_data is already the list of pairs

    # Use mean_similarity as the representative similarity for each pair
    sims = [p["mean_similarity"] for p in pairs]

    min_pair = min(pairs, key=lambda x: x["mean_similarity"])
    max_pair = max(pairs, key=lambda x: x["mean_similarity"])

    # Convert to lookup dict
    lookup = {}
    for pair in pairs:
        key = tuple(sorted([pair["artist1"], pair["artist2"]]))
        lookup[key] = pair["mean_similarity"]

    return {
        "min": min(sims),
        "max": max(sims),
        "span": max(sims) - min(sims),
        "mean": sum(sims) / len(sims),
        "min_pair": f"{min_pair['artist1']} ↔ {min_pair['artist2']}",
        "max_pair": f"{max_pair['artist1']} ↔ {max_pair['artist2']}",
        "lookup": lookup,
    }


def validate_music_map_overlap(layer_lookup: dict, music_map: dict) -> dict:
    """Calculate music-map overlap for embedding-based similarities."""
    results = {}

    for artist_name in TEST_ARTISTS:
        if artist_name not in music_map:
            results[artist_name] = {"status": "not_in_music_map"}
            continue

        # Get music-map top 5
        music_map_top5 = music_map[artist_name][:5]

        # Get embedding-based top 5 (from our test artists)
        artist_sims = []
        for other_artist in TEST_ARTISTS:
            if other_artist == artist_name:
                continue
            sim = get_similarity(layer_lookup, artist_name, other_artist)
            if sim is not None:
                artist_sims.append((other_artist, sim))

        # Sort by similarity (descending)
        artist_sims.sort(key=lambda x: x[1], reverse=True)
        embedding_top5 = [name for name, _ in artist_sims[:5]]

        # Calculate overlap
        overlap = len(set(music_map_top5) & set(embedding_top5))
        overlap_pct = overlap / 5.0 if music_map_top5 else 0.0

        results[artist_name] = {
            "status": "success",
            "music_map_top5": music_map_top5,
            "embedding_top5": embedding_top5,
            "overlap": overlap,
            "overlap_pct": overlap_pct,
        }

    # Calculate average
    overlaps = [r["overlap_pct"] for r in results.values() if r.get("status") == "success"]
    avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0.0

    return {
        "per_artist": results,
        "avg_overlap_pct": avg_overlap,
    }


def main():
    """Run comprehensive analysis."""
    print("Loading data...")
    spike_5_sims = load_spike_5_similarities()
    spike_6_layers = load_spike_6_layer_similarities()
    music_map = load_music_map_data()

    print(f"\nLoaded:")
    print(f"  - Spike 5: {len(spike_5_sims)} pairwise similarities")
    print(f"  - Spike 6: {len(spike_6_layers)} layers")
    print(f"  - Music-map: {len(music_map)} artists")

    # Analyze all layers
    print("\n" + "=" * 80)
    print("LAYER PERFORMANCE ANALYSIS")
    print("=" * 80)

    layer_stats = {}
    for layer_name, layer_data in spike_6_layers.items():
        stats = analyze_layer_performance(layer_data)
        layer_stats[layer_name] = stats

        layer_num = layer_name.replace("layer_", "")
        print(f"\n{layer_name.upper()} (Layer {layer_num}):")
        print(f"  Range: {stats['min']:.3f} - {stats['max']:.3f} (span: {stats['span']:.3f})")
        print(f"  Lowest:  {stats['min_pair']} = {stats['min']:.3f}")
        print(f"  Highest: {stats['max_pair']} = {stats['max']:.3f}")

    # Rank layers by span (discrimination ability)
    print("\n" + "=" * 80)
    print("LAYER RANKING BY DISCRIMINATION (Wider span = Better)")
    print("=" * 80)

    ranked_layers = sorted(layer_stats.items(), key=lambda x: x[1]["span"], reverse=True)
    for rank, (layer_name, stats) in enumerate(ranked_layers, 1):
        layer_num = layer_name.replace("layer_", "")
        emoji = "🏆" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
        print(f"{rank:2d}. {emoji} Layer {layer_num:2s}: span={stats['span']:.3f}  (range: {stats['min']:.3f}-{stats['max']:.3f})")

    # Best layer detailed analysis
    best_layer_name = ranked_layers[0][0]
    best_layer_stats = ranked_layers[0][1]
    best_layer_lookup = best_layer_stats["lookup"]

    print("\n" + "=" * 80)
    print(f"BEST LAYER ({best_layer_name.upper()}) - DETAILED ANALYSIS")
    print("=" * 80)

    # Compare expected LOW pairs
    print("\n📉 Expected LOW Similarity Pairs:")
    print(f"{'Pair':<50} {best_layer_name:>10}  {'Spike 5':>10}  {'Change':>10}")
    print("-" * 85)

    for pair in EXPECTED_LOW_PAIRS:
        best_sim = get_similarity(best_layer_lookup, pair.artist1, pair.artist2)
        spike5_sim = get_similarity(spike_5_sims, pair.artist1, pair.artist2)

        if best_sim is not None and spike5_sim is not None:
            change = best_sim - spike5_sim
            emoji = "✅" if best_sim < 0.6 else "⚠️" if best_sim < 0.7 else "❌"
            change_emoji = "✅" if change < 0 else "❌"
            pair_str = f"{pair.artist1} ↔ {pair.artist2}"
            desc_str = f"({pair.description})"
            print(f"{emoji} {pair_str:<35} {desc_str:<20}")
            print(f"   {'':<37} {best_sim:>9.3f}  {spike5_sim:>10.3f}  {change_emoji} {change:>+9.3f}")

    # Compare expected HIGH pairs
    print("\n📈 Expected HIGH Similarity Pairs:")
    print(f"{'Pair':<50} {best_layer_name:>10}  {'Spike 5':>10}  {'Change':>10}")
    print("-" * 85)

    for pair in EXPECTED_HIGH_PAIRS:
        best_sim = get_similarity(best_layer_lookup, pair.artist1, pair.artist2)
        spike5_sim = get_similarity(spike_5_sims, pair.artist1, pair.artist2)

        if best_sim is not None and spike5_sim is not None:
            change = best_sim - spike5_sim
            emoji = "✅" if best_sim > 0.7 else "⚠️" if best_sim > 0.6 else "❌"
            pair_str = f"{pair.artist1} ↔ {pair.artist2}"
            desc_str = f"({pair.description})"
            print(f"{emoji} {pair_str:<35} {desc_str:<20}")
            print(f"   {'':<37} {best_sim:>9.3f}  {spike5_sim:>10.3f}  {change:>+9.3f}")

    # Music-map validation for best layer
    print("\n" + "=" * 80)
    print(f"MUSIC-MAP VALIDATION ({best_layer_name.upper()})")
    print("=" * 80)

    validation = validate_music_map_overlap(best_layer_lookup, music_map)

    print(f"\n📊 Average Top-5 Overlap: {validation['avg_overlap_pct'] * 100:.1f}%")
    print("\nPer-Artist Results:")

    for artist_name in TEST_ARTISTS:
        result = validation["per_artist"][artist_name]
        if result["status"] == "not_in_music_map":
            print(f"\n  ⚠️  {artist_name}: Not in music-map.com")
        else:
            overlap = result["overlap"]
            overlap_pct = result["overlap_pct"]
            emoji = "✅" if overlap > 0 else "❌"
            print(f"\n  {emoji} {artist_name}: {overlap}/5 overlap ({overlap_pct * 100:.0f}%)")
            print(f"     Music-map top 5:  {', '.join(result['music_map_top5'][:3])}...")
            print(f"     Embedding top 5:  {', '.join(result['embedding_top5'])}")

    # Cross-layer comparison for key pairs
    print("\n" + "=" * 80)
    print("CROSS-LAYER COMPARISON FOR KEY PAIRS")
    print("=" * 80)

    key_pairs = EXPECTED_LOW_PAIRS[:3]  # Top 3 most interesting

    for pair in key_pairs:
        print(f"\n{pair.artist1} ↔ {pair.artist2} ({pair.description}):")
        print(f"{'Layer':<10} {'Similarity':>12}")
        print("-" * 25)

        # Show all layers sorted by similarity
        layer_sims = []
        for layer_name, stats in layer_stats.items():
            sim = get_similarity(stats["lookup"], pair.artist1, pair.artist2)
            if sim is not None:
                layer_num = int(layer_name.replace("layer_", ""))
                layer_sims.append((layer_num, sim))

        layer_sims.sort(key=lambda x: x[1])  # Sort by similarity (ascending)

        for layer_num, sim in layer_sims:
            best_marker = "🏆" if layer_num == int(best_layer_name.replace("layer_", "")) else "  "
            print(f"Layer {layer_num:2d} {best_marker}  {sim:>11.3f}")

        # Show Spike 5 for comparison
        spike5_sim = get_similarity(spike_5_sims, pair.artist1, pair.artist2)
        if spike5_sim is not None:
            print("-" * 25)
            print(f"Spike 5     {spike5_sim:>11.3f}  (chunked)")

    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)

    spike5_min = min(spike_5_sims.values())
    spike5_max = max(spike_5_sims.values())
    spike5_span = spike5_max - spike5_min

    print(f"\nSpike 5 (Chunked MERT, Layer 13):")
    print(f"  Range: {spike5_min:.3f} - {spike5_max:.3f}")
    print(f"  Span:  {spike5_span:.3f}")
    print(f"  Music-map overlap: 0% (from SPIKE_5_MERT_RESULTS.md)")

    print(f"\nSpike 6 (Full Context, {best_layer_name.upper()}):")
    print(f"  Range: {best_layer_stats['min']:.3f} - {best_layer_stats['max']:.3f}")
    print(f"  Span:  {best_layer_stats['span']:.3f}")
    print(f"  Music-map overlap: {validation['avg_overlap_pct'] * 100:.1f}%")

    improvement = ((best_layer_stats['span'] - spike5_span) / spike5_span) * 100
    print(f"\n  📈 Span improvement: {improvement:+.1f}%")

    if validation['avg_overlap_pct'] > 0:
        print(f"  📈 Music-map overlap: IMPROVED from 0% to {validation['avg_overlap_pct'] * 100:.1f}%")
    else:
        print(f"  ⚠️  Music-map overlap: Still 0% (no improvement)")

    # Save detailed results
    output_path = Path(__file__).parent / "data" / "spike_6_detailed_analysis.json"
    output_data = {
        "layer_rankings": [
            {
                "rank": rank,
                "layer": layer_name,
                "span": stats["span"],
                "min": stats["min"],
                "max": stats["max"],
                "min_pair": stats["min_pair"],
                "max_pair": stats["max_pair"],
            }
            for rank, (layer_name, stats) in enumerate(ranked_layers, 1)
        ],
        "best_layer": {
            "name": best_layer_name,
            "stats": {
                "min": best_layer_stats["min"],
                "max": best_layer_stats["max"],
                "span": best_layer_stats["span"],
                "mean": best_layer_stats["mean"],
            },
        },
        "music_map_validation": {
            "avg_overlap_pct": validation["avg_overlap_pct"],
            "per_artist": validation["per_artist"],
        },
        "spike_5_comparison": {
            "spike_5_span": spike5_span,
            "spike_6_span": best_layer_stats["span"],
            "improvement_pct": improvement,
        },
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✅ Detailed analysis saved to: {output_path}")


if __name__ == "__main__":
    main()
