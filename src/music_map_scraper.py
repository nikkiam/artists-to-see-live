#!/usr/bin/env python3
"""
Music-Map Scraper
Scrapes similar artist data from music-map.com including relationship strength scores.
"""

import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class SimilarArtist:
    """Similar artist with relationship data."""

    name: str
    rank: int
    relationship_strength: float | None = None


@dataclass
class ScraperResult:
    """Result from scraping an artist."""

    status: str
    similar_artists: list[SimilarArtist] | None = None
    error: str | None = None

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        if self.status == "error":
            return {"status": "error", "error": self.error}

        return {
            "status": "success",
            "similar_artists": [
                {
                    "name": a.name,
                    "rank": a.rank,
                    "relationship_strength": a.relationship_strength,
                }
                for a in (self.similar_artists or [])
            ],
            "total_count": len(self.similar_artists or []),
        }


def fetch_artist_page(artist_name: str) -> str | None:
    """
    Fetch the Music-Map page for a given artist.

    Args:
        artist_name: Name of the artist to search for

    Returns:
        HTML content as string, or None if request fails
    """
    # Convert artist name to URL format (spaces to +)
    url_artist = artist_name.replace(" ", "+").lower()
    url = f"https://www.music-map.com/{url_artist}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 404:
            logger.info("  ✗ Artist not found: %s", artist_name)
            return None

        response.raise_for_status()
        return response.text

    except requests.Timeout:
        logger.warning("  ✗ Timeout fetching: %s", artist_name)
        return None
    except requests.RequestException as e:
        logger.error("  ✗ Error fetching %s: %s", artist_name, e)
        return None


def parse_artist_names(html: str) -> list[str]:
    """
    Extract similar artist names from HTML.

    Args:
        html: HTML content as string

    Returns:
        List of artist name strings
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        artist_links = soup.find_all("a", class_="S")
        artists = [link.get_text(strip=True) for link in artist_links]

        # First artist is the queried artist itself, remove it
        if not artists:
            return []

        return artists[1:]

    except Exception as e:
        logger.error("  ✗ Error parsing artist names: %s", e)
        return []


def parse_relationship_data(html: str) -> list[float]:
    """
    Extract relationship strength data from JavaScript Aid array.

    Args:
        html: HTML content as string

    Returns:
        List of relationship strength values (first row of Aid matrix)
    """
    try:
        # Find the Aid array definition in JavaScript
        # Pattern: Aid[0]=new Array(-1,12.7927,4.52047,...);
        pattern = r"Aid\[0\]=new Array\(([^)]+)\);"
        match = re.search(pattern, html)

        if not match:
            logger.warning("  ✗ Could not find Aid array in HTML")
            return []

        # Extract the array values
        values_str = match.group(1)
        values = [float(v.strip()) for v in values_str.split(",")]

        # First value is -1 (self-relationship), remove it
        if not values or values[0] != -1:
            return values

        return values[1:]

    except Exception as e:
        logger.error("  ✗ Error parsing relationship data: %s", e)
        return []


def scrape_artist(artist_name: str) -> ScraperResult:
    """
    Scrape similar artists and relationship data for a given artist.

    Args:
        artist_name: Name of the artist to scrape

    Returns:
        ScraperResult with similar artists data or error information
    """
    logger.info("Scraping: %s", artist_name)

    # Fetch the page
    html = fetch_artist_page(artist_name)
    if html is None:
        return ScraperResult(status="error", error="Failed to fetch page")

    # Parse artist names
    similar_artists = parse_artist_names(html)
    if not similar_artists:
        return ScraperResult(status="error", error="No similar artists found")

    # Parse relationship strengths
    strengths = parse_relationship_data(html)

    # Combine artists with their relationship strengths
    artists_with_strength = []
    for i, artist in enumerate(similar_artists):
        strength = strengths[i] if i < len(strengths) else None
        artists_with_strength.append(
            SimilarArtist(name=artist, rank=i + 1, relationship_strength=strength)
        )

    return ScraperResult(status="success", similar_artists=artists_with_strength)


def load_artists() -> list[str]:
    """Load unique artists from events.json."""
    events_file = Path("output/events.json")

    if not events_file.exists():
        raise FileNotFoundError("events.json not found in output/ directory!")

    with open(events_file, encoding="utf-8") as f:
        data = json.load(f)
        events = data.get("events", [])

    # Extract unique artist names from all events
    artist_names = {
        artist["name"]
        for event in events
        for artist in event.get("artists", [])
        if artist.get("name")
    }

    return sorted(artist_names)


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


def save_results(results: dict[str, ScraperResult], output_file: Path):
    """Save results to JSON file."""
    # Convert ScraperResult objects to dictionaries
    serializable_results = {
        artist: result.to_dict() for artist, result in results.items()
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(serializable_results, f, indent=2, ensure_ascii=False)


def git_commit_results(output_file: Path, count: int):
    """Create a git commit with current results."""
    try:
        subprocess.run(
            ["git", "add", str(output_file), "scraper.log"],
            check=True,
            capture_output=True,
        )
        commit_msg = f"Update similar artists map ({count} artists processed)"
        subprocess.run(
            ["git", "commit", "-m", commit_msg], check=True, capture_output=True
        )
        logger.info("  ✓ Git commit created")
    except subprocess.CalledProcessError:
        pass


def main():
    """Main function to process all artists from my_artists.json."""
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("scraper.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    # Setup output directory
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "similar_artists_map.json"

    # Load existing results
    existing_data = load_existing_results(output_file)

    # Load artists
    artists = load_artists()
    logger.info("Loaded %d unique artists from events.json", len(artists))

    # Check which artists already have successful results
    already_processed = {
        artist
        for artist in artists
        if artist in existing_data and existing_data[artist].get("status") == "success"
    }
    to_process = [
        artist
        for artist in artists
        if artist not in existing_data or existing_data[artist].get("status") == "error"
    ]

    if already_processed:
        logger.info(
            "Found %d artists already processed - skipping them", len(already_processed)
        )

    logger.info("Will process %d new artists", len(to_process))
    logger.info("Starting scraping process...")

    # Convert existing data to ScraperResult objects
    results = {}
    for artist, data in existing_data.items():
        if data.get("status") == "success":
            similar = [
                SimilarArtist(
                    name=a["name"],
                    rank=a["rank"],
                    relationship_strength=a.get("relationship_strength"),
                )
                for a in data.get("similar_artists", [])
            ]
            results[artist] = ScraperResult(status="success", similar_artists=similar)
        else:
            results[artist] = ScraperResult(status="error", error=data.get("error"))

    # Process each new artist
    processed_count = 0
    for i, artist in enumerate(to_process, 1):
        logger.info("[%d/%d] %s", i, len(to_process), artist)

        result = scrape_artist(artist)
        results[artist] = result
        processed_count += 1

        # Show success/error
        if result.status == "success":
            count = len(result.similar_artists or [])
            logger.info("  ✓ Found %d similar artists", count)

        # Save progress and commit every 50 artists
        if processed_count % 50 == 0:
            save_results(results, output_file)
            git_commit_results(output_file, len(results))
            logger.info("  💾 Progress saved (%d total artists)", len(results))

        # Be nice to the server - delay between requests
        if i < len(to_process):
            time.sleep(2.0)

    # Save final results
    save_results(results, output_file)

    # Summary
    success_count = sum(1 for r in results.values() if r.status == "success")
    error_count = len(results) - success_count

    logger.info("=" * 60)
    logger.info("Scraping complete!")
    logger.info("  Already had: %d", len(already_processed))
    logger.info("  Newly processed: %d", processed_count)
    logger.info("  ✓ Total successful: %d", success_count)
    logger.info("  ✗ Total errors: %d", error_count)
    logger.info("  Output: %s", output_file)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
