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
from caldav.operations.calendarobject_ops import (
    CalendarObjectData,
    calculate_next_recurrence,
    copy_component_with_new_uid,
    extract_relations,
    extract_uid_from_path,
    find_id_and_path,
    generate_uid,
    generate_url,
    get_due,
    get_duration,
    get_non_timezone_subcomponents,
    get_primary_component,
    get_reverse_reltype,
    has_calendar_component,
    is_calendar_data_loaded,
    is_task_pending,
    mark_task_completed,
    mark_task_uncompleted,
    reduce_rrule_count,
    set_duration,
)
from caldav.operations.principal_ops import (
    PrincipalData,
    create_vcal_address,
    extract_calendar_user_addresses,
    sanitize_calendar_home_set_url,
    should_update_client_base_url,
    sort_calendar_user_addresses,
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
    # CalendarObjectResource operations
    "CalendarObjectData",
    "generate_uid",
    "generate_url",
    "extract_uid_from_path",
    "find_id_and_path",
    "get_duration",
    "get_due",
    "set_duration",
    "is_task_pending",
    "mark_task_completed",
    "mark_task_uncompleted",
    "calculate_next_recurrence",
    "reduce_rrule_count",
    "is_calendar_data_loaded",
    "has_calendar_component",
    "get_non_timezone_subcomponents",
    "get_primary_component",
    "copy_component_with_new_uid",
    "get_reverse_reltype",
    "extract_relations",
    # Principal operations
    "PrincipalData",
    "sanitize_calendar_home_set_url",
    "sort_calendar_user_addresses",
    "extract_calendar_user_addresses",
    "create_vcal_address",
    "should_update_client_base_url",
]
