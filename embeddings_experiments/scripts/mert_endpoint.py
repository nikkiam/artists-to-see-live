#!/usr/bin/env python3
"""
Unified CLI for managing MERT inference endpoints.

Usage:
    python mert_endpoint.py start [options]
    python mert_endpoint.py stop [options]
    python mert_endpoint.py status [options]
    python mert_endpoint.py delete [options]

Environment variables:
    HF_TOKEN: HuggingFace API token (required)
    MERT_ENDPOINT_NAME: Default endpoint name (optional)

Examples:
    # Start endpoint and wait until ready
    python mert_endpoint.py start

    # Start with custom name
    python mert_endpoint.py start --endpoint-name my-endpoint

    # Create endpoint if it doesn't exist
    python mert_endpoint.py start --create-if-missing

    # Check status
    python mert_endpoint.py status

    # Pause endpoint (stop billing)
    python mert_endpoint.py stop

    # Delete endpoint permanently
    python mert_endpoint.py delete
"""
import argparse
import os
import sys
import traceback
from pathlib import Path

# Allow importing from same directory when running as script
# Better alternatives: relative imports (requires __init__.py) or package install
# For now, this allows: python scripts/mert_endpoint.py from any directory
sys.path.insert(0, str(Path(__file__).parent))

import hf_endpoint_manager as hf_mgr
from huggingface_hub.errors import HfHubHTTPError


def cmd_start(args: argparse.Namespace) -> int:
    """Start (resume) endpoint and wait until ready."""
    try:
        hf_mgr.logger.info("=" * 80)
        hf_mgr.logger.info("STARTING MERT INFERENCE ENDPOINT")
        hf_mgr.logger.info("=" * 80)
        hf_mgr.logger.info("")

        # Get or create endpoint
        endpoint = hf_mgr.get_or_create_endpoint(
            endpoint_name=args.endpoint_name,
            hf_token=args.hf_token,
            namespace=args.namespace,
            create_if_missing=args.create_if_missing,
            custom_image={
                "url": args.docker_image,
                "port": 8080,
                "health_route": "/health"
            } if args.create_if_missing else None
        )

        # Resume and wait
        _endpoint, url = hf_mgr.resume_endpoint_and_wait(
            endpoint_name=args.endpoint_name,
            hf_token=args.hf_token,
            namespace=args.namespace,
            timeout_seconds=args.timeout
        )

        hf_mgr.logger.info("")
        hf_mgr.logger.info("=" * 80)
        hf_mgr.logger.info("✓ ENDPOINT READY")
        hf_mgr.logger.info("=" * 80)
        hf_mgr.logger.info("")
        hf_mgr.logger.info(f"Endpoint URL: {url}")
        hf_mgr.logger.info("")
        hf_mgr.logger.info("Set this in your environment:")
        hf_mgr.logger.info(f"  export HF_ENDPOINT_URL='{url}'")
        hf_mgr.logger.info("")
        hf_mgr.logger.info("Or add to embeddings_experiments/.env:")
        hf_mgr.logger.info(f"  HF_ENDPOINT_URL={url}")
        hf_mgr.logger.info("")
        hf_mgr.logger.info("=" * 80)
        return 0

    except (HfHubHTTPError, ValueError, RuntimeError, TimeoutError) as e:
        hf_mgr.logger.error("")
        hf_mgr.logger.error(f"❌ FAILED: {e}")
        hf_mgr.logger.error(traceback.format_exc())
        return 1


def cmd_stop(args: argparse.Namespace) -> int:
    """Pause endpoint to stop billing."""
    try:
        hf_mgr.logger.info("=" * 80)
        hf_mgr.logger.info("PAUSING MERT INFERENCE ENDPOINT")
        hf_mgr.logger.info("=" * 80)
        hf_mgr.logger.info("")

        endpoint = hf_mgr.pause_endpoint(
            endpoint_name=args.endpoint_name,
            hf_token=args.hf_token,
            namespace=args.namespace
        )

        hf_mgr.logger.info("")
        hf_mgr.logger.info("=" * 80)
        hf_mgr.logger.info("✓ ENDPOINT PAUSED")
        hf_mgr.logger.info("=" * 80)
        hf_mgr.logger.info("")
        hf_mgr.logger.info("The endpoint is now paused and NOT billing.")
        hf_mgr.logger.info(f"To resume, run: python mert_endpoint.py start")
        hf_mgr.logger.info("")
        hf_mgr.logger.info("=" * 80)
        return 0

    except (HfHubHTTPError, RuntimeError) as e:
        hf_mgr.logger.error("")
        hf_mgr.logger.error(f"❌ FAILED: {e}")
        hf_mgr.logger.error(traceback.format_exc())
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Check endpoint status."""
    try:
        hf_mgr.logger.info("=" * 80)
        hf_mgr.logger.info("MERT INFERENCE ENDPOINT STATUS")
        hf_mgr.logger.info("=" * 80)
        hf_mgr.logger.info("")

        status = hf_mgr.get_endpoint_status(
            endpoint_name=args.endpoint_name,
            hf_token=args.hf_token,
            namespace=args.namespace
        )

        hf_mgr.logger.info(f"Endpoint: {status.name}")
        hf_mgr.logger.info(f"Status: {status.status}")
        hf_mgr.logger.info(f"URL: {status.url or '(not running)'}")
        hf_mgr.logger.info(f"Task: {status.task}")
        hf_mgr.logger.info(f"Model: {status.model_repository}")
        hf_mgr.logger.info(f"Framework: {status.framework}")
        hf_mgr.logger.info(
            f"Instance: {status.instance_type} ({status.instance_size})"
        )
        hf_mgr.logger.info(
            f"Replicas: {status.min_replica}-{status.max_replica}"
        )
        hf_mgr.logger.info("")

        # Status-specific messages
        if status.status == hf_mgr.STATUS_RUNNING:
            hf_mgr.logger.info("✓ Endpoint is RUNNING and ready for requests")
            hf_mgr.logger.info(f"  Set: export HF_ENDPOINT_URL='{status.url}'")
        elif status.status == hf_mgr.STATUS_PAUSED:
            hf_mgr.logger.info("⏸  Endpoint is PAUSED (not billing)")
            hf_mgr.logger.info("  Run: python mert_endpoint.py start")
        elif status.status == hf_mgr.STATUS_SCALED_TO_ZERO:
            hf_mgr.logger.info("⏸  Endpoint is SCALED TO ZERO")
            hf_mgr.logger.info("  Run: python mert_endpoint.py start")
        elif status.status == hf_mgr.STATUS_PENDING:
            hf_mgr.logger.info("⏳ Endpoint is STARTING...")
            hf_mgr.logger.info("  Wait a few minutes, then check again")
        elif status.status == hf_mgr.STATUS_FAILED:
            hf_mgr.logger.error("❌ Endpoint FAILED to start")
            hf_mgr.logger.info("  Check logs at HuggingFace UI")
        else:
            hf_mgr.logger.warning(f"⚠️  Unknown status: {status.status}")

        hf_mgr.logger.info("")
        hf_mgr.logger.info("=" * 80)
        return 0

    except (HfHubHTTPError, RuntimeError) as e:
        hf_mgr.logger.error("")
        hf_mgr.logger.error(f"❌ FAILED: {e}")
        hf_mgr.logger.error(traceback.format_exc())
        return 1


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete endpoint permanently."""
    try:
        hf_mgr.logger.info("=" * 80)
        hf_mgr.logger.info("DELETING MERT INFERENCE ENDPOINT")
        hf_mgr.logger.info("=" * 80)
        hf_mgr.logger.info("")
        hf_mgr.logger.warning(
            "⚠️  WARNING: You are about to PERMANENTLY DELETE this endpoint!"
        )
        hf_mgr.logger.warning("   This will delete:")
        hf_mgr.logger.warning("     - Endpoint configuration")
        hf_mgr.logger.warning("     - Endpoint logs")
        hf_mgr.logger.warning("     - Endpoint usage metrics")
        hf_mgr.logger.info("")

        # Show current status
        try:
            status = hf_mgr.get_endpoint_status(
                endpoint_name=args.endpoint_name,
                hf_token=args.hf_token,
                namespace=args.namespace
            )
            hf_mgr.logger.info(f"Endpoint to delete: {args.endpoint_name}")
            hf_mgr.logger.info(f"  Status: {status.status}")
            hf_mgr.logger.info(f"  URL: {status.url}")
            hf_mgr.logger.info("")
        except HfHubHTTPError as e:
            hf_mgr.logger.warning(f"Could not fetch endpoint status: {e}")

        if not args.confirm:
            response = input("Type 'DELETE' to confirm: ")
            if response != "DELETE":
                hf_mgr.logger.info("Cancelled.")
                return 0

        hf_mgr.delete_endpoint(
            endpoint_name=args.endpoint_name,
            hf_token=args.hf_token,
            namespace=args.namespace,
            confirm=True
        )

        hf_mgr.logger.info("")
        hf_mgr.logger.info("=" * 80)
        hf_mgr.logger.info("✓ ENDPOINT DELETED")
        hf_mgr.logger.info("=" * 80)
        return 0

    except (HfHubHTTPError, ValueError, RuntimeError) as e:
        hf_mgr.logger.error("")
        hf_mgr.logger.error(f"❌ FAILED: {e}")
        hf_mgr.logger.error(traceback.format_exc())
        return 1


def main() -> int:
    """Main entry point for the CLI."""
    # Get default endpoint name from environment or use hardcoded default
    default_endpoint = os.environ.get(
        "MERT_ENDPOINT_NAME",
        "mert-v1-95m-spike-13layers"
    )

    parser = argparse.ArgumentParser(
        description="Manage MERT HuggingFace Inference Endpoints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mert_endpoint.py start                    # Start endpoint
  python mert_endpoint.py start --create-if-missing  # Create if needed
  python mert_endpoint.py status                   # Check status
  python mert_endpoint.py stop                     # Pause (stop billing)
  python mert_endpoint.py delete                   # Delete permanently
        """
    )

    # Global arguments (shared by all subcommands)
    parser.add_argument(
        "--endpoint-name",
        default=default_endpoint,
        help=f"Name of the HuggingFace endpoint (default: {default_endpoint})"
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="HuggingFace namespace (defaults to token owner)"
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start (resume) endpoint")
    start_parser.add_argument(
        "--create-if-missing",
        action="store_true",
        help="Create endpoint if it doesn't exist"
    )
    start_parser.add_argument(
        "--docker-image",
        default="nikkiamb/mert-spike6-inference:latest",
        help="Docker image (only used when creating new endpoint)"
    )
    start_parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Timeout in seconds (default: 600)"
    )
    start_parser.set_defaults(func=cmd_start)

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Pause endpoint (stop billing)")
    stop_parser.set_defaults(func=cmd_stop)

    # Status command
    status_parser = subparsers.add_parser("status", help="Check endpoint status")
    status_parser.set_defaults(func=cmd_status)

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete endpoint permanently")
    delete_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Skip confirmation prompt"
    )
    delete_parser.set_defaults(func=cmd_delete)

    # Parse arguments
    args = parser.parse_args()

    # Validate subcommand
    if not args.command:
        parser.print_help()
        return 1

    # Get HF token from environment
    args.hf_token = os.environ.get("HF_TOKEN")
    if not args.hf_token:
        hf_mgr.logger.error("❌ ERROR: HF_TOKEN not set in environment")
        hf_mgr.logger.error("   Please set: export HF_TOKEN='hf_...'")
        return 1

    # Execute subcommand
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
