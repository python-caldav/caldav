#!/usr/bin/env python
"""
Sync collection classes - placeholder for Phase 3.

This module will contain Principal, Calendar, CalendarSet, etc.
For now, it provides minimal stubs to allow the HTTP layer to work.
"""
from typing import Optional

import anyio

from caldav.lib.url import URL


class DAVObject:
    """Base class for sync DAV objects - placeholder."""

    def __init__(self, client=None, url=None, parent=None, **kwargs):
        self.client = client
        self.url = URL.objectify(url) if url else None
        self.parent = parent


class Principal(DAVObject):
    """Sync Principal - placeholder for Phase 3."""

    def calendars(self):
        """Get calendars - to be implemented in Phase 3."""
        raise NotImplementedError("Principal.calendars() not yet implemented")


class Calendar(DAVObject):
    """Sync Calendar - placeholder for Phase 3."""

    def events(self):
        """Get events - to be implemented in Phase 3."""
        raise NotImplementedError("Calendar.events() not yet implemented")


class CalendarSet(DAVObject):
    """Sync CalendarSet - placeholder for Phase 3."""

    pass
