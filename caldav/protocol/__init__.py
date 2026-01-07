"""
Sans-I/O CalDAV protocol implementation.

This module provides protocol-level operations without any I/O.
It builds requests and parses responses as pure data transformations.

The protocol layer is organized into:
- types: Core data structures (DAVRequest, DAVResponse, result types)
- xml_builders: Pure functions to build XML request bodies
- xml_parsers: Pure functions to parse XML response bodies
- operations: High-level CalDAVProtocol class combining builders and parsers

Example usage:

    from caldav.protocol import CalDAVProtocol, DAVRequest, DAVResponse

    protocol = CalDAVProtocol(base_url="https://cal.example.com")

    # Build a request (no I/O)
    request = protocol.propfind_request(
        path="/calendars/user/",
        props=["displayname", "resourcetype"],
        depth=1
    )

    # Execute via your preferred I/O (sync, async, or mock)
    response = your_http_client.execute(request)

    # Parse response (no I/O)
    result = protocol.parse_propfind_response(response)
"""

from .types import (
    # Enums
    DAVMethod,
    # Request/Response
    DAVRequest,
    DAVResponse,
    # Result types
    CalendarInfo,
    CalendarQueryResult,
    MultiGetResult,
    MultistatusResponse,
    PrincipalInfo,
    PropfindResult,
    SyncCollectionResult,
)
from .xml_builders import (
    build_calendar_multiget_body,
    build_calendar_query_body,
    build_freebusy_query_body,
    build_mkcalendar_body,
    build_mkcol_body,
    build_propfind_body,
    build_proppatch_body,
    build_sync_collection_body,
)
from .xml_parsers import (
    parse_calendar_multiget_response,
    parse_calendar_query_response,
    parse_multistatus,
    parse_propfind_response,
    parse_sync_collection_response,
)
from .operations import CalDAVProtocol

__all__ = [
    # Enums
    "DAVMethod",
    # Request/Response
    "DAVRequest",
    "DAVResponse",
    # Result types
    "CalendarInfo",
    "CalendarQueryResult",
    "MultiGetResult",
    "MultistatusResponse",
    "PrincipalInfo",
    "PropfindResult",
    "SyncCollectionResult",
    # XML Builders
    "build_calendar_multiget_body",
    "build_calendar_query_body",
    "build_freebusy_query_body",
    "build_mkcalendar_body",
    "build_mkcol_body",
    "build_propfind_body",
    "build_proppatch_body",
    "build_sync_collection_body",
    # XML Parsers
    "parse_calendar_multiget_response",
    "parse_calendar_query_response",
    "parse_multistatus",
    "parse_propfind_response",
    "parse_sync_collection_response",
    # Protocol
    "CalDAVProtocol",
]
