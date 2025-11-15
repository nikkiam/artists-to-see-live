# Audio Embeddings Experiments

This directory contains experimental work exploring audio embeddings as an alternative/supplement to music-map.com for artist similarity.

## Motivation

The main project uses music-map.com to find similar artists, but this has a critical limitation: **niche, new, or underground artists may not be in the database**. Audio embeddings can help us recommend events for these unknown artists.

## Current Status

✅ **COMPLETED** - Spike 6 validated MERT-v1-95M with full 30-second context

**Final Results:**
- ✅ **72% better discrimination** vs chunked approach (Spike 5)
- ✅ **Layer 11 identified as optimal** (0.280 similarity span)
- ✅ **Subgenre detection works** (Bass ↔ Minimal: 0.493 similarity)
- ❌ **0% music-map overlap** (audio ≠ artist network similarity)

**Recommendation:** Use MERT Layer 11 as **secondary signal** for new/niche artists, music-map.com as primary.

## Project Structure

```
embeddings_experiments/
├── README.md                    # This file
├── CLEANUP_PLAN.md             # Cleanup documentation
├── scripts/                     # Production scripts
│   ├── spike_6_mert_hf.py      # ⭐ Main MERT implementation (Layer 11)
│   ├── mert_server.py          # FastAPI inference server
│   ├── analyze_spike_6.py      # Comprehensive analysis tool
│   └── find_artist_ids.py      # Artist ID disambiguation utility
├── docker/                      # Deployment configuration
│   ├── Dockerfile              # MERT inference endpoint image
│   ├── DEPLOYMENT_GUIDE.md     # Deployment instructions
│   ├── GITHUB_ACTION_SETUP.md  # GitHub Actions setup
│   ├── DEPLOYMENT_OPTIONS.md   # Options comparison
│   ├── DEPLOYMENT_SUMMARY.md   # Spike 6 deployment summary
│   └── QUICK_START.md          # Quick start guide
├── docs/                        # Documentation and results
│   ├── SPIKE_6_RESULTS.md      # ⭐ Final results and recommendations
│   ├── SPIKE_6_PLAN.md         # Spike 6 approach and rationale
│   ├── SPIKE_5_RESULTS.md      # Why chunking failed
│   ├── SPIKE_5_PLAN.md         # Spike 5 planning
│   ├── SPIKE_4_RESULTS.md      # VGGish baseline results
│   ├── SPIKE_COMPARISON.md     # Spikes 1-3 comparison
│   └── recommendations.md      # Architecture recommendations
├── data/                        # Embeddings and analysis data
│   ├── spike_6_track_embeddings.json       # 40 tracks × 13 layers (12MB)
│   ├── spike_6_layer_similarities.json     # Per-layer similarities (89KB)
│   ├── spike_6_embedding_cache.json        # Inference cache (12MB)
│   ├── spike_6_detailed_analysis.json      # Analysis results
│   ├── spike_5_similarities.json           # Chunked baseline
│   ├── spike_4_similarities.json           # VGGish baseline
│   ├── artist_id_mapping.json              # Artist disambiguation
│   └── audio_cache/                        # Downloaded audio clips
└── logs/                        # Execution logs
```

## Quick Start

### Running MERT Layer 11 Inference

```bash
# Set up HuggingFace Inference Endpoint
# See docker/DEPLOYMENT_GUIDE.md for full setup

# Run inference on test artists
cd scripts
python spike_6_mert_hf.py

# Analyze results
python analyze_spike_6.py

# Review results
cat ../docs/SPIKE_6_RESULTS.md
```

### Using MERT in Production

```python
from scripts.spike_6_mert_hf import extract_mert_embeddings_layer_11

# Extract Layer 11 embeddings for an artist's tracks
embeddings = extract_mert_embeddings_layer_11(
    artist_name="Vril",
    track_paths=["track1.mp3", "track2.mp3", ...],
    endpoint_url="https://YOUR-ENDPOINT.endpoints.huggingface.cloud"
)

# Compute similarity
from sklearn.metrics.pairwise import cosine_similarity
similarity = cosine_similarity([embedding1], [embedding2])[0][0]
```

### Hybrid Similarity (Recommended)

```python
def compute_artist_similarity(artist1, artist2):
    """
    Hybrid similarity combining multiple signals.
    """
    # Get MERT audio similarity (Layer 11)
    audio_sim = mert_layer_11_similarity(artist1, artist2)

    # Get music-map similarity (when available)
    music_map_sim = get_music_map_similarity(artist1, artist2)

    # Get genre similarity
    genre_sim = genre_jaccard_similarity(artist1.genres, artist2.genres)

    # Weighted combination
    if music_map_sim is not None:
        return (
            0.3 * audio_sim +        # Audio production similarity
            0.3 * music_map_sim +    # Artist network similarity
            0.2 * genre_sim +        # Genre tags
            0.2 * collab_network     # Collaboration graph
        )
    else:
        # Fallback for new/niche artists not in music-map
        return (
            0.5 * audio_sim +        # Audio is primary signal
            0.3 * genre_sim +        # Genre tags
            0.2 * collab_network     # Collaboration graph
        )
```

## Experiment Timeline

### Spike 1: Random Baseline
- **Approach:** Random track selection + YouTube search
- **Result:** 0.14 similarity span (too narrow)

### Spike 2: YouTube Topic Search
- **Approach:** YouTube "topic" channel search
- **Result:** 37.5% wrong artists (name ambiguity)

### Spike 3: Spotify-Guided YouTube
- **Approach:** Spotify API + YouTube audio
- **Result:** 75% accuracy, but still ambiguity issues

### Spike 4: VGGish with Artist ID Mapping ✅
- **Approach:** Manual artist ID mapping + VGGish embeddings
- **Result:** 100% accuracy, 0.263 span, but 0% music-map overlap
- **Conclusion:** VGGish can't distinguish electronic subgenres

### Spike 5: MERT with Chunking ❌
- **Approach:** MERT-v1-95M on M1 Mac (10s chunks due to memory limits)
- **Result:** 0.163 span (38% WORSE than VGGish!)
- **Conclusion:** Chunking destroyed temporal coherence

### Spike 6: MERT with Full Context ✅ SUCCESS
- **Approach:** MERT-v1-95M on HuggingFace Endpoints (full 30s context)
- **Result:** 0.280 span (72% improvement over chunked)
- **Key Finding:** Layer 11 optimal, not final layer
- **Conclusion:** MERT viable for audio similarity, but 0% music-map overlap

## Key Learnings

### What Works ✅
1. **MERT Layer 11 with full 30-second context** - Best audio similarity model
2. **Manual artist ID mapping** - Prevents wrong artist matches
3. **HuggingFace Inference Endpoints** - Affordable GPU access ($1.05/hr)
4. **Hybrid approach** - Combine audio + network signals

### What Doesn't Work ❌
1. **VGGish** - Can't distinguish electronic subgenres
2. **MERT with chunking** - Destroys temporal coherence
3. **YouTube topic search** - Name ambiguity causes pollution
4. **Audio-only for music-map overlap** - Audio ≠ artist network

### Surprising Results 🤔
1. **0% music-map overlap across ALL spikes** - Audio and network similarity are orthogonal
2. **Layer 11 > Layer 13** - Earlier transformer layers more discriminative
3. **Early layers (1-2) perform well** - Not just final layers useful

## Cost Analysis

### Per-Artist Cost (MERT Layer 11)
- 5 tracks × 30s per track
- ~10 seconds inference on A10G GPU
- Cost: **~$0.0003 per artist**

### Production Scale
- 1,000 artists: **~$0.30**
- 10,000 artists: **~$3.00**

**Affordable for production use!**

## When to Use MERT vs Music-Map

### Use MERT Layer 11 when:
- 🆕 Artist is new/unknown (not in music-map)
- 🎵 Want to find similar **sound/production** style
- 🎛️ Need to distinguish electronic **subgenres**
- 🌍 Working with niche/underground artists

### Use Music-Map when:
- 🎤 Artist is established (in music-map database)
- 🤝 Want to find similar **scene/network** relationships
- 🏷️ Touring/collaboration relationships matter
- 👥 User listening patterns are relevant

### Best Approach: Use Both
Hybrid similarity combining MERT + music-map + genres provides best results.

## References

### Documentation
- **Spike 6 Results:** `docs/SPIKE_6_RESULTS.md` (comprehensive analysis)
- **Deployment Guide:** `docker/DEPLOYMENT_GUIDE.md`
- **Original Plan:** `docs/recommendations.md`

### Models
- **MERT-v1-95M:** https://huggingface.co/m-a-p/MERT-v1-95M
- **HuggingFace Endpoints:** https://huggingface.co/docs/inference-endpoints/

### Papers
- MERT: "MERT: Acoustic Music Understanding Model with Large-Scale Self-supervised Training"
- Music Similarity: "Audio-based Music Similarity and Retrieval"

## Next Steps

**If continuing with MERT:**
1. Test on 100+ artists to validate Layer 11 selection
2. Implement hybrid pipeline combining MERT + music-map + genres
3. A/B test against music-map-only recommendations
4. Cache embeddings to reduce API costs

**Alternative: Metadata-Only**
If MERT overhead too high, use genre tags + collaboration network + music-map (when available).

---

**Status:** ✅ Experiments complete, production-ready recommendation available
**Date:** 2025-11-15
**Recommended Approach:** Hybrid (MERT Layer 11 + Music-Map + Genres)
