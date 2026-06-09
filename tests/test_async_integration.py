#!/usr/bin/env python
"""
Functional integration tests for the async API.

These tests verify that the async API works correctly with real CalDAV servers.
They run against all available servers (Radicale, Xandikos, Docker servers)
using the same dynamic class generation pattern as the sync tests.
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from typing import Any

import icalendar
import pytest
import pytest_asyncio

from caldav import Event, FreeBusy, Todo
from caldav.compatibility_hints import FeatureSet

from .test_caldav import (
    ev1 as ev1_static,  # old-date (2006); distinct from ev1() near-future generator
)
from .test_caldav import ev2 as ev2_static  # same UID as ev1_static, one year later
from .test_caldav import ev3 as ev3_static  # different UID (2021)
from .test_caldav import evr as evr_static  # recurring annual event (1997)
from .test_caldav import evr2 as evr2_static  # bi-weekly with exception (2024)
from .test_caldav import journal as journal_static
from .test_caldav import (
    near_now_ics,  # shift an ical event's DTSTART/DTEND to ~now (sliding-window servers)
    next_anniversary_windows,  # near-future search windows for a FREQ=YEARLY event
)
from .test_caldav import todo as todo_static  # avoids clash with local var in add_todo()
from .test_caldav import todo2 as todo2_static  # avoids clash with todo2() generator
from .test_caldav import todo3 as todo3_static
from .test_caldav import todo4 as todo4_static
from .test_caldav import todo5 as todo5_static
from .test_caldav import todo6 as todo6_static
from .test_caldav import todo8 as todo8_static
from .test_servers import TestServer, get_available_servers


def _async_delay_decorator(f, t=20):
    """
    Async decorator that adds a delay before calling the wrapped coroutine.

    This is needed for servers like Bedework that have a search cache that
    isn't immediately updated when objects are created/modified.
    """

    @wraps(f)
    async def wrapper(*args, **kwargs):
        await asyncio.sleep(t)
        return await f(*args, **kwargs)

    return wrapper


# Dynamic test data generators - use near-future dates to avoid
# min-date-time restrictions on servers like CCS.
_base_date = None


def _get_base_date() -> datetime:
    """Return a stable base date for the current test session (tomorrow at noon UTC)."""
    global _base_date
    if _base_date is None:
        tomorrow = datetime.now(tz=timezone.utc).date() + timedelta(days=1)
        _base_date = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 12, 0, 0)
    return _base_date


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def make_event(uid: str, summary: str, dtstart: datetime, dtend: datetime) -> str:
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{_fmt(datetime.now(tz=timezone.utc))}
DTSTART:{_fmt(dtstart)}
DTEND:{_fmt(dtend)}
SUMMARY:{summary}
END:VEVENT
END:VCALENDAR"""


def make_todo(uid: str, summary: str, status: str = "NEEDS-ACTION") -> str:
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:{uid}
DTSTAMP:{_fmt(datetime.now(tz=timezone.utc))}
SUMMARY:{summary}
STATUS:{status}
END:VTODO
END:VCALENDAR"""


def ev1() -> str:
    base = _get_base_date()
    return make_event(
        f"async-test-event-001-{uuid.uuid4()}@example.com",
        "Async Test Event",
        base,
        base + timedelta(hours=11),
    )


def ev2() -> str:
    base = _get_base_date()
    return make_event(
        f"async-test-event-002-{uuid.uuid4()}@example.com",
        "Second Async Test Event",
        base + timedelta(days=1),
        base + timedelta(days=1, hours=11),
    )


def todo1() -> str:
    return make_todo(f"async-test-todo-001-{uuid.uuid4()}@example.com", "Async Test Todo")


def todo2() -> str:
    return make_todo(
        f"async-test-todo-002-{uuid.uuid4()}@example.com", "Completed Async Todo", "COMPLETED"
    )


async def add_event(calendar: Any, data: str) -> Any:
    """Helper to add an event to a calendar."""
    from caldav.aio import AsyncEvent

    event = AsyncEvent(parent=calendar, data=data)
    await event.save()
    return event


async def add_todo(calendar: Any, data: str) -> Any:
    """Helper to add a todo to a calendar."""
    from caldav.aio import AsyncTodo

    todo = AsyncTodo(parent=calendar, data=data)
    await todo.save()
    return todo


class AsyncFunctionalTestsBaseClass:
    """
    Base class for async functional tests.

    This class contains test methods that will be run against each
    configured test server. Subclasses are dynamically generated
    for each server (similar to the sync test pattern).
    """

    # Server configuration - set by dynamic class generation
    server: TestServer

    @property
    def _features(self):
        """Cached FeatureSet from server config."""
        if not hasattr(self.__class__, "_feature_set_cache"):
            features = self.server.features
            if isinstance(features, str):
                import caldav.compatibility_hints

                name = features
                if name.startswith("compatibility_hints."):
                    name = name[len("compatibility_hints.") :]
                features = getattr(caldav.compatibility_hints, name)
            self.__class__._feature_set_cache = FeatureSet(features)
        return self.__class__._feature_set_cache

    def is_supported(self, feature, return_type=bool, accept_fragile=False):
        return self._features.is_supported(feature, return_type, accept_fragile=accept_fragile)

    def skip_unless_support(self, feature):
        if not self.is_supported(feature):
            msg = self._features.find_feature(feature).get("description", feature)
            pytest.skip("Test skipped due to server incompatibility issue: " + msg)

    def check_compatibility_flag(self, flag: str) -> bool:
        return flag in getattr(self._features, "_old_flags", [])

    @pytest.fixture(scope="class")
    def test_server(self) -> TestServer:
        """Get the test server for this class."""
        server = self.server
        server.start()
        yield server
        # Stop the server to free the port for other test modules
        server.stop()

    @pytest_asyncio.fixture
    async def async_client(self, test_server: TestServer, monkeypatch: Any) -> Any:
        """Create an async client connected to the test server."""
        from caldav.aio import AsyncCalendar

        client = await test_server.get_async_client()

        # Apply search-cache delay if needed (similar to sync tests)
        # Use monkeypatch so it's automatically reverted after the test
        # (AsyncCalendar is an alias for Calendar, so we must restore it)
        search_cache_config = client.features.is_supported("search-cache", dict)
        if search_cache_config.get("behaviour") == "delay":
            delay = search_cache_config.get("delay", 1.5)
            monkeypatch.setattr(
                AsyncCalendar,
                "search",
                _async_delay_decorator(AsyncCalendar.search, t=delay),
            )

        yield client
        await client.close()

    @pytest_asyncio.fixture
    async def async_principal(self, async_client: Any) -> Any:
        """Get the principal for the async client."""
        from caldav.aio import AsyncPrincipal
        from caldav.lib.error import NotFoundError

        try:
            # Try standard principal discovery
            principal = await AsyncPrincipal.create(async_client)
        except NotFoundError:
            # Some servers (like Radicale with no auth) don't support
            # principal discovery. Fall back to using the client URL directly.
            principal = AsyncPrincipal(client=async_client, url=async_client.url)
        return principal

    @pytest_asyncio.fixture
    async def async_calendar(self, async_client: Any) -> Any:
        """Create or find a stable test calendar, wiping it before and after use.

        Uses a stable cal_id so the calendar is reused across tests.  For servers
        where deletion moves calendars to a trashbin (e.g. Nextcloud), we wipe
        objects only rather than deleting the calendar, keeping the trashbin empty.
        """
        from caldav.aio import AsyncPrincipal
        from caldav.lib.error import AuthorizationError, NotFoundError

        from .fixture_helpers import aget_or_create_test_calendar, cleanup_calendar_objects

        feats = getattr(async_client, "features", None)

        def _feat(name: str) -> bool:
            return feats.is_supported(name) if feats else True

        delete_frees_namespace = _feat("delete-calendar.free-namespace")

        principal = None
        try:
            principal = await AsyncPrincipal.create(async_client)
        except (NotFoundError, AuthorizationError):
            pass

        calendar, created = await aget_or_create_test_calendar(
            async_client,
            principal,
            calendar_name="pythoncaldav-async-test",
            cal_id="pythoncaldav-async-test",
        )

        if calendar is None:
            pytest.skip("Could not create or find a calendar for testing")

        await cleanup_calendar_objects(calendar)

        yield calendar

        if delete_frees_namespace and created:
            try:
                await calendar.delete()
            except Exception:
                pass
        else:
            await cleanup_calendar_objects(calendar)

    @pytest_asyncio.fixture
    async def async_task_list(self, async_client: Any) -> Any:
        """Create or find a stable task-list calendar, wiping it before and after use.

        For servers that don't support mixed calendars (e.g. Zimbra), a VTODO-only
        calendar is used.  The calendar is reused across tests via a stable cal_id
        rather than being deleted and recreated, avoiding trashbin accumulation on
        servers like Nextcloud.
        """
        from caldav.aio import AsyncPrincipal
        from caldav.lib.error import AuthorizationError, NotFoundError

        from .fixture_helpers import aget_or_create_test_calendar, cleanup_calendar_objects

        feats = getattr(async_client, "features", None)

        def _feat(name: str) -> bool:
            return feats.is_supported(name) if feats else True

        supports_mixed = _feat("save-load.todo.mixed-calendar")
        delete_frees_namespace = _feat("delete-calendar.free-namespace")

        component_set: list[str] | None = ["VTODO"] if not supports_mixed else None
        cal_id = "pythoncaldav-async-test-tasks"
        supports_displayname = _feat("create-calendar.set-displayname")
        calendar_name = cal_id if supports_displayname else None

        principal = None
        try:
            principal = await AsyncPrincipal.create(async_client)
        except (NotFoundError, AuthorizationError):
            pass

        calendar, created = await aget_or_create_test_calendar(
            async_client,
            principal,
            calendar_name=calendar_name,
            cal_id=cal_id,
            supported_calendar_component_set=component_set,
        )

        if calendar is None:
            pytest.skip("Could not create or find a task list for testing")

        await cleanup_calendar_objects(calendar)

        yield calendar

        if delete_frees_namespace and created:
            try:
                await calendar.delete()
            except Exception:
                pass
        else:
            await cleanup_calendar_objects(calendar)

    @pytest_asyncio.fixture
    async def async_calendar2(self, async_client: Any) -> Any:
        """Create or find a stable second test calendar for tests needing two calendars."""
        from caldav.aio import AsyncPrincipal
        from caldav.lib.error import AuthorizationError, NotFoundError

        from .fixture_helpers import aget_or_create_test_calendar, cleanup_calendar_objects

        feats = getattr(async_client, "features", None)

        def _feat(name: str) -> bool:
            return feats.is_supported(name) if feats else True

        delete_frees_namespace = _feat("delete-calendar.free-namespace")

        principal = None
        try:
            principal = await AsyncPrincipal.create(async_client)
        except (NotFoundError, AuthorizationError):
            pass

        calendar, created = await aget_or_create_test_calendar(
            async_client,
            principal,
            calendar_name="pythoncaldav-async-test-2",
            cal_id="pythoncaldav-async-test-2",
        )

        if calendar is None:
            pytest.skip("Could not create or find a second calendar for testing")

        await cleanup_calendar_objects(calendar)

        yield calendar

        if delete_frees_namespace and created:
            try:
                await calendar.delete()
            except Exception:
                pass
        else:
            await cleanup_calendar_objects(calendar)

    @pytest_asyncio.fixture
    async def async_journal_list(self, async_client: Any) -> Any:
        """Create or find a stable VJOURNAL calendar, wiping it before and after use."""
        from caldav.aio import AsyncPrincipal
        from caldav.lib.error import AuthorizationError, NotFoundError

        from .fixture_helpers import aget_or_create_test_calendar, cleanup_calendar_objects

        feats = getattr(async_client, "features", None)

        def _feat(name: str) -> bool:
            return feats.is_supported(name) if feats else True

        delete_frees_namespace = _feat("delete-calendar.free-namespace")
        supports_displayname = _feat("create-calendar.set-displayname")
        cal_id = "pythoncaldav-async-journal"
        calendar_name = cal_id if supports_displayname else None

        principal = None
        try:
            principal = await AsyncPrincipal.create(async_client)
        except (NotFoundError, AuthorizationError):
            pass

        calendar, created = await aget_or_create_test_calendar(
            async_client,
            principal,
            calendar_name=calendar_name,
            cal_id=cal_id,
            supported_calendar_component_set=["VJOURNAL"],
        )

        if calendar is None:
            pytest.skip("Could not create or find a journal list for testing")

        await cleanup_calendar_objects(calendar)

        yield calendar

        if delete_frees_namespace and created:
            try:
                await calendar.delete()
            except Exception:
                pass
        else:
            await cleanup_calendar_objects(calendar)

    async def _make_async_client_with_params(self, **overrides: Any) -> Any:
        """Build a fresh async client from this server's config with kwargs overridden.

        Used by auth-error tests (wrong password, wrong auth type) that need a
        client that is expected to fail to connect.
        """
        from caldav.aio import get_async_davclient

        kwargs: dict[str, Any] = {
            "url": self.server.url,
            "username": self.server.username,
            "password": self.server.password,
            "features": self.server.features,
            "probe": False,
        }
        if "ssl_verify_cert" in self.server.config:
            kwargs["ssl_verify_cert"] = self.server.config["ssl_verify_cert"]
        kwargs.update(overrides)
        return await get_async_davclient(**kwargs)

    # ==================== Test Methods ====================

    @pytest.mark.asyncio
    async def test_principal_calendars(self, async_client: Any) -> None:
        """Test getting calendars from calendar home."""
        from caldav.aio import AsyncCalendarSet

        # Use calendar set at client URL to get calendars
        # This bypasses principal discovery which some servers don't support
        calendar_home = AsyncCalendarSet(client=async_client, url=async_client.url)
        calendars = await calendar_home.get_calendars()
        assert isinstance(calendars, list)

    @pytest.mark.asyncio
    async def test_principal_make_calendar(self, async_client: Any) -> None:
        """Test creating and deleting a calendar."""
        self.skip_unless_support("create-calendar")

        from caldav.aio import AsyncCalendarSet, AsyncPrincipal
        from caldav.lib.error import AuthorizationError, MkcalendarError, NotFoundError

        from .fixture_helpers import cleanup_calendar_objects

        cal_id = "pythoncaldav-async-test"
        calendar = None
        principal = None

        # Try principal-based calendar creation (most servers)
        try:
            principal = await AsyncPrincipal.create(async_client)
            calendar = await principal.make_calendar(name="Async Test", cal_id=cal_id)
        except (MkcalendarError, AuthorizationError):
            # Calendar already exists from a previous run - reuse it
            # (mirrors sync _fixCalendar_ pattern)
            if principal is not None:
                calendar = principal.calendar(cal_id=cal_id)
        except NotFoundError:
            # Principal discovery failed
            pass

        if calendar is None:
            # Fall back to CalendarSet at client URL (e.g. Radicale)
            calendar_home = AsyncCalendarSet(client=async_client, url=async_client.url)
            try:
                calendar = await calendar_home.make_calendar(name="Async Test", cal_id=cal_id)
            except (MkcalendarError, AuthorizationError):
                calendar = async_client.calendar(cal_id=cal_id)

        assert calendar is not None
        assert calendar.url is not None

        # Clean up based on server capabilities
        if self.is_supported("delete-calendar"):
            await calendar.delete()
        else:
            # Can't delete the calendar, just wipe its objects
            await cleanup_calendar_objects(calendar)

    @pytest.mark.asyncio
    async def test_search_events(self, async_calendar: Any) -> None:
        """Test searching for events."""
        from caldav.aio import AsyncEvent

        # Add test events
        await add_event(async_calendar, ev1())
        await add_event(async_calendar, ev2())

        # Search for all events
        events = await async_calendar.search(event=True)

        assert len(events) >= 2
        assert all(isinstance(e, AsyncEvent) for e in events)

    @pytest.mark.asyncio
    async def test_search_events_by_date_range(self, async_calendar: Any) -> None:
        """Test searching for events in a date range."""
        # Add test event
        await add_event(async_calendar, ev1())

        # Search for events in the date range (covers ev1's day)
        base = _get_base_date()
        events = await async_calendar.search(
            event=True,
            start=base - timedelta(hours=1),
            end=base + timedelta(days=1),
        )

        assert len(events) >= 1
        assert "Async Test Event" in events[0].data

    @pytest.mark.asyncio
    async def test_search_without_comptype_with_date_range(self, async_calendar: Any) -> None:
        """Async mirror of testSearchWithoutCompTypeWithDateRange.

        Test for https://github.com/python-caldav/caldav/issues/681

        A time-range search that does NOT specify a component type must work
        even on SabreDAV-based servers (Baikal, Nextcloud, ...) which - correctly
        per RFC4791 section 9.7 - reject a CALDAV:time-range placed directly under
        VCALENDAR with HTTP 400.  The library works around this by splitting the
        search into one query per component type.

        The search is run twice: once with the server's real feature
        configuration, and once with search.time-range.comp-type-optional forced
        to "supported", exercising the reactive HTTP-400 fallback.
        """
        self.skip_unless_support("search.time-range.event")
        base = _get_base_date()
        uid = f"issue681-async-{uuid.uuid4()}@example.com"
        await add_event(
            async_calendar,
            make_event(
                uid,
                "issue 681 async comp-type-less time-range",
                base,
                base + timedelta(hours=1),
            ),
        )

        start = base - timedelta(hours=1)
        end = base + timedelta(days=1)

        async def _assert_event_found():
            ## must not raise (the crux of issue #681) and must find the event
            objects = await async_calendar.search(start=start, end=end)
            assert [o for o in objects if uid in o.data], (
                "comp-type-less time-range search did not return the event"
            )

        ## Run 1: the server's real feature configuration (proactive comp-type split)
        await _assert_event_found()

        ## Determine how this server reacts to the raw comp-type-less time-range
        ## query.  Only SabreDAV-style servers reject it with a ReportError (HTTP
        ## 400) - the case the reactive fallback (issue #681 item 4) recovers from.
        ## Others return nothing or a different error (e.g. Cyrus may answer 403),
        ## where forcing the feature on is an unrecoverable misconfiguration.
        from caldav.lib import error

        try:
            await async_calendar.search(start=start, end=end, compatibility_workarounds=False)
            raw_report_error = False
        except error.ReportError:
            raw_report_error = True
        except error.DAVError:
            raw_report_error = False

        ## Run 2 (only meaningful where the raw query raises a ReportError): force
        ## the feature ON and verify the reactive fallback recovers and finds the event.
        if raw_report_error:
            features = async_calendar.client.features
            key = "search.time-range.comp-type-optional"
            had_key = key in features._server_features
            saved = features._server_features.get(key)
            features.set_feature(key, {"support": "full"})
            try:
                objects = await async_calendar.search(start=start, end=end)
                assert [o for o in objects if uid in o.data], (
                    "reactive fallback did not recover the comp-type-less time-range search"
                )
            finally:
                if had_key:
                    features._server_features[key] = saved
                else:
                    features._server_features.pop(key, None)

    @pytest.mark.asyncio
    async def test_search_without_comptype_with_category(self, async_calendar: Any) -> None:
        """Async mirror of testSearchWithoutCompTypeWithCategory.

        Test for https://github.com/python-caldav/caldav/issues/681

        A property filter (CATEGORIES) without a component type must work.  Under
        the VCALENDAR comp-filter it targets VCALENDAR's own properties (no
        CATEGORIES), so servers match nothing; the library splits the search into
        one query per component type (search.text.comp-type-optional unsupported).
        """
        self.skip_unless_support("search.text.category")
        base = _get_base_date()
        category = "issue681cat" + uuid.uuid4().hex[:8]
        uid = f"issue681cat-async-{uuid.uuid4()}@example.com"
        data = make_event(
            uid,
            "issue 681 async comp-type-less category search",
            base,
            base + timedelta(hours=1),
        ).replace("END:VEVENT", f"CATEGORIES:{category}\nEND:VEVENT")
        await add_event(async_calendar, data)

        ## Only the proactive split is testable here: servers silently return
        ## nothing for a prop-filter under VCALENDAR (no error to recover from).
        objects = await async_calendar.search(category=category)
        assert [o for o in objects if uid in o.data], (
            "comp-type-less category search did not return the event"
        )

    @pytest.mark.asyncio
    async def test_search_todos_pending(self, async_task_list: Any) -> None:
        """Test searching for pending todos."""
        from caldav.aio import AsyncTodo

        # Add pending and completed todos
        await add_todo(async_task_list, todo1())
        await add_todo(async_task_list, todo2())

        # Search for pending todos only (default)
        todos = await async_task_list.search(todo=True, include_completed=False)

        # Should only get the pending todo
        assert len(todos) >= 1
        assert all(isinstance(t, AsyncTodo) for t in todos)
        assert any("NEEDS-ACTION" in t.data for t in todos)

    @pytest.mark.asyncio
    async def test_search_todos_all(self, async_task_list: Any) -> None:
        """Test searching for all todos including completed."""
        # Add pending and completed todos
        await add_todo(async_task_list, todo1())
        await add_todo(async_task_list, todo2())

        # Search for all todos
        todos = await async_task_list.search(todo=True, include_completed=True)

        # Should get both todos
        assert len(todos) >= 2

    @pytest.mark.asyncio
    async def test_events_method(self, async_calendar: Any) -> None:
        """Test the events() convenience method."""
        from caldav.aio import AsyncEvent

        # Add test events
        await add_event(async_calendar, ev1())
        await add_event(async_calendar, ev2())

        # Get all events
        events = await async_calendar.get_events()

        assert len(events) >= 2
        assert all(isinstance(e, AsyncEvent) for e in events)

    @pytest.mark.asyncio
    async def test_todos_method(self, async_task_list: Any) -> None:
        """Test the todos() convenience method."""
        from caldav.aio import AsyncTodo

        # Add test todos
        await add_todo(async_task_list, todo1())

        # Get all pending todos
        todos = await async_task_list.get_todos()

        assert len(todos) >= 1
        assert all(isinstance(t, AsyncTodo) for t in todos)

    @pytest.mark.asyncio
    async def test_add_organizer_no_arg(self, async_client: Any, async_calendar: Any) -> None:
        """add_organizer() without args returns a coroutine and sets ORGANIZER (issue #524).

        Verifies the async fix: on an AsyncDAVClient principal() is a coroutine
        function, so add_organizer() must await it via _async_add_organizer()
        rather than calling it synchronously (which would raise AttributeError
        on the returned coroutine object).
        """
        from caldav import Event

        self.skip_unless_support("scheduling.calendar-user-address-set")

        principal = await async_client.principal()
        expected_vcal = await principal._async_get_vcal_address()

        event = Event(client=async_client, data=ev1(), parent=async_calendar)

        ## Must return a coroutine, not raise AttributeError
        coro = event.add_organizer()
        assert asyncio.iscoroutine(coro), (
            f"add_organizer() on async client must return a coroutine, got {type(coro)}"
        )
        await coro

        org = event.icalendar_component.get("organizer")
        assert org is not None, "ORGANIZER must be set after awaiting add_organizer()"
        assert str(org) == str(expected_vcal), (
            f"ORGANIZER {org!r} should match the principal's address {expected_vcal!r}"
        )

    # ==================== Group A – Core CRUD ====================

    @pytest.mark.asyncio
    async def test_get_supported_components(self, async_calendar: Any) -> None:
        """get_supported_components() must include VEVENT."""
        components = await async_calendar.get_supported_components()
        assert components
        assert "VEVENT" in components

    @pytest.mark.asyncio
    async def test_lookup_event(self, async_calendar: Any) -> None:
        """Add an event and look it up by URL, by UID, and via Event(url=…).load()."""
        from caldav import Event
        from caldav.lib import error

        self.skip_unless_support("save-load.event")
        c = async_calendar

        # create the event (near-now date so it stays visible to REPORT-based
        # lookups on sliding-window servers; see near_now_ics)
        e1 = await c.add_event(near_now_ics(ev1_static))
        assert e1.url is not None

        # Verify that we can look it up from calendar by url
        e2 = await c.event_by_url(e1.url)
        assert e2.vobject_instance.vevent.uid == e1.vobject_instance.vevent.uid
        assert e2.url == e1.url

        # look up by UID
        e3 = await c.get_event_by_uid("20010712T182145Z-123401@example.com")
        assert str(e3.icalendar_component["uid"]) == "20010712T182145Z-123401@example.com"
        ## get_event_by_uid may return a different (canonical) URL than the PUT
        ## URL on servers that don't preserve it (e.g. OX); see save-load.stable-url
        if self.is_supported("save-load.stable-url"):
            assert e3.url == e1.url

        # load directly from URL without going through the calendar object
        e4 = Event(client=c.client, url=e1.url)
        await e4.load()
        assert str(e4.icalendar_component["uid"]) == "20010712T182145Z-123401@example.com"

        with pytest.raises(error.NotFoundError):
            await c.get_event_by_uid("nonexistent-uid-000")

    @pytest.mark.asyncio
    async def test_create_overwrite_delete_event(self, async_calendar: Any) -> None:
        """no_create/no_overwrite flags, same-UID overwrite, and delete."""
        from caldav.lib import error

        self.skip_unless_support("save-load.event")
        c = async_calendar

        ## near-now date so the event stays visible to REPORT-based lookups on
        ## sliding-window servers (e.g. OX); see near_now_ics
        ev1_now = near_now_ics(ev1_static)

        # attempting to update a non-existing event must raise ConsistencyError
        with pytest.raises(error.ConsistencyError):
            await c.add_event(ev1_now, no_create=True)

        # no_create + no_overwrite is always an error
        with pytest.raises(error.ConsistencyError):
            await c.add_event(ev1_now, no_create=True, no_overwrite=True)

        e1 = await c.add_event(ev1_now)
        assert e1.url is not None

        # same UID again → overwrite (unless server forbids it).  Overwriting via
        # a fresh PUT without an If-Match etag is gated on save-load.mutable.if-match-optional:
        # OX enforces optimistic concurrency and rejects such a PUT with 409.
        if self.is_supported("save-load.mutable") and self.is_supported(
            "save-load.mutable.if-match-optional"
        ):
            e2 = await c.add_event(ev1_now)

            # no_create on an existing event must succeed
            e2 = await c.add_event(ev1_now, no_create=True)

            # modify and save with no_create
            e2.icalendar_component["summary"] = "Bastille Day Party!"
            await e2.save(no_create=True)

            e3 = await c.event_by_url(e1.url)
            assert e3.icalendar_component["summary"] == "Bastille Day Party!"

        # no_overwrite on an existing event must raise ConsistencyError
        with pytest.raises(error.ConsistencyError):
            await c.add_event(ev1_now, no_overwrite=True)

        await e1.delete()

        with pytest.raises(error.NotFoundError):
            await c.event_by_url(e1.url)
        with pytest.raises(error.NotFoundError):
            await c.get_event_by_uid("20010712T182145Z-123401@example.com")

    @pytest.mark.asyncio
    async def test_object_by_uid(self, async_task_list: Any) -> None:
        """Add a TODO with a known UID and retrieve it via get_object_by_uid()."""
        import uuid

        from caldav.lib import error

        c = async_task_list

        ## Use a random UID to avoid cross-run 409 conflicts on servers like OX App Suite.
        ##
        ## TODO: OX silently fails to delete VTODO-only calendars (calendar.delete() swallows
        ## the error), so the fixture teardown falls back to cleanup_calendar_objects().  OX's
        ## REPORT/sliding-window search ignores undated TODOs, so a fixed UID like
        ## "well_known_1" would survive across test sessions and cause a 409 on re-add.
        ## OX also enforces unique UIDs cross-calendar (save.duplicate-uid.cross-calendar:
        ## ungraceful), so a pre-delete in just the task-list calendar is insufficient.
        ## Better long-term fixes:
        ##   A) A caldav-server-tester check that verifies calendar.delete() on a VTODO-only
        ##      calendar actually frees the namespace; expose the OX limitation as a feature
        ##      flag so the fixture can pick a safer cleanup strategy.
        ##   B) Change the fixture teardown to attempt deletion regardless of `created` when
        ##      delete_frees_namespace=True, so a prior silent-delete failure is recovered
        ##      on the next run.
        uid = f"caldav-test-{uuid.uuid4()}"
        uid_prefix = uid[:16]
        uid_suffix = uid[17:]

        await c.add_todo(summary="Some test task with a well-known uid", uid=uid)

        foo = await c.get_object_by_uid(uid)
        assert str(foo.icalendar_component["summary"]) == "Some test task with a well-known uid"

        # prefix match must NOT succeed
        with pytest.raises(error.NotFoundError):
            await c.get_object_by_uid(uid_prefix)

        # suffix match must NOT succeed
        with pytest.raises(error.NotFoundError):
            await c.get_object_by_uid(uid_suffix)

        await foo.delete()

    @pytest.mark.asyncio
    async def test_load_event(self, async_calendar: Any, async_calendar2: Any) -> None:
        """add_event() returns an object; load() must populate it."""
        self.skip_unless_support("save-load.event")
        self.skip_unless_support("create-calendar")

        c1 = async_calendar

        e1_ = await c1.add_event(near_now_ics(ev1_static))
        await e1_.load()  # load the object returned by add_event

        events = await c1.get_events()
        assert len(events) >= 1
        e1 = events[0]
        await e1.load()  # load a freshly fetched handle
        ## e1 came from a search and may carry a different (canonical) URL than
        ## the PUT URL on servers that don't preserve it (e.g. OX); see
        ## save-load.stable-url
        if self.is_supported("save-load.stable-url"):
            assert e1.url == e1_.url

    @pytest.mark.asyncio
    async def test_copy_event(self, async_calendar: Any, async_calendar2: Any) -> None:
        """copy() within same calendar and cross-calendar."""
        self.skip_unless_support("save-load.event")
        self.skip_unless_support("create-calendar")

        c1 = async_calendar
        c2 = async_calendar2

        e1_ = await c1.add_event(near_now_ics(ev1_static))
        events = await c1.get_events()
        e1 = events[0]

        # duplicate in same calendar with a new UID
        e1_dup = e1.copy()
        await e1_dup.save()
        assert len(await c1.get_events()) == 2

        # copy cross-calendar keeping the same UID
        if self.is_supported("save.duplicate-uid.cross-calendar"):
            e1_in_c2 = e1.copy(new_parent=c2, keep_uid=True)
            await e1_in_c2.save()
            assert len(await c2.get_events()) == 1

            # modifying the copy in c2 must not affect c1's event
            e1_in_c2.icalendar_component["summary"] = "asdf"
            await e1_in_c2.save()
            await e1.load()
            assert str(e1.icalendar_component["summary"]) == "Bastille Day Party"

        # copy in same calendar keeping UID — same-UID PUT is a no-op / overwrite
        e1_dup2 = e1.copy(keep_uid=True)
        await e1_dup2.save()
        # count should still be 2 (not 3) because same UID overwrites
        assert len(await c1.get_events()) == 2

    @pytest.mark.asyncio
    async def test_multi_get(self, async_calendar: Any) -> None:
        """multiget() retrieves multiple events in one request."""
        self.skip_unless_support("save-load.event")

        c = async_calendar

        event1 = await c.add_event(
            uid="test-multiget-1",
            dtstart=datetime(2015, 1, 1, 8, 0, 0),
            dtend=datetime(2015, 1, 1, 9, 0, 0),
            summary="test-multiget-1",
        )
        event2 = await c.add_event(
            uid="test-multiget-2",
            dtstart=datetime(2015, 1, 1, 8, 0, 0),
            dtend=datetime(2015, 1, 1, 9, 0, 0),
            summary="test-multiget-2",
        )

        results = await c.multiget([event1.url, event2.url])
        assert len(results) == 2
        uids = {str(r.icalendar_component["uid"]) for r in results}
        assert uids == {"test-multiget-1", "test-multiget-2"}

        await event1.load_by_multiget()

    # ==================== Group B – Sync Tokens ====================

    @pytest.mark.asyncio
    async def test_object_by_sync_token(self, async_calendar: Any) -> None:
        """Sync-token cycle via get_objects_by_sync_token()."""
        self.skip_unless_support("save-load.event")

        c = async_calendar

        sync_info = self.is_supported("sync-token", return_type=dict)
        is_time_based = sync_info.get("behaviour") == "time-based"
        is_fragile = sync_info.get("support") in (
            "fragile",
            "broken",
            "unsupported",
            "ungraceful",
        )

        objcnt = 0
        if self.is_supported("save-load.todo.mixed-calendar"):
            objcnt += len(await c.get_todos())
        objcnt += len(await c.get_events())

        obj = await c.add_event(near_now_ics(ev1_static))
        objcnt += 1
        if self.is_supported("save-load.event.recurrences"):
            await c.add_event(evr_static)
            objcnt += 1
        if self.is_supported("save-load.todo.mixed-calendar"):
            await c.add_todo(todo_static)
            await c.add_todo(todo2_static)
            await c.add_todo(todo3_static)
            objcnt += 3

        if is_time_based:
            await asyncio.sleep(1)

        my_objects = await c.objects()
        assert my_objects.sync_token != ""
        assert len(list(my_objects)) == objcnt

        is_using_fallback = my_objects.sync_token.startswith("fake-")
        if not is_using_fallback:
            for some_obj in my_objects:
                assert some_obj.data is None

        if is_time_based:
            await asyncio.sleep(1)

        my_changed_objects = await c.get_objects_by_sync_token(sync_token=my_objects.sync_token)
        if not is_fragile:
            assert len(list(my_changed_objects)) == 0

        self.skip_unless_support("save-load.mutable")

        if is_time_based:
            await asyncio.sleep(1)
        obj.icalendar_instance.subcomponents[0]["SUMMARY"] = "foobar"
        await obj.save()

        if is_time_based:
            await asyncio.sleep(1)

        my_changed_objects = await c.get_objects_by_sync_token(
            sync_token=my_changed_objects.sync_token, load_objects=True
        )
        if is_fragile:
            assert len(list(my_changed_objects)) >= 1
        else:
            assert len(list(my_changed_objects)) == 1
        assert list(my_changed_objects)[0].data is not None

        if is_time_based:
            await asyncio.sleep(1)

        my_changed_objects = await c.get_objects_by_sync_token(
            sync_token=my_changed_objects.sync_token
        )
        if not is_fragile:
            assert len(list(my_changed_objects)) == 0

        if is_time_based:
            await asyncio.sleep(1)
        obj3 = await c.add_event(near_now_ics(ev3_static))
        if is_time_based:
            await asyncio.sleep(1)
        my_changed_objects = await c.get_objects_by_sync_token(
            sync_token=my_changed_objects.sync_token
        )
        if not is_fragile:
            assert len(list(my_changed_objects)) == 1

        if is_time_based:
            await asyncio.sleep(1)

        my_changed_objects = await c.get_objects_by_sync_token(
            sync_token=my_changed_objects.sync_token
        )
        if not is_fragile:
            assert len(list(my_changed_objects)) == 0

        if is_time_based:
            await asyncio.sleep(1)

        await obj.delete()
        self.skip_unless_support("sync-token.delete")

        if is_time_based:
            await asyncio.sleep(1)
        my_changed_objects = await c.get_objects_by_sync_token(
            sync_token=my_changed_objects.sync_token, load_objects=True
        )
        if not is_fragile:
            assert len(list(my_changed_objects)) == 1
        if is_time_based:
            await asyncio.sleep(1)
        assert list(my_changed_objects)[0].data is None

        my_changed_objects = await c.get_objects_by_sync_token(
            sync_token=my_changed_objects.sync_token
        )
        if not is_fragile:
            assert len(list(my_changed_objects)) == 0

    @pytest.mark.asyncio
    async def test_sync(self, async_calendar: Any) -> None:
        """Sync-token cycle via SynchronizableCalendarObjectCollection.sync()."""
        self.skip_unless_support("save-load.event")

        c = async_calendar

        sync_info = self.is_supported("sync-token", return_type=dict)
        is_time_based = sync_info.get("behaviour") == "time-based"
        is_fragile = sync_info.get("support") in (
            "fragile",
            "broken",
            "unsupported",
            "ungraceful",
        )

        objcnt = 0
        if self.is_supported("save-load.todo.mixed-calendar"):
            objcnt += len(await c.get_todos())
        objcnt += len(await c.get_events())

        obj = await c.add_event(near_now_ics(ev1_static))
        objcnt += 1
        if self.is_supported("save-load.event.recurrences"):
            await c.add_event(evr_static)
            objcnt += 1
        if self.is_supported("save-load.todo.mixed-calendar"):
            await c.add_todo(todo_static)
            await c.add_todo(todo2_static)
            await c.add_todo(todo3_static)
            objcnt += 3

        if is_time_based:
            await asyncio.sleep(1)

        my_objects = await c.objects(load_objects=True)
        assert my_objects.sync_token != ""
        assert len(list(my_objects)) == objcnt

        stable_url = self.is_supported("save-load.stable-url")

        def synced_match(o):
            """Return the synced object corresponding to o, or None.

            objects_by_url() is keyed by the server-reported URL, which on
            servers that don't preserve the PUT URL (e.g. OX; see
            save-load.stable-url) differs from o.url - so fall back to matching
            by UID there.
            """
            synced = my_objects.objects_by_url()
            if stable_url:
                return synced.get(o.url)
            uid = o.icalendar_component["uid"]
            return next(
                (cand for cand in synced.values() if cand.icalendar_component["uid"] == uid),
                None,
            )

        if is_time_based:
            await asyncio.sleep(1)

        updated, deleted = await my_objects.sync()
        if not is_fragile:
            assert len(list(updated)) == 0
            assert len(list(deleted)) == 0

        if is_time_based:
            await asyncio.sleep(1)

        self.skip_unless_support("save-load.mutable")

        obj.icalendar_instance.subcomponents[0]["SUMMARY"] = "foobar"
        await obj.save()

        if is_time_based:
            await asyncio.sleep(1)

        updated, deleted = await my_objects.sync()
        if not is_fragile:
            assert len(list(updated)) == 1
            assert len(list(deleted)) == 0
        assert "foobar" in synced_match(obj).data

        if is_time_based:
            await asyncio.sleep(1)

        obj3 = await c.add_event(near_now_ics(ev3_static))

        if is_time_based:
            await asyncio.sleep(1)

        updated, deleted = await my_objects.sync()
        if not is_fragile:
            assert len(list(updated)) == 1
            assert len(list(deleted)) == 0
        assert synced_match(obj3) is not None

        self.skip_unless_support("sync-token.delete")

        if is_time_based:
            await asyncio.sleep(1)

        await obj.delete()
        if is_time_based:
            await asyncio.sleep(1)
        updated, deleted = await my_objects.sync()
        if not is_fragile:
            assert len(list(updated)) == 0
            assert len(list(deleted)) == 1
        assert synced_match(obj) is None

        if is_time_based:
            await asyncio.sleep(1)

        updated, deleted = await my_objects.sync()
        if not is_fragile:
            assert len(list(updated)) == 0
            assert len(list(deleted)) == 0

    # ==================== Group C – Search ====================

    @pytest.mark.asyncio
    async def test_search_should_yield_data(self, async_calendar: Any) -> None:
        """search(event=True) must return objects with non-empty .data."""
        self.skip_unless_support("search.unlimited-time-range")
        c = async_calendar
        if self.is_supported("save-load.event"):
            await c.add_event(ev1_static)
            await c.add_event(ev2_static)
            await c.add_event(ev3_static)
        objects = await c.search(event=True)
        assert objects
        assert objects[0].data

    @pytest.mark.asyncio
    async def test_search_event(self, async_calendar: Any) -> None:
        """Comprehensive event search: UID, class, category, text, sort."""
        self.skip_unless_support("save-load.event")
        self.skip_unless_support("search")
        self.skip_unless_support("search.time-range.event.old-dates")
        c = async_calendar

        await c.add_event(ev1_static)
        await c.add_event(ev3_static)
        await c.add_event(evr_static)

        all_events = await c.search()
        assert len(all_events) <= 3

        all_events = await c.search(comp_class=Event)
        assert len(all_events) == 3

        try:
            no_events = await c.search(todo=True)
        except Exception:
            no_events = []
        assert len(no_events) == 0

        some_events = await c.search(
            comp_class=Event,
            expand=False,
            start=datetime(2006, 7, 13, 13, 0),
            end=datetime(2006, 7, 15, 13, 0),
        )
        assert len(some_events) == 1

        some_events = await c.search(comp_class=Event, uid="19970901T130000Z-123403@example.com")
        assert len(some_events) == 1

        some_events = await c.search(comp_class=Event, class_="CONFIDENTIAL")
        assert len(some_events) == 1

        some_events = await c.search(comp_class=Event, no_class=True)
        assert (
            len(some_events) == 2
            or len([x for x in all_events if x.icalendar_component["class"] == "PUBLIC"]) == 2
        )

        some_events = await c.search(comp_class=Event, no_category=True)
        assert len(some_events) == 2

        some_events = await c.search(comp_class=Event, no_dtend=True)
        assert len(some_events) == 1

        some_events = await c.search(comp_class=Event, category="PERSONAL")
        assert len(some_events) == 1

        some_events = await c.search(comp_class=Event, summary="Bastille Day Party")
        assert len(some_events) == 1

        all_events = await c.search(sort_keys=("DTSTART",))
        assert len(all_events) == 3
        assert str(all_events[0].icalendar_component["DTSTART"].dt) < str(
            all_events[1].icalendar_component["DTSTART"].dt
        )

    @pytest.mark.asyncio
    async def test_search_comp_type(self, async_calendar: Any) -> None:
        """get_events() and get_todos() must filter by component type."""
        self.skip_unless_support("save-load.todo")
        self.skip_unless_support("save-load.event")
        self.skip_unless_support("save-load.todo.mixed-calendar")
        c = async_calendar

        event = await c.add_event(
            summary="Test Event for Component-Type Filtering",
            dtstart=datetime(2025, 1, 1, 12, 0, 0),
            dtend=datetime(2025, 1, 1, 13, 0, 0),
        )
        todo_obj = await c.add_todo(
            summary="Test TODO for Component-Type Filtering",
            dtstart=date(2025, 1, 2),
        )

        events = await c.get_events()
        event_summaries = [e.component["summary"] for e in events]
        todos = await c.get_todos(include_completed=True)
        todo_summaries = [t.component["summary"] for t in todos]

        assert "Test Event for Component-Type Filtering" in event_summaries
        assert "Test TODO for Component-Type Filtering" not in event_summaries
        assert "Test TODO for Component-Type Filtering" in todo_summaries
        assert "Test Event for Component-Type Filtering" not in todo_summaries

        await event.delete()
        await todo_obj.delete()

    @pytest.mark.asyncio
    async def test_search_without_comp_type(self, async_calendar: Any) -> None:
        """search() with no filter must return all objects."""
        self.skip_unless_support("save-load.todo.mixed-calendar")
        c = async_calendar
        await c.add_todo(todo_static)
        await c.add_event(ev1_static)
        objects = await c.search()
        assert len(objects) >= 2
        type_names = {type(x).__name__ for x in objects}
        assert "Todo" in type_names
        assert "Event" in type_names

    @pytest.mark.asyncio
    async def test_search_sort_todo(self, async_task_list: Any) -> None:
        """Todos are sorted correctly by various sort_keys."""
        self.skip_unless_support("save-load.todo")
        self.skip_unless_support("search")
        self.skip_unless_support("search.unlimited-time-range")
        c = async_task_list

        pre_todos = await c.get_todos()
        pre_uid_map = {x.icalendar_component["uid"] for x in pre_todos}

        def cleanse(tasks: list) -> list:
            return [x for x in tasks if x.icalendar_component["uid"] not in pre_uid_map]

        t1 = await c.add_todo(
            summary="1 task overdue",
            due=date(2022, 12, 12),
            dtstart=date(2022, 10, 11),
            uid="async-sort-test1",
        )
        t2 = await c.add_todo(
            summary="2 task future",
            due=datetime.now() + timedelta(hours=15),
            dtstart=datetime.now() + timedelta(minutes=15),
            uid="async-sort-test2",
        )
        t3 = await c.add_todo(
            summary="3 task future due",
            due=datetime.now() + timedelta(hours=15),
            dtstart=datetime(2022, 12, 11, 10, 9, 8),
            uid="async-sort-test3",
        )
        t4 = await c.add_todo(
            summary="4 task priority is set to nine which is the lowest",
            priority=9,
            uid="async-sort-test4",
        )
        t5 = await c.add_todo(
            summary="5 task status is set to COMPLETED and this will disappear from the ordinary todo search",
            status="COMPLETED",
            uid="async-sort-test5",
        )
        t6 = await c.add_todo(
            summary="6 task has categories",
            categories="home,garden,sunshine",
            uid="async-sort-test6",
        )

        def check_order(tasks: list, order: tuple) -> None:
            assert [str(x.icalendar_component["uid"]) for x in tasks] == [
                "async-sort-test" + str(x) for x in order
            ]

        all_tasks = cleanse(await c.search(todo=True, sort_keys=("uid",)))
        check_order(all_tasks, (1, 2, 3, 4, 6))

        all_tasks = cleanse(await c.search(sort_keys=("summary",)))
        check_order(all_tasks, (1, 2, 3, 4, 5, 6))

        all_tasks = cleanse(
            await c.search(
                sort_keys=("isnt_overdue", "categories", "dtstart", "priority", "status")
            )
        )
        check_order(all_tasks, (1, 5, 4, 3, 2, 6))

    @pytest.mark.asyncio
    async def test_date_search_and_freebusy(self, async_calendar: Any) -> None:
        """Date-range search and freebusy request on a non-recurring event."""
        self.skip_unless_support("save-load.event")
        self.skip_unless_support("search")
        self.skip_unless_support("search.time-range.event.old-dates")
        c = async_calendar

        e = await c.add_event(ev1_static)

        r = await c.search(
            event=True,
            start=datetime(2006, 7, 13, 17, 0, 0),
            end=datetime(2006, 7, 15, 17, 0, 0),
            expand=False,
        )
        assert len(r) == 1
        assert str(e.vobject_instance.vevent.uid) == str(r[0].vobject_instance.vevent.uid)

        self.skip_unless_support("save-load.mutable")

        e.data = ev2_static
        await e.save()

        r = await c.search(
            event=True,
            start=datetime(2006, 7, 13, 17, 0, 0),
            end=datetime(2006, 7, 15, 17, 0, 0),
            expand=False,
        )
        assert len(r) == 0

        r = await c.search(
            event=True,
            start=datetime(2007, 7, 13, 17, 0, 0),
            end=datetime(2007, 7, 15, 17, 0, 0),
            expand=False,
        )
        assert len(r) == 1

        self.skip_unless_support("freebusy-query")

        freebusy = await c.freebusy_request(
            datetime(2007, 7, 13, 17, 0, 0), datetime(2007, 7, 15, 17, 0, 0)
        )
        assert isinstance(freebusy, FreeBusy)
        assert freebusy.vobject_instance.vfreebusy

    @pytest.mark.asyncio
    async def test_recurring_date_search(self, async_calendar: Any) -> None:
        """Recurring event can be found and expanded across multiple occurrences."""
        self.skip_unless_support("save-load.event")
        self.skip_unless_support("search.recurrences.includes-implicit.event")
        c = async_calendar

        # evr is a yearly event starting at 1997-11-02.  Search the next future
        # Nov-2 anniversary rather than a fixed historic year, so sliding-window
        # servers (e.g. OX) can serve the time range.
        year, narrow_start, narrow_end, wide_end = next_anniversary_windows()

        await c.add_event(evr_static)

        r = await c.search(
            event=True,
            start=narrow_start,
            end=narrow_end,
            expand=False,
        )
        assert len(r) == 1

        r = await c.search(
            event=True,
            start=narrow_start,
            end=narrow_end,
            expand=True,
        )
        assert len(r) == 1
        assert r[0].data.count("END:VEVENT") == 1
        assert r[0].data.count(f"DTSTART;VALUE=DATE:{year}") == 1

        r2 = await c.search(
            event=True,
            start=narrow_start,
            end=wide_end,
            expand=True,
        )
        assert len(r2) == 2
        assert "RRULE" not in r2[0].data
        assert "RRULE" not in r2[1].data

    @pytest.mark.asyncio
    async def test_recurring_date_with_exception_search(self, async_calendar: Any) -> None:
        """Bi-weekly event with exception: expanded search returns correct RECURRENCE-IDs."""
        self.skip_unless_support("search")
        self.skip_unless_support("search.time-range.event.old-dates")
        c = async_calendar

        await c.add_event(evr2_static)

        rc = await c.search(
            start=datetime(2024, 3, 31, 0, 0),
            end=datetime(2024, 5, 4, 0, 0),
            event=True,
            expand=True,
        )
        rs = await c.search(
            start=datetime(2024, 3, 31, 0, 0),
            end=datetime(2024, 5, 4, 0, 0),
            event=True,
            server_expand=True,
        )

        if self.is_supported("save-load.event.recurrences.exception") or self.is_supported(
            "search.recurrences.expanded.exception"
        ):
            assert len(rc) == 2
            assert "RRULE" not in rc[0].data
            assert "RRULE" not in rc[1].data

        if self.is_supported("search.recurrences.expanded.event") and self.is_supported(
            "search.recurrences.expanded.exception"
        ):
            assert len(rs) == 2

        asserts_on_results = []
        if self.is_supported("save-load.event.recurrences.exception"):
            asserts_on_results.append(rc)
        if self.is_supported("search.recurrences.expanded.exception"):
            asserts_on_results.append(rs)

        for r in asserts_on_results:
            recurrence_ids = []
            for event in r:
                recurrence_id = event.icalendar_component.get(
                    "RECURRENCE-ID"
                ) or event.icalendar_component.get("DTSTART")
                assert recurrence_id is not None
                assert isinstance(recurrence_id, icalendar.vDDDTypes)
                recurrence_ids.append(recurrence_id.dt.replace(tzinfo=None))
            assert set(recurrence_ids) == {
                datetime(2024, 4, 11, 12, 30, 0),
                datetime(2024, 4, 25, 12, 30, 0),
            }

    @pytest.mark.asyncio
    async def test_alarm(self, async_calendar: Any) -> None:
        """alarm_start/alarm_end search finds events with matching VALARM trigger."""
        c = async_calendar
        await c.add_event(
            dtstart=datetime(2015, 10, 10, 8, 0, 0),
            summary="This is a test event",
            uid="async-alarm-test1",
            dtend=datetime(2016, 10, 10, 9, 0, 0),
            alarm_trigger=timedelta(minutes=-15),
            alarm_action="AUDIO",
        )

        self.skip_unless_support("search.time-range.alarm")

        assert (
            len(
                await c.search(
                    event=True,
                    alarm_start=datetime(2015, 10, 10, 8, 1),
                    alarm_end=datetime(2015, 10, 10, 8, 7),
                )
            )
            == 0
        )
        assert (
            len(
                await c.search(
                    event=True,
                    alarm_start=datetime(2015, 10, 10, 7, 40),
                    alarm_end=datetime(2015, 10, 10, 7, 55),
                )
            )
            == 1
        )

    # ==================== Group D – Todos ====================

    @pytest.mark.asyncio
    async def test_todos(self, async_task_list: Any) -> None:
        """get_todos() sort order and include_completed filtering."""
        self.skip_unless_support("save-load.todo")
        self.skip_unless_support("search.unlimited-time-range")
        c = async_task_list

        t1 = await c.add_todo(todo_static)
        t2 = await c.add_todo(todo2_static)
        t4 = await c.add_todo(todo4_static)

        todos = await c.get_todos()
        assert len(todos) == 3

        def uids(lst: list) -> list:
            return [x.vobject_instance.vtodo.uid for x in lst]

        assert uids(todos) == uids([t2, t1, t4])

        todos = await c.get_todos(sort_keys=("priority",))
        todos2 = await c.get_todos(sort_key="priority")

        def pri(lst: list) -> list:
            return [
                x.vobject_instance.vtodo.priority.value
                for x in lst
                if hasattr(x.vobject_instance.vtodo, "priority")
            ]

        assert pri(todos) == pri([t4, t2])
        assert pri(todos2) == pri([t4, t2])

        todos = await c.get_todos(sort_keys=("summary", "priority"))
        assert uids(todos) == uids([t4, t2, t1])

    @pytest.mark.asyncio
    async def test_todo_completion(self, async_task_list: Any) -> None:
        """complete() transitions STATUS; pending/include_completed filtering works."""
        self.skip_unless_support("save-load.todo")
        self.skip_unless_support("search.unlimited-time-range")
        c = async_task_list

        t1 = await c.add_todo(todo_static)
        t2 = await c.add_todo(todo2_static)
        t3 = await c.add_todo(todo3_static, status="NEEDS-ACTION")

        todos = await c.get_todos()
        assert len(todos) == 3

        await t3.complete()

        todos = await c.get_todos()
        assert len(todos) == 2

        todos = await c.get_todos(include_completed=True)
        assert len(todos) == 3
        t3_ = await c.get_todo_by_uid(t3.id)
        assert t3_.vobject_instance.vtodo.summary == t3.vobject_instance.vtodo.summary
        assert t3_.vobject_instance.vtodo.uid == t3.vobject_instance.vtodo.uid

        await t2.delete()

        todos = await c.get_todos(include_completed=True)
        assert len(todos) == 2

    @pytest.mark.asyncio
    async def test_todo_recurring_complete_safe(self, async_task_list: Any) -> None:
        """complete(handle_rrule=True, rrule_mode='safe') advances a recurring todo."""
        self.skip_unless_support("save-load.todo")
        self.skip_unless_support("search.unlimited-time-range")
        c = async_task_list

        assert len(await c.get_todos()) == 0
        t6 = await c.add_todo(todo6_static, status="NEEDS-ACTION")
        assert len(await c.get_todos()) == 1
        if self.is_supported("save-load.todo.recurrences.count"):
            t8 = await c.add_todo(todo8_static)
            assert len(await c.get_todos()) == 2
        else:
            assert len(await c.get_todos()) == 1

        await t6.complete(handle_rrule=True, rrule_mode="safe")

        if not self.is_supported("save-load.todo.recurrences.count"):
            assert len(await c.get_todos()) == 1
            assert len(await c.get_todos(include_completed=True)) == 2
            (await c.get_todos())[0].delete()

        self.skip_unless_support("save-load.todo.recurrences.count")
        assert len(await c.get_todos()) == 2
        assert len(await c.get_todos(include_completed=True)) == 3

        await t8.complete(handle_rrule=True, rrule_mode="safe")
        assert len(await c.get_todos()) == 2
        await t8.complete(handle_rrule=True, rrule_mode="safe")
        await t8.complete(handle_rrule=True, rrule_mode="safe")
        assert len(await c.get_todos()) == 1
        assert len(await c.get_todos(include_completed=True)) == 5
        for x in await c.get_todos(include_completed=True):
            await x.delete()

    @pytest.mark.asyncio
    async def test_todo_recurring_complete_thisandfuture(self, async_task_list: Any) -> None:
        """complete(handle_rrule=True, rrule_mode='thisandfuture') truncates the series."""
        self.skip_unless_support("save-load.todo")
        self.skip_unless_support("save-load.todo.recurrences.thisandfuture")
        c = async_task_list

        assert len(await c.get_todos()) == 0
        t6 = await c.add_todo(todo6_static, status="NEEDS-ACTION")
        if self.is_supported("save-load.todo.recurrences.count"):
            t8 = await c.add_todo(todo8_static)
            assert len(await c.get_todos()) == 2
        else:
            assert len(await c.get_todos()) == 1

        await t6.complete(handle_rrule=True, rrule_mode="thisandfuture")
        all_todos = await c.get_todos(include_completed=True)
        if not self.is_supported("save-load.todo.recurrences.count"):
            assert len(await c.get_todos()) == 1
            assert len(all_todos) == 1

        self.skip_unless_support("save-load.todo.recurrences.count")
        assert len(await c.get_todos()) == 2
        assert len(all_todos) == 2

        await t8.complete(handle_rrule=True, rrule_mode="thisandfuture")
        assert len(await c.get_todos()) == 2
        await t8.complete(handle_rrule=True, rrule_mode="thisandfuture")
        await t8.complete(handle_rrule=True, rrule_mode="thisandfuture")
        assert len(await c.get_todos()) == 1

    @pytest.mark.asyncio
    async def test_todo_datesearch(self, async_task_list: Any) -> None:
        """search() with start/end date range filters todos by DUE/DTSTART."""
        self.skip_unless_support("save-load.todo")
        self.skip_unless_support("search.time-range.todo")
        self.skip_unless_support("search.time-range.todo.old-dates")
        c = async_task_list

        await c.add_todo(todo_static)
        await c.add_todo(todo2_static)
        await c.add_todo(todo3_static)
        await c.add_todo(todo4_static)
        await c.add_todo(todo5_static)
        await c.add_todo(todo6_static)

        todos = await c.get_todos()
        assert len(todos) == 6

        todos2 = await c.search(
            start=datetime(1997, 4, 14),
            end=datetime(2015, 5, 14),
            todo=True,
            expand=True,
            split_expanded=False,
            include_completed=True,
        )

        implicit_fragile = (
            self.is_supported("search.recurrences.includes-implicit.todo", str) == "fragile"
        )
        foo = 5
        if not self.is_supported("search.recurrences.includes-implicit.todo"):
            foo -= 1
        if self.check_compatibility_flag(
            "vtodo_datesearch_nodtstart_task_is_skipped"
        ) or self.check_compatibility_flag(
            "vtodo_datesearch_nodtstart_task_is_skipped_in_closed_date_range"
        ):
            foo -= 2
        elif self.check_compatibility_flag("vtodo_datesearch_notime_task_is_skipped"):
            foo -= 1

        if implicit_fragile:
            assert len(todos2) in (foo, foo + 1)
        else:
            assert len(todos2) == foo

    @pytest.mark.asyncio
    async def test_create_journal_list_and_journal_entry(self, async_journal_list: Any) -> None:
        """add_journal() and get_journals() work; search(journal=True) returns entries."""
        self.skip_unless_support("save-load.journal")
        c = async_journal_list

        j1 = await c.add_journal(journal_static)
        journals = await c.get_journals()
        assert len(journals) == 1
        j1_ = await c.get_journal_by_uid(j1.id)
        assert j1_.get_icalendar_instance() == journals[0].get_icalendar_instance()

        await c.add_journal(
            dtstart=date(2011, 11, 11),
            summary="A childbirth in a hospital in Kupchino",
            description="A quick birth, in the middle of the night",
            uid="async-ctuid1",
        )
        assert len(await c.get_journals()) == 2
        assert len(await c.search(journal=True)) == 2
        assert await c.get_todos() == []
        assert await c.get_events() == []

    # ==================== Group E – Properties & Meta ====================

    def _skip_on_compatibility_flag(self, flag: str) -> None:
        if self.check_compatibility_flag(flag):
            pytest.skip(f"Test skipped due to compatibility flag: {flag}")

    @pytest.mark.asyncio
    async def test_support(self, async_client: Any) -> None:
        """check_dav_support / check_cdav_support / check_scheduling_support."""
        self._skip_on_compatibility_flag("dav_not_supported")
        assert await async_client.check_dav_support()
        assert await async_client.check_cdav_support()
        if self.is_supported("scheduling", return_type=str) != "unknown":
            assert await async_client.check_scheduling_support() == self.is_supported("scheduling")

    @pytest.mark.asyncio
    async def test_scheduling_info(self, async_client: Any) -> None:
        """calendar_user_address_set() and get_vcal_address() on the principal."""
        self.skip_unless_support("scheduling.calendar-user-address-set")
        principal = await async_client.principal()
        calendar_user_address_set = await principal.calendar_user_address_set()
        me_a_participant = await principal.get_vcal_address()

    @pytest.mark.asyncio
    async def test_scheduling_mailboxes(self, async_client: Any) -> None:
        """schedule_inbox() and schedule_outbox() return without error."""
        self.skip_unless_support("scheduling.mailbox")
        principal = await async_client.principal()
        inbox = await principal.schedule_inbox()
        outbox = await principal.schedule_outbox()

    @pytest.mark.asyncio
    async def test_propfind(self, async_client: Any) -> None:
        """Raw XML propfind returns a multistatus response."""
        from caldav.lib.python_utilities import to_local

        self._skip_on_compatibility_flag("propfind_allprop_failure")
        principal = await async_client.principal()
        foo = await async_client.propfind(
            principal.url,
            props='<?xml version="1.0" encoding="UTF-8"?>'
            '<D:propfind xmlns:D="DAV:">'
            "  <D:allprop/>"
            "</D:propfind>",
        )
        assert "multistatus" in to_local(foo.raw)

    @pytest.mark.asyncio
    async def test_get_calendar_home_set(self, async_client: Any) -> None:
        """get_properties([CalendarHomeSet()]) must contain the key."""
        from caldav.elements import cdav

        principal = await async_client.principal()
        chs = await principal.get_properties([cdav.CalendarHomeSet()])
        assert "{urn:ietf:params:xml:ns:caldav}calendar-home-set" in chs

    @pytest.mark.asyncio
    async def test_get_default_calendar(self, async_client: Any) -> None:
        """get_calendars() must be non-empty (gated on get-current-user-principal.has-calendar)."""
        self.skip_unless_support("get-current-user-principal.has-calendar")
        principal = await async_client.principal()
        assert len(await principal.get_calendars()) != 0

    @pytest.mark.asyncio
    async def test_get_calendar(self, async_calendar: Any) -> None:
        """Calendar has a URL; repr() includes class name and URL."""
        c = async_calendar
        assert c.url is not None
        repr_ = repr(c)
        assert "Calendar" in repr_
        assert str(c.url) in repr_

    @pytest.mark.asyncio
    async def test_principal(self, async_client: Any) -> None:
        """All items returned by get_calendars() are Calendar instances."""
        from caldav.aio import AsyncCalendar

        principal = await async_client.principal()
        collections = await principal.get_calendars()
        for c in collections:
            assert isinstance(c, AsyncCalendar)

    @pytest.mark.asyncio
    async def test_principals(self, async_client: Any) -> None:
        """caldav.principals() list-all and by-name search."""
        from caldav.aio import AsyncPrincipal

        self.skip_unless_support("principal-search")
        if self.is_supported("principal-search.by-name.self"):
            principal = await async_client.principal()
            my_name = await principal.get_display_name()
            my_principals = await async_client.principals(name=my_name)
            assert isinstance(my_principals, list)
            assert len(my_principals) == 1
            assert my_principals[0].url == principal.url

        self.skip_unless_support("principal-search.list-all")
        all_principals = await async_client.principals()
        assert isinstance(all_principals, list)
        if all_principals:
            assert all(isinstance(x, AsyncPrincipal) for x in all_principals)

    @pytest.mark.asyncio
    async def test_create_delete_calendar(self, async_client: Any) -> None:
        """make_calendar() creates; delete() removes it; auto-creation check."""
        from caldav.lib import error

        self.skip_unless_support("create-calendar")
        self.skip_unless_support("delete-calendar")
        from caldav.aio import AsyncPrincipal
        from caldav.lib.error import AuthorizationError, NotFoundError

        from .fixture_helpers import cleanup_calendar_objects

        principal = None
        try:
            principal = await AsyncPrincipal.create(async_client)
        except (NotFoundError, AuthorizationError):
            pytest.skip("Cannot discover principal")

        cal_id = "pythoncaldav-async-createdelete-test"
        try:
            existing = principal.calendar(cal_id=cal_id)
            await cleanup_calendar_objects(existing)
            await existing.delete()
        except Exception:
            pass

        c = await principal.make_calendar(name="Yep", cal_id=cal_id)
        assert c.url is not None
        events = await c.get_events()
        assert len(events) == 0
        await c.delete()

    @pytest.mark.asyncio
    async def test_calendar_by_full_url(self, async_calendar: Any, async_client: Any) -> None:
        """Passing a full URL as cal_id should find the same calendar."""
        principal = await async_client.principal()
        samecal = principal.calendar(cal_id=str(async_calendar.url))
        assert async_calendar.url.canonical() == samecal.url.canonical()
        samecal2 = principal.calendar(cal_id=async_calendar.url)
        assert async_calendar.url.canonical() == samecal2.url.canonical()

    @pytest.mark.asyncio
    async def test_find_calendar_owner(self, async_calendar: Any, async_client: Any) -> None:
        """get_property(Owner()) returns the owner URL; construct Principal from it."""
        from caldav.aio import AsyncPrincipal
        from caldav.elements import dav

        owner = await async_calendar.get_property(dav.Owner())
        if owner is None:
            return

        if self.is_supported("scheduling.calendar-user-address-set"):
            owner_principal = AsyncPrincipal(client=async_client, url=owner)
            address = await owner_principal.get_vcal_address()
            assert address is not None

    @pytest.mark.asyncio
    async def test_set_calendar_properties(self, async_client: Any) -> None:
        """get_properties/set_properties round-trip for DisplayName."""
        from caldav.aio import AsyncPrincipal
        from caldav.elements import dav
        from caldav.lib.error import AuthorizationError, NotFoundError

        from .fixture_helpers import cleanup_calendar_objects

        self.skip_unless_support("create-calendar.set-displayname")
        ## This test expects the display name to round-trip at a stable URL;
        ## servers that relocate the calendar when a name is set (Zimbra) can't.
        self.skip_unless_support("create-calendar.set-displayname.stable-url")
        self.skip_unless_support("delete-calendar")
        self.skip_unless_support("create-calendar")

        principal = None
        try:
            principal = await AsyncPrincipal.create(async_client)
        except (NotFoundError, AuthorizationError):
            pytest.skip("Cannot discover principal")

        cal_id = "pythoncaldav-async-props-test"
        try:
            existing = principal.calendar(cal_id=cal_id)
            await cleanup_calendar_objects(existing)
            await existing.delete()
        except Exception:
            pass

        c = await principal.make_calendar(name="Yep", cal_id=cal_id)
        try:
            props = await c.get_properties([dav.DisplayName()])
            assert "Yep" == props[dav.DisplayName.tag]

            await c.set_properties([dav.DisplayName("hooray")])
            props = await c.get_properties([dav.DisplayName()])
            assert props[dav.DisplayName.tag] == "hooray"
        finally:
            try:
                await c.delete()
            except Exception:
                pass

    # ==================== Group F – Regressions ====================

    @pytest.mark.asyncio
    async def test_issue_397(self, async_calendar: Any) -> None:
        """Recurring VEVENT with RECURRENCE-ID override stores and retrieves correctly."""
        self.skip_unless_support("save-load.event.recurrences.exception")
        c = async_calendar
        await c.add_event(
            """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//PeterB//caldav//en_DK
BEGIN:VEVENT
SUMMARY:recurrence with attendee one single item
DTSTART;TZID=Europe/Zurich:20240101T090000
DTEND;TZID=Europe/Zurich:20240101T180000
UID:test1
DESCRIPTION:this is the recurrent series
TRANSP:OPAQUE
RRULE:FREQ=WEEKLY;BYDAY=TU,WE,TH
END:VEVENT
BEGIN:VEVENT
SUMMARY:single item
DTSTART;TZID=Europe/Zurich:20240605T090000
DTEND;TZID=Europe/Zurich:20240605T170000
UID:test1
DESCRIPTION:this is the single item assigning a attendee to just one event
ATTENDEE:foo.bar@corge.baz
RECURRENCE-ID:20240605T070000Z
END:VEVENT
END:VCALENDAR
"""
        )
        object_by_id = await c.get_object_by_uid("test1", comp_class=Event)
        instance = object_by_id.icalendar_instance
        events = [e for e in instance.subcomponents if isinstance(e, icalendar.Event)]
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_issue_399_change_attendee_status(self, async_client: Any) -> None:
        """change_attendee_status() works with username-as-email fallback (issue #399)."""
        self.skip_unless_support("scheduling")
        username = getattr(async_client, "username", None)
        if not username or "@" not in str(username):
            pytest.skip("Client username is not an email address; cannot build matching ATTENDEE")
        my_email = "mailto:" + username

        invite_data = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//Test//EN\r\nMETHOD:REQUEST\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:test-issue-399-{uuid.uuid4()}@test.example\r\n"
            f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}\r\n"
            f"DTSTART:{(datetime.now(timezone.utc) + timedelta(days=10)).strftime('%Y%m%dT%H%M%SZ')}\r\n"
            f"DTEND:{(datetime.now(timezone.utc) + timedelta(days=10, hours=1)).strftime('%Y%m%dT%H%M%SZ')}\r\n"
            "SUMMARY:Test invite for issue 399\r\n"
            "ORGANIZER:mailto:organizer@test.example\r\n"
            f"ATTENDEE;PARTSTAT=NEEDS-ACTION:{my_email}\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        ev = Event(client=async_client, data=invite_data)
        ## Pass the email explicitly since change_attendee_status() without attendee
        ## calls self.client.principal() which is async-only and can't work synchronously.
        ev.change_attendee_status(attendee=username, partstat="ACCEPTED")
        attendee = ev.icalendar_component["attendee"]
        assert attendee.params.get("PARTSTAT") == "ACCEPTED"

    @pytest.mark.asyncio
    async def test_add_organizer_full(self, async_client: Any, async_calendar: Any) -> None:
        """add_organizer() with explicit string and vCalAddress args (pure in-memory)."""
        from icalendar import vCalAddress

        c = async_calendar
        event = Event(client=async_client, data=ev1(), parent=c)

        event.add_organizer("organizer@example.com")
        org = event.icalendar_component.get("organizer")
        assert org is not None
        assert "organizer@example.com" in str(org)

        addr = vCalAddress("mailto:addr@example.com")
        event.add_organizer(addr)
        org = event.icalendar_component.get("organizer")
        assert str(org) == "mailto:addr@example.com"

    @pytest.mark.asyncio
    async def test_change_attendee_status_with_email_given(
        self, async_calendar: Any, async_client: Any
    ) -> None:
        """change_attendee_status(attendee=email) updates PARTSTAT correctly."""
        self.skip_unless_support("save-load.event")
        ## Some servers (e.g. OX) forbid changing an attendee's PARTSTAT via a
        ## direct PUT (403 Forbidden) and require iTIP scheduling instead.
        self.skip_unless_support("save-load.mutable.attendee-partstat")
        c = async_calendar
        event = await c.add_event(
            uid="test1",
            dtstart=datetime(2015, 10, 10, 8, 7, 6),
            dtend=datetime(2015, 10, 10, 9, 7, 6),
            ical_fragment="ATTENDEE;ROLE=OPT-PARTICIPANT;PARTSTAT=TENTATIVE:MAILTO:testuser@example.com",
        )
        event.change_attendee_status(attendee="testuser@example.com", PARTSTAT="ACCEPTED")
        await event.save()
        event2 = await c.get_event_by_uid("test1")

    @pytest.mark.asyncio
    async def test_add_orphaned_recurrence(self, async_calendar: Any) -> None:
        """add_event() with orphaned RECURRENCE-ID must not raise NotFoundError."""
        from caldav.lib import error

        self.skip_unless_support("save-load.event")
        c = async_calendar
        orphaned_recurrence = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example//CalDAV test//EN
BEGIN:VEVENT
UID:orphaned-recurrence-test-uid@example.com
DTSTAMP:20200101T000000Z
DTSTART:20200115T100000Z
DTEND:20200115T110000Z
RECURRENCE-ID:20200115T100000Z
SUMMARY:Orphaned recurrence with no master
END:VEVENT
END:VCALENDAR"""
        try:
            await c.add_event(orphaned_recurrence)
        except error.NotFoundError:
            pytest.fail(
                "add_event() raised NotFoundError for an orphaned recurrence; "
                "see commit 7269f179 (graceful adding of orphaned recurrences)"
            )
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_edit_single_recurrence(self, async_calendar: Any) -> None:
        """Expand a recurring event, edit one recurrence, verify only that day changed."""
        self.skip_unless_support("search.recurrences.includes-implicit.event")
        self.skip_unless_support("search.text")
        cal = async_calendar

        await cal.add_event(
            uid="test1",
            summary="daily test",
            dtstart=datetime(2015, 1, 1, 8, 7, 6),
            dtend=datetime(2015, 1, 1, 9, 7, 6),
            rrule={"FREQ": "DAILY"},
        )

        async def search(month):
            recurrence = await cal.search(
                event=True,
                start=datetime(2015, month, 1),
                end=datetime(2015, month, 2),
                expand=True,
            )
            assert len(recurrence) == 1
            return recurrence[0]

        async def summary_by_month(month):
            return (await search(month)).icalendar_component["summary"]

        recurrence = await search(7)
        recurrence.icalendar_component["summary"] = "half a year of daily testing"
        await recurrence.save()

        assert await summary_by_month(6) == "daily test"
        assert await summary_by_month(7) == "half a year of daily testing"
        assert await summary_by_month(8) == "daily test"

        recurrence = await search(2)
        recurrence.icalendar_component["summary"] = "one month of daily testing"
        await recurrence.save()

        assert await summary_by_month(1) == "daily test"
        assert await summary_by_month(2) == "one month of daily testing"
        assert await summary_by_month(7) == "half a year of daily testing"

        recurrence = await search(7)
        recurrence.icalendar_component["summary"] = "six months of daily testing"
        await recurrence.save()
        assert await summary_by_month(7) == "six months of daily testing"

        recurrence = await search(9)
        recurrence.icalendar_component["summary"] = "daily testing"
        await recurrence.save(all_recurrences=True)
        assert await summary_by_month(1) == "daily testing"
        assert await summary_by_month(2) == "one month of daily testing"
        assert await summary_by_month(3) == "daily testing"
        assert await summary_by_month(7) == "six months of daily testing"

    # ==================== Group G – Auth errors & misc ====================

    @pytest.mark.asyncio
    async def test_wrong_auth_type(self, async_client: Any) -> None:
        """At least one of digest/bearer auth_type must raise AuthorizationError."""
        from caldav.lib import error

        if not self.server.password or self.server.password == "any-password-seems-to-work":
            pytest.skip("Server does not require a password")

        raised = False
        for auth_type in ("digest", "bearer"):
            try:
                c = await self._make_async_client_with_params(auth_type=auth_type)
                await c.principal()
            except error.AuthorizationError:
                raised = True
                break
        assert raised, "Neither digest nor bearer auth_type raised AuthorizationError"

    @pytest.mark.asyncio
    async def test_wrong_password(self, async_client: Any) -> None:
        """Bad password must raise AuthorizationError."""
        import codecs

        from caldav.lib import error

        self.skip_unless_support("wrong-password-check")
        if not self.server.password or self.server.password == "any-password-seems-to-work":
            pytest.skip("Server does not require a password")

        with pytest.raises(error.AuthorizationError):
            bad = await self._make_async_client_with_params(
                password=codecs.encode(self.server.password, "rot13") + "!"
            )
            await bad.principal()

    @pytest.mark.asyncio
    async def test_create_child_parent(self, async_calendar: Any) -> None:
        """Add parent/child/grandparent events; verify RELATED-TO structure."""
        self.skip_unless_support("save-load.event")
        self.skip_unless_support("save-load.icalendar.related-to")
        c = async_calendar
        parent = await c.add_event(
            dtstart=datetime(2022, 12, 26, 19, 15),
            dtend=datetime(2022, 12, 26, 20, 0),
            summary="parent event",
            uid="ctuid1",
        )
        child = await c.add_event(
            dtstart=datetime(2022, 12, 26, 19, 17),
            dtend=datetime(2022, 12, 26, 20, 0),
            summary="child event",
            parent=[parent.id],
            uid="ctuid2",
        )
        grandparent = await c.add_event(
            dtstart=datetime(2022, 12, 26, 19, 0),
            dtend=datetime(2022, 12, 26, 20, 0),
            summary="grandparent event",
            child=[parent.id],
            uid="ctuid3",
        )

        parent_ = await c.get_event_by_uid(parent.id)
        child_ = await c.get_event_by_uid(child.id)
        grandparent_ = await c.get_event_by_uid(grandparent.id)

        rt = grandparent_.icalendar_component["RELATED-TO"]
        if isinstance(rt, list):
            assert len(rt) == 1
            rt = rt[0]
        assert rt == parent.id
        assert rt.params["RELTYPE"] == "CHILD"

        rt = parent_.icalendar_component["RELATED-TO"]
        assert len(rt) == 2
        assert set([str(rt[0]), str(rt[1])]) == set([grandparent.id, child.id])
        assert set([rt[0].params["RELTYPE"], rt[1].params["RELTYPE"]]) == set(["CHILD", "PARENT"])

        rt = child_.icalendar_component["RELATED-TO"]
        if isinstance(rt, list):
            assert len(rt) == 1
            rt = rt[0]
        assert rt == parent.id
        assert rt.params["RELTYPE"] == "PARENT"

        foo = await parent_.get_relatives(reltypes={"PARENT"})
        assert len(foo) == 1
        assert len(foo["PARENT"]) == 1

    @pytest.mark.asyncio
    async def test_offset_url(self, async_client: Any, async_calendar: Any) -> None:
        """Connecting with url=principal.url or url=calendar.url still works."""
        principal = await async_client.principal()
        urls = [principal.url, async_calendar.url]
        for url in urls:
            conn = await self._make_async_client_with_params(url=url)
            p = await conn.principal()
            calendars = await p.get_calendars()

    @pytest.mark.asyncio
    async def test_utf8_event(self, async_client: Any) -> None:
        """Calendar with non-ASCII name; event with non-ASCII summary."""
        self.skip_unless_support("save-load.event")
        self.skip_unless_support("create-calendar")

        from caldav.aio import AsyncPrincipal
        from caldav.lib.error import AuthorizationError, NotFoundError

        from .fixture_helpers import cleanup_calendar_objects

        principal = None
        try:
            principal = await AsyncPrincipal.create(async_client)
        except (NotFoundError, AuthorizationError):
            pytest.skip("Cannot discover principal")

        cal_id = "pythoncaldav-async-utf8-test"
        try:
            existing = await principal.calendar(cal_id=cal_id)
            await cleanup_calendar_objects(existing)
            await existing.delete()
        except Exception:
            pass

        c = await principal.make_calendar(name="Yølp", cal_id=cal_id)
        try:
            await c.add_event(
                near_now_ics(ev1_static).replace("Bastille Day Party", "Bringebærsyltetøyfestival")
            )
            events = await c.get_events()
            if "zimbra" not in str(c.url):
                assert len(events) == 1
        finally:
            try:
                await c.delete()
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_create_calendar_and_event_from_vobject(self, async_calendar: Any) -> None:
        """Add event from vobject.readOne(); verify count."""
        vobject = pytest.importorskip("vobject")
        self.skip_unless_support("save-load.event")
        c = async_calendar
        cnt = len(await c.get_events())
        ve1 = vobject.readOne(near_now_ics(ev1_static))
        await c.add_event(ve1)
        cnt += 1
        events = await c.get_events()
        assert len(events) == cnt

    @pytest.mark.asyncio
    async def test_create_event_from_ical(self, async_calendar: Any) -> None:
        """Add event from icalendar.Calendar and icalendar.Event objects."""
        self.skip_unless_support("save-load.event")
        c = async_calendar
        try:
            icalcal = icalendar.Calendar.new()
        except Exception:
            pytest.skip("Newer icalendar version required (icalendar 7+)")

        start = datetime.now() + timedelta(days=30)
        end = start + timedelta(hours=1)
        icalevent = icalendar.Event.new(
            uid="ctuid1",
            start=start,
            end=end,
            summary="This is a test event",
        )
        icalcal.add_component(icalevent)

        for obj in [icalcal, icalevent]:
            await c.add_event(obj)
            events = await c.get_events()
            assert any(e.icalendar_component["uid"] == "ctuid1" for e in events), (
                f"Event with uid ctuid1 not found after adding {type(obj).__name__}"
            )

    @pytest.mark.asyncio
    async def test_set_due(self, async_task_list: Any) -> None:
        """set_due() updates DUE and optionally moves DTSTART."""
        self.skip_unless_support("save-load.todo")
        c = async_task_list
        utc = timezone.utc

        some_todo = await c.add_todo(
            dtstart=datetime(2022, 12, 26, 19, 15, tzinfo=utc),
            due=datetime(2022, 12, 26, 20, 0, tzinfo=utc),
            summary="Some task",
            uid="ctuid5",
        )
        some_todo.set_due(datetime(2022, 12, 26, 20, 10, tzinfo=utc))
        assert some_todo.icalendar_component["DUE"].dt == datetime(2022, 12, 26, 20, 10, tzinfo=utc)
        assert some_todo.icalendar_component["DTSTART"].dt == datetime(
            2022, 12, 26, 19, 15, tzinfo=utc
        )

        some_todo.set_due(datetime(2022, 12, 26, 20, 20, tzinfo=utc), move_dtstart=True)
        assert some_todo.icalendar_component["DUE"].dt == datetime(2022, 12, 26, 20, 20, tzinfo=utc)
        assert some_todo.icalendar_component["DTSTART"].dt == datetime(
            2022, 12, 26, 19, 25, tzinfo=utc
        )

        await some_todo.save()

    @pytest.mark.asyncio
    async def test_create_task_list_and_todo(self, async_task_list: Any) -> None:
        """add_todo(); get_todos(); get_object_by_uid()."""
        self.skip_unless_support("save-load.todo")
        c = async_task_list
        t = await c.add_todo(uid="well_known_t1", summary="Well-known async task")
        todos = await c.get_todos()
        assert any(str(x.icalendar_component.get("uid", "")) == "well_known_t1" for x in todos)
        obj = await c.get_object_by_uid("well_known_t1")
        assert obj.component["summary"] == "Well-known async task"


class _AsyncTestSchedulingBase:
    """
    Async counterpart of _TestSchedulingBase (tests/test_caldav.py) for
    RFC6638 scheduling tests.  Not collected directly by pytest (no ``Test``
    prefix); concrete subclasses supply ``_users`` and ``_server_features``.

    Concrete subclasses are generated dynamically in the module epilogue,
    one per server that has ``scheduling_users`` configured.
    """

    ## Subclasses set these when the class is dynamically generated.
    _users: list[dict] = []
    _server_features: object = None

    def _skip_unless_support(self, feature: str) -> None:
        """Skip if the server does not declare support for *feature*."""
        from caldav.compatibility_hints import FeatureSet

        if not self._server_features:
            pytest.skip(f"No feature information available, skipping {feature} test")
        fs = (
            self._server_features
            if isinstance(self._server_features, FeatureSet)
            else FeatureSet(self._server_features)
        )
        if not fs.is_supported(feature):
            msg = fs.find_feature(feature).get("description", feature)
            pytest.skip("Test skipped due to server incompatibility issue: " + msg)

    @pytest_asyncio.fixture
    async def scheduling_setup(self) -> Any:
        """Create async clients/principals/calendars for each scheduling user."""
        from caldav.aio import get_async_davclient

        from .fixture_helpers import aget_or_create_test_calendar, cleanup_calendar_objects

        clients: list[Any] = []
        principals: list[Any] = []
        calendars: list[Any] = []
        auto_uids: list[str] = []

        for i, user_config in enumerate(self._users):
            try:
                client = await get_async_davclient(probe=False, **user_config)
            except Exception:
                continue
            if not await client.check_scheduling_support():
                await client.close()
                continue
            principal = await client.principal()
            ## Use a fixed cal_id (not a random UUID) so the same calendar is
            ## reused across test runs and does not accumulate on the server.
            ## This mirrors the sync scheduling tests which use fixed calendar names.
            cal, _ = await aget_or_create_test_calendar(
                client,
                principal,
                calendar_name=f"async scheduling test {i}",
                cal_id=f"asyncschedtest{i}",
            )
            if cal is None:
                await client.close()
                continue
            await cleanup_calendar_objects(cal)
            clients.append(client)
            principals.append(principal)
            calendars.append(cal)

        if not clients:
            pytest.skip("No scheduling users available or server does not support scheduling")

        yield clients, principals, calendars, auto_uids

        ## Teardown: clear calendar objects and clean up auto-scheduled events
        for i, (client, principal) in enumerate(zip(clients, principals, strict=False)):
            try:
                await cleanup_calendar_objects(calendars[i])
            except Exception:
                pass
            if auto_uids:
                try:
                    for cal in await principal.calendars():
                        try:
                            for event in await cal.get_events():
                                if event.id in auto_uids:
                                    await event.delete()
                        except Exception:
                            pass
                except Exception:
                    pass
            await client.close()

    @pytest.mark.asyncio
    async def test_invite_and_respond(self, scheduling_setup: Any) -> None:
        """send a calendar invite via save_with_invites and verify delivery.

        Async counterpart of _TestSchedulingBase.testInviteAndRespond.
        """
        import uuid

        clients, principals, calendars, auto_uids = scheduling_setup
        if len(principals) < 2:
            pytest.skip("need 2 principals to do the invite and respond test")

        ## Snapshot inbox contents before the invite
        inbox0 = await principals[0].schedule_inbox()
        inbox1 = await principals[1].schedule_inbox()
        inbox_urls_before: set[Any] = set()
        for item in await inbox0.get_items():
            inbox_urls_before.add(item.url)
        for item in await inbox1.get_items():
            inbox_urls_before.add(item.url)

        ## Send the invite
        base = _get_base_date()
        ical = make_event(
            f"async-sched-{uuid.uuid4()}@example.com",
            "Async Schedule Test",
            base + timedelta(days=3),
            base + timedelta(days=3, hours=1),
        )
        attendee_vcal = await principals[1]._async_get_vcal_address()
        saved_event = await calendars[0].save_with_invites(ical, [principals[0], attendee_vcal])
        event_uid = saved_event.id
        auto_uids.append(event_uid)

        ## Event must be in the organizer's calendar
        organizer_events = await calendars[0].get_events()
        assert any(e.id == event_uid for e in organizer_events), (
            "Event should appear in organizer's calendar after save_with_invites"
        )

        ## Poll: check attendee's inbox and calendars.  Some servers process
        ## scheduling asynchronously, so poll with backoff before giving up.
        new_attendee_inbox_items: list[Any] = []
        auto_scheduled = False
        for _ in range(30):
            new_attendee_inbox_items = [
                item for item in await inbox1.get_items() if item.url not in inbox_urls_before
            ]
            ## Check whether the server auto-scheduled the event directly into
            ## the attendee's calendar.  The event may land in any calendar,
            ## so search all attendee calendars for the event UID.
            ## Always check even when inbox items were found: some servers (e.g.
            ## Davis/sabre/dav) deliver iTIP to the inbox AND auto-schedule.
            if not auto_scheduled:
                for cal in await principals[1].calendars():
                    for event in await cal.get_events():
                        if event.id == event_uid:
                            auto_scheduled = True
                            break
                    if auto_scheduled:
                        break
            if new_attendee_inbox_items or auto_scheduled:
                break
            await asyncio.sleep(1)

        if len(new_attendee_inbox_items) == 0 or auto_scheduled:
            ## Server implements automatic scheduling.  Some servers (e.g.
            ## Stalwart) may additionally deliver an iTIP copy to the inbox as
            ## a notification, but the acceptance is already done.
            assert auto_scheduled, (
                "Expected invite in attendee inbox OR event auto-added to attendee calendar, "
                "got neither"
            )
            return

        ## Normal inbox-delivery flow (RFC6638 section 4.1).

        ## No new inbox items expected for principals[0] yet
        for item in await inbox0.get_items():
            assert item.url in inbox_urls_before

        assert len(new_attendee_inbox_items) == 1
        assert new_attendee_inbox_items[0].is_invite_request()

        ## Approving the invite.
        await new_attendee_inbox_items[0].accept_invite(calendar=calendars[1])

        ## principals[0] should now have a notification in the inbox that the
        ## calendar invite was accepted
        new_organizer_inbox_items = [
            item for item in await inbox0.get_items() if item.url not in inbox_urls_before
        ]
        assert len(new_organizer_inbox_items) == 1
        assert new_organizer_inbox_items[0].is_invite_reply()
        await new_organizer_inbox_items[0].delete()

    @pytest.mark.asyncio
    async def test_freebusy(self, scheduling_setup: Any) -> None:
        """Test RFC6638 freebusy query via the schedule outbox.

        Async counterpart of _TestSchedulingBase.testFreeBusy.
        Verifies that Principal.freebusy_request() returns a coroutine for
        async clients and that awaiting it completes without error.
        """
        clients, principals, calendars, auto_uids = scheduling_setup
        self._skip_unless_support("scheduling.freebusy-query")

        base = _get_base_date()
        dtstart = base
        dtend = base + timedelta(days=1)
        attendees = [await principals[0]._async_get_vcal_address()]

        coro = principals[0].freebusy_request(dtstart, dtend, attendees)
        assert asyncio.iscoroutine(coro), (
            f"Principal.freebusy_request() on async client must return a coroutine, "
            f"got {type(coro)}"
        )
        ## Just verify it completes without raising; response format varies per server.
        await coro

    # ------------------------------------------------------------------ #
    # Schedule-Tag tests (RFC 6638 section 3.2–3.3)                       #
    # These are async counterparts of the sync tests in                   #
    # _TestSchedulingBase.  They are EXPECTED TO FAIL until async         #
    # scheduling support (_async_put with If-Schedule-Tag-Match etc.)     #
    # is implemented.                                                      #
    # ------------------------------------------------------------------ #

    @pytest.mark.asyncio
    async def test_schedule_tag_returned_on_save(self, scheduling_setup: Any) -> None:
        """Saving a scheduling object must return a Schedule-Tag header.

        Async counterpart of testScheduleTagReturnedOnSave.
        Expected to fail: _async_put() does not yet capture the Schedule-Tag
        response header into event.props.
        """
        import uuid

        clients, principals, calendars, auto_uids = scheduling_setup
        self._skip_unless_support("scheduling.schedule-tag")
        if len(principals) < 2:
            pytest.skip("need 2 principals")

        organizer_cal = calendars[0]
        addr = await principals[0].get_vcal_address()
        addr2 = await principals[1].get_vcal_address()
        uid = str(uuid.uuid4())
        ical = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//Test//EN\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            "DTSTAMP:20260101T000000Z\r\n"
            "DTSTART:20320601T100000Z\r\nDURATION:PT1H\r\n"
            "SUMMARY:Schedule-Tag test\r\n"
            f"ORGANIZER:{addr}\r\n"
            f"ATTENDEE;RSVP=TRUE;PARTSTAT=NEEDS-ACTION:{addr}\r\n"
            f"ATTENDEE;RSVP=TRUE;PARTSTAT=NEEDS-ACTION:{addr2}\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        event = await organizer_cal.save_event(ical)
        auto_uids.append(uid)

        assert event.schedule_tag is not None, "Server did not return Schedule-Tag header after PUT"

    @pytest.mark.asyncio
    async def test_schedule_tag_stable_on_partstate_update(self, scheduling_setup: Any) -> None:
        """PARTSTAT-only update must not change the Schedule-Tag.

        Async counterpart of testScheduleTagStableOnPartstateUpdate.
        """
        import uuid

        clients, principals, calendars, auto_uids = scheduling_setup
        self._skip_unless_support("scheduling.schedule-tag")
        self._skip_unless_support("scheduling.schedule-tag.stable-partstat")
        if len(principals) < 2:
            pytest.skip("need 2 principals")
        if not clients[1].features.is_supported("scheduling.mailbox.inbox-delivery"):
            pytest.skip("server does not deliver iTIP requests to the inbox")

        organizer_cal = calendars[0]
        attendee_cal = calendars[1]
        organizer_addr = await principals[0].get_vcal_address()
        attendee_addr = await principals[1].get_vcal_address()
        uid = str(uuid.uuid4())
        ical = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//Test//EN\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            "SEQUENCE:0\r\n"
            "DTSTAMP:20260101T000000Z\r\n"
            "DTSTART:20320601T100000Z\r\nDURATION:PT1H\r\n"
            "SUMMARY:Partstat stability test\r\n"
            f"ORGANIZER:{organizer_addr}\r\n"
            f"ATTENDEE;RSVP=TRUE;PARTSTAT=NEEDS-ACTION:{attendee_addr}\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        saved_event = await organizer_cal.save_with_invites(ical, [principals[0], attendee_addr])
        auto_uids.append(uid)

        ## Wait for the REQUEST invite to land in attendee's inbox
        invite = None
        for _ in range(30):
            inbox = await principals[1].schedule_inbox()
            for item in await inbox.get_items():
                await item.load()
                if item.is_invite_request() and item.id == saved_event.id:
                    invite = item
                    break
            if invite:
                break
            await asyncio.sleep(1)

        if not invite:
            pytest.skip("Invite not delivered to attendee inbox; cannot test PARTSTAT stability")

        await invite.accept_invite(calendar=attendee_cal)

        ## Find the attendee's copy
        attendee_event = None
        for _ in range(5):
            for cal in await principals[1].calendars():
                try:
                    attendee_event = await cal.get_event_by_uid(saved_event.id)
                    break
                except Exception:
                    pass
            if attendee_event:
                break
            await asyncio.sleep(1)

        assert attendee_event is not None, "Event not found in any attendee calendar after accept"
        await attendee_event.load()
        tag_before = attendee_event.schedule_tag
        assert tag_before is not None, "No Schedule-Tag on attendee's calendar event after accept"

        ## PARTSTAT-only change — tag must not move.
        ## Pass attendee_addr explicitly: without an arg, change_attendee_status() resolves
        ## the principal via self.client.principal(), which returns a coroutine in async mode.
        attendee_event.change_attendee_status(str(attendee_addr), partstat="TENTATIVE")
        await attendee_event.save()
        await attendee_event.load()
        tag_after = attendee_event.schedule_tag

        assert tag_after is not None, "No Schedule-Tag on attendee's event after PARTSTAT update"
        assert tag_before == tag_after, (
            f"Schedule-Tag changed after PARTSTAT-only update: {tag_before!r} → {tag_after!r}"
        )

    @pytest.mark.asyncio
    async def test_schedule_tag_changes_on_organizer_update(self, scheduling_setup: Any) -> None:
        """Organizer update must advance the Schedule-Tag on the attendee's copy.

        Async counterpart of testScheduleTagChangesOnOrganizerUpdate.
        Expected to fail: _async_load() does not yet capture the Schedule-Tag
        response header.
        """
        import uuid

        clients, principals, calendars, auto_uids = scheduling_setup
        self._skip_unless_support("scheduling.schedule-tag")
        if len(principals) < 2:
            pytest.skip("need 2 principals")

        organizer_cal = calendars[0]
        organizer_addr = await principals[0].get_vcal_address()
        attendee_addr = await principals[1].get_vcal_address()
        uid = str(uuid.uuid4())
        seqno = 0

        def _make_ical(summary: str) -> str:
            nonlocal seqno
            s = seqno
            seqno += 1
            return (
                "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//Test//EN\r\n"
                "BEGIN:VEVENT\r\n"
                f"UID:{uid}\r\n"
                f"SEQUENCE:{s}\r\n"
                "DTSTAMP:20260101T000000Z\r\n"
                "DTSTART:20320601T100000Z\r\nDURATION:PT1H\r\n"
                f"SUMMARY:{summary}\r\n"
                f"ORGANIZER:{organizer_addr}\r\n"
                f"ATTENDEE;RSVP=TRUE;PARTSTAT=NEEDS-ACTION:{attendee_addr}\r\n"
                "END:VEVENT\r\nEND:VCALENDAR\r\n"
            )

        await organizer_cal.save_with_invites(
            _make_ical("Original summary"), [principals[0], attendee_addr]
        )
        auto_uids.append(uid)

        ## Poll for attendee's copy
        attendee_event = None
        for _ in range(30):
            for cal in await principals[1].calendars():
                for ev in await cal.get_events():
                    if ev.id == uid:
                        attendee_event = ev
                        break
                if attendee_event:
                    break
            if attendee_event:
                break
            await asyncio.sleep(1)

        if attendee_event is None:
            pytest.skip("Event not delivered to attendee; cannot test tag change")

        await attendee_event.load()
        tag_before = attendee_event.schedule_tag
        assert tag_before is not None, "No Schedule-Tag on attendee's copy before organizer update"

        ## Organizer sends a substantive update
        await organizer_cal.save_with_invites(
            _make_ical("Updated summary"), [principals[0], attendee_addr]
        )

        ## Poll until the tag advances
        for _ in range(30):
            await attendee_event.load()
            if attendee_event.schedule_tag != tag_before:
                break
            await asyncio.sleep(1)

        assert attendee_event.schedule_tag != tag_before, (
            f"Schedule-Tag did not change after organizer update: still {tag_before!r}"
        )

    @pytest.mark.asyncio
    async def test_schedule_tag_mismatch_raises_error(self, scheduling_setup: Any) -> None:
        """save() with a stale Schedule-Tag must raise ScheduleTagMismatchError.

        Async counterpart of testScheduleTagMismatchRaisesError.
        Expected to fail: _async_put() does not yet send If-Schedule-Tag-Match
        or raise ScheduleTagMismatchError on a 412 response.
        """
        import uuid

        from caldav.lib import error

        clients, principals, calendars, auto_uids = scheduling_setup
        self._skip_unless_support("scheduling.schedule-tag")
        if len(principals) < 2:
            pytest.skip("need 2 principals to cause a server-side tag advance")

        organizer_cal = calendars[0]
        organizer_addr = await principals[0].get_vcal_address()
        attendee_addr = await principals[1].get_vcal_address()
        uid = str(uuid.uuid4())

        def _make_ical(summary: str, seq: int) -> str:
            return (
                "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//Test//EN\r\n"
                "BEGIN:VEVENT\r\n"
                f"UID:{uid}\r\n"
                f"SEQUENCE:{seq}\r\n"
                "DTSTAMP:20260101T000000Z\r\n"
                "DTSTART:20320601T100000Z\r\nDURATION:PT1H\r\n"
                f"SUMMARY:{summary}\r\n"
                f"ORGANIZER:{organizer_addr}\r\n"
                f"ATTENDEE;RSVP=TRUE;PARTSTAT=NEEDS-ACTION:{attendee_addr}\r\n"
                "END:VEVENT\r\nEND:VCALENDAR\r\n"
            )

        ## Create event, load it: event holds original content + tag=1
        event = await organizer_cal.save_event(_make_ical("Original", 0))
        auto_uids.append(uid)
        await event.load()
        assert event.schedule_tag is not None, (
            "server did not return Schedule-Tag after initial save"
        )

        ## Make a local conflicting edit before the concurrent organizer update
        event.icalendar_component["SUMMARY"] = "Conflicting client change"

        ## Concurrent organizer PUT advances the server-side tag
        await organizer_cal.save_event(_make_ical("Organizer update", 1))

        ## PUT stale content with stale tag — server must reject with 412
        with pytest.raises(error.ScheduleTagMismatchError):
            await event.save(increase_seqno=False)

    @pytest.mark.asyncio
    async def test_schedule_tag_match_succeeds(self, scheduling_setup: Any) -> None:
        """save() with the correct Schedule-Tag must succeed.

        Async counterpart of testScheduleTagMatchSucceeds.
        Expected to fail: _async_put() does not yet send If-Schedule-Tag-Match,
        so the conditional PUT is not exercised.
        """
        import uuid

        clients, principals, calendars, auto_uids = scheduling_setup
        self._skip_unless_support("scheduling.schedule-tag")
        if len(principals) < 2:
            pytest.skip("need 2 principals for Schedule-Tag to be assigned")

        cal = calendars[0]
        addr = await principals[0].get_vcal_address()
        addr2 = await principals[1].get_vcal_address()
        uid = str(uuid.uuid4())
        ical = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//Test//EN\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            "DTSTAMP:20260101T000000Z\r\n"
            "DTSTART:20320601T100000Z\r\nDURATION:PT1H\r\n"
            "SUMMARY:Correct-tag test\r\n"
            f"ORGANIZER:{addr}\r\n"
            f"ATTENDEE;RSVP=TRUE;PARTSTAT=NEEDS-ACTION:{addr}\r\n"
            f"ATTENDEE;RSVP=TRUE;PARTSTAT=NEEDS-ACTION:{addr2}\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        event = await cal.save_event(ical)
        auto_uids.append(uid)
        await event.load()

        tag_before = event.schedule_tag
        assert tag_before is not None, "Server did not return Schedule-Tag"

        ## Minor update with the correct tag — must not raise
        event.icalendar_component["SUMMARY"] = "Correct-tag test (updated)"
        await event.save(increase_seqno=False)

        ## Tag must still be present after save
        assert event.schedule_tag is not None, (
            "schedule_tag property disappeared after conditional save"
        )


# ==================== Dynamic Test Class Generation ====================
#
# Create a test class for each available server, similar to how
# test_caldav.py works for sync tests.

_generated_classes: dict[str, type] = {}

for _server in get_available_servers():
    _classname = f"TestAsyncFor{_server.name.replace(' ', '')}"

    # Skip if we already have a class with this name
    if _classname in _generated_classes:
        continue

    # Create a new test class for this server
    _test_class = type(
        _classname,
        (AsyncFunctionalTestsBaseClass,),
        {"server": _server},
    )

    # Add to module namespace so pytest discovers it
    vars()[_classname] = _test_class
    _generated_classes[_classname] = _test_class

    ## If the server has scheduling_users, also generate an async scheduling class.
    if hasattr(_server, "config") and "scheduling_users" in _server.config:
        _sched_classname = f"TestAsyncSchedulingFor{_server.name.replace(' ', '')}"
        if _sched_classname not in _generated_classes:
            _sched_class = type(
                _sched_classname,
                (_AsyncTestSchedulingBase,),
                {
                    "_users": _server.config["scheduling_users"],
                    "_server_features": _server.features,
                },
            )
            vars()[_sched_classname] = _sched_class
            _generated_classes[_sched_classname] = _sched_class
