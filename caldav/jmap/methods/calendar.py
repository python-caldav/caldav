"""
JMAP Calendar method builders and response parsers.

These are pure functions — no HTTP, no state. They build the request
tuples that go into a ``methodCalls`` list, and parse the corresponding
``methodResponses`` entries.

Method shapes follow RFC 8620 §3.3 (get), §3.4 (changes), §3.5 (set); Calendar-specific
properties are defined in the JMAP Calendars specification.
"""

from __future__ import annotations

from caldav.jmap.objects.calendar import JMAPCalendar


def build_calendar_get(
    account_id: str,
    ids: list[str] | None = None,
    properties: list[str] | None = None,
) -> tuple:
    """Build a ``Calendar/get`` method call tuple.

    Args:
        account_id: The JMAP accountId to query.
        ids: List of calendar IDs to fetch, or ``None`` to fetch all.
        properties: List of property names to return, or ``None`` for all.

    Returns:
        A 3-tuple ``("Calendar/get", arguments_dict, call_id)`` suitable
        for inclusion in a ``methodCalls`` list.
    """
    args: dict = {"accountId": account_id, "ids": ids}
    if properties is not None:
        args["properties"] = properties
    return ("Calendar/get", args, "cal-get-0")


def parse_calendar_get(response_args: dict) -> list[JMAPCalendar]:
    """Parse the arguments dict from a ``Calendar/get`` method response.

    Args:
        response_args: The second element of a ``methodResponses`` entry
            whose method name is ``"Calendar/get"``.

    Returns:
        List of :class:`~caldav.jmap.objects.calendar.JMAPCalendar` objects.
        Returns an empty list if ``"list"`` is absent or empty.
    """
    return [JMAPCalendar.from_jmap(item) for item in response_args.get("list", [])]


def build_calendar_changes(account_id: str, since_state: str) -> tuple:
    """Build a ``Calendar/changes`` method call tuple.

    Args:
        account_id: The JMAP accountId to query.
        since_state: The ``state`` string from a previous ``Calendar/get``
            or ``Calendar/changes`` response.

    Returns:
        A 3-tuple ``("Calendar/changes", arguments_dict, call_id)``.
    """
    return (
        "Calendar/changes",
        {"accountId": account_id, "sinceState": since_state},
        "cal-changes-0",
    )
