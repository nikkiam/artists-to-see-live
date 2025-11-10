# Audio Embeddings for Artist Similarity - Technical Recommendations

## Problem Statement

The current project uses music-map.com to find similar artists, but this approach has limitations:
- **Coverage gap**: Niche, new, or underground artists may not be in music-map.com's database
- **Discovery limitation**: We miss recommending events for unknown artists that users might like

## Proposed Solution: Direct Embedding Similarity

Use pre-trained audio models to compute similarity directly from audio tracks, bypassing the need for existing metadata or tags.

## Why Embeddings Over Tags?

The paper "Few-Shot Learning for Multi-Label Music Auto-Tagging" demonstrates that pre-trained models (VGGish, OpenL3, PaSST) can extract meaningful audio features. However, for our use case:

- ✅ **We don't need the tagging layer** - Tags were an intermediate representation for interpretability
- ✅ **Direct embeddings work better** - Compute similarity directly on feature vectors
- ✅ **No training data required** - Pre-trained models work out-of-the-box on any audio
- ✅ **Handles unknown artists** - As long as tracks exist on Spotify/SoundCloud

## Technical Architecture

### Pipeline Overview

```
Email Parsing → Artist Extraction → Track Lookup (Spotify) →
Audio Download (30s previews) → Embedding Extraction →
Similarity Computation → Event Recommendations
```

### Core Components

1. **Track Lookup Layer**
   - Input: Artist name from email scraper
   - Use Spotify API to find top tracks
   - Get 30-second preview URLs (available for most tracks)
   - Fallback: Check SoundCloud if Spotify preview unavailable

2. **Embedding Extraction**
   - Download audio previews (30s sufficient for embeddings)
   - Load audio with librosa (16kHz for VGGish, 48kHz for others)
   - Pass through pre-trained model (OpenL3, VGGish, or PaSST)
   - Output: Fixed-size embedding vector (dimensionality depends on model)

3. **Artist-Level Aggregation**
   - Extract embeddings for multiple tracks per artist (recommend 3-5)
   - Average track embeddings to get artist-level representation
   - Store in embeddings database for reuse

4. **Similarity Computation**
   - Use cosine similarity between embedding vectors
   - Threshold: similarity > 0.7 suggests strong match (tune empirically)
   - Return top-k most similar known artists

## Model Selection

### Recommended: OpenL3 (Start Here)

**Pros:**
- Easy installation: `pip install openl3`
- Well-documented API
- Good performance/complexity tradeoff
- Active community support
- Outputs 512-dim or 6144-dim embeddings

**Usage:**
```python
import openl3
import soundfile as sf

audio, sr = sf.read('track.mp3')
emb, ts = openl3.get_audio_embedding(audio, sr, content_type="music")
```

### Alternative: VGGish

**Pros:**
- Lightweight (128-dim embeddings)
- Fast inference
- Google AudioSet pre-trained

**Cons:**
- Slightly lower performance than OpenL3
- Requires TensorFlow 1.x (compatibility issues)

### Advanced: PaSST (Future Work)

**Pros:**
- State-of-the-art performance
- Transformer-based architecture

**Cons:**
- More computationally expensive
- Harder to set up
- Overkill for POC

## Data Storage Strategy

### Embeddings Database Structure

```python
# embeddings_experiments/embeddings_db.json
{
    "artist_name": {
        "embedding": [0.123, 0.456, ...],  # 512-dim vector
        "tracks_used": ["Track 1", "Track 2", "Track 3"],
        "spotify_ids": ["id1", "id2", "id3"],
        "computed_at": "2025-11-10T12:00:00",
        "model": "openl3"
    }
}
```

### Integration with Existing Data

- Embeddings stored separately from music-map.com data
- Can compute similarity for both known and unknown artists
- Use music-map.com as ground truth for validation
- Hybrid approach: Use music-map.com when available, embeddings for unknowns

## Proof of Concept Plan

### Phase 1: Validation (Spike Work)

**Goal:** Verify embeddings correlate with music-map.com similarity

**Steps:**
1. Select 10 known artists from existing music-map.com data
2. Extract embeddings for each artist (3-5 tracks per artist)
3. Compute pairwise cosine similarities
4. Compare to music-map.com similar artist lists
5. **Success criteria:** Top-5 similar artists overlap >50% with music-map.com

### Phase 2: Unknown Artist Testing

**Goal:** Test on artists not in music-map.com

**Steps:**
1. Identify 3-5 niche/new artists from recent emails
2. Extract embeddings
3. Find top-10 similar known artists
4. **Manual validation:** Do results make sense musically? (Use DJ intuition)

### Phase 3: Integration

**Goal:** Integrate into production pipeline

**Steps:**
1. Build embeddings for all known artists (~1300+ artists)
2. Add embedding extraction to email scraping pipeline
3. Implement hybrid similarity: music-map.com + embeddings
4. Store embeddings in version-controlled JSON

## Implementation Considerations

### Spotify API Access

- **Existing integration:** Project already has Spotify playlist extraction
- **Rate limits:** 10,000 requests/day (more than sufficient)
- **Preview availability:** ~80-90% of tracks have 30s previews
- **Fallback:** Try multiple tracks per artist if preview unavailable

### Computational Requirements

- **OpenL3 inference:** ~0.5-1 second per 30s audio clip (CPU)
- **Batch processing:** Can process 100 artists in ~10 minutes
- **Storage:** 512 floats × 1300 artists = ~2.6MB (negligible)

### Logging Requirements (Per Project Standards)

- **No print() statements** - Use file logging
- **Log to:** `embeddings_experiments/logs/spike_YYYY-MM-DD.log`
- **Commit logs** to git for review after semi-autonomous runs
- **Log entries:**
  - Artist name being processed
  - Number of tracks found/used
  - Embedding extraction success/failure
  - Similarity scores for validation
  - Any errors/fallbacks

### Error Handling

- Artist not found on Spotify → Log and skip
- No audio previews available → Try more tracks, log if all fail
- Audio processing error → Log exception, continue with next artist
- Model loading failure → Fatal error, stop execution

## Success Metrics

### Quantitative
- **Embedding extraction success rate** > 85% (for artists with Spotify presence)
- **Similarity correlation** with music-map.com > 0.6 (Pearson correlation)
- **Top-5 overlap** with music-map.com > 50%

### Qualitative
- **Musical coherence:** Do similar artists "make sense" to a DJ?
- **Genre consistency:** Artists in same cluster share genre characteristics
- **Usefulness:** Would you book/attend events based on these recommendations?

## Future Enhancements

1. **Multi-model ensemble:** Combine VGGish + OpenL3 + PaSST for better accuracy
2. **Fine-tuning:** Train model on your specific music taste/genre
3. **Temporal analysis:** Track how artist similarity evolves over time
4. **Playlist generation:** Auto-generate Spotify playlists based on similarity
5. **Event recommendation engine:** "You liked Artist X, here are upcoming shows"

## References

- Paper: "Few-Shot Learning for Multi-Label Music Auto-Tagging" (2024)
- OpenL3: https://github.com/marl/openl3
- VGGish: https://github.com/tensorflow/models/tree/master/research/audioset/vggish
- Spotify Web API: https://developer.spotify.com/documentation/web-api/
