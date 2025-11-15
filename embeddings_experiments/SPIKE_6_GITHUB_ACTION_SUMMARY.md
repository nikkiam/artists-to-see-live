# Spike 6: GitHub Action Deployment Summary

## What We Built

A complete GitHub Actions workflow that:
1. ✅ Builds MERT Docker image on AMD64 (GitHub runners)
2. ✅ Pushes to Docker Hub
3. ✅ Deploys to HuggingFace Spaces with GPU
4. ✅ Automatically handles environment variables
5. ✅ Includes cleanup scripts to stop billing

## Why This Approach?

### Problem: Direct HuggingFace Spaces Deployment Failed

When we tried deploying directly from your M1 Mac:
- ❌ Permission errors: `/.cache` not writable
- ❌ Runtime model download failed repeatedly
- ❌ ARM64/AMD64 compatibility issues

### Solution: Pre-build on AMD64

Build the Docker image on GitHub's AMD64 runners where:
- ✅ Full AMD64 compatibility (same as HF Spaces)
- ✅ Model downloads during build (not runtime)
- ✅ Cached layers speed up rebuilds
- ✅ Free compute for public repos

## Files Created

### GitHub Action Workflow
```
.github/workflows/build-mert-docker.yml
```
- Triggers on push or manual dispatch
- Builds on ubuntu-latest (AMD64)
- Pushes to Docker Hub
- Deploys to HuggingFace Spaces

### Deployment Scripts
```
embeddings_experiments/deploy_to_hf_spaces.py
embeddings_experiments/cleanup_hf_space.py
embeddings_experiments/setup_hf_space.py (deprecated - kept for reference)
```

### Documentation
```
embeddings_experiments/GITHUB_ACTION_SETUP.md
embeddings_experiments/SPIKE_6_GITHUB_ACTION_SUMMARY.md (this file)
```

### Updated Files
```
embeddings_experiments/spike_6_mert_hf.py - Now loads .env automatically
embeddings_experiments/.env - Contains HF_TOKEN (gitignored)
```

## Required GitHub Secrets

You need to add these to your GitHub repository:

1. **DOCKER_USERNAME** - Your Docker Hub username
2. **DOCKER_PASSWORD** - Your Docker Hub password/token (from .env file)
3. **HF_TOKEN** - Your HuggingFace token (from .env file)

### How to Add Secrets

1. Go to: https://github.com/YOUR_USERNAME/artists-to-see-live/settings/secrets/actions
2. Click "New repository secret"
3. Add each secret one by one

## Running Spike 6

### Step 1: Trigger GitHub Action

**Option A: Manual**
```bash
# Push the workflow file
git add .github/workflows/build-mert-docker.yml
git add embeddings_experiments/deploy_to_hf_spaces.py
git add embeddings_experiments/GITHUB_ACTION_SETUP.md
git commit -m "Add GitHub Action for MERT Docker build"
git push

# Then go to GitHub → Actions → "Build and Deploy MERT Docker Image" → "Run workflow"
```

**Option B: Automatic**
```bash
# Any change to these files triggers the build:
git add embeddings_experiments/Dockerfile
git add embeddings_experiments/mert_server.py
git commit -m "Update MERT server"
git push
```

### Step 2: Wait for Build (~15 minutes)

Monitor at: https://github.com/YOUR_USERNAME/artists-to-see-live/actions

The action will:
1. Build Docker image (10-12 min - downloads MERT model)
2. Push to Docker Hub (1-2 min)
3. Deploy to HF Spaces (1 min)

### Step 3: Wait for Space to Start (~5-10 minutes)

Check: https://huggingface.co/spaces/YOUR_USERNAME/mert-spike6-inference

Status progression: `BUILDING` → `APP_STARTING` → `RUNNING`

### Step 4: Update .env with Endpoint URL

```bash
echo 'HF_ENDPOINT_URL=https://YOUR_USERNAME-mert-spike6-inference.hf.space' >> embeddings_experiments/.env
```

Replace `YOUR_USERNAME` with your HuggingFace username.

### Step 5: Run Spike 6

```bash
cd embeddings_experiments

# Test with 1 artist (deadmau5)
uv run python spike_6_mert_hf.py --test

# If test works, run full spike (8 artists)
uv run python spike_6_mert_hf.py
```

### Step 6: Clean Up (STOP BILLING!)

```bash
# Stop the Space to prevent charges
uv run python cleanup_hf_space.py
```

## Cost Breakdown

| Service | Cost | Duration | Total |
|---------|------|----------|-------|
| GitHub Actions | FREE | ~15 min | $0.00 |
| Docker Hub | FREE | Storage | $0.00 |
| HF Spaces (A10G) | $1.05/hr | ~30 min | ~$0.50 |
| **TOTAL** | | | **~$0.50** |

**Critical**: Remember to run `cleanup_hf_space.py` after spike completes!

## Success Indicators

### GitHub Action Success
- ✅ All steps green in Actions tab
- ✅ Docker image visible at https://hub.docker.com/r/YOUR_USERNAME/mert-spike6-inference

### HF Space Success
- ✅ Space status shows "RUNNING"
- ✅ Can access https://YOUR_USERNAME-mert-spike6-inference.hf.space/health
- ✅ Returns: `{"status": "healthy", "model": "MERT-v1-95M"}`

### Spike 6 Success
- ✅ spike_6_mert_hf.py runs without errors
- ✅ Generates `spike_6_layer_similarities.json`
- ✅ Shows wider similarity range than Spike 5 (0.163)

## Troubleshooting

### GitHub Action Fails

**"Invalid credentials"**
- Check DOCKER_USERNAME and DOCKER_PASSWORD secrets
- Verify Docker Hub login works manually

**"HF_TOKEN not set"**
- Add HF_TOKEN to GitHub Secrets
- Value: (from .env file)

### HF Space Fails

**"Runtime Error"**
- Check Docker image was pushed successfully
- View logs at: https://huggingface.co/spaces/YOUR_USERNAME/mert-spike6-inference/logs

**"Build Error"**
- Check Dockerfile syntax
- Verify mert_server.py has no errors

### spike_6_mert_hf.py Fails

**"HF_ENDPOINT_URL not set"**
- Add to .env: `HF_ENDPOINT_URL=https://...`
- Or: `export HF_ENDPOINT_URL="https://..."`

**"Connection refused"**
- Verify Space status is RUNNING
- First request may timeout (30-60s cold start)
- Increase timeout in spike_6_mert_hf.py line 86

## What Happens Next?

### If Spike 6 Shows Improvement
- Similarity range > 0.4 (vs 0.163 in Spike 5)
- Music-map overlap > 10% (vs 0% in Spike 5)
- **Conclusion**: MERT works with full context!
- **Next**: Use MERT in production with HF Inference API

### If Spike 6 Shows No Improvement
- Range still narrow (<0.3)
- Still 0% overlap with music-map
- **Conclusion**: Audio embeddings insufficient
- **Next**: Hybrid metadata approach (genres + networks)

## Comparison: Spike 5 vs Spike 6

| Aspect | Spike 5 (Local M1) | Spike 6 (HF Spaces) |
|--------|-------------------|---------------------|
| Architecture | ARM64 (M1) | AMD64 (A10G GPU) |
| Context | 10s chunks | Full 30s |
| Layers | Layer 13 only | All 13 layers |
| Memory | MPS limited | 24GB VRAM |
| Processing | 61 min / 40 tracks | ~10 min / 40 tracks |
| Similarity Range | 0.163 (narrow) | TBD |
| Music-map Overlap | 0% | TBD |
| Cost | $0 | ~$0.50 |

## Files for Cleanup Later

If Spike 6 succeeds or fails, you can delete:
- `embeddings_experiments/setup_hf_space.py` (deprecated)
- Docker image from Docker Hub (if not using in production)
- HF Space (via cleanup_hf_space.py)

Keep:
- `.github/workflows/build-mert-docker.yml` (for future rebuilds)
- `embeddings_experiments/deploy_to_hf_spaces.py` (for redeployment)
- All spike results JSON files (for comparison)

---

**Ready to run?** Just add the GitHub Secrets and trigger the workflow!
