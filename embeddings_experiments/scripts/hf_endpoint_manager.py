"""
HuggingFace Inference Endpoint Management Library

Core utilities for managing MERT inference endpoints programmatically.
Supports create, get, resume, pause, and delete operations.

Usage:
    from hf_endpoint_manager import resume_endpoint_and_wait, pause_endpoint

    # Start endpoint
    endpoint, url = resume_endpoint_and_wait("my-endpoint", hf_token)

    # Pause endpoint
    pause_endpoint("my-endpoint", hf_token)
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG_FILE = Path(__file__).parent.parent / "endpoint_manager.log"


def log(message: str) -> None:
    """
    Log message to both stdout and log file.

    Following project convention from CLAUDE.md: never use print(),
    always log to a file.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"

    # Write to stdout
    print(log_line)

    # Append to log file
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception:
        # Silently fail if log file write fails
        pass


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
):
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
        repository: Model repository (default: m-a-p/MERT-v1-95M)
        framework: Model framework (default: pytorch)
        task: Task type (default: feature-extraction)
        accelerator: Accelerator type (default: gpu)
        vendor: Cloud vendor (default: aws)
        region: Cloud region (default: us-east-1)
        instance_size: Instance size (default: medium)
        instance_type: Instance type (default: nvidia-a10g)
        min_replica: Minimum replicas (default: 0 for auto-pause)
        max_replica: Maximum replicas (default: 1)

    Returns:
        InferenceEndpoint instance

    Raises:
        ValueError: If endpoint doesn't exist and create_if_missing=False
        Exception: If HuggingFace API call fails
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
            raise ValueError(
                f"Endpoint '{endpoint_name}' not found and create_if_missing=False. "
                f"Error: {e}"
            )

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


def resume_endpoint_and_wait(
    endpoint_name: str,
    hf_token: str,
    namespace: Optional[str] = None,
    timeout_seconds: int = 600,  # 10 minutes
) -> tuple:
    """
    Resume a paused endpoint and wait until it's ready.

    Args:
        endpoint_name: Name of the endpoint
        hf_token: HuggingFace API token
        namespace: HF namespace (username or org)
        timeout_seconds: Max time to wait for endpoint to be ready (default: 600)

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


def pause_endpoint(
    endpoint_name: str,
    hf_token: str,
    namespace: Optional[str] = None,
):
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


def get_endpoint_status(
    endpoint_name: str,
    hf_token: str,
    namespace: Optional[str] = None,
) -> dict:
    """
    Get detailed status information about an endpoint.

    Args:
        endpoint_name: Name of the endpoint
        hf_token: HuggingFace API token
        namespace: HF namespace (username or org)

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
