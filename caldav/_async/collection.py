#!/usr/bin/env python
"""
Async collection classes - CalendarSet, Principal, Calendar, etc.

This is the async implementation that the sync wrapper delegates to.
"""
import logging
import sys
import uuid
from typing import Any
from typing import List
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union
from urllib.parse import ParseResult
from urllib.parse import quote
from urllib.parse import SplitResult
from urllib.parse import unquote

import icalendar

if TYPE_CHECKING:
    from caldav._async.davclient import AsyncDAVClient

if sys.version_info < (3, 9):
    from typing import Iterable, Sequence
else:
    from collections.abc import Iterable, Sequence

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

from caldav._async.davobject import AsyncDAVObject
from caldav.elements import cdav, dav
from caldav.lib import error
from caldav.lib.url import URL


log = logging.getLogger("caldav")


class AsyncCalendarSet(AsyncDAVObject):
    """
    A CalendarSet is a set of calendars.
    """

    async def calendars(self) -> List["AsyncCalendar"]:
        """
        List all calendar collections in this set.

        Returns:
         * [AsyncCalendar(), ...]
        """
        cals = []

        data = await self.children(cdav.Calendar.tag)
        for c_url, c_type, c_name in data:
            try:
                cal_id = c_url.split("/")[-2]
                if not cal_id:
                    continue
            except:
                log.error(f"Calendar {c_name} has unexpected url {c_url}")
                cal_id = None
            cals.append(
                AsyncCalendar(
                    self.client, id=cal_id, url=c_url, parent=self, name=c_name
                )
            )

        return cals

    async def make_calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        supported_calendar_component_set: Optional[Any] = None,
        method=None,
    ) -> "AsyncCalendar":
        """
        Utility method for creating a new calendar.

        Args:
          name: the display name of the new calendar
          cal_id: the uuid of the new calendar
          supported_calendar_component_set: what kind of objects
           (EVENT, VTODO, VFREEBUSY, VJOURNAL) the calendar should handle.

        Returns:
          AsyncCalendar(...)-object
        """
        cal = AsyncCalendar(
            self.client,
            name=name,
            parent=self,
            id=cal_id,
            supported_calendar_component_set=supported_calendar_component_set,
        )
        return await cal.save(method=method)

    async def calendar(
        self, name: Optional[str] = None, cal_id: Optional[str] = None
    ) -> "AsyncCalendar":
        """
        The calendar method will return a calendar object.  If it gets a cal_id
        but no name, it will not initiate any communication with the server

        Args:
          name: return the calendar with this display name
          cal_id: return the calendar with this calendar id or URL

        Returns:
          AsyncCalendar(...)-object
        """
        if name and not cal_id:
            for calendar in await self.calendars():
                display_name = await calendar.get_display_name()
                if display_name == name:
                    return calendar
        if name and not cal_id:
            raise error.NotFoundError(
                "No calendar with name %s found under %s" % (name, self.url)
            )
        if not cal_id and not name:
            cals = await self.calendars()
            if not cals:
                raise error.NotFoundError("no calendars found")
            return cals[0]

        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        if cal_id is None:
            raise ValueError("Unexpected value None for cal_id")

        if str(URL.objectify(cal_id).canonical()).startswith(
            str(self.client.url.canonical())
        ):
            url = self.client.url.join(cal_id)
        elif isinstance(cal_id, URL) or (
            isinstance(cal_id, str)
            and (cal_id.startswith("https://") or cal_id.startswith("http://"))
        ):
            if self.url is None:
                raise ValueError("Unexpected value None for self.url")

            url = self.url.join(cal_id)
        else:
            if self.url is None:
                raise ValueError("Unexpected value None for self.url")

            if cal_id is None:
                raise ValueError("Unexpected value None for cal_id")

            url = self.url.join(quote(cal_id) + "/")

        return AsyncCalendar(self.client, name=name, parent=self, url=url, id=cal_id)


class AsyncPrincipal(AsyncDAVObject):
    """
    This class represents a DAV Principal. It doesn't do much, except
    keep track of the URLs for the calendar-home-set, etc.
    """

    def __init__(
        self,
        client: Optional["AsyncDAVClient"] = None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        calendar_home_set: URL = None,
        **kwargs,
    ) -> None:
        """
        Returns a Principal.
        """
        self._calendar_home_set = calendar_home_set
        self._initialized = False
        super(AsyncPrincipal, self).__init__(client=client, url=url, **kwargs)

    async def _ensure_initialized(self) -> None:
        """Initialize the principal URL if not already done."""
        if self._initialized:
            return

        if self.url is None:
            if self.client is None:
                raise ValueError("Unexpected value None for self.client")

            self.url = self.client.url
            cup = await self.get_property(dav.CurrentUserPrincipal())

            if cup is None:
                log.warning("calendar server lacking a feature:")
                log.warning("current-user-principal property not found")
                log.warning("assuming %s is the principal URL" % self.client.url)

            self.url = self.client.url.join(URL.objectify(cup))

        self._initialized = True

    async def make_calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        supported_calendar_component_set: Optional[Any] = None,
        method=None,
    ) -> "AsyncCalendar":
        """
        Convenience method, bypasses the self.calendar_home_set object.
        See AsyncCalendarSet.make_calendar for details.
        """
        calendar_home = await self.get_calendar_home_set()
        return await calendar_home.make_calendar(
            name,
            cal_id,
            supported_calendar_component_set=supported_calendar_component_set,
            method=method,
        )

    async def calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        cal_url: Optional[str] = None,
    ) -> "AsyncCalendar":
        """
        The calendar method will return a calendar object.
        It will not initiate any communication with the server.
        """
        if not cal_url:
            calendar_home = await self.get_calendar_home_set()
            return await calendar_home.calendar(name, cal_id)
        else:
            if self.client is None:
                raise ValueError("Unexpected value None for self.client")

            return AsyncCalendar(self.client, url=self.client.url.join(cal_url))

    async def get_vcal_address(self) -> "icalendar.vCalAddress":
        """
        Returns the principal, as an icalendar.vCalAddress object
        """
        from icalendar import vCalAddress, vText

        cn = await self.get_display_name()
        ids = await self.calendar_user_address_set()
        cutype = await self.get_property(cdav.CalendarUserType())
        ret = vCalAddress(ids[0])
        ret.params["cn"] = vText(cn)
        ret.params["cutype"] = vText(cutype)
        return ret

    async def get_calendar_home_set(self) -> AsyncCalendarSet:
        """Get the calendar home set for this principal."""
        await self._ensure_initialized()

        if not self._calendar_home_set:
            calendar_home_set_url = await self.get_property(cdav.CalendarHomeSet())
            if (
                calendar_home_set_url is not None
                and "@" in calendar_home_set_url
                and "://" not in calendar_home_set_url
            ):
                calendar_home_set_url = quote(calendar_home_set_url)
            await self._set_calendar_home_set(calendar_home_set_url)
        return self._calendar_home_set

    async def _set_calendar_home_set(self, url) -> None:
        if isinstance(url, AsyncCalendarSet):
            self._calendar_home_set = url
            return
        sanitized_url = URL.objectify(url)
        if sanitized_url is not None:
            if (
                sanitized_url.hostname
                and sanitized_url.hostname != self.client.url.hostname
            ):
                self.client.url = sanitized_url
        self._calendar_home_set = AsyncCalendarSet(
            self.client, self.client.url.join(sanitized_url)
        )

    async def calendars(self) -> List["AsyncCalendar"]:
        """
        Return the principal's calendars
        """
        calendar_home = await self.get_calendar_home_set()
        return await calendar_home.calendars()

    async def freebusy_request(self, dtstart, dtend, attendees):
        """Sends a freebusy-request for some attendee to the server
        as per RFC6638
        """
        from caldav._async.calendarobjectresource import AsyncFreeBusy
        from datetime import datetime

        freebusy_ical = icalendar.Calendar()
        freebusy_ical.add("prodid", "-//tobixen/python-caldav//EN")
        freebusy_ical.add("version", "2.0")
        freebusy_ical.add("method", "REQUEST")
        uid = uuid.uuid1()
        freebusy_comp = icalendar.FreeBusy()
        freebusy_comp.add("uid", uid)
        freebusy_comp.add("dtstamp", datetime.now())
        freebusy_comp.add("dtstart", dtstart)
        freebusy_comp.add("dtend", dtend)
        freebusy_ical.add_component(freebusy_comp)
        outbox = await self.schedule_outbox()
        caldavobj = AsyncFreeBusy(data=freebusy_ical, parent=outbox)
        await caldavobj.add_organizer()
        for attendee in attendees:
            caldavobj.add_attendee(attendee, no_default_parameters=True)

        response = await self.client.post(
            outbox.url,
            caldavobj.data,
            headers={"Content-Type": "text/calendar; charset=utf-8"},
        )
        return response.find_objects_and_props()

    async def calendar_user_address_set(self) -> List[Optional[str]]:
        """
        defined in RFC6638
        """
        _addresses = await self.get_property(
            cdav.CalendarUserAddressSet(), parse_props=False
        )

        if _addresses is None:
            raise error.NotFoundError("No calendar user addresses given from server")

        assert not [x for x in _addresses if x.tag != dav.Href().tag]
        addresses = list(_addresses)
        addresses.sort(key=lambda x: -int(x.get("preferred", 0)))
        return [x.text for x in addresses]

    async def schedule_inbox(self) -> "AsyncScheduleInbox":
        """
        Returns the schedule inbox, as defined in RFC6638
        """
        return AsyncScheduleInbox(principal=self)

    async def schedule_outbox(self) -> "AsyncScheduleOutbox":
        """
        Returns the schedule outbox, as defined in RFC6638
        """
        return AsyncScheduleOutbox(principal=self)


class AsyncCalendar(AsyncDAVObject):
    """
    The `AsyncCalendar` object is used to represent a calendar collection.
    """

    async def _create(
        self, name=None, id=None, supported_calendar_component_set=None, method=None
    ) -> None:
        """
        Create a new calendar with display name `name` in `parent`.
        """
        if id is None:
            id = str(uuid.uuid1())
        self.id = id

        if method is None:
            if self.client:
                supported = self.client.features.is_supported(
                    "create-calendar", return_type=dict
                )
                if supported["support"] not in ("full", "fragile", "quirk"):
                    raise error.MkcalendarError(
                        "Creation of calendars (allegedly) not supported on this server"
                    )
                if (
                    supported["support"] == "quirk"
                    and supported["behaviour"] == "mkcol-required"
                ):
                    method = "mkcol"
                else:
                    method = "mkcalendar"
            else:
                method = "mkcalendar"

        path = self.parent.url.join(id + "/")
        self.url = path

        prop = dav.Prop()
        if name:
            display_name = dav.DisplayName(name)
            prop += [display_name]
        if supported_calendar_component_set:
            sccs = cdav.SupportedCalendarComponentSet()
            for scc in supported_calendar_component_set:
                sccs += cdav.Comp(scc)
            prop += sccs
        if method == "mkcol":
            prop += dav.ResourceType() + [dav.Collection(), cdav.Calendar()]

        set = dav.Set() + prop

        mkcol = (dav.Mkcol() if method == "mkcol" else cdav.Mkcalendar()) + set

        r = await self._query(
            root=mkcol, query_method=method, url=path, expected_return_value=201
        )

        if name:
            try:
                await self.set_properties([display_name])
            except Exception as e:
                try:
                    current_display_name = await self.get_display_name()
                    error.assert_(current_display_name == name)
                except:
                    log.warning(
                        "calendar server does not support display name on calendar?  Ignoring",
                        exc_info=True,
                    )

    async def get_supported_components(self) -> List[Any]:
        """
        returns a list of component types supported by the calendar
        """
        if self.url is None:
            raise ValueError("Unexpected value None for self.url")

        props = [cdav.SupportedCalendarComponentSet()]
        response = await self.get_properties(props, parse_response_xml=False)
        response_list = response.find_objects_and_props()
        prop = response_list[unquote(self.url.path)][
            cdav.SupportedCalendarComponentSet().tag
        ]
        return [supported.get("name") for supported in prop]

    async def save(self, method=None) -> Self:
        """
        The save method for a calendar is only used to create it, for now.
        We know we have to create it when we don't have a url.

        Returns:
         * self
        """
        if self.url is None:
            await self._create(
                id=self.id, name=self.name, method=method, **self.extra_init_options
            )
        return self

    async def _request_report_build_resultlist(
        self, xml, comp_class=None, props=None, no_calendardata=False
    ):
        """
        Takes some input XML, does a report query on a calendar object
        and returns the resource objects found.
        """
        from caldav._async.calendarobjectresource import AsyncCalendarObjectResource

        matches = []
        if props is None:
            props_ = [cdav.CalendarData()]
        else:
            props_ = [cdav.CalendarData()] + props
        response = await self._query(xml, 1, "report")
        results = response.expand_simple_props(props_)
        for r in results:
            pdata = results[r]
            if cdav.CalendarData.tag in pdata:
                cdata = pdata.pop(cdav.CalendarData.tag)
                comp_class_ = (
                    self._calendar_comp_class_by_data(cdata)
                    if comp_class is None
                    else comp_class
                )
            else:
                cdata = None
            if comp_class_ is None:
                comp_class_ = AsyncCalendarObjectResource
            url = URL(r)
            if url.hostname is None:
                url = quote(r)
            if self.url.join(url) == self.url:
                continue
            matches.append(
                comp_class_(
                    self.client,
                    url=self.url.join(url),
                    data=cdata,
                    parent=self,
                    props=pdata,
                )
            )
        return (response, matches)

    async def search(
        self,
        xml: str = None,
        server_expand: bool = False,
        split_expanded: bool = True,
        sort_reverse: bool = False,
        props=None,
        filters=None,
        post_filter=None,
        _hacks=None,
        **searchargs,
    ) -> List:
        """Sends a search request towards the server."""
        from caldav.search import CalDAVSearcher

        my_searcher = CalDAVSearcher()
        for key in searchargs:
            alias = key
            if key == "class_":
                alias = "class"
            if key == "category":
                alias = "categories"
            if key == "no_category":
                alias = "no_categories"
            if key == "no_class_":
                alias = "no_class"
            if key == "sort_keys":
                if isinstance(searchargs["sort_keys"], str):
                    searchargs["sort_keys"] = [searchargs["sort_keys"]]
                for sortkey in searchargs["sort_keys"]:
                    my_searcher.add_sort_key(sortkey, sort_reverse)
                    continue
            elif key == "comp_class" or key in my_searcher.__dataclass_fields__:
                setattr(my_searcher, key, searchargs[key])
                continue
            elif alias.startswith("no_"):
                my_searcher.add_property_filter(
                    alias[3:], searchargs[key], operator="undef"
                )
            else:
                my_searcher.add_property_filter(alias, searchargs[key])

        if not xml and filters:
            xml = filters

        return await my_searcher.async_search(
            self, server_expand, split_expanded, props, xml, post_filter, _hacks
        )

    async def events(self) -> List:
        """
        List all events from the calendar.
        """
        from caldav._async.calendarobjectresource import AsyncEvent

        return await self.search(comp_class=AsyncEvent)

    async def todos(
        self,
        sort_keys: Sequence[str] = ("due", "priority"),
        include_completed: bool = False,
        sort_key: Optional[str] = None,
    ) -> List:
        """
        Fetches a list of todo events
        """
        if sort_key:
            sort_keys = (sort_key,)

        return await self.search(
            todo=True, include_completed=include_completed, sort_keys=sort_keys
        )

    async def journals(self) -> List:
        """
        List all journals from the calendar.
        """
        from caldav._async.calendarobjectresource import AsyncJournal

        return await self.search(comp_class=AsyncJournal)

    async def freebusy_request(self, start, end):
        """
        Search the calendar, but return only the free/busy information.
        """
        from caldav._async.calendarobjectresource import AsyncFreeBusy

        root = cdav.FreeBusyQuery() + [cdav.TimeRange(start, end)]
        response = await self._query(root, 1, "report")
        return AsyncFreeBusy(self, response.raw)

    def _calendar_comp_class_by_data(self, data):
        """
        Returns the appropriate CalendarResourceObject child class.
        """
        from caldav._async.calendarobjectresource import (
            AsyncCalendarObjectResource,
            AsyncEvent,
            AsyncTodo,
            AsyncJournal,
            AsyncFreeBusy,
        )

        if data is None:
            return AsyncCalendarObjectResource
        if hasattr(data, "split"):
            for line in data.split("\n"):
                line = line.strip()
                if line == "BEGIN:VEVENT":
                    return AsyncEvent
                if line == "BEGIN:VTODO":
                    return AsyncTodo
                if line == "BEGIN:VJOURNAL":
                    return AsyncJournal
                if line == "BEGIN:VFREEBUSY":
                    return AsyncFreeBusy
        elif hasattr(data, "subcomponents"):
            if not len(data.subcomponents):
                return AsyncCalendarObjectResource

            ical2caldav = {
                icalendar.Event: AsyncEvent,
                icalendar.Todo: AsyncTodo,
                icalendar.Journal: AsyncJournal,
                icalendar.FreeBusy: AsyncFreeBusy,
            }
            for sc in data.subcomponents:
                if sc.__class__ in ical2caldav:
                    return ical2caldav[sc.__class__]
        return AsyncCalendarObjectResource

    async def object_by_uid(
        self,
        uid: str,
        comp_filter=None,
        comp_class=None,
    ):
        """
        Get one event from the calendar by UID.
        """
        from caldav.search import CalDAVSearcher

        searcher = CalDAVSearcher(comp_class=comp_class)
        searcher.add_property_filter("uid", uid, "==")
        items_found = await searcher.async_search(
            self, xml=comp_filter, _hacks="insist", post_filter=True
        )

        if not items_found:
            raise error.NotFoundError("%s not found on server" % uid)
        error.assert_(len(items_found) == 1)
        return items_found[0]

    async def event_by_uid(self, uid: str):
        """Returns the event with the given uid"""
        return await self.object_by_uid(uid, comp_filter=cdav.CompFilter("VEVENT"))

    async def todo_by_uid(self, uid: str):
        """Returns the task with the given uid"""
        return await self.object_by_uid(uid, comp_filter=cdav.CompFilter("VTODO"))

    async def journal_by_uid(self, uid: str):
        """Returns the journal with the given uid"""
        return await self.object_by_uid(uid, comp_filter=cdav.CompFilter("VJOURNAL"))

    def _use_or_create_ics(self, ical, objtype, **ical_data):
        """Create or use an ical object."""
        from caldav.lib import vcal
        from caldav.lib.python_utilities import to_wire

        if ical_data or (
            (isinstance(ical, str) or isinstance(ical, bytes))
            and b"BEGIN:VCALENDAR" not in to_wire(ical)
        ):
            if ical and "ical_fragment" not in ical_data:
                ical_data["ical_fragment"] = ical
            return vcal.create_ical(objtype=objtype, **ical_data)
        return ical

    async def save_object(
        self,
        objclass,
        ical=None,
        no_overwrite=False,
        no_create=False,
        **ical_data,
    ):
        """Add a new object to the calendar.

        Args:
          objclass: AsyncEvent, AsyncTodo, AsyncJournal
          ical: ical object (text, icalendar or vobject instance)
          no_overwrite: existing calendar objects should not be overwritten
          no_create: don't create a new object
        """
        o = objclass(
            self.client,
            data=self._use_or_create_ics(
                ical,
                objtype=f"V{objclass.__name__.replace('Async', '').upper()}",
                **ical_data,
            ),
            parent=self,
        )
        o = await o.save(no_overwrite=no_overwrite, no_create=no_create)
        return o

    async def save_event(
        self, ical=None, no_overwrite=False, no_create=False, **ical_data
    ):
        """Save an event to the calendar."""
        from caldav._async.calendarobjectresource import AsyncEvent

        return await self.save_object(
            AsyncEvent, ical, no_overwrite, no_create, **ical_data
        )

    async def save_todo(
        self, ical=None, no_overwrite=False, no_create=False, **ical_data
    ):
        """Save a todo to the calendar."""
        from caldav._async.calendarobjectresource import AsyncTodo

        return await self.save_object(
            AsyncTodo, ical, no_overwrite, no_create, **ical_data
        )

    async def save_journal(
        self, ical=None, no_overwrite=False, no_create=False, **ical_data
    ):
        """Save a journal entry to the calendar."""
        from caldav._async.calendarobjectresource import AsyncJournal

        return await self.save_object(
            AsyncJournal, ical, no_overwrite, no_create, **ical_data
        )


class AsyncScheduleMailbox(AsyncCalendar):
    """
    RFC6638 defines an inbox and an outbox for handling event scheduling.
    """

    def __init__(
        self,
        client: Optional["AsyncDAVClient"] = None,
        principal: Optional[AsyncPrincipal] = None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
    ) -> None:
        super(AsyncScheduleMailbox, self).__init__(client=client, url=url)
        self._items = None
        self._principal = principal
        if not client and principal:
            self.client = principal.client

    async def _ensure_url(self) -> None:
        """Ensure the URL is set by querying the principal if needed."""
        if self.url is not None:
            return

        principal = self._principal
        if not principal and self.client:
            principal = await self.client.principal()

        if principal is None:
            raise ValueError("Unexpected value None for principal")

        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        self.url = principal.url
        try:
            prop_url = await self.get_property(self.findprop())
            self.url = self.client.url.join(URL(prop_url))
        except:
            logging.error("something bad happened", exc_info=True)
            error.assert_(await self.client.check_scheduling_support())
            self.url = None
            raise error.NotFoundError(
                "principal has no %s.  %s" % (str(self.findprop()), error.ERR_FRAGMENT)
            )


class AsyncScheduleInbox(AsyncScheduleMailbox):
    findprop = cdav.ScheduleInboxURL


class AsyncScheduleOutbox(AsyncScheduleMailbox):
    findprop = cdav.ScheduleOutboxURL
