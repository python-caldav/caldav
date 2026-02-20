"""
iCalendar → JSCalendar conversion (RFC 5545 → RFC 8984).

Public API:
    ical_to_jscal(ical_str, calendar_id=None) -> dict

The output dict is a raw JSCalendar CalendarEvent object suitable for passing
directly to CalendarEvent/set, or to JMAPEvent.from_jmap() to get a dataclass.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import icalendar

from caldav.jmap.convert._utils import _format_local_dt, _timedelta_to_duration
from caldav.lib import vcal

_CLASS_MAP = {
    "PRIVATE": "private",
    "CONFIDENTIAL": "secret",
}

_PARTSTAT_MAP = {
    "NEEDS-ACTION": "needs-action",
    "ACCEPTED": "accepted",
    "DECLINED": "declined",
    "TENTATIVE": "tentative",
    "DELEGATED": "delegated",
}

_CUTYPE_MAP = {
    "INDIVIDUAL": "individual",
    "GROUP": "group",
    "RESOURCE": "resource",
    "ROOM": "room",
}

_BYDAY_ABBR = {"SU", "MO", "TU", "WE", "TH", "FR", "SA"}


def _dtstart_to_jscal(dtstart_prop) -> tuple[str, str | None, bool]:
    """Extract JSCalendar start, timeZone, showWithoutTime from a DTSTART property.

    Returns:
        (start_str, time_zone, show_without_time)
    """
    dt = dtstart_prop.dt

    if isinstance(dt, date) and not isinstance(dt, datetime):
        # VALUE=DATE — all-day event
        return f"{dt.isoformat()}T00:00:00", None, True

    if dt.tzinfo is not None and dt.utcoffset() == timedelta(0):
        # UTC (Z suffix)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ"), None, False

    if dt.tzinfo is not None:
        # Timezone-aware — prefer the TZID parameter (IANA name) over tzinfo repr
        # NOTE: non-IANA TZIDs (e.g. "Eastern Standard Time" from Outlook)
        # are passed through unchanged; mapping to IANA is out of scope.
        tz_str = dtstart_prop.params.get("TZID")
        return dt.strftime("%Y-%m-%dT%H:%M:%S"), tz_str, False

    # Floating (no timezone)
    return dt.strftime("%Y-%m-%dT%H:%M:%S"), None, False


def _rrule_to_jscal(rrule_prop) -> dict:
    """Convert an iCalendar RRULE property to a JSCalendar RecurrenceRule dict.

    Always emits @type, interval, rscale, skip, firstDayOfWeek to match the
    fields Cyrus returns — makes round-trip comparison predictable.
    """
    rule: dict = {
        "@type": "RecurrenceRule",
        "rscale": "gregorian",
        "skip": "omit",
    }

    freq_list = rrule_prop.get("FREQ", [])
    if not freq_list:
        raise ValueError(f"RRULE is missing required FREQ component: {rrule_prop!r}")
    rule["frequency"] = freq_list[0].lower()

    interval_list = rrule_prop.get("INTERVAL", [])
    rule["interval"] = int(interval_list[0]) if interval_list else 1

    wkst_list = rrule_prop.get("WKST", [])
    rule["firstDayOfWeek"] = wkst_list[0].lower() if wkst_list else "mo"

    count_list = rrule_prop.get("COUNT", [])
    if count_list:
        rule["count"] = int(count_list[0])

    until_list = rrule_prop.get("UNTIL", [])
    if until_list:
        rule["until"] = _format_local_dt(until_list[0])

    byday_list = rrule_prop.get("BYDAY", [])
    if byday_list:
        by_day = []
        for item in byday_list:
            s = str(item)
            day_abbr = s.lstrip("+-0123456789")
            nth_str = s[: len(s) - len(day_abbr)]
            nday: dict = {"@type": "NDay", "day": day_abbr.lower()}
            if nth_str:
                nday["nthOfPeriod"] = int(nth_str)
            by_day.append(nday)
        rule["byDay"] = by_day

    bymonth_list = rrule_prop.get("BYMONTH", [])
    if bymonth_list:
        rule["byMonth"] = [str(m) for m in bymonth_list]

    bymonthday = rrule_prop.get("BYMONTHDAY", [])
    if bymonthday:
        rule["byMonthDay"] = [int(d) for d in bymonthday]

    byyearday = rrule_prop.get("BYYEARDAY", [])
    if byyearday:
        rule["byYearDay"] = [int(d) for d in byyearday]

    byweekno = rrule_prop.get("BYWEEKNO", [])
    if byweekno:
        rule["byWeekNo"] = [int(n) for n in byweekno]

    byhour = rrule_prop.get("BYHOUR", [])
    if byhour:
        rule["byHour"] = [int(h) for h in byhour]
    byminute = rrule_prop.get("BYMINUTE", [])
    if byminute:
        rule["byMinute"] = [int(m) for m in byminute]
    bysecond = rrule_prop.get("BYSECOND", [])
    if bysecond:
        rule["bySecond"] = [int(s) for s in bysecond]

    bysetpos = rrule_prop.get("BYSETPOS", [])
    if bysetpos:
        rule["bySetPosition"] = [int(p) for p in bysetpos]

    return rule


def _exdate_to_overrides(exdate_prop) -> dict:
    """Convert an EXDATE property (single or list) to recurrenceOverrides entries.

    Returns:
        Dict mapping LocalDateTime/UTCDateTime string → {"excluded": True}
    """
    # EXDATE may be a single vDDDLists or a list of them
    if not isinstance(exdate_prop, list):
        exdate_prop = [exdate_prop]

    overrides: dict = {}
    for ex in exdate_prop:
        dts = getattr(ex, "dts", [ex])
        for dt_prop in dts:
            dt = getattr(dt_prop, "dt", dt_prop)
            overrides[_format_local_dt(dt)] = {"excluded": True}
    return overrides


def _organizer_to_participant(organizer) -> tuple[str, dict]:
    """Convert an ORGANIZER property to a (participant_id, Participant dict) tuple."""
    email = str(organizer).removeprefix("mailto:")
    pid = str(uuid.uuid4())
    p: dict = {
        "roles": {"owner": True, "organizer": True},
        "sendTo": {
            "imip": str(organizer) if str(organizer).startswith("mailto:") else f"mailto:{email}"
        },
    }
    cn = organizer.params.get("CN")
    if cn:
        p["name"] = str(cn)
    p["email"] = email
    return pid, p


def _attendee_to_participant(attendee) -> tuple[str, dict]:
    """Convert an ATTENDEE property to a (participant_id, Participant dict) tuple."""
    addr = str(attendee)
    email = addr.removeprefix("mailto:")
    pid = str(uuid.uuid4())
    p: dict = {
        "roles": {"attendee": True},
        "sendTo": {"imip": addr if addr.startswith("mailto:") else f"mailto:{email}"},
        "email": email,
    }
    cn = attendee.params.get("CN")
    if cn:
        p["name"] = str(cn)

    partstat = attendee.params.get("PARTSTAT")
    if partstat:
        p["participationStatus"] = _PARTSTAT_MAP.get(partstat.upper(), partstat.lower())

    rsvp = attendee.params.get("RSVP", "")
    if str(rsvp).upper() == "TRUE":
        p["expectReply"] = True

    cutype = attendee.params.get("CUTYPE")
    if cutype:
        p["kind"] = _CUTYPE_MAP.get(cutype.upper(), cutype.lower())

    role = attendee.params.get("ROLE")
    if role and role.upper() == "CHAIR":
        p["roles"]["chair"] = True

    return pid, p


def _valarm_to_alert(alarm) -> tuple[str, dict]:
    """Convert a VALARM component to a (alert_id, Alert dict) tuple.

    Trigger is emitted as a plain SignedDuration string (e.g. "-PT15M") or
    UTCDateTime string — matching the JMAPEvent.alerts docstring convention.
    """
    alert_id = str(uuid.uuid4())
    action = str(alarm.get("ACTION", "display")).lower()
    alert: dict = {"action": action}

    trigger_prop = alarm.get("TRIGGER")
    if trigger_prop is not None:
        trigger_val = trigger_prop.dt
        if isinstance(trigger_val, timedelta):
            # Relative trigger — convert to SignedDuration string
            alert["trigger"] = _timedelta_to_duration(trigger_val)
        elif isinstance(trigger_val, datetime):
            # Absolute trigger — UTCDateTime string
            alert["trigger"] = trigger_val.strftime("%Y-%m-%dT%H:%M:%SZ")

    description = alarm.get("DESCRIPTION")
    if description:
        alert["description"] = str(description)

    return alert_id, alert


def _location_str_to_jscal(location_str: str) -> dict:
    """Convert a LOCATION string to a JSCalendar locations map entry.

    Returns:
        {"<uuid>": {"name": location_str}}
    """
    return {str(uuid.uuid4()): {"name": location_str}}


def _categories_to_keywords(categories_prop) -> dict:
    """Convert a CATEGORIES property to a JSCalendar keywords map.

    icalendar returns one of three types depending on how CATEGORIES appears:
    - vCategory (single CATEGORIES line, possibly multi-value): access .cats
    - list of vCategory (multiple CATEGORIES lines): flatten .cats from each
    - vText (rare, single bare string value): str() and comma-split
    """
    if hasattr(categories_prop, "cats"):
        values = [str(c) for c in categories_prop.cats]
    elif isinstance(categories_prop, list):
        values = []
        for item in categories_prop:
            if hasattr(item, "cats"):
                values.extend(str(c) for c in item.cats)
            else:
                values.append(str(item))
    else:
        raw = str(categories_prop)
        values = [v.strip() for v in raw.split(",") if v.strip()]

    return {v: True for v in values}


def ical_to_jscal(ical_str: str, calendar_id: str | None = None) -> dict:
    """Convert an iCalendar string to a JSCalendar CalendarEvent dict (RFC 8984).

    Processes the first VEVENT found in the string. Any sibling VEVENTs with a
    RECURRENCE-ID are folded into the ``recurrenceOverrides`` map of the master
    event. EXDATE entries are also added to ``recurrenceOverrides``.

    Args:
        ical_str: A VCALENDAR string (or bare VEVENT — vcal.fix normalises it).
        calendar_id: If provided, sets ``calendarIds: {calendar_id: true}``
            on the output. Required when the result will be used in
            ``CalendarEvent/set`` (the server needs to know which calendar).

    Returns:
        Raw JSCalendar dict suitable for passing to ``JMAPEvent.from_jmap()``
        or directly to ``CalendarEvent/set``.

    Raises:
        ValueError: If no VEVENT component is found.
    """
    # Normalize iCal string (fixes common server-generated violations)
    fixed = vcal.fix(ical_str)

    cal = icalendar.Calendar.from_ical(fixed)

    # Split subcomponents into master VEVENTs and override VEVENTs
    master: icalendar.Event | None = None
    overrides_by_recurrence_id: dict[str, icalendar.Event] = {}

    for component in cal.subcomponents:
        if not isinstance(component, icalendar.Event):
            continue
        if component.get("RECURRENCE-ID") is not None:
            # Override instance — key by its recurrence-id datetime
            rid = _format_local_dt(component["RECURRENCE-ID"].dt)
            overrides_by_recurrence_id[rid] = component
        elif master is None:
            master = component

    if master is None:
        raise ValueError("No VEVENT component found in iCalendar string")

    uid = str(master["UID"])
    summary = master.get("SUMMARY")
    title = str(summary) if summary else ""
    dtstart_prop = master["DTSTART"]
    start, time_zone, show_without_time = _dtstart_to_jscal(dtstart_prop)

    if master.get("DURATION"):
        duration = _timedelta_to_duration(master["DURATION"].dt)
    elif master.get("DTEND"):
        delta = master["DTEND"].dt - dtstart_prop.dt
        duration = _timedelta_to_duration(delta)
    else:
        duration = "P0D"

    jscal: dict = {
        "uid": uid,
        "title": title,
        "start": start,
        "duration": duration,
    }

    if calendar_id is not None:
        jscal["calendarIds"] = {calendar_id: True}

    if time_zone is not None:
        jscal["timeZone"] = time_zone

    if show_without_time:
        jscal["showWithoutTime"] = True

    description = master.get("DESCRIPTION")
    if description:
        jscal["description"] = str(description)

    sequence = master.get("SEQUENCE")
    if sequence is not None:
        jscal["sequence"] = int(sequence)

    priority = master.get("PRIORITY")
    if priority is not None:
        p_int = int(priority)
        if p_int != 0:
            jscal["priority"] = p_int

    cls = master.get("CLASS")
    if cls:
        privacy = _CLASS_MAP.get(str(cls).upper())
        if privacy:
            jscal["privacy"] = privacy

    transp = master.get("TRANSP")
    if transp and str(transp).upper() == "TRANSPARENT":
        jscal["freeBusyStatus"] = "free"

    color = master.get("COLOR")
    if color:
        jscal["color"] = str(color)

    categories = master.get("CATEGORIES")
    if categories is not None:
        kw = _categories_to_keywords(categories)
        if kw:
            jscal["keywords"] = kw

    location = master.get("LOCATION")
    if location:
        jscal["locations"] = _location_str_to_jscal(str(location))

    participants: dict = {}
    organizer = master.get("ORGANIZER")
    if organizer is not None:
        pid, p = _organizer_to_participant(organizer)
        participants[pid] = p

    # .get() returns a single vCalAddress or a list; normalise to list
    raw_attendees = master.get("ATTENDEE")
    if raw_attendees is None:
        attendees = []
    elif isinstance(raw_attendees, list):
        attendees = raw_attendees
    else:
        attendees = [raw_attendees]
    for attendee in attendees:
        pid, p = _attendee_to_participant(attendee)
        participants[pid] = p

    if participants:
        jscal["participants"] = participants

    rrules = master.get("RRULE")
    if rrules is not None:
        if not isinstance(rrules, list):
            rrules = [rrules]
        jscal["recurrenceRules"] = [_rrule_to_jscal(r) for r in rrules]

    exrules = master.get("EXRULE")
    if exrules is not None:
        if not isinstance(exrules, list):
            exrules = [exrules]
        jscal["excludedRecurrenceRules"] = [_rrule_to_jscal(r) for r in exrules]

    recurrence_overrides: dict = {}

    exdate = master.get("EXDATE")
    if exdate is not None:
        recurrence_overrides.update(_exdate_to_overrides(exdate))

    for rid_key, child in overrides_by_recurrence_id.items():
        # Build a patch: only fields that differ from the master
        patch: dict = {}
        child_summary = child.get("SUMMARY")
        if child_summary and str(child_summary) != title:
            patch["title"] = str(child_summary)
        child_start_prop = child.get("DTSTART")
        if child_start_prop:
            child_start, _, _ = _dtstart_to_jscal(child_start_prop)
            if child_start != start:
                patch["start"] = child_start
        child_duration_prop = child.get("DURATION")
        if child_duration_prop:
            child_dur = _timedelta_to_duration(child_duration_prop.dt)
            if child_dur != duration:
                patch["duration"] = child_dur
        child_description = child.get("DESCRIPTION")
        if child_description and str(child_description) != jscal.get("description"):
            patch["description"] = str(child_description)
        recurrence_overrides[rid_key] = patch or {}

    if recurrence_overrides:
        jscal["recurrenceOverrides"] = recurrence_overrides

    alarms = [c for c in master.subcomponents if getattr(c, "name", None) == "VALARM"]
    if alarms:
        alerts: dict = {}
        for alarm in alarms:
            alert_id, alert = _valarm_to_alert(alarm)
            alerts[alert_id] = alert
        jscal["alerts"] = alerts

    return jscal
