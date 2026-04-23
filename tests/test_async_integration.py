#!/usr/bin/env python
"""
Functional integration tests for the async API.

These tests verify that the async API works correctly with real CalDAV servers.
They run against all available servers (Radicale, Xandikos, Docker servers)
using the same dynamic class generation pattern as the sync tests.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any

import pytest
import pytest_asyncio

from caldav.compatibility_hints import FeatureSet

from .test_caldav import (
    ev1 as ev1_static,  # old-date (2006); distinct from ev1() near-future generator
)
from .test_caldav import ev2 as ev2_static  # same UID as ev1_static, one year later
from .test_caldav import ev3 as ev3_static  # different UID (2021)
from .test_caldav import evr as evr_static  # recurring annual event (1997)
from .test_caldav import evr2 as evr2_static  # bi-weekly with exception (2024)
from .test_caldav import journal as journal_static
from .test_caldav import todo as todo_static  # avoids clash with local var in add_todo()
from .test_caldav import todo2 as todo2_static  # avoids clash with todo2() generator
from .test_caldav import todo3 as todo3_static
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
        "async-test-event-001@example.com",
        "Async Test Event",
        base,
        base + timedelta(hours=11),
    )


def ev2() -> str:
    base = _get_base_date()
    return make_event(
        "async-test-event-002@example.com",
        "Second Async Test Event",
        base + timedelta(days=1),
        base + timedelta(days=1, hours=11),
    )


def todo1() -> str:
    return make_todo("async-test-todo-001@example.com", "Async Test Todo")


def todo2() -> str:
    return make_todo("async-test-todo-002@example.com", "Completed Async Todo", "COMPLETED")


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
        """Create a test calendar or use an existing one if creation not supported."""
        from caldav.aio import AsyncPrincipal
        from caldav.lib.error import AuthorizationError, NotFoundError

        from .fixture_helpers import aget_or_create_test_calendar

        calendar_name = f"async-test-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        # Try to get principal for calendar operations
        principal = None
        try:
            principal = await AsyncPrincipal.create(async_client)
        except (NotFoundError, AuthorizationError):
            pass

        # Use shared helper for calendar setup
        calendar, created = await aget_or_create_test_calendar(
            async_client, principal, calendar_name=calendar_name
        )

        if calendar is None:
            pytest.skip("Could not create or find a calendar for testing")

        yield calendar

        # Only cleanup if we created the calendar
        if created:
            try:
                await calendar.delete()
            except Exception:
                pass

    @pytest_asyncio.fixture
    async def async_task_list(self, async_client: Any) -> Any:
        """Create a task list for todo tests.

        For servers that don't support mixed calendars (like Zimbra), todos must
        be stored in a separate task list with supported_calendar_component_set=["VTODO"].
        """
        from caldav.aio import AsyncPrincipal
        from caldav.lib.error import AuthorizationError, NotFoundError

        from .fixture_helpers import aget_or_create_test_calendar

        # Check if server supports mixed calendars
        supports_mixed = True
        if hasattr(async_client, "features") and async_client.features:
            supports_mixed = async_client.features.is_supported("save-load.todo.mixed-calendar")

        calendar_name = f"async-task-list-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        # Try to get principal for calendar operations
        principal = None
        try:
            principal = await AsyncPrincipal.create(async_client)
        except (NotFoundError, AuthorizationError):
            pass

        # For servers without mixed calendar support, create a dedicated task list
        component_set = ["VTODO"] if not supports_mixed else None

        calendar, created = await aget_or_create_test_calendar(
            async_client,
            principal,
            calendar_name=calendar_name,
            supported_calendar_component_set=component_set,
        )

        if calendar is None:
            pytest.skip("Could not create or find a task list for testing")

        yield calendar

        # Only cleanup if we created the calendar
        if created:
            try:
                await calendar.delete()
            except Exception:
                pass

    @pytest_asyncio.fixture
    async def async_calendar2(self, async_client: Any) -> Any:
        """Create a second test calendar for tests that need two distinct calendars."""
        from caldav.aio import AsyncPrincipal
        from caldav.lib.error import AuthorizationError, NotFoundError

        from .fixture_helpers import aget_or_create_test_calendar

        calendar_name = f"async-test2-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        principal = None
        try:
            principal = await AsyncPrincipal.create(async_client)
        except (NotFoundError, AuthorizationError):
            pass

        calendar, created = await aget_or_create_test_calendar(
            async_client, principal, calendar_name=calendar_name
        )

        if calendar is None:
            pytest.skip("Could not create or find a second calendar for testing")

        yield calendar

        if created:
            try:
                await calendar.delete()
            except Exception:
                pass

    @pytest_asyncio.fixture
    async def async_journal_list(self, async_client: Any) -> Any:
        """Create a VJOURNAL calendar for journal tests."""
        from caldav.aio import AsyncPrincipal
        from caldav.lib.error import AuthorizationError, NotFoundError

        from .fixture_helpers import aget_or_create_test_calendar

        calendar_name = f"async-journal-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        principal = None
        try:
            principal = await AsyncPrincipal.create(async_client)
        except (NotFoundError, AuthorizationError):
            pass

        calendar, created = await aget_or_create_test_calendar(
            async_client,
            principal,
            calendar_name=calendar_name,
            supported_calendar_component_set=["VJOURNAL"],
        )

        if calendar is None:
            pytest.skip("Could not create or find a journal list for testing")

        yield calendar

        if created:
            try:
                await calendar.delete()
            except Exception:
                pass

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
