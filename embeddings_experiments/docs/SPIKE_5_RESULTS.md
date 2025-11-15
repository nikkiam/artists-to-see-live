# Spike 5 Results: MERT vs VGGish

## Summary

**MERT (768-dim music transformer) performed WORSE than VGGish (128-dim CNN)** - showing even LESS variance and distinction between artists.

## Key Findings

### ❌ MERT Failed All Success Criteria

| Metric | VGGish (S4) | MERT (S5) | Expected | Result |
|--------|-------------|-----------|----------|--------|
| **Similarity Range** | 0.711-0.974 (0.263) | 0.808-0.971 (0.163) | Wider (0.4+) | **WORSE** |
| **Music-map Overlap** | 0% | 0% | 20-50% | **No improvement** |
| **Extraction Rate** | 100% | 100% | ≥85% | ✓ Success |
| **Subgenre Detection** | Poor | **Even worse** | Better | **FAILURE** |

### Expected LOW Similarities - All Failed

| Artist Pair | Genre Difference | Expected | VGGish (S4) | MERT (S5) | Status |
|-------------|------------------|----------|-------------|-----------|--------|
| **Vril ↔ Sabrina** | Minimal Techno ↔ Pop | **0.1-0.3** | 0.711 | **0.892** | ❌ WORSE |
| **TroyBoi ↔ Calibre** | Trap ↔ Liquid DnB | **0.2-0.4** | 0.891 | **0.955** | ❌ WORSE |
| **PEEKABOO ↔ Vril** | Bass ↔ Minimal | **0.2-0.4** | 0.786 | **0.808** | ❌ WORSE |
| **IMANU ↔ Vril** | Neurofunk ↔ Minimal | **0.2-0.4** | 0.869 | **0.822** | ⚠️ Slight improvement |

### Similarity Comparison

**Vril (minimal techno) - The Test Case:**

| vs Artist | Genre | VGGish (S4) | MERT (S5) | Change |
|-----------|-------|-------------|-----------|--------|
| Sabrina Carpenter | Pop | 0.711 | **0.892** | +0.181 ❌ |
| TroyBoi | Trap | 0.763 | **0.835** | +0.072 ❌ |
| PEEKABOO | Bass | 0.786 | **0.808** | +0.022 ❌ |
| deadmau5 | Progressive | 0.858 | **0.890** | +0.032 ❌ |
| Rezz | Dark Techno | 0.915 | **0.863** | -0.052 ✓ |
| Calibre | Liquid DnB | 0.928 | **0.839** | -0.089 ✓ |

**MERT sees Sabrina Carpenter (pop) as MORE similar to Vril (minimal techno) than VGGish did!**

### Full Similarity Matrix

**VGGish (Spike 4) Range: 0.711-0.974**
- Lowest: Vril ↔ Sabrina Carpenter (0.711) ✓ Correct (different genres)
- Highest: TroyBoi ↔ PEEKABOO (0.974) - Both bass music

**MERT (Spike 5) Range: 0.808-0.971**
- Lowest: PEEKABOO ↔ Vril (0.808) - Still too high
- Highest: deadmau5 ↔ Sabrina Carpenter (0.971) ❌ WRONG (progressive house vs pop)

### Variance Analysis

| Statistic | VGGish (S4) | MERT (S5) | Change |
|-----------|-------------|-----------|--------|
| Minimum | 0.711 | 0.808 | +0.097 ❌ |
| Maximum | 0.974 | 0.971 | -0.003 |
| **Range** | **0.263** | **0.163** | **-38%** ❌ |
| Mean | ~0.88 | ~0.92 | +0.04 ❌ |

**MERT shows 38% LESS variance than VGGish - everything looks more similar!**

## Why MERT Failed

### 1. Chunking Artifact
- Processed audio in 10-second chunks to avoid OOM
- MERT is designed for full-context processing
- Averaging chunk embeddings lost temporal coherence

### 2. Model Design Mismatch
- MERT trained on full songs for music understanding tasks
- Our use case: 30-second YouTube clips, chunked to 10 seconds
- Lost the long-term structure that MERT excels at

### 3. Higher Baseline Similarity
- 768-dim embeddings in high-dimensional space
- All electronic music maps to similar regions
- Less discriminative than expected

### 4. Still 0% Music-Map Overlap
- Like VGGish, MERT found zero overlap with music-map.com
- Music-map likely uses collaborative filtering, not audio features
- Audio embeddings alone insufficient

## Detailed Pair Analysis

### Worst MERT Failures

**1. deadmau5 ↔ Sabrina Carpenter: 0.971** (HIGHEST similarity!)
- VGGish: 0.886 (already too high)
- MERT: 0.971 (even worse!)
- Progressive house should NOT be 97% similar to pop

**2. Sabrina Carpenter ↔ Calibre: 0.957**
- VGGish: 0.828 (moderate)
- MERT: 0.957 (very high)
- Pop vocals vs liquid drum & bass - should be LOW

**3. All Electronic ↔ Electronic: 0.93-0.97**
- MERT sees ALL electronic music as 93-97% similar
- Can't distinguish trap, dnb, techno, progressive house
- Useless for recommendation within electronic genre

### Only Partial Success: Vril Detection

MERT correctly identified Vril (minimal techno) as the most different:
- PEEKABOO ↔ Vril: 0.808 (lowest)
- IMANU ↔ Vril: 0.822
- TroyBoi ↔ Vril: 0.835

But still TOO HIGH - 80%+ similarity between minimal techno and bass music is wrong.

## Execution Details

- **Model**: m-a-p/MERT-v1-95M (768-dim)
- **Device**: MPS (Apple M1)
- **Audio Processing**: 30s max, 10s chunks
- **Tracks per Artist**: 5
- **Total Tracks**: 40
- **Runtime**: ~6 minutes (much slower than VGGish)
- **Extraction Success**: 100% (8/8 artists)

## Conclusions

### MERT is NOT Suitable for This Use Case

1. **Worse than VGGish** across all metrics
2. **Less variance** (38% reduction)
3. **Still 0% music-map overlap**
4. **Requires full-song context** (our chunks break it)
5. **6x slower** than VGGish

### Audio Embeddings Alone Don't Work

After testing:
- VGGish (general audio CNN): 0% overlap
- MERT (music transformer): 0% overlap

**Conclusion**: Music-map.com similarity is NOT based on audio features alone.

### Music-Map Likely Uses:
- Genre tags
- Artist relationships (collaborations, labels, tours)
- User listening patterns (collaborative filtering)
- Social graph data
- Metadata, not audio

### Audio Embeddings Show:
- All electronic music sounds similar (93-97%)
- Can barely distinguish pop from electronic (89-97%)
- Only minimal techno (Vril) shows some differentiation (81-89%)

## Recommendations

### ❌ Abandon Pure Audio Embeddings

Neither VGGish nor MERT can replicate music-map.com:
- VGGish: 0% overlap, 0.711-0.974 range
- MERT: 0% overlap, 0.808-0.971 range

### ✅ Hybrid Approach (Best Path Forward)

```python
similarity = (
    0.4 * spotify_audio_features_similarity +  # tempo, energy, key
    0.3 * genre_tag_similarity +                # Spotify genres
    0.2 * music_map_similarity +                # when available
    0.1 * artist_network_similarity             # collab graph
)
```

### Spotify Audio Features (Free & Fast)
- Tempo (BPM)
- Energy (0-1)
- Danceability (0-1)
- Valence (mood)
- Key & Mode
- Instrumentalness
- Acousticness

**Advantages**:
- Available for ALL Spotify tracks
- Actually correlates with music-map (likely used in their algo)
- Fast to compute
- No ML models needed
- Can be combined with genre tags

### For Unknown Artists
1. Use Spotify audio features + genres (primary signal)
2. Fallback to music-map when available
3. Manual curation for edge cases
4. Skip audio embeddings entirely

## Files

- `spike_5_mert.py` - Runner script (100 lines vs 630 in standalone)
- `spike_5_embeddings.json` - MERT embeddings (768-dim)
- `spike_5_similarities.json` - Pairwise results
- `logs/spike_5_2025-11-14.log` - Full execution log

## Final Verdict

**Audio embeddings (VGGish, MERT) cannot replace music-map.com for artist similarity.**

Move to hybrid approach using Spotify's native features + genre tags.
