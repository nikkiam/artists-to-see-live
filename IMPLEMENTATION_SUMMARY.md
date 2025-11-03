# Artist Connection Search - Implementation Summary

## Overview

Implemented a bidirectional artist connection search using **Option 1: Weighted Bidirectional Dijkstra** with tiered presentation for user-friendly output.

## Algorithm Choice

After evaluating multiple approaches, we implemented **scipy's sparse graph Dijkstra** for these reasons:

1. **Battle-tested** - Highly optimized C implementation
2. **Perfect for sparse graphs** - Our graph has ~10% density (96K edges / 923K possible)
3. **Simple implementation** - ~300 lines of clean, functional Python
4. **Fast performance** - <1 second for full search (961 nodes, 42 source artists)

### Key Design Decision

We use **average relationship strength** for tier classification (keeping it simple, as requested):
- **Very Similar Artists:** avg ≥ 7.0
- **Similar Artists:** avg ≥ 5.0
- **Moderately Related Artists:** avg ≥ 3.0
- **Distantly Related Artists:** avg < 3.0

This addresses the "weakest link problem" - a path with edges [9.0, 8.9, 0.9] has avg=6.27 and is correctly classified as "Similar Artists" rather than being dismissed as weak.

## Implementation

### Files Created

1. **`src/artist_connection_search.py`** - Core search logic
   - `build_sparse_graph()` - Converts similarity map to CSR sparse matrix
   - `find_optimal_paths()` - Runs Dijkstra and finds all connections
   - `reconstruct_path()` - Rebuilds paths from predecessor matrix
   - `calculate_path_metrics()` - Computes path quality metrics
   - `classify_tier()` - Categorizes connections by strength

2. **`src/find_event_connections.py`** - Main executable script
   - Loads all data files
   - Runs search algorithm
   - Generates reports (JSON + Markdown)
   - Git commits after each step for progress tracking

3. **`src/models.py`** - Added `ConnectionPath` dataclass (immutable)

### Dependencies Added

- `scipy>=1.11.0` - Sparse graph algorithms
- `numpy>=1.24.0` - Array operations (scipy dependency)

## Results Summary

**Run Date:** 2025-11-03 00:06:34

### Statistics

- **Total Connections:** 452
- **Event Artists Connected:** 1 (only Justin Martin from graph)
- **Favorite Artists Connected:** 452
- **Average Path Length:** 7.19 hops
- **Average Path Score:** 0.26

### Tier Breakdown

- **Very Similar Artists:** 0 connections
- **Similar Artists:** 20 connections
- **Moderately Related Artists:** 238 connections
- **Distantly Related Artists:** 194 connections

### Key Findings

1. **Limited overlap** - Only 7 out of 197 event artists were in the music-map graph
   - This is expected since the graph was seeded from `my_artists.json`, not event artists
   - Event artists like "Armana Khan", "Chrysalis", etc. are not in music-map.com data

2. **Justin Martin dominates** - All 452 connections come from Justin Martin performing at "Golden Record Halloween" (Refuge)
   - He's well-connected in the graph with strong relationships to house/electronic artists

3. **Path quality varies** - Most connections are 5-8 hops, suggesting distant relationships
   - Best connections (avg strength >5.0): AC Slater, Wax Motif, Oliver Heldens
   - Longer paths through well-known artists: Swedish House Mafia, Skrillex, Madeon

## Output Files

All results committed and pushed to GitHub:

1. **`output/event_connections.md`** - Human-readable report with:
   - Summary statistics
   - Connections grouped by tier
   - Detailed paths with metrics for each connection

2. **`output/event_connections.json`** - Machine-readable data
   - Full connection details
   - Easy to process programmatically

3. **`output/connection_search.log`** - Execution log
   - Step-by-step progress
   - Timing information
   - Commit history

## Algorithm Performance

- **Graph construction:** ~50ms
- **Dijkstra search (7 sources → 961 targets):** ~100ms
- **Path reconstruction & metrics:** ~50ms
- **Total runtime:** ~1 second

## Recommendations for Better Results

To find more connections, consider:

1. **Scrape event artists** - Run music-map scraper on the 197 event artists to expand the graph
2. **Bidirectional scraping** - Scrape from both favorites → similar AND events → similar
3. **Multiple data sources** - music-map.com may not have all techno/underground artists

## Usage

Run the search anytime with:

```bash
uv run python -m src.find_event_connections
```

The script will:
- Load latest event data from `output/events.json`
- Search for connections to `output/my_artists.json`
- Generate updated reports
- Commit and push results to GitHub

## Technical Notes

### Bug Fixed During Implementation

Initial run found 0 connections due to a bug in `reconstruct_path()`:
- Was comparing source **array index** (0, 1, 2...) with source **node index** (7385, ...)
- Fixed by passing both indices separately
- Now correctly reconstructs all paths

### Top-K Paths Per Pair

Script keeps **top-5 paths** for each event artist → favorite artist pair:
- Allows exploring alternative routes
- Currently only seeing 1 path per pair (optimal path from Dijkstra)
- Future: Could explore K-shortest paths if desired

## Code Quality

- ✅ Functional programming style (immutable dataclasses)
- ✅ Early exit pattern throughout
- ✅ No `print()` statements (uses proper logging)
- ✅ Type hints on all functions
- ✅ Zero linting errors (ruff compliant)
