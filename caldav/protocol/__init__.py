"""
CalDAV protocol layer — XML builders and (legacy) re-exports.

The xml_builders submodule provides functions to build CalDAV request XML.
Result dataclasses previously defined here have been moved to caldav.response.
"""

from caldav.response import (
    CalendarQueryResult,
    MultistatusResponse,
    PropfindResult,
    SyncCollectionResult,
)

__all__ = [
    "CalendarQueryResult",
    "MultistatusResponse",
    "PropfindResult",
    "SyncCollectionResult",
]
