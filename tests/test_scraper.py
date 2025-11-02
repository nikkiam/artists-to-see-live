"""Tests for the HTML scraper."""

import pytest
from src.techno_queers_email_scraper import _is_time_pattern, _parse_artists
from src.models import Artist


def test_time_pattern_detection():
    """Test detection of time patterns in brackets."""
    # Valid time patterns
    assert _is_time_pattern("8p-4a") is True
    assert _is_time_pattern("10p-?") is True
    assert _is_time_pattern("7-11p") is True
    assert _is_time_pattern("10p-10p|Sunday") is True
    assert _is_time_pattern("9p-2a") is True
    assert _is_time_pattern("10:30p-7a") is True

    # Invalid patterns (not times)
    assert _is_time_pattern("Nowadays") is False
    assert _is_time_pattern("fundraiser") is False
    assert _is_time_pattern("Artist Name") is False


def test_parse_artists_simple_list():
    """Test parsing simple comma-separated artist lists."""
    artist_text = "Artist1, Artist2, Artist3"
    artists = _parse_artists(artist_text)

    assert len(artists) == 3
    assert artists[0].name == "Artist1"
    assert artists[0].set_time is None
    assert artists[1].name == "Artist2"
    assert artists[2].name == "Artist3"


def test_parse_artists_with_set_times():
    """Test parsing artists with set times."""
    artist_text = "10-1: Solofan, 1-4: Morenxxx b2b Shyboi, 4-7: DJ Hell"
    artists = _parse_artists(artist_text)

    assert len(artists) == 3
    assert artists[0].name == "Solofan"
    assert artists[0].set_time == "10-1"
    assert artists[1].name == "Morenxxx b2b Shyboi"
    assert artists[1].set_time == "1-4"
    assert artists[2].name == "DJ Hell"
    assert artists[2].set_time == "4-7"


def test_parse_artists_handles_whitespace():
    """Test that artist parsing normalizes whitespace."""
    artist_text = "Artist  With\n  Newlines,  Another   Artist  "
    artists = _parse_artists(artist_text)

    assert len(artists) == 2
    assert artists[0].name == "Artist With Newlines"
    assert artists[1].name == "Another Artist"


def test_parse_artists_with_ellipsis():
    """Test parsing artists with ellipsis truncation."""
    artist_text = "...7-11: DJ Hell, 11-2: Saia..."
    artists = _parse_artists(artist_text)

    assert len(artists) == 2
    assert artists[0].name == "DJ Hell"
    assert artists[0].set_time == "7-11"
    assert artists[1].name == "Saia"
    assert artists[1].set_time == "11-2"
