"""
JMAP Task and TaskList objects.

Represents JMAP Task and TaskList resources as returned by ``Task/get`` and
``TaskList/get``. Properties follow RFC 9553 (JMAP for Tasks) and RFC 8984
(JSCalendar), extended with JMAP-specific additions.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JMAPTaskList:
    """A JMAP TaskList object.

    Attributes:
        id: Server-assigned identifier (immutable, scoped to account).
        name: Display name of the task list.
        description: Optional longer description.
        color: Optional CSS color string (e.g. ``"#ff0000"``).
        is_subscribed: Whether the user is subscribed to this list.
        my_rights: Dict of right names → bool for the current user.
        sort_order: Hint for display ordering (lower = first).
        time_zone: IANA timezone name for tasks in this list.
        role: ``"inbox"``, ``"trash"``, or ``None`` for a regular list.
    """

    id: str
    name: str
    description: str | None = None
    color: str | None = None
    is_subscribed: bool = True
    my_rights: dict = field(default_factory=dict)
    sort_order: int = 0
    time_zone: str | None = None
    role: str | None = None

    @classmethod
    def from_jmap(cls, data: dict) -> JMAPTaskList:
        """Construct a JMAPTaskList from a raw JMAP TaskList JSON dict.

        Unknown keys are silently ignored for forward compatibility.
        """
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            color=data.get("color"),
            is_subscribed=data.get("isSubscribed", True),
            my_rights=data.get("myRights", {}),
            sort_order=data.get("sortOrder", 0),
            time_zone=data.get("timeZone"),
            role=data.get("role"),
        )

    def to_jmap(self) -> dict:
        """Serialise to a JMAP TaskList JSON dict for ``TaskList/set``.

        ``id`` and ``myRights`` are intentionally excluded — both are
        server-set and must not appear in create or update payloads.
        Optional fields are included only when they hold a non-default value.
        """
        d: dict = {
            "name": self.name,
            "isSubscribed": self.is_subscribed,
            "sortOrder": self.sort_order,
        }
        if self.description is not None:
            d["description"] = self.description
        if self.color is not None:
            d["color"] = self.color
        if self.time_zone is not None:
            d["timeZone"] = self.time_zone
        if self.role is not None:
            d["role"] = self.role
        return d


@dataclass
class JMAPTask:
    """A JMAP Task object.

    Fields map to RFC 9553 (JMAP for Tasks) and RFC 8984 (JSCalendar Task).
    Only user-settable fields are stored; server-computed properties
    (``utcStart``, ``utcDue``) are not included.

    Note: ``estimatedDuration`` is the Task equivalent of an Event's
    ``duration`` — they are distinct fields with different wire names.
    ``due`` (LocalDateTime) replaces the Event's ``start + duration`` pattern.

    Attributes:
        id: Server-assigned identifier (immutable, scoped to account).
        uid: iCalendar UID — stable across copies.
        task_list_id: ID of the parent TaskList.
        title: Short summary. Maps to VTODO ``SUMMARY``.
        description: Full description. Maps to VTODO ``DESCRIPTION``.
        start: Local start date-time (no TZ suffix). Maps to VTODO ``DTSTART``.
        due: Local due date-time (no TZ suffix). Maps to VTODO ``DUE``.
        time_zone: IANA timezone name for ``start`` and ``due``.
        estimated_duration: ISO 8601 duration. Maps to VTODO ``DURATION``.
        percent_complete: Progress percentage 0–100. Maps to VTODO ``PERCENT-COMPLETE``.
        progress: Lifecycle status. Maps to VTODO ``STATUS``.
        progress_updated: UTC timestamp of last progress change.
        priority: Priority –9 to 9. Maps to VTODO ``PRIORITY``.
        is_draft: When ``True``, server suppresses alerts and scheduling messages.
        keywords: Tag set (map of string → ``True``). Maps to VTODO ``CATEGORIES``.
        recurrence_rules: List of RecurrenceRule dicts.
        recurrence_overrides: Map of LocalDateTime → patch dict.
        alerts: Map of alert id → alert dict.
        participants: Map of participant id → participant dict.
        color: Optional CSS color hint.
        privacy: Optional visibility level (``"public"``, ``"private"``, ``"secret"``).
    """

    id: str
    uid: str
    task_list_id: str
    title: str = ""
    description: str | None = None
    start: str | None = None
    due: str | None = None
    time_zone: str | None = None
    estimated_duration: str | None = None
    percent_complete: int = 0
    progress: str = "needs-action"
    progress_updated: str | None = None
    priority: int = 0
    is_draft: bool = False
    keywords: dict = field(default_factory=dict)
    recurrence_rules: list = field(default_factory=list)
    recurrence_overrides: dict = field(default_factory=dict)
    alerts: dict = field(default_factory=dict)
    participants: dict = field(default_factory=dict)
    color: str | None = None
    privacy: str | None = None

    @classmethod
    def from_jmap(cls, data: dict) -> JMAPTask:
        """Construct a JMAPTask from a raw JMAP Task JSON dict.

        ``id``, ``uid``, and ``taskListId`` are required; a missing key raises
        ``KeyError``. Unknown keys are silently ignored for forward compatibility.
        """
        return cls(
            id=data["id"],
            uid=data["uid"],
            task_list_id=data["taskListId"],
            title=data.get("title", ""),
            description=data.get("description"),
            start=data.get("start"),
            due=data.get("due"),
            time_zone=data.get("timeZone"),
            estimated_duration=data.get("estimatedDuration"),
            percent_complete=data.get("percentComplete", 0),
            progress=data.get("progress", "needs-action"),
            progress_updated=data.get("progressUpdated"),
            priority=data.get("priority", 0),
            is_draft=data.get("isDraft", False),
            keywords=data.get("keywords") or {},
            recurrence_rules=data.get("recurrenceRules") or [],
            recurrence_overrides=data.get("recurrenceOverrides") or {},
            alerts=data.get("alerts") or {},
            participants=data.get("participants") or {},
            color=data.get("color"),
            privacy=data.get("privacy"),
        )

    def to_jmap(self) -> dict:
        """Serialise to a JMAP Task JSON dict for ``Task/set``.

        Includes ``@type: "Task"`` — the server requires this discriminator to
        distinguish Task from CalendarEvent in mixed-type contexts.

        ``id`` is intentionally excluded — it is server-assigned on create.
        Optional fields are included only when they hold a non-default value.
        """
        d: dict = {
            "@type": "Task",
            "uid": self.uid,
            "taskListId": self.task_list_id,
            "title": self.title,
            "percentComplete": self.percent_complete,
            "progress": self.progress,
            "priority": self.priority,
        }
        if self.description is not None:
            d["description"] = self.description
        if self.start is not None:
            d["start"] = self.start
        if self.due is not None:
            d["due"] = self.due
        if self.time_zone is not None:
            d["timeZone"] = self.time_zone
        if self.estimated_duration is not None:
            d["estimatedDuration"] = self.estimated_duration
        if self.progress_updated is not None:
            d["progressUpdated"] = self.progress_updated
        if self.is_draft:
            d["isDraft"] = self.is_draft
        if self.keywords:
            d["keywords"] = self.keywords
        if self.recurrence_rules:
            d["recurrenceRules"] = self.recurrence_rules
        if self.recurrence_overrides:
            d["recurrenceOverrides"] = self.recurrence_overrides
        if self.alerts:
            d["alerts"] = self.alerts
        if self.participants:
            d["participants"] = self.participants
        if self.color is not None:
            d["color"] = self.color
        if self.privacy is not None:
            d["privacy"] = self.privacy
        return d
