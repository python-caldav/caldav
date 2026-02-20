"""
JSCalendar → iCalendar conversion (RFC 8984 → RFC 5545).

Public API:
    jscal_to_ical(jscal: dict) -> str

Accepts a raw JSCalendar CalendarEvent dict (as returned by CalendarEvent/get
or produced by ical_to_jscal). Returns a VCALENDAR string.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import icalendar
from icalendar import vCalAddress, vText

from caldav.jmap.convert._utils import _duration_to_timedelta, _format_local_dt
from caldav.lib import vcal

_PRIVACY_TO_CLASS = {
    "private": "PRIVATE",
    "secret": "CONFIDENTIAL",
}

_FREE_BUSY_TO_TRANSP = {
    "free": "TRANSPARENT",
    "busy": "OPAQUE",
}

_PARTSTAT_MAP = {
    "needs-action": "NEEDS-ACTION",
    "accepted": "ACCEPTED",
    "declined": "DECLINED",
    "tentative": "TENTATIVE",
    "delegated": "DELEGATED",
}

_KIND_TO_CUTYPE = {
    "individual": "INDIVIDUAL",
    "group": "GROUP",
    "resource": "RESOURCE",
    "room": "ROOM",
}


def _start_to_dtstart(
    component: icalendar.Event,
    start_str: str,
    time_zone: str | None,
    show_without_time: bool,
) -> None:
    """Add a DTSTART property to component from JSCalendar start fields.

    Handles three cases:
    - All-day (showWithoutTime): VALUE=DATE
    - UTC (start ends with Z): UTC DATETIME
    - Timezone-aware: DATETIME;TZID=...
    - Floating (no timeZone, no Z): plain DATETIME
    """
    if show_without_time:
        dt = date.fromisoformat(start_str[:10])
        component.add("dtstart", dt)
        return

    if start_str.endswith("Z"):
        dt = datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        component.add("dtstart", dt)
        return

    dt_naive = datetime.strptime(start_str[:19], "%Y-%m-%dT%H:%M:%S")

    if time_zone:

        def _add_dtstart_tzid_passthrough():
            dtstart = icalendar.vDatetime(dt_naive)
            dtstart.params["TZID"] = time_zone
    if time_zone:
        try:
            tz = ZoneInfo(time_zone)
            dt = dt_naive.replace(tzinfo=tz)
            component.add("dtstart", dt)
        except ZoneInfoNotFoundError:
            # Non-IANA TZID (e.g. "Eastern Standard Time") — pass through as-is
            # so the consuming calendar client can resolve it.
            dtstart = icalendar.vDatetime(dt_naive)
            dtstart.params["TZID"] = time_zone
            component.add("dtstart", dtstart)

        try:
            import pytz  # type: ignore[import]

            try:
                tz = pytz.timezone(time_zone)
                dt = tz.localize(dt_naive)
                component.add("dtstart", dt)
            except pytz.exceptions.UnknownTimeZoneError:
                _add_dtstart_tzid_passthrough()
        except ImportError:
            _add_dtstart_tzid_passthrough()
    else:
        component.add("dtstart", dt_naive)


def _jscal_rrule_to_rrule(rule: dict) -> dict:
    """Convert a JSCalendar RecurrenceRule dict to an iCalendar vRecur-compatible dict.

    Strips @type and NDay @type fields — icalendar library rejects them.
    Returns a plain dict suitable for icalendar.vRecur.
    """
    freq = rule.get("frequency", "").upper()
    if not freq:
        return {}

    ical_rule: dict = {"FREQ": freq}

    interval = rule.get("interval")
    if interval and interval != 1:
        ical_rule["INTERVAL"] = interval

    count = rule.get("count")
    if count is not None:
        ical_rule["COUNT"] = count

    until = rule.get("until")
    if until:
        if until.endswith("Z"):
            ical_rule["UNTIL"] = datetime.strptime(until, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        else:
            ical_rule["UNTIL"] = datetime.strptime(until[:19], "%Y-%m-%dT%H:%M:%S")

    by_day = rule.get("byDay", [])
    if by_day:
        byday_strs = []
        for nday in by_day:
            day = nday.get("day", "").upper()
            nth = nday.get("nthOfPeriod")
            if nth:
                byday_strs.append(f"{nth}{day}")
            else:
                byday_strs.append(day)
        ical_rule["BYDAY"] = byday_strs

    by_month = rule.get("byMonth", [])
    if by_month:
        ical_rule["BYMONTH"] = [
            m if isinstance(m, int) else int(str(m).rstrip("L")) for m in by_month
        ]

    by_month_day = rule.get("byMonthDay", [])
    if by_month_day:
        ical_rule["BYMONTHDAY"] = by_month_day

    by_year_day = rule.get("byYearDay", [])
    if by_year_day:
        ical_rule["BYYEARDAY"] = by_year_day

    by_week_no = rule.get("byWeekNo", [])
    if by_week_no:
        ical_rule["BYWEEKNO"] = by_week_no

    by_hour = rule.get("byHour", [])
    if by_hour:
        ical_rule["BYHOUR"] = by_hour

    by_minute = rule.get("byMinute", [])
    if by_minute:
        ical_rule["BYMINUTE"] = by_minute

    by_second = rule.get("bySecond", [])
    if by_second:
        ical_rule["BYSECOND"] = by_second

    by_set_pos = rule.get("bySetPosition", [])
    if by_set_pos:
        ical_rule["BYSETPOS"] = by_set_pos

    first_day = rule.get("firstDayOfWeek")
    if first_day and first_day != "mo":
        ical_rule["WKST"] = first_day.upper()

    return ical_rule


def _participant_imip(p: dict) -> str:
    send_to = p.get("sendTo", {})
    imip = send_to.get("imip") or send_to.get("other") or p.get("email", "")
    if imip and not imip.startswith("mailto:"):
        imip = f"mailto:{imip}"
    return imip


def _participant_to_organizer(p: dict) -> vCalAddress | None:
    """Build a vCalAddress for ORGANIZER, or None if this participant is not an organizer."""
    roles = p.get("roles", {})
    if not (roles.get("owner") or roles.get("organizer")):
        return None

    addr = vCalAddress(_participant_imip(p))
    name = p.get("name")
    if name:
        addr.params["CN"] = vText(name)
    return addr


def _participant_to_attendee(p: dict) -> vCalAddress | None:
    """Build a vCalAddress for ATTENDEE, or None if participant is purely an organizer."""
    roles = p.get("roles", {})
    has_attendee_role = any(
        roles.get(r) for r in ("attendee", "chair", "informational", "optional")
    )
    if not has_attendee_role and (roles.get("owner") or roles.get("organizer")):
        return None

    addr = vCalAddress(_participant_imip(p))
    name = p.get("name")
    if name:
        addr.params["CN"] = vText(name)

    partstat = p.get("participationStatus")
    if partstat:
        addr.params["PARTSTAT"] = _PARTSTAT_MAP.get(partstat, partstat.upper())
    else:
        addr.params["PARTSTAT"] = "NEEDS-ACTION"

    if p.get("expectReply"):
        addr.params["RSVP"] = "TRUE"

    kind = p.get("kind")
    if kind:
        addr.params["CUTYPE"] = _KIND_TO_CUTYPE.get(kind, kind.upper())

    if roles.get("chair"):
        addr.params["ROLE"] = "CHAIR"
    elif roles.get("attendee") or has_attendee_role:
        addr.params["ROLE"] = "REQ-PARTICIPANT"

    return addr


def _alert_to_valarm(alert: dict) -> icalendar.Alarm:
    """Convert a JSCalendar Alert dict to an icalendar.Alarm component."""
    alarm = icalendar.Alarm()
    action = alert.get("action", "display").upper()
    alarm.add("action", action)

    trigger_str = alert.get("trigger", "")
    if trigger_str:
        if trigger_str.endswith("Z"):
            try:
                dt = datetime.strptime(trigger_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
                alarm.add("trigger", dt)
            except ValueError:
                alarm.add("trigger", timedelta(0))
        else:
            try:
                td = _duration_to_timedelta(trigger_str)
                alarm.add("trigger", td)
            except ValueError:
                alarm.add("trigger", timedelta(0))
    else:
        alarm.add("trigger", timedelta(0))

    description = alert.get("description")
    if description:
        alarm.add("description", description)
    elif action == "DISPLAY":
        alarm.add("description", "Reminder")

    return alarm


def _keywords_to_categories(keywords: dict) -> list[str]:
    """Convert JSCalendar keywords map to a list of CATEGORIES strings."""
    return [k for k, v in keywords.items() if v]


def _locations_to_location(locations: dict) -> str | None:
    """Extract the first location name from a JSCalendar locations map."""
    for loc in locations.values():
        name = loc.get("name")
        if name:
            return str(name)
    return None


def jscal_to_ical(jscal: dict) -> str:
    """Convert a JSCalendar CalendarEvent dict to an iCalendar VCALENDAR string.

    Handles the full set of fields supported by ``ical_to_jscal`` for round-trip
    fidelity. ``recurrenceOverrides`` entries with ``excluded: true`` become
    EXDATE properties; patch dicts become child VEVENTs with RECURRENCE-ID.

    Args:
        jscal: A JSCalendar CalendarEvent dict (raw, not a JMAPEvent dataclass).

    Returns:
        An iCalendar VCALENDAR string, normalised by ``vcal.fix()``.
    """
    cal = icalendar.Calendar()
    cal.add("prodid", "-//python-caldav//JMAP//EN")
    cal.add("version", "2.0")

    event = icalendar.Event()

    uid = jscal.get("uid", "")
    if uid:
        event.add("uid", uid)
    event.add("dtstamp", datetime.now(tz=timezone.utc))

    sequence = jscal.get("sequence", 0)
    if sequence:
        event.add("sequence", sequence)

    start_str = jscal.get("start", "")
    time_zone = jscal.get("timeZone")
    show_without_time = jscal.get("showWithoutTime", False)
    if start_str:
        _start_to_dtstart(event, start_str, time_zone, show_without_time)

    duration_str = jscal.get("duration", "P0D")
    if duration_str and duration_str != "P0D":
        td = _duration_to_timedelta(duration_str)
        event.add("duration", td)

    title = jscal.get("title", "")
    if title:
        event.add("summary", title)

    description = jscal.get("description")
    if description:
        event.add("description", description)

    priority = jscal.get("priority", 0)
    if priority:
        event.add("priority", priority)

    privacy = jscal.get("privacy")
    if privacy:
        cls = _PRIVACY_TO_CLASS.get(privacy)
        if cls:
            event.add("class", cls)

    free_busy = jscal.get("freeBusyStatus", "busy")
    transp = _FREE_BUSY_TO_TRANSP.get(free_busy, "OPAQUE")
    if transp != "OPAQUE":
        event.add("transp", transp)

    color = jscal.get("color")
    if color:
        event.add("color", color)

    keywords = jscal.get("keywords") or {}
    if keywords:
        cats = _keywords_to_categories(keywords)
        if cats:
            event.add("categories", cats)

    locations = jscal.get("locations") or {}
    if locations:
        loc_name = _locations_to_location(locations)
        if loc_name:
            event.add("location", loc_name)

    for rule in jscal.get("recurrenceRules") or []:
        ical_rule = _jscal_rrule_to_rrule(rule)
        if ical_rule:
            event.add("rrule", ical_rule)

    for rule in jscal.get("excludedRecurrenceRules") or []:
        ical_rule = _jscal_rrule_to_rrule(rule)
        if ical_rule:
            event.add("exrule", ical_rule)

    exdates: list[datetime | date] = []
    child_events: list[icalendar.Event] = []

    for override_key, patch in (jscal.get("recurrenceOverrides") or {}).items():
        if override_key.endswith("Z"):
            rid_dt: datetime | date = datetime.strptime(override_key, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        else:
            rid_dt = datetime.strptime(override_key[:19], "%Y-%m-%dT%H:%M:%S")

        if patch is None or (isinstance(patch, dict) and patch.get("excluded")):
            exdates.append(rid_dt)
        else:
            child = icalendar.Event()
            child.add("uid", uid)
            child.add("dtstamp", datetime.now(tz=timezone.utc))
            child.add("recurrence-id", rid_dt)
            child_start = patch.get("start", start_str)
            child_tz = patch.get("timeZone", time_zone)
            child_swt = patch.get("showWithoutTime", show_without_time)
            if child_start:
                _start_to_dtstart(child, child_start, child_tz, child_swt)
            child_dur = patch.get("duration", duration_str)
            if child_dur and child_dur != "P0D":
                child.add("duration", _duration_to_timedelta(child_dur))
            child_title = patch.get("title", title)
            if child_title:
                child.add("summary", child_title)
            child_desc = patch.get("description", description)
            if child_desc:
                child.add("description", child_desc)
            child_events.append(child)

    if exdates:
        for exdate_dt in exdates:
            event.add("exdate", exdate_dt)

    organizer_added = False
    for p in (jscal.get("participants") or {}).values():
        org = _participant_to_organizer(p)
        if org and not organizer_added:
            event.add("organizer", org)
            organizer_added = True

    for p in (jscal.get("participants") or {}).values():
        att = _participant_to_attendee(p)
        if att is not None:
            event.add("attendee", att)

    for alert in (jscal.get("alerts") or {}).values():
        alarm = _alert_to_valarm(alert)
        event.add_component(alarm)

    cal.add_component(event)

    for child in child_events:
        cal.add_component(child)

    raw = cal.to_ical().decode("utf-8")
    return vcal.fix(raw)
