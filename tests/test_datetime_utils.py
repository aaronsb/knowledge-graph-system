"""
Tests for datetime_utils module (ADR-056)

Tests timezone-aware datetime utilities to prevent naive/aware comparison errors.
"""

import pytest
from datetime import datetime, timezone, timedelta
from src.api.lib.datetime_utils import (
    utcnow,
    utc_from_timestamp,
    utc_from_iso,
    ensure_utc,
    is_expired,
    timedelta_from_now,
    to_iso,
    format_duration
)


class TestUtcnow:
    """Tests for utcnow() function."""

    def test_returns_aware_datetime(self):
        """utcnow() should return timezone-aware datetime."""
        now = utcnow()
        assert now.tzinfo is not None
        assert now.tzinfo == timezone.utc

    def test_returns_current_time(self):
        """utcnow() should return current UTC time."""
        before = datetime.now(timezone.utc)
        result = utcnow()
        after = datetime.now(timezone.utc)

        assert before <= result <= after

    def test_is_datetime_instance(self):
        """utcnow() should return datetime instance."""
        result = utcnow()
        assert isinstance(result, datetime)


class TestUtcFromTimestamp:
    """Tests for utc_from_timestamp() function."""

    def test_converts_timestamp_to_utc(self):
        """utc_from_timestamp() should convert Unix timestamp to UTC datetime."""
        timestamp = 1699027200.0  # 2023-11-03 12:00:00 UTC
        result = utc_from_timestamp(timestamp)

        assert result.tzinfo == timezone.utc
        assert result.year == 2023
        assert result.month == 11
        assert result.day == 3

    def test_preserves_timezone_info(self):
        """utc_from_timestamp() should always include timezone info."""
        timestamp = 0.0  # Unix epoch
        result = utc_from_timestamp(timestamp)

        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc


class TestUtcFromIso:
    """Tests for utc_from_iso() function."""

    def test_parses_iso_with_z_suffix(self):
        """utc_from_iso() should parse ISO string with 'Z' suffix."""
        iso_string = '2025-11-04T12:00:00Z'
        result = utc_from_iso(iso_string)

        assert result.tzinfo == timezone.utc
        assert result.year == 2025
        assert result.month == 11
        assert result.day == 4
        assert result.hour == 12

    def test_parses_iso_with_offset(self):
        """utc_from_iso() should parse ISO string with timezone offset."""
        iso_string = '2025-11-04T12:00:00+00:00'
        result = utc_from_iso(iso_string)

        assert result.tzinfo == timezone.utc

    def test_assumes_utc_for_naive_iso(self):
        """utc_from_iso() should assume UTC for naive ISO strings."""
        iso_string = '2025-11-04T12:00:00'
        result = utc_from_iso(iso_string)

        assert result.tzinfo == timezone.utc

    def test_converts_other_timezone_to_utc(self):
        """utc_from_iso() should convert non-UTC timezone to UTC."""
        # 4am PST (UTC-8) = 12pm UTC
        iso_string = '2025-11-04T04:00:00-08:00'
        result = utc_from_iso(iso_string)

        assert result.tzinfo == timezone.utc
        assert result.hour == 12  # Converted to UTC

    def test_raises_on_invalid_format(self):
        """utc_from_iso() should raise ValueError for invalid ISO format."""
        with pytest.raises(ValueError, match="Invalid ISO 8601"):
            utc_from_iso('not-a-date')


class TestEnsureUtc:
    """Tests for ensure_utc() function."""

    def test_adds_timezone_to_naive_datetime(self):
        """ensure_utc() should add UTC timezone to naive datetime."""
        naive = datetime(2025, 11, 4, 12, 0, 0)
        result = ensure_utc(naive)

        assert result.tzinfo == timezone.utc
        assert result.year == 2025
        assert result.month == 11
        assert result.day == 4
        assert result.hour == 12

    def test_converts_pst_to_utc(self):
        """ensure_utc() should convert PST datetime to UTC."""
        # 4am PST (UTC-8)
        pst = timezone(timedelta(hours=-8))
        dt_pst = datetime(2025, 11, 4, 4, 0, 0, tzinfo=pst)

        result = ensure_utc(dt_pst)

        assert result.tzinfo == timezone.utc
        assert result.hour == 12  # 4am PST = 12pm UTC

    def test_preserves_utc_datetime(self):
        """ensure_utc() should return UTC datetime unchanged."""
        dt_utc = datetime(2025, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
        result = ensure_utc(dt_utc)

        assert result == dt_utc
        assert result.tzinfo == timezone.utc


class TestIsExpired:
    """Tests for is_expired() function."""

    def test_returns_true_for_past_datetime(self):
        """is_expired() should return True for past datetime."""
        past = utcnow() - timedelta(hours=1)
        assert is_expired(past) is True

    def test_returns_false_for_future_datetime(self):
        """is_expired() should return False for future datetime."""
        future = utcnow() + timedelta(hours=1)
        assert is_expired(future) is False

    def test_accepts_custom_now_parameter(self):
        """is_expired() should accept custom 'now' parameter for testing."""
        expires_at = datetime(2025, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
        mock_now = datetime(2025, 11, 4, 11, 0, 0, tzinfo=timezone.utc)

        assert is_expired(expires_at, now=mock_now) is False

        mock_now = datetime(2025, 11, 4, 13, 0, 0, tzinfo=timezone.utc)
        assert is_expired(expires_at, now=mock_now) is True

    def test_handles_naive_datetimes_safely(self):
        """is_expired() should handle naive datetimes by assuming UTC."""
        # Create naive datetimes that will be interpreted as UTC
        base = datetime(2025, 11, 4, 12, 0, 0)  # Naive UTC equivalent

        # Naive datetime in the past (relative to base)
        naive_past = datetime(2025, 11, 4, 10, 0, 0)
        mock_now = datetime(2025, 11, 4, 11, 0, 0, tzinfo=timezone.utc)
        assert is_expired(naive_past, now=mock_now) is True

        # Naive datetime in the future (relative to base)
        naive_future = datetime(2025, 11, 4, 14, 0, 0)
        mock_now = datetime(2025, 11, 4, 13, 0, 0, tzinfo=timezone.utc)
        assert is_expired(naive_future, now=mock_now) is False


class TestTimedeltaFromNow:
    """Tests for timedelta_from_now() function."""

    def test_creates_future_datetime(self):
        """timedelta_from_now() should create future datetime."""
        before = utcnow()
        future = timedelta_from_now(hours=1)
        after = utcnow()

        assert future > before
        assert future > after
        assert future.tzinfo == timezone.utc

    def test_creates_past_datetime_with_negative_values(self):
        """timedelta_from_now() should create past datetime with negative values."""
        before = utcnow()
        past = timedelta_from_now(hours=-1)
        after = utcnow()

        assert past < before
        assert past < after
        assert past.tzinfo == timezone.utc

    def test_supports_multiple_units(self):
        """timedelta_from_now() should support days, hours, minutes, seconds."""
        result = timedelta_from_now(days=1, hours=2, minutes=30, seconds=15)

        # Should be roughly 26.5 hours in the future
        now = utcnow()
        delta = result - now
        total_seconds = delta.total_seconds()

        # Allow some tolerance for execution time
        expected = (1 * 86400) + (2 * 3600) + (30 * 60) + 15
        assert abs(total_seconds - expected) < 1  # Within 1 second


class TestToIso:
    """Tests for to_iso() function."""

    def test_converts_datetime_to_iso_string(self):
        """to_iso() should convert datetime to ISO 8601 string."""
        dt = datetime(2025, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
        result = to_iso(dt)

        assert isinstance(result, str)
        assert '2025-11-04' in result
        assert '12:00:00' in result
        assert '+00:00' in result or 'Z' in result

    def test_includes_timezone_for_utc(self):
        """to_iso() should include timezone info in output."""
        dt = utcnow()
        result = to_iso(dt)

        assert 'T' in result  # ISO format separator
        assert ('+00:00' in result) or ('Z' in result)

    def test_handles_naive_datetime_gracefully(self):
        """to_iso() should handle naive datetime by assuming UTC."""
        naive = datetime(2025, 11, 4, 12, 0, 0)
        result = to_iso(naive)

        # Should still produce valid ISO string
        assert isinstance(result, str)
        assert '2025-11-04' in result


class TestFormatDuration:
    """Tests for format_duration() function."""

    def test_formats_hours_and_minutes(self):
        """format_duration() should format timedelta as human-readable string."""
        delta = timedelta(hours=2, minutes=30)
        result = format_duration(delta)

        assert '2 hours' in result
        assert '30 minutes' in result

    def test_formats_days(self):
        """format_duration() should include days if present."""
        delta = timedelta(days=3, hours=2)
        result = format_duration(delta)

        assert '3 days' in result
        assert '2 hours' in result

    def test_formats_seconds_only_when_no_larger_units(self):
        """format_duration() should show seconds only if no larger units."""
        delta = timedelta(seconds=45)
        result = format_duration(delta)

        assert '45 seconds' in result

    def test_handles_negative_duration_as_expired(self):
        """format_duration() should return 'expired' for negative duration."""
        delta = timedelta(hours=-1)
        result = format_duration(delta)

        assert result == "expired"

    def test_handles_zero_duration(self):
        """format_duration() should handle zero duration."""
        delta = timedelta(seconds=0)
        result = format_duration(delta)

        assert result == "0 seconds"

    def test_uses_singular_for_one_unit(self):
        """format_duration() should use singular form for 1 day/hour/minute."""
        delta = timedelta(days=1, hours=1, minutes=1)
        result = format_duration(delta)

        assert '1 day' in result
        assert '1 hour' in result
        assert '1 minute' in result
        assert 'days' not in result or '1 day' in result


class TestIntegration:
    """Integration tests combining multiple datetime_utils functions."""

    def test_roundtrip_iso_conversion(self):
        """Test converting to ISO and back preserves value."""
        original = utcnow()
        iso_string = to_iso(original)
        parsed = utc_from_iso(iso_string)

        # Should be equal within microsecond precision
        delta = abs((original - parsed).total_seconds())
        assert delta < 0.001

    def test_expiration_workflow(self):
        """Test typical token expiration workflow."""
        # Create expiration time 1 hour from now
        expires_at = timedelta_from_now(hours=1)

        # Should not be expired yet
        assert is_expired(expires_at) is False

        # Simulate time passing (mock now as 2 hours from original now)
        future_now = utcnow() + timedelta(hours=2)
        assert is_expired(expires_at, now=future_now) is True

    def test_naive_to_aware_comparison(self):
        """Test that ensure_utc prevents comparison errors."""
        naive = datetime(2025, 11, 4, 12, 0, 0)
        aware = datetime(2025, 11, 4, 12, 0, 0, tzinfo=timezone.utc)

        # This would raise TypeError without ensure_utc
        naive_utc = ensure_utc(naive)
        aware_utc = ensure_utc(aware)

        # Should now be comparable
        assert naive_utc == aware_utc
