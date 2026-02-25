"""
Shared test fixture helpers for both sync and async tests.

This module provides common logic for setting up test calendars,
ensuring consistent behavior and safeguards across sync and async tests.
"""

import inspect
from typing import Any


async def _maybe_await(result: Any) -> Any:
    """Await if result is awaitable, otherwise return as-is."""
    if inspect.isawaitable(result):
        return await result
    return result


def _build_make_calendar_kwargs(
    calendar_name: str | None,
    cal_id: str | None,
    supported_calendar_component_set: list[str] | None,
) -> dict[str, Any]:
    """Build kwargs dict for principal.make_calendar()."""
    kwargs: dict[str, Any] = {}
    if calendar_name is not None:
        kwargs["name"] = calendar_name
    if cal_id:
        kwargs["cal_id"] = cal_id
    if supported_calendar_component_set:
        kwargs["supported_calendar_component_set"] = supported_calendar_component_set
    return kwargs


def _filter_calendars_by_url_heuristic(
    calendars: list[Any],
    supported_calendar_component_set: list[str],
) -> list[Any]:
    """URL/name pattern heuristics fallback for component set filtering.

    Some servers (e.g. Zimbra) don't return the supported-calendar-component-set
    property, so we fall back to matching on URL path patterns.
    """
    matching = []
    for c in calendars:
        url_path = str(c.url).lower()
        if "VTODO" in supported_calendar_component_set:
            if "/tasks/" in url_path or "_tasks/" in url_path:
                matching.append(c)
        elif "VJOURNAL" in supported_calendar_component_set:
            if "/journal" in url_path or "_journal" in url_path:
                matching.append(c)
    return matching


def _filter_calendars_by_component_set(
    calendars: list[Any],
    supported_calendar_component_set: list[str],
    get_properties_fn: Any = None,
) -> list[Any] | None:
    """Filter calendars by supported component set.

    Uses property lookup first, then URL-based heuristics as fallback.
    Returns None if no matching calendars found (caller should skip test).

    Args:
        calendars: List of calendar objects to filter
        supported_calendar_component_set: Required component types
        get_properties_fn: Callable that takes (calendar, keys) and returns
            properties dict. If None, uses calendar.get_properties() directly.
    """
    comp_set_key = "{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set"

    matching_calendars = []
    for c in calendars:
        try:
            if get_properties_fn:
                props = get_properties_fn(c, [comp_set_key])
            else:
                props = c.get_properties([comp_set_key])
            cal_components = props.get(comp_set_key, [])
            if cal_components and all(
                comp in cal_components for comp in supported_calendar_component_set
            ):
                matching_calendars.append(c)
        except Exception:
            pass

    if not matching_calendars:
        matching_calendars = _filter_calendars_by_url_heuristic(
            calendars, supported_calendar_component_set
        )

    return matching_calendars or None


def _find_test_calendar(
    calendars: list[Any],
    get_properties_fn: Any = None,
) -> Any:
    """Find a dedicated test calendar by display name, or return first calendar.

    Args:
        calendars: List of calendar objects to search
        get_properties_fn: Callable that takes (calendar, keys) and returns
            properties dict. If None, uses calendar.get_properties() directly.
    """
    for c in calendars:
        try:
            if get_properties_fn:
                props = get_properties_fn(c, [])
            else:
                props = c.get_properties([])
            display_name = props.get("{DAV:}displayname", "")
            if "pythoncaldav-test" in str(display_name):
                return c
        except Exception:
            pass
    return calendars[0] if calendars else None


def get_or_create_test_calendar(
    client: Any,
    principal: Any,
    calendar_name: str | None = "pythoncaldav-test",
    cal_id: str | None = None,
    supported_calendar_component_set: list[str] | None = None,
) -> tuple[Any, bool]:
    """
    Get or create a test calendar (sync version), with fallback to existing calendars.

    Args:
        client: The DAV client
        principal: The principal object (or None to skip principal-based creation)
        calendar_name: Name for the test calendar, or None to skip setting name
        cal_id: Optional calendar ID
        supported_calendar_component_set: Component types this calendar should support

    Returns:
        Tuple of (calendar, was_created) where was_created indicates if
        we created the calendar (and should clean it up) or are using
        an existing one.
    """
    from caldav.lib import error

    calendar = None
    created = False

    ## First of all, check if the server test config specifies that we
    ## should use a dedicated calendar.  This can be specified in the features
    ## as for now.
    test_cal_info = client.features.is_supported("test-calendar", return_type=dict)
    if "name" in test_cal_info or "cal_url" in test_cal_info or "cal_id" in test_cal_info:
        ## TODO: we should consider some better error messages if the configured calendar
        ## does not exist
        return (principal.calendar(**test_cal_info), False)

    # Check if server supports calendar creation via features
    supports_create = True
    if hasattr(client, "features") and client.features:
        supports_create = client.features.is_supported("create-calendar")

    if supports_create and principal is not None:
        try:
            kwargs = _build_make_calendar_kwargs(
                calendar_name, cal_id, supported_calendar_component_set
            )
            calendar = principal.make_calendar(**kwargs)
            created = True
        except (error.MkcalendarError, error.AuthorizationError, error.NotFoundError):
            # Creation failed - try to get by cal_id if available
            if cal_id:
                try:
                    calendar = principal.calendar(cal_id=cal_id)
                except Exception:
                    pass

    if calendar is None:
        # Fall back to finding an existing calendar
        calendars = None

        if principal is not None:
            try:
                calendars = principal.get_calendars()
            except (error.NotFoundError, error.AuthorizationError):
                pass

        if calendars:
            if supported_calendar_component_set:
                filtered = _filter_calendars_by_component_set(
                    calendars, supported_calendar_component_set
                )
                if filtered is None:
                    return None, False
                calendars = filtered

            calendar = _find_test_calendar(calendars)

    return calendar, created


async def _afilter_calendars_by_component_set(
    calendars: list[Any],
    supported_calendar_component_set: list[str],
) -> list[Any] | None:
    """Async version of _filter_calendars_by_component_set.

    Uses async property lookup first, then URL-based heuristics as fallback.
    Returns None if no matching calendars found (caller should skip test).
    """
    comp_set_key = "{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set"

    matching_calendars = []
    for c in calendars:
        try:
            props = await _maybe_await(c.get_properties([comp_set_key]))
            cal_components = props.get(comp_set_key, [])
            if cal_components and all(
                comp in cal_components for comp in supported_calendar_component_set
            ):
                matching_calendars.append(c)
        except Exception:
            pass

    if not matching_calendars:
        matching_calendars = _filter_calendars_by_url_heuristic(
            calendars, supported_calendar_component_set
        )

    return matching_calendars or None


async def _afind_test_calendar(calendars: list[Any]) -> Any:
    """Async version of _find_test_calendar.

    Find a dedicated test calendar by display name, or return first calendar.
    """
    for c in calendars:
        try:
            props = await _maybe_await(c.get_properties([]))
            display_name = props.get("{DAV:}displayname", "")
            if "pythoncaldav-test" in str(display_name):
                return c
        except Exception:
            pass
    return calendars[0] if calendars else None


async def aget_or_create_test_calendar(
    client: Any,
    principal: Any,
    calendar_name: str | None = "pythoncaldav-test",
    cal_id: str | None = None,
    supported_calendar_component_set: list[str] | None = None,
) -> tuple[Any, bool]:
    """
    Get or create a test calendar (async version), with fallback to existing calendars.

    Args:
        client: The DAV client (sync or async)
        principal: The principal object (or None to skip principal-based creation)
        calendar_name: Name for the test calendar, or None to skip setting name
        cal_id: Optional calendar ID
        supported_calendar_component_set: Component types this calendar should support

    Returns:
        Tuple of (calendar, was_created) where was_created indicates if
        we created the calendar (and should clean it up) or are using
        an existing one.
    """
    from caldav.lib import error

    calendar = None
    created = False

    ## Check if the server test config specifies a dedicated calendar
    ## (mirrors the sync version)
    test_cal_info = client.features.is_supported("test-calendar", return_type=dict)
    if "name" in test_cal_info or "cal_url" in test_cal_info or "cal_id" in test_cal_info:
        return (principal.calendar(**test_cal_info), False)

    # Check if server supports calendar creation via features
    supports_create = True
    if hasattr(client, "features") and client.features:
        supports_create = client.features.is_supported("create-calendar")

    if supports_create and principal is not None:
        try:
            kwargs = _build_make_calendar_kwargs(
                calendar_name, cal_id, supported_calendar_component_set
            )
            calendar = await _maybe_await(principal.make_calendar(**kwargs))
            created = True
        except (error.MkcalendarError, error.AuthorizationError, error.NotFoundError):
            # Creation failed - try to get by cal_id if available
            if cal_id:
                try:
                    calendar = await _maybe_await(principal.calendar(cal_id=cal_id))
                except Exception:
                    pass

    if calendar is None:
        # Fall back to finding an existing calendar
        calendars = None

        if principal is not None:
            try:
                calendars = await _maybe_await(principal.get_calendars())
            except (error.NotFoundError, error.AuthorizationError):
                pass

        if calendars:
            if supported_calendar_component_set:
                filtered = await _afilter_calendars_by_component_set(
                    calendars, supported_calendar_component_set
                )
                if filtered is None:
                    return None, False
                calendars = filtered

            calendar = await _afind_test_calendar(calendars)

    return calendar, created


async def cleanup_calendar_objects(calendar: Any) -> None:
    """
    Remove all objects from a calendar (for test isolation).

    Args:
        calendar: The calendar to clean up
    """
    try:
        objects = await _maybe_await(calendar.search())
        for obj in objects:
            try:
                await _maybe_await(obj.delete())
            except Exception:
                pass
    except Exception:
        pass
