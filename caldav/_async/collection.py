#!/usr/bin/env python
"""
Async collection classes - placeholder for Phase 3.

This module will contain AsyncPrincipal, AsyncCalendar, AsyncCalendarSet, etc.
For now, it provides minimal stubs to allow the HTTP layer to work.
"""
from typing import Optional

from caldav.lib.url import URL


class AsyncDAVObject:
    """Base class for async DAV objects - placeholder."""

    def __init__(self, client=None, url=None, parent=None, **kwargs):
        self.client = client
        self.url = URL.objectify(url) if url else None
        self.parent = parent


class AsyncPrincipal(AsyncDAVObject):
    """Async Principal - placeholder for Phase 3."""

    async def calendars(self):
        """Get calendars - to be implemented in Phase 3."""
        raise NotImplementedError("AsyncPrincipal.calendars() not yet implemented")


class AsyncCalendar(AsyncDAVObject):
    """Async Calendar - placeholder for Phase 3."""

    async def events(self):
        """Get events - to be implemented in Phase 3."""
        raise NotImplementedError("AsyncCalendar.events() not yet implemented")


class AsyncCalendarSet(AsyncDAVObject):
    """Async CalendarSet - placeholder for Phase 3."""

    pass
