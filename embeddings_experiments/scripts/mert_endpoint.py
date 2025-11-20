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
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from hf_endpoint_manager import (
    get_or_create_endpoint,
    resume_endpoint_and_wait,
    pause_endpoint,
    delete_endpoint,
    get_endpoint_status,
    logger,
    STATUS_RUNNING,
    STATUS_PAUSED,
    STATUS_SCALED_TO_ZERO,
    STATUS_PENDING,
    STATUS_FAILED,
)


def cmd_start(args) -> int:
    """Start (resume) endpoint and wait until ready."""
    try:
        logger.info("=" * 80)
        logger.info("STARTING MERT INFERENCE ENDPOINT")
        logger.info("=" * 80)
        logger.info("")

        # Get or create endpoint
        endpoint = get_or_create_endpoint(
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
        endpoint, url = resume_endpoint_and_wait(
            endpoint_name=args.endpoint_name,
            hf_token=args.hf_token,
            namespace=args.namespace,
            timeout_seconds=args.timeout
        )

        logger.info("")
        logger.info("=" * 80)
        logger.info("✓ ENDPOINT READY")
        logger.info("=" * 80)
        logger.info("")
        logger.info(f"Endpoint URL: {url}")
        logger.info("")
        logger.info("Set this in your environment:")
        logger.info(f"  export HF_ENDPOINT_URL='{url}'")
        logger.info("")
        logger.info("Or add to embeddings_experiments/.env:")
        logger.info(f"  HF_ENDPOINT_URL={url}")
        logger.info("")
        logger.info("=" * 80)
        return 0

    except Exception as e:
        logger.error("")
        logger.error(f"❌ FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


def cmd_stop(args) -> int:
    """Pause endpoint to stop billing."""
    try:
        logger.info("=" * 80)
        logger.info("PAUSING MERT INFERENCE ENDPOINT")
        logger.info("=" * 80)
        logger.info("")

        endpoint = pause_endpoint(
            endpoint_name=args.endpoint_name,
            hf_token=args.hf_token,
            namespace=args.namespace
        )

        logger.info("")
        logger.info("=" * 80)
        logger.info("✓ ENDPOINT PAUSED")
        logger.info("=" * 80)
        logger.info("")
        logger.info("The endpoint is now paused and NOT billing.")
        logger.info(f"To resume, run: python mert_endpoint.py start")
        logger.info("")
        logger.info("=" * 80)
        return 0

    except Exception as e:
        logger.error("")
        logger.error(f"❌ FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


def cmd_status(args) -> int:
    """Check endpoint status."""
    try:
        logger.info("=" * 80)
        logger.info("MERT INFERENCE ENDPOINT STATUS")
        logger.info("=" * 80)
        logger.info("")

        status = get_endpoint_status(
            endpoint_name=args.endpoint_name,
            hf_token=args.hf_token,
            namespace=args.namespace
        )

        logger.info(f"Endpoint: {status['name']}")
        logger.info(f"Status: {status['status']}")
        logger.info(f"URL: {status['url'] or '(not running)'}")
        logger.info(f"Task: {status['task']}")
        logger.info(f"Model: {status['model_repository']}")
        logger.info(f"Framework: {status['framework']}")
        logger.info(f"Instance: {status['instance_type']} ({status['instance_size']})")
        logger.info(f"Replicas: {status['min_replica']}-{status['max_replica']}")
        logger.info("")

        # Status-specific messages
        if status['status'] == STATUS_RUNNING:
            logger.info("✓ Endpoint is RUNNING and ready for requests")
            logger.info(f"  Set: export HF_ENDPOINT_URL='{status['url']}'")
        elif status['status'] == STATUS_PAUSED:
            logger.info("⏸  Endpoint is PAUSED (not billing)")
            logger.info("  Run: python mert_endpoint.py start")
        elif status['status'] == STATUS_SCALED_TO_ZERO:
            logger.info("⏸  Endpoint is SCALED TO ZERO")
            logger.info("  Run: python mert_endpoint.py start")
        elif status['status'] == STATUS_PENDING:
            logger.info("⏳ Endpoint is STARTING...")
            logger.info("  Wait a few minutes, then check again")
        elif status['status'] == STATUS_FAILED:
            logger.error("❌ Endpoint FAILED to start")
            logger.info("  Check logs at HuggingFace UI")
        else:
            logger.warning(f"⚠️  Unknown status: {status['status']}")

        logger.info("")
        logger.info("=" * 80)
        return 0

    except Exception as e:
        logger.error("")
        logger.error(f"❌ FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


def cmd_delete(args) -> int:
    """Delete endpoint permanently."""
    try:
        logger.info("=" * 80)
        logger.info("DELETING MERT INFERENCE ENDPOINT")
        logger.info("=" * 80)
        logger.info("")
        logger.warning("⚠️  WARNING: You are about to PERMANENTLY DELETE this endpoint!")
        logger.warning("   This will delete:")
        logger.warning("     - Endpoint configuration")
        logger.warning("     - Endpoint logs")
        logger.warning("     - Endpoint usage metrics")
        logger.info("")

        # Show current status
        try:
            status = get_endpoint_status(
                endpoint_name=args.endpoint_name,
                hf_token=args.hf_token,
                namespace=args.namespace
            )
            logger.info(f"Endpoint to delete: {args.endpoint_name}")
            logger.info(f"  Status: {status['status']}")
            logger.info(f"  URL: {status['url']}")
            logger.info("")
        except Exception:
            pass

        if not args.confirm:
            response = input("Type 'DELETE' to confirm: ")
            if response != "DELETE":
                logger.info("Cancelled.")
                return 0

        delete_endpoint(
            endpoint_name=args.endpoint_name,
            hf_token=args.hf_token,
            namespace=args.namespace,
            confirm=True
        )

        logger.info("")
        logger.info("=" * 80)
        logger.info("✓ ENDPOINT DELETED")
        logger.info("=" * 80)
        return 0

    except Exception as e:
        logger.error("")
        logger.error(f"❌ FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


def main():
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
        default="mert-spike6-inference",
        help="Name of the HuggingFace endpoint (default: mert-spike6-inference)"
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
        logger.error("❌ ERROR: HF_TOKEN not set in environment")
        logger.error("   Please set: export HF_TOKEN='hf_...'")
        return 1

    # Execute subcommand
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
