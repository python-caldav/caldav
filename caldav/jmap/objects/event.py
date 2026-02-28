"""
JMAP CalendarEvent object.

Represents a JMAP CalendarEvent resource as returned by ``CalendarEvent/get``.
Properties follow RFC 8984 (JSCalendar) extended with JMAP-specific additions
defined in the JMAP Calendars specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JMAPEvent:
    """A JMAP CalendarEvent object.

    Fields map directly to the JMAP Calendars specification.  Only fields
    that are stored on the server are represented here; computed properties
    (``utcStart``, ``utcEnd``, ``baseEventId``) and server-assigned metadata
    (``created``, ``updated``, ``isOrigin``) are not stored as attributes
    because they are either read-only or fetched on demand.

    Attributes:
        id: Server-assigned event identifier (immutable, scoped to account).
        uid: iCalendar UID — stable across copies and scheduling messages.
        calendar_ids: Map of calendarId → ``True`` for each calendar
            containing this event.  An event may belong to multiple calendars.
        title: Short summary.  Maps to iCalendar ``SUMMARY``.
        start: Local start date-time, e.g. ``"2024-06-15T14:30:00"``.
            No timezone offset in the string — context comes from
            ``time_zone``.
        time_zone: IANA timezone name for interpreting ``start``
            (e.g. ``"Europe/Berlin"``).  ``None`` means the event is
            "floating" — it occurs at the same wall-clock time in every zone.
        duration: ISO 8601 duration, e.g. ``"PT1H30M"``.  Default ``"P0D"``
            (zero duration / instantaneous event).
        show_without_time: Presentation hint — when ``True`` the time
            component is not important to display.  Equivalent to the
            all-day concept in iCalendar.  Does not affect scheduling
            semantics.
        description: Full plain-text description.  Maps to iCalendar
            ``DESCRIPTION``.
        locations: Map of location id → location dict.
        virtual_locations: Map of virtual location id → virtual-location dict
            (video-conference links, etc.).
        links: Map of link id → link dict (attachments, related URLs).
        keywords: Map of free-form tag string → ``True``.  Maps to iCalendar
            ``CATEGORIES``.
        participants: Map of participant id → participant dict.  The
            participant with ``"roles": {"owner": True}`` or
            ``"roles": {"organizer": True}`` is the organizer.
        recurrence_rules: List of recurrence-rule dicts.  Each dict uses
            JSCalendar ``RecurrenceRule`` structure (JSON, not RFC 5545 RRULE
            text syntax).
        excluded_recurrence_rules: List of exclusion recurrence-rule dicts.
        recurrence_overrides: Map of LocalDateTime string →  patch dict.
            An empty patch ``{}`` adds the occurrence without changes; a
            partial patch modifies individual properties via JSON Pointer
            paths; a ``null`` value cancels that occurrence.
        alerts: Map of alert id → alert dict.  ``trigger`` is a
            ``SignedDuration`` (e.g. ``"-PT15M"``) or a ``UTCDateTime``
            string.  ``action`` is ``"display"`` or ``"email"``.
        use_default_alerts: When ``True``, the server's default alerts
            are applied instead of ``alerts``.
        sequence: Scheduling sequence number.  Maps to iCalendar
            ``SEQUENCE``.
        free_busy_status: ``"busy"`` (default) or ``"free"``.
        privacy: Optional visibility/privacy level string.
        color: Optional CSS color hint for calendar clients.
        is_draft: When ``True``, the server suppresses scheduling messages.
    """

    id: str
    uid: str
    calendar_ids: dict
    title: str
    start: str
    time_zone: str | None = None
    duration: str = "P0D"
    show_without_time: bool = False
    description: str | None = None
    locations: dict = field(default_factory=dict)
    virtual_locations: dict = field(default_factory=dict)
    links: dict = field(default_factory=dict)
    keywords: dict = field(default_factory=dict)
    participants: dict = field(default_factory=dict)
    recurrence_rules: list = field(default_factory=list)
    excluded_recurrence_rules: list = field(default_factory=list)
    recurrence_overrides: dict = field(default_factory=dict)
    alerts: dict = field(default_factory=dict)
    use_default_alerts: bool = False
    sequence: int = 0
    free_busy_status: str = "busy"
    privacy: str | None = None
    color: str | None = None
    is_draft: bool = False
    priority: int = 0

    @classmethod
    def from_jmap(cls, data: dict) -> JMAPEvent:
        """Construct a JMAPEvent from a raw JMAP CalendarEvent JSON dict.

        ``id``, ``uid``, ``calendarIds``, ``title``, and ``start`` are
        required in server responses; a missing key raises ``KeyError``.
        Unknown keys are silently ignored for forward compatibility.
        """
        return cls(
            id=data["id"],
            uid=data["uid"],
            calendar_ids=data["calendarIds"],
            title=data["title"],
            start=data["start"],
            time_zone=data.get("timeZone"),
            duration=data.get("duration", "P0D"),
            show_without_time=data.get("showWithoutTime", False),
            description=data.get("description"),
            locations=data.get("locations") or {},
            virtual_locations=data.get("virtualLocations") or {},
            links=data.get("links") or {},
            keywords=data.get("keywords") or {},
            participants=data.get("participants") or {},
            recurrence_rules=data.get("recurrenceRules") or [],
            excluded_recurrence_rules=data.get("excludedRecurrenceRules") or [],
            recurrence_overrides=data.get("recurrenceOverrides") or {},
            alerts=data.get("alerts") or {},
            use_default_alerts=data.get("useDefaultAlerts", False),
            sequence=data.get("sequence", 0),
            free_busy_status=data.get("freeBusyStatus", "busy"),
            privacy=data.get("privacy"),
            color=data.get("color"),
            is_draft=data.get("isDraft", False),
            priority=data.get("priority", 0),
        )

    def to_jmap(self) -> dict:
        """Serialise to a JMAP CalendarEvent JSON dict for ``CalendarEvent/set``.

        Always includes the fields required for a valid create payload.
        Optional fields are included only when they hold a non-default value,
        keeping the payload minimal.

        Note: ``id`` is intentionally excluded — it is server-assigned on
        create and not sent in the request body.
        """
        d: dict = {
            "uid": self.uid,
            "calendarIds": self.calendar_ids,
            "title": self.title,
            "start": self.start,
            "duration": self.duration,
            "showWithoutTime": self.show_without_time,
            "sequence": self.sequence,
            "freeBusyStatus": self.free_busy_status,
            "useDefaultAlerts": self.use_default_alerts,
            "priority": self.priority,
        }
        if self.time_zone is not None:
            d["timeZone"] = self.time_zone
        if self.description is not None:
            d["description"] = self.description
        if self.locations:
            d["locations"] = self.locations
        if self.virtual_locations:
            d["virtualLocations"] = self.virtual_locations
        if self.links:
            d["links"] = self.links
        if self.keywords:
            d["keywords"] = self.keywords
        if self.participants:
            d["participants"] = self.participants
        if self.recurrence_rules:
            d["recurrenceRules"] = self.recurrence_rules
        if self.excluded_recurrence_rules:
            d["excludedRecurrenceRules"] = self.excluded_recurrence_rules
        if self.recurrence_overrides:
            d["recurrenceOverrides"] = self.recurrence_overrides
        if self.alerts:
            d["alerts"] = self.alerts
        if self.privacy is not None:
            d["privacy"] = self.privacy
        if self.color is not None:
            d["color"] = self.color
        if self.is_draft:
            d["isDraft"] = self.is_draft
        return d
