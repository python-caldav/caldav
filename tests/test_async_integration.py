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
