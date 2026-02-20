"""
Shared datetime and duration utilities for JSCalendar ↔ iCalendar conversion.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


def _timedelta_to_duration(td: timedelta) -> str:
    """Convert a timedelta to an ISO 8601 duration string.

    Examples:
        timedelta(hours=1, minutes=30) → "PT1H30M"
        timedelta(days=1, hours=2)     → "P1DT2H"
        timedelta(0)                   → "P0D"
        timedelta(seconds=-900)        → "-PT15M"

    Args:
        td: The duration to convert.

    Returns:
        ISO 8601 duration string, always positive or negative prefix,
        never fractional components.
    """
    total_seconds = int(td.total_seconds())
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)

    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    day_part = f"{days}D" if days else ""
    time_parts = []
    if hours:
        time_parts.append(f"{hours}H")
    if minutes:
        time_parts.append(f"{minutes}M")
    if seconds:
        time_parts.append(f"{seconds}S")

    time_part = ("T" + "".join(time_parts)) if time_parts else ""

    body = day_part + time_part or "0D"
    return f"{sign}P{body}"


def _duration_to_timedelta(duration_str: str) -> timedelta:
    """Parse an ISO 8601 duration string into a timedelta.

    Handles the subset used in JSCalendar: P[nW][nD][T[nH][nM][nS]].
    Does not handle months or years (JSCalendar uses recurrenceRules for those).

    Examples:
        "PT1H30M"  → timedelta(hours=1, minutes=30)
        "P1DT2H"   → timedelta(days=1, hours=2)
        "P0D"      → timedelta(0)
        "-PT15M"   → timedelta(seconds=-900)

    Args:
        duration_str: ISO 8601 duration string.

    Returns:
        Equivalent timedelta.

    Raises:
        ValueError: If the string cannot be parsed.
    """
    s = duration_str.strip()
    sign = 1
    if s.startswith("-"):
        sign = -1
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]

    if not s.startswith("P"):
        raise ValueError(f"Invalid duration string: {duration_str!r}")
    s = s[1:]

    weeks = days = hours = minutes = seconds = 0

    if "T" in s:
        date_part, time_part = s.split("T", 1)
    else:
        date_part, time_part = s, ""

    if date_part:
        if "W" in date_part:
            w, date_part = date_part.split("W", 1)
            weeks = int(w)
        if "D" in date_part:
            d, _ = date_part.split("D", 1)
            days = int(d)

    if time_part:
        remaining = time_part
        if "H" in remaining:
            h, remaining = remaining.split("H", 1)
            hours = int(h)
        if "M" in remaining:
            m, remaining = remaining.split("M", 1)
            minutes = int(m)
        if "S" in remaining:
            sec_str, _ = remaining.split("S", 1)
            seconds = int(float(sec_str))  # truncate fractional seconds to whole seconds

    td = timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds)
    return sign * td


def _format_local_dt(dt: datetime | date) -> str:
    """Format a datetime or date as a JSCalendar LocalDateTime or UTCDateTime string.

    JSCalendar uses:
      - LocalDateTime: "2024-03-15T09:00:00"    (no TZ suffix)
      - UTCDateTime:   "2024-03-15T09:00:00Z"   (uppercase Z)

    For date objects (all-day), uses T00:00:00 suffix.

    Args:
        dt: A datetime (with or without tzinfo) or a date.

    Returns:
        Formatted string suitable for use as a JSCalendar override key or datetime value.
    """
    if isinstance(dt, datetime):
        if dt.tzinfo is not None and dt.utcoffset() == timedelta(0):
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    return f"{dt.isoformat()}T00:00:00"
