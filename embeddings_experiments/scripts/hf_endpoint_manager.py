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
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import HfApi, InferenceEndpoint, get_inference_endpoint
from huggingface_hub.errors import HfHubHTTPError

# Configure logging
LOG_FILE = Path(__file__).parent.parent / "endpoint_manager.log"
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Endpoint status constants
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_SCALED_TO_ZERO = "scaledToZero"
STATUS_PENDING = "pending"
STATUS_FAILED = "failed"

# Default endpoint configuration
DEFAULT_MODEL_REPOSITORY = "m-a-p/MERT-v1-95M"
DEFAULT_FRAMEWORK = "pytorch"
DEFAULT_TASK = "feature-extraction"
DEFAULT_ACCELERATOR = "gpu"
DEFAULT_VENDOR = "aws"
DEFAULT_REGION = "us-east-1"
DEFAULT_INSTANCE_SIZE = "medium"
DEFAULT_INSTANCE_TYPE = "nvidia-a10g"
DEFAULT_MIN_REPLICA = 0  # Auto-pause when idle
DEFAULT_MAX_REPLICA = 1
DEFAULT_TIMEOUT_SECONDS = 600  # 10 minutes


@dataclass(frozen=True)
class EndpointStatus:
    """Immutable dataclass representing endpoint status information."""

    name: str
    status: str
    url: str | None
    task: str
    model_repository: str
    framework: str
    instance_size: str
    instance_type: str
    min_replica: int
    max_replica: int


def get_or_create_endpoint(
    endpoint_name: str,
    hf_token: str,
    namespace: str | None = None,
    create_if_missing: bool = False,
    # Creation parameters (only used if creating new endpoint)
    repository: str = DEFAULT_MODEL_REPOSITORY,
    framework: str = DEFAULT_FRAMEWORK,
    task: str = DEFAULT_TASK,
    custom_image: dict | None = None,
    accelerator: str = DEFAULT_ACCELERATOR,
    vendor: str = DEFAULT_VENDOR,
    region: str = DEFAULT_REGION,
    instance_size: str = DEFAULT_INSTANCE_SIZE,
    instance_type: str = DEFAULT_INSTANCE_TYPE,
    min_replica: int = DEFAULT_MIN_REPLICA,
    max_replica: int = DEFAULT_MAX_REPLICA,
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
        HfHubHTTPError: If HuggingFace API call fails
    """
    api = HfApi(token=hf_token)

    # Try to get existing endpoint
    try:
        endpoint = get_inference_endpoint(
            name=endpoint_name,
            namespace=namespace,
            token=hf_token
        )
        logger.info(f"✓ Found existing endpoint: {endpoint_name}")
        logger.info(f"  Status: {endpoint.status}")
        logger.info(f"  URL: {endpoint.url}")
        return endpoint

    except HfHubHTTPError as e:
        if not create_if_missing:
            raise ValueError(
                f"Endpoint '{endpoint_name}' not found and "
                f"create_if_missing=False. Error: {e}"
            ) from e

        logger.info(f"Endpoint not found, creating new one: {endpoint_name}")

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

        logger.info(f"✓ Created endpoint: {endpoint_name}")
        logger.info(f"  Status: {endpoint.status}")
        return endpoint


def resume_endpoint_and_wait(
    endpoint_name: str,
    hf_token: str,
    namespace: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[InferenceEndpoint, str]:
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
    logger.info(f"Resuming endpoint: {endpoint_name}")

    endpoint = get_inference_endpoint(
        name=endpoint_name,
        namespace=namespace,
        token=hf_token
    )

    # Check current status
    current_status = endpoint.status
    logger.info(f"  Current status: {current_status}")

    # Resume if paused or scaled to zero
    if current_status in [STATUS_PAUSED, STATUS_SCALED_TO_ZERO]:
        logger.info("  Resuming endpoint...")
        endpoint = endpoint.resume()
        logger.info(f"  Status after resume: {endpoint.status}")
    elif current_status == STATUS_RUNNING:
        logger.info("  Endpoint already running!")
        if endpoint.url is None:
            raise RuntimeError("Endpoint is running but has no URL")
        return endpoint, endpoint.url
    elif current_status == STATUS_PENDING:
        logger.info("  Endpoint already starting...")
    else:
        logger.warning(f"  ⚠️  Unexpected status: {current_status}")

    # Wait for endpoint to be ready
    logger.info(
        f"  Waiting for endpoint to be ready (timeout: {timeout_seconds}s)..."
    )
    start_time = time.time()

    try:
        # Use wait() method with timeout
        endpoint = endpoint.wait(timeout=timeout_seconds)
        elapsed = time.time() - start_time

        logger.info(f"  ✓ Endpoint ready in {elapsed:.1f}s")
        logger.info(f"  URL: {endpoint.url}")

        if endpoint.url is None:
            raise RuntimeError("Endpoint ready but has no URL")
        return endpoint, endpoint.url

    except TimeoutError as e:
        elapsed = time.time() - start_time
        logger.error(
            f"  ❌ Failed to start endpoint after {elapsed:.1f}s: {e}"
        )
        raise


def pause_endpoint(
    endpoint_name: str,
    hf_token: str,
    namespace: str | None = None,
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
    logger.info(f"Pausing endpoint: {endpoint_name}")

    endpoint = get_inference_endpoint(
        name=endpoint_name,
        namespace=namespace,
        token=hf_token
    )

    current_status = endpoint.status
    logger.info(f"  Current status: {current_status}")

    if current_status == STATUS_PAUSED:
        logger.info("  Endpoint already paused")
        return endpoint

    endpoint = endpoint.pause()
    logger.info(f"  ✓ Endpoint paused")
    logger.info(f"  Status: {endpoint.status}")

    return endpoint


def delete_endpoint(
    endpoint_name: str,
    hf_token: str,
    namespace: str | None = None,
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
    if not confirm:
        raise ValueError(
            "Must set confirm=True to delete endpoint. "
            "This action is non-revertible and will delete all endpoint data."
        )

    logger.warning(f"⚠️  Deleting endpoint: {endpoint_name} (NON-REVERTIBLE)")

    endpoint = get_inference_endpoint(
        name=endpoint_name,
        namespace=namespace,
        token=hf_token
    )

    endpoint.delete()
    logger.info(f"  ✓ Endpoint deleted: {endpoint_name}")


def get_endpoint_status(
    endpoint_name: str,
    hf_token: str,
    namespace: str | None = None,
) -> EndpointStatus:
    """
    Get detailed status information about an endpoint.

    Args:
        endpoint_name: Name of the endpoint
        hf_token: HuggingFace API token
        namespace: HF namespace (username or org)

    Returns:
        EndpointStatus dataclass with endpoint information
    """
    endpoint = get_inference_endpoint(
        name=endpoint_name,
        namespace=namespace,
        token=hf_token
    )

    # Access compute attributes via the raw dict if not in type stubs
    endpoint_dict = endpoint.__dict__ if hasattr(endpoint, '__dict__') else {}

    return EndpointStatus(
        name=endpoint.name,
        status=endpoint.status,
        url=endpoint.url if endpoint.status == STATUS_RUNNING else None,
        task=endpoint.task,
        model_repository=endpoint.repository,
        framework=endpoint.framework,
        instance_size=endpoint_dict.get('instance_size', 'unknown'),
        instance_type=endpoint_dict.get('instance_type', 'unknown'),
        min_replica=endpoint_dict.get('min_replica', 0),
        max_replica=endpoint_dict.get('max_replica', 1),
    )
