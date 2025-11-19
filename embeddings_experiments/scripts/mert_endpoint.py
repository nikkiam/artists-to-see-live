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
    log,
)


def cmd_start(args) -> int:
    """Start (resume) endpoint and wait until ready."""
    try:
        log("=" * 80)
        log("STARTING MERT INFERENCE ENDPOINT")
        log("=" * 80)
        log("")

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
        return 0

    except Exception as e:
        log("")
        log(f"❌ FAILED: {e}")
        import traceback
        log(traceback.format_exc())
        return 1


def cmd_stop(args) -> int:
    """Pause endpoint to stop billing."""
    try:
        log("=" * 80)
        log("PAUSING MERT INFERENCE ENDPOINT")
        log("=" * 80)
        log("")

        endpoint = pause_endpoint(
            endpoint_name=args.endpoint_name,
            hf_token=args.hf_token,
            namespace=args.namespace
        )

        log("")
        log("=" * 80)
        log("✓ ENDPOINT PAUSED")
        log("=" * 80)
        log("")
        log("The endpoint is now paused and NOT billing.")
        log(f"To resume, run: python mert_endpoint.py start")
        log("")
        log("=" * 80)
        return 0

    except Exception as e:
        log("")
        log(f"❌ FAILED: {e}")
        import traceback
        log(traceback.format_exc())
        return 1


def cmd_status(args) -> int:
    """Check endpoint status."""
    try:
        log("=" * 80)
        log("MERT INFERENCE ENDPOINT STATUS")
        log("=" * 80)
        log("")

        status = get_endpoint_status(
            endpoint_name=args.endpoint_name,
            hf_token=args.hf_token,
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
            log("  Run: python mert_endpoint.py start")
        elif status['status'] == 'scaledToZero':
            log("⏸  Endpoint is SCALED TO ZERO")
            log("  Run: python mert_endpoint.py start")
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
        return 0

    except Exception as e:
        log("")
        log(f"❌ FAILED: {e}")
        import traceback
        log(traceback.format_exc())
        return 1


def cmd_delete(args) -> int:
    """Delete endpoint permanently."""
    try:
        log("=" * 80)
        log("DELETING MERT INFERENCE ENDPOINT")
        log("=" * 80)
        log("")
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
                hf_token=args.hf_token,
                namespace=args.namespace
            )
            log(f"Endpoint to delete: {args.endpoint_name}")
            log(f"  Status: {status['status']}")
            log(f"  URL: {status['url']}")
            log("")
        except Exception:
            pass

        if not args.confirm:
            response = input("Type 'DELETE' to confirm: ")
            if response != "DELETE":
                log("Cancelled.")
                return 0

        delete_endpoint(
            endpoint_name=args.endpoint_name,
            hf_token=args.hf_token,
            namespace=args.namespace,
            confirm=True
        )

        log("")
        log("=" * 80)
        log("✓ ENDPOINT DELETED")
        log("=" * 80)
        return 0

    except Exception as e:
        log("")
        log(f"❌ FAILED: {e}")
        import traceback
        log(traceback.format_exc())
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
        log("❌ ERROR: HF_TOKEN not set in environment")
        log("   Please set: export HF_TOKEN='hf_...'")
        return 1

    # Execute subcommand
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
