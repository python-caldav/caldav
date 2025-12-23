#!/usr/bin/env python
"""
Async collection classes for Phase 3.

This module provides async versions of Principal, CalendarSet, and Calendar.
For sync usage, see collection.py which wraps these async implementations.
"""

import logging
import sys
from typing import TYPE_CHECKING, Any, Optional, Union
from urllib.parse import ParseResult, SplitResult, quote

from caldav.async_davobject import AsyncDAVObject
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

    async def events(self) -> list["AsyncCalendarObjectResource"]:
        """
        Get all events in the calendar.

        Note: Full implementation requires search() which will be added later.
        """
        raise NotImplementedError(
            "AsyncCalendar.events() requires search() implementation. "
            "Use the sync API via caldav.Calendar for now."
        )

    async def search(self, **kwargs: Any) -> list["AsyncCalendarObjectResource"]:
        """
        Search for calendar objects.

        Note: Full implementation will be added in a future commit.
        """
        raise NotImplementedError(
            "AsyncCalendar.search() is not yet implemented. "
            "Use the sync API via caldav.Calendar for now."
        )


# Forward reference for type hints
AsyncCalendarObjectResource = Any  # Will be properly imported when needed


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
