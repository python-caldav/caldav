#!/usr/bin/env python
"""
Sync collection classes - thin wrappers around async implementations.

This provides backward-compatible synchronous API.
"""
import sys
from typing import Any
from typing import List
from typing import Optional
from typing import Union
from urllib.parse import ParseResult
from urllib.parse import SplitResult

import anyio

from caldav._async.collection import AsyncCalendar
from caldav._async.collection import AsyncCalendarSet
from caldav._async.collection import AsyncPrincipal
from caldav._async.collection import AsyncScheduleInbox
from caldav._async.collection import AsyncScheduleMailbox
from caldav._async.collection import AsyncScheduleOutbox
from caldav._async.davobject import AsyncDAVObject
from caldav.lib.url import URL

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


def _run_sync(async_fn, *args, **kwargs):
    """Execute an async function synchronously."""

    async def _wrapper():
        return await async_fn(*args, **kwargs)

    return anyio.run(_wrapper)


class DAVObject:
    """Sync DAVObject - thin wrapper around AsyncDAVObject."""

    def __init__(self, client=None, url=None, parent=None, **kwargs):
        # Get the async client if we have a sync client
        async_client = client._async if hasattr(client, "_async") else client
        async_parent = parent._async if hasattr(parent, "_async") else parent
        self._async = AsyncDAVObject(
            client=async_client, url=url, parent=async_parent, **kwargs
        )
        self._sync_client = client
        self._sync_parent = parent

    @property
    def client(self):
        return self._sync_client

    @property
    def parent(self):
        return self._sync_parent

    @property
    def url(self):
        return self._async.url

    @url.setter
    def url(self, value):
        self._async.url = value

    @property
    def id(self):
        return self._async.id

    @id.setter
    def id(self, value):
        self._async.id = value

    @property
    def name(self):
        return self._async.name

    @property
    def props(self):
        return self._async.props

    def children(self, type=None):
        return _run_sync(self._async.children, type)

    def get_property(self, prop, use_cached=False, **passthrough):
        return _run_sync(self._async.get_property, prop, use_cached, **passthrough)

    def get_properties(
        self, props=None, depth=0, parse_response_xml=True, parse_props=True
    ):
        return _run_sync(
            self._async.get_properties, props, depth, parse_response_xml, parse_props
        )

    def set_properties(self, props=None):
        _run_sync(self._async.set_properties, props)
        return self

    def save(self):
        _run_sync(self._async.save)
        return self

    def delete(self):
        _run_sync(self._async.delete)

    def get_display_name(self):
        return _run_sync(self._async.get_display_name)


class CalendarSet(DAVObject):
    """Sync CalendarSet - thin wrapper around AsyncCalendarSet."""

    def __init__(self, client=None, url=None, parent=None, **kwargs):
        async_client = client._async if hasattr(client, "_async") else client
        async_parent = parent._async if hasattr(parent, "_async") else parent
        self._async = AsyncCalendarSet(
            client=async_client, url=url, parent=async_parent, **kwargs
        )
        self._sync_client = client
        self._sync_parent = parent

    def calendars(self) -> List["Calendar"]:
        async_cals = _run_sync(self._async.calendars)
        return [Calendar._from_async(cal, self._sync_client) for cal in async_cals]

    def make_calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        supported_calendar_component_set: Optional[Any] = None,
        method=None,
    ) -> "Calendar":
        async_cal = _run_sync(
            self._async.make_calendar,
            name,
            cal_id,
            supported_calendar_component_set,
            method,
        )
        return Calendar._from_async(async_cal, self._sync_client)

    def calendar(
        self, name: Optional[str] = None, cal_id: Optional[str] = None
    ) -> "Calendar":
        async_cal = _run_sync(self._async.calendar, name, cal_id)
        return Calendar._from_async(async_cal, self._sync_client)


class Principal(DAVObject):
    """Sync Principal - thin wrapper around AsyncPrincipal."""

    def __init__(
        self,
        client=None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        calendar_home_set: URL = None,
        **kwargs,
    ):
        async_client = client._async if hasattr(client, "_async") else client
        self._async = AsyncPrincipal(
            client=async_client, url=url, calendar_home_set=calendar_home_set, **kwargs
        )
        self._sync_client = client
        self._sync_parent = None

    def make_calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        supported_calendar_component_set: Optional[Any] = None,
        method=None,
    ) -> "Calendar":
        async_cal = _run_sync(
            self._async.make_calendar,
            name,
            cal_id,
            supported_calendar_component_set,
            method,
        )
        return Calendar._from_async(async_cal, self._sync_client)

    def calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        cal_url: Optional[str] = None,
    ) -> "Calendar":
        async_cal = _run_sync(self._async.calendar, name, cal_id, cal_url)
        return Calendar._from_async(async_cal, self._sync_client)

    def calendars(self) -> List["Calendar"]:
        async_cals = _run_sync(self._async.calendars)
        return [Calendar._from_async(cal, self._sync_client) for cal in async_cals]

    def get_vcal_address(self):
        return _run_sync(self._async.get_vcal_address)

    @property
    def calendar_home_set(self):
        async_home = _run_sync(self._async.get_calendar_home_set)
        sync_home = CalendarSet.__new__(CalendarSet)
        sync_home._async = async_home
        sync_home._sync_client = self._sync_client
        sync_home._sync_parent = self
        return sync_home

    def freebusy_request(self, dtstart, dtend, attendees):
        return _run_sync(self._async.freebusy_request, dtstart, dtend, attendees)

    def calendar_user_address_set(self):
        return _run_sync(self._async.calendar_user_address_set)

    def schedule_inbox(self):
        async_inbox = _run_sync(self._async.schedule_inbox)
        sync_inbox = ScheduleInbox.__new__(ScheduleInbox)
        sync_inbox._async = async_inbox
        sync_inbox._sync_client = self._sync_client
        sync_inbox._sync_parent = self
        return sync_inbox

    def schedule_outbox(self):
        async_outbox = _run_sync(self._async.schedule_outbox)
        sync_outbox = ScheduleOutbox.__new__(ScheduleOutbox)
        sync_outbox._async = async_outbox
        sync_outbox._sync_client = self._sync_client
        sync_outbox._sync_parent = self
        return sync_outbox


class Calendar(DAVObject):
    """Sync Calendar - thin wrapper around AsyncCalendar."""

    def __init__(self, client=None, url=None, parent=None, **kwargs):
        async_client = client._async if hasattr(client, "_async") else client
        async_parent = parent._async if hasattr(parent, "_async") else parent
        self._async = AsyncCalendar(
            client=async_client, url=url, parent=async_parent, **kwargs
        )
        self._sync_client = client
        self._sync_parent = parent

    @classmethod
    def _from_async(cls, async_cal, sync_client):
        """Create a sync Calendar from an async one."""
        sync_cal = cls.__new__(cls)
        sync_cal._async = async_cal
        sync_cal._sync_client = sync_client
        sync_cal._sync_parent = None
        return sync_cal

    def save(self, method=None) -> Self:
        _run_sync(self._async.save, method)
        return self

    def get_supported_components(self):
        return _run_sync(self._async.get_supported_components)

    def search(self, **kwargs):
        from caldav._sync.calendarobjectresource import (
            CalendarObjectResource,
            Event,
            Todo,
            Journal,
            FreeBusy,
        )

        async_results = _run_sync(self._async.search, **kwargs)
        # Wrap results in sync classes
        results = []
        for obj in async_results:
            cls_name = obj.__class__.__name__.replace("Async", "")
            if cls_name == "Event":
                sync_obj = Event._from_async(obj, self._sync_client, self)
            elif cls_name == "Todo":
                sync_obj = Todo._from_async(obj, self._sync_client, self)
            elif cls_name == "Journal":
                sync_obj = Journal._from_async(obj, self._sync_client, self)
            elif cls_name == "FreeBusy":
                sync_obj = FreeBusy._from_async(obj, self._sync_client, self)
            else:
                sync_obj = CalendarObjectResource._from_async(
                    obj, self._sync_client, self
                )
            results.append(sync_obj)
        return results

    def events(self):
        from caldav._sync.calendarobjectresource import Event

        async_events = _run_sync(self._async.events)
        return [Event._from_async(e, self._sync_client, self) for e in async_events]

    def todos(
        self, sort_keys=("due", "priority"), include_completed=False, sort_key=None
    ):
        from caldav._sync.calendarobjectresource import Todo

        async_todos = _run_sync(
            self._async.todos, sort_keys, include_completed, sort_key
        )
        return [Todo._from_async(t, self._sync_client, self) for t in async_todos]

    def journals(self):
        from caldav._sync.calendarobjectresource import Journal

        async_journals = _run_sync(self._async.journals)
        return [Journal._from_async(j, self._sync_client, self) for j in async_journals]

    def freebusy_request(self, start, end):
        from caldav._sync.calendarobjectresource import FreeBusy

        async_fb = _run_sync(self._async.freebusy_request, start, end)
        return FreeBusy._from_async(async_fb, self._sync_client, self)

    def object_by_uid(self, uid, comp_filter=None, comp_class=None):
        from caldav._sync.calendarobjectresource import CalendarObjectResource

        async_obj = _run_sync(self._async.object_by_uid, uid, comp_filter, comp_class)
        return CalendarObjectResource._from_async(async_obj, self._sync_client, self)

    def event_by_uid(self, uid):
        from caldav._sync.calendarobjectresource import Event

        async_event = _run_sync(self._async.event_by_uid, uid)
        return Event._from_async(async_event, self._sync_client, self)

    def todo_by_uid(self, uid):
        from caldav._sync.calendarobjectresource import Todo

        async_todo = _run_sync(self._async.todo_by_uid, uid)
        return Todo._from_async(async_todo, self._sync_client, self)

    def journal_by_uid(self, uid):
        from caldav._sync.calendarobjectresource import Journal

        async_journal = _run_sync(self._async.journal_by_uid, uid)
        return Journal._from_async(async_journal, self._sync_client, self)

    def save_event(self, ical=None, no_overwrite=False, no_create=False, **ical_data):
        from caldav._sync.calendarobjectresource import Event

        # This needs to delegate to the original sync logic for now
        # as the async version doesn't have save_event yet
        raise NotImplementedError("save_event not yet implemented in async")

    def save_todo(self, ical=None, no_overwrite=False, no_create=False, **ical_data):
        from caldav._sync.calendarobjectresource import Todo

        raise NotImplementedError("save_todo not yet implemented in async")

    def save_journal(self, ical=None, no_overwrite=False, no_create=False, **ical_data):
        from caldav._sync.calendarobjectresource import Journal

        raise NotImplementedError("save_journal not yet implemented in async")


class ScheduleMailbox(Calendar):
    """Sync ScheduleMailbox - thin wrapper around AsyncScheduleMailbox."""

    def __init__(self, client=None, principal=None, url=None):
        async_client = client._async if client and hasattr(client, "_async") else client
        async_principal = (
            principal._async
            if principal and hasattr(principal, "_async")
            else principal
        )
        self._async = AsyncScheduleMailbox(
            client=async_client, principal=async_principal, url=url
        )
        self._sync_client = client
        self._sync_parent = principal


class ScheduleInbox(ScheduleMailbox):
    """Sync ScheduleInbox."""

    def __init__(self, client=None, principal=None, url=None):
        async_client = client._async if client and hasattr(client, "_async") else client
        async_principal = (
            principal._async
            if principal and hasattr(principal, "_async")
            else principal
        )
        self._async = AsyncScheduleInbox(
            client=async_client, principal=async_principal, url=url
        )
        self._sync_client = client
        self._sync_parent = principal


class ScheduleOutbox(ScheduleMailbox):
    """Sync ScheduleOutbox."""

    def __init__(self, client=None, principal=None, url=None):
        async_client = client._async if client and hasattr(client, "_async") else client
        async_principal = (
            principal._async
            if principal and hasattr(principal, "_async")
            else principal
        )
        self._async = AsyncScheduleOutbox(
            client=async_client, principal=async_principal, url=url
        )
        self._sync_client = client
        self._sync_parent = principal
