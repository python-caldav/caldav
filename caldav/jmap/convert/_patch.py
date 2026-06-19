"""
RFC 8620 PatchObject helpers for CalendarEvent/set update calls.

When updating an event, absent keys preserve the server's current value.
To delete an optional property the patch must set it to null explicitly.
"""

from __future__ import annotations

# Optional JSCalendar top-level properties that must be explicitly nulled in
# a CalendarEvent/set update when they are absent from the converted result.
# This ensures properties removed client-side (e.g. LOCATION deleted from
# the iCalendar) are actually removed on the server, not silently preserved.
_NULL_FOR_UPDATE: frozenset[str] = frozenset(
    {
        "description",
        "color",
        "locations",
        "keywords",
        "priority",
        "privacy",
        "freeBusyStatus",
        "status",
        "sequence",
        "showWithoutTime",
        "timeZone",
        "recurrenceRules",
        "excludedRecurrenceRules",
        "recurrenceOverrides",
        "participants",
        "alerts",
    }
)
