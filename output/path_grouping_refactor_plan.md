# Path Grouping Refactor Implementation Plan

## Problem
Currently, paths between the same (event_artist, favorite_artist) combination are scattered throughout the output. The code attempts to limit paths per pair but does so inefficiently by sorting all paths globally first, then filtering.

Example: Danny Daze connections appear on lines 18, 282, 399, 470, etc. instead of being grouped together.

## Goal
- Group all paths for the same (event_artist, favorite_artist) combination together
- Keep only the top 3 paths per combination based on connection strength (path_score)
- Show statistics for each path to enable comparison
- Optimize memory by discarding weak paths during search (not storing all then filtering)
- Produce two outputs:
  1. **Full detailed output** (existing format, moved to `output/full_reports/` subfolder)
  2. **Summary output** (new format, at `output/connections_summary_*.json` for easy consumption)

## Design Decision: Max Heap Approach

**Rationale:**
- Use Python's `heapq` with negated scores to maintain top 3 paths per pair
- **Benefits:**
  - Future-proof for extensions (easy to change heap size or add features)
  - Clean semantics: `heappush` and `heapreplace` make intent clear
  - O(log n) operations are idiomatic for priority queues in Python
  - Efficient memory management by discarding weak paths immediately
- **Implementation:**
  - Min heap with negated `path_score` (simulates max heap)
  - Use `heappush` when heap size < 3
  - Use `heapreplace` when new path is better than worst
  - Extract and sort paths in `build_grouped_connections` for final ordering

## Implementation Steps

### 1. Update `ConnectionPath` model in `src/models.py`
- No changes needed to the dataclass itself
- Keep all existing fields for statistics and comparison

### 2. Create new model for grouped connections in `src/models.py`
- Add `ArtistPairConnections` dataclass to store grouped paths:
  - `event_artist: str`
  - `favorite_artist: str`
  - `paths: list[ConnectionPath]` (max 3 paths, sorted by path_score descending)
  - `best_path_score: float` (convenience field for the top path)
  - `best_avg_strength: float` (avg_strength of top path, used for ordering output)
  - `event_name: str`
  - `event_venue: str | None`
  - `event_url: str`

### 3. Refactor `find_optimal_paths` in `src/artist_connection_search.py`
- Replace the current post-filtering approach (lines 304-316) with inline filtering
- Use `dict[tuple[str, str], list[ConnectionPath]]` to track top paths per pair during search
- For each new path found:
  - Get pair key `(event_artist, favorite_artist)`
  - Get current paths list for this pair
  - If `len(paths) < 3`:
    - Append new path
    - Sort by path_score descending
  - If `len(paths) == 3`:
    - Check if `new_path.path_score > paths[-1].path_score` (better than worst)
    - If yes: append, sort by path_score descending, keep top 3 only
    - If no: discard the new path (this is the key optimization)
- Remove global sorting (line 302)
- Return `list[ArtistPairConnections]` instead of flat `list[ConnectionPath]`

### 4. Add helper function to build grouped connections
- Add `build_grouped_connections` function in `src/artist_connection_search.py`
- Input: `dict[tuple[str, str], list[ConnectionPath]]`
- Output: `list[ArtistPairConnections]`
- For each pair, create an `ArtistPairConnections` object with:
  - Paths already sorted by path_score (descending)
  - `best_path_score` = `paths[0].path_score`
  - `best_avg_strength` = `paths[0].avg_strength`
  - Event metadata from first path
- Sort final list by `best_avg_strength` descending before returning
  - This orders pairs by their strongest connection's average strength
  - Pairs with higher average strength (better connected) appear first

### 5. Update output directory structure in `src/find_event_connections.py`
- Create `output/full_reports/` subdirectory if it doesn't exist
- Move existing detailed JSON and markdown outputs to `full_reports/` subfolder
- Keep existing output format for full_reports (current flat list structure)
- Files: `output/full_reports/event_connections_{date}.json` and `.md`

### 6. Create new summary JSON generation function
- Add `save_summary_json_report` function in `src/find_event_connections.py`
- Input: `list[ArtistPairConnections]`, stats, output_file
- Output: Summary JSON at `output/connections_summary_{date}.json`
- New JSON structure:
```json
{
  "timestamp": "...",
  "stats": {
    "total_connections": 6343,
    "unique_event_artists_connected": 15,
    "unique_favorites_connected": 454,
    "avg_path_length": 8.48,
    "avg_path_score": 0.11,
    "tier_counts": {...}
  },
  "top_five_by_hops": [
    {
      "event_artist": "Danny Daze",
      "favorite_artist": "Justin Martin",
      "event_name": "Halloween",
      "event_venue": "Signal",
      "event_url": "...",
      "best_path_score": 3.07874,
      "best_avg_strength": 3.07874,
      "hops": 1,
      "paths": [...]
    }
  ],
  "top_five_by_best_path_score": [
    {
      "event_artist": "...",
      "favorite_artist": "...",
      ...
    }
  ],
  "connections": {
    "Very Similar Artists": [
      {
        "event_artist": "...",
        "favorite_artist": "...",
        ...
      }
    ],
    "Similar Artists": [...],
    "Moderately Related Artists": [...],
    "Distantly Related Artists": [...]
  }
}
```
- Sorting logic:
  - `top_five_by_hops`: sort by `paths[0].hops` ascending, tie-break by `best_avg_strength` descending
  - `top_five_by_best_path_score`: sort by `best_path_score` descending
  - `connections`: group by tier, sort within tier by `best_avg_strength` descending

### 7. Create new summary markdown generation function
- Add `generate_summary_markdown_report` function in `src/find_event_connections.py`
- Input: top_five_by_hops, top_five_by_best_path_score, connections_by_tier, stats
- Output: Markdown at `output/connections_summary_{date}.md`
- Structure:
  - Summary stats (same as current)
  - "Top 5 Shortest Paths" section showing quickest connections
  - "Top 5 Strongest Connections" section showing highest path scores
  - "All Connections by Tier" section with grouped pairs
  - Within each section, show all paths for comparison

### 8. Update `calculate_stats` in `src/find_event_connections.py`
- Accept `list[ArtistPairConnections]` instead of flat list
- Flatten the paths when calculating statistics:
  - `total_connections`: sum of `len(group.paths)` for all groups
  - `unique_event_artists_connected`: count unique event artists across groups
  - `unique_favorites_connected`: count unique favorite artists across groups
  - Flatten all paths: `all_paths = [path for group in groups for path in group.paths]`
  - Calculate avg_path_length and avg_path_score from flattened paths

### 9. Add helper function to group ArtistPairConnections by tier
- Add `group_pairs_by_tier` function in `src/find_event_connections.py`
- Input: `list[ArtistPairConnections]`
- Output: `dict[str, list[ArtistPairConnections]]`
- Group pairs by their tier (using `paths[0].tier` since all paths in a pair have same event_artist/favorite_artist)
- Within each tier, sort by `best_avg_strength` descending
- Return dict with tier names as keys

### 10. Update Dijkstra loop in `find_optimal_paths` to use max heap
- Replace lines 264-316 with heap-based approach
- Import: `import heapq` at top of file
- Initialize: `pair_paths: dict[tuple[str, str], list[tuple[float, ConnectionPath]]] = {}`
- Use min heap with negated path_score (to simulate max heap)
- In the loop (lines 266-299), after creating connection:
  ```python
  # Get or create heap for this pair
  pair_key = (connection.event_artist, connection.favorite_artist)
  if pair_key not in pair_paths:
      pair_paths[pair_key] = []

  heap = pair_paths[pair_key]

  # Add to heap: use negative score for max heap behavior
  if len(heap) < 3:
      heapq.heappush(heap, (-connection.path_score, connection))
  elif connection.path_score > -heap[0][0]:  # Better than worst
      heapq.heapreplace(heap, (-connection.path_score, connection))
  # else: discard the connection (optimization)
  ```
- After loop, extract connections from heaps and call `build_grouped_connections(pair_paths)`
- Note: `build_grouped_connections` will need to extract `ConnectionPath` from tuples and sort

### 11. Implement `build_grouped_connections` function
- Location: `src/artist_connection_search.py` after `find_optimal_paths`
- Input: `dict[tuple[str, str], list[tuple[float, ConnectionPath]]]` (heaps from step 10)
- For each pair:
  - Extract `ConnectionPath` objects from heap tuples: `[conn for _, conn in heap]`
  - Sort extracted paths by `path_score` descending (heap doesn't maintain full order)
  - Create `ArtistPairConnections` object
  - Extract `best_path_score` and `best_avg_strength` from first path (paths[0] after sorting)
- Sort final result by `best_avg_strength` descending for default ordering
- Return sorted list of `ArtistPairConnections`

### 12. Update main function to generate both outputs
- Update `main` function in `src/find_event_connections.py`
- After Step 4 (finding connections), now have `list[ArtistPairConnections]` sorted by `best_avg_strength`
- Step 5a: Generate full detailed output (backward compatible)
  - Flatten grouped connections to flat list: `flat_connections = [path for group in grouped_connections for path in group.paths]`
  - Create `output/full_reports/` directory if needed
  - Call existing `save_json_report(flat_connections, stats, full_reports/event_connections_{date}.json)`
  - Call existing `generate_markdown_report(tiers, stats, full_reports/event_connections_{date}.md)`
- Step 5b: Generate summary output (new)
  - Sort copy by hops ascending (tie-break by best_avg_strength descending), take top 5
  - Sort copy by best_path_score descending, take top 5
  - Group connections by tier using new helper (groups and sorts within tier by best_avg_strength)
  - Call new `save_summary_json_report(..., output/connections_summary_{date}.json)`
  - Call new `generate_summary_markdown_report(..., output/connections_summary_{date}.md)`
- Update git commit to include all 4 files (2 in full_reports, 2 at top level)

### 13. Update function signatures and type hints
- Change `find_optimal_paths` return type to `list[ArtistPairConnections]`
- Update helper functions to accept `list[ArtistPairConnections]`
- Keep existing `save_json_report` and `generate_markdown_report` for full output (flat list)
- Add new functions for summary output
- Ensure all type hints are correct throughout the chain

### 14. Update command line parameter
- Change `max_paths_per_pair` from 5 to 3 in line 284 of `src/find_event_connections.py`
- Since this is now hardcoded to 3, consider removing the parameter entirely
- Keep parameter for flexibility: future changes might want 5 or 1

## Benefits of This Approach

1. **Memory efficiency**: Discards weak paths immediately instead of storing all
2. **Dual outputs**: Full detailed data for analysis + digestible summary for quick review
3. **Backward compatibility**: Existing full output format preserved, just relocated
4. **Clarity**: Summary output groups paths and highlights top connections
5. **Performance**: Simple list approach is fast for n=3 and highly readable
6. **Maintainability**: Clear code structure, easy to debug and modify
7. **Flexible sorting**: Multiple views (by hops, by score, by tier) for different use cases
