# GitHub Action Setup for MERT Docker Build

## Overview

This GitHub Action builds the MERT inference server Docker image on AMD64 architecture (avoiding M1 ARM compatibility issues) and deploys it to HuggingFace Spaces.

## Why This Approach?

**Problem**: HuggingFace Spaces was failing with permission errors when trying to download the MERT model at runtime.

**Solution**:
1. Build Docker image on GitHub's AMD64 runners
2. Pre-download the MERT model during build
3. Push to Docker Hub
4. HuggingFace Spaces pulls the pre-built image (no runtime model download needed)

## Setup Steps

### 1. Create Docker Hub Account (if needed)

Go to https://hub.docker.com/ and create an account.

### 2. Add GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:

- `DOCKER_USERNAME` - Your Docker Hub username
- `DOCKER_PASSWORD` - Your Docker Hub password or access token
- `HF_TOKEN` - Your HuggingFace token (already in .env)

### 3. Trigger the GitHub Action

**Option A: Manual trigger**
1. Go to GitHub → Actions tab
2. Select "Build and Deploy MERT Docker Image"
3. Click "Run workflow"

**Option B: Automatic trigger**
The workflow runs automatically when you push changes to:
- `embeddings_experiments/Dockerfile`
- `embeddings_experiments/mert_server.py`
- `.github/workflows/build-mert-docker.yml`

### 4. Monitor the Build

1. Go to GitHub → Actions tab
2. Watch the build progress
3. Build takes ~10-15 minutes (includes downloading MERT model)

### 5. Wait for HuggingFace Space

After GitHub Action completes:
1. Go to https://huggingface.co/spaces/YOUR_USERNAME/mert-spike6-inference
2. Wait for Space status to be "RUNNING" (~5-10 minutes)
3. Space will show "Building" → "App starting" → "Running"

### 6. Set Endpoint URL

Once running:
```bash
export HF_ENDPOINT_URL="https://YOUR_USERNAME-mert-spike6-inference.hf.space"
```

Or add to `.env`:
```
HF_ENDPOINT_URL=https://YOUR_USERNAME-mert-spike6-inference.hf.space
```

### 7. Run Spike 6

```bash
cd embeddings_experiments

# Test with 1 artist
uv run python spike_6_mert_hf.py --test

# Full run (8 artists)
uv run python spike_6_mert_hf.py
```

### 8. Clean Up (IMPORTANT!)

**Stop billing** after Spike 6 completes:

```bash
uv run python cleanup_hf_space.py
```

Or pause the Space:
```python
from huggingface_hub import HfApi
api = HfApi(token="YOUR_HF_TOKEN")
api.pause_space("YOUR_USERNAME/mert-spike6-inference")
```

## Files Created

- `.github/workflows/build-mert-docker.yml` - GitHub Action workflow
- `embeddings_experiments/deploy_to_hf_spaces.py` - Deployment script
- `embeddings_experiments/cleanup_hf_space.py` - Cleanup script

## Troubleshooting

### Build fails on GitHub
- Check Actions logs for errors
- Verify Docker Hub credentials in Secrets
- Ensure Dockerfile and mert_server.py are valid

### Space fails to start
- Check Space logs at https://huggingface.co/spaces/YOUR_USERNAME/mert-spike6-inference/logs
- Verify Docker image was pushed to Docker Hub
- Check GPU quota on HuggingFace (Pro account required)

### Endpoint not responding
- Verify Space status is "RUNNING"
- Check endpoint URL format: `https://username-space-name.hf.space`
- First request may take 30-60s (cold start)

## Cost Estimate

- **GitHub Actions**: Free (public repos)
- **Docker Hub**: Free (public images)
- **HuggingFace GPU (A10G Small)**: $1.05/hr
- **Spike 6 runtime**: ~30 minutes
- **Total**: ~$0.50

**Always remember to pause/delete the Space after use!**

## Architecture

```
┌─────────────────┐
│  GitHub Action  │  ← Builds on AMD64
│   (AMD64 VM)    │
└────────┬────────┘
         │
         │ docker push
         ▼
┌─────────────────┐
│   Docker Hub    │  ← Stores pre-built image
└────────┬────────┘
         │
         │ docker pull
         ▼
┌─────────────────┐
│ HuggingFace     │  ← Runs pre-built image
│    Spaces       │     (A10G GPU)
│  (AMD64 + GPU)  │
└─────────────────┘
         │
         │ HTTP requests
         ▼
┌─────────────────┐
│  spike_6.py     │  ← Your local machine
│   (M1 Mac)      │
└─────────────────┘
```

## Next Steps After Spike 6

If MERT works:
- Keep Docker image for production use
- Cache embeddings to reduce API calls
- Budget ~$5 for 1000 artists

If MERT fails:
- Delete Docker image and Space
- Proceed with hybrid metadata approach (genres + music-map)
