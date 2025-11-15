#!/usr/bin/env python3
"""
Deploy pre-built Docker image to HuggingFace Spaces.
Called by GitHub Action after building on AMD64.
"""

from huggingface_hub import HfApi, SpaceHardware
import os
import sys

# Get configuration from environment
HF_TOKEN = os.environ.get("HF_TOKEN")
DOCKER_IMAGE = os.environ.get("DOCKER_IMAGE")
SPACE_NAME = "mert-spike6-inference"

if not HF_TOKEN:
    print("❌ ERROR: HF_TOKEN not set")
    sys.exit(1)

if not DOCKER_IMAGE:
    print("❌ ERROR: DOCKER_IMAGE not set")
    sys.exit(1)

print("=" * 80)
print("DEPLOYING TO HUGGINGFACE SPACES")
print("=" * 80)
print(f"Docker image: {DOCKER_IMAGE}")
print(f"Space name: {SPACE_NAME}")
print()

# Initialize API
api = HfApi(token=HF_TOKEN)

# Get username
user_info = api.whoami()
username = user_info['name']
space_id = f"{username}/{SPACE_NAME}"

# Create or update Space
print(f"Creating/updating Space: {space_id}")
try:
    api.create_repo(
        repo_id=SPACE_NAME,
        repo_type="space",
        space_sdk="docker",
        private=False
    )
    print(f"✓ Created new Space: {space_id}")
except Exception as e:
    if "already created" in str(e).lower() or "already exists" in str(e).lower():
        print(f"⚠️  Space already exists: {space_id}")
        print("Will update existing space...")
    else:
        print(f"❌ Failed to create space: {e}")
        sys.exit(1)

# Create README that references the Docker image
readme_content = f"""---
title: MERT Spike 6 Inference
emoji: 🎵
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# MERT-v1-95M Inference Server

Audio embedding extraction server using MERT (Music Understanding Model with Large-Scale Self-supervised Training).

## Endpoints

- `GET /health` - Health check
- `POST /embed` - Extract embeddings from audio
- `GET /` - API documentation

## Docker Image

This Space uses a pre-built Docker image: `{DOCKER_IMAGE}`

Built on AMD64 architecture via GitHub Actions.

## Usage

```python
import requests
import numpy as np
import librosa

# Load audio (30 seconds at 24kHz)
audio, sr = librosa.load("song.mp3", sr=24000, duration=30.0)

# Call endpoint
response = requests.post(
    "https://{space_id.replace('/', '-')}.hf.space/embed",
    json={{
        "audio": audio.tolist(),
        "sampling_rate": int(sr)
    }}
)

# Get embeddings (13 layers, 768 dimensions each)
result = response.json()
embeddings = np.array(result["embedding"])  # Shape: [13, 768]
```

## Model

- **Model**: m-a-p/MERT-v1-95M
- **Output**: All 13 transformer layers
- **Embedding size**: 768 dimensions per layer
- **Max duration**: 30 seconds
"""

print("\nUploading README...")
api.upload_file(
    path_or_fileobj=readme_content.encode(),
    path_in_repo="README.md",
    repo_id=space_id,
    repo_type="space"
)

# Create Dockerfile that pulls the pre-built image
dockerfile_content = f"""FROM {DOCKER_IMAGE}

# The pre-built image already contains everything we need
# This Dockerfile just references it for HuggingFace Spaces
"""

print("Uploading Dockerfile reference...")
api.upload_file(
    path_or_fileobj=dockerfile_content.encode(),
    path_in_repo="Dockerfile",
    repo_id=space_id,
    repo_type="space"
)

print("✓ Files uploaded")

# Request GPU hardware
print("\nRequesting GPU (A10G Small - $1.05/hr)...")
try:
    api.request_space_hardware(space_id, SpaceHardware.A10G_SMALL)
    print("✓ GPU requested")
except Exception as e:
    print(f"⚠️  GPU request note: {e}")

print()
print("=" * 80)
print("DEPLOYMENT COMPLETE")
print("=" * 80)
print(f"\nSpace URL: https://huggingface.co/spaces/{space_id}")
print(f"Endpoint URL: https://{space_id.replace('/', '-')}.hf.space")
print()
print("⚠️  Space will take a few minutes to start")
print("⚠️  Remember to pause/delete Space after use to stop billing!")
