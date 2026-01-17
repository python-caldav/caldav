"""
Shared test fixture helpers for both sync and async tests.

This module provides common logic for setting up test calendars,
ensuring consistent behavior and safeguards across sync and async tests.
"""
import inspect
from typing import Any
from typing import Optional


async def _maybe_await(result: Any) -> Any:
    """Await if result is awaitable, otherwise return as-is."""
    if inspect.isawaitable(result):
        return await result
    return result


async def get_or_create_test_calendar(
    client: Any,
    principal: Any,
    calendar_name: str = "pythoncaldav-test",
    cal_id: Optional[str] = None,
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
            calendar = await _maybe_await(
                principal.make_calendar(name=calendar_name, cal_id=cal_id)
            )
            created = True
        except (error.MkcalendarError, error.AuthorizationError, error.NotFoundError):
            # Creation failed - fall back to finding existing calendar
            pass

    if calendar is None:
        # Fall back to finding an existing calendar
        calendars = None

        if principal is not None:
            try:
                calendars = await _maybe_await(principal.calendars())
            except (error.NotFoundError, error.AuthorizationError):
                pass

        if calendars:
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
            if calendar is None:
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
