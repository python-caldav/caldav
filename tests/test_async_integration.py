#!/usr/bin/env python
"""
Functional integration tests for the async API.

These tests verify that the async API works correctly with real CalDAV servers.
They run against all available servers (Radicale, Xandikos, Docker servers)
using the same dynamic class generation pattern as the sync tests.
"""
import asyncio
from datetime import datetime
from functools import wraps
from typing import Any

import pytest
import pytest_asyncio

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


# Test data
ev1 = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:async-test-event-001@example.com
DTSTAMP:20060712T182145Z
DTSTART:20060714T170000Z
DTEND:20060715T040000Z
SUMMARY:Async Test Event
END:VEVENT
END:VCALENDAR"""

ev2 = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:async-test-event-002@example.com
DTSTAMP:20060712T182145Z
DTSTART:20060715T170000Z
DTEND:20060716T040000Z
SUMMARY:Second Async Test Event
END:VEVENT
END:VCALENDAR"""

todo1 = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:async-test-todo-001@example.com
DTSTAMP:20060712T182145Z
SUMMARY:Async Test Todo
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""

todo2 = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:async-test-todo-002@example.com
DTSTAMP:20060712T182145Z
SUMMARY:Completed Async Todo
STATUS:COMPLETED
END:VTODO
END:VCALENDAR"""


async def save_event(calendar: Any, data: str) -> Any:
    """Helper to save an event to a calendar."""
    from caldav.async_davobject import AsyncEvent

    event = AsyncEvent(parent=calendar, data=data)
    await event.save()
    return event


async def save_todo(calendar: Any, data: str) -> Any:
    """Helper to save a todo to a calendar."""
    from caldav.async_davobject import AsyncTodo

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

    # Class-level tracking for patched methods
    _original_search = None

    @pytest.fixture(scope="class")
    def test_server(self) -> TestServer:
        """Get the test server for this class."""
        server = self.server
        server.start()
        yield server
        # Stop the server to free the port for other test modules
        server.stop()

    @pytest_asyncio.fixture
    async def async_client(self, test_server: TestServer) -> Any:
        """Create an async client connected to the test server."""
        from caldav.async_collection import AsyncCalendar

        client = await test_server.get_async_client()

        # Apply search-cache delay if needed (similar to sync tests)
        search_cache_config = client.features.is_supported("search-cache", dict)
        if search_cache_config.get("behaviour") == "delay":
            delay = search_cache_config.get("delay", 1.5)
            # Only wrap once - store original and check before wrapping
            if AsyncFunctionalTestsBaseClass._original_search is None:
                AsyncFunctionalTestsBaseClass._original_search = AsyncCalendar.search
                AsyncCalendar.search = _async_delay_decorator(
                    AsyncFunctionalTestsBaseClass._original_search, t=delay
                )

        yield client
        await client.close()

    @pytest_asyncio.fixture
    async def async_principal(self, async_client: Any) -> Any:
        """Get the principal for the async client."""
        from caldav.async_collection import AsyncPrincipal
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
        """Create a test calendar and clean up afterwards."""
        from caldav.async_collection import AsyncCalendarSet, AsyncPrincipal
        from caldav.lib.error import AuthorizationError, MkcalendarError, NotFoundError

        calendar_name = f"async-test-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        calendar = None

        # Try principal-based calendar creation first (works for Baikal, Xandikos)
        try:
            principal = await AsyncPrincipal.create(async_client)
            calendar = await principal.make_calendar(name=calendar_name)
        except (NotFoundError, AuthorizationError, MkcalendarError):
            # Fall back to direct calendar creation (works for Radicale)
            pass

        if calendar is None:
            # Fall back to creating calendar at client URL
            calendar_home = AsyncCalendarSet(client=async_client, url=async_client.url)
            calendar = await calendar_home.make_calendar(name=calendar_name)

        yield calendar

        # Cleanup
        try:
            await calendar.delete()
        except Exception:
            pass

    # ==================== Test Methods ====================

    @pytest.mark.asyncio
    async def test_principal_calendars(self, async_client: Any) -> None:
        """Test getting calendars from calendar home."""
        from caldav.async_collection import AsyncCalendarSet

        # Use calendar set at client URL to get calendars
        # This bypasses principal discovery which some servers don't support
        calendar_home = AsyncCalendarSet(client=async_client, url=async_client.url)
        calendars = await calendar_home.calendars()
        assert isinstance(calendars, list)

    @pytest.mark.asyncio
    async def test_principal_make_calendar(self, async_client: Any) -> None:
        """Test creating and deleting a calendar."""
        from caldav.async_collection import AsyncCalendarSet, AsyncPrincipal
        from caldav.lib.error import AuthorizationError, MkcalendarError, NotFoundError

        calendar_name = f"async-principal-test-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        calendar = None

        # Try principal-based calendar creation first (works for Baikal, Xandikos)
        try:
            principal = await AsyncPrincipal.create(async_client)
            calendar = await principal.make_calendar(name=calendar_name)
        except (NotFoundError, AuthorizationError, MkcalendarError):
            # Fall back to direct calendar creation (works for Radicale)
            pass

        if calendar is None:
            # Fall back to creating calendar at client URL
            calendar_home = AsyncCalendarSet(client=async_client, url=async_client.url)
            calendar = await calendar_home.make_calendar(name=calendar_name)

        assert calendar is not None
        assert calendar.url is not None

        # Clean up
        await calendar.delete()

    @pytest.mark.asyncio
    async def test_search_events(self, async_calendar: Any) -> None:
        """Test searching for events."""
        from caldav.async_davobject import AsyncEvent

        # Add test events
        await save_event(async_calendar, ev1)
        await save_event(async_calendar, ev2)

        # Search for all events
        events = await async_calendar.search(event=True)

        assert len(events) >= 2
        assert all(isinstance(e, AsyncEvent) for e in events)

    @pytest.mark.asyncio
    async def test_search_events_by_date_range(self, async_calendar: Any) -> None:
        """Test searching for events in a date range."""
        # Add test event
        await save_event(async_calendar, ev1)

        # Search for events in the date range
        events = await async_calendar.search(
            event=True,
            start=datetime(2006, 7, 14),
            end=datetime(2006, 7, 16),
        )

        assert len(events) >= 1
        assert "Async Test Event" in events[0].data

    @pytest.mark.asyncio
    async def test_search_todos_pending(self, async_calendar: Any) -> None:
        """Test searching for pending todos."""
        from caldav.async_davobject import AsyncTodo

        # Add pending and completed todos
        await save_todo(async_calendar, todo1)
        await save_todo(async_calendar, todo2)

        # Search for pending todos only (default)
        todos = await async_calendar.search(todo=True, include_completed=False)

        # Should only get the pending todo
        assert len(todos) >= 1
        assert all(isinstance(t, AsyncTodo) for t in todos)
        assert any("NEEDS-ACTION" in t.data for t in todos)

    @pytest.mark.asyncio
    async def test_search_todos_all(self, async_calendar: Any) -> None:
        """Test searching for all todos including completed."""
        # Add pending and completed todos
        await save_todo(async_calendar, todo1)
        await save_todo(async_calendar, todo2)

        # Search for all todos
        todos = await async_calendar.search(todo=True, include_completed=True)

        # Should get both todos
        assert len(todos) >= 2

    @pytest.mark.asyncio
    async def test_events_method(self, async_calendar: Any) -> None:
        """Test the events() convenience method."""
        from caldav.async_davobject import AsyncEvent

        # Add test events
        await save_event(async_calendar, ev1)
        await save_event(async_calendar, ev2)

        # Get all events
        events = await async_calendar.events()

        assert len(events) >= 2
        assert all(isinstance(e, AsyncEvent) for e in events)

    @pytest.mark.asyncio
    async def test_todos_method(self, async_calendar: Any) -> None:
        """Test the todos() convenience method."""
        from caldav.async_davobject import AsyncTodo

        # Add test todos
        await save_todo(async_calendar, todo1)

        # Get all pending todos
        todos = await async_calendar.todos()

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
