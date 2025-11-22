"""Tests for EDMTrain API fetcher."""

from datetime import time

import pytest

from src.edmtrain_api_fetcher import (
    EDMTrainDataError,
    _derive_day_marker,
    _parse_event_times,
    _parse_iso_time,
)


class TestDeriveDayMarker:
    """Tests for _derive_day_marker function."""

    def test_valid_dates(self):
        """Test deriving day markers from valid ISO dates."""
        # Known dates and their expected day markers
        assert _derive_day_marker("2025-01-01") == "Wed"  # New Year 2025
        assert _derive_day_marker("2025-12-25") == "Thu"  # Christmas 2025
        assert _derive_day_marker("2024-02-29") == "Thu"  # Leap day 2024
        assert _derive_day_marker("2025-11-22") == "Sat"  # Today (from test)

    def test_all_days_of_week(self):
        """Test that all days of the week can be derived correctly."""
        # Week of 2025-11-17 to 2025-11-23
        assert _derive_day_marker("2025-11-17") == "Mon"
        assert _derive_day_marker("2025-11-18") == "Tue"
        assert _derive_day_marker("2025-11-19") == "Wed"
        assert _derive_day_marker("2025-11-20") == "Thu"
        assert _derive_day_marker("2025-11-21") == "Fri"
        assert _derive_day_marker("2025-11-22") == "Sat"
        assert _derive_day_marker("2025-11-23") == "Sun"

    def test_invalid_date_format(self):
        """Test that invalid date formats raise EDMTrainDataError."""
        with pytest.raises(EDMTrainDataError, match="Invalid date format"):
            _derive_day_marker("2025/11/22")  # Wrong separator

        with pytest.raises(EDMTrainDataError, match="Invalid date format"):
            _derive_day_marker("11-22-2025")  # Wrong order

        with pytest.raises(EDMTrainDataError, match="Invalid date format"):
            _derive_day_marker("not-a-date")

    def test_invalid_date_values(self):
        """Test that invalid date values raise EDMTrainDataError."""
        with pytest.raises(EDMTrainDataError, match="Invalid date format"):
            _derive_day_marker("2025-13-01")  # Invalid month

        with pytest.raises(EDMTrainDataError, match="Invalid date format"):
            _derive_day_marker("2025-02-30")  # Invalid day


class TestParseIsoTime:
    """Tests for _parse_iso_time function."""

    def test_parse_time_with_seconds(self):
        """Test parsing ISO time with seconds."""
        result = _parse_iso_time("14:30:45")
        assert result == time(14, 30, 45)

        result = _parse_iso_time("00:00:00")
        assert result == time(0, 0, 0)

        result = _parse_iso_time("23:59:59")
        assert result == time(23, 59, 59)

    def test_parse_time_without_seconds(self):
        """Test parsing ISO time without seconds."""
        result = _parse_iso_time("14:30")
        assert result == time(14, 30, 0)

        result = _parse_iso_time("00:00")
        assert result == time(0, 0, 0)

        result = _parse_iso_time("23:59")
        assert result == time(23, 59, 0)

    def test_parse_invalid_time_format(self):
        """Test that invalid time formats return None."""
        assert _parse_iso_time("not-a-time") is None
        assert _parse_iso_time("25:00:00") is None  # Invalid hour
        assert _parse_iso_time("14:60:00") is None  # Invalid minute
        assert _parse_iso_time("14-30-00") is None  # Wrong separator


class TestParseEventTimes:
    """Tests for _parse_event_times function."""

    def test_parse_both_times(self):
        """Test parsing when both start and end times are provided."""
        start, end = _parse_event_times("20:00:00", "04:00:00")
        assert start == time(20, 0, 0)
        assert end == time(4, 0, 0)

    def test_parse_only_start_time(self):
        """Test parsing when only start time is provided."""
        start, end = _parse_event_times("20:00", None)
        assert start == time(20, 0, 0)
        assert end is None

    def test_parse_only_end_time(self):
        """Test parsing when only end time is provided."""
        start, end = _parse_event_times(None, "04:00")
        assert start is None
        assert end == time(4, 0, 0)

    def test_parse_no_times(self):
        """Test parsing when no times are provided."""
        start, end = _parse_event_times(None, None)
        assert start is None
        assert end is None

    def test_parse_invalid_times(self):
        """Test parsing when times are invalid."""
        start, end = _parse_event_times("invalid", "also-invalid")
        assert start is None
        assert end is None
