# Spike 5 Plan: Discogs-Effnet Embeddings

## Objective

Test **Essentia's Discogs-Effnet** model as an alternative to VGGish for artist similarity detection.

## Why Discogs-Effnet?

### VGGish Limitations (from Spike 4)
- ❌ Trained on AudioSet (general audio, not music-specific)
- ❌ Can't distinguish electronic subgenres (all 0.7-0.97 similarity)
- ❌ 0% overlap with music-map.com
- ✅ Only detects broad differences (minimal techno vs pop: 0.711)

### Discogs-Effnet Advantages (Opus 4.1 Recommendation #2)
- ✅ **Trained on 1.8M tracks from Discogs** (electronic music heavy!)
- ✅ **Specifically designed for music similarity** (not general audio)
- ✅ **Lighter weight than transformers** (fast on your RTX 2060)
- ✅ **Available through Essentia** (well-maintained, easy to use)
- ✅ **Artist-specific embeddings** available (discogs_artist_embeddings model)

## Implementation Strategy

### Keep VGGish Code (Comparison)
- Don't remove VGGish functions
- Add new Discogs-Effnet functions alongside
- Allows direct comparison of results

### New Functions to Add
1. `load_discogs_model()` - Load Essentia model
2. `extract_discogs_embedding()` - Extract embedding from audio
3. `compute_artist_embedding_discogs()` - Artist-level embedding using Discogs model
4. Runner script that uses Discogs instead of VGGish

## Technical Details

### Installation
```bash
uv add essentia-tensorflow
```

### Model File
- **Artist embeddings**: `discogs_artist_embeddings-effnet-bs64-1.pb`
- Downloaded automatically by Essentia on first use
- Size: ~50MB

### Audio Requirements
- **Sample rate**: 16000 Hz (same as VGGish)
- **Format**: Mono WAV
- **Processing**: Uses `MonoLoader` from Essentia

### Embedding Output
- **Dimensions**: TBD (likely 128 or 256-dim, similar to VGGish)
- **Format**: NumPy array
- **Aggregation**: Mean pooling over time frames → single vector

## Code Changes

### 1. New Import
```python
from essentia.standard import MonoLoader, TensorflowPredictEffnetDiscogs
```

### 2. Load Model Function
```python
def load_discogs_model() -> TensorflowPredictEffnetDiscogs:
    """Load Discogs-Effnet artist embeddings model from Essentia.

    Model will be downloaded automatically on first use.
    """
    log("  Loading Discogs-Effnet artist embeddings model...")

    model = TensorflowPredictEffnetDiscogs(
        graphFilename="discogs_artist_embeddings-effnet-bs64-1.pb",
        output="PartitionedCall:1"
    )

    log("  ✓ Discogs-Effnet model loaded")
    return model
```

### 3. Extract Embedding Function
```python
def extract_discogs_embedding(
    audio_path: Path,
    model: TensorflowPredictEffnetDiscogs
) -> Optional[np.ndarray]:
    """Extract Discogs-Effnet embedding from audio file.

    Essentia expects:
    - 16kHz mono audio
    - Returns embeddings per frame (similar to VGGish)
    """
    try:
        # Load audio at 16kHz (Discogs-Effnet requirement)
        loader = MonoLoader(
            filename=str(audio_path),
            sampleRate=16000,
            resampleQuality=4
        )
        audio = loader()

        # Extract embeddings - returns (num_frames, embedding_dim)
        embeddings = model(audio)

        # Average over time frames to get single vector
        embedding_avg = np.mean(embeddings, axis=0)

        return embedding_avg

    except Exception as e:
        log(f"      ⚠️  Discogs embedding extraction failed: {e}")
        return None
```

### 4. Artist Embedding Function
```python
def compute_artist_embedding_discogs(
    artist_name: str,
    cache_dir: Path,
    discogs_model: TensorflowPredictEffnetDiscogs,
    spotify_client: spotipy.Spotify,
    artist_id_mapping: dict[str, str] = None
) -> Optional[ArtistEmbedding]:
    """
    Compute artist-level embedding using Discogs-Effnet model.

    Uses same Spotify-guided YouTube search as Spike 4 (v2 approach).
    Only difference: uses Discogs-Effnet instead of VGGish for embedding extraction.
    """
    log(f"Processing artist: {artist_name}")

    # Get tracks from Spotify (same as v2)
    spotify_tracks = get_artist_top_tracks_spotify(
        spotify_client, artist_name, limit=5, artist_id_mapping=artist_id_mapping
    )

    if not spotify_tracks:
        log(f"  ❌ No tracks found on Spotify for {artist_name}")
        return None

    log(f"  Found {len(spotify_tracks)} tracks on Spotify")

    # Search YouTube and extract embeddings
    embeddings = []
    track_names = []
    track_ids = []

    for spotify_track in spotify_tracks:
        # Search YouTube (same as v2)
        youtube_track = search_youtube_for_track(
            spotify_track.artist_name,
            spotify_track.name
        )

        if not youtube_track:
            log(f"    ⚠️  YouTube search failed for: {spotify_track.name}")
            continue

        audio_path = cache_dir / f"{youtube_track.video_id}.wav"

        # Download if not cached (same as v2)
        if not audio_path.exists():
            if not download_youtube_audio(youtube_track.video_id, audio_path):
                continue

        # Extract embedding using Discogs-Effnet (NEW!)
        emb = extract_discogs_embedding(audio_path, discogs_model)
        if emb is not None:
            embeddings.append(emb)
            track_names.append(spotify_track.name)
            track_ids.append(spotify_track.spotify_id)
            log(f"    ✓ Extracted Discogs embedding for: {spotify_track.name}")

    # Early exit: Need at least one successful embedding
    if not embeddings:
        log(f"  ❌ No successful embeddings for {artist_name}")
        return None

    # Average embeddings
    avg_embedding = np.mean(embeddings, axis=0)

    log(f"  ✓ Computed artist embedding from {len(embeddings)} tracks")

    return ArtistEmbedding(
        artist_name=artist_name,
        embedding=avg_embedding.tolist(),
        tracks_used=track_names,
        spotify_ids=track_ids,
        computed_at=datetime.now().isoformat(),
        model="discogs-effnet-artist",  # NEW model name
    )
```

### 5. Spike Runner Script
Create `spike_5_discogs.py`:
```python
#!/usr/bin/env python3
"""
Spike 5: Test Discogs-Effnet embeddings vs VGGish.

Uses same 8 artists from Spike 4:
- deadmau5, Rezz, TroyBoi, IMANU, PEEKABOO, Sabrina Carpenter, Vril, Calibre

Saves results as spike_5_*.json for comparison.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from spike import (
    log, load_spotify_client, load_artist_id_mapping,
    compute_pairwise_similarities, validate_vs_music_map,
    load_music_map_data, load_discogs_model,
    compute_artist_embedding_discogs, ArtistEmbedding
)
import json
from dataclasses import asdict

def run_spike_5() -> None:
    """Run Spike 5 with Discogs-Effnet embeddings."""

    log("=" * 80)
    log("SPIKE 5: DISCOGS-EFFNET EMBEDDINGS")
    log("=" * 80)

    try:
        # Setup paths
        project_root = Path(__file__).parent.parent
        music_map_path = project_root / "output" / "similar_artists_map.json"
        cache_dir = Path(__file__).parent / "data" / "audio_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Test artists (same as Spike 4)
        test_artists = [
            "deadmau5", "Rezz", "TroyBoi", "IMANU",
            "PEEKABOO", "Sabrina Carpenter", "Vril", "Calibre"
        ]

        log(f"\n[1/5] Loading music-map data...")
        music_map_data = load_music_map_data(music_map_path)
        log(f"  Loaded {len(music_map_data)} artists from music-map.com")
        log(f"  Testing with {len(test_artists)} artists: {test_artists}")

        log("\n[2/5] Initializing Spotify client...")
        spotify_client = load_spotify_client()
        artist_id_mapping = load_artist_id_mapping()
        log("  ✓ Spotify client initialized")

        log("\n[3/5] Loading Discogs-Effnet model...")
        discogs_model = load_discogs_model()

        log("\n[4/5] Extracting embeddings with Discogs-Effnet...")
        embeddings_db = {}

        for artist in test_artists:
            emb = compute_artist_embedding_discogs(
                artist, cache_dir, discogs_model,
                spotify_client, artist_id_mapping
            )
            if emb:
                embeddings_db[artist] = emb

        log(f"\n  ✓ Extracted embeddings for {len(embeddings_db)}/{len(test_artists)} artists")

        log("\n[5/5] Computing similarities and validating...")
        similarities = compute_pairwise_similarities(embeddings_db)
        validation_results = validate_vs_music_map(
            embeddings_db, music_map_data, similarities
        )

        # Save results with spike_5 prefix
        output_dir = Path(__file__).parent / "data"

        embeddings_json = {name: asdict(emb) for name, emb in embeddings_db.items()}
        with open(output_dir / "spike_5_embeddings.json", "w", encoding="utf-8") as f:
            json.dump(embeddings_json, f, indent=2)

        similarities_json = [asdict(s) for s in similarities]
        with open(output_dir / "spike_5_similarities.json", "w", encoding="utf-8") as f:
            json.dump({"pairwise_similarities": similarities_json}, f, indent=2)

        with open(output_dir / "spike_5_validation.json", "w", encoding="utf-8") as f:
            json.dump(validation_results, f, indent=2)

        log("\n  ✓ Results saved to embeddings_experiments/data/spike_5_*.json")

        log("\n" + "=" * 80)
        log("SPIKE 5 COMPLETE")
        log("=" * 80)

    except Exception as e:
        log(f"\n❌ FATAL ERROR: {str(e)}")
        import traceback
        log(traceback.format_exc())
        raise

if __name__ == "__main__":
    # Suppress TensorFlow warnings
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

    run_spike_5()
```

## Expected Improvements Over VGGish

### Similarity Variance
- **VGGish Spike 4**: 0.711-0.974 (range: 0.263)
- **Expected Discogs**: 0.2-0.9 (range: 0.7) - wider variance

### Subgenre Detection
| Artist Pair | VGGish S4 | Expected Discogs | Reason |
|------------|-----------|------------------|--------|
| Vril ↔ Sabrina Carpenter | 0.711 | **0.1-0.3** | Techno ≠ Pop |
| Calibre ↔ Rezz | 0.962 | **0.3-0.5** | Liquid DnB ≠ Dark techno |
| TroyBoi ↔ Calibre | 0.891 | **0.2-0.4** | Trap ≠ Liquid DnB |
| deadmau5 ↔ Rezz | 0.920 | **0.6-0.8** | Both electronic, similar energy |

### Music-Map Overlap
- **VGGish**: 0%
- **Expected Discogs**: 20-50% (trained on music, should correlate better)

## Success Criteria

1. ✅ **Wider similarity variance** (range > 0.4)
2. ✅ **Better subgenre distinction** (electronic pairs show meaningful differences)
3. ✅ **Music-map overlap > 10%** (any improvement over VGGish)
4. ✅ **Extraction success rate ≥ 85%** (can reuse Spike 4 audio cache!)

## Execution Plan

### Step 1: Install Dependencies (5 min)
```bash
uv add essentia-tensorflow
```

### Step 2: Add Functions to spike.py (30 min)
- Add `load_discogs_model()`
- Add `extract_discogs_embedding()`
- Add `compute_artist_embedding_discogs()`

### Step 3: Create spike_5_discogs.py (15 min)
- Copy structure from spike.py's `run_spike()`
- Replace VGGish calls with Discogs calls

### Step 4: Run Spike 5 (20-30 min)
```bash
uv run python embeddings_experiments/spike_5_discogs.py
```

**Note**: Can reuse audio cache from Spike 4! Only embedding extraction is new.

### Step 5: Compare Results (30 min)
- Compare `spike_4_similarities.json` vs `spike_5_similarities.json`
- Look for improved variance and subgenre detection
- Document in `SPIKE_5_RESULTS.md`

**Total time: ~2 hours**

## Fallback Plan

If Discogs-Effnet also shows poor results:
- **Option 3**: Try MERT (transformer-based, state-of-the-art)
- **Option 4**: Hybrid approach (Spotify audio features + embeddings)
- **Option 5**: Abandon embeddings, use music-map.com + manual curation

## Files Created

- `SPIKE_5_PLAN.md` - This file
- `spike_5_discogs.py` - Runner script
- `data/spike_5_embeddings.json` - Results
- `data/spike_5_similarities.json` - Pairwise similarities
- `data/spike_5_validation.json` - Music-map comparison
- `SPIKE_5_RESULTS.md` - Analysis and comparison (after run)

## References

- Essentia models: https://essentia.upf.edu/models.html
- Discogs-Effnet paper: "Enriched Music Representations with Multiple Cross-modal Contrastive Learning" (2021)
- Discogs dataset: 1.8M tracks from Discogs (electronic music heavy)
