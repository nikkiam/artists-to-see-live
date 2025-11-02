#!/usr/bin/env python3
"""
Music-Map Scraper
Scrapes similar artist data from music-map.com including relationship strength scores.
"""

import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup

LOG_FILE = Path("scraper.log")


def log(message: str):
    """Log message to both console and file, with immediate flush."""
    print(message, flush=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(message + '\n')
        f.flush()


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
                    "relationship_strength": a.relationship_strength
                }
                for a in (self.similar_artists or [])
            ],
            "total_count": len(self.similar_artists or [])
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
    url_artist = artist_name.replace(' ', '+').lower()
    url = f"https://www.music-map.com/{url_artist}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 404:
            log(f"  ✗ Artist not found: {artist_name}")
            return None

        response.raise_for_status()
        return response.text

    except requests.Timeout:
        log(f"  ✗ Timeout fetching: {artist_name}")
        return None
    except requests.RequestException as e:
        log(f"  ✗ Error fetching {artist_name}: {e}")
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
        soup = BeautifulSoup(html, 'html.parser')
        artist_links = soup.find_all('a', class_='S')
        artists = [link.get_text(strip=True) for link in artist_links]

        # First artist is the queried artist itself, remove it
        if not artists:
            return []

        return artists[1:]

    except Exception as e:
        log(f"  ✗ Error parsing artist names: {e}")
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
        pattern = r'Aid\[0\]=new Array\(([^)]+)\);'
        match = re.search(pattern, html)

        if not match:
            log("  ✗ Could not find Aid array in HTML")
            return []

        # Extract the array values
        values_str = match.group(1)
        values = [float(v.strip()) for v in values_str.split(',')]

        # First value is -1 (self-relationship), remove it
        if not values or values[0] != -1:
            return values

        return values[1:]

    except Exception as e:
        log(f"  ✗ Error parsing relationship data: {e}")
        return []


def scrape_artist(artist_name: str) -> ScraperResult:
    """
    Scrape similar artists and relationship data for a given artist.

    Args:
        artist_name: Name of the artist to scrape

    Returns:
        ScraperResult with similar artists data or error information
    """
    log(f"Scraping: {artist_name}")

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
    """Load artists from my_artists.json."""
    artists_file = Path("my_artists.json")

    if not artists_file.exists():
        raise FileNotFoundError("my_artists.json not found!")

    with open(artists_file, 'r') as f:
        data = json.load(f)
        return data.get("artists", [])


def load_existing_results(output_file: Path) -> dict[str, dict]:
    """Load existing results from JSON file if it exists."""
    if not output_file.exists():
        return {}

    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log(f"  ⚠ Warning: Could not load existing results: {e}")
        return {}


def save_results(results: dict[str, ScraperResult], output_file: Path):
    """Save results to JSON file."""
    # Convert ScraperResult objects to dictionaries
    serializable_results = {
        artist: result.to_dict()
        for artist, result in results.items()
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_results, f, indent=2, ensure_ascii=False)


def git_commit_results(output_file: Path, count: int):
    """Create a git commit with current results."""
    try:
        subprocess.run(["git", "add", str(output_file), str(LOG_FILE)], check=True, capture_output=True)
        commit_msg = f"Update similar artists map ({count} artists processed)"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True, capture_output=True)
        log(f"  ✓ Git commit created")
    except subprocess.CalledProcessError:
        pass


def main():
    """Main function to process all artists from my_artists.json."""
    # Setup output directory
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "similar_artists_map.json"

    # Load existing results
    existing_data = load_existing_results(output_file)

    # Load artists
    artists = load_artists()
    log(f"Loaded {len(artists)} artists from my_artists.json")

    # Check which artists already have results
    already_processed = {artist for artist in artists if artist in existing_data}
    to_process = [artist for artist in artists if artist not in existing_data]

    if already_processed:
        log(f"Found {len(already_processed)} artists already processed - skipping them")

    log(f"Will process {len(to_process)} new artists")
    log("Starting scraping process...\n")

    # Convert existing data to ScraperResult objects
    results = {}
    for artist, data in existing_data.items():
        if data.get("status") == "success":
            similar = [
                SimilarArtist(
                    name=a["name"],
                    rank=a["rank"],
                    relationship_strength=a.get("relationship_strength")
                )
                for a in data.get("similar_artists", [])
            ]
            results[artist] = ScraperResult(status="success", similar_artists=similar)
        else:
            results[artist] = ScraperResult(status="error", error=data.get("error"))

    # Process each new artist
    processed_count = 0
    for i, artist in enumerate(to_process, 1):
        log(f"[{i}/{len(to_process)}] {artist}")

        result = scrape_artist(artist)
        results[artist] = result
        processed_count += 1

        # Show success/error
        if result.status == "success":
            count = len(result.similar_artists or [])
            log(f"  ✓ Found {count} similar artists")

        # Save progress and commit every 50 artists
        if processed_count % 50 == 0:
            save_results(results, output_file)
            git_commit_results(output_file, len(results))
            log(f"  💾 Progress saved ({len(results)} total artists)")

        # Be nice to the server - delay between requests
        if i < len(to_process):
            time.sleep(2.0)

    # Save final results
    save_results(results, output_file)

    # Summary
    success_count = sum(1 for r in results.values() if r.status == "success")
    error_count = len(results) - success_count

    log(f"\n{'='*60}")
    log(f"Scraping complete!")
    log(f"  Already had: {len(already_processed)}")
    log(f"  Newly processed: {processed_count}")
    log(f"  ✓ Total successful: {success_count}")
    log(f"  ✗ Total errors: {error_count}")
    log(f"  Output: {output_file}")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
