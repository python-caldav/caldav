"""
Principal operations - Sans-I/O business logic for Principal objects.

This module contains pure functions for Principal operations like
URL sanitization and vCalAddress creation. Both sync and async clients
use these same functions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import List
from typing import Optional
from urllib.parse import quote


@dataclass
class PrincipalData:
    """Data extracted from a principal."""

    url: Optional[str]
    display_name: Optional[str]
    calendar_home_set_url: Optional[str]
    calendar_user_addresses: List[str]


def sanitize_calendar_home_set_url(url: Optional[str]) -> Optional[str]:
    """
    Sanitize calendar home set URL, handling server quirks.

    OwnCloud returns URLs like /remote.php/dav/calendars/tobixen@e.email/
    where the @ should be quoted. Some servers return already-quoted URLs.

    Args:
        url: Calendar home set URL from server

    Returns:
        Sanitized URL with @ properly quoted (if not already)
    """
    if url is None:
        return None

    # Quote @ in URLs that aren't full URLs (owncloud quirk)
    # Don't double-quote if already quoted
    if "@" in url and "://" not in url and "%40" not in url:
        return quote(url)

    return url


def sort_calendar_user_addresses(addresses: List[Any]) -> List[Any]:
    """
    Sort calendar user addresses by preference.

    The 'preferred' attribute is possibly iCloud-specific but we honor
    it when present.

    Args:
        addresses: List of address elements (lxml elements with text and attributes)

    Returns:
        Sorted list (highest preference first)
    """
    return sorted(addresses, key=lambda x: -int(x.get("preferred", 0)))


def extract_calendar_user_addresses(addresses: List[Any]) -> List[Optional[str]]:
    """
    Extract calendar user address strings from XML elements.

    Args:
        addresses: List of DAV:href elements

    Returns:
        List of address strings (sorted by preference)
    """
    sorted_addresses = sort_calendar_user_addresses(addresses)
    return [x.text for x in sorted_addresses]


def create_vcal_address(
    display_name: Optional[str],
    address: str,
    calendar_user_type: Optional[str] = None,
) -> Any:
    """
    Create an icalendar vCalAddress object from principal properties.

    Args:
        display_name: The principal's display name (CN parameter)
        address: The primary calendar user address
        calendar_user_type: CalendarUserType (CUTYPE parameter)

    Returns:
        icalendar.vCalAddress object
    """
    from icalendar import vCalAddress, vText

    vcal_addr = vCalAddress(address)
    if display_name:
        vcal_addr.params["cn"] = vText(display_name)
    if calendar_user_type:
        vcal_addr.params["cutype"] = vText(calendar_user_type)

    return vcal_addr


def should_update_client_base_url(
    calendar_home_set_url: Optional[str],
    client_hostname: Optional[str],
) -> bool:
    """
    Check if client base URL should be updated for load-balanced systems.

    iCloud and others use load-balanced systems where each principal
    resides on one named host. If the calendar home set URL has a different
    hostname, we may need to update the client's base URL.

    Args:
        calendar_home_set_url: The sanitized calendar home set URL
        client_hostname: The current client hostname

    Returns:
        True if client URL should be updated
    """
    if calendar_home_set_url is None:
        return False

    # Check if it's a full URL with a different host
    if "://" in calendar_home_set_url:
        from urllib.parse import urlparse

        parsed = urlparse(calendar_home_set_url)
        if parsed.hostname and parsed.hostname != client_hostname:
            return True

    return False
