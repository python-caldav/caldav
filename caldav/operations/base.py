"""
Base utilities for the operations layer.

This module provides foundational types and utilities used by all
operations modules. The operations layer contains pure functions
(Sans-I/O) that handle business logic without performing any network I/O.

Design principles:
- All functions are pure: same inputs always produce same outputs
- No network I/O - that's the client's responsibility
- Request specs describe WHAT to request, not HOW
- Response processors transform parsed data into domain-friendly formats
"""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence

from caldav.lib.url import URL


@dataclass(frozen=True)
class QuerySpec:
    """
    Base specification for a DAV query.

    This is an immutable description of what to request from the server.
    The client uses this to construct and execute the actual HTTP request.

    Attributes:
        url: The URL to query
        method: HTTP method (PROPFIND, REPORT, etc.)
        depth: DAV depth header (0, 1, or infinity)
        props: Properties to request
        body: Optional pre-built XML body (if complex)
    """

    url: str
    method: str = "PROPFIND"
    depth: int = 0
    props: tuple[str, ...] = ()
    body: Optional[bytes] = None

    def with_url(self, new_url: str) -> "QuerySpec":
        """Return a copy with a different URL."""
        return QuerySpec(
            url=new_url,
            method=self.method,
            depth=self.depth,
            props=self.props,
            body=self.body,
        )


@dataclass
class PropertyData:
    """
    Generic property data extracted from a DAV response.

    Used when we need to pass around arbitrary properties
    without knowing their specific structure.
    """

    href: str
    properties: Dict[str, Any] = field(default_factory=dict)
    status: int = 200


def normalize_href(href: str, base_url: Optional[str] = None) -> str:
    """
    Normalize an href to a consistent format.

    Handles relative URLs, double slashes, and other common issues.

    Args:
        href: The href from the server response
        base_url: Optional base URL to resolve relative hrefs against

    Returns:
        Normalized href string
    """
    if not href:
        return href

    # Handle double slashes
    while "//" in href and not href.startswith("http"):
        href = href.replace("//", "/")

    # Resolve relative URLs if base provided
    if base_url and not href.startswith("http"):
        try:
            base = URL.objectify(base_url)
            if base:
                return str(base.join(href))
        except Exception:
            pass

    return href


def extract_resource_type(properties: Dict[str, Any]) -> List[str]:
    """
    Extract resource types from properties dict.

    Args:
        properties: Dict of property tag -> value

    Returns:
        List of resource type tags (e.g., ['{DAV:}collection', '{urn:ietf:params:xml:ns:caldav}calendar'])
    """
    resource_type_key = "{DAV:}resourcetype"
    rt = properties.get(resource_type_key, [])

    if isinstance(rt, list):
        return rt
    elif rt is None:
        return []
    else:
        # Single value
        return [rt] if rt else []


def is_calendar_resource(properties: Dict[str, Any]) -> bool:
    """
    Check if properties indicate a calendar resource.

    Args:
        properties: Dict of property tag -> value

    Returns:
        True if this is a calendar collection
    """
    resource_types = extract_resource_type(properties)
    calendar_tag = "{urn:ietf:params:xml:ns:caldav}calendar"
    return calendar_tag in resource_types


def is_collection_resource(properties: Dict[str, Any]) -> bool:
    """
    Check if properties indicate a collection resource.

    Args:
        properties: Dict of property tag -> value

    Returns:
        True if this is a collection
    """
    resource_types = extract_resource_type(properties)
    collection_tag = "{DAV:}collection"
    return collection_tag in resource_types


def get_property_value(
    properties: Dict[str, Any],
    prop_name: str,
    default: Any = None,
) -> Any:
    """
    Get a property value, handling both namespaced and simple keys.

    Tries the full namespaced key first, then common namespace prefixes.

    Args:
        properties: Dict of property tag -> value
        prop_name: Property name (e.g., 'displayname' or '{DAV:}displayname')
        default: Default value if not found

    Returns:
        Property value or default
    """
    # Try exact key first
    if prop_name in properties:
        return properties[prop_name]

    # Try with common namespaces
    namespaces = [
        "{DAV:}",
        "{urn:ietf:params:xml:ns:caldav}",
        "{http://calendarserver.org/ns/}",
        "{http://apple.com/ns/ical/}",
    ]

    for ns in namespaces:
        full_key = f"{ns}{prop_name}"
        if full_key in properties:
            return properties[full_key]

    return default
