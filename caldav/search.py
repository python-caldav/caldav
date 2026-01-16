from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import datetime
from typing import Any
from typing import List
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union

from icalendar import Timezone
from icalendar.prop import TypesFactory
from icalendar_searcher import Searcher
from icalendar_searcher.collation import Collation

from .calendarobjectresource import CalendarObjectResource
from .calendarobjectresource import Event
from .calendarobjectresource import Journal
from .calendarobjectresource import Todo
from .collection import Calendar
from .lib import error
from .operations.search_ops import build_search_xml_query as _build_search_xml_query
from .operations.search_ops import collation_to_caldav
from .operations.search_ops import determine_post_filter_needed
from .operations.search_ops import filter_search_results
from .operations.search_ops import get_explicit_contains_properties
from .operations.search_ops import needs_pending_todo_multi_search
from .operations.search_ops import should_remove_category_filter
from .operations.search_ops import should_remove_property_filters_for_combined

if TYPE_CHECKING:
    from .collection import Calendar as AsyncCalendar
    from .calendarobjectresource import (
        CalendarObjectResource as AsyncCalendarObjectResource,
        Event as AsyncEvent,
        Journal as AsyncJournal,
        Todo as AsyncTodo,
    )

TypesFactory = TypesFactory()


# Re-export for backward compatibility
_collation_to_caldav = collation_to_caldav


@dataclass
class CalDAVSearcher(Searcher):
    """The baseclass (which is generic, and not CalDAV-specific)
    allows building up a search query search logic.

    The base class also allows for simple client-side filtering (and
    at some point in the future, more complex client-side filtering).

    The CalDAV protocol is difficult, ambigiuous and does not offer
    all kind of searches.  Client-side filtering may be needed to
    smoothen over differences in how the different servers handle
    search queries, as well as allowing for more complex searches.

    A search may be performed by first setting up a CalDAVSearcher,
    populate it with filter options, and then initiate the search from
    he CalDAVSearcher.  Something like this (see the doc in the base
    class):

    ``ComponentSearchFilter(from=..., to=...).search(calendar)``

    However, for simple searches, the old way to
    do it will always work:

    ``calendar.search(from=..., to=..., ...)``

    The ``todo``, ``event`` and ``journal`` parameters are booleans
    for filtering the component type.  It's currently recommended to
    set one and only one of them to True, as of 2025-11 there is no
    guarantees for correct behaviour if setting two of them.  Also, if
    none is given (the default), all objects should be returned -
    however, all examples in the CalDAV RFC filters things by
    component, and the different servers do different things when
    confronted with a search missing component type.  With the correct
    ``compatibility_hints`` (``davclient.features``) configured for
    the caldav server, the algorithms will ensure correct behaviour.

    Both the iCalendar standard and the (Cal)DAV standard defines
    "properties".  Make sure not to confuse those.  iCalendar
    properties used for filtering can be passed using
    ``searcher.add_property_filter``.
    """

    comp_class: Optional["CalendarObjectResource"] = None
    _explicit_operators: set = field(default_factory=set)

    def add_property_filter(
        self,
        key: str,
        value: Any,
        operator: str = None,
        case_sensitive: bool = True,
        collation: Optional[Collation] = None,
        locale: Optional[str] = None,
    ) -> None:
        """Adds a filter for some specific iCalendar property.

        Examples of valid iCalendar properties: SUMMARY,
        LOCATION, DESCRIPTION, DTSTART, STATUS, CLASS, etc

        :param key: iCalendar property name (e.g., SUMMARY).
                   Special virtual property "category" (singular) is also supported
                   for substring matching within category names
        :param value: Filter value, should adhere to the type defined in the RFC
        :param operator: Comparison operator ("contains", "==", "undef"). If not
                        specified, the server decides the matching behavior (usually
                        substring search per RFC). If explicitly set to "contains"
                        and the server doesn't support substring search, client-side
                        filtering is used (may transfer more data from server).
        :param case_sensitive: If False, text comparisons are case-insensitive.
                              Note: CalDAV standard case-insensitivity only applies
                              to ASCII characters.
        :param collation: Advanced collation strategy for text comparison.
                         May not work on all servers.
        :param locale: Locale string (e.g., "de_DE") for locale-aware collation.
                      Only used with collation=Collation.LOCALE. May not work on
                      all servers.

        **Supported operators:**

        * **contains** - substring match (e.g., "rain" matches "Training session"
          and "Singing in the rain")
        * **==** - exact match required, enforced client-side
        * **undef** - matches if property is not defined (value parameter ignored)

        **Special handling for categories:**

        - **"categories"** (plural): Exact category name matching
          - "contains": subset check (all filter categories must be in component)
          - "==": exact set equality (same categories, order doesn't matter)
          - Commas in filter values split into multiple categories

        - **"category"** (singular): Substring matching within category names
          - "contains": substring match (e.g., "out" matches "outdoor")
          - "==": exact match to at least one category name
          - Commas in filter values treated as literal characters

        Examples:
            # Case-insensitive search
            searcher.add_property_filter("SUMMARY", "meeting", case_sensitive=False)

            # Explicit substring search (guaranteed via client-side if needed)
            searcher.add_property_filter("LOCATION", "room", operator="contains")

            # Exact match
            searcher.add_property_filter("STATUS", "CONFIRMED", operator="==")
        """
        if operator is not None:
            # Base class lowercases the key, so we need to as well
            self._explicit_operators.add(key.lower())
            super().add_property_filter(
                key, value, operator, case_sensitive, collation, locale
            )
        else:
            # operator not specified - don't pass it, let base class use default
            # Don't track as explicit
            super().add_property_filter(
                key,
                value,
                case_sensitive=case_sensitive,
                collation=collation,
                locale=locale,
            )

    def _search_with_comptypes(
        self,
        calendar: Calendar,
        server_expand: bool = False,
        split_expanded: bool = True,
        props: Optional[List[cdav.CalendarData]] = None,
        xml: str = None,
        _hacks: str = None,
        post_filter: bool = None,
    ) -> List[CalendarObjectResource]:
        """
        Internal method - does three searches, one for each comp class (event, journal, todo).
        """
        if xml and (isinstance(xml, str) or "calendar-query" in xml.tag):
            raise NotImplementedError(
                "full xml given, and it has to be patched to include comp_type"
            )
        objects = []

        assert self.event is None and self.todo is None and self.journal is None

        for comp_class in (Event, Todo, Journal):
            clone = replace(self)
            clone.comp_class = comp_class
            objects += clone.search(
                calendar, server_expand, split_expanded, props, xml, post_filter, _hacks
            )
        return self.sort(objects)

    ## TODO: refactor, split more logic out in smaller methods
    def search(
        self,
        calendar: Calendar,
        server_expand: bool = False,
        split_expanded: bool = True,
        props: Optional[List[cdav.CalendarData]] = None,
        xml: str = None,
        post_filter=None,
        _hacks: str = None,
    ) -> List[CalendarObjectResource]:
        """Do the search on a CalDAV calendar.

        Only CalDAV-specific parameters goes to this method.  Those
        parameters are pretty obscure - mostly for power users and
        internal usage.  Unless you have some very special needs, the
        recommendation is to not pass anything but the calendar.

        :param calendar: Calendar to be searched
        :param server_expand: Ask the CalDAV server to expand recurrences
        :param split_expanded: Don't collect a recurrence set in one ical calendar
        :param props: CalDAV properties to send in the query
        :param xml: XML query to be sent to the server (string or elements)
        :param post_filter: Do client-side filtering after querying the server
        :param _hacks: Please don't ask!

        Make sure not to confuse he CalDAV properties with iCalendar properties.

        If ``xml`` is given, any other filtering will not be sent to the server.
        They may still be applied through client-side filtering. (TODO: work in progress)

        ``post_filter`` takes three values, ``True`` will always
        filter the results, ``False`` will never filter the results,
        and the default ``None`` will cause automagics to happen (not
        implemented yet).  Or perhaps I'll just set it to True as
        default.  TODO - make a decision here

        In the CalDAV protocol, a VCALENDAR object returned from the
        server may contain only one event/task/journal - but if the
        object is recurrent, it may contain several recurrences.
        ``split_expanded`` will split the recurrences into several
        objects.  If you don't know what you're doing, then leave this
        flag on.

        Use ``searcher.search(calendar)`` to apply the search on a caldav server.

        """
        ## Handle servers with broken component-type filtering (e.g., Bedework)
        ## Such servers may misclassify component types in responses
        comp_type_support = calendar.client.features.is_supported(
            "search.comp-type", str
        )
        if (
            (self.comp_class or self.todo or self.event or self.journal)
            and comp_type_support == "broken"
            and not _hacks
            and post_filter is not False
        ):
            _hacks = "no_comp_filter"
            post_filter = True

        ## Setting default value for post_filter
        if post_filter is None and (
            (self.todo and not self.include_completed)
            or self.expand
            or "categories" in self._property_filters
            or "category" in self._property_filters
            or not calendar.client.features.is_supported("search.text.case-sensitive")
            or not calendar.client.features.is_supported("search.time-range.accurate")
        ):
            post_filter = True

        ## split_expanded should only take effect on expanded data
        if not self.expand and not server_expand:
            split_expanded = False

        if self.expand or server_expand:
            if not self.start or not self.end:
                raise error.ReportError("can't expand without a date range")

        ## special compatbility-case for servers that does not
        ## support category search properly
        things = ("filters", "operator", "locale", "collation")
        things = [f"_property_{thing}" for thing in things]
        if (
            not calendar.client.features.is_supported("search.text.category")
            and (
                "categories" in self._property_filters
                or "category" in self._property_filters
            )
            and post_filter is not False
        ):
            replacements = {}
            for thing in things:
                replacements[thing] = getattr(self, thing).copy()
                replacements[thing].pop("categories", None)
                replacements[thing].pop("category", None)
            clone = replace(self, **replacements)
            objects = clone.search(calendar, server_expand, split_expanded, props, xml)
            return self.filter(objects, post_filter, split_expanded, server_expand)

        ## special compatibility-case for servers that do not support substring search
        ## Only applies when user explicitly requested substring search with operator="contains"
        if (
            not calendar.client.features.is_supported("search.text.substring")
            and post_filter is not False
        ):
            # Check if any property has explicitly specified operator="contains"
            explicit_contains = [
                prop
                for prop in self._property_operator
                if prop in self._explicit_operators
                and self._property_operator[prop] == "contains"
            ]
            if explicit_contains:
                # Remove explicit substring filters from server query,
                # will be applied client-side instead
                replacements = {}
                for thing in things:
                    replacements[thing] = getattr(self, thing).copy()
                    for prop in explicit_contains:
                        replacements[thing].pop(prop, None)
                # Also need to preserve the _explicit_operators set but remove these properties
                clone = replace(self, **replacements)
                clone._explicit_operators = self._explicit_operators - set(
                    explicit_contains
                )
                objects = clone.search(
                    calendar, server_expand, split_expanded, props, xml
                )
                return self.filter(
                    objects,
                    post_filter=True,
                    split_expanded=split_expanded,
                    server_expand=server_expand,
                )

        ## special compatibility-case for servers that does not
        ## support combined searches very well
        if not calendar.client.features.is_supported("search.combined-is-logical-and"):
            if self.start or self.end:
                if self._property_filters:
                    replacements = {}
                    for thing in things:
                        replacements[thing] = {}
                    clone = replace(self, **replacements)
                    objects = clone.search(
                        calendar, server_expand, split_expanded, props, xml
                    )
                    return self.filter(
                        objects, post_filter, split_expanded, server_expand
                    )

        ## special compatibility-case when searching for pending todos
        if self.todo and self.include_completed is False:
            ## There are two ways to get the pending tasks - we can
            ## ask the server to filter them out, or we can do it
            ## client side.

            ## If the server does not support combined searches, then it's
            ## safest to do it client-side.

            ## There is a special case (observed with radicale as of
            ## 2025-11) where future recurrences of a task does not
            ## match when doing a server-side filtering, so for this
            ## case we also do client-side filtering (but the
            ## "feature"
            ## search.recurrences.includes-implicit.todo.pending will
            ## not be supported if the feature
            ## "search.recurrences.includes-implicit.todo" is not
            ## supported ... hence the weird or below)

            ## To be completely sure to get all pending tasks, for all
            ## server implementations and for all valid icalendar
            ## objects, we send three different searches to the
            ## server.  This is probably bloated, and may in many
            ## cases be more expensive than to ask for all tasks.  At
            ## the other hand, for a well-used and well-handled old
            ## todo-list, there may be a small set of pending tasks
            ## and heaps of done tasks.

            ## TODO: consider if not ignore_completed3 is sufficient,
            ## then the recursive part of the query here is moot, and
            ## we wouldn't waste so much time on repeated queries
            clone = replace(self, include_completed=True)
            clone.include_completed = True
            ## No point with expanding in the subqueries - the expand logic will be handled
            ## further down.  We leave server_expand as it is, though.
            clone.expand = False
            if (
                calendar.client.features.is_supported("search.text")
                and calendar.client.features.is_supported(
                    "search.combined-is-logical-and"
                )
                and (
                    not calendar.client.features.is_supported(
                        "search.recurrences.includes-implicit.todo"
                    )
                    or calendar.client.features.is_supported(
                        "search.recurrences.includes-implicit.todo.pending"
                    )
                )
            ):
                matches = []
                for hacks in (
                    "ignore_completed1",
                    "ignore_completed2",
                    "ignore_completed3",
                ):
                    ## The algorithm below does not handle recurrence split gently
                    matches.extend(
                        clone.search(
                            calendar,
                            server_expand,
                            split_expanded=False,
                            props=props,
                            xml=xml,
                            _hacks=hacks,
                        )
                    )
            else:
                ## The algorithm below does not handle recurrence split gently
                matches = clone.search(
                    calendar,
                    server_expand,
                    split_expanded=False,
                    props=props,
                    xml=xml,
                    _hacks=_hacks,
                )
            objects = []
            match_set = set()
            for item in matches:
                if item.url not in match_set:
                    match_set.add(item.url)
                    objects.append(item)
        else:
            orig_xml = xml

            ## Now the xml variable may be either a full query or a filter
            ## and it may be either a string or an object.
            if not xml or (
                not isinstance(xml, str) and not xml.tag.endswith("calendar-query")
            ):
                (xml, self.comp_class) = self.build_search_xml_query(
                    server_expand, props=props, filters=xml, _hacks=_hacks
                )

            if not self.comp_class and not calendar.client.features.is_supported(
                "search.comp-type-optional"
            ):
                if self.include_completed is None:
                    self.include_completed = True

                return self._search_with_comptypes(
                    calendar,
                    server_expand,
                    split_expanded,
                    props,
                    orig_xml,
                    post_filter,
                    _hacks,
                )

            try:
                (response, objects) = calendar._request_report_build_resultlist(
                    xml, self.comp_class, props=props
                )

            except error.ReportError as err:
                ## This is only for backward compatibility.
                ## Partial fix https://github.com/python-caldav/caldav/issues/401
                if (
                    calendar.client.features.backward_compatibility_mode
                    and not self.comp_class
                    and not "400" in err.reason
                ):
                    return self._search_with_comptypes(
                        calendar,
                        server_expand,
                        split_expanded,
                        props,
                        orig_xml,
                        post_filter,
                        _hacks,
                    )
                raise

            ## Some things, like `calendar.object_by_uid`, should always work, no matter if `davclient.compatibility_hints` is correctly configured or not
            if not objects and not self.comp_class and _hacks == "insist":
                return self._search_with_comptypes(
                    calendar,
                    server_expand,
                    split_expanded,
                    props,
                    orig_xml,
                    post_filter,
                    _hacks,
                )

        obj2 = []

        for o in objects:
            ## This would not be needed if the servers would follow the standard ...
            ## TODO: use calendar.calendar_multiget - see https://github.com/python-caldav/caldav/issues/487
            try:
                o.load(only_if_unloaded=True)
                obj2.append(o)
            except:
                logging.error(
                    "Server does not want to reveal details about the calendar object",
                    exc_info=True,
                )
                pass
        objects = obj2

        ## Google sometimes returns empty objects
        objects = [o for o in objects if o.has_component()]
        objects = self.filter(objects, post_filter, split_expanded, server_expand)

        ## partial workaround for https://github.com/python-caldav/caldav/issues/201
        for obj in objects:
            try:
                obj.load(only_if_unloaded=True)
            except:
                pass

        return self.sort(objects)

    async def _async_search_with_comptypes(
        self,
        calendar: "AsyncCalendar",
        server_expand: bool = False,
        split_expanded: bool = True,
        props: Optional[List[cdav.CalendarData]] = None,
        xml: str = None,
        _hacks: str = None,
        post_filter: bool = None,
    ) -> List["AsyncCalendarObjectResource"]:
        """
        Internal async method - does three searches, one for each comp class.
        """
        # Import unified types at runtime to avoid circular imports
        # These work with both sync and async clients
        from .calendarobjectresource import Event as AsyncEvent, Journal as AsyncJournal, Todo as AsyncTodo

        if xml and (isinstance(xml, str) or "calendar-query" in xml.tag):
            raise NotImplementedError(
                "full xml given, and it has to be patched to include comp_type"
            )
        objects: List["AsyncCalendarObjectResource"] = []

        assert self.event is None and self.todo is None and self.journal is None

        for comp_class in (AsyncEvent, AsyncTodo, AsyncJournal):
            clone = replace(self)
            clone.comp_class = comp_class
            results = await clone.async_search(
                calendar, server_expand, split_expanded, props, xml, post_filter, _hacks
            )
            objects.extend(results)
        return self.sort(objects)

    async def async_search(
        self,
        calendar: "AsyncCalendar",
        server_expand: bool = False,
        split_expanded: bool = True,
        props: Optional[List[cdav.CalendarData]] = None,
        xml: str = None,
        post_filter=None,
        _hacks: str = None,
    ) -> List["AsyncCalendarObjectResource"]:
        """Async version of search() - does the search on an AsyncCalendar.

        This method mirrors the sync search() method but uses async HTTP operations.
        All the same compatibility logic is applied.

        See the sync search() method for full documentation.
        """
        # Import unified types at runtime to avoid circular imports
        # These work with both sync and async clients
        from .calendarobjectresource import Event as AsyncEvent, Journal as AsyncJournal, Todo as AsyncTodo

        ## Handle servers with broken component-type filtering (e.g., Bedework)
        comp_type_support = calendar.client.features.is_supported(
            "search.comp-type", str
        )
        if (
            (self.comp_class or self.todo or self.event or self.journal)
            and comp_type_support == "broken"
            and not _hacks
            and post_filter is not False
        ):
            _hacks = "no_comp_filter"
            post_filter = True

        ## Setting default value for post_filter
        if post_filter is None and (
            (self.todo and not self.include_completed)
            or self.expand
            or "categories" in self._property_filters
            or "category" in self._property_filters
            or not calendar.client.features.is_supported("search.text.case-sensitive")
            or not calendar.client.features.is_supported("search.time-range.accurate")
        ):
            post_filter = True

        ## split_expanded should only take effect on expanded data
        if not self.expand and not server_expand:
            split_expanded = False

        if self.expand or server_expand:
            if not self.start or not self.end:
                raise error.ReportError("can't expand without a date range")

        ## special compatibility-case for servers that does not
        ## support category search properly
        things = ("filters", "operator", "locale", "collation")
        things = [f"_property_{thing}" for thing in things]
        if (
            not calendar.client.features.is_supported("search.text.category")
            and (
                "categories" in self._property_filters
                or "category" in self._property_filters
            )
            and post_filter is not False
        ):
            replacements = {}
            for thing in things:
                replacements[thing] = getattr(self, thing).copy()
                replacements[thing].pop("categories", None)
                replacements[thing].pop("category", None)
            clone = replace(self, **replacements)
            objects = await clone.async_search(
                calendar, server_expand, split_expanded, props, xml
            )
            return self.filter(objects, post_filter, split_expanded, server_expand)

        ## special compatibility-case for servers that do not support substring search
        if (
            not calendar.client.features.is_supported("search.text.substring")
            and post_filter is not False
        ):
            explicit_contains = [
                prop
                for prop in self._property_operator
                if prop in self._explicit_operators
                and self._property_operator[prop] == "contains"
            ]
            if explicit_contains:
                replacements = {}
                for thing in things:
                    replacements[thing] = getattr(self, thing).copy()
                    for prop in explicit_contains:
                        replacements[thing].pop(prop, None)
                clone = replace(self, **replacements)
                clone._explicit_operators = self._explicit_operators - set(
                    explicit_contains
                )
                objects = await clone.async_search(
                    calendar, server_expand, split_expanded, props, xml
                )
                return self.filter(
                    objects,
                    post_filter=True,
                    split_expanded=split_expanded,
                    server_expand=server_expand,
                )

        ## special compatibility-case for servers that do not support combined searches
        if not calendar.client.features.is_supported("search.combined-is-logical-and"):
            if self.start or self.end:
                if self._property_filters:
                    replacements = {}
                    for thing in things:
                        replacements[thing] = {}
                    clone = replace(self, **replacements)
                    objects = await clone.async_search(
                        calendar, server_expand, split_expanded, props, xml
                    )
                    return self.filter(
                        objects, post_filter, split_expanded, server_expand
                    )

        ## special compatibility-case when searching for pending todos
        if self.todo and self.include_completed is False:
            clone = replace(self, include_completed=True)
            clone.include_completed = True
            clone.expand = False
            if (
                calendar.client.features.is_supported("search.text")
                and calendar.client.features.is_supported(
                    "search.combined-is-logical-and"
                )
                and (
                    not calendar.client.features.is_supported(
                        "search.recurrences.includes-implicit.todo"
                    )
                    or calendar.client.features.is_supported(
                        "search.recurrences.includes-implicit.todo.pending"
                    )
                )
            ):
                matches: List["AsyncCalendarObjectResource"] = []
                for hacks in (
                    "ignore_completed1",
                    "ignore_completed2",
                    "ignore_completed3",
                ):
                    results = await clone.async_search(
                        calendar,
                        server_expand,
                        split_expanded=False,
                        props=props,
                        xml=xml,
                        _hacks=hacks,
                    )
                    matches.extend(results)
            else:
                matches = await clone.async_search(
                    calendar,
                    server_expand,
                    split_expanded=False,
                    props=props,
                    xml=xml,
                    _hacks=_hacks,
                )
            objects: List["AsyncCalendarObjectResource"] = []
            match_set = set()
            for item in matches:
                if item.url not in match_set:
                    match_set.add(item.url)
                    objects.append(item)
        else:
            orig_xml = xml

            if not xml or (
                not isinstance(xml, str) and not xml.tag.endswith("calendar-query")
            ):
                (xml, self.comp_class) = self.build_search_xml_query(
                    server_expand, props=props, filters=xml, _hacks=_hacks
                )

            # Convert sync comp_class to async equivalent
            sync_to_async = {
                Event: AsyncEvent,
                Todo: AsyncTodo,
                Journal: AsyncJournal,
            }
            async_comp_class = sync_to_async.get(self.comp_class, self.comp_class)

            if not self.comp_class and not calendar.client.features.is_supported(
                "search.comp-type-optional"
            ):
                if self.include_completed is None:
                    self.include_completed = True

                return await self._async_search_with_comptypes(
                    calendar,
                    server_expand,
                    split_expanded,
                    props,
                    orig_xml,
                    _hacks,
                    post_filter,
                )

            try:
                (response, objects) = await calendar._request_report_build_resultlist(
                    xml, async_comp_class, props=props
                )

            except error.ReportError as err:
                if (
                    calendar.client.features.backward_compatibility_mode
                    and not self.comp_class
                    and "400" not in err.reason
                ):
                    return await self._async_search_with_comptypes(
                        calendar,
                        server_expand,
                        split_expanded,
                        props,
                        orig_xml,
                        _hacks,
                        post_filter,
                    )
                raise

            if not objects and not self.comp_class and _hacks == "insist":
                return await self._async_search_with_comptypes(
                    calendar,
                    server_expand,
                    split_expanded,
                    props,
                    orig_xml,
                    _hacks,
                    post_filter,
                )

        obj2: List["AsyncCalendarObjectResource"] = []
        for o in objects:
            try:
                # load() may return self (sync) or coroutine (async) depending on state
                result = o.load(only_if_unloaded=True)
                import inspect
                if inspect.isawaitable(result):
                    await result
                obj2.append(o)
            except Exception:
                import logging

                logging.error(
                    "Server does not want to reveal details about the calendar object",
                    exc_info=True,
                )
        objects = obj2

        ## Google sometimes returns empty objects
        objects = [o for o in objects if o.has_component()]
        objects = self.filter(objects, post_filter, split_expanded, server_expand)

        ## partial workaround for https://github.com/python-caldav/caldav/issues/201
        for obj in objects:
            try:
                # load() may return self (sync) or coroutine (async) depending on state
                result = obj.load(only_if_unloaded=True)
                import inspect
                if inspect.isawaitable(result):
                    await result
            except Exception:
                pass

        return self.sort(objects)

    def filter(
        self,
        objects: List[CalendarObjectResource],
        post_filter: Optional[bool] = None,
        split_expanded: bool = True,
        server_expand: bool = False,
    ) -> List[CalendarObjectResource]:
        """Apply client-side filtering and handle recurrence expansion/splitting.

        This method delegates to the operations layer filter_search_results().
        See that function for full documentation.

        :param objects: List of Event/Todo/Journal objects to filter
        :param post_filter: Whether to apply the searcher's filter logic
        :param split_expanded: Whether to split recurrence sets into separate objects
        :param server_expand: Whether server was asked to expand recurrences
        :return: Filtered and/or split list of CalendarObjectResource objects
        """
        return filter_search_results(
            objects=objects,
            searcher=self,
            post_filter=post_filter,
            split_expanded=split_expanded,
            server_expand=server_expand,
        )

    def build_search_xml_query(
        self, server_expand=False, props=None, filters=None, _hacks=None
    ):
        """Build a CalDAV calendar-query XML request.

        Delegates to the operations layer for the actual XML building.
        This method updates self.comp_class as a side effect based on
        the search parameters.

        :param server_expand: Ask server to expand recurrences
        :param props: Additional CalDAV properties to request
        :param filters: Pre-built filter elements (or None to build from self)
        :param _hacks: Compatibility hack mode
        :return: Tuple of (xml_element, comp_class)
        """
        xml, comp_class = _build_search_xml_query(
            searcher=self,
            server_expand=server_expand,
            props=props,
            filters=filters,
            _hacks=_hacks,
        )
        # Update self.comp_class from the result (side effect for compatibility)
        self.comp_class = comp_class
        return (xml, comp_class)
