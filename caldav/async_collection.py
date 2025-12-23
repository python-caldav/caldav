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
    """Stub for Phase 3: Async Principal implementation."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError(
            "AsyncPrincipal is not yet implemented. "
            "This is a Phase 3 feature (async collections). "
            "For now, use the sync API via caldav.Principal"
        )


class AsyncCalendar(AsyncDAVObject):
    """Stub for Phase 3: Async Calendar implementation."""

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

    async def save(self, method: Optional[str] = None) -> Self:
        """Stub: Calendar save not yet implemented."""
        raise NotImplementedError(
            "AsyncCalendar.save() is not yet implemented. "
            "This is a Phase 3 feature (async collections). "
            "For now, use the sync API via caldav.Calendar"
        )
