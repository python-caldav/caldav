from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import datetime
from typing import Any
from typing import List
from typing import Optional

from icalendar.prop import TypesFactory
from lxml import etree

from .calendarobjectresource import CalendarObjectResource
from .calendarobjectresource import Event
from .calendarobjectresource import Journal
from .calendarobjectresource import Todo
from .collection import Calendar
from .elements import cdav
from .elements import dav
from .elements.base import BaseElement
from .lib import error

TypesFactory = TypesFactory()


@dataclass
class ComponentSearcher:
    """The primary purpose of this class is to bundle together all
    search filters plus sort options to be used in calendar searches.
    I also have long-term plans to allow for comparative filtering,
    logical OR, etc.  Things that are not supported by the CalDAV
    protocol can still be done client-side.  Over time I'm going to
    support other protocols that may or may not support more advanced
    searches.

    For simple searches, the old way to do it will always work:
    ``calendar.search(from=..., to=..., ...)``
    This class offers an alternative way, this should be equivalent:
    ``ComponentSearchFilter(from=..., to=...).search(calendar)``

    icalendar properties are not meant to be sent through the
    constructor, use the ``add_property_filter`` method.  Same
    goes with sort keys, they can be added through the ``add_sort_key`` method.

    The ``todo``, ``event`` and ``journal`` parameters are booleans
    for filtering the component type.  It's currently recommended to
    set one and only one of them to True.  If i.e. both todo and
    journal is set to True, everything but events should be returned,
    but don't expect this to work as of 2025-11.  If none er given
    (the default), all objects should be returned.  The latter depends
    either on the server implementation or that the correct
    ``compatibility_hints`` is configured for the caldav server.

    For ``todo``, ``include_completed`` defaults to None, adding
    logic for filtering out those.

    ``start`` and ``end`` is giving a time range as defined in
    RFC4791, section 9.9.  Note that those must be timestamps
    and cannot be dates (as for now).

    ``alarm_start`` and ``alarm_end`` is similar for alarm searching

    If ``expand`` is set to True, recurring objects will be expanded
    into reccurence objects.  This is only applicable if used together
    with both ``start`` and ``end``.  Recommended.
    """

    todo: bool = None
    event: bool = None
    journal: bool = None
    start: datetime = None
    end: datetime = None
    alarm_start: datetime = None
    alarm_end: datetime = None
    comp_class: CalendarObjectResource = None
    include_completed: bool = None

    expand: bool = False

    _sort_keys: list = field(default_factory=list)
    _property_filters: dict = field(default_factory=dict)
    _property_operator: dict = field(default_factory=dict)

    def add_property_filter(self, key: str, value: Any, operator: str = "contains") -> None:
        """Adds a filter for some specific iCalendar property.

        An iCalendar property should not be confused with a CalDAV
        property.  Examples of valid iCalendar properties: SUMMARY,
        LOCATION, DESCRIPTION, DTSTART, STATUS, CLASS, etc

        :param key: must be an icalendar property, i.e. SUMMARY
        :param value: must adhere to the type defined in the RFC
        :param operator: only == supported as for now

        """
        ## some day in the future, perhaps we'll implement support for comparative operators ...
        assert operator in ("contains", "undef")
        if operator != "undef":
            self._property_filters[key] = TypesFactory.for_property(key)(value)
        self._property_operator[key] = operator

    def add_sort_key(self, key: str, reversed: bool = None) -> None:
        """
        The sort key should be an icalendar property.
        """
        assert key in TypesFactory.types_map or key in ("isnt_overdue", "hasnt_started")
        self._sort_keys.append((key, reversed))

    def filter(*args, **kwargs):
        raise NotImplementedError()

    def _search_caldav_with_comptypes(
        self,
        calendar: Calendar,
        server_expand: bool = False,
        split_expanded: bool = True,
        props: Optional[List[cdav.CalendarData]] = None,
        xml: str = None,
        _hacks: str = None,
    ) -> List[CalendarObjectResource]:
        """
        Internal method - does three searches, one for each comp class (event, journal, todo).
        """
        if xml and (isinstance(xml, str) or "calendar-query" in xml.tag):
            raise NotImplementedError(
                "full xml given, and it has to be patched to include comp_type"
            )
        clone = replace(self)
        objects = []
        for comp_class in (Event, Todo, Journal):
            clone.comp_class = comp_class
            objects += clone.search_caldav(
                calendar, server_expand, split_expanded, props, xml
            )
        self.sort_objects(objects)
        return objects

    ## TODO: refactor, split more logic out in smaller methods
    def search_caldav(
        self,
        calendar: Calendar,
        server_expand: bool = False,
        split_expanded: bool = True,
        props: Optional[List[cdav.CalendarData]] = None,
        xml: str = None,
        _hacks: str = None,
    ) -> List[CalendarObjectResource]:
        """Do the search on a CalDAV calendar.

        Only CalDAV-specific parameters goes to this method.  Those
        parameters are pretty obscure - mostly for power users.
        Unless you have some very special needs, the recommendation is
        to not use those.

        :param calendar: Calendar to be searched
        :param server_expand: Ask the CalDAV server to expand recurrences
        :param split_expanded: Don't collect a recurrence set in one ical calendar
        :param props: CalDAV properties to send in the query
        :param xml: XML query to be sent to the server (string or elements)
        :param _hacks: Please don't ask!

        If xml is given, any other filtering will not be sent to the server.
        They may still be applied through client-side filtering. (TODO: work in progress)

        caldav search is the default search as for now - so we have an alias for it ``search``.

        ``searcher.search(calendar)`` will always work, but no future guarantees are given
        that the caldav parameters can be added.

        """
        if self.expand or server_expand:
            if not self.start or not self.end:
                raise error.ReportError("can't expand without a date range")

        ## special compatibility-case for servers that does not
        ## support combined searches very well
        if not calendar.client.features.is_supported("search.combined-is-logical-and"):
            if self.start or self.end:
                if self._property_filters:
                    clone = replace(self, _property_filters={})
                    objects = clone.search_caldav(
                        calendar, server_expand, split_expanded, props, xml
                    )
                    return self.filter(objects)

        ## special compatibility-case when searching for pending todos
        if self.todo and not self.include_completed:
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
            if calendar.client.features.is_supported(
                "search.combined-is-logical-and"
            ) and (
                not calendar.client.features.is_supported(
                    "search.recurrences.includes-implicit.todo"
                )
                or calendar.client.features.is_supported(
                    "search.recurrences.includes-implicit.todo.pending"
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
                        clone.search_caldav(
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
                matches = clone.search_caldav(
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
                    ## Client-side filtering is probably cheap, so we'll do it
                    ## even when it shouldn't be needed.
                    ## (can we assert all tasks have a valid STATUS field?)
                    if any(
                        x.get("STATUS") not in ("COMPLETED", "CANCELLED")
                        for x in item.icalendar_instance.subcomponents
                    ):
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

                return self._search_caldav_with_comptypes(
                    calendar, server_expand, split_expanded, props, orig_xml, _hacks
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
                    return self._search_caldav_with_comptypes(
                        calendar, server_expand, split_expanded, props, orig_xml, _hacks
                    )
                raise

            ## Some things, like `calendar.object_by_uid`, should always work, no matter if `davclient.compatibility_hints` is correctly configured or not
            if not objects and not self.comp_class and _hacks == "insist":
                return self._search_caldav_with_comptypes(
                    calendar, server_expand, split_expanded, props, orig_xml, _hacks
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

        if self.expand:
            ## expand can only be used together with start and end (and not
            ## with xml).  Error checking has already been done in
            ## build_search_xml_query above.
            start = self.start
            end = self.end

            ## Verify that any recurring objects returned are already expanded
            for o in objects:
                component = o.icalendar_component
                if component is None:
                    continue
                recurrence_properties = ["exdate", "exrule", "rdate", "rrule"]
                if any(key in component for key in recurrence_properties):
                    o.expand_rrule(start, end, include_completed=self.include_completed)

            ## An expanded recurring object comes as one Event() with
            ## icalendar data containing multiple objects.  The caller may
            ## expect multiple Event()s.  This code splits events into
            ## separate objects:
        if (self.expand or server_expand) and split_expanded:
            objects_ = objects
            objects = []
            for o in objects_:
                objects.extend(o.split_expanded())

        ## partial workaround for https://github.com/python-caldav/caldav/issues/201
        for obj in objects:
            try:
                obj.load(only_if_unloaded=True)
            except:
                pass

        self.sort_objects(objects)
        return objects

    search = search_caldav

    def build_search_xml_query(
        self, server_expand=False, props=None, filters=None, _hacks=None
    ):
        """This method will produce a caldav search query as an etree object.

        It is primarily to be used from the search method.  See the
        documentation for the search method for more information.
        """
        # those xml elements are weird.  (a+b)+c != a+(b+c).  First makes b and c as list members of a, second makes c an element in b which is an element of a.
        # First objective is to let this take over all xml search query building and see that the current tests pass.
        # ref https://www.ietf.org/rfc/rfc4791.txt, section 7.8.9 for how to build a todo-query
        # We'll play with it and don't mind it's getting ugly and don't mind that the test coverage is lacking.
        # we'll refactor and create some unit tests later, as well as ftests for complicated queries.

        # build the request
        data = cdav.CalendarData()
        if server_expand:
            if not self.start or not self.end:
                raise error.ReportError("can't expand without a date range")
            data += cdav.Expand(self.start, self.end)
        if props is None:
            props_ = [data]
        else:
            props_ = [data] + props
        prop = dav.Prop() + props_
        vcalendar = cdav.CompFilter("VCALENDAR")

        comp_filter = None

        if filters:
            ## It's disgraceful - `somexml = xml + [ more_elements ]` will alter xml,
            ## and there exists no `xml.copy`
            ## Hence, we need to import the deepcopy tool ...
            filters = deepcopy(filters)
            if filters.tag == cdav.CompFilter.tag:
                comp_filter = filters
                filters = []

        else:
            filters = []

        vNotCompleted = cdav.TextMatch("COMPLETED", negate=True)
        vNotCancelled = cdav.TextMatch("CANCELLED", negate=True)
        vNeedsAction = cdav.TextMatch("NEEDS-ACTION")
        vStatusNotCompleted = cdav.PropFilter("STATUS") + vNotCompleted
        vStatusNotCancelled = cdav.PropFilter("STATUS") + vNotCancelled
        vStatusNeedsAction = cdav.PropFilter("STATUS") + vNeedsAction
        vStatusNotDefined = cdav.PropFilter("STATUS") + cdav.NotDefined()
        vNoCompleteDate = cdav.PropFilter("COMPLETED") + cdav.NotDefined()
        if _hacks == "ignore_completed1":
            ## This query is quite much in line with https://tools.ietf.org/html/rfc4791#section-7.8.9
            filters.extend([vNoCompleteDate, vStatusNotCompleted, vStatusNotCancelled])
        elif _hacks == "ignore_completed2":
            ## some server implementations (i.e. NextCloud
            ## and Baikal) will yield "false" on a negated TextMatch
            ## if the field is not defined.  Hence, for those
            ## implementations we need to turn back and ask again
            ## ... do you have any VTODOs for us where the STATUS
            ## field is not defined? (ref
            ## https://github.com/python-caldav/caldav/issues/14)
            filters.extend([vNoCompleteDate, vStatusNotDefined])
        elif _hacks == "ignore_completed3":
            ## ... and considering recurring tasks we really need to
            ## look a third time as well, this time for any task with
            ## the NEEDS-ACTION status set (do we need the first go?
            ## NEEDS-ACTION or no status set should cover them all?)
            filters.extend([vStatusNeedsAction])

        if self.start or self.end:
            filters.append(cdav.TimeRange(self.start, self.end))

        if self.alarm_start or self.alarm_end:
            filters.append(
                cdav.CompFilter("VALARM")
                + cdav.TimeRange(self.alarm_start, self.alarm_end)
            )

        ## I've designed this badly, at different places the caller
        ## may pass the component type either as boolean flags:
        ##   `search(event=True, ...)`
        ## as a component class:
        ##   `search(comp_class=caldav.calendarobjectresource.Event)`
        ## or as a component filter:
        ##   `search(filters=cdav.CompFilter('VEVENT'), ...)`
        ## The only thing I don't support is the component name ('VEVENT').
        ## Anyway, this code section ensures both comp_filter and comp_class
        ## is given.  Or at least, it tries to ensure it.
        for flagged, comp_name, comp_class_ in (
            (self.event, "VEVENT", Event),
            (self.todo, "VTODO", Todo),
            (self.journal, "VJOURNAL", Journal),
        ):
            if flagged is not None:
                if not flagged:
                    raise NotImplementedError(
                        f"Negated search for {comp_name} not supported yet"
                    )
                if flagged:
                    ## event/journal/todo is set, we adjust comp_class accordingly
                    if (
                        self.comp_class is not None
                        and self.comp_class is not comp_class_
                    ):
                        raise error.ConsistencyError(
                            f"inconsistent search parameters - comp_class = {self.comp_class}, want {comp_class_}"
                        )
                    self.comp_class = comp_class_

            if comp_filter and comp_filter.attributes["name"] == comp_name:
                self.comp_class = comp_class_

            if self.comp_class == comp_class_:
                if comp_filter:
                    assert comp_filter.attributes["name"] == comp_name
                else:
                    comp_filter = cdav.CompFilter(comp_name)

        if self.comp_class and not comp_filter:
            raise error.ConsistencyError(
                f"unsupported comp class {self.comp_class} for search"
            )

        for property in self._property_operator:
            if self._property_operator[property] == "undef":
                match = cdav.NotDefined()
            else:
                match = cdav.TextMatch(self._property_filters[property].to_ical())
            filters.append(cdav.PropFilter(property.upper()) + match)

        if comp_filter and filters:
            comp_filter += filters
            vcalendar += comp_filter
        elif comp_filter:
            vcalendar += comp_filter
        elif filters:
            vcalendar += filters

        filter = cdav.Filter() + vcalendar

        root = cdav.CalendarQuery() + [prop, filter]

        return (root, self.comp_class)

    def sort_objects(self, objects):
        def sort_key_func(x):
            ret = []
            comp = x.icalendar_component
            defaults = {
                ## TODO: all possible non-string sort attributes needs to be listed here, otherwise we will get type errors when comparing objects with the property defined vs undefined (or maybe we should make an "undefined" object that always will compare below any other type?  Perhaps there exists such an object already?)
                "due": "2050-01-01",
                "dtstart": "1970-01-01",
                "priority": 0,
                "status": {
                    "VTODO": "NEEDS-ACTION",
                    "VJOURNAL": "FINAL",
                    "VEVENT": "TENTATIVE",
                }[comp.name],
                "category": "",
                ## Usage of strftime is a simple way to ensure there won't be
                ## problems if comparing dates with timestamps
                "isnt_overdue": not (
                    "due" in comp
                    and comp["due"].dt.strftime("%F%H%M%S")
                    < datetime.now().strftime("%F%H%M%S")
                ),
                "hasnt_started": (
                    "dtstart" in comp
                    and comp["dtstart"].dt.strftime("%F%H%M%S")
                    > datetime.now().strftime("%F%H%M%S")
                ),
            }
            for sort_key, reverse in self._sort_keys:
                val = comp.get(sort_key, None)
                if val is None:
                    ret.append(defaults.get(sort_key.lower(), ""))
                    continue
                if hasattr(val, "dt"):
                    val = val.dt
                elif hasattr(val, "cats"):
                    val = ",".join(val.cats)
                if hasattr(val, "strftime"):
                    val = val.strftime("%F%H%M%S")
                if reverse:
                    if isinstance(val, str):
                        val = val.encode()
                        val = bytes(b ^ 0xFF for b in val)
                    else:
                        val = -val
                ret.append(val)

            return ret

        if self._sort_keys:
            objects.sort(key=sort_key_func)
