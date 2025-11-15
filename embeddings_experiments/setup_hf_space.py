#!/usr/bin/env python3
"""Create HuggingFace Space for MERT Spike 6."""

from huggingface_hub import HfApi, SpaceHardware
import time
import os
from pathlib import Path

# Load .env file if it exists
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Configuration
HF_TOKEN = os.environ.get("HF_TOKEN")
SPACE_NAME = "mert-spike6-inference"

def setup_space():
    """Deploy MERT inference server to HuggingFace Spaces."""

    if not HF_TOKEN:
        print("❌ ERROR: HF_TOKEN not set in environment")
        print("Please set HF_TOKEN in your .env file or environment")
        return None

    # Initialize API
    print("Initializing HuggingFace API...")
    api = HfApi(token=HF_TOKEN)

    # Get username first
    user_info = api.whoami()
    username = user_info['name']
    space_id = f"{username}/{SPACE_NAME}"

    # Create Space
    print(f"Creating Space '{SPACE_NAME}'...")
    try:
        api.create_repo(
            repo_id=SPACE_NAME,
            repo_type="space",
            space_sdk="docker",
            private=False
        )
        print(f"✓ Created: {space_id}")
    except Exception as e:
        if "already created" in str(e).lower() or "already exists" in str(e).lower():
            print(f"⚠️  Space already exists: {space_id}")
            print("Will update existing space...")
        else:
            print(f"❌ Failed to create space: {e}")
            return None

    # Change to embeddings_experiments directory for file uploads
    embeddings_dir = Path(__file__).parent

    # Upload files
    print("\nUploading files...")

    print("  Uploading Dockerfile...")
    api.upload_file(
        path_or_fileobj=str(embeddings_dir / "Dockerfile"),
        path_in_repo="Dockerfile",
        repo_id=space_id,
        repo_type="space"
    )

    print("  Uploading mert_server.py...")
    api.upload_file(
        path_or_fileobj=str(embeddings_dir / "mert_server.py"),
        path_in_repo="mert_server.py",
        repo_id=space_id,
        repo_type="space"
    )

    # Create README
    print("  Creating README.md...")
    readme = """---
title: MERT Spike 6 Inference
emoji: 🎵
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
---

# MERT-v1-95M Inference Server

Extracts all 13 layers from MERT for artist similarity analysis.

Endpoint: POST /embed with audio samples
"""

    api.upload_file(
        path_or_fileobj=readme.encode(),
        path_in_repo="README.md",
        repo_id=space_id,
        repo_type="space"
    )

    print("✓ Files uploaded")

    # Request GPU
    print("\nRequesting GPU (A10G Small - $1.05/hr)...")
    try:
        api.request_space_hardware(space_id, SpaceHardware.A10G_SMALL)
        print("✓ GPU requested")
    except Exception as e:
        print(f"⚠️  GPU request note: {e}")
        print("This may be normal if GPU is already assigned")

    # Wait for build
    print("\nWaiting for build to complete...")
    print("(This may take several minutes...)")

    build_started = False
    check_count = 0
    max_checks = 60  # 30 minutes max (30s intervals)

    while check_count < max_checks:
        try:
            info = api.space_info(space_id)
            status = info.runtime.stage if hasattr(info, 'runtime') and info.runtime else "UNKNOWN"

            if not build_started and status not in ["NO_APP_FILE", "STOPPED", "UNKNOWN"]:
                build_started = True

            print(f"  [{check_count + 1}] Status: {status}")

            if status == "RUNNING":
                endpoint_url = f"https://{space_id.replace('/', '-')}.hf.space"
                print(f"\n✓ Space is live!")
                print(f"Endpoint: {endpoint_url}")
                print(f"\nSet environment variable:")
                print(f'export HF_ENDPOINT_URL="{endpoint_url}"')
                print(f"\nOr add to your .env file:")
                print(f'HF_ENDPOINT_URL={endpoint_url}')
                return endpoint_url
            elif status == "BUILD_ERROR":
                print("\n❌ Build failed")
                print(f"Check logs at: https://huggingface.co/spaces/{space_id}/logs")
                return None
            elif status == "RUNTIME_ERROR":
                print("\n❌ Runtime error")
                print(f"Check logs at: https://huggingface.co/spaces/{space_id}/logs")
                return None
        except Exception as e:
            print(f"  ⚠️  Error checking status: {e}")

        time.sleep(30)
        check_count += 1

    print("\n⚠️  Build timeout after 30 minutes")
    print(f"Check status manually at: https://huggingface.co/spaces/{space_id}")
    return None


if __name__ == "__main__":
    print("=" * 80)
    print("HUGGINGFACE SPACES SETUP FOR SPIKE 6")
    print("=" * 80)
    print()

    endpoint_url = setup_space()

    if endpoint_url:
        print("\n" + "=" * 80)
        print("SETUP COMPLETE!")
        print("=" * 80)
        print(f"\nNext steps:")
        print(f"1. Test endpoint: curl {endpoint_url}/health")
        print(f"2. Run test: uv run python spike_6_mert_hf.py --test")
        print(f"3. Run full spike: uv run python spike_6_mert_hf.py")
        print(f"\n⚠️  REMEMBER TO PAUSE/DELETE SPACE AFTER SPIKE TO STOP BILLING!")
    else:
        print("\n" + "=" * 80)
        print("SETUP FAILED")
        print("=" * 80)
        print("\nPlease check the errors above and try again.")
