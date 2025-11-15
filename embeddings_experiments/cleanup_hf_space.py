#!/usr/bin/env python3
"""Clean up (delete) the HuggingFace Space."""

from huggingface_hub import HfApi
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

HF_TOKEN = os.environ.get("HF_TOKEN")
SPACE_NAME = "mert-spike6-inference"

if not HF_TOKEN:
    print("❌ ERROR: HF_TOKEN not set")
    exit(1)

api = HfApi(token=HF_TOKEN)

# Get username
user_info = api.whoami()
username = user_info['name']
space_id = f"{username}/{SPACE_NAME}"

print(f"Deleting Space: {space_id}")

try:
    api.delete_repo(repo_id=space_id, repo_type="space")
    print(f"✓ Space deleted: {space_id}")
    print("✓ Billing stopped")
except Exception as e:
    print(f"❌ Failed to delete space: {e}")
