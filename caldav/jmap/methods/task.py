"""
JMAP Task and TaskList method builders and response parsers.

These are pure functions — no HTTP, no state. They build the request
tuples that go into a ``methodCalls`` list, and parse the corresponding
``methodResponses`` entries.

Method shapes follow RFC 8620 §3.3 (get), §3.5 (set); Task-specific
properties are defined in RFC 9553 (JMAP for Tasks).
"""

from __future__ import annotations

from caldav.jmap.objects.task import JMAPTask, JMAPTaskList


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


def parse_task_list_get(response_args: dict) -> list[JMAPTaskList]:
    """Parse the arguments dict from a ``TaskList/get`` method response.

    Args:
        response_args: The second element of a ``methodResponses`` entry
            whose method name is ``"TaskList/get"``.

    Returns:
        List of :class:`~caldav.jmap.objects.task.JMAPTaskList` objects.
        Returns an empty list if ``"list"`` is absent or empty.
    """
    return [JMAPTaskList.from_jmap(item) for item in response_args.get("list", [])]


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


def parse_task_get(response_args: dict) -> list[JMAPTask]:
    """Parse the arguments dict from a ``Task/get`` method response.

    Args:
        response_args: The second element of a ``methodResponses`` entry
            whose method name is ``"Task/get"``.

    Returns:
        List of :class:`~caldav.jmap.objects.task.JMAPTask` objects.
        Returns an empty list if ``"list"`` is absent or empty.
    """
    return [JMAPTask.from_jmap(item) for item in response_args.get("list", [])]


def build_task_set_create(
    account_id: str,
    tasks: dict[str, JMAPTask],
) -> tuple:
    """Build a ``Task/set`` method call for creating tasks.

    Args:
        account_id: The JMAP accountId.
        tasks: Map of client-assigned creation ID → :class:`JMAPTask`.

    Returns:
        A 3-tuple ``("Task/set", arguments_dict, call_id)``.
    """
    return (
        "Task/set",
        {
            "accountId": account_id,
            "create": {cid: task.to_jmap() for cid, task in tasks.items()},
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

    Args:
        response_args: The second element of a ``methodResponses`` entry
            whose method name is ``"Task/set"``.

    Returns:
        A 6-tuple ``(created, updated, destroyed, not_created, not_updated, not_destroyed)``:

        - ``created``: Map of creation ID → server-assigned task dict.
        - ``updated``: Map of task ID → null or partial server-updated object.
        - ``destroyed``: List of successfully destroyed task IDs.
        - ``not_created``: Map of creation ID → SetError dict for failed creates.
        - ``not_updated``: Map of task ID → SetError dict for failed updates.
        - ``not_destroyed``: Map of task ID → SetError dict for failed destroys.
    """
    created: dict = response_args.get("created") or {}
    updated: dict = response_args.get("updated") or {}
    destroyed: list[str] = response_args.get("destroyed") or []
    not_created: dict = response_args.get("notCreated") or {}
    not_updated: dict = response_args.get("notUpdated") or {}
    not_destroyed: dict = response_args.get("notDestroyed") or {}
    return created, updated, destroyed, not_created, not_updated, not_destroyed
