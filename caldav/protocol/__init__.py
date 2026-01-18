"""
Sans-I/O CalDAV protocol implementation.

This module provides protocol-level operations without any I/O.
It builds requests and parses responses as pure data transformations.

The protocol layer is organized into:
- types: Core data structures (DAVRequest, DAVResponse, result types)
- xml_builders: Pure functions to build XML request bodies
- xml_parsers: Pure functions to parse XML response bodies

Both DAVClient (sync) and AsyncDAVClient (async) use these shared
functions for XML building and parsing, ensuring consistent behavior.

Example usage:

    from caldav.protocol import build_propfind_body, parse_propfind_response

    # Build XML body (no I/O)
    body = build_propfind_body(["displayname", "resourcetype"])

    # ... send request via your HTTP client ...

    # Parse response (no I/O)
    results = parse_propfind_response(response_body)
"""
from .types import CalendarInfo
from .types import CalendarQueryResult
from .types import DAVMethod
from .types import DAVRequest
from .types import DAVResponse
from .types import MultiGetResult
from .types import MultistatusResponse
from .types import PrincipalInfo
from .types import PropfindResult
from .types import SyncCollectionResult
from .xml_builders import build_calendar_multiget_body
from .xml_builders import build_calendar_query_body
from .xml_builders import build_freebusy_query_body
from .xml_builders import build_mkcalendar_body
from .xml_builders import build_mkcol_body
from .xml_builders import build_propfind_body
from .xml_builders import build_proppatch_body
from .xml_builders import build_sync_collection_body
from .xml_parsers import parse_calendar_multiget_response
from .xml_parsers import parse_calendar_query_response
from .xml_parsers import parse_multistatus
from .xml_parsers import parse_propfind_response
from .xml_parsers import parse_sync_collection_response

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
]
