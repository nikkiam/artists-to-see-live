"""Core search logic for finding connections between event artists and favorites."""

import heapq

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra

from src.models import (
    TIER_MODERATELY_RELATED_THRESHOLD,
    TIER_SIMILAR_THRESHOLD,
    TIER_VERY_SIMILAR_THRESHOLD,
    ArtistPairConnections,
    ArtistSimilarityData,
    ConnectionPath,
    Event,
)

# Sentinel value indicating no path exists in the predecessors array
NO_PATH_SENTINEL = -9999


def build_strength_lookup(
    similarity_map: dict[str, ArtistSimilarityData],
) -> dict[tuple[str, str], float]:
    """
    Build a pre-computed lookup for (source, target) -> strength.

    This avoids O(n) list iteration during path reconstruction.

    Args:
        similarity_map: Dict of artist similarity data

    Returns:
        Dict mapping (source_artist, target_artist) to relationship strength
    """
    lookup = {}
    for source_artist, artist_data in similarity_map.items():
        for similar_artist in artist_data.similar_artists:
            lookup[(source_artist, similar_artist.name)] = (
                similar_artist.relationship_strength
            )
    return lookup


def build_sparse_graph(
    similarity_map: dict[str, ArtistSimilarityData],
) -> tuple[sp.csr_matrix, dict[str, int], dict[int, str]]:
    """
    Convert similarity map to sparse CSR matrix with costs.

    Args:
        similarity_map: Dict mapping artist names to their similarity data

    Returns:
        Tuple of (csr_matrix, artist_to_idx, idx_to_artist)
        - csr_matrix: Graph with costs (1/relationship_strength)
        - artist_to_idx: Maps artist name to matrix index
        - idx_to_artist: Maps matrix index to artist name
    """
    # Collect all unique artist names
    all_artists = set(similarity_map.keys())
    for artist_data in similarity_map.values():
        all_artists.update(sim.name for sim in artist_data.similar_artists)

    # Create bidirectional index mappings
    artist_to_idx = {artist: idx for idx, artist in enumerate(sorted(all_artists))}
    idx_to_artist = {idx: artist for artist, idx in artist_to_idx.items()}

    # Build edge lists using list comprehensions
    edges = [
        (
            artist_to_idx[source_artist],
            artist_to_idx[sim.name],
            1.0 / sim.relationship_strength,
        )
        for source_artist, artist_data in similarity_map.items()
        for sim in artist_data.similar_artists
    ]

    # Unpack into separate lists
    if edges:
        rows_tuple, cols_tuple, costs_tuple = zip(*edges, strict=True)
        rows = list(rows_tuple)
        cols = list(cols_tuple)
        costs = list(costs_tuple)
    else:
        rows, cols, costs = [], [], []

    # Create sparse matrix
    n = len(all_artists)
    graph = sp.csr_matrix((costs, (rows, cols)), shape=(n, n))

    return graph, artist_to_idx, idx_to_artist


def classify_tier(avg_strength: float) -> str:
    """Classify connection into tier based on average strength."""
    if avg_strength >= TIER_VERY_SIMILAR_THRESHOLD:
        return "Very Similar Artists"
    if avg_strength >= TIER_SIMILAR_THRESHOLD:
        return "Similar Artists"
    if avg_strength >= TIER_MODERATELY_RELATED_THRESHOLD:
        return "Moderately Related Artists"
    return "Distantly Related Artists"


def reconstruct_path(
    predecessors: np.ndarray,
    source_array_idx: int,
    source_node_idx: int,
    target_idx: int,
    idx_to_artist: dict,
) -> list[str] | None:
    """Reconstruct path from source to target using predecessors array."""
    # Check if target is reachable
    if predecessors[source_array_idx, target_idx] == NO_PATH_SENTINEL:
        return None

    path = []
    current = target_idx

    while current != source_node_idx:
        path.append(idx_to_artist[current])
        current = predecessors[source_array_idx, current]
        if current == NO_PATH_SENTINEL:
            return None

    path.append(idx_to_artist[source_node_idx])
    return list(reversed(path))


def calculate_path_metrics(
    path: list[str], strength_lookup: dict[tuple[str, str], float]
) -> tuple[list[float], float, float, float, float] | None:
    """
    Calculate metrics for a path using pre-computed strength lookup.

    Args:
        path: List of artist names forming the path
        strength_lookup: Pre-computed (source, target) -> strength mapping

    Returns:
        Tuple of (path_strengths, total_cost, min_strength, max_strength, avg_strength)
        or None if path is invalid
    """
    # Build list of strengths, checking each exists
    strengths = []
    for i in range(len(path) - 1):
        strength = strength_lookup.get((path[i], path[i + 1]))
        # Early exit if any edge is missing
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
    strength_lookup: dict[tuple[str, str], float],
    events: list[Event],
    max_paths_per_pair: int = 3,
) -> list[ArtistPairConnections]:
    """
    Find optimal paths from source artists to target artists.

    Args:
        graph: Sparse CSR matrix with edge costs
        artist_to_idx: Mapping from artist name to index
        idx_to_artist: Mapping from index to artist name
        source_artists: List of event artist names
        target_artists: List of favorite artist names
        strength_lookup: Pre-computed (source, target) -> strength mapping
        events: List of Event objects
        max_paths_per_pair: Maximum paths to keep per event artist → favorite pair

    Returns:
        List of ArtistPairConnections objects, sorted by best_avg_strength (descending)
    """
    # Filter to artists that exist in graph (using list comprehension)
    valid_sources = [
        (artist, artist_to_idx[artist])
        for artist in source_artists
        if artist in artist_to_idx
    ]

    # Early exit if no valid sources
    if not valid_sources:
        return []

    # Extract indices
    source_artists_valid, source_indices = zip(*valid_sources, strict=True)
    source_idx_to_artist = dict(
        zip(source_indices, source_artists_valid, strict=True)
    )

    # Get target indices (using set comprehension)
    target_indices = {
        artist_to_idx[artist]
        for artist in target_artists
        if artist in artist_to_idx
    }

    # Early exit if no valid targets
    if not target_indices:
        return []

    # Run Dijkstra from all sources
    distances, predecessors = dijkstra(
        graph, indices=source_indices, return_predecessors=True
    )

    # Build event lookup using dict comprehension
    event_lookup = {
        artist.name: {
            "name": event.name,
            "venue": event.venue,
            "url": event.ticket_url,
        }
        for event in events
        for artist in event.artists
    }

    # Initialize heap storage for each (event_artist, favorite_artist) pair
    # Use min heap with negated path_score to simulate max heap
    pair_paths: dict[tuple[str, str], list[tuple[float, ConnectionPath]]] = {}

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
            path = reconstruct_path(
                predecessors, source_array_idx, source_idx, target_idx, idx_to_artist
            )
            if not path:
                continue

            # Calculate metrics using pre-computed lookup
            metrics = calculate_path_metrics(path, strength_lookup)
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

            # Get or create heap for this pair
            pair_key = (connection.event_artist, connection.favorite_artist)
            if pair_key not in pair_paths:
                pair_paths[pair_key] = []

            heap = pair_paths[pair_key]

            # Add to heap: use negative score for max heap behavior
            if len(heap) < max_paths_per_pair:
                heapq.heappush(heap, (-connection.path_score, connection))
            elif connection.path_score > -heap[0][0]:  # Better than worst
                heapq.heapreplace(heap, (-connection.path_score, connection))
            # else: discard the connection (optimization)

    # Build grouped connections from heaps
    return build_grouped_connections(pair_paths)


def build_grouped_connections(
    pair_paths: dict[tuple[str, str], list[tuple[float, ConnectionPath]]],
) -> list[ArtistPairConnections]:
    """
    Build ArtistPairConnections objects from heap storage.

    Args:
        pair_paths: Dict mapping (event_artist, favorite_artist) to heap of paths
                    Each heap contains tuples of (-path_score, ConnectionPath)

    Returns:
        List of ArtistPairConnections, sorted by best_avg_strength (descending)
    """
    grouped_connections = []

    for _pair_key, heap in pair_paths.items():
        # Extract ConnectionPath objects from heap tuples
        paths = [conn for _, conn in heap]

        # Sort by path_score descending (heap doesn't maintain full order)
        paths.sort(key=lambda p: p.path_score, reverse=True)

        # Early exit if no paths (shouldn't happen, but defensive)
        if not paths:
            continue

        # Create ArtistPairConnections with convenience fields
        grouped_conn = ArtistPairConnections(
            event_artist=paths[0].event_artist,
            favorite_artist=paths[0].favorite_artist,
            paths=tuple(paths),
            best_path_score=paths[0].path_score,
            best_avg_strength=paths[0].avg_strength,
            event_name=paths[0].event_name,
            event_venue=paths[0].event_venue,
            event_url=paths[0].event_url,
        )
        grouped_connections.append(grouped_conn)

    # Sort by best_avg_strength descending (pairs with stronger connections first)
    grouped_connections.sort(key=lambda g: g.best_avg_strength, reverse=True)

    return grouped_connections
