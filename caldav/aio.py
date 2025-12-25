#!/usr/bin/env python
"""
Async-first CalDAV API.

This module provides async versions of the CalDAV client and objects.
Use this for new async code:

    from caldav import aio

    async with aio.AsyncDAVClient(url=..., username=..., password=...) as client:
        principal = await client.principal()
        calendars = await principal.calendars()
        for cal in calendars:
            events = await cal.events()

For backward-compatible sync code, continue using:

    from caldav import DAVClient
"""
# Re-export async components for convenience
from caldav.async_collection import (
    AsyncCalendar,
    AsyncCalendarSet,
    AsyncPrincipal,
    AsyncScheduleInbox,
    AsyncScheduleMailbox,
    AsyncScheduleOutbox,
)
from caldav.async_davclient import AsyncDAVClient, AsyncDAVResponse
from caldav.async_davclient import get_davclient as get_async_davclient
from caldav.async_davobject import (
    AsyncCalendarObjectResource,
    AsyncDAVObject,
    AsyncEvent,
    AsyncFreeBusy,
    AsyncJournal,
    AsyncTodo,
)

__all__ = [
    # Client
    "AsyncDAVClient",
    "AsyncDAVResponse",
    "get_async_davclient",
    # Base objects
    "AsyncDAVObject",
    "AsyncCalendarObjectResource",
    # Calendar object types
    "AsyncEvent",
    "AsyncTodo",
    "AsyncJournal",
    "AsyncFreeBusy",
    # Collections
    "AsyncCalendar",
    "AsyncCalendarSet",
    "AsyncPrincipal",
    # Scheduling (RFC6638)
    "AsyncScheduleMailbox",
    "AsyncScheduleInbox",
    "AsyncScheduleOutbox",
]
