"""Load and parse JSON data into typed dataclasses."""

import json
import logging
from pathlib import Path

from src.models import Artist, ArtistSimilarityData, Event, SimilarArtist

logger = logging.getLogger(__name__)


def load_similar_artists_map(
    filepath: Path,
) -> dict[str, ArtistSimilarityData]:
    """
    Load similar artists map and filter to only successful scrapes.

    Args:
        filepath: Path to similar_artists_map.json

    Returns:
        Dict mapping artist name to ArtistSimilarityData (only successful)
    """
    if not filepath.exists():
        error_msg = f"File not found: {filepath}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    with open(filepath, encoding="utf-8") as f:
        raw_data = json.load(f)

    # Filter to only successful scrapes and convert to dataclasses
    successful_artists = {
        artist_name: artist_data
        for artist_name, artist_data in raw_data.items()
        if artist_data.get("status") == "success"
    }

    # Convert to dataclasses
    result = {}
    for artist_name, artist_data in successful_artists.items():
        similar_artists = tuple(
            SimilarArtist(
                name=sim["name"],
                rank=sim["rank"],
                relationship_strength=sim["relationship_strength"],
            )
            for sim in artist_data["similar_artists"]
            if sim["relationship_strength"] > 0  # Filter invalid strengths
        )

        result[artist_name] = ArtistSimilarityData(
            artist_name=artist_name,
            similar_artists=similar_artists,
        )

    total_artists = len(raw_data)
    successful_count = len(result)
    failed_count = total_artists - successful_count

    logger.info(
        "Loaded %d successful artists (%d failed/skipped)",
        successful_count,
        failed_count,
    )

    return result


def load_events(filepath: Path) -> list[Event]:
    """
    Load events from JSON file.

    Args:
        filepath: Path to events.json

    Returns:
        List of Event objects
    """
    if not filepath.exists():
        error_msg = f"File not found: {filepath}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    events = [
        Event(
            name=event["name"],
            ticket_url=event["ticket_url"],
            venue=event.get("venue"),
            event_time=event.get("event_time"),
            artists=[
                Artist(name=artist["name"], set_time=artist.get("set_time"))
                for artist in event.get("artists", [])
            ],
            tags=event.get("tags", []),
            day_marker=event.get("day_marker"),
            event_id=event.get("event_id"),
            event_date=event.get("event_date"),
            festival_ind=event.get("festival_ind", False),
        )
        for event in data["events"]
    ]

    logger.info("Loaded %d events", len(events))

    return events


def load_artist_list(filepath: Path) -> list[str]:
    """
    Load artist list from JSON file.

    Args:
        filepath: Path to JSON file with {"artists": [...]} structure

    Returns:
        List of artist names
    """
    if not filepath.exists():
        error_msg = f"File not found: {filepath}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    artists = data["artists"]
    logger.info("Loaded %d artists", len(artists))

    return artists
