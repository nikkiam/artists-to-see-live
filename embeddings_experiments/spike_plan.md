# Embeddings Spike - Implementation Plan

## Objective

Validate that audio embeddings can replicate music-map.com similarity for known artists, demonstrating feasibility for unknown artist recommendations.

## Success Criteria

1. **Embedding extraction works** for ≥85% of test artists
2. **Similarity correlation** with music-map.com ≥ 0.6 (Pearson correlation)
3. **Top-5 overlap** with music-map.com ≥ 50%
4. **All work follows project standards** (no print, file logging, typed dataclasses)

## Test Artist Selection

### Selection Criteria
- 10 artists from existing music-map.com database
- Mix of popularity levels (well-known + mid-tier)
- Diverse genres within techno/house/electronic
- Known to have tracks on Spotify with previews

### Suggested Test Artists
(To be selected from `output/similar_artists_map.json` during implementation)

## Technical Implementation

### Directory Structure

```
embeddings_experiments/
├── recommendations.md          (this file's companion)
├── spike_plan.md              (this file)
├── logs/
│   └── spike_2025-11-10.log  (created during run)
├── data/
│   └── spike_embeddings.json (results from spike)
└── spike.py                   (main script)
```

### Dependencies to Install

```bash
uv add librosa soundfile numpy scikit-learn spotipy openl3
```

### Code Structure (Functional Style)

```python
# embeddings_experiments/spike.py

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import openl3
import soundfile as sf
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials

# --- Logging Setup (Per CLAUDE.md) ---

LOG_FILE = Path(__file__).parent / "logs" / f"spike_{datetime.now().strftime('%Y-%m-%d')}.log"

def log(message: str) -> None:
    """Log to file only - NO PRINT STATEMENTS"""
    LOG_FILE.parent.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {message}\n")

# --- Data Models (Typed Dataclasses) ---

@dataclass(frozen=True)
class TrackInfo:
    name: str
    spotify_id: str
    preview_url: Optional[str]

@dataclass(frozen=True)
class ArtistEmbedding:
    artist_name: str
    embedding: np.ndarray
    tracks_used: list[str]
    spotify_ids: list[str]
    computed_at: str
    model: str = "openl3"

@dataclass(frozen=True)
class SimilarityResult:
    artist1: str
    artist2: str
    cosine_similarity: float

# --- Core Functions (Functional, Pure When Possible) ---

def get_artist_top_tracks(
    spotify: Spotify,
    artist_name: str,
    limit: int = 5
) -> list[TrackInfo]:
    """Fetch top tracks for an artist from Spotify"""
    # Implementation here
    pass

def download_audio_preview(preview_url: str, output_path: Path) -> bool:
    """Download 30s preview from Spotify"""
    # Implementation here
    pass

def extract_embedding(audio_path: Path) -> Optional[np.ndarray]:
    """Extract OpenL3 embedding from audio file"""
    # Implementation here
    pass

def compute_artist_embedding(
    spotify: Spotify,
    artist_name: str,
    cache_dir: Path
) -> Optional[ArtistEmbedding]:
    """
    Compute artist-level embedding by averaging track embeddings.

    Early exit pattern:
    - Return None if artist not found
    - Return None if no tracks have previews
    - Return None if embedding extraction fails
    """
    log(f"Processing artist: {artist_name}")

    # Early exit: Get tracks
    tracks = get_artist_top_tracks(spotify, artist_name)
    if not tracks:
        log(f"  ❌ No tracks found for {artist_name}")
        return None

    # Early exit: Filter tracks with previews
    tracks_with_previews = [t for t in tracks if t.preview_url]
    if not tracks_with_previews:
        log(f"  ❌ No preview URLs available for {artist_name}")
        return None

    log(f"  Found {len(tracks_with_previews)} tracks with previews")

    # Extract embeddings for each track
    embeddings = []
    track_names = []
    track_ids = []

    for track in tracks_with_previews:
        audio_path = cache_dir / f"{track.spotify_id}.mp3"

        # Download if not cached
        if not audio_path.exists():
            success = download_audio_preview(track.preview_url, audio_path)
            if not success:
                log(f"    ⚠️  Failed to download: {track.name}")
                continue

        # Extract embedding
        emb = extract_embedding(audio_path)
        if emb is not None:
            embeddings.append(emb)
            track_names.append(track.name)
            track_ids.append(track.spotify_id)
            log(f"    ✓ Extracted embedding for: {track.name}")
        else:
            log(f"    ⚠️  Failed to extract embedding: {track.name}")

    # Early exit: Need at least one successful embedding
    if not embeddings:
        log(f"  ❌ No successful embeddings for {artist_name}")
        return None

    # Average embeddings to get artist-level representation
    avg_embedding = np.mean(embeddings, axis=0)

    log(f"  ✓ Computed artist embedding from {len(embeddings)} tracks")

    return ArtistEmbedding(
        artist_name=artist_name,
        embedding=avg_embedding,
        tracks_used=track_names,
        spotify_ids=track_ids,
        computed_at=datetime.now().isoformat(),
        model="openl3"
    )

def compute_cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """Compute cosine similarity between two embeddings"""
    from sklearn.metrics.pairwise import cosine_similarity
    return float(cosine_similarity([emb1], [emb2])[0, 0])

def load_music_map_data(artist_name: str) -> Optional[list[str]]:
    """Load similar artists from music-map.com data"""
    # Load from output/similar_artists_map.json
    # Return list of similar artist names
    pass

def validate_embeddings_vs_music_map(
    embeddings_db: dict[str, ArtistEmbedding],
    music_map_data: dict[str, list[str]]
) -> dict[str, any]:
    """
    Compare embedding-based similarity to music-map.com ground truth.

    Returns validation metrics:
    - correlation: Pearson correlation coefficient
    - top5_overlap: Average overlap of top-5 similar artists
    - top10_overlap: Average overlap of top-10 similar artists
    """
    log("\n=== Validation: Embeddings vs Music-Map ===")

    # Implementation here
    pass

# --- Main Execution ---

def run_spike() -> None:
    """Main spike execution - all logging to file"""
    log("=" * 80)
    log("EMBEDDINGS SPIKE - START")
    log("=" * 80)

    try:
        # 1. Setup
        log("\n[1/5] Setting up Spotify client...")
        # Implementation

        # 2. Select test artists
        log("\n[2/5] Selecting test artists...")
        # Implementation

        # 3. Extract embeddings
        log("\n[3/5] Extracting embeddings...")
        # Implementation

        # 4. Compute similarities
        log("\n[4/5] Computing pairwise similarities...")
        # Implementation

        # 5. Validate against music-map.com
        log("\n[5/5] Validating against music-map.com data...")
        # Implementation

        log("\n" + "=" * 80)
        log("EMBEDDINGS SPIKE - COMPLETE")
        log("=" * 80)

    except Exception as e:
        log(f"\n❌ FATAL ERROR: {str(e)}")
        import traceback
        log(traceback.format_exc())
        raise

if __name__ == "__main__":
    run_spike()
```

## Logging Requirements (CRITICAL)

### Adherence to CLAUDE.md Standards

1. ✅ **NO print() statements** - Ruff will enforce this (T201 rule)
2. ✅ **All output to log file** - `embeddings_experiments/logs/spike_YYYY-MM-DD.log`
3. ✅ **Logs committed to git** - For review after semi-autonomous execution
4. ✅ **Structured logging** - Include timestamps, progress markers, error details

### Log Output Structure

```
[2025-11-10 12:00:00] ================================================================================
[2025-11-10 12:00:00] EMBEDDINGS SPIKE - START
[2025-11-10 12:00:00] ================================================================================

[2025-11-10 12:00:05] [1/5] Setting up Spotify client...
[2025-11-10 12:00:06]   ✓ Spotify client initialized

[2025-11-10 12:00:06] [2/5] Selecting test artists...
[2025-11-10 12:00:07]   Selected artists: ['Artist1', 'Artist2', ...]

[2025-11-10 12:00:07] [3/5] Extracting embeddings...
[2025-11-10 12:00:08] Processing artist: Artist1
[2025-11-10 12:00:10]   Found 5 tracks with previews
[2025-11-10 12:00:15]     ✓ Extracted embedding for: Track Name 1
[2025-11-10 12:00:20]     ✓ Extracted embedding for: Track Name 2
...
[2025-11-10 12:00:50]   ✓ Computed artist embedding from 5 tracks

[2025-11-10 12:05:00] [4/5] Computing pairwise similarities...
[2025-11-10 12:05:01]   Artist1 <-> Artist2: 0.812
[2025-11-10 12:05:01]   Artist1 <-> Artist3: 0.654
...

[2025-11-10 12:05:30] [5/5] Validating against music-map.com data...
[2025-11-10 12:05:31]   Pearson correlation: 0.723
[2025-11-10 12:05:31]   Top-5 overlap: 62.5%
[2025-11-10 12:05:31]   Top-10 overlap: 58.3%

[2025-11-10 12:05:31] ================================================================================
[2025-11-10 12:05:31] EMBEDDINGS SPIKE - COMPLETE
[2025-11-10 12:05:31] ================================================================================
```

## Data Outputs

### 1. Embeddings Database
**File:** `embeddings_experiments/data/spike_embeddings.json`

```json
{
  "Artist Name": {
    "embedding": [0.123, 0.456, ...],
    "tracks_used": ["Track 1", "Track 2", "Track 3"],
    "spotify_ids": ["id1", "id2", "id3"],
    "computed_at": "2025-11-10T12:00:00",
    "model": "openl3"
  }
}
```

### 2. Similarity Matrix
**File:** `embeddings_experiments/data/spike_similarities.json`

```json
{
  "pairwise_similarities": [
    {"artist1": "A", "artist2": "B", "similarity": 0.812},
    {"artist1": "A", "artist2": "C", "similarity": 0.654}
  ]
}
```

### 3. Validation Results
**File:** `embeddings_experiments/data/spike_validation.json`

```json
{
  "metrics": {
    "pearson_correlation": 0.723,
    "top5_overlap_avg": 0.625,
    "top10_overlap_avg": 0.583
  },
  "per_artist_results": {
    "Artist1": {
      "music_map_top5": ["A", "B", "C", "D", "E"],
      "embedding_top5": ["A", "B", "F", "D", "G"],
      "overlap": 3,
      "overlap_pct": 0.6
    }
  }
}
```

## Execution Plan

### Pre-Spike Checklist

- [ ] Install dependencies: `uv add librosa soundfile numpy scikit-learn spotipy openl3`
- [ ] Set up Spotify API credentials (if not already configured)
- [ ] Create directory structure
- [ ] Verify music-map.com data is available at `output/similar_artists_map.json`

### Running the Spike

```bash
# Run spike (all output goes to log file)
uv run python -m embeddings_experiments.spike

# After completion, review logs
cat embeddings_experiments/logs/spike_2025-11-10.log

# Review results
cat embeddings_experiments/data/spike_validation.json
```

### Post-Spike Review

1. **Check success criteria:**
   - Extraction rate ≥ 85%?
   - Correlation ≥ 0.6?
   - Top-5 overlap ≥ 50%?

2. **Manual validation:**
   - Do similar artists make musical sense?
   - Any surprising results (good or bad)?

3. **Decision point:**
   - ✅ **Success:** Proceed to Phase 2 (unknown artists)
   - ⚠️ **Partial success:** Tune parameters, try different model
   - ❌ **Failure:** Investigate issues, consider alternative approaches

## Time Estimate

- **Setup:** 15 minutes (dependencies, Spotify API)
- **Implementation:** 2-3 hours (spike.py script)
- **Execution:** 30-45 minutes (10 artists, ~3 min each)
- **Review:** 30 minutes (analyze logs and results)

**Total:** ~4-5 hours for complete spike

## Next Steps After Spike

Based on spike results:

1. **If successful:** Plan Phase 2 (unknown artists testing)
2. **If needs tuning:** Iterate on parameters, model selection
3. **If failed:** Reassess approach, consider alternative strategies

## Notes

- This is a **proof of concept** - code quality is good but not production-ready
- Focus on **validation** - does the approach work?
- **Log everything** - we may not watch this run in real-time
- **Commit logs** - preserve execution history for future reference
