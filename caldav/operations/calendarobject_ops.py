"""
CalendarObjectResource operations - Sans-I/O business logic.

This module contains pure functions for working with calendar objects
(events, todos, journals) without performing any network I/O.
Both sync and async clients use these same functions.

These functions work on icalendar component objects or raw data strings.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from urllib.parse import quote

import icalendar
from dateutil.rrule import rrulestr


# Relation type reverse mapping (RFC 9253)
RELTYPE_REVERSE_MAP = {
    "PARENT": "CHILD",
    "CHILD": "PARENT",
    "SIBLING": "SIBLING",
    "DEPENDS-ON": "FINISHTOSTART",
    "FINISHTOSTART": "DEPENDENT",
}


@dataclass
class CalendarObjectData:
    """Data extracted from a calendar object."""

    uid: Optional[str]
    url: Optional[str]
    etag: Optional[str]
    data: Optional[str]


def generate_uid() -> str:
    """Generate a new UID for a calendar object."""
    return str(uuid.uuid1())


def generate_url(parent_url: str, uid: str) -> str:
    """
    Generate a URL for a calendar object based on its UID.

    Handles special characters in UID by proper quoting.

    Args:
        parent_url: URL of the parent calendar (must end with /)
        uid: The UID of the calendar object

    Returns:
        Full URL for the calendar object
    """
    # Double-quote slashes per https://github.com/python-caldav/caldav/issues/143
    quoted_uid = quote(uid.replace("/", "%2F"))
    if not parent_url.endswith("/"):
        parent_url += "/"
    return f"{parent_url}{quoted_uid}.ics"


def extract_uid_from_path(path: str) -> Optional[str]:
    """
    Extract UID from a .ics file path.

    Args:
        path: Path like "/calendars/user/calendar/event-uid.ics"

    Returns:
        The UID portion, or None if not found
    """
    if not path.endswith(".ics"):
        return None
    match = re.search(r"(/|^)([^/]*).ics$", path)
    if match:
        return match.group(2)
    return None


def find_id_and_path(
    component: Any,  # icalendar component
    given_id: Optional[str] = None,
    given_path: Optional[str] = None,
    existing_id: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Determine the UID and path for a calendar object.

    This is Sans-I/O logic extracted from CalendarObjectResource._find_id_path().

    Priority:
    1. given_id parameter
    2. existing_id (from object)
    3. UID from component
    4. UID extracted from path
    5. Generate new UID

    Args:
        component: icalendar component (VEVENT, VTODO, etc.)
        given_id: Explicitly provided ID
        given_path: Explicitly provided path
        existing_id: ID already set on the object

    Returns:
        Tuple of (uid, relative_path)
    """
    uid = given_id or existing_id

    if not uid:
        # Try to get UID from component
        uid_prop = component.get("UID")
        if uid_prop:
            uid = str(uid_prop)

    if not uid and given_path and given_path.endswith(".ics"):
        # Extract from path
        uid = extract_uid_from_path(given_path)

    if not uid:
        # Generate new UID
        uid = generate_uid()

    # Set UID in component (remove old one first)
    if "UID" in component:
        component.pop("UID")
    component.add("UID", uid)

    # Determine path
    if given_path:
        path = given_path
    else:
        path = quote(uid.replace("/", "%2F")) + ".ics"

    return uid, path


def get_duration(
    component: Any,  # icalendar component
    end_param: str = "DTEND",
) -> timedelta:
    """
    Get duration from a calendar component.

    According to the RFC, either DURATION or DTEND/DUE should be set,
    but never both. This function calculates duration from whichever is present.

    Args:
        component: icalendar component (VEVENT, VTODO, etc.)
        end_param: The end parameter name ("DTEND" for events, "DUE" for todos)

    Returns:
        Duration as timedelta
    """
    if "DURATION" in component:
        return component["DURATION"].dt

    if "DTSTART" in component and end_param in component:
        end = component[end_param].dt
        start = component["DTSTART"].dt

        # Handle date vs datetime mismatch
        if isinstance(end, datetime) != isinstance(start, datetime):
            # Convert both to datetime for comparison
            if not isinstance(start, datetime):
                start = datetime(start.year, start.month, start.day)
            if not isinstance(end, datetime):
                end = datetime(end.year, end.month, end.day)

        return end - start

    # Default: if only DTSTART and it's a date (not datetime), assume 1 day
    if "DTSTART" in component:
        dtstart = component["DTSTART"].dt
        if not isinstance(dtstart, datetime):
            return timedelta(days=1)

    return timedelta(0)


def get_due(component: Any) -> Optional[datetime]:
    """
    Get due date from a VTODO component.

    Handles DUE, DTEND, or DURATION+DTSTART.

    Args:
        component: icalendar VTODO component

    Returns:
        Due date/datetime, or None if not set
    """
    if "DUE" in component:
        return component["DUE"].dt
    elif "DTEND" in component:
        return component["DTEND"].dt
    elif "DURATION" in component and "DTSTART" in component:
        return component["DTSTART"].dt + component["DURATION"].dt
    return None


def set_duration(
    component: Any,  # icalendar component
    duration: timedelta,
    movable_attr: str = "DTSTART",
) -> None:
    """
    Set duration on a component, adjusting other properties as needed.

    If both DTSTART and DUE/DTEND are set, one must be moved.

    Args:
        component: icalendar component to modify
        duration: New duration
        movable_attr: Which attribute to move ("DTSTART" or "DUE")
    """
    has_due = "DUE" in component or "DURATION" in component
    has_start = "DTSTART" in component

    if has_due and has_start:
        component.pop(movable_attr, None)
        if movable_attr == "DUE":
            component.pop("DURATION", None)
        if movable_attr == "DTSTART":
            component.add("DTSTART", component["DUE"].dt - duration)
        elif movable_attr == "DUE":
            component.add("DUE", component["DTSTART"].dt + duration)
    elif "DUE" in component:
        component.add("DTSTART", component["DUE"].dt - duration)
    elif "DTSTART" in component:
        component.add("DUE", component["DTSTART"].dt + duration)
    else:
        if "DURATION" in component:
            component.pop("DURATION")
        component.add("DURATION", duration)


def is_task_pending(component: Any) -> bool:
    """
    Check if a VTODO component is pending (not completed).

    Args:
        component: icalendar VTODO component

    Returns:
        True if task is pending, False if completed/cancelled
    """
    if component.get("COMPLETED") is not None:
        return False

    status = component.get("STATUS", "NEEDS-ACTION")
    if status in ("NEEDS-ACTION", "IN-PROCESS"):
        return True
    if status in ("CANCELLED", "COMPLETED"):
        return False

    # Unknown status - treat as pending
    return True


def mark_task_completed(
    component: Any,  # icalendar VTODO component
    completion_timestamp: Optional[datetime] = None,
) -> None:
    """
    Mark a VTODO component as completed.

    Modifies the component in place.

    Args:
        component: icalendar VTODO component
        completion_timestamp: When the task was completed (defaults to now)
    """
    if completion_timestamp is None:
        completion_timestamp = datetime.now(timezone.utc)

    component.pop("STATUS", None)
    component.add("STATUS", "COMPLETED")
    component.add("COMPLETED", completion_timestamp)


def mark_task_uncompleted(component: Any) -> None:
    """
    Mark a VTODO component as not completed.

    Args:
        component: icalendar VTODO component
    """
    component.pop("status", None)
    component.pop("STATUS", None)
    component.add("STATUS", "NEEDS-ACTION")
    component.pop("completed", None)
    component.pop("COMPLETED", None)


def calculate_next_recurrence(
    component: Any,  # icalendar VTODO component
    completion_timestamp: Optional[datetime] = None,
    rrule: Optional[Any] = None,
    dtstart: Optional[datetime] = None,
    use_fixed_deadlines: Optional[bool] = None,
    ignore_count: bool = True,
) -> Optional[datetime]:
    """
    Calculate the next DTSTART for a recurring task after completion.

    This implements the logic from Todo._next().

    Args:
        component: icalendar VTODO component with RRULE
        completion_timestamp: When the task was completed
        rrule: Override RRULE (default: from component)
        dtstart: Override DTSTART (default: calculated based on use_fixed_deadlines)
        use_fixed_deadlines: If True, preserve DTSTART from component.
                            If False, use completion time minus duration.
                            If None, auto-detect from BY* parameters in rrule.
        ignore_count: If True, ignore COUNT in RRULE

    Returns:
        Next DTSTART datetime, or None if no more recurrences
    """
    if rrule is None:
        rrule = component.get("RRULE")
        if rrule is None:
            return None

    # Determine if we should use fixed deadlines
    if use_fixed_deadlines is None:
        use_fixed_deadlines = any(x for x in rrule if x.startswith("BY"))

    # Determine starting point for calculation
    if dtstart is None:
        if use_fixed_deadlines:
            if "DTSTART" in component:
                dtstart = component["DTSTART"].dt
            else:
                dtstart = completion_timestamp or datetime.now(timezone.utc)
        else:
            duration = get_duration(component, "DUE")
            dtstart = (completion_timestamp or datetime.now(timezone.utc)) - duration

    # Normalize to UTC for comparison
    if hasattr(dtstart, "astimezone"):
        dtstart = dtstart.astimezone(timezone.utc)

    ts = completion_timestamp or dtstart

    # Optionally ignore COUNT
    if ignore_count and "COUNT" in rrule:
        rrule = rrule.copy()
        rrule.pop("COUNT")

    # Parse and calculate next occurrence
    rrule_obj = rrulestr(rrule.to_ical().decode("utf-8"), dtstart=dtstart)
    return rrule_obj.after(ts)


def reduce_rrule_count(component: Any) -> bool:
    """
    Reduce the COUNT in an RRULE by 1.

    Args:
        component: icalendar component with RRULE

    Returns:
        False if COUNT was 1 (task should end), True otherwise
    """
    if "RRULE" not in component:
        return True

    rrule = component["RRULE"]
    count = rrule.get("COUNT", None)
    if count is not None:
        # COUNT is stored as a list in vRecur
        count_val = count[0] if isinstance(count, list) else count
        if count_val == 1:
            return False
        if isinstance(count, list):
            count[0] = count_val - 1
        else:
            rrule["COUNT"] = count_val - 1

    return True


def is_calendar_data_loaded(
    data: Optional[str],
    vobject_instance: Any,
    icalendar_instance: Any,
) -> bool:
    """
    Check if calendar object data is loaded.

    Args:
        data: Raw iCalendar data string
        vobject_instance: vobject instance (if any)
        icalendar_instance: icalendar instance (if any)

    Returns:
        True if data is loaded
    """
    return bool(
        (data and data.count("BEGIN:") > 1) or vobject_instance or icalendar_instance
    )


def has_calendar_component(data: Optional[str]) -> bool:
    """
    Check if data contains VEVENT, VTODO, or VJOURNAL.

    Args:
        data: Raw iCalendar data string

    Returns:
        True if a calendar component is present
    """
    if not data:
        return False

    return (
        data.count("BEGIN:VEVENT")
        + data.count("BEGIN:VTODO")
        + data.count("BEGIN:VJOURNAL")
    ) > 0


def get_non_timezone_subcomponents(
    icalendar_instance: Any,
) -> List[Any]:
    """
    Get all subcomponents except VTIMEZONE.

    Args:
        icalendar_instance: icalendar.Calendar instance

    Returns:
        List of non-timezone subcomponents
    """
    return [
        x
        for x in icalendar_instance.subcomponents
        if not isinstance(x, icalendar.Timezone)
    ]


def get_primary_component(icalendar_instance: Any) -> Optional[Any]:
    """
    Get the primary (non-timezone) component from a calendar.

    For events/todos/journals, there should be exactly one.
    For recurrence sets, returns the master component.

    Args:
        icalendar_instance: icalendar.Calendar instance

    Returns:
        The primary component (VEVENT, VTODO, VJOURNAL, or VFREEBUSY)
    """
    components = get_non_timezone_subcomponents(icalendar_instance)
    if not components:
        return None

    for comp in components:
        if isinstance(
            comp,
            (icalendar.Event, icalendar.Todo, icalendar.Journal, icalendar.FreeBusy),
        ):
            return comp

    return None


def copy_component_with_new_uid(
    component: Any,
    new_uid: Optional[str] = None,
) -> Any:
    """
    Create a copy of a component with a new UID.

    Args:
        component: icalendar component to copy
        new_uid: New UID (generated if not provided)

    Returns:
        Copy of the component with new UID
    """
    new_comp = component.copy()
    new_comp.pop("UID", None)
    new_comp.add("UID", new_uid or generate_uid())
    return new_comp


def get_reverse_reltype(reltype: str) -> Optional[str]:
    """
    Get the reverse relation type for a given relation type.

    Args:
        reltype: Relation type (e.g., "PARENT", "CHILD")

    Returns:
        Reverse relation type, or None if not defined
    """
    return RELTYPE_REVERSE_MAP.get(reltype.upper())


def extract_relations(
    component: Any,
    reltypes: Optional[set] = None,
) -> Dict[str, set]:
    """
    Extract RELATED-TO relations from a component.

    Args:
        component: icalendar component
        reltypes: Optional set of relation types to filter

    Returns:
        Dict mapping reltype -> set of UIDs
    """
    from collections import defaultdict

    result = defaultdict(set)
    relations = component.get("RELATED-TO", [])

    if not isinstance(relations, list):
        relations = [relations]

    for rel in relations:
        reltype = rel.params.get("RELTYPE", "PARENT")
        if reltypes and reltype not in reltypes:
            continue
        result[reltype].add(str(rel))

    return dict(result)
