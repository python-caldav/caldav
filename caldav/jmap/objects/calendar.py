"""
JMAP Calendar object.

Represents a JMAP Calendar resource as returned by ``Calendar/get``.
Properties are defined in the JMAP Calendars specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from caldav.jmap.async_client import AsyncJMAPClient
    from caldav.jmap.client import JMAPClient


@dataclass
class JMAPCalendar:
    """A JMAP Calendar object.

    Attributes:
        id: Server-assigned calendar identifier.
        name: Display name of the calendar.
        description: Optional longer description.
        color: Optional CSS color string (e.g. ``"#ff0000"``).
        is_subscribed: Whether the user is subscribed to this calendar.
        my_rights: Dict of right names → bool for the current user.
        sort_order: Hint for display ordering (lower = first).
        is_visible: Whether the calendar should be displayed.
    """

    id: str
    name: str
    description: str | None = None
    color: str | None = None
    is_subscribed: bool = True
    my_rights: dict = field(default_factory=dict)
    sort_order: int = 0
    is_visible: bool = True

    # Injected by JMAPClient.get_calendars() / AsyncJMAPClient.get_calendars()
    _client: JMAPClient | AsyncJMAPClient | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _is_async: bool = field(default=False, init=False, repr=False, compare=False)

    @classmethod
    def from_jmap(cls, data: dict) -> JMAPCalendar:
        """Construct a JMAPCalendar from a raw JMAP Calendar JSON dict.

        Unknown keys in ``data`` are silently ignored so that forward
        compatibility is maintained as the spec evolves.
        """
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            color=data.get("color"),
            is_subscribed=data.get("isSubscribed", True),
            my_rights=data.get("myRights", {}),
            sort_order=data.get("sortOrder", 0),
            is_visible=data.get("isVisible", True),
        )

    def to_jmap(self) -> dict:
        """Serialise to a JMAP Calendar JSON dict for ``Calendar/set``.

        ``id`` and ``myRights`` are intentionally excluded — both are
        server-set and must not appear in create or update payloads.
        Optional fields are included only when they hold a non-default value.
        """
        d: dict = {
            "name": self.name,
            "isSubscribed": self.is_subscribed,
            "sortOrder": self.sort_order,
            "isVisible": self.is_visible,
        }
        if self.description is not None:
            d["description"] = self.description
        if self.color is not None:
            d["color"] = self.color
        return d

    def search(self, **searchargs) -> list[str]:
        """Search for calendar objects and return them as iCalendar strings.

        Mirrors :meth:`caldav.collection.Calendar.search`. When called on an
        async-backed calendar, returns a coroutine that must be awaited.

        Accepted keyword arguments (all optional):

        - ``event`` (bool): search for events (VEVENT components).
        - ``todo`` (bool): search for tasks (VTODO). Note: requires server
          JMAP Task capability; raises :class:`NotImplementedError` if absent.
        - ``start`` (datetime or str): only events ending after this time
          (maps to JMAP ``after`` filter).
        - ``end`` (datetime or str): only events starting before this time
          (maps to JMAP ``before`` filter).
        - ``text`` (str): free-text search across title, description,
          locations, and participants.

        Unknown searchargs keys are silently ignored for forward compatibility.

        Returns:
            List of VCALENDAR strings for all matching objects.
        """
        if self._is_async:
            return self._async_search(**searchargs)
        start = searchargs.get("start")
        end = searchargs.get("end")
        if isinstance(start, datetime):
            start = start.isoformat()
        if isinstance(end, datetime):
            end = end.isoformat()
        return self._client._search(
            calendar_id=self.id,
            start=start,
            end=end,
            text=searchargs.get("text"),
        )

    async def _async_search(self, **searchargs) -> list[str]:
        start = searchargs.get("start")
        end = searchargs.get("end")
        if isinstance(start, datetime):
            start = start.isoformat()
        if isinstance(end, datetime):
            end = end.isoformat()
        return await self._client._search(
            calendar_id=self.id,
            start=start,
            end=end,
            text=searchargs.get("text"),
        )

    def get_object_by_uid(self, uid: str, comp_class=None) -> str:
        """Get a calendar object by its iCalendar UID.

        Mirrors :meth:`caldav.collection.Calendar.get_object_by_uid`. When
        called on an async-backed calendar, returns a coroutine that must be
        awaited.

        Args:
            uid: The iCalendar UID to search for.
            comp_class: Accepted for API compatibility with the CalDAV interface;
                JMAP ``CalendarEvent/query`` has no native component-type filter,
                so this argument is currently ignored.

        Returns:
            A VCALENDAR string for the matching object.

        Raises:
            JMAPMethodError: If no object with this UID is found.
        """
        if self._is_async:
            return self._async_get_object_by_uid(uid)
        return self._client._get_object_by_uid(uid, calendar_id=self.id)

    async def _async_get_object_by_uid(self, uid: str) -> str:
        return await self._client._get_object_by_uid(uid, calendar_id=self.id)

    def add_event(self, ical_str: str) -> str:
        """Add an event to this calendar from an iCalendar string.

        Mirrors :meth:`caldav.collection.Calendar.add_event`. When called on
        an async-backed calendar, returns a coroutine that must be awaited.

        Args:
            ical_str: A VCALENDAR string representing the event.

        Returns:
            The server-assigned JMAP event ID.

        Raises:
            JMAPMethodError: If the server rejects the create request.
        """
        if self._is_async:
            return self._async_add_event(ical_str)
        return self._client.create_event(self.id, ical_str)

    async def _async_add_event(self, ical_str: str) -> str:
        return await self._client.create_event(self.id, ical_str)
