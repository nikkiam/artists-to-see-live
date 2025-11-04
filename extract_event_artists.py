"""Extract unique event artists for scraping."""

import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load events
with open("output/events.json") as f:
    events = json.load(f)["events"]

# Extract unique artists
event_artists = set()
for event in events:
    for artist in event.get("artists", []):
        event_artists.add(artist["name"])

event_artists_list = sorted(event_artists)

# Save to file
output = {"artists": event_artists_list}

with open("output/event_artists.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

logger.info("Extracted %d unique event artists", len(event_artists_list))
logger.info("Saved to: output/event_artists.json")
