"""HTML parser for extracting event information from email content."""

import json
import logging
import re
import sys
from dataclasses import asdict
from pathlib import Path

from bs4 import BeautifulSoup

from src.models import Artist, Event

logger = logging.getLogger(__name__)

# Constants
NON_EVENT_STREAK_THRESHOLD = 3
MIN_ARGV_LENGTH = 2


def parse_html_file(filepath: str) -> list[Event]:
    """
    Parse an HTML file containing event listings.

    Args:
        filepath: Path to the HTML file to parse

    Returns:
        List of Event objects extracted from the HTML
    """
    with open(filepath, encoding="utf-8") as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, "lxml")
    events = []

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

        # Try to parse as an event
        try:
            event = _parse_event_div(div)
            if event and event.ticket_url not in seen_urls:
                seen_urls.add(event.ticket_url)
                events.append(event)
        except (AttributeError, ValueError, IndexError, TypeError, KeyError) as e:
            # Log and skip malformed events
            logger.warning("Failed to parse event: %s", e)
            continue

    return events


def _parse_event_div(div) -> Event | None:
    """
    Parse a single event div element.

    Args:
        div: BeautifulSoup div element

    Returns:
        Event object or None if parsing fails
    """
    # Get the full text content
    full_text = div.get_text(separator=" ", strip=False)

    # Check for day marker: + [Day] +
    day_marker = None
    day_match = re.search(r"\+\s*\[([A-Z][a-z]{2})\]\s*\+", full_text)
    if day_match:
        day_marker = day_match.group(1)

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
    venue, event_time, tags, artists = _parse_metadata(text_after_link)

    return Event(
        name=event_name,
        ticket_url=ticket_url,
        venue=venue,
        event_time=event_time,
        artists=artists,
        tags=tags,
        day_marker=day_marker,
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
        logger.error("Could not extract date from filename. Expected format: YYYY-MM-DD.html")
        sys.exit(1)

    date_str = date_match.group(1)
    output_file = f"output/events_{date_str}.json"

    # Parse the HTML file
    events = parse_html_file(html_file)

    # Convert events to dictionaries for JSON serialization
    events_data = [asdict(event) for event in events]
    result = {"events": events_data, "count": len(events)}

    # Write output file
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info("Wrote %d events to %s", len(events), output_file)


if __name__ == "__main__":
    main()
