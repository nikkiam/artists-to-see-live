"""HTML parser for extracting event information from email content."""

import hashlib
import json
import logging
import re
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

from bs4 import BeautifulSoup

from src.date_utils import DAY_TO_WEEKDAY
from src.models import Artist, Event

logger = logging.getLogger(__name__)

# Constants
NON_EVENT_STREAK_THRESHOLD = 3
MIN_ARGV_LENGTH = 2

# Festival detection heuristic: Events with more than this many artists
# are likely festivals. This threshold is based on observation that typical
# club nights have 5-8 artists, while festivals tend to have 15+ artists
# across multiple stages
FESTIVAL_ARTIST_THRESHOLD = 10

# Time parsing constants
NOON_HOUR_12 = 12  # 12pm in 12-hour format
MIDNIGHT_HOUR_24 = 0  # Midnight in 24-hour format
PM_HOUR_OFFSET = 12  # Hours to add for PM times (except noon)
MAX_HOUR_24 = 23  # Maximum valid hour in 24-hour format
MAX_MINUTE = 59  # Maximum valid minute
TIME_RANGE_PART_COUNT = 2  # Expected parts when splitting time range (start-end)

# Day-of-week image mapping (Thu/Fri/Sat/Sun use images instead of text)
# These image URLs are specific to the Techno Queers email template
# and map day-of-week images to their corresponding day abbreviations
_IMG_BASE = "https://gallery.eomail4.com/62a6a8da-856c-11ee-aacc-278c4c25eb7d"
DAY_IMAGE_MAPPING = {
    (
        f"{_IMG_BASE}%2F1700244826919-7138264c-a74e-bcb4-7687-368e83a7d8c7.png"
    ): "Thu",
    (
        f"{_IMG_BASE}%2F1700244961959-2d3560ab-8662-308f-2b83-f302eb7ac219.png"
    ): "Fri",
    (
        f"{_IMG_BASE}%2F1700245086670-fe1d7559-3c5a-4084-95ab-d3e1ba1de408.png"
    ): "Sat",
    (
        f"{_IMG_BASE}%2F1700245283470-98a350a2-632f-2e42-bf5b-41443cb53ccb.png"
    ): "Sun",
}


def _generate_event_id(ticket_url: str) -> str:
    """Generate unique event ID from ticket URL using MD5 hash."""
    return hashlib.md5(ticket_url.encode(), usedforsecurity=False).hexdigest()


def _parse_techno_queers_time(
    time_str: str | None,
) -> tuple[time | None, time | None]:
    """
    Parse Techno Queers time format to time objects.

    Examples: "8p-4a", "10p", "midnight-6a"

    Args:
        time_str: Time string in format like "8p-4a" (8pm to 4am)

    Returns:
        Tuple of (start_time, end_time) as time objects, or (None, None)
    """
    if not time_str:
        return (None, None)

    # Split on dash to get start and end
    parts = time_str.split("-")

    if len(parts) == 1:
        # Only start time provided
        start_time = _parse_single_time(parts[0].strip())
        return (start_time, None)

    if len(parts) == TIME_RANGE_PART_COUNT:
        # Both start and end times
        start_time = _parse_single_time(parts[0].strip())
        end_time = _parse_single_time(parts[1].strip())
        return (start_time, end_time)

    # Invalid format
    return (None, None)


def _parse_single_time(time_part: str) -> time | None:
    """
    Parse a single time component like "8p", "4a", "10:30p", "midnight".

    Args:
        time_part: Single time string (e.g., "8p", "4a", "10:30p")

    Returns:
        time object or None if parsing fails
    """
    time_part = time_part.lower().strip()

    # Handle special cases
    if time_part == "midnight":
        return time(MIDNIGHT_HOUR_24, 0)
    if time_part == "noon":
        return time(NOON_HOUR_12, 0)

    # Extract hour/minute and am/pm
    # Pattern: optional digits, optional colon and digits, then 'a' or 'p'
    match = re.match(r"^(\d{1,2})(?::(\d{2}))?([ap])$", time_part)
    if not match:
        logger.warning("Failed to parse time component: %s", time_part)
        return None

    hour_str, minute_str, period = match.groups()
    hour = int(hour_str)
    minute = int(minute_str) if minute_str else 0

    # Convert to 24-hour format
    if period == "a":  # AM
        if hour == NOON_HOUR_12:
            hour = MIDNIGHT_HOUR_24  # 12am = midnight
    elif hour != NOON_HOUR_12:  # PM (except 12pm)
        hour += PM_HOUR_OFFSET  # 1pm = 13:00, but 12pm stays 12:00

    # Validate hour and minute
    if not (0 <= hour <= MAX_HOUR_24) or not (0 <= minute <= MAX_MINUTE):
        logger.warning("Invalid time values: hour=%d, minute=%d", hour, minute)
        return None

    return time(hour, minute)


def _calculate_event_date(reference_date: str, day_marker: str | None) -> str | None:
    """
    Calculate actual event date from reference date and day marker.

    Args:
        reference_date: Reference date in YYYY-MM-DD format
        day_marker: Day abbreviation (Mon, Tue, Wed, Thu, Fri, Sat, Sun)

    Returns:
        Event date in YYYY-MM-DD format, or None if day_marker is None
    """
    if not day_marker or day_marker not in DAY_TO_WEEKDAY:
        return None

    ref_date = datetime.strptime(reference_date, "%Y-%m-%d")
    target_weekday = DAY_TO_WEEKDAY[day_marker]
    current_weekday = ref_date.weekday()

    # Calculate days ahead (0-6)
    days_ahead = (target_weekday - current_weekday) % 7

    event_date = ref_date + timedelta(days=days_ahead)
    return event_date.strftime("%Y-%m-%d")


def _is_festival(event_name: str, artists: list[Artist], tags: list[str]) -> bool:
    """
    Detect if event is a festival based on name, artist count, and tags.

    Args:
        event_name: Event name
        artists: List of artists
        tags: List of tags

    Returns:
        True if event appears to be a festival
    """
    # Check for "festival" in name or tags
    name_lower = event_name.lower()
    if "festival" in name_lower or "fest" in name_lower:
        return True

    if "festival" in tags:
        return True

    # Many artists suggests festival (see FESTIVAL_ARTIST_THRESHOLD constant)
    return len(artists) > FESTIVAL_ARTIST_THRESHOLD


def parse_html_file(filepath: str, reference_date: str) -> list[Event]:
    """
    Parse an HTML file containing event listings.

    Args:
        filepath: Path to the HTML file to parse
        reference_date: Reference date in YYYY-MM-DD format (from filename)

    Returns:
        List of Event objects extracted from the HTML
    """
    with open(filepath, encoding="utf-8") as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, "lxml")
    events = []

    # Find all image-based day delimiters (Thu/Fri/Sat/Sun only)
    day_delimiter_images = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src in DAY_IMAGE_MAPPING:
            day_delimiter_images.append((img, DAY_IMAGE_MAPPING[src]))
            logger.debug("Found image day delimiter: %s", DAY_IMAGE_MAPPING[src])

    logger.info("Found %d image day delimiters", len(day_delimiter_images))

    # Find all divs that might contain events (divs with '+' character)
    all_divs = soup.find_all("div")
    non_event_streak = 0
    seen_urls = set()  # Track URLs to avoid duplicates

    for div in all_divs:
        text = div.get_text(strip=True)

        # Check if this div starts with a '+'
        if not text.startswith("+"):
            continue

        # Event divs must have both '+' and a link
        link = div.find("a")
        if not link:
            continue

        # Check if this has bracket patterns (indicating it's an event)
        # Just check for opening bracket - simpler and more reliable
        has_brackets = "[" in text

        if not has_brackets:
            # If we've already found events and now hitting non-bracket content,
            # we might be in the advice section
            non_event_streak += 1

            # If we've seen 3+ non-event divs in a row, stop
            if non_event_streak >= NON_EVENT_STREAK_THRESHOLD and len(events) > 0:
                break
            continue

        # Reset streak when we find a potential event
        non_event_streak = 0

        # Determine day marker for this event
        # Check if this div comes after any image delimiter
        image_day_marker = None
        for img, day_name in day_delimiter_images:
            # Check if image comes before this div in document order
            # We compare by checking if the image is in the div's previous siblings tree
            if img in div.find_all_previous():
                image_day_marker = day_name
                # Keep checking - we want the LAST (most recent) image before this div

        # Try to parse as an event
        try:
            event = _parse_event_div(div, reference_date, image_day_marker)
            if event and event.ticket_url not in seen_urls:
                seen_urls.add(event.ticket_url)
                events.append(event)
        except (AttributeError, ValueError, IndexError, TypeError, KeyError) as e:
            # Log and skip malformed events
            logger.warning("Failed to parse event: %s", e)
            continue

    return events


def _parse_event_div(
    div, reference_date: str, fallback_day_marker: str | None
) -> Event | None:
    """
    Parse a single event div element.

    Args:
        div: BeautifulSoup div element
        reference_date: Reference date in YYYY-MM-DD format
        fallback_day_marker: Day marker from image delimiter
                             (used if no text marker found)

    Returns:
        Event object or None if parsing fails
    """
    # Get the full text content
    full_text = div.get_text(separator=" ", strip=False)

    # Check for day marker: + [Day] +
    day_match = re.search(r"\+\s*\[([A-Z][a-z]{2})\]\s*\+", full_text)
    day_marker = day_match.group(1) if day_match else fallback_day_marker

    # Find the first link (event name and URL)
    link = div.find("a")
    if not link:
        return None

    event_name = link.get_text(strip=True)
    ticket_url = link.get("href", "")

    # Get text after the link for parsing metadata
    # We need to extract the text that comes after the </a> tag
    link_parent = link.parent
    text_after_link = ""

    # Try to get text after the link
    for element in link.next_siblings:
        if hasattr(element, "get_text"):
            text_after_link += element.get_text(separator=" ")
        else:
            text_after_link += str(element)

    # Also check if there's text in the same element after the link
    if link_parent:
        parent_text = link_parent.get_text(separator=" ")
        link_text = link.get_text()
        if link_text in parent_text:
            idx = parent_text.find(link_text) + len(link_text)
            text_after_link = parent_text[idx:] + " " + text_after_link

    # Parse bracket patterns from the text after the link
    venue, event_time_str, tags, artists = _parse_metadata(text_after_link)

    # Parse event time string to time objects
    start_time, end_time = _parse_techno_queers_time(event_time_str)

    # Generate new fields
    event_id = _generate_event_id(ticket_url)
    event_date = _calculate_event_date(reference_date, day_marker)
    festival_ind = _is_festival(event_name, artists, tags)

    return Event(
        name=event_name,
        ticket_url=ticket_url,
        venue=venue,
        start_time=start_time,
        end_time=end_time,
        artists=artists,
        tags=tags,
        day_marker=day_marker,
        event_id=event_id,
        event_date=event_date,
        festival_ind=festival_ind,
    )


def _parse_metadata(
    text: str,
) -> tuple[str | None, str | None, list[str], list[Artist]]:
    """
    Parse venue, time, tags, and artists from bracket-delimited text.

    Args:
        text: Text content after the event link

    Returns:
        Tuple of (venue, event_time, tags, artists)
    """
    # Find all bracket patterns
    bracket_pattern = r"\[([^\]]+)\]"
    matches = re.findall(bracket_pattern, text)

    if not matches:
        return None, None, [], []

    venue = None
    event_time = None
    tags = []
    artist_brackets = []

    # Classify each bracket
    for i, match in enumerate(matches):
        content = match.strip()

        # Check if it's a tag (starts with #)
        if content.startswith("#"):
            # Extract all hashtags from this bracket
            tag_matches = re.findall(r"#(\w+)", content)
            tags.extend(tag_matches)

        # Check if it's a time pattern
        elif _is_time_pattern(content):
            event_time = content

        # Otherwise, it might be artists or venue
        else:
            artist_brackets.append((i, content))

    # Heuristic: venue is typically the last non-tag bracket before time
    # Artists are typically the first bracket(s) after the event name
    if artist_brackets:
        # If we have a time, find the bracket just before it
        if event_time:
            # Find the position of the time bracket
            time_pos = None
            for i, match in enumerate(matches):
                if _is_time_pattern(match.strip()):
                    time_pos = i
                    break

            if time_pos is not None:
                # Venue is the last artist_bracket before time_pos
                # Artists are all artist_brackets before the venue
                venue_candidates = [b for b in artist_brackets if b[0] < time_pos]
                if venue_candidates:
                    venue_bracket = venue_candidates[-1]
                    venue = venue_bracket[1]
                    artist_brackets = [
                        b for b in artist_brackets if b[0] < venue_bracket[0]
                    ]

        # If no venue found yet, assume last bracket is venue
        if not venue and artist_brackets:
            venue = artist_brackets[-1][1]
            artist_brackets = artist_brackets[:-1]

    # Parse artists from remaining brackets
    artists = []
    for _, artist_text in artist_brackets:
        artists.extend(_parse_artists(artist_text))

    # Deduplicate artists by (name, set_time) tuple
    seen = set()
    unique_artists = []
    for artist in artists:
        key = (artist.name, artist.set_time)
        if key not in seen:
            seen.add(key)
            unique_artists.append(artist)

    # Deduplicate tags
    unique_tags = list(dict.fromkeys(tags))  # Preserves order

    return venue, event_time, unique_tags, unique_artists


def _is_time_pattern(text: str) -> bool:
    """
    Check if text matches a time pattern.

    Examples: 8p-4a, 10p-?, 7-11p, 10p-10p|Sunday, 10:30p-7a
    """
    # Pattern: number + optional :minutes + optional p/a, dash/hyphen,
    # number + optional :minutes + optional p/a/?, optional |Day
    time_regex = r"^\d{1,2}(:\d{2})?[ap]?[-]\d{0,2}(:\d{2})?[ap\?]?(\|[A-Za-z]+)?$"
    return bool(re.match(time_regex, text.strip()))


def _parse_artists(artist_text: str) -> list[Artist]:
    """
    Parse artist names and set times from a text string.

    Handles formats like:
    - Simple: "Artist1, Artist2, Artist3"
    - Timed: "10-1: Solofan, 1-4: Morenxxx b2b Shyboi"
    - Truncated: "...7-11: DJ Hell, 11-2: Saia..."

    Args:
        artist_text: Text containing artist names

    Returns:
        List of Artist objects
    """
    artists = []

    # Remove leading/trailing ellipsis and whitespace
    artist_text = artist_text.strip().strip(".")

    # Check if this is a timed format (contains time: pattern)
    # Pattern: number-number: Artist Name
    timed_pattern = r"(\d{1,2}(?::\d{2})?-\d{1,2}(?::\d{2})?):?\s*([^,]+)"
    timed_matches = re.findall(timed_pattern, artist_text)

    if timed_matches:
        # Parse timed artists
        for time, name in timed_matches:
            # Clean up name: strip whitespace and normalize newlines/spaces
            cleaned_name = re.sub(r"\s+", " ", name.strip())
            if cleaned_name and cleaned_name.lower() not in ["", "..."]:
                artists.append(Artist(name=cleaned_name, set_time=time))
    else:
        # Parse simple comma-separated list
        names = re.split(r",\s*", artist_text)
        for name in names:
            # Clean up name: strip whitespace and normalize newlines/spaces
            cleaned_name = re.sub(r"\s+", " ", name.strip())
            # Skip empty, ellipsis, or very short names
            if cleaned_name and len(cleaned_name) > 1 and cleaned_name != "...":
                artists.append(Artist(name=cleaned_name, set_time=None))

    return artists


def main():
    """Main CLI function for running the email scraper directly."""
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("email_scraper.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    if len(sys.argv) < MIN_ARGV_LENGTH:
        logger.error("Usage: python -m src.techno_queers_email_scraper <html_file>")
        sys.exit(1)

    html_file = sys.argv[1]

    # Extract date from filename for output naming
    html_path = Path(html_file)
    date_match = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", html_path.stem)
    if not date_match:
        logger.error(
            "Could not extract date from filename. Expected format: YYYY-MM-DD.html"
        )
        sys.exit(1)

    date_str = date_match.group(1)
    output_file = f"output/events_{date_str}.json"

    # Parse the HTML file with reference date
    events = parse_html_file(html_file, date_str)

    # Convert events to dictionaries for JSON serialization
    events_data = [event.to_dict() for event in events]
    result = {"events": events_data, "count": len(events)}

    # Write output file
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info("Wrote %d events to %s", len(events), output_file)


if __name__ == "__main__":
    main()
