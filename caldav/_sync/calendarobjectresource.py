#!/usr/bin/env python
"""
Sync Calendar Object Resources - thin wrappers around async implementations.

This provides backward-compatible synchronous API.
"""
import sys
from datetime import datetime
from typing import Any
from typing import Optional
from typing import Union
from urllib.parse import ParseResult
from urllib.parse import SplitResult

import anyio

from caldav._async.calendarobjectresource import AsyncCalendarObjectResource
from caldav._async.calendarobjectresource import AsyncEvent
from caldav._async.calendarobjectresource import AsyncFreeBusy
from caldav._async.calendarobjectresource import AsyncJournal
from caldav._async.calendarobjectresource import AsyncTodo
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


class CalendarObjectResource:
    """Sync CalendarObjectResource - thin wrapper around AsyncCalendarObjectResource."""

    def __init__(
        self,
        client=None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        data: Optional[Any] = None,
        parent=None,
        id: Optional[Any] = None,
        props: Optional[Any] = None,
    ):
        async_client = client._async if client and hasattr(client, "_async") else client
        async_parent = parent._async if parent and hasattr(parent, "_async") else parent
        self._async = AsyncCalendarObjectResource(
            client=async_client,
            url=url,
            data=data,
            parent=async_parent,
            id=id,
            props=props,
        )
        self._sync_client = client
        self._sync_parent = parent

    @classmethod
    def _from_async(cls, async_obj, sync_client, sync_parent=None):
        """Create a sync object from an async one."""
        sync_obj = cls.__new__(cls)
        sync_obj._async = async_obj
        sync_obj._sync_client = sync_client
        sync_obj._sync_parent = sync_parent
        return sync_obj

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
    def props(self):
        return self._async.props

    @property
    def data(self):
        return self._async.data

    @data.setter
    def data(self, value):
        self._async.data = value

    @property
    def wire_data(self):
        return self._async.wire_data

    @property
    def icalendar_instance(self):
        return self._async.icalendar_instance

    @icalendar_instance.setter
    def icalendar_instance(self, value):
        self._async.icalendar_instance = value

    @property
    def icalendar_component(self):
        return self._async.icalendar_component

    @icalendar_component.setter
    def icalendar_component(self, value):
        self._async.icalendar_component = value

    @property
    def component(self):
        return self._async.component

    @property
    def vobject_instance(self):
        return self._async.vobject_instance

    @vobject_instance.setter
    def vobject_instance(self, value):
        self._async.vobject_instance = value

    def load(self, only_if_unloaded: bool = False) -> Self:
        _run_sync(self._async.load, only_if_unloaded)
        return self

    def save(
        self,
        no_overwrite: bool = False,
        no_create: bool = False,
        obj_type: Optional[str] = None,
        increase_seqno: bool = True,
        if_schedule_tag_match: bool = False,
        only_this_recurrence: bool = True,
        all_recurrences: bool = False,
    ) -> Self:
        _run_sync(
            self._async.save,
            no_overwrite,
            no_create,
            obj_type,
            increase_seqno,
            if_schedule_tag_match,
            only_this_recurrence,
            all_recurrences,
        )
        return self

    def delete(self):
        _run_sync(self._async.delete)

    def is_loaded(self):
        return self._async.is_loaded()

    def copy(self, keep_uid: bool = False, new_parent=None) -> Self:
        async_parent = (
            new_parent._async
            if new_parent and hasattr(new_parent, "_async")
            else new_parent
        )
        async_copy = self._async.copy(keep_uid, async_parent)
        return self._from_async(
            async_copy, self._sync_client, new_parent or self._sync_parent
        )

    def add_organizer(self):
        _run_sync(self._async.add_organizer)

    def add_attendee(self, attendee, no_default_parameters: bool = False, **parameters):
        self._async.add_attendee(attendee, no_default_parameters, **parameters)

    def get_duration(self):
        return self._async.get_duration()

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

    def get_display_name(self):
        return _run_sync(self._async.get_display_name)

    def __str__(self):
        return str(self._async)


class Event(CalendarObjectResource):
    """Sync Event - thin wrapper around AsyncEvent."""

    def __init__(
        self,
        client=None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        data: Optional[Any] = None,
        parent=None,
        id: Optional[Any] = None,
        props: Optional[Any] = None,
    ):
        async_client = client._async if client and hasattr(client, "_async") else client
        async_parent = parent._async if parent and hasattr(parent, "_async") else parent
        self._async = AsyncEvent(
            client=async_client,
            url=url,
            data=data,
            parent=async_parent,
            id=id,
            props=props,
        )
        self._sync_client = client
        self._sync_parent = parent


class Journal(CalendarObjectResource):
    """Sync Journal - thin wrapper around AsyncJournal."""

    def __init__(
        self,
        client=None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        data: Optional[Any] = None,
        parent=None,
        id: Optional[Any] = None,
        props: Optional[Any] = None,
    ):
        async_client = client._async if client and hasattr(client, "_async") else client
        async_parent = parent._async if parent and hasattr(parent, "_async") else parent
        self._async = AsyncJournal(
            client=async_client,
            url=url,
            data=data,
            parent=async_parent,
            id=id,
            props=props,
        )
        self._sync_client = client
        self._sync_parent = parent


class FreeBusy(CalendarObjectResource):
    """Sync FreeBusy - thin wrapper around AsyncFreeBusy."""

    def __init__(
        self,
        parent,
        data,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        id: Optional[Any] = None,
    ):
        async_parent = parent._async if parent and hasattr(parent, "_async") else parent
        self._async = AsyncFreeBusy(
            parent=async_parent,
            data=data,
            url=url,
            id=id,
        )
        self._sync_client = parent.client if hasattr(parent, "client") else None
        self._sync_parent = parent


class Todo(CalendarObjectResource):
    """Sync Todo - thin wrapper around AsyncTodo."""

    def __init__(
        self,
        client=None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        data: Optional[Any] = None,
        parent=None,
        id: Optional[Any] = None,
        props: Optional[Any] = None,
    ):
        async_client = client._async if client and hasattr(client, "_async") else client
        async_parent = parent._async if parent and hasattr(parent, "_async") else parent
        self._async = AsyncTodo(
            client=async_client,
            url=url,
            data=data,
            parent=async_parent,
            id=id,
            props=props,
        )
        self._sync_client = client
        self._sync_parent = parent

    def complete(
        self,
        completion_timestamp: Optional[datetime] = None,
        handle_rrule: bool = False,
        rrule_mode: str = "safe",
    ):
        _run_sync(self._async.complete, completion_timestamp, handle_rrule, rrule_mode)

    def uncomplete(self):
        _run_sync(self._async.uncomplete)

    def is_pending(self, i=None):
        return self._async.is_pending(i)

    def get_due(self):
        return self._async.get_due()

    get_dtend = get_due
