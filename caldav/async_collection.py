#!/usr/bin/env python
"""
Async collection classes for Phase 3.

This module provides async versions of Principal, CalendarSet, and Calendar.
For sync usage, see collection.py which wraps these async implementations.
"""

import logging
import sys
import warnings
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Optional, Union
from urllib.parse import ParseResult, SplitResult, quote

from lxml import etree

from caldav.async_davobject import (
    AsyncCalendarObjectResource,
    AsyncDAVObject,
    AsyncEvent,
    AsyncJournal,
    AsyncTodo,
)
from caldav.elements import cdav
from caldav.lib import error
from caldav.lib.url import URL

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

if TYPE_CHECKING:
    from caldav.async_davclient import AsyncDAVClient

log = logging.getLogger("caldav")


class AsyncCalendarSet(AsyncDAVObject):
    """
    Async version of CalendarSet - a collection of calendars.
    """

    async def calendars(self) -> list["AsyncCalendar"]:
        """
        List all calendar collections in this set.

        Returns:
            List of AsyncCalendar objects
        """
        cals = []

        data = await self.children(cdav.Calendar.tag)
        for c_url, _c_type, c_name in data:
            try:
                cal_id = str(c_url).split("/")[-2]
                if not cal_id:
                    continue
            except Exception:
                log.error(f"Calendar {c_name} has unexpected url {c_url}")
                cal_id = None
            cals.append(AsyncCalendar(self.client, id=cal_id, url=c_url, parent=self, name=c_name))

        return cals

    async def make_calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        supported_calendar_component_set: Optional[Any] = None,
        method: Optional[str] = None,
    ) -> "AsyncCalendar":
        """
        Create a new calendar.

        Args:
            name: the display name of the new calendar
            cal_id: the uuid of the new calendar
            supported_calendar_component_set: what kind of objects
                (EVENT, VTODO, VFREEBUSY, VJOURNAL) the calendar should handle.
            method: 'mkcalendar' or 'mkcol' - usually auto-detected

        Returns:
            AsyncCalendar object
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
        Get a calendar by name or id.

        If it gets a cal_id but no name, it will not initiate any
        communication with the server.

        Args:
            name: return the calendar with this display name
            cal_id: return the calendar with this calendar id or URL

        Returns:
            AsyncCalendar object
        """
        if name and not cal_id:
            for calendar in await self.calendars():
                display_name = await calendar.get_display_name()
                if display_name == name:
                    return calendar
        if name and not cal_id:
            raise error.NotFoundError(f"No calendar with name {name} found under {self.url}")
        if not cal_id and not name:
            cals = await self.calendars()
            if not cals:
                raise error.NotFoundError("no calendars found")
            return cals[0]

        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        if cal_id is None:
            raise ValueError("Unexpected value None for cal_id")

        if str(URL.objectify(cal_id).canonical()).startswith(str(self.client.url.canonical())):
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
            url = self.url.join(quote(cal_id) + "/")

        return AsyncCalendar(self.client, name=name, parent=self, url=url, id=cal_id)


class AsyncPrincipal(AsyncDAVObject):
    """
    Async version of Principal - represents a DAV Principal.

    A principal MUST have a non-empty DAV:displayname property
    and a DAV:resourcetype property. Additionally, a principal MUST report
    the DAV:principal XML element in the value of the DAV:resourcetype property.
    """

    def __init__(
        self,
        client: Optional["AsyncDAVClient"] = None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        calendar_home_set: Optional[URL] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize an AsyncPrincipal.

        Note: Unlike the sync Principal, this constructor does NOT perform
        PROPFIND to discover the URL. Use the async class method
        `create()` or call `discover_url()` after construction.

        Args:
            client: An AsyncDAVClient instance
            url: The principal URL (if known)
            calendar_home_set: The calendar home set URL (if known)
        """
        self._calendar_home_set: Optional[AsyncCalendarSet] = None
        if calendar_home_set:
            self._calendar_home_set = AsyncCalendarSet(client=client, url=calendar_home_set)
        super().__init__(client=client, url=url, **kwargs)

    @classmethod
    async def create(
        cls,
        client: "AsyncDAVClient",
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        calendar_home_set: Optional[URL] = None,
    ) -> "AsyncPrincipal":
        """
        Create an AsyncPrincipal, discovering URL if not provided.

        This is the recommended way to create an AsyncPrincipal as it
        handles async URL discovery.

        Args:
            client: An AsyncDAVClient instance
            url: The principal URL (if known)
            calendar_home_set: The calendar home set URL (if known)

        Returns:
            AsyncPrincipal with URL discovered if not provided
        """
        from caldav.elements import dav

        principal = cls(client=client, url=url, calendar_home_set=calendar_home_set)

        if url is None:
            principal.url = client.url
            cup = await principal.get_property(dav.CurrentUserPrincipal())
            if cup is None:
                log.warning("calendar server lacking a feature:")
                log.warning("current-user-principal property not found")
                log.warning(f"assuming {client.url} is the principal URL")
            principal.url = client.url.join(URL.objectify(cup))

        return principal

    async def get_calendar_home_set(self) -> AsyncCalendarSet:
        """
        Get the calendar home set (async version of calendar_home_set property).

        Returns:
            AsyncCalendarSet object
        """
        if not self._calendar_home_set:
            calendar_home_set_url = await self.get_property(cdav.CalendarHomeSet())
            # Handle unquoted @ in URLs (owncloud quirk)
            if (
                calendar_home_set_url is not None
                and "@" in calendar_home_set_url
                and "://" not in calendar_home_set_url
            ):
                calendar_home_set_url = quote(calendar_home_set_url)

            if self.client is None:
                raise ValueError("Unexpected value None for self.client")

            sanitized_url = URL.objectify(calendar_home_set_url)
            if sanitized_url is not None:
                if sanitized_url.hostname and sanitized_url.hostname != self.client.url.hostname:
                    # icloud (and others?) having a load balanced system
                    self.client.url = sanitized_url

            self._calendar_home_set = AsyncCalendarSet(
                self.client, self.client.url.join(sanitized_url)
            )

        return self._calendar_home_set

    async def calendars(self) -> list["AsyncCalendar"]:
        """
        Return the principal's calendars.
        """
        calendar_home = await self.get_calendar_home_set()
        return await calendar_home.calendars()

    async def make_calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        supported_calendar_component_set: Optional[Any] = None,
        method: Optional[str] = None,
    ) -> "AsyncCalendar":
        """
        Convenience method, bypasses the calendar_home_set object.
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
        Get a calendar. Will not initiate any communication with the server
        if cal_url is provided.
        """
        if not cal_url:
            calendar_home = await self.get_calendar_home_set()
            return await calendar_home.calendar(name, cal_id)
        else:
            if self.client is None:
                raise ValueError("Unexpected value None for self.client")
            return AsyncCalendar(self.client, url=self.client.url.join(cal_url))

    async def calendar_user_address_set(self) -> list[Optional[str]]:
        """
        Get the calendar user address set (RFC6638).

        Returns:
            List of calendar user addresses, sorted by preference
        """
        from caldav.elements import dav

        _addresses = await self.get_property(cdav.CalendarUserAddressSet(), parse_props=False)

        if _addresses is None:
            raise error.NotFoundError("No calendar user addresses given from server")

        assert not [x for x in _addresses if x.tag != dav.Href().tag]
        addresses = list(_addresses)
        # Sort by preferred attribute (possibly iCloud-specific)
        addresses.sort(key=lambda x: -int(x.get("preferred", 0)))
        return [x.text for x in addresses]

    async def get_vcal_address(self) -> Any:
        """
        Returns the principal as an icalendar.vCalAddress object.
        """
        from icalendar import vCalAddress, vText

        cn = await self.get_display_name()
        ids = await self.calendar_user_address_set()
        cutype = await self.get_property(cdav.CalendarUserType())
        ret = vCalAddress(ids[0])
        ret.params["cn"] = vText(cn)
        ret.params["cutype"] = vText(cutype)
        return ret

    def schedule_inbox(self) -> "AsyncScheduleInbox":
        """
        Returns the schedule inbox (RFC6638).
        """
        return AsyncScheduleInbox(principal=self)

    def schedule_outbox(self) -> "AsyncScheduleOutbox":
        """
        Returns the schedule outbox (RFC6638).
        """
        return AsyncScheduleOutbox(principal=self)


class AsyncCalendar(AsyncDAVObject):
    """
    Async version of Calendar - represents a calendar collection.

    Refer to RFC 4791 for details:
    https://tools.ietf.org/html/rfc4791#section-5.3.1
    """

    def __init__(
        self,
        client: Optional["AsyncDAVClient"] = None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        parent: Optional["AsyncDAVObject"] = None,
        name: Optional[str] = None,
        id: Optional[str] = None,
        supported_calendar_component_set: Optional[Any] = None,
        **extra: Any,
    ) -> None:
        super().__init__(
            client=client,
            url=url,
            parent=parent,
            name=name,
            id=id,
            **extra,
        )
        self.supported_calendar_component_set = supported_calendar_component_set
        self.extra_init_options = extra

    async def _create(
        self,
        name: Optional[str] = None,
        id: Optional[str] = None,
        supported_calendar_component_set: Optional[Any] = None,
        method: Optional[str] = None,
    ) -> None:
        """
        Create a new calendar on the server.

        Args:
            name: Display name for the calendar
            id: UUID for the calendar (generated if not provided)
            supported_calendar_component_set: Component types (VEVENT, VTODO, etc.)
            method: 'mkcalendar' or 'mkcol' (auto-detected if not provided)
        """
        import uuid as uuid_mod

        from lxml import etree

        from caldav.elements import dav
        from caldav.lib.python_utilities import to_wire

        if id is None:
            id = str(uuid_mod.uuid1())
        self.id = id

        if method is None:
            if self.client:
                supported = self.client.features.is_supported("create-calendar", return_type=dict)
                if supported["support"] not in ("full", "fragile", "quirk"):
                    raise error.MkcalendarError(
                        "Creation of calendars (allegedly) not supported on this server"
                    )
                if supported["support"] == "quirk" and supported["behaviour"] == "mkcol-required":
                    method = "mkcol"
                else:
                    method = "mkcalendar"
            else:
                method = "mkcalendar"

        if self.parent is None or self.parent.url is None:
            raise ValueError("Calendar parent URL is required for creation")

        path = self.parent.url.join(id + "/")
        self.url = path

        # Build the XML body
        prop = dav.Prop()
        display_name = None
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

        set_elem = dav.Set() + prop
        mkcol = (dav.Mkcol() if method == "mkcol" else cdav.Mkcalendar()) + set_elem

        body = etree.tostring(mkcol.xmlelement(), encoding="utf-8", xml_declaration=True)

        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        # Execute the create request
        if method == "mkcol":
            response = await self.client.mkcol(str(path), to_wire(body))
        else:
            response = await self.client.mkcalendar(str(path), to_wire(body))

        if response.status not in (200, 201, 204):
            raise error.MkcalendarError(f"Failed to create calendar: {response.status}")

        # Try to set display name explicitly (some servers don't handle it in MKCALENDAR)
        if name and display_name:
            try:
                await self.set_properties([display_name])
            except Exception:
                try:
                    current_display_name = await self.get_display_name()
                    if current_display_name != name:
                        log.warning(
                            "calendar server does not support display name on calendar? Ignoring"
                        )
                except Exception:
                    log.warning(
                        "calendar server does not support display name on calendar? Ignoring",
                        exc_info=True,
                    )

    async def save(self, method: Optional[str] = None) -> Self:
        """
        Save the calendar. Creates it on the server if it doesn't exist yet.

        Returns:
            self
        """
        if self.url is None:
            await self._create(
                id=self.id,
                name=self.name,
                supported_calendar_component_set=self.supported_calendar_component_set,
                method=method,
            )
        return self

    async def delete(self) -> None:
        """
        Delete the calendar.

        Handles fragile servers with retry logic.
        """
        import asyncio

        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        quirk_info = self.client.features.is_supported("delete-calendar", dict)
        wipe = quirk_info["support"] in ("unsupported", "fragile")

        if quirk_info["support"] == "fragile":
            # Do some retries on deleting the calendar
            for _ in range(20):
                try:
                    await super().delete()
                except error.DeleteError:
                    pass
                try:
                    # Check if calendar still exists
                    await self.events()
                    await asyncio.sleep(0.3)
                except error.NotFoundError:
                    wipe = False
                    break

        if wipe:
            # Wipe all objects first
            async for obj in await self.search():
                await obj.delete()
        else:
            await super().delete()

    async def get_supported_components(self) -> list[Any]:
        """
        Get the list of component types supported by this calendar.

        Returns:
            List of component names (e.g., ['VEVENT', 'VTODO', 'VJOURNAL'])
        """
        from urllib.parse import unquote

        if self.url is None:
            raise ValueError("Unexpected value None for self.url")

        props = [cdav.SupportedCalendarComponentSet()]
        response = await self.get_properties(props, parse_response_xml=False)
        response_list = response.find_objects_and_props()
        prop = response_list[unquote(self.url.path)][cdav.SupportedCalendarComponentSet().tag]
        return [supported.get("name") for supported in prop]

    def _calendar_comp_class_by_data(self, data: Optional[str]) -> type:
        """
        Determine the async component class based on iCalendar data.

        Args:
            data: iCalendar text data

        Returns:
            AsyncEvent, AsyncTodo, AsyncJournal, or AsyncCalendarObjectResource
        """
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
        return AsyncCalendarObjectResource

    async def _request_report_build_resultlist(
        self,
        xml: Any,
        comp_class: Optional[type] = None,
        props: Optional[list[Any]] = None,
    ) -> tuple[Any, list[AsyncCalendarObjectResource]]:
        """
        Send a REPORT query and build a list of calendar objects from the response.

        Args:
            xml: XML query (string or element)
            comp_class: Component class to use for results (auto-detected if None)
            props: Additional properties to request

        Returns:
            Tuple of (response, list of calendar objects)
        """
        if self.url is None:
            raise ValueError("Unexpected value None for self.url")
        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        # Build XML body
        if hasattr(xml, "xmlelement"):
            body = etree.tostring(
                xml.xmlelement(),
                encoding="utf-8",
                xml_declaration=True,
            )
        elif isinstance(xml, str):
            body = xml.encode("utf-8") if isinstance(xml, str) else xml
        else:
            body = etree.tostring(xml, encoding="utf-8", xml_declaration=True)

        # Send REPORT request
        response = await self.client.report(str(self.url), body, depth=1)
        if response.status == 404:
            raise error.NotFoundError(f"{response.status} {response.reason}")
        if response.status >= 400:
            raise error.ReportError(f"{response.status} {response.reason}")

        # Build result list from response
        matches = []
        if props is None:
            props_ = [cdav.CalendarData()]
        else:
            props_ = [cdav.CalendarData()] + props

        results = response.expand_simple_props(props_)
        for r in results:
            pdata = results[r]
            cdata = None
            comp_class_ = comp_class

            if cdav.CalendarData.tag in pdata:
                cdata = pdata.pop(cdav.CalendarData.tag)
                if comp_class_ is None:
                    comp_class_ = self._calendar_comp_class_by_data(cdata)

            if comp_class_ is None:
                comp_class_ = AsyncCalendarObjectResource

            url = URL(r)
            if url.hostname is None:
                url = quote(r)

            # Skip if the URL matches the calendar URL itself (iCloud quirk)
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
        xml: Optional[str] = None,
        server_expand: bool = False,
        split_expanded: bool = True,
        sort_reverse: bool = False,
        props: Optional[list[Any]] = None,
        filters: Any = None,
        post_filter: Optional[bool] = None,
        _hacks: Optional[str] = None,
        **searchargs: Any,
    ) -> list[AsyncCalendarObjectResource]:
        """
        Search for calendar objects.

        This async method uses CalDAVSearcher.async_search() which shares all
        the compatibility logic with the sync version.

        Args:
            xml: Raw XML query to send (overrides other filters)
            server_expand: Request server-side recurrence expansion
            split_expanded: Split expanded recurrences into separate objects
            sort_reverse: Reverse sort order
            props: Additional CalDAV properties to request
            filters: Additional filters (lxml elements)
            post_filter: Force client-side filtering (True/False/None)
            _hacks: Internal compatibility flags
            **searchargs: Search parameters (event, todo, journal, start, end,
                         summary, uid, category, expand, include_completed, etc.)

        Returns:
            List of AsyncCalendarObjectResource objects (AsyncEvent, AsyncTodo, etc.)
        """
        from caldav.search import CalDAVSearcher

        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        # Handle deprecated expand parameter
        if searchargs.get("expand", True) not in (True, False):
            warnings.warn(
                "in cal.search(), expand should be a bool",
                DeprecationWarning,
                stacklevel=2,
            )
            if searchargs["expand"] == "client":
                searchargs["expand"] = True
            if searchargs["expand"] == "server":
                server_expand = True
                searchargs["expand"] = False

        # Build CalDAVSearcher and configure it
        my_searcher = CalDAVSearcher()
        for key in searchargs:
            assert key[0] != "_"
            alias = key
            if key == "class_":
                alias = "class"
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
                my_searcher.add_property_filter(alias[3:], searchargs[key], operator="undef")
            else:
                my_searcher.add_property_filter(alias, searchargs[key])

        if not xml and filters:
            xml = filters

        # Use CalDAVSearcher.async_search() which has all the compatibility logic
        return await my_searcher.async_search(
            self,
            server_expand=server_expand,
            split_expanded=split_expanded,
            props=props,
            xml=xml,
            post_filter=post_filter,
            _hacks=_hacks,
        )

    async def events(self) -> list[AsyncEvent]:
        """
        Get all events in the calendar.

        Returns:
            List of AsyncEvent objects
        """
        return await self.search(event=True)

    async def todos(
        self,
        sort_keys: Sequence[str] = ("due", "priority"),
        include_completed: bool = False,
    ) -> list[AsyncTodo]:
        """
        Get todo items from the calendar.

        Args:
            sort_keys: Properties to sort by
            include_completed: Include completed todos

        Returns:
            List of AsyncTodo objects
        """
        return await self.search(
            todo=True, include_completed=include_completed, sort_keys=list(sort_keys)
        )

    async def journals(self) -> list[AsyncJournal]:
        """
        Get all journal entries in the calendar.

        Returns:
            List of AsyncJournal objects
        """
        return await self.search(journal=True)

    async def event_by_uid(self, uid: str) -> AsyncEvent:
        """
        Get an event by its UID.

        Args:
            uid: The UID of the event

        Returns:
            AsyncEvent object

        Raises:
            NotFoundError: If no event with that UID exists
        """
        results = await self.search(event=True, uid=uid)
        if not results:
            raise error.NotFoundError(f"No event with UID {uid}")
        return results[0]

    async def todo_by_uid(self, uid: str) -> AsyncTodo:
        """
        Get a todo by its UID.

        Args:
            uid: The UID of the todo

        Returns:
            AsyncTodo object

        Raises:
            NotFoundError: If no todo with that UID exists
        """
        results = await self.search(todo=True, uid=uid, include_completed=True)
        if not results:
            raise error.NotFoundError(f"No todo with UID {uid}")
        return results[0]

    async def journal_by_uid(self, uid: str) -> AsyncJournal:
        """
        Get a journal entry by its UID.

        Args:
            uid: The UID of the journal

        Returns:
            AsyncJournal object

        Raises:
            NotFoundError: If no journal with that UID exists
        """
        results = await self.search(journal=True, uid=uid)
        if not results:
            raise error.NotFoundError(f"No journal with UID {uid}")
        return results[0]

    async def object_by_uid(self, uid: str) -> AsyncCalendarObjectResource:
        """
        Get a calendar object by its UID (any type).

        Args:
            uid: The UID of the object

        Returns:
            AsyncCalendarObjectResource (could be Event, Todo, or Journal)

        Raises:
            NotFoundError: If no object with that UID exists
        """
        results = await self.search(uid=uid)
        if not results:
            raise error.NotFoundError(f"No object with UID {uid}")
        return results[0]

    def _use_or_create_ics(
        self, ical: Any, objtype: str, **ical_data: Any
    ) -> Any:
        """
        Create an iCalendar object from provided data or use existing one.

        Args:
            ical: Existing ical data (text, icalendar or vobject instance)
            objtype: Object type (VEVENT, VTODO, VJOURNAL)
            **ical_data: Properties to insert into the icalendar object

        Returns:
            iCalendar data
        """
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
        objclass: type,
        ical: Optional[Any] = None,
        no_overwrite: bool = False,
        no_create: bool = False,
        **ical_data: Any,
    ) -> AsyncCalendarObjectResource:
        """
        Add a new object to the calendar, with the given ical.

        Args:
            objclass: AsyncEvent, AsyncTodo, or AsyncJournal
            ical: ical object (text, icalendar or vobject instance)
            no_overwrite: existing calendar objects should not be overwritten
            no_create: don't create a new object, existing objects should be updated
            **ical_data: properties to be inserted into the icalendar object

        Returns:
            AsyncCalendarObjectResource (AsyncEvent, AsyncTodo, or AsyncJournal)
        """
        obj = objclass(
            self.client,
            data=self._use_or_create_ics(
                ical, objtype=f"V{objclass.__name__.replace('Async', '').upper()}", **ical_data
            ),
            parent=self,
        )
        return await obj.save(no_overwrite=no_overwrite, no_create=no_create)

    async def save_event(
        self,
        ical: Optional[Any] = None,
        no_overwrite: bool = False,
        no_create: bool = False,
        **ical_data: Any,
    ) -> AsyncEvent:
        """
        Save an event to the calendar.

        See save_object for full documentation.
        """
        return await self.save_object(
            AsyncEvent, ical, no_overwrite=no_overwrite, no_create=no_create, **ical_data
        )

    async def save_todo(
        self,
        ical: Optional[Any] = None,
        no_overwrite: bool = False,
        no_create: bool = False,
        **ical_data: Any,
    ) -> AsyncTodo:
        """
        Save a todo to the calendar.

        See save_object for full documentation.
        """
        return await self.save_object(
            AsyncTodo, ical, no_overwrite=no_overwrite, no_create=no_create, **ical_data
        )

    async def save_journal(
        self,
        ical: Optional[Any] = None,
        no_overwrite: bool = False,
        no_create: bool = False,
        **ical_data: Any,
    ) -> AsyncJournal:
        """
        Save a journal entry to the calendar.

        See save_object for full documentation.
        """
        return await self.save_object(
            AsyncJournal, ical, no_overwrite=no_overwrite, no_create=no_create, **ical_data
        )

    # Legacy aliases
    add_object = save_object
    add_event = save_event
    add_todo = save_todo
    add_journal = save_journal

    async def _multiget(
        self, event_urls: list[URL], raise_notfound: bool = False
    ) -> list[tuple[str, Optional[str]]]:
        """
        Get multiple events' data using calendar-multiget REPORT.

        Args:
            event_urls: List of URLs to fetch
            raise_notfound: Raise NotFoundError if any URL returns 404

        Returns:
            List of (url, data) tuples
        """
        from caldav.elements import dav
        from caldav.lib.python_utilities import to_wire

        if self.url is None:
            raise ValueError("Unexpected value None for self.url")
        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        prop = cdav.Prop() + cdav.CalendarData()
        root = (
            cdav.CalendarMultiGet()
            + prop
            + [dav.Href(value=u.path) for u in event_urls]
        )

        body = etree.tostring(
            root.xmlelement(), encoding="utf-8", xml_declaration=True
        )
        response = await self.client.report(str(self.url), to_wire(body), depth=1)

        if raise_notfound:
            for href in response.statuses:
                status = response.statuses[href]
                if status and "404" in status:
                    raise error.NotFoundError(f"Status {status} in {href}")

        results = response.expand_simple_props([cdav.CalendarData()])
        return [(r, results[r].get(cdav.CalendarData.tag)) for r in results]

    async def multiget(
        self, event_urls: list[URL], raise_notfound: bool = False
    ) -> list[AsyncCalendarObjectResource]:
        """
        Get multiple events' data using calendar-multiget REPORT.

        Args:
            event_urls: List of URLs to fetch
            raise_notfound: Raise NotFoundError if any URL returns 404

        Returns:
            List of AsyncCalendarObjectResource objects
        """
        results = await self._multiget(event_urls, raise_notfound=raise_notfound)
        objects = []
        for url, data in results:
            comp_class = self._calendar_comp_class_by_data(data)
            objects.append(
                comp_class(
                    self.client,
                    url=self.url.join(url),
                    data=data,
                    parent=self,
                )
            )
        return objects

    async def calendar_multiget(
        self, event_urls: list[URL], raise_notfound: bool = False
    ) -> list[AsyncCalendarObjectResource]:
        """
        Legacy alias for multiget.

        This is for backward compatibility. It may be removed in 3.0 or later.
        """
        return await self.multiget(event_urls, raise_notfound=raise_notfound)

    async def freebusy_request(
        self, start: Any, end: Any
    ) -> AsyncCalendarObjectResource:
        """
        Search the calendar for free/busy information.

        Args:
            start: Start datetime
            end: End datetime

        Returns:
            AsyncCalendarObjectResource containing free/busy data
        """
        from caldav.lib.python_utilities import to_wire

        if self.client is None:
            raise ValueError("Unexpected value None for self.client")
        if self.url is None:
            raise ValueError("Unexpected value None for self.url")

        root = cdav.FreeBusyQuery() + [cdav.TimeRange(start, end)]
        body = etree.tostring(
            root.xmlelement(), encoding="utf-8", xml_declaration=True
        )
        response = await self.client.report(str(self.url), to_wire(body), depth=1)

        # Return a FreeBusy-like object (using AsyncCalendarObjectResource for now)
        return AsyncCalendarObjectResource(
            self.client, url=self.url, data=response.raw, parent=self
        )

    async def event_by_url(
        self, href: Union[str, URL], data: Optional[str] = None
    ) -> AsyncEvent:
        """
        Get an event by its URL.

        Args:
            href: URL of the event
            data: Optional cached data

        Returns:
            AsyncEvent object
        """
        event = AsyncEvent(url=href, data=data, parent=self, client=self.client)
        return await event.load()

    async def objects(self) -> list[AsyncCalendarObjectResource]:
        """
        Get all objects in the calendar (events, todos, journals).

        Returns:
            List of AsyncCalendarObjectResource objects
        """
        return await self.search()


class AsyncScheduleMailbox(AsyncCalendar):
    """Base class for schedule inbox/outbox (RFC6638)."""

    def __init__(
        self,
        client: Optional["AsyncDAVClient"] = None,
        principal: Optional[AsyncPrincipal] = None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        **kwargs: Any,
    ) -> None:
        if client is None and principal is not None:
            client = principal.client
        super().__init__(client=client, url=url, **kwargs)
        self.principal = principal


class AsyncScheduleInbox(AsyncScheduleMailbox):
    """Schedule inbox (RFC6638) - stub for Phase 3."""

    pass


class AsyncScheduleOutbox(AsyncScheduleMailbox):
    """Schedule outbox (RFC6638) - stub for Phase 3."""

    pass
