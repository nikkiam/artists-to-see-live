# HuggingFace Inference Endpoint Management - Implementation Plan

## Overview

This document provides a plan to implement Python utilities for managing the MERT HuggingFace Inference Endpoint used in Spike 6. The code will allow spinning up and spinning down the endpoint programmatically to minimize costs.

## Context from Spike 6

**Current Setup:**
- Docker image: Built via GitHub Actions, pushed to Docker Hub (`YOUR_USERNAME/mert-spike6-inference:latest`)
- Model: MERT-v1-95M with all 13 layers
- Endpoint configuration: A10G GPU, custom Docker container
- Usage pattern: Intermittent (run inference, then shut down to avoid billing)

**Problem:**
- Manual endpoint management via UI is tedious
- Risk of forgetting to pause endpoint → unexpected costs
- Want programmatic control for automated workflows

**Solution:**
- Use `huggingface_hub` library (v0.19.0+) to manage endpoints via Python

## Required Dependencies

```toml
# Add to pyproject.toml
[project]
dependencies = [
    # ... existing dependencies ...
    "huggingface-hub>=0.19.0",  # Inference Endpoint API support
]
```

## Implementation Plan

### 1. Create Endpoint Management Module

**File:** `embeddings_experiments/scripts/hf_endpoint_manager.py`

**Purpose:** Centralized utilities for endpoint lifecycle management

**Key Functions:**

#### 1.1 Get or Create Endpoint

```python
def get_or_create_endpoint(
    endpoint_name: str,
    hf_token: str,
    namespace: Optional[str] = None,
    create_if_missing: bool = False,
    # Creation parameters (only used if creating new endpoint)
    repository: str = "m-a-p/MERT-v1-95M",
    framework: str = "pytorch",
    task: str = "feature-extraction",
    custom_image: Optional[dict] = None,
    accelerator: str = "gpu",
    vendor: str = "aws",
    region: str = "us-east-1",
    instance_size: str = "medium",  # A10G
    instance_type: str = "nvidia-a10g",
    min_replica: int = 0,  # Auto-pause when idle
    max_replica: int = 1,
) -> InferenceEndpoint:
    """
    Get existing endpoint or create new one if it doesn't exist.

    Args:
        endpoint_name: Name of the endpoint
        hf_token: HuggingFace API token
        namespace: HF namespace (username or org), defaults to token owner
        create_if_missing: If True, create endpoint if it doesn't exist
        custom_image: Dict with custom Docker image config
            Example: {
                "url": "nikkiamb/mert-spike6-inference:latest",
                "port": 8080,
                "health_route": "/health"
            }
        ... other params for endpoint creation ...

    Returns:
        InferenceEndpoint instance

    Raises:
        ValueError: If endpoint doesn't exist and create_if_missing=False
    """
    from huggingface_hub import HfApi, get_inference_endpoint

    api = HfApi(token=hf_token)

    # Try to get existing endpoint
    try:
        endpoint = get_inference_endpoint(
            name=endpoint_name,
            namespace=namespace,
            token=hf_token
        )
        log(f"✓ Found existing endpoint: {endpoint_name}")
        log(f"  Status: {endpoint.status}")
        log(f"  URL: {endpoint.url}")
        return endpoint

    except Exception as e:
        if not create_if_missing:
            raise ValueError(f"Endpoint '{endpoint_name}' not found and create_if_missing=False")

        log(f"Endpoint not found, creating new one: {endpoint_name}")

        # Create endpoint with custom Docker image
        endpoint = api.create_inference_endpoint(
            name=endpoint_name,
            repository=repository,
            framework=framework,
            task=task,
            accelerator=accelerator,
            vendor=vendor,
            region=region,
            instance_size=instance_size,
            instance_type=instance_type,
            min_replica=min_replica,  # 0 = auto-pause
            max_replica=max_replica,
            custom_image=custom_image,
            namespace=namespace,
            token=hf_token
        )

        log(f"✓ Created endpoint: {endpoint_name}")
        log(f"  Status: {endpoint.status}")
        return endpoint
```

#### 1.2 Resume Endpoint and Wait for Ready

```python
def resume_endpoint_and_wait(
    endpoint_name: str,
    hf_token: str,
    namespace: Optional[str] = None,
    timeout_seconds: int = 600,  # 10 minutes
) -> tuple[InferenceEndpoint, str]:
    """
    Resume a paused endpoint and wait until it's ready.

    Args:
        endpoint_name: Name of the endpoint
        hf_token: HuggingFace API token
        namespace: HF namespace (username or org)
        timeout_seconds: Max time to wait for endpoint to be ready

    Returns:
        Tuple of (InferenceEndpoint, endpoint_url)

    Raises:
        TimeoutError: If endpoint doesn't become ready in time
        RuntimeError: If endpoint fails to start
    """
    from huggingface_hub import get_inference_endpoint
    import time

    log(f"Resuming endpoint: {endpoint_name}")

    endpoint = get_inference_endpoint(
        name=endpoint_name,
        namespace=namespace,
        token=hf_token
    )

    # Check current status
    current_status = endpoint.status
    log(f"  Current status: {current_status}")

    # Resume if paused or scaled to zero
    if current_status in ["paused", "scaledToZero"]:
        log("  Resuming endpoint...")
        endpoint = endpoint.resume()
        log(f"  Status after resume: {endpoint.status}")
    elif current_status == "running":
        log("  Endpoint already running!")
        return endpoint, endpoint.url
    elif current_status == "pending":
        log("  Endpoint already starting...")
    else:
        log(f"  ⚠️  Unexpected status: {current_status}")

    # Wait for endpoint to be ready
    log(f"  Waiting for endpoint to be ready (timeout: {timeout_seconds}s)...")
    start_time = time.time()

    try:
        # Use wait() method with timeout
        endpoint = endpoint.wait(timeout=timeout_seconds)
        elapsed = time.time() - start_time

        log(f"  ✓ Endpoint ready in {elapsed:.1f}s")
        log(f"  URL: {endpoint.url}")

        return endpoint, endpoint.url

    except Exception as e:
        elapsed = time.time() - start_time
        log(f"  ❌ Failed to start endpoint after {elapsed:.1f}s: {e}")
        raise
```

#### 1.3 Pause Endpoint

```python
def pause_endpoint(
    endpoint_name: str,
    hf_token: str,
    namespace: Optional[str] = None,
) -> InferenceEndpoint:
    """
    Pause an endpoint to stop billing.

    Important: Paused endpoints do NOT count towards GPU quota.
    Use this instead of scale_to_zero() to completely stop billing.

    Args:
        endpoint_name: Name of the endpoint
        hf_token: HuggingFace API token
        namespace: HF namespace (username or org)

    Returns:
        InferenceEndpoint with status 'paused'
    """
    from huggingface_hub import get_inference_endpoint

    log(f"Pausing endpoint: {endpoint_name}")

    endpoint = get_inference_endpoint(
        name=endpoint_name,
        namespace=namespace,
        token=hf_token
    )

    current_status = endpoint.status
    log(f"  Current status: {current_status}")

    if current_status == "paused":
        log("  Endpoint already paused")
        return endpoint

    endpoint = endpoint.pause()
    log(f"  ✓ Endpoint paused")
    log(f"  Status: {endpoint.status}")

    return endpoint
```

#### 1.4 Delete Endpoint (Permanent)

```python
def delete_endpoint(
    endpoint_name: str,
    hf_token: str,
    namespace: Optional[str] = None,
    confirm: bool = False,
) -> None:
    """
    Delete an endpoint permanently.

    ⚠️  WARNING: This is NON-REVERTIBLE. It will delete:
    - Endpoint configuration
    - Endpoint logs
    - Endpoint usage metrics

    Use pause_endpoint() instead if you want to temporarily stop billing.

    Args:
        endpoint_name: Name of the endpoint
        hf_token: HuggingFace API token
        namespace: HF namespace (username or org)
        confirm: Must be True to actually delete (safety check)

    Raises:
        ValueError: If confirm=False
    """
    from huggingface_hub import get_inference_endpoint

    if not confirm:
        raise ValueError(
            "Must set confirm=True to delete endpoint. "
            "This action is non-revertible and will delete all endpoint data."
        )

    log(f"⚠️  Deleting endpoint: {endpoint_name} (NON-REVERTIBLE)")

    endpoint = get_inference_endpoint(
        name=endpoint_name,
        namespace=namespace,
        token=hf_token
    )

    endpoint.delete()
    log(f"  ✓ Endpoint deleted: {endpoint_name}")
```

#### 1.5 Get Endpoint Status

```python
def get_endpoint_status(
    endpoint_name: str,
    hf_token: str,
    namespace: Optional[str] = None,
) -> dict:
    """
    Get detailed status information about an endpoint.

    Returns:
        Dict with endpoint info:
        {
            "name": str,
            "status": str,  # running, paused, scaledToZero, pending, failed
            "url": str | None,
            "task": str,
            "model_repository": str,
            "framework": str,
            "instance_size": str,
            "instance_type": str,
            "min_replica": int,
            "max_replica": int,
        }
    """
    from huggingface_hub import get_inference_endpoint

    endpoint = get_inference_endpoint(
        name=endpoint_name,
        namespace=namespace,
        token=hf_token
    )

    return {
        "name": endpoint.name,
        "status": endpoint.status,
        "url": endpoint.url if endpoint.status == "running" else None,
        "task": endpoint.task,
        "model_repository": endpoint.repository,
        "framework": endpoint.framework,
        "instance_size": endpoint.instance_size,
        "instance_type": endpoint.instance_type,
        "min_replica": endpoint.min_replica,
        "max_replica": endpoint.max_replica,
    }
```

### 2. Create CLI Utility Scripts

#### 2.1 Spin Up Endpoint

**File:** `embeddings_experiments/scripts/start_mert_endpoint.py`

```python
#!/usr/bin/env python3
"""
Start the MERT inference endpoint and wait for it to be ready.

Usage:
    python start_mert_endpoint.py
    python start_mert_endpoint.py --endpoint-name my-custom-endpoint
    python start_mert_endpoint.py --create-if-missing

Environment variables:
    HF_TOKEN: HuggingFace API token (required)
"""
import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from hf_endpoint_manager import resume_endpoint_and_wait, get_or_create_endpoint
from spike import log


def main():
    parser = argparse.ArgumentParser(description="Start MERT inference endpoint")
    parser.add_argument(
        "--endpoint-name",
        default="mert-spike6-inference",
        help="Name of the HuggingFace endpoint"
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="HuggingFace namespace (defaults to token owner)"
    )
    parser.add_argument(
        "--create-if-missing",
        action="store_true",
        help="Create endpoint if it doesn't exist"
    )
    parser.add_argument(
        "--docker-image",
        default="nikkiamb/mert-spike6-inference:latest",
        help="Docker image to use for custom endpoint"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Timeout in seconds (default: 600)"
    )

    args = parser.parse_args()

    # Get HF token from environment
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        log("❌ ERROR: HF_TOKEN not set in environment")
        log("   Please set: export HF_TOKEN='hf_...'")
        sys.exit(1)

    try:
        log("=" * 80)
        log("STARTING MERT INFERENCE ENDPOINT")
        log("=" * 80)
        log("")

        # Get or create endpoint
        endpoint = get_or_create_endpoint(
            endpoint_name=args.endpoint_name,
            hf_token=hf_token,
            namespace=args.namespace,
            create_if_missing=args.create_if_missing,
            custom_image={
                "url": args.docker_image,
                "port": 8080,
                "health_route": "/health"
            }
        )

        # Resume and wait
        endpoint, url = resume_endpoint_and_wait(
            endpoint_name=args.endpoint_name,
            hf_token=hf_token,
            namespace=args.namespace,
            timeout_seconds=args.timeout
        )

        log("")
        log("=" * 80)
        log("✓ ENDPOINT READY")
        log("=" * 80)
        log("")
        log(f"Endpoint URL: {url}")
        log("")
        log("Set this in your environment:")
        log(f"  export HF_ENDPOINT_URL='{url}'")
        log("")
        log("Or add to embeddings_experiments/.env:")
        log(f"  HF_ENDPOINT_URL={url}")
        log("")
        log("=" * 80)

    except Exception as e:
        log("")
        log(f"❌ FAILED: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
```

#### 2.2 Spin Down Endpoint

**File:** `embeddings_experiments/scripts/stop_mert_endpoint.py`

```python
#!/usr/bin/env python3
"""
Stop the MERT inference endpoint to avoid billing.

Usage:
    python stop_mert_endpoint.py
    python stop_mert_endpoint.py --endpoint-name my-custom-endpoint
    python stop_mert_endpoint.py --delete  # PERMANENT deletion

Environment variables:
    HF_TOKEN: HuggingFace API token (required)
"""
import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from hf_endpoint_manager import pause_endpoint, delete_endpoint, get_endpoint_status
from spike import log


def main():
    parser = argparse.ArgumentParser(description="Stop MERT inference endpoint")
    parser.add_argument(
        "--endpoint-name",
        default="mert-spike6-inference",
        help="Name of the HuggingFace endpoint"
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="HuggingFace namespace (defaults to token owner)"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="⚠️  DELETE endpoint permanently (non-revertible)"
    )

    args = parser.parse_args()

    # Get HF token from environment
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        log("❌ ERROR: HF_TOKEN not set in environment")
        log("   Please set: export HF_TOKEN='hf_...'")
        sys.exit(1)

    try:
        log("=" * 80)
        log("STOPPING MERT INFERENCE ENDPOINT")
        log("=" * 80)
        log("")

        if args.delete:
            # Permanent deletion
            log("⚠️  WARNING: You are about to PERMANENTLY DELETE this endpoint!")
            log("   This will delete:")
            log("     - Endpoint configuration")
            log("     - Endpoint logs")
            log("     - Endpoint usage metrics")
            log("")

            # Show current status
            try:
                status = get_endpoint_status(
                    endpoint_name=args.endpoint_name,
                    hf_token=hf_token,
                    namespace=args.namespace
                )
                log(f"Endpoint to delete: {args.endpoint_name}")
                log(f"  Status: {status['status']}")
                log(f"  URL: {status['url']}")
                log("")
            except Exception:
                pass

            response = input("Type 'DELETE' to confirm: ")
            if response != "DELETE":
                log("Cancelled.")
                sys.exit(0)

            delete_endpoint(
                endpoint_name=args.endpoint_name,
                hf_token=hf_token,
                namespace=args.namespace,
                confirm=True
            )

            log("")
            log("=" * 80)
            log("✓ ENDPOINT DELETED")
            log("=" * 80)
        else:
            # Pause endpoint (reversible)
            endpoint = pause_endpoint(
                endpoint_name=args.endpoint_name,
                hf_token=hf_token,
                namespace=args.namespace
            )

            log("")
            log("=" * 80)
            log("✓ ENDPOINT PAUSED")
            log("=" * 80)
            log("")
            log("The endpoint is now paused and NOT billing.")
            log("To resume, run: python start_mert_endpoint.py")
            log("")
            log("=" * 80)

    except Exception as e:
        log("")
        log(f"❌ FAILED: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
```

#### 2.3 Check Endpoint Status

**File:** `embeddings_experiments/scripts/check_mert_endpoint.py`

```python
#!/usr/bin/env python3
"""
Check the status of the MERT inference endpoint.

Usage:
    python check_mert_endpoint.py
    python check_mert_endpoint.py --endpoint-name my-custom-endpoint

Environment variables:
    HF_TOKEN: HuggingFace API token (required)
"""
import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from hf_endpoint_manager import get_endpoint_status
from spike import log


def main():
    parser = argparse.ArgumentParser(description="Check MERT endpoint status")
    parser.add_argument(
        "--endpoint-name",
        default="mert-spike6-inference",
        help="Name of the HuggingFace endpoint"
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="HuggingFace namespace (defaults to token owner)"
    )

    args = parser.parse_args()

    # Get HF token from environment
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        log("❌ ERROR: HF_TOKEN not set in environment")
        log("   Please set: export HF_TOKEN='hf_...'")
        sys.exit(1)

    try:
        log("=" * 80)
        log("MERT INFERENCE ENDPOINT STATUS")
        log("=" * 80)
        log("")

        status = get_endpoint_status(
            endpoint_name=args.endpoint_name,
            hf_token=hf_token,
            namespace=args.namespace
        )

        log(f"Endpoint: {status['name']}")
        log(f"Status: {status['status']}")
        log(f"URL: {status['url'] or '(not running)'}")
        log(f"Task: {status['task']}")
        log(f"Model: {status['model_repository']}")
        log(f"Framework: {status['framework']}")
        log(f"Instance: {status['instance_type']} ({status['instance_size']})")
        log(f"Replicas: {status['min_replica']}-{status['max_replica']}")
        log("")

        # Status-specific messages
        if status['status'] == 'running':
            log("✓ Endpoint is RUNNING and ready for requests")
            log(f"  Set: export HF_ENDPOINT_URL='{status['url']}'")
        elif status['status'] == 'paused':
            log("⏸  Endpoint is PAUSED (not billing)")
            log("  Run: python start_mert_endpoint.py")
        elif status['status'] == 'scaledToZero':
            log("⏸  Endpoint is SCALED TO ZERO")
            log("  Run: python start_mert_endpoint.py")
        elif status['status'] == 'pending':
            log("⏳ Endpoint is STARTING...")
            log("  Wait a few minutes, then check again")
        elif status['status'] == 'failed':
            log("❌ Endpoint FAILED to start")
            log("  Check logs at HuggingFace UI")
        else:
            log(f"⚠️  Unknown status: {status['status']}")

        log("")
        log("=" * 80)

    except Exception as e:
        log("")
        log(f"❌ FAILED: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
```

### 3. Integration with spike_6_mert_hf.py

**Update spike_6_mert_hf.py to automatically manage endpoint:**

```python
def run_spike_6_with_auto_endpoint(
    test_one_artist: bool = False,
    auto_pause_after: bool = True,
    endpoint_name: str = "mert-spike6-inference"
) -> None:
    """
    Run Spike 6 with automatic endpoint management.

    Args:
        test_one_artist: If True, only process deadmau5
        auto_pause_after: If True, pause endpoint when done
        endpoint_name: Name of the HF endpoint
    """
    from hf_endpoint_manager import (
        resume_endpoint_and_wait,
        pause_endpoint,
        get_endpoint_status
    )

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        log("❌ ERROR: HF_TOKEN not set!")
        return

    endpoint_url = None

    try:
        # Start endpoint
        log("=" * 80)
        log("STARTING INFERENCE ENDPOINT")
        log("=" * 80)
        log("")

        endpoint, endpoint_url = resume_endpoint_and_wait(
            endpoint_name=endpoint_name,
            hf_token=hf_token,
            timeout_seconds=600
        )

        log("")
        log(f"✓ Endpoint ready: {endpoint_url}")
        log("")

        # Run spike with this endpoint
        run_spike_6(
            test_one_artist=test_one_artist,
            hf_endpoint_url=endpoint_url,
            hf_token=hf_token
        )

    finally:
        # Auto-pause endpoint to stop billing
        if auto_pause_after and hf_token:
            log("")
            log("=" * 80)
            log("PAUSING ENDPOINT")
            log("=" * 80)
            log("")

            try:
                pause_endpoint(
                    endpoint_name=endpoint_name,
                    hf_token=hf_token
                )
                log("✓ Endpoint paused (not billing)")
            except Exception as e:
                log(f"⚠️  Failed to pause endpoint: {e}")
                log("   Please pause manually via HuggingFace UI or:")
                log(f"   python stop_mert_endpoint.py")
```

### 4. Update pyproject.toml

```toml
# Add to dependencies
[project]
dependencies = [
    # ... existing dependencies ...
    "huggingface-hub>=0.19.0",
]

# Add convenience scripts
[project.scripts]
start-mert-endpoint = "embeddings_experiments.scripts.start_mert_endpoint:main"
stop-mert-endpoint = "embeddings_experiments.scripts.stop_mert_endpoint:main"
check-mert-endpoint = "embeddings_experiments.scripts.check_mert_endpoint:main"
```

## Usage Examples

### Basic Workflow

```bash
# 1. Start the endpoint
cd embeddings_experiments
python scripts/start_mert_endpoint.py

# 2. Run inference
python scripts/spike_6_mert_hf.py

# 3. Stop the endpoint (IMPORTANT!)
python scripts/stop_mert_endpoint.py
```

### Automated Workflow

```bash
# Run spike with auto endpoint management
cd embeddings_experiments
python scripts/spike_6_mert_hf.py --auto-manage-endpoint

# Endpoint will automatically start, run inference, and pause
```

### Check Status

```bash
# Check if endpoint is running
python scripts/check_mert_endpoint.py
```

### Delete Endpoint (Permanent)

```bash
# ⚠️  WARNING: This is permanent!
python scripts/stop_mert_endpoint.py --delete
```

## Cost Management Strategy

### Pause vs Scale-to-Zero vs Delete

| Action | Billing | GPU Quota | Reversal | When to Use |
|--------|---------|-----------|----------|-------------|
| **Pause** | ✅ No billing | ✅ Frees quota | Easy (resume) | Between spike runs |
| **Scale-to-Zero** | ✅ No billing | ❌ Counts towards quota | Auto on request | Frequent use |
| **Delete** | ✅ No billing | ✅ Frees quota | ❌ Permanent | Done with endpoint |

**Recommendation:**
- Use **Pause** between spike runs (days/weeks apart)
- Use **Scale-to-Zero** if running multiple times per day
- Use **Delete** when done with experiments entirely

### Auto-Pause Configuration

For safety, always use auto-pause:

```python
# In spike_6_mert_hf.py
if __name__ == "__main__":
    run_spike_6_with_auto_endpoint(
        test_one_artist="--test" in sys.argv,
        auto_pause_after=True,  # Always pause after run
    )
```

## Error Handling

### Common Issues

**1. Endpoint stuck in "pending"**
- Wait 5-10 minutes for cold start
- Check HuggingFace UI for logs
- May need to delete and recreate

**2. Endpoint fails to start**
- Check Docker image is available
- Verify custom_image configuration
- Check HuggingFace logs

**3. "Out of GPU quota"**
- Pause or delete unused endpoints
- Upgrade HuggingFace account tier
- Use different region

**4. Timeout on wait()**
- Increase timeout parameter
- Check endpoint logs for errors
- May indicate Docker image issue

## Testing Plan

### 1. Unit Tests

Test each function in isolation:

```python
def test_get_or_create_endpoint_existing():
    """Test getting an existing endpoint."""
    # Setup: Create endpoint via UI first
    endpoint = get_or_create_endpoint(
        endpoint_name="test-endpoint",
        hf_token=HF_TOKEN,
        create_if_missing=False
    )
    assert endpoint.status in ["running", "paused", "scaledToZero"]

def test_pause_and_resume():
    """Test pause/resume cycle."""
    # Pause
    endpoint = pause_endpoint("test-endpoint", HF_TOKEN)
    assert endpoint.status == "paused"

    # Resume
    endpoint, url = resume_endpoint_and_wait("test-endpoint", HF_TOKEN)
    assert endpoint.status == "running"
    assert url is not None
```

### 2. Integration Tests

Test full workflow:

```bash
# Start endpoint
python scripts/start_mert_endpoint.py --endpoint-name test-endpoint

# Check status
python scripts/check_mert_endpoint.py --endpoint-name test-endpoint

# Run inference (1 track)
python scripts/spike_6_mert_hf.py --test

# Stop endpoint
python scripts/stop_mert_endpoint.py --endpoint-name test-endpoint
```

### 3. Cost Monitoring

Track actual costs:

```python
# Add to endpoint manager
def get_endpoint_metrics(endpoint_name: str, hf_token: str) -> dict:
    """Get endpoint usage metrics."""
    # Use HF API to get billing info
    # Return: uptime, requests, estimated cost
    pass
```

## Documentation Updates

After implementation:

1. **Update README.md:**
   - Add "Endpoint Management" section
   - Document new scripts
   - Add usage examples

2. **Update DEPLOYMENT_GUIDE.md:**
   - Reference new endpoint management scripts
   - Simplify manual UI steps

3. **Update SPIKE_6_RESULTS.md:**
   - Add note about automated endpoint management
   - Update cost section with actual usage

## Next Steps After Implementation

1. **Test with existing endpoint:**
   - Use current "mert-spike6-inference" endpoint
   - Verify pause/resume works
   - Measure startup time

2. **Add logging:**
   - Log endpoint state transitions
   - Track total uptime/cost
   - Alert if endpoint left running

3. **Create GitHub Action:**
   - Automatically pause endpoints after spike runs
   - Scheduled check to pause any running endpoints

4. **Extend to other models:**
   - Generalize for future embedding experiments
   - Support multiple concurrent endpoints

## Files to Create

```
embeddings_experiments/
├── scripts/
│   ├── hf_endpoint_manager.py          # Core endpoint management utilities
│   ├── start_mert_endpoint.py          # CLI: Start endpoint
│   ├── stop_mert_endpoint.py           # CLI: Stop endpoint
│   ├── check_mert_endpoint.py          # CLI: Check status
│   └── spike_6_mert_hf.py              # Updated with auto-management
├── docs/
│   └── HF_ENDPOINT_MANAGEMENT_PLAN.md  # This document
└── tests/
    └── test_endpoint_manager.py        # Unit tests
```

## Success Criteria

✅ Can start endpoint programmatically
✅ Can pause endpoint programmatically
✅ Can check endpoint status
✅ Auto-pause after spike runs
✅ No manual UI interaction needed
✅ Cost reduced by preventing forgotten endpoints

## Estimated Implementation Time

- **hf_endpoint_manager.py:** 2-3 hours
- **CLI scripts:** 1-2 hours
- **Integration with spike_6:** 1 hour
- **Testing:** 2 hours
- **Documentation:** 1 hour

**Total:** ~7-9 hours

## Cost Estimate

- Testing: ~$2-3 (multiple start/stop cycles)
- Production use: $0 (pause when not in use)

---

**Status:** Ready for implementation
**Priority:** High (prevents accidental billing)
**Dependencies:** huggingface-hub >= 0.19.0
