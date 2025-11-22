"""Tests for Techno Queers time parser."""

from datetime import time

from src.techno_queers_email_scraper import (
    _parse_single_time,
    _parse_techno_queers_time,
)


class TestParseSingleTime:
    """Tests for _parse_single_time function."""

    def test_parse_am_times(self):
        """Test parsing AM times."""
        assert _parse_single_time("8a") == time(8, 0)
        assert _parse_single_time("9a") == time(9, 0)
        assert _parse_single_time("11a") == time(11, 0)

    def test_parse_pm_times(self):
        """Test parsing PM times."""
        assert _parse_single_time("8p") == time(20, 0)
        assert _parse_single_time("9p") == time(21, 0)
        assert _parse_single_time("11p") == time(23, 0)

    def test_parse_noon_and_midnight(self):
        """Test parsing 12am (midnight) and 12pm (noon)."""
        assert _parse_single_time("12a") == time(0, 0)  # Midnight
        assert _parse_single_time("12p") == time(12, 0)  # Noon

    def test_parse_special_keywords(self):
        """Test parsing special time keywords."""
        assert _parse_single_time("midnight") == time(0, 0)
        assert _parse_single_time("noon") == time(12, 0)

    def test_parse_times_with_minutes(self):
        """Test parsing times with minutes."""
        assert _parse_single_time("8:30p") == time(20, 30)
        assert _parse_single_time("10:45a") == time(10, 45)
        assert _parse_single_time("12:15p") == time(12, 15)
        assert _parse_single_time("12:30a") == time(0, 30)

    def test_parse_case_insensitive(self):
        """Test that parsing is case insensitive."""
        assert _parse_single_time("8P") == time(20, 0)
        assert _parse_single_time("8A") == time(8, 0)
        assert _parse_single_time("MIDNIGHT") == time(0, 0)
        assert _parse_single_time("NOON") == time(12, 0)

    def test_parse_with_whitespace(self):
        """Test that extra whitespace is handled."""
        assert _parse_single_time("  8p  ") == time(20, 0)
        assert _parse_single_time(" noon ") == time(12, 0)

    def test_parse_invalid_format(self):
        """Test that invalid formats return None."""
        assert _parse_single_time("25p") is None  # Invalid hour
        assert _parse_single_time("8") is None  # Missing am/pm
        assert _parse_single_time("8:70p") is None  # Invalid minute
        assert _parse_single_time("not-a-time") is None


class TestParseTechnoQueersTime:
    """Tests for _parse_techno_queers_time function."""

    def test_parse_time_range(self):
        """Test parsing time ranges (start-end)."""
        start, end = _parse_techno_queers_time("8p-4a")
        assert start == time(20, 0)
        assert end == time(4, 0)

        start, end = _parse_techno_queers_time("10p-6a")
        assert start == time(22, 0)
        assert end == time(6, 0)

    def test_parse_time_range_with_minutes(self):
        """Test parsing time ranges with minutes."""
        start, end = _parse_techno_queers_time("8:30p-4:30a")
        assert start == time(20, 30)
        assert end == time(4, 30)

    def test_parse_single_time_only(self):
        """Test parsing when only start time is provided."""
        start, end = _parse_techno_queers_time("8p")
        assert start == time(20, 0)
        assert end is None

        start, end = _parse_techno_queers_time("10:30p")
        assert start == time(22, 30)
        assert end is None

    def test_parse_special_times(self):
        """Test parsing with special time keywords."""
        start, end = _parse_techno_queers_time("midnight-6a")
        assert start == time(0, 0)
        assert end == time(6, 0)

        start, end = _parse_techno_queers_time("noon-8p")
        assert start == time(12, 0)
        assert end == time(20, 0)

    def test_parse_none_input(self):
        """Test that None input returns (None, None)."""
        start, end = _parse_techno_queers_time(None)
        assert start is None
        assert end is None

    def test_parse_empty_string(self):
        """Test that empty string returns (None, None)."""
        start, end = _parse_techno_queers_time("")
        assert start is None
        assert end is None

    def test_parse_invalid_format(self):
        """Test that invalid formats return (None, None)."""
        # Too many parts
        start, end = _parse_techno_queers_time("8p-4a-2p")
        assert start is None
        assert end is None

    def test_parse_with_invalid_times(self):
        """Test parsing when individual times are invalid."""
        start, end = _parse_techno_queers_time("25p-4a")
        assert start is None  # Invalid start time
        assert end == time(4, 0)

        start, end = _parse_techno_queers_time("8p-25a")
        assert start == time(20, 0)
        assert end is None  # Invalid end time
