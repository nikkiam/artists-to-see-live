#!/usr/bin/env python3
"""
Music-Map Scraper
Scrapes similar artist data from music-map.com including relationship strength scores.
"""

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup


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
            print(f"  ✗ Artist not found: {artist_name}")
            return None

        response.raise_for_status()
        return response.text

    except requests.Timeout:
        print(f"  ✗ Timeout fetching: {artist_name}")
        return None
    except requests.RequestException as e:
        print(f"  ✗ Error fetching {artist_name}: {e}")
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
        print(f"  ✗ Error parsing artist names: {e}")
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
            print("  ✗ Could not find Aid array in HTML")
            return []

        # Extract the array values
        values_str = match.group(1)
        values = [float(v.strip()) for v in values_str.split(',')]

        # First value is -1 (self-relationship), remove it
        if not values or values[0] != -1:
            return values

        return values[1:]

    except Exception as e:
        print(f"  ✗ Error parsing relationship data: {e}")
        return []


def scrape_artist(artist_name: str) -> ScraperResult:
    """
    Scrape similar artists and relationship data for a given artist.

    Args:
        artist_name: Name of the artist to scrape

    Returns:
        ScraperResult with similar artists data or error information
    """
    print(f"Scraping: {artist_name}")

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


def save_results(results: dict[str, ScraperResult], output_file: Path):
    """Save results to JSON file."""
    # Convert ScraperResult objects to dictionaries
    serializable_results = {
        artist: result.to_dict()
        for artist, result in results.items()
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_results, f, indent=2, ensure_ascii=False)


def main():
    """Main function to process all artists from my_artists.json."""
    # Load artists
    artists = load_artists()
    print(f"Loaded {len(artists)} artists from my_artists.json")
    print("Starting scraping process...\n")

    # Process each artist
    results = {}
    for i, artist in enumerate(artists, 1):
        print(f"[{i}/{len(artists)}] ", end="")

        result = scrape_artist(artist)
        results[artist] = result

        # Show success/error
        if result.status == "success":
            count = len(result.similar_artists or [])
            print(f"  ✓ Found {count} similar artists")

        # Be nice to the server - small delay between requests
        if i < len(artists):
            time.sleep(0.5)

    # Save results
    output_file = Path("similar_artists_map.json")
    save_results(results, output_file)

    # Summary
    success_count = sum(1 for r in results.values() if r.status == "success")
    error_count = len(results) - success_count

    print(f"\n{'='*60}")
    print(f"Scraping complete!")
    print(f"  ✓ Successful: {success_count}")
    print(f"  ✗ Errors: {error_count}")
    print(f"  Output: {output_file}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
