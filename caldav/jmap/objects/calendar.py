"""
JMAP Calendar object.

Represents a JMAP Calendar resource as returned by ``Calendar/get``.
Properties are defined in the JMAP Calendars specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
        """Serialise to a JMAP Calendar JSON dict.

        Only includes fields that are non-None so that the output can be
        used directly in ``Calendar/set`` create/update patches.
        """
        d: dict = {
            "id": self.id,
            "name": self.name,
            "isSubscribed": self.is_subscribed,
            "myRights": self.my_rights,
            "sortOrder": self.sort_order,
            "isVisible": self.is_visible,
        }
        if self.description is not None:
            d["description"] = self.description
        if self.color is not None:
            d["color"] = self.color
        return d
