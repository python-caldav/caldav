"""
Shared test fixture helpers for both sync and async tests.

This module provides common logic for setting up test calendars,
ensuring consistent behavior and safeguards across sync and async tests.
"""

import asyncio
import inspect
import logging
import time
from typing import Any
from urllib.parse import unquote, urlparse

from caldav.compatibility_hints import write_delay
from caldav.lib.error import DAVError, NotFoundError


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


## Skip reason when _find_test_calendar() finds nothing set aside for the tests.
NO_TEST_CALENDAR = (
    "no calendar could be created and none is set aside for the tests - give a "
    "calendar the tests may wipe a display name containing 'pythoncaldav-test' "
    "or the fixture's cal_id, or name it under 'test-calendar' in the server's features"
)


async def _find_test_calendar(calendars: list[Any], cal_id: str | None = None) -> Any:
    """Find the calendar set aside for the tests, or None.

    A calendar is set aside when its URL path ends in ``cal_id`` or its display
    name contains ``pythoncaldav-test``.  Any other calendar is the user's own: the
    tests wipe the calendar they use, so it must never be picked just because
    the server lists it first.  A different calendar can be named in the
    ``test-calendar`` server config.

    Works with both sync and async calendar objects via _maybe_await.
    """
    for c in calendars:
        last_segment = urlparse(str(c.url)).path.rstrip("/").rsplit("/", 1)[-1]
        if cal_id and unquote(last_segment) == cal_id:
            return c
        try:
            display_name = await _maybe_await(c.get_display_name())
        except Exception as e:
            logging.debug(f"no display name for {c.url}: {e}")
            continue
        if "pythoncaldav-test" in str(display_name):
            return c
    return None


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

            calendar = await _find_test_calendar(calendars, cal_id)

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


def component_set_unobtainable(client: Any, comp_set: list[str] | None) -> str | None:
    """Why a calendar restricted to ``comp_set`` cannot be had, or ``None``.

    Asking for a VTODO-only (or VJOURNAL-only) calendar is how the fixtures get
    somewhere to put tasks on servers that will not mix them with events.  When
    the server also ignores the requested component set (Bedework 5: every
    calendar a client creates is VEVENT-only), there is nowhere to put them,
    and the caller should skip rather than fail on the PUT.
    """
    if not comp_set or "VEVENT" in comp_set:
        return None
    if _supports(client, "create-calendar.with-supported-component-types"):
        return None
    for component in comp_set:
        mixed = f"save-load.{component[1:].lower()}.mixed-calendar"
        if not _supports(client, mixed):
            return (
                f"server ignores supported-calendar-component-set and {component} "
                "cannot share a calendar with events"
            )
    return None


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
      on servers where deleting actually frees the URL, which is what
      ``delete-calendar.free-namespace`` records.  Two different servers fail
      that: Synology refuses the DELETE outright (``delete-calendar``
      unsupported), while Nextcloud accepts it but moves the calendar to a
      trashbin, so the id stays taken.  Either way a ``delete()`` is a no-op
      wipe, the MKCALENDAR that follows would 405 with "a collection already
      exists at that location", and the correct move is to reuse the calendar
      instead.
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

    ## Without create-calendar there is nothing to recreate, so a leftover must
    ## not be deleted - and the calendar at cal_id most likely never existed
    ## (Posteo answers the DELETE of a missing collection with 403, not 404).
    if (
        principal is not None
        and _supports(client, "create-calendar")
        and _supports(client, "delete-calendar.free-namespace")
    ):
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


async def adelete_calendar_if_present(principal: Any, cal_id: str, client: Any = None) -> None:
    """Best-effort removal of a leftover test calendar from a previous run.

    A test that recreates a calendar with a fixed ``cal_id`` must first clear
    any leftover, or the recreate MKCALENDAR 405s ("resource already exists").
    Given the ``client``, the leftover goes as adelete_test_calendar() deletes
    it: past the trashbin where a plain DELETE would keep the id taken.

    Only ``NotFoundError`` (the calendar isn't there) is swallowed - everything
    else propagates, except on that past-the-trashbin path, where a refused
    DELETE is logged rather than raised.  A previous incarnation wrapped this in a bare
    ``except Exception: pass``, which silently hid a real bug (async
    ``principal.calendar()`` raising ``TypeError``), so the cleanup never ran
    and calendars leaked.  Keep the catch narrow so that can't recur.
    """
    from caldav.lib import error

    calendar = await _maybe_await(principal.calendar(cal_id=cal_id))
    await cleanup_calendar_objects(calendar)
    try:
        if client is None:
            await _maybe_await(calendar.delete())
        else:
            await adelete_test_calendar(client, calendar)
    except error.NotFoundError:
        # Already gone, which is exactly what this function wants.  Nothing
        # wider is caught on purpose - see the docstring.
        pass


## Most calendars the functional tests create have an id starting with this.
TEST_CALENDAR_PREFIX = "pythoncaldav-"

## Nextcloud moves a deleted calendar to a trashbin, where it still counts
## towards the account's calendar limit and still holds the id; this header
## deletes it for good.  Other servers ignore it.
NO_TRASHBIN_HEADERS = {"X-NC-CalDAV-No-Trashbin": "1"}

## Servers already swept in this pytest session, by registry name.
_swept_servers: set[str] = set()


def sweep_test_calendars(client: Any, principal: Any) -> list[str]:
    """Delete every test calendar (id starting with ``pythoncaldav-``) for good.

    The fixtures leave calendars behind on purpose where deleting them would
    not free the id (wipe-calendar regime), and an interrupted run leaves them
    behind anywhere.  On accounts allowing only a handful of calendars that
    adds up, so the session sweeps them away at its start and end.

    Nothing is touched where the calendars could not be recreated: without
    calendar creation or deletion, with a calendar configured for the tests, or
    with cleanup switched off.  Returns the ids deleted.
    """
    if not (_supports(client, "create-calendar") and _supports(client, "delete-calendar")):
        return []
    test_cal_info = client.features.is_supported("test-calendar", return_type=dict)
    if test_cal_info.get("cleanup-regime") == "none" or any(
        k in test_cal_info for k in ("name", "cal_id", "cal_url")
    ):
        return []
    deleted = [
        cal_id
        for cal in principal.get_calendars()
        if (cal_id := _cal_id(cal)).startswith(TEST_CALENDAR_PREFIX)
        and delete_calendar_for_good(client, cal)
    ]
    ## A server deleting calendars asynchronously (Infomaniak) answers before
    ## the calendar is gone; a fixture re-creating the id right after would
    ## meet the old one, as Calendar.delete() knows.
    delay = write_delay(client.features, "synchronous-write.delete-calendar")
    deadline = time.monotonic() + delay
    while deleted and delay:
        if not any(_cal_id(cal) in deleted for cal in principal.get_calendars()):
            break
        if time.monotonic() >= deadline:
            logging.warning("sweep: %s still listed after %ss", deleted, delay)
            break
        time.sleep(0.5)
    return deleted


def _cal_id(cal: Any) -> str:
    return unquote(str(cal.url).rstrip("/").rsplit("/", 1)[-1])


def delete_calendar_for_good(client: Any, cal: Any) -> bool:
    """DELETE a calendar past the Nextcloud trashbin; False if refused.

    A refusal is logged, not raised: the callers clean up, and one calendar
    the server will not let go of must not stop them.
    """
    try:
        response = client.delete(str(cal.url), headers=NO_TRASHBIN_HEADERS)
    except DAVError as e:
        return _deleted_for_good(cal, e)
    return _deleted_for_good(cal, response)


async def adelete_calendar_for_good(client: Any, cal: Any) -> bool:
    """Async twin of delete_calendar_for_good()."""
    try:
        response = await _maybe_await(client.delete(str(cal.url), headers=NO_TRASHBIN_HEADERS))
    except DAVError as e:
        return _deleted_for_good(cal, e)
    return _deleted_for_good(cal, response)


def delete_test_calendar(client: Any, cal: Any) -> None:
    """Delete a calendar the tests made, freeing its id where that takes more.

    Where a plain DELETE leaves the id taken (``delete-calendar.free-namespace``
    unsupported: Nextcloud's trashbin), the calendar goes for good, so that it
    neither counts towards the account's calendar limit nor blocks the next
    MKCALENDAR of the same id.  Elsewhere Calendar.delete() does it, with its
    retries and its wait for an asynchronous deletion, or by wiping the
    objects where the server refuses to delete calendars (Synology).
    """
    if _plain_delete_will_do(client):
        cal.delete()
    else:
        delete_calendar_for_good(client, cal)


async def adelete_test_calendar(client: Any, cal: Any) -> None:
    """Async twin of delete_test_calendar()."""
    if _plain_delete_will_do(client):
        await _maybe_await(cal.delete())
    else:
        await adelete_calendar_for_good(client, cal)


def _plain_delete_will_do(client: Any) -> bool:
    return not _supports(client, "delete-calendar") or _supports(
        client, "delete-calendar.free-namespace"
    )


def _deleted_for_good(cal: Any, outcome: Any) -> bool:
    """Read a DELETE's response, or the error it raised; log a refusal."""
    if isinstance(outcome, NotFoundError):
        return True
    if isinstance(outcome, DAVError):
        logging.warning("DELETE %s refused: %s", cal.url, outcome)
        return False
    if outcome.status in (200, 204, 404):
        return True
    logging.warning("DELETE %s answered %s", cal.url, outcome.status)
    return False


def sweep_server(server_name: str) -> None:
    """Sweep the test calendars off an external test server.

    Docker and embedded servers are thrown away after the run anyway.  Best
    effort: a sweep that fails must not fail a test.
    """
    from caldav.testing.base import ExternalTestServer
    from caldav.testing.registry import get_registry

    server = get_registry().get(server_name)
    if not isinstance(server, ExternalTestServer):
        return
    try:
        with server.get_sync_client() as client:
            deleted = sweep_test_calendars(client, client.principal())
    except Exception as e:
        logging.warning("sweep of %s failed: %s", server_name, e)
        return
    if deleted:
        logging.info("sweep of %s deleted %s", server_name, deleted)


def sweep_server_once(server_name: str | None) -> None:
    """Sweep a server the first time a test in this session uses it.

    Clears leftovers from interrupted runs; conftest sweeps the same servers
    again when the session ends.
    """
    if not server_name or server_name in _swept_servers:
        return
    _swept_servers.add(server_name)
    sweep_server(server_name)


def sweep_used_servers() -> None:
    """Sweep every server swept at its first use, at the end of the session."""
    for server_name in sorted(_swept_servers):
        sweep_server(server_name)
