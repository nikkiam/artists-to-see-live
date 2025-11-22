"""EDMTrain API client for fetching electronic music events."""

import json
import logging
import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

import requests

from src.date_utils import DAY_NAMES
from src.models import Artist, Event

logger = logging.getLogger(__name__)


# Custom exceptions for EDMTrain API errors
class EDMTrainAPIError(Exception):
    """Base exception for EDMTrain API errors."""


class EDMTrainAuthError(EDMTrainAPIError):
    """Authentication/API key error."""


class EDMTrainDataError(EDMTrainAPIError):
    """Invalid data from API or parsing error."""

# Constants
EDMTRAIN_API_KEY = os.getenv("EDMTRAIN_API_KEY")
NYC_LOCATION_ID = 38  # New York Metropolitan Area
API_BASE_URL = "https://edmtrain.com/api"
LOOKAHEAD_DAYS = 14
MAX_ARTISTS_IN_GENERATED_NAME = 3  # Show first N artists in generated event names


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
        raise EDMTrainAuthError("EDMTRAIN_API_KEY not found in environment")

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
            raise EDMTrainAPIError(f"API request failed: {error_msg}")

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

    except requests.Timeout as e:
        raise EDMTrainAPIError("Request timed out") from e
    except requests.RequestException as e:
        raise EDMTrainAPIError(f"Request failed: {e}") from e
    except (KeyError, ValueError) as e:
        raise EDMTrainDataError(f"Failed to parse API response: {e}") from e


def _transform_api_event(api_event: dict) -> Event | None:
    """
    Transform single API event response to Event dataclass.

    Args:
        api_event: Raw event dict from API

    Returns:
        Event object or None if invalid
    """
    # Early exit for required fields
    event_id = api_event.get("id", "unknown")

    # Check for event name - if missing, we'll generate from artists
    event_name = api_event.get("name")
    needs_generated_name = not event_name

    if not api_event.get("link"):
        logger.warning("Skipping event %s: missing ticket link", event_id)
        return None
    if not api_event.get("date"):
        logger.warning("Skipping event %s: missing date", event_id)
        return None

    # Extract venue name (early exit if missing)
    venue_data = api_event.get("venue", {})
    venue_name = venue_data.get("name")
    if not venue_name:
        logger.warning("Skipping event %s: missing venue name", event_id)
        return None

    # Parse event date to derive day_marker
    event_date = api_event["date"]
    day_marker = _derive_day_marker(event_date)

    # Parse start/end times from startTime/endTime if available
    start_time, end_time = _parse_event_times(
        api_event.get("startTime"), api_event.get("endTime")
    )

    # Parse artists
    artists = _parse_artists(api_event.get("artistList", []))

    # Generate event name from artists if needed
    if needs_generated_name:
        event_name = _generate_event_name_from_artists(artists, event_id)
        if not event_name:
            logger.warning("Skipping event %s: no name and no artists", event_id)
            return None

    return Event(
        name=event_name,
        ticket_url=api_event["link"],
        venue=venue_name,
        start_time=start_time,
        end_time=end_time,
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


def _generate_event_name_from_artists(
    artists: list[Artist], event_id: str | int
) -> str | None:
    """
    Generate an event name from the artist lineup.

    Args:
        artists: List of Artist objects
        event_id: Event ID for logging

    Returns:
        Generated event name or None if no artists
    """
    if not artists:
        return None

    # Single artist: use their name
    if len(artists) == 1:
        return artists[0].name

    # Show up to MAX_ARTISTS_IN_GENERATED_NAME artists
    if len(artists) <= MAX_ARTISTS_IN_GENERATED_NAME:
        return " & ".join(artist.name for artist in artists)

    # More artists than max: show first MAX_ARTISTS_IN_GENERATED_NAME and indicate more
    artist_names = [
        artist.name for artist in artists[:MAX_ARTISTS_IN_GENERATED_NAME]
    ]
    remaining = len(artists) - MAX_ARTISTS_IN_GENERATED_NAME
    return f"{' & '.join(artist_names)} +{remaining} more"


def _derive_day_marker(event_date: str) -> str:
    """
    Derive day-of-week marker from ISO date string.

    Args:
        event_date: ISO formatted date (YYYY-MM-DD)

    Returns:
        Three-letter day marker (e.g., "Fri", "Sat")

    Raises:
        EDMTrainDataError: If event_date is not in valid ISO format
    """
    try:
        date_obj = datetime.strptime(event_date, "%Y-%m-%d")
        return DAY_NAMES[date_obj.weekday()]
    except ValueError as e:
        raise EDMTrainDataError(f"Invalid date format: {event_date}") from e


def _parse_event_times(
    start_time_str: str | None, end_time_str: str | None
) -> tuple[time | None, time | None]:
    """
    Parse ISO time strings to time objects.

    Args:
        start_time_str: Start time from API (ISO format: "HH:MM:SS" or "HH:MM")
        end_time_str: End time from API (ISO format: "HH:MM:SS" or "HH:MM")

    Returns:
        Tuple of (start_time, end_time) as time objects, or (None, None)
    """
    start_time = _parse_iso_time(start_time_str) if start_time_str else None
    end_time = _parse_iso_time(end_time_str) if end_time_str else None
    return (start_time, end_time)


def _parse_iso_time(time_str: str) -> time | None:
    """
    Parse ISO time string to time object.

    Args:
        time_str: ISO format time string ("HH:MM:SS" or "HH:MM")

    Returns:
        time object or None if parsing fails
    """
    # Try parsing with seconds first
    for fmt in ["%H:%M:%S", "%H:%M"]:
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.time()
        except ValueError:
            continue

    logger.warning("Failed to parse time string: %s", time_str)
    return None


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

    # Calculate date range
    start_date, end_date = _calculate_date_range()

    # Fetch events
    try:
        events = fetch_edmtrain_events(
            api_key=EDMTRAIN_API_KEY,
            location_ids=[NYC_LOCATION_ID],
            start_date=start_date,
            end_date=end_date,
        )
    except EDMTrainAuthError as e:
        logger.error("Authentication error: %s", e)
        sys.exit(1)
    except EDMTrainDataError as e:
        logger.error("Data error: %s", e)
        sys.exit(1)
    except EDMTrainAPIError as e:
        logger.error("API error: %s", e)
        sys.exit(1)

    if not events:
        logger.warning("No events fetched")
        sys.exit(0)

    # Convert to JSON
    events_data = [event.to_dict() for event in events]
    result = {"events": events_data, "count": len(events)}

    # Save to output
    output_file = f"output/edmtrain_events_{datetime.now().strftime('%Y-%m-%d')}.json"
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    logger.info("Wrote %d events to %s", len(events), output_file)


if __name__ == "__main__":
    main()
