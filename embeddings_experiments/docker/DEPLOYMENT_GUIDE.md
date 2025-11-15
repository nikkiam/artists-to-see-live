# Docker Deployment Guide for MERT Spike 6

## Overview

Deploy MERT-v1-95M to HuggingFace Inference Endpoints using a custom Docker container with `trust_remote_code` support to process full 30-second audio clips without chunking.

## Prerequisites

- Docker installed and running
- Docker Hub account (free)
- HuggingFace account with payment method
- HF_TOKEN in environment

## Step 1: Build Docker Image

```bash
cd embeddings_experiments

# Build the image
docker build -t mert-inference:latest -f Dockerfile .

# Verify the build
docker images | grep mert-inference
```

## Step 2: Test Local Build (Verification Only)

```bash
# Run the container to verify it starts
docker run -p 8080:8080 \
  -e HF_MODEL_ID=m-a-p/MERT-v1-95M \
  -e TRUST_REMOTE_CODE=true \
  mert-inference:latest

# In another terminal, test health endpoint
curl http://localhost:8080/health
```

## Step 3: Push to Docker Hub

```bash
# Login
docker login

# Tag for your Docker Hub repo
docker tag mert-inference:latest YOUR_USERNAME/mert-inference:latest

# Push
docker push YOUR_USERNAME/mert-inference:latest
```

## Step 4: Create HuggingFace Inference Endpoint

Via https://huggingface.co/ → Profile → Inference Endpoints:

**Configuration:**
- Name: `mert-v1-95m-spike6`
- Model: `m-a-p/MERT-v1-95M`
- Task: `Feature Extraction`
- Cloud: AWS us-east-1
- Instance: GPU Medium (A10G) - $1.00/hour
- Custom Container: `YOUR_USERNAME/mert-inference:latest`
- Environment Variables:
  - `TRUST_REMOTE_CODE=true`
  - `HF_MODEL_ID=m-a-p/MERT-v1-95M`
- Auto-scaling:
  - Min: 0 (auto-pause)
  - Max: 1
  - Scale to zero: 15 minutes

Wait 5-10 minutes for deployment, then copy endpoint URL.

## Step 5: Configure Spike 6

```bash
export HF_ENDPOINT_URL="https://your-endpoint.aws.endpoints.huggingface.cloud"
export HF_TOKEN="hf_..."
```

## Step 6: Run Experiment

Test with 1 artist:
```bash
cd embeddings_experiments
uv run python spike_6_mert_hf.py --test
```

Full run with 8 artists:
```bash
uv run python spike_6_mert_hf.py
```

## Step 7: Clean Up

Delete endpoint immediately in HuggingFace dashboard to stop billing.

## Cost Estimate

- Test (1 artist, 5 tracks): ~5 min = $0.08
- Full (8 artists, 40 tracks): ~30 min = $0.50
- Total with overhead: ~$1.00

## Success Criteria

Experiment succeeds when:
1. All tracks process without chunking (full 30s)
2. Embeddings extracted for all 8 artists
3. Similarities computed and saved to `data/spike_6_*.json`
4. Logs confirm no memory errors or truncation
