"""
Search operations - Sans-I/O business logic for calendar search.

This module contains pure functions that implement search logic
without performing any network I/O. Both sync (CalDAVSearcher.search)
and async (CalDAVSearcher.async_search) use these same functions.

Key functions:
- build_search_xml_query(): Build CalDAV REPORT XML query
- filter_search_results(): Client-side filtering of search results
- determine_search_strategy(): Analyze server features and return search plan
- collation_to_caldav(): Map collation enum to CalDAV identifier
"""
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple
from typing import TYPE_CHECKING

from icalendar import Timezone
from icalendar_searcher.collation import Collation

from caldav.elements import cdav
from caldav.elements import dav
from caldav.lib import error

if TYPE_CHECKING:
    from caldav.calendarobjectresource import CalendarObjectResource
    from caldav.calendarobjectresource import Event, Todo, Journal
    from caldav.compatibility_hints import FeatureSet
    from icalendar_searcher import Searcher


def collation_to_caldav(collation: Collation, case_sensitive: bool = True) -> str:
    """Map icalendar-searcher Collation enum to CalDAV collation identifier.

    CalDAV supports collation identifiers from RFC 4790. The default is "i;ascii-casemap"
    and servers must support at least "i;ascii-casemap" and "i;octet".

    :param collation: icalendar-searcher Collation enum value
    :param case_sensitive: Whether the collation should be case-sensitive
    :return: CalDAV collation identifier string
    """
    if collation == Collation.SIMPLE:
        # SIMPLE collation maps to CalDAV's basic collations
        if case_sensitive:
            return "i;octet"
        else:
            return "i;ascii-casemap"
    elif collation == Collation.UNICODE:
        # Unicode Collation Algorithm - not all servers support this
        # Note: "i;unicode-casemap" is case-insensitive by definition
        # For case-sensitive Unicode, we fall back to i;octet (binary)
        if case_sensitive:
            return "i;octet"
        else:
            return "i;unicode-casemap"
    elif collation == Collation.LOCALE:
        # Locale-specific collation - not widely supported in CalDAV
        # Fallback to i;ascii-casemap as most servers don't support locale-specific
        return "i;ascii-casemap"
    else:
        # Default to binary/octet for unknown collations
        return "i;octet"


@dataclass
class SearchStrategy:
    """Encapsulates the search strategy decisions based on server capabilities.

    This dataclass holds all the decisions about how to execute a search,
    allowing the same logic to be shared between sync and async implementations.
    """

    # Whether to apply client-side post-filtering
    post_filter: Optional[bool] = None

    # Hack mode for server compatibility
    hacks: Optional[str] = None

    # Whether to split expanded recurrences into separate objects
    split_expanded: bool = True

    # Properties to remove from server query (for client-side filtering)
    remove_properties: Set[str] = field(default_factory=set)

    # Whether category filters should be removed (server doesn't support them)
    remove_category_filter: bool = False

    # Whether we need to do multiple searches for pending todos
    pending_todo_multi_search: bool = False

    # Whether to retry with individual component types
    retry_with_comptypes: bool = False


def determine_post_filter_needed(
    searcher: "Searcher",
    features: "FeatureSet",
    comp_type_support: Optional[str],
    current_hacks: Optional[str],
    current_post_filter: Optional[bool],
) -> Tuple[Optional[bool], Optional[str]]:
    """Determine if post-filtering is needed based on searcher state and server features.

    Returns (post_filter, hacks) tuple with potentially updated values.

    This is a Sans-I/O function - it only examines data and makes decisions.
    """
    post_filter = current_post_filter
    hacks = current_hacks

    # Handle servers with broken component-type filtering (e.g., Bedework)
    if (
        (
            searcher.comp_class
            or getattr(searcher, "todo", False)
            or getattr(searcher, "event", False)
            or getattr(searcher, "journal", False)
        )
        and comp_type_support == "broken"
        and not hacks
        and post_filter is not False
    ):
        hacks = "no_comp_filter"
        post_filter = True

    # Setting default value for post_filter based on various conditions
    if post_filter is None and (
        (getattr(searcher, "todo", False) and not searcher.include_completed)
        or searcher.expand
        or "categories" in searcher._property_filters
        or "category" in searcher._property_filters
        or not features.is_supported("search.text.case-sensitive")
        or not features.is_supported("search.time-range.accurate")
    ):
        post_filter = True

    return post_filter, hacks


def should_remove_category_filter(
    searcher: "Searcher",
    features: "FeatureSet",
    post_filter: Optional[bool],
) -> bool:
    """Check if category filters should be removed from server query.

    Returns True if categories/category are in property filters but server
    doesn't support category search properly.
    """
    return (
        not features.is_supported("search.text.category")
        and (
            "categories" in searcher._property_filters
            or "category" in searcher._property_filters
        )
        and post_filter is not False
    )


def get_explicit_contains_properties(
    searcher: "Searcher",
    features: "FeatureSet",
    post_filter: Optional[bool],
) -> List[str]:
    """Get list of properties with explicit 'contains' operator that server doesn't support.

    These properties should be removed from server query and applied client-side.
    """
    if features.is_supported("search.text.substring") or post_filter is False:
        return []

    explicit_operators = getattr(searcher, "_explicit_operators", set())
    return [
        prop
        for prop in searcher._property_operator
        if prop in explicit_operators
        and searcher._property_operator[prop] == "contains"
    ]


def should_remove_property_filters_for_combined(
    searcher: "Searcher",
    features: "FeatureSet",
) -> bool:
    """Check if property filters should be removed due to combined search issues.

    Some servers don't handle combined time-range + property filters properly.
    """
    if features.is_supported("search.combined-is-logical-and"):
        return False
    return bool((searcher.start or searcher.end) and searcher._property_filters)


def needs_pending_todo_multi_search(
    searcher: "Searcher",
    features: "FeatureSet",
) -> bool:
    """Check if we need multiple searches for pending todos.

    Returns True if searching for pending todos and server supports the
    necessary features for multi-search approach.
    """
    if not (getattr(searcher, "todo", False) and searcher.include_completed is False):
        return False

    return (
        features.is_supported("search.text")
        and features.is_supported("search.combined-is-logical-and")
        and (
            not features.is_supported("search.recurrences.includes-implicit.todo")
            or features.is_supported(
                "search.recurrences.includes-implicit.todo.pending"
            )
        )
    )


def filter_search_results(
    objects: List["CalendarObjectResource"],
    searcher: "Searcher",
    post_filter: Optional[bool] = None,
    split_expanded: bool = True,
    server_expand: bool = False,
) -> List["CalendarObjectResource"]:
    """Apply client-side filtering and handle recurrence expansion/splitting.

    This is a Sans-I/O function - it only processes data without network I/O.

    :param objects: List of Event/Todo/Journal objects to filter
    :param searcher: The CalDAVSearcher with filter criteria
    :param post_filter: Whether to apply the searcher's filter logic.
        - True: Always apply filters (check_component)
        - False: Never apply filters, only handle splitting
        - None: Use default behavior (depends on searcher.expand and other flags)
    :param split_expanded: Whether to split recurrence sets into multiple
        separate CalendarObjectResource objects. If False, a recurrence set
        will be contained in a single object with multiple subcomponents.
    :param server_expand: Indicates that the server was supposed to expand
        recurrences. If True and split_expanded is True, splitting will be
        performed even without searcher.expand being set.
    :return: Filtered and/or split list of CalendarObjectResource objects
    """
    if not (post_filter or searcher.expand or (split_expanded and server_expand)):
        return objects

    result = []
    for o in objects:
        if searcher.expand or post_filter:
            filtered = searcher.check_component(o, expand_only=not post_filter)
            if not filtered:
                continue
        else:
            filtered = [
                x
                for x in o.icalendar_instance.subcomponents
                if not isinstance(x, Timezone)
            ]

        i = o.icalendar_instance
        tz_ = [x for x in i.subcomponents if isinstance(x, Timezone)]
        i.subcomponents = tz_

        for comp in filtered:
            if isinstance(comp, Timezone):
                continue
            if split_expanded:
                new_obj = o.copy(keep_uid=True)
                new_i = new_obj.icalendar_instance
                new_i.subcomponents = []
                for tz in tz_:
                    new_i.add_component(tz)
                result.append(new_obj)
            else:
                new_i = i
            new_i.add_component(comp)

        if not split_expanded:
            result.append(o)

    return result


def build_search_xml_query(
    searcher: "Searcher",
    server_expand: bool = False,
    props: Optional[List[Any]] = None,
    filters: Any = None,
    _hacks: Optional[str] = None,
) -> Tuple[Any, Optional[type]]:
    """Build a CalDAV calendar-query XML request.

    This is a Sans-I/O function - it only builds XML without network I/O.

    :param searcher: CalDAVSearcher instance with search parameters
    :param server_expand: Ask server to expand recurrences
    :param props: Additional CalDAV properties to request
    :param filters: Pre-built filter elements (or None to build from searcher)
    :param _hacks: Compatibility hack mode
    :return: Tuple of (xml_element, comp_class)
    """
    # Import here to avoid circular imports at module level
    from caldav.calendarobjectresource import Event, Todo, Journal

    # With dual-mode classes, Async* are now aliases to the sync classes
    # Keep the aliases for backward compatibility in type checks
    AsyncEvent = Event
    AsyncTodo = Todo
    AsyncJournal = Journal

    # Build the request
    data = cdav.CalendarData()
    if server_expand:
        if not searcher.start or not searcher.end:
            raise error.ReportError("can't expand without a date range")
        data += cdav.Expand(searcher.start, searcher.end)

    if props is None:
        props_ = [data]
    else:
        props_ = [data] + list(props)
    prop = dav.Prop() + props_
    vcalendar = cdav.CompFilter("VCALENDAR")

    comp_filter = None
    comp_class = searcher.comp_class

    if filters:
        # Deep copy to avoid mutating the original
        filters = deepcopy(filters)
        if hasattr(filters, "tag") and filters.tag == cdav.CompFilter.tag:
            comp_filter = filters
            filters = []
    else:
        filters = []

    # Build status filters for pending todos
    vNotCompleted = cdav.TextMatch("COMPLETED", negate=True)
    vNotCancelled = cdav.TextMatch("CANCELLED", negate=True)
    vNeedsAction = cdav.TextMatch("NEEDS-ACTION")
    vStatusNotCompleted = cdav.PropFilter("STATUS") + vNotCompleted
    vStatusNotCancelled = cdav.PropFilter("STATUS") + vNotCancelled
    vStatusNeedsAction = cdav.PropFilter("STATUS") + vNeedsAction
    vStatusNotDefined = cdav.PropFilter("STATUS") + cdav.NotDefined()
    vNoCompleteDate = cdav.PropFilter("COMPLETED") + cdav.NotDefined()

    if _hacks == "ignore_completed1":
        # Query in line with RFC 4791 section 7.8.9
        filters.extend([vNoCompleteDate, vStatusNotCompleted, vStatusNotCancelled])
    elif _hacks == "ignore_completed2":
        # Handle servers that return false on negated TextMatch for undefined fields
        filters.extend([vNoCompleteDate, vStatusNotDefined])
    elif _hacks == "ignore_completed3":
        # Handle recurring tasks with NEEDS-ACTION status
        filters.extend([vStatusNeedsAction])

    if searcher.start or searcher.end:
        filters.append(cdav.TimeRange(searcher.start, searcher.end))

    if searcher.alarm_start or searcher.alarm_end:
        filters.append(
            cdav.CompFilter("VALARM")
            + cdav.TimeRange(searcher.alarm_start, searcher.alarm_end)
        )

    # Map component flags/classes to comp_filter
    comp_mappings = [
        ("event", "VEVENT", Event, AsyncEvent),
        ("todo", "VTODO", Todo, AsyncTodo),
        ("journal", "VJOURNAL", Journal, AsyncJournal),
    ]

    for flag, comp_name, sync_class, async_class in comp_mappings:
        comp_classes = (
            (sync_class,) if async_class is None else (sync_class, async_class)
        )
        flagged = getattr(searcher, flag, False)

        if flagged:
            if comp_class is not None and comp_class not in comp_classes:
                raise error.ConsistencyError(
                    f"inconsistent search parameters - comp_class = {comp_class}, want {sync_class}"
                )
            comp_class = sync_class

        if comp_filter and comp_filter.attributes.get("name") == comp_name:
            comp_class = sync_class
            if (
                flag == "todo"
                and not getattr(searcher, "todo", False)
                and searcher.include_completed is None
            ):
                searcher.include_completed = True
            setattr(searcher, flag, True)

        if comp_class in comp_classes:
            if comp_filter:
                assert comp_filter.attributes.get("name") == comp_name
            else:
                comp_filter = cdav.CompFilter(comp_name)
            setattr(searcher, flag, True)

    if comp_class and not comp_filter:
        raise error.ConsistencyError(f"unsupported comp class {comp_class} for search")

    # Special hack for bedework - no comp_filter, do client-side filtering
    if _hacks == "no_comp_filter":
        comp_filter = None
        comp_class = None

    # Add property filters
    for property in searcher._property_operator:
        if searcher._property_operator[property] == "undef":
            match = cdav.NotDefined()
            filters.append(cdav.PropFilter(property.upper()) + match)
        else:
            value = searcher._property_filters[property]
            property_ = property.upper()
            if property.lower() == "category":
                property_ = "CATEGORIES"
            if property.lower() == "categories":
                values = value.cats
            else:
                values = [value]

            for value in values:
                if hasattr(value, "to_ical"):
                    value = value.to_ical()

                # Get collation setting for this property if available
                collation_str = "i;octet"  # Default to binary
                if (
                    hasattr(searcher, "_property_collation")
                    and property in searcher._property_collation
                ):
                    case_sensitive = searcher._property_case_sensitive.get(
                        property, True
                    )
                    collation_str = collation_to_caldav(
                        searcher._property_collation[property], case_sensitive
                    )

                match = cdav.TextMatch(value, collation=collation_str)
                filters.append(cdav.PropFilter(property_) + match)

    # Assemble the query
    if comp_filter and filters:
        comp_filter += filters
        vcalendar += comp_filter
    elif comp_filter:
        vcalendar += comp_filter
    elif filters:
        vcalendar += filters

    filter_elem = cdav.Filter() + vcalendar
    root = cdav.CalendarQuery() + [prop, filter_elem]

    return (root, comp_class)
