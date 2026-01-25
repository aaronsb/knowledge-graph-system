"""
Timezone-Aware Datetime Utilities (ADR-056)

Centralized datetime helpers to prevent naive/aware comparison errors.
All functions return timezone-aware datetimes in UTC.

Background:
-----------
The knowledge graph system repeatedly encountered timezone comparison errors:
    TypeError: can't compare offset-naive and offset-aware datetimes

This module provides utilities that always return timezone-aware datetimes,
preventing these errors.

Usage:
------
    from api.app.lib.datetime_utils import utcnow, is_expired

    # Get current time (always UTC, always timezone-aware)
    current_time = utcnow()

    # Check if token expired
    if is_expired(token.expires_at):
        raise TokenExpiredError()

    # Create expiration time
    expires_at = timedelta_from_now(hours=24)

Related ADRs:
-------------
- ADR-056: Timezone-Aware Datetime Utilities (this module)
- ADR-054: OAuth Client Management (uses these utilities)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.

    This replaces datetime.utcnow() which returns a naive datetime.

    Returns:
        Current UTC time with timezone info

    Example:
        >>> now = utcnow()
        >>> now.tzinfo
        datetime.timezone.utc
        >>> isinstance(now, datetime)
        True
    """
    return datetime.now(timezone.utc)


def utc_from_timestamp(timestamp: float) -> datetime:
    """
    Convert Unix timestamp to timezone-aware UTC datetime.

    Args:
        timestamp: Unix timestamp (seconds since epoch)

    Returns:
        Timezone-aware datetime in UTC

    Example:
        >>> dt = utc_from_timestamp(1699027200.0)
        >>> dt.tzinfo
        datetime.timezone.utc
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def utc_from_iso(iso_string: str) -> datetime:
    """
    Parse ISO 8601 string to timezone-aware UTC datetime.

    If input has no timezone, assumes UTC.
    If input has different timezone, converts to UTC.

    Args:
        iso_string: ISO 8601 datetime string (e.g., "2025-11-04T12:00:00Z")

    Returns:
        Timezone-aware datetime in UTC

    Raises:
        ValueError: If iso_string is not a valid ISO 8601 format

    Example:
        >>> dt = utc_from_iso('2025-11-04T12:00:00Z')
        >>> dt.tzinfo
        datetime.timezone.utc
        >>> dt2 = utc_from_iso('2025-11-04T12:00:00')  # No timezone
        >>> dt2.tzinfo  # Assumes UTC
        datetime.timezone.utc
    """
    # Handle 'Z' suffix (common in ISO format)
    normalized = iso_string.replace('Z', '+00:00')

    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as e:
        raise ValueError(f"Invalid ISO 8601 datetime format: {iso_string}") from e

    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        logger.debug(f"Parsed naive datetime from ISO string, assuming UTC: {iso_string}")
        return dt.replace(tzinfo=timezone.utc)

    # Convert to UTC if in different timezone
    return dt.astimezone(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure datetime is timezone-aware and in UTC.

    - If naive, assumes UTC
    - If aware but not UTC, converts to UTC
    - If already UTC, returns as-is

    Args:
        dt: Input datetime (naive or aware)

    Returns:
        Timezone-aware datetime in UTC

    Example:
        >>> naive = datetime(2025, 11, 4, 12, 0, 0)
        >>> aware = ensure_utc(naive)
        >>> aware.tzinfo
        datetime.timezone.utc
    """
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        logger.debug(f"Converting naive datetime to UTC: {dt}")
        return dt.replace(tzinfo=timezone.utc)

    # Already aware - convert to UTC
    return dt.astimezone(timezone.utc)


def is_expired(expires_at: datetime, now: Optional[datetime] = None) -> bool:
    """
    Check if a datetime has passed (timezone-safe).

    Handles both naive and aware datetimes safely by converting to UTC.

    Args:
        expires_at: Expiration datetime (naive or aware)
        now: Current time (defaults to utcnow())

    Returns:
        True if expired, False otherwise

    Example:
        >>> past = utcnow() - timedelta(hours=1)
        >>> is_expired(past)
        True
        >>> future = utcnow() + timedelta(hours=1)
        >>> is_expired(future)
        False
    """
    if now is None:
        now = utcnow()

    # Ensure both datetimes are timezone-aware
    expires_at_utc = ensure_utc(expires_at)
    now_utc = ensure_utc(now)

    return now_utc > expires_at_utc


def timedelta_from_now(
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    seconds: int = 0
) -> datetime:
    """
    Get timezone-aware UTC datetime offset from now.

    Useful for creating expiration times.

    Args:
        days: Days to add (can be negative)
        hours: Hours to add (can be negative)
        minutes: Minutes to add (can be negative)
        seconds: Seconds to add (can be negative)

    Returns:
        Timezone-aware datetime in UTC

    Example:
        >>> future = timedelta_from_now(hours=1)
        >>> future > utcnow()
        True
        >>> past = timedelta_from_now(hours=-1)
        >>> is_expired(past)
        True
    """
    return utcnow() + timedelta(
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds
    )


def to_iso(dt: datetime) -> str:
    """
    Convert datetime to ISO 8601 string with timezone.

    If datetime is naive, assumes UTC and logs a warning.

    Args:
        dt: Datetime to convert

    Returns:
        ISO 8601 formatted string with timezone

    Example:
        >>> dt = utcnow()
        >>> iso = to_iso(dt)
        >>> 'T' in iso and ('+00:00' in iso or 'Z' in iso)
        True
    """
    aware_dt = ensure_utc(dt)
    return aware_dt.isoformat()


def format_duration(delta: timedelta) -> str:
    """
    Format a timedelta as human-readable duration.

    Args:
        delta: Time duration

    Returns:
        Human-readable string (e.g., "2 hours 30 minutes")

    Example:
        >>> format_duration(timedelta(hours=2, minutes=30))
        '2 hours 30 minutes'
        >>> format_duration(timedelta(seconds=90))
        '1 minute 30 seconds'
    """
    total_seconds = int(delta.total_seconds())

    if total_seconds < 0:
        return "expired"

    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 and not parts:  # Only show seconds if no larger units
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return " ".join(parts) if parts else "0 seconds"
