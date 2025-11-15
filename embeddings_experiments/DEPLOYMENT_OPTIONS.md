# MERT Docker Deployment Options

## Overview

The GitHub Action builds a Docker image on AMD64 and pushes it to Docker Hub.
You can then deploy it anywhere you want.

## Step 1: Build the Image (Required)

### Add GitHub Secrets

Go to: https://github.com/YOUR_USERNAME/artists-to-see-live/settings/secrets/actions

Add:
- `DOCKER_USERNAME` - Your Docker Hub username
- `DOCKER_PASSWORD` - Your Docker Hub PAT (from .env file)

### Trigger Build

```bash
# Push the workflow
git add .github/workflows/build-mert-docker.yml
git commit -m "Add MERT Docker build workflow"
git push

# Go to GitHub Actions and run "Build MERT Docker Image (AMD64)"
```

Wait ~10-15 minutes for build to complete.

---

## Step 2: Deploy (Choose One Option)

### Option A: HuggingFace Spaces (Easiest, GPU included)

**Pros:** GPU provided, simple deployment
**Cons:** $1.05/hr, had runtime issues before
**Cost:** ~$0.50 for spike

```bash
cd embeddings_experiments
uv run python deploy_to_hf_spaces.py
```

Wait for Space to show "RUNNING", then:

```bash
export HF_ENDPOINT_URL="https://YOUR_USERNAME-mert-spike6-inference.hf.space"
uv run python spike_6_mert_hf.py --test
```

**Remember to clean up:**
```bash
uv run python cleanup_hf_space.py
```

---

### Option B: Run Locally (Testing/Development)

**Pros:** Free, full control
**Cons:** Need GPU, M1 Mac won't work well (ARM vs AMD64)

If you have an x86 machine with GPU:

```bash
docker pull YOUR_DOCKERHUB_USERNAME/mert-spike6-inference:latest
docker run -p 8080:8080 -e PORT=8080 --gpus all YOUR_DOCKERHUB_USERNAME/mert-spike6-inference:latest
```

Then:
```bash
export HF_ENDPOINT_URL="http://localhost:8080"
cd embeddings_experiments
uv run python spike_6_mert_hf.py --test
```

**Note:** Won't work well on M1 Mac (ARM architecture mismatch).

---

### Option C: Fly.io (Good Alternative)

**Pros:** Simple deployment, GPU available, pay-per-second
**Cons:** Setup required
**Cost:** Similar to HF Spaces

1. Install Fly CLI: `brew install flyctl`
2. Login: `fly auth login`
3. Create `fly.toml`:

```toml
app = "mert-spike6"

[build]
  image = "YOUR_DOCKERHUB_USERNAME/mert-spike6-inference:latest"

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

[vm]
  gpu_kind = "a10"
  cpus = 4
  memory_mb = 16384
```

4. Deploy:
```bash
fly deploy
fly scale count 1
```

5. Get URL:
```bash
fly status
# Use the hostname, e.g., https://mert-spike6.fly.dev
```

---

### Option D: Railway (Simplest Cloud Deploy)

**Pros:** Dead simple, great DX
**Cons:** No GPU tier yet (CPU only - will be SLOW)
**Cost:** Free tier available

1. Go to https://railway.app
2. New Project → Deploy from Docker Hub
3. Image: `YOUR_DOCKERHUB_USERNAME/mert-spike6-inference:latest`
4. Add environment variable: `PORT=8080`
5. Generate domain
6. Use that URL as `HF_ENDPOINT_URL`

**Warning:** CPU-only, will be very slow (5-10 minutes per track).

---

### Option E: Render (Free Tier Available)

**Pros:** Free tier, simple
**Cons:** No GPU tier (CPU only)

1. Go to https://render.com
2. New → Web Service
3. Select "Docker"
4. Image URL: `YOUR_DOCKERHUB_USERNAME/mert-spike6-inference:latest`
5. Instance Type: Free or Starter
6. Add env var: `PORT=8080`
7. Deploy

**Warning:** CPU-only, will be very slow.

---

## Recommended Approach

**For Spike 6 (testing):**
→ **Option A (HuggingFace Spaces)** - Despite earlier issues, easiest with GPU

**For Production (if MERT works):**
→ **Option C (Fly.io)** - More reliable than HF Spaces, pay-per-second

**For Local Testing:**
→ Build and test on AMD64 machine if available

---

## Cost Comparison

| Option | GPU | Cost/hour | Spike 6 (~30 min) |
|--------|-----|-----------|-------------------|
| HF Spaces A10G | ✅ | $1.05 | ~$0.50 |
| Fly.io A10 | ✅ | ~$1.50 | ~$0.75 |
| Railway | ❌ | Free-$5/mo | N/A (too slow) |
| Render | ❌ | Free-$7/mo | N/A (too slow) |
| Local GPU | ✅ | $0 | $0 (if you have GPU) |

---

## After Deployment

Once your endpoint is running:

```bash
# Test health
curl $HF_ENDPOINT_URL/health

# Run spike 6 test
cd embeddings_experiments
uv run python spike_6_mert_hf.py --test

# Run full spike
uv run python spike_6_mert_hf.py
```

---

## Troubleshooting

**"Cannot connect to endpoint"**
- Verify endpoint URL is correct
- Check service logs
- Try curl to `/health` endpoint

**"Timeout"**
- First request takes 30-60s (cold start)
- Increase timeout in spike_6_mert_hf.py (line 86)

**"Out of memory"**
- MERT needs ~8GB VRAM minimum
- Use A10G (24GB) or larger

---

**My Recommendation:** Try HuggingFace Spaces first (Option A). It's the path of least resistance for getting Spike 6 done.
