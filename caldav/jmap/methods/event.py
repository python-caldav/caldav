"""
JMAP CalendarEvent method builders and response parsers.

These are pure functions — no HTTP, no state. They build the request
tuples that go into a ``methodCalls`` list, and parse the corresponding
``methodResponses`` entries.

Method shapes follow RFC 8620 §3.3 (get), §3.4 (changes), §3.5 (set),
§3.6 (query), §3.7 (queryChanges); CalendarEvent-specific properties are
defined in the JMAP Calendars specification.
"""

from __future__ import annotations

from caldav.jmap.objects.event import JMAPEvent


def build_event_get(
    account_id: str,
    ids: list[str] | None = None,
    properties: list[str] | None = None,
) -> tuple:
    """Build a ``CalendarEvent/get`` method call tuple.

    Args:
        account_id: The JMAP accountId to query.
        ids: List of event IDs to fetch, or ``None`` to fetch all.
        properties: List of property names to return, or ``None`` for all.

    Returns:
        A 3-tuple ``("CalendarEvent/get", arguments_dict, call_id)`` suitable
        for inclusion in a ``methodCalls`` list.
    """
    args: dict = {"accountId": account_id, "ids": ids}
    if properties is not None:
        args["properties"] = properties
    return ("CalendarEvent/get", args, "ev-get-0")


def parse_event_get(response_args: dict) -> list[JMAPEvent]:
    """Parse the arguments dict from a ``CalendarEvent/get`` method response.

    Args:
        response_args: The second element of a ``methodResponses`` entry
            whose method name is ``"CalendarEvent/get"``.

    Returns:
        List of :class:`~caldav.jmap.objects.event.JMAPEvent` objects.
        Returns an empty list if ``"list"`` is absent or empty.
    """
    return [JMAPEvent.from_jmap(item) for item in response_args.get("list", [])]


def build_event_changes(
    account_id: str,
    since_state: str,
    max_changes: int | None = None,
) -> tuple:
    """Build a ``CalendarEvent/changes`` method call tuple.

    Args:
        account_id: The JMAP accountId to query.
        since_state: The ``state`` string from a previous ``CalendarEvent/get``
            or ``CalendarEvent/changes`` response.
        max_changes: Optional upper bound on the number of changes returned.
            The server may return fewer.

    Returns:
        A 3-tuple ``("CalendarEvent/changes", arguments_dict, call_id)``.
    """
    args: dict = {"accountId": account_id, "sinceState": since_state}
    if max_changes is not None:
        args["maxChanges"] = max_changes
    return ("CalendarEvent/changes", args, "ev-changes-0")


def build_event_query(
    account_id: str,
    filter: dict | None = None,
    sort: list[dict] | None = None,
    position: int = 0,
    limit: int | None = None,
) -> tuple:
    """Build a ``CalendarEvent/query`` method call tuple.

    Args:
        account_id: The JMAP accountId to query.
        filter: A ``FilterCondition`` or ``FilterOperator`` dict, e.g.
            ``{"after": "2024-01-01T00:00:00Z", "before": "2024-12-31T23:59:59Z"}``.
            ``None`` means no filter (return all events).
        sort: List of ``Comparator`` dicts, e.g.
            ``[{"property": "start", "isAscending": True}]``.
            ``None`` means server default ordering.
        position: Zero-based index of the first result to return.
        limit: Maximum number of IDs to return. ``None`` means no limit.

    Returns:
        A 3-tuple ``("CalendarEvent/query", arguments_dict, call_id)``.
    """
    args: dict = {"accountId": account_id, "position": position}
    if filter is not None:
        args["filter"] = filter
    if sort is not None:
        args["sort"] = sort
    if limit is not None:
        args["limit"] = limit
    return ("CalendarEvent/query", args, "ev-query-0")


def parse_event_query(response_args: dict) -> tuple[list[str], str, int]:
    """Parse the arguments dict from a ``CalendarEvent/query`` response.

    Args:
        response_args: The second element of a ``methodResponses`` entry
            whose method name is ``"CalendarEvent/query"``.

    Returns:
        A 3-tuple ``(ids, query_state, total)``:

        - ``ids``: Ordered list of matching event IDs.
        - ``query_state``: Opaque state string for use with
          ``CalendarEvent/queryChanges``.
        - ``total``: Total number of matching events (may exceed ``len(ids)``
          when a limit was applied).
    """
    ids: list[str] = response_args.get("ids", [])
    query_state: str = response_args.get("queryState", "")
    total: int = response_args.get("total", len(ids))
    return ids, query_state, total


def build_event_query_changes(
    account_id: str,
    since_query_state: str,
    filter: dict | None = None,
    sort: list[dict] | None = None,
    max_changes: int | None = None,
) -> tuple:
    """Build a ``CalendarEvent/queryChanges`` method call tuple.

    Args:
        account_id: The JMAP accountId to query.
        since_query_state: The ``queryState`` string from a previous
            ``CalendarEvent/query`` or ``CalendarEvent/queryChanges`` response.
        filter: Same filter as the original ``CalendarEvent/query`` call.
        sort: Same sort as the original ``CalendarEvent/query`` call.
        max_changes: Optional upper bound on the number of changes returned.

    Returns:
        A 3-tuple ``("CalendarEvent/queryChanges", arguments_dict, call_id)``.
    """
    args: dict = {"accountId": account_id, "sinceQueryState": since_query_state}
    if filter is not None:
        args["filter"] = filter
    if sort is not None:
        args["sort"] = sort
    if max_changes is not None:
        args["maxChanges"] = max_changes
    return ("CalendarEvent/queryChanges", args, "ev-qchanges-0")


def build_event_set_create(
    account_id: str,
    events: dict[str, JMAPEvent],
) -> tuple:
    """Build a ``CalendarEvent/set`` method call for creating events.

    Args:
        account_id: The JMAP accountId.
        events: Map of client-assigned creation ID → :class:`JMAPEvent`.
            The creation IDs are ephemeral — they are used to correlate
            server responses with individual creation requests within the
            same batch call.

    Returns:
        A 3-tuple ``("CalendarEvent/set", arguments_dict, call_id)``.
    """
    return (
        "CalendarEvent/set",
        {
            "accountId": account_id,
            "create": {cid: ev.to_jmap() for cid, ev in events.items()},
        },
        "ev-set-create-0",
    )


def build_event_set_update(
    account_id: str,
    updates: dict[str, dict],
) -> tuple:
    """Build a ``CalendarEvent/set`` method call for updating events.

    Args:
        account_id: The JMAP accountId.
        updates: Map of event ID → partial patch dict.  Keys are property
            names (or JSON Pointer paths for nested properties); values are
            the new values.  Use ``None`` as a value to reset a property to
            its server default.

    Returns:
        A 3-tuple ``("CalendarEvent/set", arguments_dict, call_id)``.
    """
    return (
        "CalendarEvent/set",
        {"accountId": account_id, "update": updates},
        "ev-set-update-0",
    )


def build_event_set_destroy(
    account_id: str,
    ids: list[str],
) -> tuple:
    """Build a ``CalendarEvent/set`` method call for destroying events.

    Args:
        account_id: The JMAP accountId.
        ids: List of event IDs to destroy.

    Returns:
        A 3-tuple ``("CalendarEvent/set", arguments_dict, call_id)``.
    """
    return (
        "CalendarEvent/set",
        {"accountId": account_id, "destroy": ids},
        "ev-set-destroy-0",
    )


def parse_event_set(response_args: dict) -> tuple[dict, dict, list[str]]:
    """Parse the arguments dict from a ``CalendarEvent/set`` method response.

    Args:
        response_args: The second element of a ``methodResponses`` entry
            whose method name is ``"CalendarEvent/set"``.

    Returns:
        A 3-tuple ``(created, updated, destroyed)``:

        - ``created``: Map of creation ID → server-assigned event dict
          (includes the new ``id`` and any server-set properties).
          Empty dict if no creates were requested or all failed.
        - ``updated``: Map of event ID → ``null`` (per RFC 8620) or a
          partial object with server-updated properties.
          Empty dict if no updates were requested or all failed.
        - ``destroyed``: List of successfully destroyed event IDs.
    """
    created: dict = response_args.get("created") or {}
    updated: dict = response_args.get("updated") or {}
    destroyed: list[str] = response_args.get("destroyed") or []
    return created, updated, destroyed
