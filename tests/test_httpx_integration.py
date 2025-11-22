#!/usr/bin/env python
"""
Simple integration tests for the httpx async-first implementation.

Tests both sync and async clients against a live CalDAV server.
Requires a running CalDAV server (e.g., Nextcloud, Radicale).

These tests are skipped by default unless CALDAV_TEST_URL is set,
or a server is reachable at the default URL.

Usage:
    # With explicit server URL
    CALDAV_TEST_URL=http://localhost:8080/remote.php/dav pytest tests/test_httpx_integration.py -v

    # Or just run if server is at default location
    pytest tests/test_httpx_integration.py -v

Environment variables:
    CALDAV_TEST_URL - CalDAV server URL (enables tests when set)
    CALDAV_USER - Username (default: admin)
    CALDAV_PASS - Password (default: admin)
"""
import os
import uuid
from datetime import datetime
from datetime import timedelta

import pytest

# Test configuration from environment or defaults
# Use CALDAV_TEST_URL to explicitly enable these tests
CALDAV_URL = os.environ.get("CALDAV_TEST_URL", "http://localhost:8080/remote.php/dav")
CALDAV_USER = os.environ.get("CALDAV_USER", "admin")
CALDAV_PASS = os.environ.get("CALDAV_PASS", "admin")


def _server_reachable():
    """Check if the CalDAV server is reachable."""
    try:
        import httpx

        with httpx.Client(timeout=5.0) as client:
            response = client.get(CALDAV_URL)
            # Accept any response - server is reachable
            return True
    except Exception:
        return False


# Skip all tests in this module if server not reachable and not explicitly enabled
_explicit_url = "CALDAV_TEST_URL" in os.environ
_server_available = _server_reachable() if not _explicit_url else True

pytestmark = pytest.mark.skipif(
    not _explicit_url and not _server_available,
    reason="CalDAV server not available. Set CALDAV_TEST_URL to enable.",
)


# Sample iCalendar data
def make_event_ical(uid: str, summary: str, start: datetime, end: datetime) -> str:
    """Create a simple VEVENT iCalendar string."""
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}
DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}
SUMMARY:{summary}
END:VEVENT
END:VCALENDAR"""


def make_todo_ical(uid: str, summary: str) -> str:
    """Create a simple VTODO iCalendar string."""
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VTODO
UID:{uid}
DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}
SUMMARY:{summary}
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""


class TestSyncClient:
    """Tests for the synchronous DAVClient."""

    @pytest.fixture
    def client(self):
        """Create a sync DAVClient."""
        from caldav import DAVClient

        client = DAVClient(url=CALDAV_URL, username=CALDAV_USER, password=CALDAV_PASS)
        yield client

    @pytest.fixture
    def test_calendar(self, client):
        """Create a test calendar, yield it, then clean up."""
        principal = client.principal()
        cal_id = f"test-sync-{uuid.uuid4().hex[:8]}"
        calendar = principal.make_calendar(
            name=f"Test Calendar {cal_id}", cal_id=cal_id
        )
        yield calendar
        # Cleanup
        try:
            calendar.delete()
        except Exception:
            pass

    def test_connect_and_get_principal(self, client):
        """Test basic connection and principal retrieval."""
        principal = client.principal()
        assert principal is not None

    def test_list_calendars(self, client):
        """Test listing calendars."""
        principal = client.principal()
        calendars = principal.calendars()
        assert isinstance(calendars, list)
        # Should have at least one calendar (default)
        assert len(calendars) >= 1

    def test_create_and_delete_calendar(self, client):
        """Test calendar creation and deletion."""
        principal = client.principal()
        cal_id = f"test-create-{uuid.uuid4().hex[:8]}"

        # Create
        calendar = principal.make_calendar(name=f"Test {cal_id}", cal_id=cal_id)
        assert calendar is not None

        # Verify it exists
        calendars = principal.calendars()
        cal_urls = [str(c.url) for c in calendars]
        assert any(cal_id in url for url in cal_urls)

        # Delete
        calendar.delete()

        # Verify it's gone
        calendars = principal.calendars()
        cal_urls = [str(c.url) for c in calendars]
        assert not any(cal_id in url for url in cal_urls)

    def test_create_read_delete_event(self, test_calendar):
        """Test event CRUD operations."""
        uid = f"test-event-{uuid.uuid4().hex}"
        start = datetime.utcnow() + timedelta(days=1)
        end = start + timedelta(hours=1)
        ical_data = make_event_ical(uid, "Test Event", start, end)

        # Create
        event = test_calendar.save_event(ical_data)
        assert event is not None

        # Read back
        events = test_calendar.events()
        assert len(events) >= 1
        assert any(uid in e.data for e in events)

        # Delete
        event.delete()

        # Verify deleted
        events = test_calendar.events()
        assert not any(uid in e.data for e in events)

    def test_create_read_delete_todo(self, test_calendar):
        """Test todo CRUD operations."""
        uid = f"test-todo-{uuid.uuid4().hex}"
        ical_data = make_todo_ical(uid, "Test Todo")

        # Create
        todo = test_calendar.save_todo(ical_data)
        assert todo is not None

        # Read back
        todos = test_calendar.todos()
        assert len(todos) >= 1
        assert any(uid in t.data for t in todos)

        # Delete
        todo.delete()

    def test_search_events(self, test_calendar):
        """Test event search functionality."""
        # Create a few events
        now = datetime.utcnow()
        events_data = []
        for i in range(3):
            uid = f"search-test-{uuid.uuid4().hex}"
            start = now + timedelta(days=i + 1)
            end = start + timedelta(hours=1)
            ical_data = make_event_ical(uid, f"Search Event {i}", start, end)
            test_calendar.save_event(ical_data)
            events_data.append((uid, start, end))

        # Search for events in the date range
        search_start = now
        search_end = now + timedelta(days=5)
        results = test_calendar.search(
            start=search_start,
            end=search_end,
            event=True,
            expand=False,
        )

        # Should find all 3 events
        assert len(results) >= 3


class TestAsyncClient:
    """Tests for the asynchronous AsyncDAVClient."""

    pytestmark = pytest.mark.anyio

    @pytest.fixture
    def anyio_backend(self):
        """Use asyncio backend for async tests."""
        return "asyncio"

    @pytest.fixture
    def async_client(self):
        """Create an async DAVClient."""
        from caldav.aio import AsyncDAVClient

        client = AsyncDAVClient(
            url=CALDAV_URL, username=CALDAV_USER, password=CALDAV_PASS
        )
        return client

    async def test_connect_and_get_principal(self, async_client):
        """Test basic async connection and principal retrieval."""
        principal = await async_client.principal()
        assert principal is not None

    async def test_list_calendars(self, async_client):
        """Test async listing calendars."""
        principal = await async_client.principal()
        calendars = await principal.calendars()
        assert isinstance(calendars, list)
        assert len(calendars) >= 1

    async def test_create_and_delete_calendar(self, async_client):
        """Test async calendar creation and deletion."""
        principal = await async_client.principal()
        cal_id = f"test-async-{uuid.uuid4().hex[:8]}"

        # Create
        calendar = await principal.make_calendar(
            name=f"Async Test {cal_id}", cal_id=cal_id
        )
        assert calendar is not None

        # Verify exists
        calendars = await principal.calendars()
        cal_urls = [str(c.url) for c in calendars]
        assert any(cal_id in url for url in cal_urls)

        # Delete
        await calendar.delete()

        # Verify gone
        calendars = await principal.calendars()
        cal_urls = [str(c.url) for c in calendars]
        assert not any(cal_id in url for url in cal_urls)

    async def test_create_read_delete_event(self, async_client):
        """Test async event CRUD operations."""
        principal = await async_client.principal()
        cal_id = f"test-async-event-{uuid.uuid4().hex[:8]}"
        calendar = await principal.make_calendar(
            name=f"Async Event Test {cal_id}", cal_id=cal_id
        )

        try:
            uid = f"async-event-{uuid.uuid4().hex}"
            start = datetime.utcnow() + timedelta(days=1)
            end = start + timedelta(hours=1)
            ical_data = make_event_ical(uid, "Async Test Event", start, end)

            # Create
            event = await calendar.save_event(ical_data)
            assert event is not None

            # Read back
            events = await calendar.events()
            assert len(events) >= 1
            assert any(uid in e.data for e in events)

            # Delete event
            await event.delete()
        finally:
            # Cleanup calendar
            await calendar.delete()

    async def test_search_events(self, async_client):
        """Test async event search functionality."""
        principal = await async_client.principal()
        cal_id = f"test-async-search-{uuid.uuid4().hex[:8]}"
        calendar = await principal.make_calendar(
            name=f"Async Search Test {cal_id}", cal_id=cal_id
        )

        try:
            now = datetime.utcnow()
            for i in range(3):
                uid = f"async-search-{uuid.uuid4().hex}"
                start = now + timedelta(days=i + 1)
                end = start + timedelta(hours=1)
                ical_data = make_event_ical(uid, f"Async Search Event {i}", start, end)
                await calendar.save_event(ical_data)

            # Search
            search_start = now
            search_end = now + timedelta(days=5)
            results = await calendar.search(
                start=search_start,
                end=search_end,
                event=True,
                expand=False,
            )

            assert len(results) >= 3
        finally:
            await calendar.delete()


# Allow running directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
