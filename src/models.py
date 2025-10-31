"""Data models for events and artists."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Artist:
    """Represents an artist performing at an event."""
    name: str
    set_time: Optional[str] = None


@dataclass
class Event:
    """Represents a music event with venue, artists, and timing information."""
    name: str
    ticket_url: str
    venue: Optional[str] = None
    event_time: Optional[str] = None
    artists: list[Artist] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    day_marker: Optional[str] = None
