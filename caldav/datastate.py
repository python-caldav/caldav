"""
Data state management for CalendarObjectResource.

This module implements the Strategy/State pattern for managing different
representations of calendar data (raw string, icalendar object, vobject object).

See https://github.com/python-caldav/caldav/issues/613 for design discussion.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import icalendar

if TYPE_CHECKING:
    import vobject


class DataState(ABC):
    """Abstract base class for calendar data states.

    Each concrete state represents a different "source of truth" for the
    calendar data. The state provides access to all representations, but
    only one is authoritative at any time.
    """

    @abstractmethod
    def get_data(self) -> str:
        """Get raw iCalendar string representation.

        This may involve serialization if the current state holds a
        parsed object.
        """
        pass

    @abstractmethod
    def get_icalendar_copy(self) -> icalendar.Calendar:
        """Get a fresh copy of the icalendar object.

        This is safe for read-only access - modifications won't affect
        the stored data.
        """
        pass

    @abstractmethod
    def get_vobject_copy(self) -> vobject.base.Component:
        """Get a fresh copy of the vobject object.

        This is safe for read-only access - modifications won't affect
        the stored data.
        """
        pass

    def get_uid(self) -> str | None:
        """Extract UID without full parsing if possible.

        Default implementation parses the data, but subclasses can optimize.
        """
        cal = self.get_icalendar_copy()
        for comp in cal.subcomponents:
            if comp.name in ("VEVENT", "VTODO", "VJOURNAL") and "UID" in comp:
                return str(comp["UID"])
        return None

    def get_component_type(self) -> str | None:
        """Get the component type (VEVENT, VTODO, VJOURNAL) without full parsing.

        Default implementation parses the data, but subclasses can optimize.
        """
        cal = self.get_icalendar_copy()
        for comp in cal.subcomponents:
            if comp.name in ("VEVENT", "VTODO", "VJOURNAL"):
                return comp.name
        return None

    def has_data(self) -> bool:
        """Check if this state has any data."""
        return True


class NoDataState(DataState):
    """Null Object pattern - no data loaded yet.

    This state is used when a CalendarObjectResource is created without
    any initial data. It provides empty/default values for all accessors.
    """

    def get_data(self) -> str:
        return ""

    def get_icalendar_copy(self) -> icalendar.Calendar:
        return icalendar.Calendar()

    def get_vobject_copy(self) -> vobject.base.Component:
        import vobject

        return vobject.iCalendar()

    def get_uid(self) -> str | None:
        return None

    def get_component_type(self) -> str | None:
        return None

    def has_data(self) -> bool:
        return False


class RawDataState(DataState):
    """State when raw string data is the source of truth.

    This is the most common initial state when data is loaded from
    a CalDAV server.
    """

    def __init__(self, data: str):
        self._data = data

    def get_data(self) -> str:
        return self._data

    def get_icalendar_copy(self) -> icalendar.Calendar:
        return icalendar.Calendar.from_ical(self._data)

    def get_vobject_copy(self) -> vobject.base.Component:
        import vobject

        return vobject.readOne(self._data)

    def get_uid(self) -> str | None:
        # Optimization: use regex instead of full parsing
        match = re.search(r"^UID:(.+)$", self._data, re.MULTILINE)
        if match:
            return match.group(1).strip()
        # Fall back to parsing if regex fails (e.g., folded lines)
        return super().get_uid()

    def get_component_type(self) -> str | None:
        # Optimization: use simple string search
        if "BEGIN:VEVENT" in self._data:
            return "VEVENT"
        elif "BEGIN:VTODO" in self._data:
            return "VTODO"
        elif "BEGIN:VJOURNAL" in self._data:
            return "VJOURNAL"
        return None


class IcalendarState(DataState):
    """State when icalendar object is the source of truth.

    This state is entered when:
    - User calls edit_icalendar_instance()
    - User sets icalendar_instance property
    - User modifies the icalendar object
    """

    def __init__(self, calendar: icalendar.Calendar):
        self._calendar = calendar

    def get_data(self) -> str:
        return self._calendar.to_ical().decode("utf-8")

    def get_icalendar_copy(self) -> icalendar.Calendar:
        # Parse from serialized form to get a true copy
        return icalendar.Calendar.from_ical(self.get_data())

    def get_authoritative_icalendar(self) -> icalendar.Calendar:
        """Returns THE icalendar object (not a copy).

        This is the authoritative object - modifications will be saved.
        """
        return self._calendar

    def get_vobject_copy(self) -> vobject.base.Component:
        import vobject

        return vobject.readOne(self.get_data())

    def get_uid(self) -> str | None:
        for comp in self._calendar.subcomponents:
            if comp.name in ("VEVENT", "VTODO", "VJOURNAL") and "UID" in comp:
                return str(comp["UID"])
        return None

    def get_component_type(self) -> str | None:
        for comp in self._calendar.subcomponents:
            if comp.name in ("VEVENT", "VTODO", "VJOURNAL"):
                return comp.name
        return None


class VobjectState(DataState):
    """State when vobject object is the source of truth.

    This state is entered when:
    - User calls edit_vobject_instance()
    - User sets vobject_instance property
    - User modifies the vobject object
    """

    def __init__(self, vobj: vobject.base.Component):
        self._vobject = vobj

    def get_data(self) -> str:
        return self._vobject.serialize()

    def get_icalendar_copy(self) -> icalendar.Calendar:
        return icalendar.Calendar.from_ical(self.get_data())

    def get_vobject_copy(self) -> vobject.base.Component:
        import vobject

        return vobject.readOne(self.get_data())

    def get_authoritative_vobject(self) -> vobject.base.Component:
        """Returns THE vobject object (not a copy).

        This is the authoritative object - modifications will be saved.
        """
        return self._vobject

    def get_uid(self) -> str | None:
        # vobject uses different attribute access
        try:
            if hasattr(self._vobject, "vevent"):
                return str(self._vobject.vevent.uid.value)
            elif hasattr(self._vobject, "vtodo"):
                return str(self._vobject.vtodo.uid.value)
            elif hasattr(self._vobject, "vjournal"):
                return str(self._vobject.vjournal.uid.value)
        except AttributeError:
            pass
        return None

    def get_component_type(self) -> str | None:
        if hasattr(self._vobject, "vevent"):
            return "VEVENT"
        elif hasattr(self._vobject, "vtodo"):
            return "VTODO"
        elif hasattr(self._vobject, "vjournal"):
            return "VJOURNAL"
        return None
