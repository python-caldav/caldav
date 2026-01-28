#!/usr/bin/env python
"""
Async-first CalDAV API.

This module provides async versions of the CalDAV client and objects.
Use this for new async code:

    from caldav import aio

    async with aio.AsyncDAVClient(url=..., username=..., password=...) as client:
        principal = await client.get_principal()
        calendars = await principal.get_calendars()
        for cal in calendars:
            events = await cal.get_events()

For backward-compatible sync code, continue using:

    from caldav import DAVClient

Note: As of the Sans-I/O refactoring (Phase 9), the domain objects (Calendar,
Principal, Event, etc.) are now dual-mode - they work with both sync and async
clients. When used with AsyncDAVClient, methods like calendars(), events(), etc.
return coroutines that must be awaited.

The Async* aliases are kept for backward compatibility but now point to the
unified dual-mode classes.
"""

# Import the async client (this is truly async)
from caldav.async_davclient import AsyncDAVClient, AsyncDAVResponse
from caldav.async_davclient import get_davclient as get_async_davclient
from caldav.calendarobjectresource import CalendarObjectResource, Event, FreeBusy, Journal, Todo
from caldav.collection import (
    Calendar,
    CalendarSet,
    Principal,
    ScheduleInbox,
    ScheduleMailbox,
    ScheduleOutbox,
)
from caldav.davobject import DAVObject

# Import unified dual-mode domain classes

# Create aliases for backward compatibility with code using Async* names
AsyncDAVObject = DAVObject
AsyncCalendarObjectResource = CalendarObjectResource
AsyncEvent = Event
AsyncTodo = Todo
AsyncJournal = Journal
AsyncFreeBusy = FreeBusy
AsyncCalendar = Calendar
AsyncCalendarSet = CalendarSet
AsyncPrincipal = Principal
AsyncScheduleMailbox = ScheduleMailbox
AsyncScheduleInbox = ScheduleInbox
AsyncScheduleOutbox = ScheduleOutbox

__all__ = [
    # Client
    "AsyncDAVClient",
    "AsyncDAVResponse",
    "get_async_davclient",
    # Base objects (unified dual-mode)
    "DAVObject",
    "CalendarObjectResource",
    # Calendar object types (unified dual-mode)
    "Event",
    "Todo",
    "Journal",
    "FreeBusy",
    # Collections (unified dual-mode)
    "Calendar",
    "CalendarSet",
    "Principal",
    # Scheduling (RFC6638)
    "ScheduleMailbox",
    "ScheduleInbox",
    "ScheduleOutbox",
    # Legacy aliases for backward compatibility
    "AsyncDAVObject",
    "AsyncCalendarObjectResource",
    "AsyncEvent",
    "AsyncTodo",
    "AsyncJournal",
    "AsyncFreeBusy",
    "AsyncCalendar",
    "AsyncCalendarSet",
    "AsyncPrincipal",
    "AsyncScheduleMailbox",
    "AsyncScheduleInbox",
    "AsyncScheduleOutbox",
]
