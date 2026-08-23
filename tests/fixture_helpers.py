"""
Shared test fixture helpers for both sync and async tests.

This module provides common logic for setting up test calendars,
ensuring consistent behavior and safeguards across sync and async tests.
"""

import asyncio
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


async def _filter_calendars_by_component_set(
    calendars: list[Any],
    supported_calendar_component_set: list[str],
) -> list[Any] | None:
    """Filter calendars by supported component set.

    Uses property lookup first, then URL-based heuristics as fallback.
    Returns None if no matching calendars found (caller should skip test).
    Works with both sync and async calendar objects via _maybe_await.
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


async def _find_test_calendar(calendars: list[Any]) -> Any:
    """Find a dedicated test calendar by display name, or return first calendar.

    Works with both sync and async calendar objects via _maybe_await.
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


async def _get_or_create_impl(
    client: Any,
    principal: Any,
    calendar_name: str | None = "pythoncaldav-test",
    cal_id: str | None = None,
    supported_calendar_component_set: list[str] | None = None,
) -> tuple[Any, bool]:
    """Shared async implementation for get_or_create_test_calendar."""
    from caldav.lib import error

    calendar = None
    created = False

    ## First of all, check if the server test config specifies that we
    ## should use a dedicated calendar.  This can be specified in the features
    ## as for now.
    test_cal_info = client.features.is_supported("test-calendar", return_type=dict)
    ## Only the keys principal.calendar() actually accepts may be forwarded - the
    ## same dict also carries bookkeeping like "support" and "cleanup-regime".
    ## cal_url is a keyword of its own and is *not* interchangeable with cal_id:
    ## it is joined against the client URL verbatim, while cal_id is URL-quoted
    ## and joined against the calendar home set (a PROPFIND on async clients).
    lookup = {k: v for k, v in test_cal_info.items() if k in ("name", "cal_id", "cal_url")}
    if lookup:
        ## TODO: we should consider some better error messages if the configured calendar
        ## does not exist
        ## A lookup by name round-trips, so on an async client this is a coroutine.
        return (await _maybe_await(principal.calendar(**lookup)), False)

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
                filtered = await _filter_calendars_by_component_set(
                    calendars, supported_calendar_component_set
                )
                if filtered is None:
                    return None, False
                calendars = filtered

            calendar = await _find_test_calendar(calendars)

    return calendar, created


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
    return asyncio.run(
        _get_or_create_impl(
            client, principal, calendar_name, cal_id, supported_calendar_component_set
        )
    )


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
    return await _get_or_create_impl(
        client, principal, calendar_name, cal_id, supported_calendar_component_set
    )


def _supports(client: Any, feature: str) -> bool:
    """Feature lookup that defaults to True when the client carries no feature set.

    A missing/empty feature set means "nothing is known about this server", and
    the fixtures have always treated that as "assume it works".
    """
    features = getattr(client, "features", None)
    return features.is_supported(feature) if features else True


async def atry_principal(client: Any) -> Any:
    """Discover the principal, or ``None`` if the server won't tell us.

    Some servers don't support principal discovery at all; the async fixtures
    treat that as "no principal" and fall back to URL-based lookups.
    """
    from caldav.aio import AsyncPrincipal
    from caldav.lib.error import AuthorizationError, NotFoundError

    try:
        return await AsyncPrincipal.create(client)
    except (NotFoundError, AuthorizationError):
        return None


async def afix_calendar(
    client: Any,
    principal: Any,
    *,
    cal_id: str,
    calendar_name: str | None = None,
    keep_name: bool = False,
    supported_calendar_component_set: list[str] | None = None,
) -> tuple[Any, bool]:
    """Async counterpart of ``test_caldav.py``'s ``_fixCalendar``.

    Hands back an *empty* test calendar at ``cal_id`` plus a flag telling
    whether it had to be created, taking care of the server-capability
    bookkeeping that every async fixture and every async test that wants its
    own calendar used to repeat inline:

    * a leftover calendar from an interrupted run is deleted first - but only
      on servers where deleting actually frees the URL.  On servers where it
      does not (``delete-calendar`` unsupported: Synology, Nextcloud), a
      ``delete()`` is a no-op wipe, the MKCALENDAR that follows would 405 with
      "a collection already exists at that location", and the correct move is
      to reuse the calendar instead.
    * the display name is dropped on servers that cannot set one, or that move
      the calendar to a server-chosen URL when one is set, and on
      component-restricted calendars - same three-legged rule as
      ``_fixCalendar_``: the fixture is always looked up by ``cal_id``.  Pass
      ``keep_name=True`` to opt out, for a test whose subject *is* the display
      name; that is the async spelling of ``_fixCalendar_``'s "only mangle the
      name when the caller did not supply one" (``if "name" not in kwargs``).
    * whatever is left inside the calendar is wiped, so the caller can count
      objects from zero whether the calendar is brand new or reused.

    Pair every call with :func:`arelease_calendar`.
    """
    from caldav.lib import error

    ## A component-restricted fixture (VTODO-only / VJOURNAL-only) is only ever
    ## found by cal_id, and naming it can collide on servers enforcing
    ## per-principal unique calendar names (SOGo) - so it stays nameless too.
    restricted = bool(supported_calendar_component_set) and (
        "VEVENT" not in supported_calendar_component_set
    )
    if (
        calendar_name is not None
        and not keep_name
        and (
            restricted
            or not _supports(client, "create-calendar.set-displayname")
            or not _supports(client, "create-calendar.stable-url")
        )
    ):
        calendar_name = None

    if principal is not None and _supports(client, "delete-calendar.free-namespace"):
        try:
            await adelete_calendar_if_present(principal, cal_id)
        except error.DeleteError:
            ## The server advertises calendar deletion but refused this one.
            ## Not fatal: get_or_create below reuses whatever is there.
            pass

    calendar, created = await aget_or_create_test_calendar(
        client,
        principal,
        calendar_name=calendar_name,
        cal_id=cal_id,
        supported_calendar_component_set=supported_calendar_component_set,
    )

    if calendar is not None:
        await cleanup_calendar_objects(calendar)

    return calendar, created


async def arelease_calendar(client: Any, calendar: Any, created: bool) -> None:
    """Tear down a calendar handed out by :func:`afix_calendar`.

    Deletes it when we created it and deletion frees the URL again; otherwise
    just empties it, so that servers moving deleted calendars to a trashbin
    (or refusing deletion outright) don't accumulate junk.
    """
    if calendar is None:
        return
    if created and _supports(client, "delete-calendar.free-namespace"):
        try:
            await _maybe_await(calendar.delete())
            return
        except Exception:
            ## Best-effort teardown: a calendar that refuses to go must not
            ## turn a passing test red.  Fall through and at least empty it.
            pass
    await cleanup_calendar_objects(calendar)


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
                # Best-effort, and deliberately broad: one object that refuses
                # to go must not stop the rest of the calendar from being
                # emptied, and every caller treats a failed cleanup as
                # acceptable.  The catch is wide enough to hide a client-side
                # bug too - see adelete_calendar_if_present() below, where
                # exactly that happened - so narrow it if you get the chance.
                pass
    except Exception:
        # Ditto for listing the calendar: if search() fails there is nothing
        # this helper can clean up, and it is not the test's business to fail
        # over it.
        pass


async def adelete_calendar_if_present(principal: Any, cal_id: str) -> None:
    """Best-effort removal of a leftover test calendar from a previous run.

    A test that recreates a calendar with a fixed ``cal_id`` must first clear
    any leftover, or the recreate MKCALENDAR 405s ("resource already exists").

    Only ``NotFoundError`` (the calendar isn't there) is swallowed - everything
    else propagates.  A previous incarnation wrapped this in a bare
    ``except Exception: pass``, which silently hid a real bug (async
    ``principal.calendar()`` raising ``TypeError``), so the cleanup never ran
    and calendars leaked.  Keep the catch narrow so that can't recur.
    """
    from caldav.lib import error

    calendar = await _maybe_await(principal.calendar(cal_id=cal_id))
    await cleanup_calendar_objects(calendar)
    try:
        await _maybe_await(calendar.delete())
    except error.NotFoundError:
        # Already gone, which is exactly what this function wants.  Nothing
        # wider is caught on purpose - see the docstring.
        pass
