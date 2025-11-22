"""Data models for events and artists."""

from dataclasses import dataclass, field
from datetime import time

# Tier classification thresholds for artist connections
TIER_VERY_SIMILAR_THRESHOLD = 7.0
TIER_SIMILAR_THRESHOLD = 5.0
TIER_MODERATELY_RELATED_THRESHOLD = 3.0

TIER_NAMES = {
    "very_similar": "Very Similar Artists",
    "similar": "Similar Artists",
    "moderately_related": "Moderately Related Artists",
    "distantly_related": "Distantly Related Artists",
}


@dataclass(frozen=True)
class SimilarArtist:
    """Represents a similar artist with relationship metrics."""

    name: str
    rank: int
    relationship_strength: float


@dataclass(frozen=True)
class ArtistSimilarityData:
    """
    Contains similarity data for a successfully scraped artist.

    Note: Only successful scrapes should be loaded into this structure.
    Failed/skipped scrapes are filtered out at load time.
    """

    artist_name: str
    similar_artists: tuple[SimilarArtist, ...]


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
    start_time: time | None = None  # Event start time (time object, no date)
    end_time: time | None = None  # Event end time (time object, no date)
    artists: list[Artist] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    day_marker: str | None = None
    # Interoperable fields across data sources (Techno Queers, EDMTrain)
    event_id: str | None = None  # Unique identifier
    event_date: str | None = None  # ISO format: YYYY-MM-DD (actual event date)
    festival_ind: bool = False  # Is this a festival?


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


@dataclass(frozen=True)
class ArtistPairConnections:
    """
    Groups multiple connection paths between the same event artist and favorite artist.

    Contains the top paths (max 3) for a single (event_artist, favorite_artist) pair,
    sorted by path_score descending (best paths first).
    """

    event_artist: str
    favorite_artist: str
    paths: tuple[ConnectionPath, ...]  # Max 3 paths, sorted by path_score descending
    best_path_score: float  # Convenience field: paths[0].path_score
    best_avg_strength: float  # Convenience field: paths[0].avg_strength
    event_name: str
    event_venue: str | None
    event_url: str
