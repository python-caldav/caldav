"""
CalendarSet operations - Sans-I/O business logic for CalendarSet objects.

This module contains pure functions for CalendarSet operations like
extracting calendar IDs and building calendar URLs. Both sync and async
clients use these same functions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple
from urllib.parse import quote

log = logging.getLogger("caldav")


@dataclass
class CalendarInfo:
    """Data for a calendar extracted from PROPFIND response."""

    url: str
    cal_id: Optional[str]
    name: Optional[str]
    resource_types: List[str]


def extract_calendar_id_from_url(url: str) -> Optional[str]:
    """
    Extract calendar ID from a calendar URL.

    Calendar URLs typically look like: /calendars/user/calendar-id/
    The calendar ID is the second-to-last path segment.

    Args:
        url: Calendar URL

    Returns:
        Calendar ID, or None if extraction fails
    """
    try:
        # Split and get second-to-last segment (last is empty due to trailing /)
        parts = str(url).rstrip("/").split("/")
        if len(parts) >= 1:
            cal_id = parts[-1]
            if cal_id:
                return cal_id
    except Exception:
        log.error(f"Calendar has unexpected url {url}")
    return None


def process_calendar_list(
    children_data: List[Tuple[str, List[str], Optional[str]]],
) -> List[CalendarInfo]:
    """
    Process children data into CalendarInfo objects.

    Args:
        children_data: List of (url, resource_types, display_name) tuples
                      from children() call

    Returns:
        List of CalendarInfo objects with extracted calendar IDs
    """
    calendars = []
    for c_url, c_types, c_name in children_data:
        cal_id = extract_calendar_id_from_url(c_url)
        if not cal_id:
            continue
        calendars.append(
            CalendarInfo(
                url=c_url,
                cal_id=cal_id,
                name=c_name,
                resource_types=c_types,
            )
        )
    return calendars


def resolve_calendar_url(
    cal_id: str,
    parent_url: str,
    client_base_url: str,
) -> str:
    """
    Resolve a calendar URL from a calendar ID.

    Handles different formats:
    - Full URLs (https://...)
    - Absolute paths (/calendars/...)
    - Relative IDs (just the calendar name)

    Args:
        cal_id: Calendar ID or URL
        parent_url: URL of the calendar set
        client_base_url: Base URL of the client

    Returns:
        Resolved calendar URL
    """
    # Normalize URLs for comparison
    client_canonical = str(client_base_url).rstrip("/")
    cal_id_str = str(cal_id)

    # Check if cal_id is already a full URL under the client base
    if cal_id_str.startswith(client_canonical):
        # It's a full URL, just join to handle any path adjustments
        return _join_url(client_base_url, cal_id)

    # Check if it's a full URL (http:// or https://)
    if cal_id_str.startswith("https://") or cal_id_str.startswith("http://"):
        # Join with parent URL
        return _join_url(parent_url, cal_id)

    # It's a relative ID - quote it and append trailing slash
    quoted_id = quote(cal_id)
    if not quoted_id.endswith("/"):
        quoted_id += "/"

    return _join_url(parent_url, quoted_id)


def _join_url(base: str, path: str) -> str:
    """
    Simple URL join - concatenates base and path.

    This is a placeholder that the actual URL class will handle.
    Returns a string representation for the operations layer.

    Args:
        base: Base URL
        path: Path to join

    Returns:
        Joined URL string
    """
    # Basic implementation - real code uses URL.join()
    base = str(base).rstrip("/")
    path = str(path).lstrip("/")
    return f"{base}/{path}"


def find_calendar_by_name(
    calendars: List[CalendarInfo],
    name: str,
) -> Optional[CalendarInfo]:
    """
    Find a calendar by display name.

    Args:
        calendars: List of CalendarInfo objects
        name: Display name to search for

    Returns:
        CalendarInfo if found, None otherwise
    """
    for cal in calendars:
        if cal.name == name:
            return cal
    return None


def find_calendar_by_id(
    calendars: List[CalendarInfo],
    cal_id: str,
) -> Optional[CalendarInfo]:
    """
    Find a calendar by ID.

    Args:
        calendars: List of CalendarInfo objects
        cal_id: Calendar ID to search for

    Returns:
        CalendarInfo if found, None otherwise
    """
    for cal in calendars:
        if cal.cal_id == cal_id:
            return cal
    return None
