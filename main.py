"""CLI entry point for the artists-to-see-live scraper."""

import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from src.techno_queers_email_scraper import parse_html_file

logger = logging.getLogger(__name__)


def main():
    """Main CLI function."""
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("app.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    if len(sys.argv) < 2:
        logger.error("Usage: python main.py <html_file> [--output <output_file>]")
        sys.exit(1)

    html_file = sys.argv[1]
    output_file = None

    # Check for --output flag
    if len(sys.argv) >= 4 and sys.argv[2] == "--output":
        output_file = sys.argv[3]

    # Parse the HTML file
    events = parse_html_file(html_file)

    # Convert events to dictionaries for JSON serialization
    events_data = [asdict(event) for event in events]
    result = {"events": events_data, "count": len(events)}

    # Output results
    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        logger.info("Wrote %d events to %s", len(events), output_file)
    else:
        logger.info(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
