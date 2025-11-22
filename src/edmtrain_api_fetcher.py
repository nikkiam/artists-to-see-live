"""EDMTrain API client for fetching electronic music events."""

import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import requests

from src.models import Artist, Event

logger = logging.getLogger(__name__)

# Constants
EDMTRAIN_API_KEY = os.getenv("EDMTRAIN_API_KEY")
NYC_LOCATION_ID = 38  # New York Metropolitan Area
API_BASE_URL = "https://edmtrain.com/api"
LOOKAHEAD_DAYS = 14


def fetch_edmtrain_events(
    api_key: str,
    location_ids: list[int],
    start_date: str,
    end_date: str,
) -> list[Event]:
    """
    Fetch events from EDMTrain API and transform to Event objects.

    Args:
        api_key: EDMTrain API client key
        location_ids: List of location IDs to query
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: End date in ISO format (YYYY-MM-DD)

    Returns:
        List of Event objects
    """
    # Early exit if no API key
    if not api_key:
        logger.error("EDMTRAIN_API_KEY not found in environment")
        return []

    # Build API request
    params = {
        "client": api_key,
        "locationIds": ",".join(str(lid) for lid in location_ids),
        "startDate": start_date,
        "endDate": end_date,
        "includeElectronicGenreInd": "true",
        "includeOtherGenreInd": "false",
    }

    url = f"{API_BASE_URL}/events"

    try:
        logger.info("Fetching events from %s to %s", start_date, end_date)
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Check for API success
        if not data.get("success", False):
            error_msg = data.get("message", "Unknown API error")
            logger.error("API request failed: %s", error_msg)
            return []

        api_events = data.get("data", [])
        logger.info("Received %d events from API", len(api_events))

        # Transform to Event objects, filtering out invalid entries
        events = [
            transformed
            for api_event in api_events
            if (transformed := _transform_api_event(api_event)) is not None
        ]

        logger.info("Successfully transformed %d events", len(events))
        return events

    except requests.Timeout:
        logger.error("Request timed out")
        return []
    except requests.RequestException as e:
        logger.error("Request failed: %s", e)
        return []
    except (KeyError, ValueError) as e:
        logger.error("Failed to parse API response: %s", e)
        return []


def _transform_api_event(api_event: dict) -> Event | None:
    """
    Transform single API event response to Event dataclass.

    Args:
        api_event: Raw event dict from API

    Returns:
        Event object or None if invalid
    """
    # Early exit for required fields
    if not api_event.get("name"):
        return None
    if not api_event.get("link"):
        return None
    if not api_event.get("date"):
        return None

    # Extract venue name (early exit if missing)
    venue_data = api_event.get("venue", {})
    venue_name = venue_data.get("name")
    if not venue_name:
        return None

    # Parse event date to derive day_marker
    event_date = api_event["date"]
    day_marker = _derive_day_marker(event_date)

    # Build event_time from startTime/endTime if available
    event_time = _build_event_time(
        api_event.get("startTime"), api_event.get("endTime")
    )

    # Parse artists
    artists = _parse_artists(api_event.get("artistList", []))

    return Event(
        name=api_event["name"],
        ticket_url=api_event["link"],
        venue=venue_name,
        event_time=event_time,
        artists=artists,
        tags=[],  # EDMTrain doesn't provide tags
        day_marker=day_marker,
        event_id=str(api_event["id"]),
        event_date=event_date,
        festival_ind=api_event.get("festivalInd", False),
    )


def _parse_artists(artist_list: list[dict]) -> list[Artist]:
    """
    Extract Artist objects from API lineup data.

    Args:
        artist_list: List of artist dicts from API

    Returns:
        List of Artist objects
    """
    return [
        Artist(name=artist["name"], set_time=None)
        for artist in artist_list
        if artist.get("name")
    ]


def _derive_day_marker(event_date: str) -> str:
    """
    Derive day-of-week marker from ISO date string.

    Args:
        event_date: ISO formatted date (YYYY-MM-DD)

    Returns:
        Three-letter day marker (e.g., "Fri", "Sat")
    """
    try:
        date_obj = datetime.strptime(event_date, "%Y-%m-%d")
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return day_names[date_obj.weekday()]
    except ValueError:
        return "Unknown"


def _build_event_time(start_time: str | None, end_time: str | None) -> str | None:
    """
    Build event_time string from start/end times.

    Args:
        start_time: Start time from API
        end_time: End time from API

    Returns:
        Formatted time string (e.g., "8p-4a") or None
    """
    if not start_time and not end_time:
        return None

    # For now, just concatenate with dash if both exist
    # Could add logic to parse and format like "8p-4a" in the future
    if start_time and end_time:
        return f"{start_time}-{end_time}"

    return start_time or end_time


def _calculate_date_range() -> tuple[str, str]:
    """
    Calculate date range for event query (today + LOOKAHEAD_DAYS).

    Returns:
        Tuple of (start_date, end_date) in ISO format
    """
    today = datetime.now()
    end_date = today + timedelta(days=LOOKAHEAD_DAYS)

    return (today.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))


def main():
    """CLI entry point for fetching EDMTrain events."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("output/edmtrain_fetcher.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    # Load API key
    api_key = EDMTRAIN_API_KEY
    if not api_key:
        logger.error("EDMTRAIN_API_KEY environment variable not set")
        sys.exit(1)

    # Calculate date range
    start_date, end_date = _calculate_date_range()

    # Fetch events
    events = fetch_edmtrain_events(
        api_key=api_key,
        location_ids=[NYC_LOCATION_ID],
        start_date=start_date,
        end_date=end_date,
    )

    if not events:
        logger.warning("No events fetched")
        sys.exit(0)

    # Convert to JSON
    events_data = [asdict(event) for event in events]
    result = {"events": events_data, "count": len(events)}

    # Save to output
    output_file = f"output/edmtrain_events_{datetime.now().strftime('%Y-%m-%d')}.json"
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    logger.info("Wrote %d events to %s", len(events), output_file)


if __name__ == "__main__":
    main()
