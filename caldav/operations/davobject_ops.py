"""
DAVObject operations - Sans-I/O business logic for DAV objects.

This module contains pure functions for DAVObject operations like
getting/setting properties, listing children, and deleting resources.
Both sync and async clients use these same functions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

from caldav.operations.base import (
    PropertyData,
    QuerySpec,
    extract_resource_type,
    is_calendar_resource,
    normalize_href,
)

log = logging.getLogger("caldav")


# Property tags used in operations
DAV_DISPLAYNAME = "{DAV:}displayname"
DAV_RESOURCETYPE = "{DAV:}resourcetype"
CALDAV_CALENDAR = "{urn:ietf:params:xml:ns:caldav}calendar"


@dataclass(frozen=True)
class ChildrenQuery:
    """Query specification for listing children."""

    url: str
    depth: int = 1
    props: Tuple[str, ...] = (DAV_DISPLAYNAME, DAV_RESOURCETYPE)


@dataclass
class ChildData:
    """Data for a child resource."""

    url: str
    resource_types: List[str]
    display_name: Optional[str]


@dataclass
class PropertiesResult:
    """Result of extracting properties for a specific object."""

    properties: Dict[str, Any]
    matched_path: str


def build_children_query(url: str) -> ChildrenQuery:
    """
    Build query for listing children of a collection.

    Args:
        url: URL of the parent collection

    Returns:
        ChildrenQuery specification
    """
    return ChildrenQuery(url=url)


def process_children_response(
    properties_by_href: Dict[str, Dict[str, Any]],
    parent_url: str,
    filter_type: Optional[str] = None,
    is_calendar_set: bool = False,
) -> List[ChildData]:
    """
    Process PROPFIND response into list of children.

    This is Sans-I/O - works on already-parsed response data.

    Args:
        properties_by_href: Dict mapping href -> properties dict
        parent_url: URL of the parent collection (to exclude from results)
        filter_type: Optional resource type to filter by (e.g., CALDAV_CALENDAR)
        is_calendar_set: True if parent is a CalendarSet (affects filtering logic)

    Returns:
        List of ChildData for matching children
    """
    children = []

    # Normalize parent URL for comparison
    parent_canonical = _canonical_path(parent_url)

    for path, props in properties_by_href.items():
        resource_types = props.get(DAV_RESOURCETYPE, [])
        if isinstance(resource_types, str):
            resource_types = [resource_types]
        elif resource_types is None:
            resource_types = []

        display_name = props.get(DAV_DISPLAYNAME)

        # Filter by type if specified
        if filter_type is not None and filter_type not in resource_types:
            continue

        # Build URL, quoting if it's a relative path
        url_obj_path = path
        if not path.startswith("http"):
            url_obj_path = quote(path)

        # Determine child's canonical path for comparison
        child_canonical = _canonical_path(path)

        # Skip the parent itself
        # Special case for CalendarSet filtering for calendars
        if is_calendar_set and filter_type == CALDAV_CALENDAR:
            # Include if it's a calendar (already filtered above)
            children.append(
                ChildData(
                    url=url_obj_path,
                    resource_types=resource_types,
                    display_name=display_name,
                )
            )
        elif parent_canonical != child_canonical:
            children.append(
                ChildData(
                    url=url_obj_path,
                    resource_types=resource_types,
                    display_name=display_name,
                )
            )

    return children


def _canonical_path(url: str) -> str:
    """Get canonical path for comparison, stripping trailing slashes."""
    # Extract path from URL
    if "://" in url:
        # Full URL - extract path
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path = parsed.path
    else:
        path = url

    # Strip trailing slash for comparison
    return path.rstrip("/")


def find_object_properties(
    properties_by_href: Dict[str, Dict[str, Any]],
    object_url: str,
    is_principal: bool = False,
) -> PropertiesResult:
    """
    Find properties for a specific object from a PROPFIND response.

    Handles various server quirks like trailing slash mismatches,
    iCloud path issues, and double slashes.

    Args:
        properties_by_href: Dict mapping href -> properties dict
        object_url: URL of the object we're looking for
        is_principal: True if object is a Principal (affects warning behavior)

    Returns:
        PropertiesResult with the found properties

    Raises:
        ValueError: If no matching properties found
    """
    path = unquote(object_url) if "://" not in object_url else unquote(_extract_path(object_url))

    # Try with and without trailing slash
    if path.endswith("/"):
        exchange_path = path[:-1]
    else:
        exchange_path = path + "/"

    # Try exact path match
    if path in properties_by_href:
        return PropertiesResult(properties=properties_by_href[path], matched_path=path)

    # Try with/without trailing slash
    if exchange_path in properties_by_href:
        if not is_principal:
            log.warning(
                f"The path {path} was not found in the properties, but {exchange_path} was. "
                "This may indicate a server bug or a trailing slash issue."
            )
        return PropertiesResult(properties=properties_by_href[exchange_path], matched_path=exchange_path)

    # Try full URL as key
    if object_url in properties_by_href:
        return PropertiesResult(properties=properties_by_href[object_url], matched_path=object_url)

    # iCloud workaround - /principal/ path
    if "/principal/" in properties_by_href and path.endswith("/principal/"):
        log.warning("Applying iCloud workaround for /principal/ path mismatch")
        return PropertiesResult(
            properties=properties_by_href["/principal/"], matched_path="/principal/"
        )

    # Double slash workaround
    if "//" in path:
        normalized = path.replace("//", "/")
        if normalized in properties_by_href:
            log.warning(f"Path contained double slashes: {path} -> {normalized}")
            return PropertiesResult(properties=properties_by_href[normalized], matched_path=normalized)

    # Last resort: if only one result, use it
    if len(properties_by_href) == 1:
        only_path = list(properties_by_href.keys())[0]
        log.warning(
            f"Possibly the server has a path handling problem, possibly the URL configured is wrong. "
            f"Path expected: {path}, path found: {only_path}. "
            "Continuing, probably everything will be fine"
        )
        return PropertiesResult(properties=properties_by_href[only_path], matched_path=only_path)

    # No match found
    raise ValueError(
        f"Could not find properties for {path}. "
        f"Available paths: {list(properties_by_href.keys())}"
    )


def _extract_path(url: str) -> str:
    """Extract path component from a URL."""
    if "://" not in url:
        return url
    from urllib.parse import urlparse

    return urlparse(url).path


def convert_protocol_results_to_properties(
    results: List[Any],  # List[PropfindResult]
    requested_props: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Convert protocol layer results to the {href: {tag: value}} format.

    Args:
        results: List of PropfindResult from protocol layer
        requested_props: Optional list of property tags that were requested
                        (used to initialize missing props to None)

    Returns:
        Dict mapping href -> properties dict
    """
    properties = {}
    for result in results:
        result_props = {}
        # Initialize requested props to None for backward compat
        if requested_props:
            for prop in requested_props:
                result_props[prop] = None
        # Overlay with actual values
        result_props.update(result.properties)
        properties[result.href] = result_props
    return properties


def validate_delete_response(status: int) -> None:
    """
    Validate DELETE response status.

    Args:
        status: HTTP status code

    Raises:
        ValueError: If status indicates failure
    """
    # 200 OK, 204 No Content, 404 Not Found (already deleted) are all acceptable
    if status not in (200, 204, 404):
        raise ValueError(f"Delete failed with status {status}")


def validate_proppatch_response(status: int) -> None:
    """
    Validate PROPPATCH response status.

    Args:
        status: HTTP status code

    Raises:
        ValueError: If status indicates failure
    """
    if status >= 400:
        raise ValueError(f"PROPPATCH failed with status {status}")
