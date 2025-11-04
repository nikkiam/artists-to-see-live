#!/usr/bin/env python3
"""
Scrape event artists from music-map.com and merge into existing similar_artists_map.json
"""

import json
import logging
import subprocess
import time
from pathlib import Path

from src.music_map_scraper import ScraperResult, save_results, scrape_artist

logger = logging.getLogger(__name__)


def load_artists_from_file(filepath: Path) -> list[str]:
    """Load artists from JSON file."""
    with open(filepath) as f:
        data = json.load(f)
        return data.get("artists", [])


def load_existing_results(output_file: Path) -> dict[str, dict]:
    """Load existing results from JSON file if it exists."""
    if not output_file.exists():
        return {}

    try:
        with open(output_file, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("  ⚠ Warning: Could not load existing results: %s", e)
        return {}


def git_commit_results(output_file: Path, count: int, total: int):
    """Create a git commit with current results."""
    try:
        subprocess.run(
            ["git", "add", str(output_file), "event_scraper.log"],
            check=True,
            capture_output=True,
        )
        commit_msg = f"Scrape event artists progress ({count}/{total})"
        subprocess.run(
            ["git", "commit", "-m", commit_msg], check=True, capture_output=True
        )
        subprocess.run(["git", "push"], check=True, capture_output=True)
        logger.info("  ✓ Git commit and push successful")
    except subprocess.CalledProcessError:
        pass


def main():
    """Scrape event artists and merge into similar_artists_map.json."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("event_scraper.log", encoding="utf-8"),
        ],
    )

    logger.info("=" * 60)
    logger.info("Starting event artist scraping")
    logger.info("=" * 60)

    # Setup paths
    output_dir = Path("output")
    event_artists_file = output_dir / "event_artists.json"
    similar_artists_file = output_dir / "similar_artists_map.json"

    # Load event artists
    event_artists = load_artists_from_file(event_artists_file)
    logger.info("Loaded %d event artists to scrape", len(event_artists))

    # Load existing similar_artists_map
    existing_data = load_existing_results(similar_artists_file)
    logger.info("Loaded existing map with %d artists", len(existing_data))

    # Check which artists already have successful results
    already_processed = {
        artist
        for artist in event_artists
        if artist in existing_data and existing_data[artist].get("status") == "success"
    }

    artists_to_scrape = [a for a in event_artists if a not in already_processed]

    logger.info("Already processed: %d", len(already_processed))
    logger.info("Need to scrape: %d", len(artists_to_scrape))

    if not artists_to_scrape:
        logger.info("All event artists already scraped!")
        return

    # Convert existing data to ScraperResult objects
    results = {}
    for artist, data in existing_data.items():
        if data.get("status") == "success":
            from src.music_map_scraper import SimilarArtist

            similar_artists = [
                SimilarArtist(
                    name=a["name"],
                    rank=a["rank"],
                    relationship_strength=a.get("relationship_strength"),
                )
                for a in data.get("similar_artists", [])
            ]
            results[artist] = ScraperResult(
                status="success", similar_artists=similar_artists
            )
        else:
            results[artist] = ScraperResult(status="error", error=data.get("error"))

    # Scrape new artists
    total = len(artists_to_scrape)
    for idx, artist in enumerate(artists_to_scrape, 1):
        logger.info(f"[{idx}/{total}] Scraping: {artist}")

        result = scrape_artist(artist)
        results[artist] = result

        if result.status == "success":
            logger.info(
                f"  ✓ Found {len(result.similar_artists)} similar artists"
            )
        else:
            logger.warning(f"  ✗ Error: {result.error}")

        # Save progress every 10 artists
        if idx % 10 == 0:
            save_results(results, similar_artists_file)
            logger.info(f"  💾 Progress saved ({idx}/{total})")
            git_commit_results(similar_artists_file, idx, total)

        # Rate limiting
        time.sleep(1)

    # Final save
    save_results(results, similar_artists_file)
    logger.info("=" * 60)
    logger.info("Event artist scraping completed!")
    logger.info(f"Total artists in map: {len(results)}")
    logger.info(f"New artists added: {total}")
    logger.info("=" * 60)

    git_commit_results(similar_artists_file, total, total)


if __name__ == "__main__":
    main()
