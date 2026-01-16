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
    search_ops: Search operations (query building, filtering, strategy)
"""
from caldav.operations.base import extract_resource_type
from caldav.operations.base import get_property_value
from caldav.operations.base import is_calendar_resource
from caldav.operations.base import is_collection_resource
from caldav.operations.base import normalize_href
from caldav.operations.base import PropertyData
from caldav.operations.base import QuerySpec
from caldav.operations.calendar_ops import build_calendar_object_url
from caldav.operations.calendar_ops import CalendarObjectInfo
from caldav.operations.calendar_ops import detect_component_type
from caldav.operations.calendar_ops import detect_component_type_from_icalendar
from caldav.operations.calendar_ops import detect_component_type_from_string
from caldav.operations.calendar_ops import generate_fake_sync_token
from caldav.operations.calendar_ops import is_fake_sync_token
from caldav.operations.calendar_ops import normalize_result_url
from caldav.operations.calendar_ops import process_report_results
from caldav.operations.calendar_ops import should_skip_calendar_self_reference
from caldav.operations.calendarobject_ops import calculate_next_recurrence
from caldav.operations.calendarobject_ops import CalendarObjectData
from caldav.operations.calendarobject_ops import copy_component_with_new_uid
from caldav.operations.calendarobject_ops import extract_relations
from caldav.operations.calendarobject_ops import extract_uid_from_path
from caldav.operations.calendarobject_ops import find_id_and_path
from caldav.operations.calendarobject_ops import generate_uid
from caldav.operations.calendarobject_ops import generate_url
from caldav.operations.calendarobject_ops import get_due
from caldav.operations.calendarobject_ops import get_duration
from caldav.operations.calendarobject_ops import get_non_timezone_subcomponents
from caldav.operations.calendarobject_ops import get_primary_component
from caldav.operations.calendarobject_ops import get_reverse_reltype
from caldav.operations.calendarobject_ops import has_calendar_component
from caldav.operations.calendarobject_ops import is_calendar_data_loaded
from caldav.operations.calendarobject_ops import is_task_pending
from caldav.operations.calendarobject_ops import mark_task_completed
from caldav.operations.calendarobject_ops import mark_task_uncompleted
from caldav.operations.calendarobject_ops import reduce_rrule_count
from caldav.operations.calendarobject_ops import set_duration
from caldav.operations.calendarset_ops import CalendarInfo
from caldav.operations.calendarset_ops import extract_calendar_id_from_url
from caldav.operations.calendarset_ops import find_calendar_by_id
from caldav.operations.calendarset_ops import find_calendar_by_name
from caldav.operations.calendarset_ops import process_calendar_list
from caldav.operations.calendarset_ops import resolve_calendar_url
from caldav.operations.davobject_ops import build_children_query
from caldav.operations.davobject_ops import ChildData
from caldav.operations.davobject_ops import ChildrenQuery
from caldav.operations.davobject_ops import convert_protocol_results_to_properties
from caldav.operations.davobject_ops import find_object_properties
from caldav.operations.davobject_ops import process_children_response
from caldav.operations.davobject_ops import PropertiesResult
from caldav.operations.davobject_ops import validate_delete_response
from caldav.operations.davobject_ops import validate_proppatch_response
from caldav.operations.principal_ops import create_vcal_address
from caldav.operations.principal_ops import extract_calendar_user_addresses
from caldav.operations.principal_ops import PrincipalData
from caldav.operations.principal_ops import sanitize_calendar_home_set_url
from caldav.operations.principal_ops import should_update_client_base_url
from caldav.operations.principal_ops import sort_calendar_user_addresses
from caldav.operations.search_ops import build_search_xml_query
from caldav.operations.search_ops import collation_to_caldav
from caldav.operations.search_ops import determine_post_filter_needed
from caldav.operations.search_ops import filter_search_results
from caldav.operations.search_ops import get_explicit_contains_properties
from caldav.operations.search_ops import needs_pending_todo_multi_search
from caldav.operations.search_ops import SearchStrategy
from caldav.operations.search_ops import should_remove_category_filter
from caldav.operations.search_ops import should_remove_property_filters_for_combined

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
    # CalendarSet operations
    "CalendarInfo",
    "extract_calendar_id_from_url",
    "process_calendar_list",
    "resolve_calendar_url",
    "find_calendar_by_name",
    "find_calendar_by_id",
    # Calendar operations
    "CalendarObjectInfo",
    "detect_component_type",
    "detect_component_type_from_string",
    "detect_component_type_from_icalendar",
    "generate_fake_sync_token",
    "is_fake_sync_token",
    "normalize_result_url",
    "should_skip_calendar_self_reference",
    "process_report_results",
    "build_calendar_object_url",
    # Search operations
    "SearchStrategy",
    "build_search_xml_query",
    "filter_search_results",
    "collation_to_caldav",
    "determine_post_filter_needed",
    "should_remove_category_filter",
    "get_explicit_contains_properties",
    "should_remove_property_filters_for_combined",
    "needs_pending_todo_multi_search",
]
