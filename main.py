"""CLI entry point for the artists-to-see-live scraper."""

import sys
import json
from dataclasses import asdict
from pathlib import Path
from src.scraper import parse_html_file


def main():
    """Main CLI function."""
    if len(sys.argv) < 2:
        print("Usage: python main.py <html_file> [--output <output_file>]")
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
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Wrote {len(events)} events to {output_file}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
