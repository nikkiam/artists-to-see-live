"""Data models for events and artists."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Artist:
    """Represents an artist performing at an event."""

    name: str
    set_time: str | None = None


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


@dataclass(frozen=True)
class ConnectionPath:
    """Represents a connection between an event artist and a favorite artist."""

    event_artist: str
    favorite_artist: str
    path: tuple[str, ...]  # Full path including source and target
    path_strengths: tuple[float, ...]  # Relationship strength for each edge
    total_cost: float  # Sum of 1/strength (Dijkstra cost)
    path_score: float  # 1/total_cost (higher = better)
    min_strength: float  # Weakest link
    max_strength: float  # Strongest link
    avg_strength: float  # Average edge strength
    hops: int  # Path length - 1
    tier: str  # Classification based on avg_strength
    event_name: str
    event_venue: str | None
    event_url: str
