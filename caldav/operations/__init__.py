"""
Operations Layer - Sans-I/O Business Logic for CalDAV.

This package contains pure functions that implement CalDAV business logic
without performing any network I/O. Both sync (DAVClient) and async
(AsyncDAVClient) clients use these same functions.

Architecture:
    ┌─────────────────────────────────────┐
    │  DAVClient / AsyncDAVClient         │
    │  (handles I/O)                      │
    ├─────────────────────────────────────┤
    │  Operations Layer (this package)    │
    │  - build_*() -> QuerySpec           │
    │  - process_*() -> Result data       │
    │  - Pure functions, no I/O           │
    ├─────────────────────────────────────┤
    │  Protocol Layer (caldav.protocol)   │
    │  - XML building and parsing         │
    └─────────────────────────────────────┘

Usage:
    from caldav.operations import calendar_ops

    # Build query (Sans-I/O)
    query = calendar_ops.build_calendars_query(calendar_home_url)

    # Client executes I/O
    response = client.propfind(query.url, props=query.props, depth=query.depth)

    # Process response (Sans-I/O)
    calendars = calendar_ops.process_calendars_response(response.results)

Modules:
    base: Common utilities and base types
    davobject_ops: DAVObject operations (properties, children, delete)
    calendarobject_ops: CalendarObjectResource operations (load, save, ical manipulation)
    principal_ops: Principal operations (discovery, calendar home set)
    calendarset_ops: CalendarSet operations (list calendars, make calendar)
    calendar_ops: Calendar operations (search, multiget, sync)
"""

from caldav.operations.base import (
    PropertyData,
    QuerySpec,
    extract_resource_type,
    get_property_value,
    is_calendar_resource,
    is_collection_resource,
    normalize_href,
)
from caldav.operations.davobject_ops import (
    ChildData,
    ChildrenQuery,
    PropertiesResult,
    build_children_query,
    convert_protocol_results_to_properties,
    find_object_properties,
    process_children_response,
    validate_delete_response,
    validate_proppatch_response,
)

__all__ = [
    # Base types
    "QuerySpec",
    "PropertyData",
    # Utility functions
    "normalize_href",
    "extract_resource_type",
    "is_calendar_resource",
    "is_collection_resource",
    "get_property_value",
    # DAVObject operations
    "ChildrenQuery",
    "ChildData",
    "PropertiesResult",
    "build_children_query",
    "process_children_response",
    "find_object_properties",
    "convert_protocol_results_to_properties",
    "validate_delete_response",
    "validate_proppatch_response",
]
