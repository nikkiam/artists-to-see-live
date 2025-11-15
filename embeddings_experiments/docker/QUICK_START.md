# Spike 6: Quick Start Guide

## TL;DR

1. Add GitHub Secrets (DOCKER_USERNAME, DOCKER_PASSWORD, HF_TOKEN)
2. Push code to GitHub
3. Run GitHub Action
4. Wait ~20 minutes
5. Run `uv run python spike_6_mert_hf.py`
6. Run `uv run python cleanup_hf_space.py` (stop billing!)

## Detailed Steps

### 1. Add GitHub Secrets (5 minutes)

Go to: https://github.com/YOUR_USERNAME/artists-to-see-live/settings/secrets/actions

Add these three secrets:

- `DOCKER_USERNAME` → Your Docker Hub username
- `DOCKER_PASSWORD` → Your Docker Hub password/PAT (from .env file)
- `HF_TOKEN` → Your HuggingFace token (from .env file)

### 2. Push to GitHub (2 minutes)

```bash
cd /Users/nikki/dev/artists-to-see-live

git add .github/workflows/build-mert-docker.yml
git add embeddings_experiments/deploy_to_hf_spaces.py
git add embeddings_experiments/cleanup_hf_space.py
git add embeddings_experiments/GITHUB_ACTION_SETUP.md
git add embeddings_experiments/SPIKE_6_GITHUB_ACTION_SUMMARY.md
git add embeddings_experiments/QUICK_START.md
git add embeddings_experiments/Dockerfile
git add embeddings_experiments/mert_server.py
git add embeddings_experiments/spike_6_mert_hf.py

git commit -m "Add GitHub Action for MERT Docker build on AMD64"
git push
```

### 3. Trigger GitHub Action (1 click)

1. Go to: https://github.com/YOUR_USERNAME/artists-to-see-live/actions
2. Click "Build and Deploy MERT Docker Image"
3. Click "Run workflow" → "Run workflow"

### 4. Wait for Completion (~20 minutes)

**Phase 1: GitHub Action (~15 min)**
- Building Docker image (10-12 min)
- Pushing to Docker Hub (1-2 min)
- Deploying to HF Spaces (1 min)

**Phase 2: HF Space Startup (~5-10 min)**
- Building container
- Starting app
- Loading model

Monitor at:
- GitHub: https://github.com/YOUR_USERNAME/artists-to-see-live/actions
- HF Space: https://huggingface.co/spaces/YOUR_USERNAME/mert-spike6-inference

### 5. Update .env (30 seconds)

Once Space shows "RUNNING":

```bash
cd embeddings_experiments
echo 'HF_ENDPOINT_URL=https://YOUR_USERNAME-mert-spike6-inference.hf.space' >> .env
```

Replace `YOUR_USERNAME` with your actual HuggingFace username.

### 6. Test Endpoint (1 minute)

```bash
curl https://YOUR_USERNAME-mert-spike6-inference.hf.space/health
```

Expected response:
```json
{"status": "healthy", "model": "MERT-v1-95M", "device": "cuda"}
```

### 7. Run Spike 6 Test (5 minutes)

```bash
cd embeddings_experiments
uv run python spike_6_mert_hf.py --test
```

This processes 1 artist (deadmau5) to verify everything works.

### 8. Run Full Spike 6 (20-30 minutes)

```bash
uv run python spike_6_mert_hf.py
```

This processes all 8 artists × 5 tracks = 40 tracks through all 13 MERT layers.

### 9. STOP BILLING! (30 seconds)

**CRITICAL - Do not forget!**

```bash
uv run python cleanup_hf_space.py
```

This deletes the HuggingFace Space and stops GPU charges.

## Expected Output

### spike_6_mert_hf.py Success

```
================================================================================
SPIKE 6: MERT WITH CUSTOM ENDPOINT (ALL 13 LAYERS)
================================================================================

[1/6] Loading music-map data...
  Loaded 1307 artists
  Testing with 8 artists: ['deadmau5', 'Rezz', ...]

[2/6] Initializing Spotify...
  ✓ Spotify ready

[3/6] Initializing Custom HuggingFace Endpoint...
  ✓ Endpoint healthy: https://...

[4/6] Extracting track-level embeddings (13 layers)...
  ✓ Total artists with embeddings: 8/8
  ✓ Total tracks with embeddings: 40

[5/6] Computing layer-wise similarities (13 layers × all combinations)...
  Layer 1/13: Mean range: 0.XXX - 0.XXX (span: 0.XXX)
  ...
  Layer 13/13: Mean range: 0.XXX - 0.XXX (span: 0.XXX)

[6/6] Saving results...
  ✓ Results saved

================================================================================
SPIKE 6 SUMMARY (Per-Layer Analysis)
================================================================================

Best Layer: X (span: 0.XXX)
Worst Layer: Y (span: 0.XXX)

COMPARISON TO SPIKE 5
Spike 5 (Layer 13, 10s chunks): 0.808 - 0.971 (span: 0.163)
Spike 6 (Best layer, 30s full):  0.XXX - 0.XXX (span: 0.XXX)

[✓/❌] IMPROVEMENT/NO IMPROVEMENT
```

### Generated Files

```
embeddings_experiments/data/spike_6_track_embeddings.json
embeddings_experiments/data/spike_6_layer_similarities.json
embeddings_experiments/data/spike_6_embedding_cache.json
```

## Troubleshooting

### "GitHub Action failed"
- Check Secrets are set correctly
- View error in Actions tab → Click failed job → View logs

### "Space shows RUNTIME_ERROR"
- Check logs: https://huggingface.co/spaces/YOUR_USERNAME/mert-spike6-inference/logs
- Verify Docker image exists on Docker Hub

### "Connection refused" when running spike_6
- Verify Space status is "RUNNING" (not "Building")
- Check HF_ENDPOINT_URL in .env is correct
- Try: `curl $HF_ENDPOINT_URL/health`

### "Timeout" errors
- First request to Space can take 30-60s (cold start)
- Wait and retry
- spike_6_mert_hf.py has 60s timeout (line 86)

## Cost

- GitHub Actions: **FREE**
- Docker Hub: **FREE**
- HF Spaces GPU: **$1.05/hour**
- Spike 6 runtime: **~30 minutes**
- **Total: ~$0.50**

## Next Steps

After reviewing results:

**If MERT improved (span > 0.25)**
→ Consider using MERT for production
→ Budget ~$3-5 per 1000 artists

**If MERT didn't improve (span < 0.25)**
→ Abandon audio embeddings
→ Use hybrid metadata approach (genres + music-map + networks)

---

**Questions?** See `GITHUB_ACTION_SETUP.md` or `SPIKE_6_GITHUB_ACTION_SUMMARY.md`
