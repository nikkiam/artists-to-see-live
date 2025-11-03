"""Extract unique event artists for scraping."""

import json
from pathlib import Path

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

print(f"Extracted {len(event_artists_list)} unique event artists")
print(f"Saved to: output/event_artists.json")
