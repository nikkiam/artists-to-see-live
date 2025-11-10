# Audio Embeddings Experiments

This directory contains experimental work exploring audio embeddings as an alternative/supplement to music-map.com for artist similarity.

## Motivation

The main project uses music-map.com to find similar artists, but this has a critical limitation: **niche, new, or underground artists may not be in the database**. Audio embeddings can help us recommend events for these unknown artists.

## Approach

Use pre-trained audio models (OpenL3) to extract features directly from Spotify track previews, then compute artist similarity via cosine distance on embedding vectors.

**Key insight:** We don't need tags or metadata - just the audio itself!

## Files in This Directory

- **recommendations.md** - Full technical writeup of the embedding approach
- **spike_plan.md** - Detailed implementation plan for proof-of-concept work
- **README.md** - This file

## Current Status

📋 **Planning Phase** - Spike work not yet started

## Quick Start (When Ready)

```bash
# Install dependencies
uv add librosa soundfile numpy scikit-learn spotipy openl3

# Run spike
uv run python -m embeddings_experiments.spike

# Review results
cat embeddings_experiments/logs/spike_$(date +%Y-%m-%d).log
cat embeddings_experiments/data/spike_validation.json
```

## Success Criteria for Spike

- ✅ Embedding extraction works for ≥85% of test artists
- ✅ Similarity correlation with music-map.com ≥ 0.6
- ✅ Top-5 overlap with music-map.com ≥ 50%
- ✅ Follows project standards (file logging, typed dataclasses, functional style)

## References

- Paper: "Few-Shot Learning for Multi-Label Music Auto-Tagging" (2024)
- OpenL3: https://github.com/marl/openl3
- Spotify Web API: https://developer.spotify.com/documentation/web-api/
