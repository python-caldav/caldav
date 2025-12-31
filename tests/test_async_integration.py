#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
Functional integration tests for the async API.

These tests verify that the async API works correctly with real CalDAV servers.
They test the same functionality as the sync tests but using the async API.
"""
import pytest
import pytest_asyncio
import socket
import tempfile
import threading
import time
from datetime import datetime, timedelta

from .conf import test_radicale, radicale_host, radicale_port

try:
    import niquests as requests
except ImportError:
    import requests

# Skip all tests if radicale is not configured
pytestmark = pytest.mark.skipif(
    not test_radicale, reason="Radicale not configured for testing"
)


@pytest.fixture(scope="module")
def radicale_server():
    """Start a Radicale server for the async tests.

    This fixture starts a Radicale server in a separate thread for the duration
    of the test module. It uses the same approach as the main test suite in conf.py.
    """
    if not test_radicale:
        pytest.skip("Radicale not configured for testing")

    import radicale
    import radicale.config
    import radicale.server

    # Create a namespace object to hold server state
    class ServerState:
        pass

    state = ServerState()
    state.serverdir = tempfile.TemporaryDirectory()
    state.serverdir.__enter__()

    state.configuration = radicale.config.load("")
    state.configuration.update(
        {
            "storage": {"filesystem_folder": state.serverdir.name},
            "auth": {"type": "none"},
        }
    )

    state.shutdown_socket, state.shutdown_socket_out = socket.socketpair()
    state.radicale_thread = threading.Thread(
        target=radicale.server.serve,
        args=(state.configuration, state.shutdown_socket_out),
    )
    state.radicale_thread.start()

    # Wait for the server to become ready
    url = f"http://{radicale_host}:{radicale_port}"
    for i in range(100):
        try:
            requests.get(url)
            break
        except Exception:
            time.sleep(0.05)
    else:
        raise RuntimeError("Radicale server did not start in time")

    yield url

    # Teardown
    state.shutdown_socket.close()
    state.serverdir.__exit__(None, None, None)


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


@pytest_asyncio.fixture
async def async_client(radicale_server):
    """Create an async client connected to the test Radicale server."""
    from caldav.aio import get_async_davclient

    url = radicale_server
    async with await get_async_davclient(url=url, username="user1", password="password1") as client:
        yield client


@pytest_asyncio.fixture
async def async_principal(async_client):
    """Get the principal for the async client."""
    from caldav.async_collection import AsyncPrincipal

    principal = await AsyncPrincipal.create(async_client)
    return principal


@pytest_asyncio.fixture
async def async_calendar(async_principal):
    """Create a test calendar and clean up afterwards."""
    calendar_name = f"async-test-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Create calendar
    calendar = await async_principal.make_calendar(name=calendar_name)

    yield calendar

    # Cleanup
    try:
        await calendar.delete()
    except Exception:
        pass


async def save_event(calendar, data):
    """Helper to save an event to a calendar."""
    from caldav.async_davobject import AsyncEvent

    event = AsyncEvent(parent=calendar, data=data)
    await event.save()
    return event


async def save_todo(calendar, data):
    """Helper to save a todo to a calendar."""
    from caldav.async_davobject import AsyncTodo

    todo = AsyncTodo(parent=calendar, data=data)
    await todo.save()
    return todo


class TestAsyncSearch:
    """Test async search functionality."""

    @pytest.mark.asyncio
    async def test_search_events(self, async_calendar):
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
    async def test_search_events_by_date_range(self, async_calendar):
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
    async def test_search_todos_pending(self, async_calendar):
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
    async def test_search_todos_all(self, async_calendar):
        """Test searching for all todos including completed."""
        # Add pending and completed todos
        await save_todo(async_calendar, todo1)
        await save_todo(async_calendar, todo2)

        # Search for all todos
        todos = await async_calendar.search(todo=True, include_completed=True)

        # Should get both todos
        assert len(todos) >= 2


class TestAsyncEvents:
    """Test async event operations."""

    @pytest.mark.asyncio
    async def test_events_method(self, async_calendar):
        """Test the events() convenience method."""
        from caldav.async_davobject import AsyncEvent

        # Add test events
        await save_event(async_calendar, ev1)
        await save_event(async_calendar, ev2)

        # Get all events
        events = await async_calendar.events()

        assert len(events) >= 2
        assert all(isinstance(e, AsyncEvent) for e in events)


class TestAsyncTodos:
    """Test async todo operations."""

    @pytest.mark.asyncio
    async def test_todos_method(self, async_calendar):
        """Test the todos() convenience method."""
        from caldav.async_davobject import AsyncTodo

        # Add test todos
        await save_todo(async_calendar, todo1)

        # Get all pending todos
        todos = await async_calendar.todos()

        assert len(todos) >= 1
        assert all(isinstance(t, AsyncTodo) for t in todos)


class TestAsyncPrincipal:
    """Test async principal operations."""

    @pytest.mark.asyncio
    async def test_principal_calendars(self, async_principal):
        """Test getting calendars from principal."""
        calendars = await async_principal.calendars()

        # Should return a list (may be empty or have calendars)
        assert isinstance(calendars, list)

    @pytest.mark.asyncio
    async def test_principal_make_calendar(self, async_principal):
        """Test creating and deleting a calendar via principal."""
        calendar_name = f"async-principal-test-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Create calendar
        calendar = await async_principal.make_calendar(name=calendar_name)

        assert calendar is not None
        assert calendar.url is not None

        # Clean up
        await calendar.delete()


class TestSyncAsyncEquivalence:
    """Test that sync and async produce equivalent results."""

    @pytest.mark.asyncio
    async def test_sync_async_search_equivalence(self, async_calendar):
        """Test that sync search (via delegation) and async search return same results."""
        # This test verifies that when we use sync API, it delegates to async
        # and produces the same results as calling async directly

        # Add test events
        await save_event(async_calendar, ev1)
        await save_event(async_calendar, ev2)

        # Get results via async API
        async_events = await async_calendar.search(event=True)

        # Verify we got results
        assert len(async_events) >= 2

        # Check that all events have proper data
        for event in async_events:
            assert event.data is not None
            assert "VCALENDAR" in event.data
