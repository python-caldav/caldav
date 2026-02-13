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


async def get_or_create_test_calendar(
    client: Any,
    principal: Any,
    calendar_name: str = "pythoncaldav-test",
    cal_id: str | None = None,
    supported_calendar_component_set: list[str] | None = None,
) -> tuple[Any, bool]:
    """
    Get or create a test calendar, with fallback to existing calendars.

    This implements the same logic as the sync _fixCalendar_ method,
    providing safeguards against accidentally overwriting user data.

    Args:
        client: The DAV client (sync or async)
        principal: The principal object (or None to skip principal-based creation)
        calendar_name: Name for the test calendar
        cal_id: Optional calendar ID
        supported_calendar_component_set: Component types this calendar should support
            (e.g., ["VTODO"] for task lists, ["VEVENT"] for event calendars).
            Important for servers like Zimbra that don't support mixed calendars.

    Returns:
        Tuple of (calendar, was_created) where was_created indicates if
        we created the calendar (and should clean it up) or are using
        an existing one.
    """
    from caldav.lib import error

    calendar = None
    created = False

    # Check if server supports calendar creation via features
    supports_create = True
    if hasattr(client, "features") and client.features:
        supports_create = client.features.is_supported("create-calendar")

    if supports_create and principal is not None:
        # Try to create a new calendar
        try:
            kwargs: dict[str, Any] = {"name": calendar_name}
            if cal_id:
                kwargs["cal_id"] = cal_id
            if supported_calendar_component_set:
                kwargs["supported_calendar_component_set"] = supported_calendar_component_set
            calendar = await _maybe_await(principal.make_calendar(**kwargs))
            created = True
        except (error.MkcalendarError, error.AuthorizationError, error.NotFoundError):
            # Creation failed - fall back to finding existing calendar
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
            # Property key for supported component set
            comp_set_key = "{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set"

            # If we need specific component support, filter calendars
            if supported_calendar_component_set:
                matching_calendars = []
                for c in calendars:
                    try:
                        props = await _maybe_await(c.get_properties([comp_set_key]))
                        cal_components = props.get(comp_set_key, [])
                        # Check if calendar supports all required components
                        if cal_components and all(
                            comp in cal_components for comp in supported_calendar_component_set
                        ):
                            matching_calendars.append(c)
                    except Exception:
                        pass

                # If no matching calendars found by component set, try heuristics
                # based on URL/name patterns (some servers like Zimbra don't return
                # the supported-calendar-component-set property)
                if not matching_calendars:
                    for c in calendars:
                        url_path = str(c.url).lower()
                        # For VTODO, look for task-related calendars
                        if "VTODO" in supported_calendar_component_set:
                            if "/tasks/" in url_path or "_tasks/" in url_path:
                                matching_calendars.append(c)
                        # For VJOURNAL, look for journal-related calendars
                        elif "VJOURNAL" in supported_calendar_component_set:
                            if "/journal" in url_path or "_journal" in url_path:
                                matching_calendars.append(c)

                # Only use matching calendars - if none found, return None
                # (caller should skip the test)
                if not matching_calendars:
                    return None, False
                calendars = matching_calendars

            # Look for a dedicated test calendar first
            for c in calendars:
                try:
                    props = await _maybe_await(c.get_properties([]))
                    display_name = props.get("{DAV:}displayname", "")
                    if "pythoncaldav-test" in str(display_name):
                        calendar = c
                        break
                except Exception:
                    pass

            # Fall back to first calendar
            if calendar is None and calendars:
                calendar = calendars[0]

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
