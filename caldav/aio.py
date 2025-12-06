#!/usr/bin/env python
"""
Async CalDAV client API.

This module provides the async-first implementation of the CalDAV library.
Users who want to use async/await can import from here:

    from caldav.aio import AsyncDAVClient, AsyncCalendar, AsyncEvent

For synchronous usage, continue to use the main caldav module:

    from caldav import DAVClient
"""
from caldav._async.calendarobjectresource import AsyncCalendarObjectResource
from caldav._async.calendarobjectresource import AsyncEvent
from caldav._async.calendarobjectresource import AsyncFreeBusy
from caldav._async.calendarobjectresource import AsyncJournal
from caldav._async.calendarobjectresource import AsyncTodo
from caldav._async.collection import AsyncCalendar
from caldav._async.collection import AsyncCalendarSet
from caldav._async.collection import AsyncPrincipal
from caldav._async.collection import AsyncScheduleInbox
from caldav._async.collection import AsyncScheduleMailbox
from caldav._async.collection import AsyncScheduleOutbox
from caldav._async.davclient import AsyncDAVClient
from caldav._async.davclient import DAVResponse
from caldav._async.davclient import HTTPBearerAuth
from caldav._async.davobject import AsyncDAVObject

__all__ = [
    # Client
    "AsyncDAVClient",
    "DAVResponse",
    "HTTPBearerAuth",
    # Base
    "AsyncDAVObject",
    # Collections
    "AsyncCalendar",
    "AsyncCalendarSet",
    "AsyncPrincipal",
    "AsyncScheduleInbox",
    "AsyncScheduleMailbox",
    "AsyncScheduleOutbox",
    # Calendar objects
    "AsyncCalendarObjectResource",
    "AsyncEvent",
    "AsyncFreeBusy",
    "AsyncJournal",
    "AsyncTodo",
]
