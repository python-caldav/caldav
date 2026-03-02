"""
JMAP calendar resource object.

Wraps a raw JSCalendar CalendarEvent dict with the same minimal interface
as :class:`caldav.calendarobjectresource.CalendarObjectResource`:
``.id``, ``.parent``, :meth:`get_data`, :meth:`get_icalendar_instance`,
:meth:`edit_icalendar_instance`, and :meth:`save`.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import icalendar

from caldav.jmap.convert import jscal_to_ical
from caldav.jmap.error import JMAPMethodError

if TYPE_CHECKING:
    from caldav.jmap.objects.calendar import JMAPCalendar


@dataclass
class JMAPCalendarObject:
    """Thin wrapper around a raw JSCalendar CalendarEvent dict.

    Stores the server's JSON response as-is.  No JMAP field names are mapped
    to typed attributes — callers work with the dict directly via
    :meth:`get_data`, or convert to iCalendar via :meth:`get_icalendar_instance`.

    Attributes:
        data: Raw JSCalendar CalendarEvent dict as returned by ``CalendarEvent/get``.
        parent: The :class:`~caldav.jmap.objects.calendar.JMAPCalendar` this object
            belongs to, or ``None`` when fetched without a calendar context
            (e.g. via :meth:`~caldav.jmap.client.JMAPClient.get_event`).
    """

    data: dict
    parent: JMAPCalendar | None

    _ical_cache: icalendar.Calendar | None = field(
        default=None, init=False, repr=False, compare=False
    )

    @property
    def id(self) -> str:
        """Server-assigned JMAP event ID."""
        return self.data["id"]

    def get_data(self) -> dict:
        """Return the raw JSCalendar dict as returned by ``CalendarEvent/get``."""
        return self.data

    def get_icalendar_instance(self) -> icalendar.Calendar:
        """Return an :class:`icalendar.Calendar` for this object.

        The result is cached after the first conversion.  Treat it as
        read-only; use :meth:`edit_icalendar_instance` to make and persist
        changes.
        """
        if self._ical_cache is None:
            self._ical_cache = icalendar.Calendar.from_ical(jscal_to_ical(self.data))
        return self._ical_cache

    @contextmanager
    def edit_icalendar_instance(self):
        """Borrow an editable :class:`icalendar.Calendar` for this object.

        Yields the cached :class:`icalendar.Calendar` for in-place editing.
        Call :meth:`save` after the ``with`` block to persist changes to the server.

        Note: :meth:`save` is sync-only.  Async-backed calendars cannot use
        this path yet.

        Example::

            with obj.edit_icalendar_instance() as cal:
                cal.subcomponents[0]["SUMMARY"] = vText("New title")
            obj.save()
        """
        cal = self.get_icalendar_instance()
        yield cal

    def save(self) -> None:
        """Persist changes made via :meth:`edit_icalendar_instance` to the server.

        Serialises the (possibly edited) icalendar object back to an iCalendar
        string and calls ``update_event()`` on the parent calendar's client.

        Raises:
            JMAPMethodError: If no parent calendar is set (``parent`` is ``None``).
            RuntimeError: If called on an async-backed calendar.
        """
        if self.parent is None:
            raise JMAPMethodError(url="N/A", reason="Cannot save: no parent calendar is set")
        if self.parent._is_async:
            raise RuntimeError(
                "save() is not supported for async-backed calendars. "
                "Use await parent._client.update_event() directly."
            )
        ical_str = (
            self._ical_cache.to_ical().decode()
            if self._ical_cache is not None
            else jscal_to_ical(self.data)
        )
        self.parent._client.update_event(self.id, ical_str)
