"""
Sans-I/O CalDAV protocol implementation.

This module provides protocol-level operations without any I/O.
It builds requests and parses responses as pure data transformations.

The protocol layer is organized into:
- types: Core data structures (DAVRequest, DAVResponse, result types)
- xml_builders: Internal functions to build XML request bodies
- xml_parsers: Internal functions to parse XML response bodies

Both DAVClient (sync) and AsyncDAVClient (async) use these shared
functions for XML building and parsing, ensuring consistent behavior.

Note: The xml_builders and xml_parsers functions are internal implementation
details and should not be used directly. Use the client methods instead.
"""

from .types import (
    CalendarQueryResult,
    DAVMethod,
    DAVRequest,
    DAVResponse,
    MultiGetResult,
    MultistatusResponse,
    PrincipalInfo,
    PropfindResult,
    SyncCollectionResult,
)

__all__ = [
    # Enums
    "DAVMethod",
    # Request/Response
    "DAVRequest",
    "DAVResponse",
    # Result types
    "CalendarQueryResult",
    "MultiGetResult",
    "MultistatusResponse",
    "PrincipalInfo",
    "PropfindResult",
    "SyncCollectionResult",
]
