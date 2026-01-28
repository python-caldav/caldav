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
    │  - _build_*() -> QuerySpec          │
    │  - _process_*() -> Result data      │
    │  - Pure functions, no I/O           │
    ├─────────────────────────────────────┤
    │  Protocol Layer (caldav.protocol)   │
    │  - XML building and parsing         │
    └─────────────────────────────────────┘

The functions in this layer are private (prefixed with _) and should be
imported directly from the submodules when needed. Only data types are
exported from this package.

Modules:
    base: Common utilities and base types
    davobject_ops: DAVObject operations (properties, children, delete)
    calendarobject_ops: CalendarObjectResource operations (load, save, ical manipulation)
    principal_ops: Principal operations (discovery, calendar home set)
    calendarset_ops: CalendarSet operations (list calendars, make calendar)
    calendar_ops: Calendar operations (search, multiget, sync)
    search_ops: Search operations (query building, filtering, strategy)
"""

from caldav.operations.base import PropertyData, QuerySpec
from caldav.operations.calendar_ops import CalendarObjectInfo
from caldav.operations.calendarobject_ops import CalendarObjectData
from caldav.operations.calendarset_ops import CalendarInfo
from caldav.operations.davobject_ops import ChildData, ChildrenQuery, PropertiesResult
from caldav.operations.principal_ops import PrincipalData
from caldav.operations.search_ops import SearchStrategy

__all__ = [
    # Base types
    "QuerySpec",
    "PropertyData",
    # DAVObject types
    "ChildrenQuery",
    "ChildData",
    "PropertiesResult",
    # CalendarObjectResource types
    "CalendarObjectData",
    # Principal types
    "PrincipalData",
    # CalendarSet types
    "CalendarInfo",
    # Calendar types
    "CalendarObjectInfo",
    # Search types
    "SearchStrategy",
]
