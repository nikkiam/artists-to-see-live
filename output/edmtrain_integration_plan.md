# EDMTrain API Integration Plan

**Date:** 2025-11-21
**Status:** Planning
**Goal:** Integrate EDMTrain API as a second event data source with interoperable schema

---

## Overview

Add three new fields to the Event model that **both data sources** (Techno Queers email & EDMTrain API) can populate, then implement the EDMTrain API integration. Also fix date handling for multi-day events and implement image-based day delimiter detection.

---

## Part 1: Update Shared Event Model

### File: `src/models.py`

Add three new fields to the `Event` dataclass:

```python
@dataclass
class Event:
    """Represents a music event with venue, artists, and timing information."""

    name: str
    ticket_url: str
    venue: str | None = None
    event_time: str | None = None
    artists: list[Artist] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    day_marker: str | None = None

    # NEW FIELDS - interoperable across both sources
    event_id: str | None = None        # Unique identifier
    event_date: str | None = None      # ISO format: YYYY-MM-DD (actual event date)
    festival_ind: bool = False         # Is this a festival?
```

**Note on dates:**
- `event_date` stores the **actual date** the event occurs (not just reference date)
- For multi-day festivals, this is the start date
- Calculated by combining reference date (from filename) + day_marker (from image delimiter)

---

## Part 2: Image-Based Day Delimiter Detection

### Problem
Techno Queers emails contain image tags that mark day-of-week sections:

```html
<img src="https://gallery.eomail4.com/.../image.png" ... />
```

These images display day names ("FRIDAY", "SATURDAY", etc.) and act as section delimiters.

### Solution: Two-Pass Approach

#### Step 1: One-Time Image Mapping Creation

**New File:** `src/build_day_image_mapping.py`

**Purpose:** Parse images once to build a cached mapping of URL → day-of-week

**Implementation:**
```python
import json
from pathlib import Path
from bs4 import BeautifulSoup
import base64
import anthropic  # For vision API

def extract_image_urls(html_file: str) -> list[str]:
    """Extract all unique image URLs from HTML file."""
    # Find all <img> tags
    # Filter to likely day delimiter images (by size, position, or pattern)
    # Return unique URLs

def analyze_image_with_claude(image_url: str) -> str | None:
    """Use Claude vision API to extract day-of-week from image."""
    # Fetch image
    # Send to Claude vision API
    # Parse response for day name
    # Return normalized day (e.g., "Mon", "Tue", etc.)

def build_mapping(html_files: list[str]) -> dict[str, str]:
    """Build URL → day mapping from multiple email files."""
    # Extract all unique image URLs
    # For each URL, call analyze_image_with_claude()
    # Build dict: {url: day_name}
    # Return mapping

def main():
    """Build and save the image mapping."""
    # Find all HTML files in example_emails/
    # Build mapping
    # Save to output/day_image_mapping.json
```

**Output:** `output/day_image_mapping.json`
```json
{
  "https://gallery.eomail4.com/.../image1.png": "Fri",
  "https://gallery.eomail4.com/.../image2.png": "Sat",
  ...
}
```

**Usage:** Run once, then commit the mapping file to git.

#### Step 2: Use Mapping in Scraper

**File:** `src/techno_queers_email_scraper.py`

**Changes:**

1. **Load day image mapping** at module level:
```python
DAY_IMAGE_MAPPING_FILE = Path("output/day_image_mapping.json")

def load_day_image_mapping() -> dict[str, str]:
    """Load cached image URL → day mapping."""
    if not DAY_IMAGE_MAPPING_FILE.exists():
        logger.warning("Day image mapping not found. Run build_day_image_mapping.py first.")
        return {}

    with open(DAY_IMAGE_MAPPING_FILE) as f:
        return json.load(f)

DAY_IMAGE_MAPPING = load_day_image_mapping()
```

2. **Detect day delimiters while parsing**:

```python
def parse_html_file(filepath: str) -> list[Event]:
    """Parse HTML file with day delimiter detection."""

    soup = BeautifulSoup(html_content, "lxml")
    events = []
    current_day = None  # Track current section's day

    # Get reference date from filename
    reference_date = _extract_reference_date(filepath)

    # Find all divs and images in order
    all_elements = soup.find_all(["div", "img"])

    for element in all_elements:
        # Check if this is a day delimiter image
        if element.name == "img":
            img_url = element.get("src", "")
            if img_url in DAY_IMAGE_MAPPING:
                current_day = DAY_IMAGE_MAPPING[img_url]
                logger.debug(f"Found day delimiter: {current_day}")
                continue

        # Check if this is an event div
        if element.name == "div":
            # ... existing event parsing logic ...
            if event:
                # Calculate actual event date from reference_date + current_day
                event.day_marker = current_day
                event.event_date = _calculate_event_date(reference_date, current_day)
                events.append(event)

    return events
```

3. **Date calculation helper**:

```python
from datetime import datetime, timedelta

def _extract_reference_date(filepath: str) -> datetime:
    """Extract reference date from filename (e.g., '2025-11-8.html')."""
    date_match = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", Path(filepath).stem)
    if not date_match:
        raise ValueError(f"Could not extract date from filename: {filepath}")

    return datetime.strptime(date_match.group(1), "%Y-%m-%d")

def _calculate_event_date(reference_date: datetime, day_marker: str | None) -> str | None:
    """Calculate actual event date from reference date and day marker.

    Args:
        reference_date: Date from email filename (e.g., 2025-11-08)
        day_marker: Day of week (e.g., "Fri", "Sat", "Sun")

    Returns:
        ISO formatted date string (YYYY-MM-DD) or None
    """
    if not day_marker:
        return None

    # Map day markers to weekday numbers (0=Monday, 6=Sunday)
    day_map = {
        "Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3,
        "Fri": 4, "Sat": 5, "Sun": 6
    }

    target_weekday = day_map.get(day_marker)
    if target_weekday is None:
        return None

    # Find the date of the target weekday in the same week as reference_date
    # (Assuming events are in the same week or following week)
    current_weekday = reference_date.weekday()
    days_ahead = target_weekday - current_weekday

    # If the day is before the reference date's weekday, assume it's next week
    if days_ahead < 0:
        days_ahead += 7

    event_date = reference_date + timedelta(days=days_ahead)
    return event_date.strftime("%Y-%m-%d")
```

---

## Part 3: Update Techno Queers Email Scraper (Other Fields)

### File: `src/techno_queers_email_scraper.py`

**Additional changes to `_parse_event_div()` function:**

1. **Generate `event_id`** - Create hash from `ticket_url`:
```python
import hashlib

def _generate_event_id(ticket_url: str) -> str:
    """Generate unique event ID from ticket URL."""
    return hashlib.md5(ticket_url.encode()).hexdigest()[:12]
```

2. **Detect `festival_ind`** - Heuristic based on event name:
```python
def _detect_festival(event_name: str) -> bool:
    """Detect if event is likely a festival based on name."""
    festival_keywords = ["festival", "fest", "palooza", "summit", "gathering"]
    return any(keyword in event_name.lower() for keyword in festival_keywords)
```

**Update `_parse_event_div()` to use these:**
```python
def _parse_event_div(div) -> Event | None:
    # ... existing parsing logic ...

    return Event(
        name=event_name,
        ticket_url=ticket_url,
        venue=venue,
        event_time=event_time,
        artists=artists,
        tags=tags,
        day_marker=None,  # Set by parse_html_file
        event_id=_generate_event_id(ticket_url),
        event_date=None,  # Set by parse_html_file
        festival_ind=_detect_festival(event_name),
    )
```

---

## Part 4: Update Data Loader

### File: `src/data_loader.py`

Update `load_events()` to handle new optional fields:

```python
def load_events(filepath: Path) -> list[Event]:
    """Load events from JSON file."""
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
            event_id=event.get("event_id"),              # NEW
            event_date=event.get("event_date"),          # NEW
            festival_ind=event.get("festival_ind", False), # NEW with default
        )
        for event in data["events"]
    ]

    logger.info("Loaded %d events", len(events))
    return events
```

---

## Part 5: Create EDMTrain API Fetcher

### File: `src/edmtrain_api_fetcher.py`

**Complete new module:**

```python
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
        api_event.get("startTime"),
        api_event.get("endTime")
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

    return (
        today.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d")
    )


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
```

---

## Part 6: Field Mapping Summary

| Field | Techno Queers Source | EDMTrain Source |
|-------|---------------------|-----------------|
| `event_id` | MD5 hash of `ticket_url` (12 chars) | API `id` field (as string) |
| `event_date` | Calculated from filename date + day_marker | API `date` field (ISO format) |
| `festival_ind` | Keyword detection in event name | API `festivalInd` boolean |
| `day_marker` | Parsed from image delimiter | Derived from `event_date` |

---

## Implementation Order

1. ✅ Update `Event` model in `src/models.py` (add 3 new fields)
2. ✅ Update `src/data_loader.py` to handle new fields
3. ✅ Create `src/build_day_image_mapping.py` (one-time image analysis)
4. ✅ Run image mapping builder on existing emails
5. ✅ Update `src/techno_queers_email_scraper.py`:
   - Load day image mapping
   - Detect day delimiters
   - Calculate event dates
   - Generate event IDs
   - Detect festivals
6. ✅ Create `src/edmtrain_api_fetcher.py`
7. ✅ Test Techno Queers scraper with new schema
8. ✅ Test EDMTrain fetcher
9. ✅ Verify both outputs load correctly with `data_loader.load_events()`

---

## Testing Plan

### 1. Image Mapping Builder
```bash
uv run python -m src.build_day_image_mapping
# Expected: output/day_image_mapping.json created
# Verify: Check that image URLs map to correct days
```

### 2. Techno Queers Scraper
```bash
uv run python -m src.techno_queers_email_scraper example_emails/2025-11-8.html
# Expected: output/events_2025-11-8.json with new fields
# Verify:
#   - event_id present and unique
#   - event_date matches day_marker
#   - festival_ind detected for festivals
```

### 3. EDMTrain Fetcher
```bash
uv run python -m src.edmtrain_api_fetcher
# Expected: output/edmtrain_events_YYYY-MM-DD.json
# Verify:
#   - event_id from API
#   - event_date in ISO format
#   - festival_ind from API
#   - day_marker derived from date
```

### 4. Data Loader Compatibility
```python
from pathlib import Path
from src.data_loader import load_events

# Test loading both sources
tq_events = load_events(Path("output/events_2025-11-8.json"))
edt_events = load_events(Path("output/edmtrain_events_2025-11-21.json"))

# Verify new fields accessible
assert all(e.event_id for e in tq_events)
assert all(e.event_date for e in edt_events)
```

---

## Open Questions

1. **Artist ID tracking**: How do we want to build the artist ID cache?
   - Option A: Separate background process that maintains artist DB
   - Option B: Add to `build_day_image_mapping.py` or separate script
   - Option C: Defer for future iteration

2. **Image mapping updates**: When new emails arrive with new image URLs:
   - Re-run `build_day_image_mapping.py` on all emails
   - Or detect missing URLs and only analyze new ones

3. **Multi-day festivals**: For festivals spanning multiple days:
   - Currently store start date only
   - Future: Add `end_date` field?

---

## Success Criteria

- [ ] Both data sources produce events with `event_id`, `event_date`, `festival_ind`
- [ ] Techno Queers events have accurate dates derived from day delimiters
- [ ] Image mapping works across multiple email files
- [ ] EDMTrain API returns 2 weeks of events
- [ ] All events can be loaded by `data_loader.load_events()`
- [ ] Output JSON schemas are identical between sources
- [ ] Zero linting errors (Ruff)
- [ ] All functions have type hints
- [ ] Logging to files (no print statements)
