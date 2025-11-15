# Spike 6 Plan: MERT with HuggingFace Inference API

## Objective

Test MERT-v1-95M with **full 30-second context** using HuggingFace Inference API to properly evaluate if the poor Spike 5 results were due to chunking artifacts or fundamental model limitations.

## Background: Why Spike 6?

### Spike 5 Problem: Chunking Destroyed MERT

From SPIKE_5_MERT_RESULTS.md:
- MERT chunked to 10-second clips due to M1 MPS memory limits
- Averaging chunk embeddings destroyed temporal coherence
- Result: Everything 80-97% similar (no discrimination)
- **0% overlap with music-map.com**

### Question: Was chunking the problem?

MERT was **designed for full song context**. Spike 5's poor results could be due to:
1. **Chunking artifact** (fixable with more memory/GPU)
2. **Fundamental model limitation** (MERT doesn't capture artist similarity)

Spike 6 tests option #1 by running MERT with full 30s context on proper GPU infrastructure.

---

## Abandoned Approaches (Documented for Posterity)

### ❌ Approach A: Spotify Audio Features API

**Why it seemed good:**
- Fast, free, music-specific features (tempo, energy, danceability, etc.)
- Recommended in Spike 5 results as likely to correlate with music-map.com

**Why it failed:**
- Spotify **permanently deprecated** the `/v1/audio-features` endpoint (returns 403)
- No alternative API endpoint available
- Abandoned 2024-11-14

### ❌ Approach B: Kaggle Spotify Dataset

**Attempted workaround:**
- Use [Kaggle 12M Songs dataset](https://www.kaggle.com/datasets/rodolfofigueroa/spotify-12m-songs)
- 1.2M tracks with audio features extracted before API deprecation

**Why it failed:**
- Dataset from **December 2020** (4+ years old)
- Spotify "top tracks" API returns current popularity (2021-2024 tracks)
- **2% coverage** of test artists' current top tracks
- Even established artists (Taylor Swift, Kaskade) have 0% match
- Testing on 2020 data won't validate production app (needs current tracks)
- Abandoned 2024-11-14

**Key learning:** Audio features approach is no longer viable for new implementations.

---

## Approach: HuggingFace Inference API

### What is it?

- Serverless API to run ML models without local hardware
- Pay per compute-second
- Uses optimized GPU infrastructure (A100s/H100s)
- Supports MERT-v1-95M model

### Why this solves Spike 5's problem

✅ **Full 30-second context** (no chunking!)
✅ **Optimized GPU** (no M1 MPS memory limits)
✅ **Fast inference** (parallel processing)
✅ **Cheap** (~$0.08 for 40 tracks)

### Cost Analysis

Based on Spike 5 timing (61 minutes for 40 tracks):

**Local M1 Processing:**
- 40 tracks in 61 minutes
- 1.5 minutes per track
- Chunked to 10 seconds (temporal coherence lost)

**HuggingFace Inference API:**
- Estimated: 5-10 seconds per 30s track (A100 GPU)
- Full 30-second context preserved
- Parallel processing possible

**Pricing:**
- Standard Inference API: ~$0.00006/second (T4/A100)
- Per track (30s audio, ~10s processing): **~$0.0006**
- **40 tracks**: $0.024 (~2.4 cents)
- **1,000 artists × 5 tracks**: ~$3-5

### Implementation Strategy

```python
from huggingface_hub import InferenceClient
import librosa

# Initialize client
client = InferenceClient(token="hf_xxx")

def extract_mert_embedding_hf(audio_path: Path) -> np.ndarray:
    """Extract MERT embedding via HuggingFace Inference API."""

    # Load full 30-second clip (no chunking!)
    audio, sr = librosa.load(audio_path, sr=24000, duration=30.0)

    # Send to HF Inference API
    # Note: May need to send as base64 or use specific format
    result = client.feature_extraction(
        audio.tolist(),
        model="m-a-p/MERT-v1-95M"
    )

    # Result is full-context embedding (768-dim)
    embedding = np.mean(result, axis=0)  # Average over time if needed

    return embedding
```

### Expected Results

**If chunking was the problem:**
- Similarity range: 0.3-0.9 (wider than Spike 5's 0.808-0.971)
- Music-map overlap: >20%
- Vril ↔ Sabrina Carpenter: <0.5 (currently 0.808)

**If MERT fundamentally doesn't work:**
- Similarity range still narrow (0.7-0.95)
- Music-map overlap still ~0%
- Audio alone insufficient for artist similarity

---

## Philosophy: Scientific Exploration Over Premature Optimization

**This spike is about finding the needle in the haystack**, not giving up at the first roadblock.

Working with underground music subgenres requires going beyond generic approaches like genre tags and music-map. We need **actual audio understanding** to distinguish:
- Liquid DnB vs Jump-up DnB
- Minimal techno vs Deep techno
- Future bass vs Melodic dubstep

Standard metadata won't capture these nuances. **We need to push through uncertainty** and test if MERT with full context can capture these distinctions.

A few dollars and a Docker configuration are trivial costs compared to building the wrong solution. **We explore, we measure, we decide based on data.**

---

## Execution Plan: Docker-Based HF Inference Endpoint

### Problem Encountered

HuggingFace Inference Endpoints UI doesn't expose `trust_remote_code=True` for vLLM deployments.

**Solution**: Custom Docker image that passes the required flag.

### Step 1: Create Custom Docker Image (30 min)

Create `Dockerfile` that extends HF's vLLM image with the required configuration:

```dockerfile
FROM ghcr.io/huggingface/text-generation-inference:latest

# Set environment to trust remote code
ENV TRUST_REMOTE_CODE=true

# The model will be loaded from HF_MODEL_ID env var set by the endpoint
# vLLM will use our TRUST_REMOTE_CODE setting
```

Build and push:
```bash
docker build -t your-dockerhub-user/mert-vllm:latest .
docker push your-dockerhub-user/mert-vllm:latest
```

### Step 2: Deploy Custom Endpoint (15 min)

1. Go to https://ui.endpoints.huggingface.co/
2. Create endpoint with **Custom Container**
3. Container image: `your-dockerhub-user/mert-vllm:latest`
4. Model: `m-a-p/MERT-v1-95M`
5. GPU: 1x T4 (small)
6. Environment variables:
   - `TRUST_REMOTE_CODE=true`
   - `HF_TOKEN=your_token`

### Step 3: Test Locally First (20 min)

Before deploying to HF, test Docker image locally:

```bash
docker run -p 8080:8080 \
  -e TRUST_REMOTE_CODE=true \
  -e MODEL_ID=m-a-p/MERT-v1-95M \
  -e HF_TOKEN=your_token \
  your-dockerhub-user/mert-vllm:latest
```

Validate with test request to localhost:8080.

### Step 4: Run Spike 6 (10-20 min)

1. Test with 1 artist first (`--test` flag)
2. Validate results make sense
3. Run all 8 artists
4. **Cost: ~$0.20-0.40**

### Step 5: Analysis (30 min)

Compare to Spike 5:
- Did full context improve similarity range?
- Music-map overlap change?
- Subgenre discrimination?

**Total time: ~2-3 hours**
**Total cost: ~$0.50-1.00** (including Docker testing)

---

## Alternative: Local vLLM with trust_remote_code

If Docker deployment fails, run vLLM locally:

```bash
pip install vllm
vllm serve m-a-p/MERT-v1-95M --trust-remote-code --gpu-memory-utilization 0.9
```

Then point spike script to `localhost:8000`.

**Cost: $0** (uses your M1, may require chunking but at least we test trust_remote_code works)

---

## Success Criteria

### MERT is viable if:
1. ✅ Similarity range > 0.4 (vs 0.163 in Spike 5)
2. ✅ Music-map overlap > 10% (vs 0% in Spike 5)
3. ✅ Vril ↔ Sabrina Carpenter < 0.6 (vs 0.808 in Spike 5)
4. ✅ Genre pairs show meaningful differences

### MERT fails if:
- ❌ Similarity range still narrow (<0.3)
- ❌ Music-map overlap still ~0%
- ❌ No improvement over Spike 5 chunked results

If MERT fails: **Audio embeddings don't work for artist similarity**, recommend metadata-based approach (genres, artist networks, etc.)

---

## Alternative: Hybrid Similarity (If MERT Fails)

If Spike 6 shows MERT doesn't work even with full context:

```python
def compute_artist_similarity_hybrid(artist1, artist2):
    """
    Hybrid similarity without audio features.
    """
    # Primary: Spotify genre tags
    genre_sim = compute_genre_jaccard(artist1.genres, artist2.genres)

    # Secondary: Music-map (when available)
    music_map_sim = get_music_map_similarity(artist1, artist2)

    # Tertiary: Collaboration network
    collab_sim = compute_collab_network_similarity(artist1, artist2)

    if music_map_sim is not None:
        return 0.5 * music_map_sim + 0.3 * genre_sim + 0.2 * collab_sim
    else:
        return 0.6 * genre_sim + 0.4 * collab_sim
```

No audio processing, no ML models, fast and cheap.

---

## Files to Create/Update

**New files:**
- `spike_6_mert_hf.py` - HuggingFace Inference API runner
- `SPIKE_6_RESULTS.md` - Analysis comparing to Spike 5
- `data/spike_6_embeddings.json` - Full-context embeddings
- `data/spike_6_similarities.json` - Pairwise similarities
- `data/spike_6_validation.json` - Music-map comparison

**Updated files:**
- `spike.py` - Add `extract_mert_embedding_hf()` function
- `SPIKE_6_PLAN.md` - This file (document abandoned approaches)

---

## Decision Tree

```
Run Spike 6 with HF Inference API ($0.03)
│
├─ MERT shows improvement (range >0.4, overlap >10%)
│  ├─ Cost-benefit: Is $3-5 for 1000 artists worth it?
│  │  ├─ YES → Use MERT in production
│  │  └─ NO → Use hybrid metadata approach
│  │
├─ MERT shows no improvement
│  └─ Abandon audio embeddings entirely
│     └─ Use hybrid metadata approach (genres + music-map + network)
```

---

## Next Steps (After Spike 6)

**If MERT works:**
- Implement production pipeline with HF Inference API
- Budget for ~$5/1000 artists
- Consider caching embeddings

**If MERT fails:**
- Spike 7: Genre-based similarity
- Spike 8: Collaboration network analysis
- Production: Metadata-only hybrid approach

---

## References

- HuggingFace Inference API: https://huggingface.co/docs/api-inference/
- MERT model: https://huggingface.co/m-a-p/MERT-v1-95M
- Spike 5 Results: `SPIKE_5_MERT_RESULTS.md`
- Music-map validation: `output/similar_artists_map.json`
