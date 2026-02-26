"""
Pure functions for parsing CalDAV XML responses.

All functions in this module are pure - they take XML bytes in and return
structured data out, with no side effects or I/O.
"""

import logging
from typing import Any
from urllib.parse import unquote

from lxml import etree
from lxml.etree import _Element

from caldav.elements import cdav, dav
from caldav.lib import error
from caldav.lib.url import URL

from .types import CalendarQueryResult, MultistatusResponse, PropfindResult, SyncCollectionResult

log = logging.getLogger(__name__)


def _parse_multistatus(
    body: bytes,
    huge_tree: bool = False,
) -> MultistatusResponse:
    """
    Parse a 207 Multi-Status response body.

    Args:
        body: Raw XML response bytes
        huge_tree: Allow parsing very large XML documents

    Returns:
        Structured MultistatusResponse with parsed results

    Raises:
        XMLSyntaxError: If body is not valid XML
        ResponseError: If response indicates an error
    """
    parser = etree.XMLParser(huge_tree=huge_tree)
    tree = etree.fromstring(body, parser)

    responses: list[PropfindResult] = []
    sync_token: str | None = None

    # Strip to multistatus content
    response_elements = _strip_to_multistatus(tree)

    for elem in response_elements:
        if elem.tag == dav.SyncToken.tag:
            sync_token = elem.text
            continue

        if elem.tag != dav.Response.tag:
            continue

        href, propstats, status = _parse_response_element(elem)
        properties = _extract_properties(propstats)
        status_code = _status_to_code(status) if status else 200

        responses.append(
            PropfindResult(
                href=href,
                properties=properties,
                status=status_code,
            )
        )

    return MultistatusResponse(responses=responses, sync_token=sync_token)


def _parse_propfind_response(
    body: bytes,
    status_code: int = 207,
    huge_tree: bool = False,
) -> list[PropfindResult]:
    """
    Parse a PROPFIND response.

    Args:
        body: Raw XML response bytes
        status_code: HTTP status code of the response
        huge_tree: Allow parsing very large XML documents

    Returns:
        List of PropfindResult with properties for each resource
    """
    if status_code == 404:
        return []

    if status_code not in (200, 207):
        raise error.ResponseError(f"PROPFIND failed with status {status_code}")

    if not body:
        return []

    result = _parse_multistatus(body, huge_tree=huge_tree)
    return result.responses


def _parse_calendar_query_response(
    body: bytes,
    status_code: int = 207,
    huge_tree: bool = False,
) -> list[CalendarQueryResult]:
    """
    Parse a calendar-query REPORT response.

    Args:
        body: Raw XML response bytes
        status_code: HTTP status code of the response
        huge_tree: Allow parsing very large XML documents

    Returns:
        List of CalendarQueryResult with calendar data
    """
    if status_code not in (200, 207):
        raise error.ResponseError(f"REPORT failed with status {status_code}")

    if not body:
        return []

    parser = etree.XMLParser(huge_tree=huge_tree)
    tree = etree.fromstring(body, parser)

    results: list[CalendarQueryResult] = []
    response_elements = _strip_to_multistatus(tree)

    for elem in response_elements:
        if elem.tag != dav.Response.tag:
            continue

        href, propstats, status = _parse_response_element(elem)
        status_code_elem = _status_to_code(status) if status else 200

        calendar_data: str | None = None
        etag: str | None = None

        # Extract properties from propstats
        for propstat in propstats:
            prop = propstat.find(dav.Prop.tag)
            if prop is None:
                continue

            for child in prop:
                if child.tag == cdav.CalendarData.tag:
                    calendar_data = child.text
                elif child.tag == dav.GetEtag.tag:
                    etag = child.text

        results.append(
            CalendarQueryResult(
                href=href,
                etag=etag,
                calendar_data=calendar_data,
                status=status_code_elem,
            )
        )

    return results


def _parse_sync_collection_response(
    body: bytes,
    status_code: int = 207,
    huge_tree: bool = False,
) -> SyncCollectionResult:
    """
    Parse a sync-collection REPORT response.

    Args:
        body: Raw XML response bytes
        status_code: HTTP status code of the response
        huge_tree: Allow parsing very large XML documents

    Returns:
        SyncCollectionResult with changed items, deleted hrefs, and new sync token
    """
    if status_code not in (200, 207):
        raise error.ResponseError(f"sync-collection failed with status {status_code}")

    if not body:
        return SyncCollectionResult()

    parser = etree.XMLParser(huge_tree=huge_tree)
    tree = etree.fromstring(body, parser)

    changed: list[CalendarQueryResult] = []
    deleted: list[str] = []
    sync_token: str | None = None

    response_elements = _strip_to_multistatus(tree)

    for elem in response_elements:
        if elem.tag == dav.SyncToken.tag:
            sync_token = elem.text
            continue

        if elem.tag != dav.Response.tag:
            continue

        href, propstats, status = _parse_response_element(elem)
        status_code_elem = _status_to_code(status) if status else 200

        # 404 means deleted
        if status_code_elem == 404:
            deleted.append(href)
            continue

        calendar_data: str | None = None
        etag: str | None = None

        for propstat in propstats:
            prop = propstat.find(dav.Prop.tag)
            if prop is None:
                continue

            for child in prop:
                if child.tag == cdav.CalendarData.tag:
                    calendar_data = child.text
                elif child.tag == dav.GetEtag.tag:
                    etag = child.text

        changed.append(
            CalendarQueryResult(
                href=href,
                etag=etag,
                calendar_data=calendar_data,
                status=status_code_elem,
            )
        )

    return SyncCollectionResult(
        changed=changed,
        deleted=deleted,
        sync_token=sync_token,
    )


def _parse_calendar_multiget_response(
    body: bytes,
    status_code: int = 207,
    huge_tree: bool = False,
) -> list[CalendarQueryResult]:
    """
    Parse a calendar-multiget REPORT response.

    This is the same format as calendar-query, so we delegate to that parser.

    Args:
        body: Raw XML response bytes
        status_code: HTTP status code of the response
        huge_tree: Allow parsing very large XML documents

    Returns:
        List of CalendarQueryResult with calendar data
    """
    return _parse_calendar_query_response(body, status_code, huge_tree)


# Helper functions


def _strip_to_multistatus(tree: _Element) -> _Element | list[_Element]:
    """
    Strip outer elements to get to the multistatus content.

    The general format is:
        <xml><multistatus>
            <response>...</response>
            <response>...</response>
        </multistatus></xml>

    But sometimes multistatus and/or xml element is missing.
    Returns the element(s) containing responses.
    """
    if tree.tag == "xml" and len(tree) > 0 and tree[0].tag == dav.MultiStatus.tag:
        return tree[0]
    if tree.tag == dav.MultiStatus.tag:
        return tree
    return [tree]


def _parse_response_element(
    response: _Element,
) -> tuple[str, list[_Element], str | None]:
    """
    Parse a single DAV:response element.

    Returns:
        Tuple of (href, propstat elements list, status string)
    """
    status: str | None = None
    href: str | None = None
    propstats: list[_Element] = []

    for elem in response:
        if elem.tag == dav.Status.tag:
            status = elem.text
            _validate_status(status)
        elif elem.tag == dav.Href.tag:
            # Fix for double-encoded URLs (e.g., Confluence)
            text = elem.text or ""
            if "%2540" in text:
                text = text.replace("%2540", "%40")
            href = unquote(text)
            # Convert absolute URLs to paths
            if ":" in href:
                href = unquote(URL(href).path)
        elif elem.tag == dav.PropStat.tag:
            propstats.append(elem)

    return (href or "", propstats, status)


def _extract_properties(propstats: list[_Element]) -> dict[str, Any]:
    """
    Extract properties from propstat elements into a dict.

    Args:
        propstats: List of propstat elements

    Returns:
        Dict mapping property tag to value (text or element)
    """
    properties: dict[str, Any] = {}

    for propstat in propstats:
        # Check status - skip 404 properties
        status_elem = propstat.find(dav.Status.tag)
        if status_elem is not None and status_elem.text:
            if " 404 " in status_elem.text:
                continue

        # Find prop element
        prop = propstat.find(dav.Prop.tag)
        if prop is None:
            continue

        # Extract each property
        for child in prop:
            tag = child.tag
            # Get simple text value or store element for complex values
            if len(child) == 0:
                properties[tag] = child.text
            else:
                # For complex elements, store the element itself
                # or extract nested text values
                properties[tag] = _element_to_value(child)

    return properties


def _element_to_value(elem: _Element) -> Any:
    """
    Convert an XML element to a Python value.

    For simple elements, returns text content.
    For complex elements with children, returns dict or list.
    Handles special CalDAV elements like supported-calendar-component-set.
    """
    if len(elem) == 0:
        return elem.text

    # Special handling for known complex properties
    tag = elem.tag

    # supported-calendar-component-set: extract comp names
    if tag == cdav.SupportedCalendarComponentSet.tag:
        return [child.get("name") for child in elem if child.get("name")]

    # calendar-user-address-set: extract href texts
    if tag == cdav.CalendarUserAddressSet.tag:
        return [child.text for child in elem if child.tag == dav.Href.tag and child.text]

    # calendar-home-set: extract href text (usually single)
    if tag == cdav.CalendarHomeSet.tag:
        hrefs = [child.text for child in elem if child.tag == dav.Href.tag and child.text]
        return hrefs[0] if len(hrefs) == 1 else hrefs

    # resourcetype: extract child tag names (e.g., collection, calendar)
    if tag == dav.ResourceType.tag:
        return [child.tag for child in elem]

    # current-user-principal: extract href
    if tag == dav.CurrentUserPrincipal.tag:
        for child in elem:
            if child.tag == dav.Href.tag and child.text:
                return child.text
        return None

    # Generic handling for elements with children
    children_texts = []
    for child in elem:
        if child.text:
            children_texts.append(child.text)
        elif child.get("name"):
            # Elements with name attribute (like comp)
            children_texts.append(child.get("name"))
        elif len(child) == 0:
            # Empty element - use tag name
            children_texts.append(child.tag)

    if len(children_texts) == 1:
        return children_texts[0]
    elif children_texts:
        return children_texts

    # Fallback: return the element for further processing
    return elem


def _validate_status(status: str | None) -> None:
    """
    Validate a status string like "HTTP/1.1 404 Not Found".

    200, 201, 207, and 404 are considered acceptable statuses.

    Args:
        status: Status string from response

    Raises:
        ResponseError: If status indicates an error
    """
    if status is None:
        return

    acceptable = (" 200 ", " 201 ", " 207 ", " 404 ")
    if not any(code in status for code in acceptable):
        raise error.ResponseError(status)


def _status_to_code(status: str | None) -> int:
    """
    Extract status code from status string like "HTTP/1.1 200 OK".

    Args:
        status: Status string

    Returns:
        Integer status code (defaults to 200 if parsing fails)
    """
    if not status:
        return 200

    parts = status.split()
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            pass

    return 200
