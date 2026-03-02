"""
JMAP Task and TaskList method builders and response parsers.

These are pure functions — no HTTP, no state. They build the request
tuples that go into a ``methodCalls`` list, and parse the corresponding
``methodResponses`` entries.

Method shapes follow RFC 8620 §3.3 (get), §3.5 (set); Task-specific
properties are defined in draft-ietf-jmap-tasks (built on RFC 8984).
"""

from __future__ import annotations

from caldav.jmap._methods import parse_set_response


def build_task_list_get(
    account_id: str,
    ids: list[str] | None = None,
    properties: list[str] | None = None,
) -> tuple:
    """Build a ``TaskList/get`` method call tuple.

    Args:
        account_id: The JMAP accountId to query.
        ids: List of task list IDs to fetch, or ``None`` to fetch all.
        properties: List of property names to return, or ``None`` for all.

    Returns:
        A 3-tuple ``("TaskList/get", arguments_dict, call_id)`` suitable
        for inclusion in a ``methodCalls`` list.
    """
    args: dict = {"accountId": account_id, "ids": ids}
    if properties is not None:
        args["properties"] = properties
    return ("TaskList/get", args, "tasklist-get-0")


def parse_task_list_get(response_args: dict) -> list[dict]:
    """Parse the arguments dict from a ``TaskList/get`` method response.

    Args:
        response_args: The second element of a ``methodResponses`` entry
            whose method name is ``"TaskList/get"``.

    Returns:
        List of raw JMAP TaskList dicts as returned by the server.
        Returns an empty list if ``"list"`` is absent or empty.
    """
    return list(response_args.get("list", []))


def build_task_get(
    account_id: str,
    ids: list[str] | None = None,
    properties: list[str] | None = None,
) -> tuple:
    """Build a ``Task/get`` method call tuple.

    Args:
        account_id: The JMAP accountId to query.
        ids: List of task IDs to fetch, or ``None`` to fetch all.
        properties: List of property names to return, or ``None`` for all.

    Returns:
        A 3-tuple ``("Task/get", arguments_dict, call_id)``.
    """
    args: dict = {"accountId": account_id, "ids": ids}
    if properties is not None:
        args["properties"] = properties
    return ("Task/get", args, "task-get-0")


def parse_task_get(response_args: dict) -> list[dict]:
    """Parse the arguments dict from a ``Task/get`` method response.

    Args:
        response_args: The second element of a ``methodResponses`` entry
            whose method name is ``"Task/get"``.

    Returns:
        List of raw JMAP Task dicts as returned by the server.
        Returns an empty list if ``"list"`` is absent or empty.
    """
    return list(response_args.get("list", []))


def build_task_set_create(
    account_id: str,
    tasks: dict[str, dict],
) -> tuple:
    """Build a ``Task/set`` method call for creating tasks.

    Args:
        account_id: The JMAP accountId.
        tasks: Map of client-assigned creation ID → JMAP Task dict.

    Returns:
        A 3-tuple ``("Task/set", arguments_dict, call_id)``.
    """
    return (
        "Task/set",
        {
            "accountId": account_id,
            "create": dict(tasks),
        },
        "task-set-create-0",
    )


def build_task_set_update(
    account_id: str,
    updates: dict[str, dict],
) -> tuple:
    """Build a ``Task/set`` method call for updating tasks.

    Args:
        account_id: The JMAP accountId.
        updates: Map of task ID → partial patch dict.

    Returns:
        A 3-tuple ``("Task/set", arguments_dict, call_id)``.
    """
    return (
        "Task/set",
        {"accountId": account_id, "update": updates},
        "task-set-update-0",
    )


def build_task_set_destroy(
    account_id: str,
    ids: list[str],
) -> tuple:
    """Build a ``Task/set`` method call for destroying tasks.

    Args:
        account_id: The JMAP accountId.
        ids: List of task IDs to destroy.

    Returns:
        A 3-tuple ``("Task/set", arguments_dict, call_id)``.
    """
    return (
        "Task/set",
        {"accountId": account_id, "destroy": ids},
        "task-set-destroy-0",
    )


def parse_task_set(
    response_args: dict,
) -> tuple[dict, dict, list[str], dict, dict, dict]:
    """Parse the arguments dict from a ``Task/set`` method response.

    Returns a 6-tuple ``(created, updated, destroyed, not_created, not_updated, not_destroyed)``.
    See :func:`caldav.jmap._methods.parse_set_response` for field semantics.
    """
    return parse_set_response(response_args)
