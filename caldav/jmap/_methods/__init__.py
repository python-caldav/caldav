def parse_set_response(response_args: dict) -> tuple[dict, dict, list[str], dict, dict, dict]:
    """Parse the arguments dict from any JMAP ``*/set`` method response.

    Returns a 6-tuple ``(created, updated, destroyed, not_created, not_updated, not_destroyed)``.
    """
    created: dict = response_args.get("created") or {}
    updated: dict = response_args.get("updated") or {}
    destroyed: list[str] = response_args.get("destroyed") or []
    not_created: dict = response_args.get("notCreated") or {}
    not_updated: dict = response_args.get("notUpdated") or {}
    not_destroyed: dict = response_args.get("notDestroyed") or {}
    return created, updated, destroyed, not_created, not_updated, not_destroyed
