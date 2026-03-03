"""
Integration tests for the caldav.jmap package against live JMAP servers.

Cyrus (port 8802):
    docker-compose -f tests/docker-test-servers/cyrus/docker-compose.yml up -d

Stalwart (port 8806):
    docker-compose -f tests/docker-test-servers/stalwart/docker-compose.yml up -d
    ./tests/docker-test-servers/stalwart/setup_stalwart.sh

Each server's test classes are skipped automatically when that server is not
reachable — no failure, no noise.
"""

import socket
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

try:
    from niquests.auth import HTTPBasicAuth
except ImportError:
    from requests.auth import HTTPBasicAuth  # type: ignore[no-redef]

from caldav.jmap import AsyncJMAPClient, JMAPClient
from caldav.jmap.constants import CALENDAR_CAPABILITY
from caldav.jmap.convert import jscal_to_ical
from caldav.jmap.error import JMAPMethodError
from caldav.jmap.session import fetch_session

CYRUS_HOST = "localhost"
CYRUS_PORT = 8802
CYRUS_JMAP_URL = f"http://{CYRUS_HOST}:{CYRUS_PORT}/.well-known/jmap"
CYRUS_USERNAME = "user1"
CYRUS_PASSWORD = "x"

STALWART_HOST = "localhost"
STALWART_PORT = 8809
STALWART_JMAP_URL = f"http://{STALWART_HOST}:{STALWART_PORT}/.well-known/jmap"
STALWART_USERNAME = "testuser"
STALWART_PASSWORD = "testpass"


def _reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


_cyrus_up = _reachable(CYRUS_HOST, CYRUS_PORT)
_stalwart_up = _reachable(STALWART_HOST, STALWART_PORT)

# Backward-compatible alias used by the module-level pytestmark below.
# The mark only gates tests that don't carry their own skipif marker.
pytestmark = pytest.mark.skipif(
    not _cyrus_up,
    reason=f"Cyrus Docker not reachable on {CYRUS_HOST}:{CYRUS_PORT} — "
    "start it with: docker-compose -f tests/docker-test-servers/cyrus/docker-compose.yml up -d",
)


def _minimal_ical(title: str = "Test Event", start: datetime | None = None) -> str:
    if start is None:
        start = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    uid = str(uuid.uuid4())
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//test//test//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"SUMMARY:{title}\r\n"
        f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}\r\n"
        f"DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


@pytest.fixture(scope="module")
def client():
    return JMAPClient(url=CYRUS_JMAP_URL, username=CYRUS_USERNAME, password=CYRUS_PASSWORD)


@pytest.fixture(scope="module")
def session():
    return fetch_session(CYRUS_JMAP_URL, auth=HTTPBasicAuth(CYRUS_USERNAME, CYRUS_PASSWORD))


@pytest.fixture(scope="module")
def calendar_id(client):
    calendars = client.get_calendars()
    assert calendars, "Cyrus did not provision any calendars for user1"
    return calendars[0].id


@pytest.fixture
def created_event_id(client, calendar_id):
    event_id = client.create_event(calendar_id, _minimal_ical("Integration Test Event"))
    yield event_id
    try:
        client.delete_event(event_id)
    except Exception:
        pass


@pytest_asyncio.fixture
async def async_client():
    return AsyncJMAPClient(url=CYRUS_JMAP_URL, username=CYRUS_USERNAME, password=CYRUS_PASSWORD)


@pytest_asyncio.fixture
async def async_calendar_id(async_client):
    calendars = await async_client.get_calendars()
    assert calendars, "Cyrus did not provision any calendars for user1"
    return calendars[0].id


@pytest_asyncio.fixture
async def async_created_event_id(async_client, async_calendar_id):
    event_id = await async_client.create_event(
        async_calendar_id, _minimal_ical("Async Integration Test Event")
    )
    yield event_id
    try:
        await async_client.delete_event(event_id)
    except Exception:
        pass


_stalwart_skip = pytest.mark.skipif(
    not _stalwart_up,
    reason=f"Stalwart Docker not reachable on {STALWART_HOST}:{STALWART_PORT} — "
    "start it with: cd tests/docker-test-servers/stalwart && ./start.sh",
)


@pytest.fixture(scope="module")
def stalwart_client():
    return JMAPClient(url=STALWART_JMAP_URL, username=STALWART_USERNAME, password=STALWART_PASSWORD)


@pytest.fixture(scope="module")
def stalwart_calendar_id(stalwart_client):
    calendars = stalwart_client.get_calendars()
    assert calendars, "Stalwart did not return any calendars for user1"
    return calendars[0].id


@pytest.fixture
def stalwart_event_id(stalwart_client, stalwart_calendar_id):
    event_id = stalwart_client.create_event(
        stalwart_calendar_id, _minimal_ical("Stalwart Test Event")
    )
    yield event_id
    try:
        stalwart_client.delete_event(event_id)
    except Exception:
        pass


class TestJMAPSessionIntegration:
    def test_session_fetch_returns_api_url(self, session):
        assert session.api_url
        assert session.api_url.startswith("http")

    def test_session_has_account_id(self, session):
        assert session.account_id

    def test_session_has_calendar_capability(self, session):
        assert CALENDAR_CAPABILITY in session.account_capabilities


class TestJMAPCalendarListIntegration:
    def test_list_calendars_returns_list(self, client):
        calendars = client.get_calendars()
        assert isinstance(calendars, list)

    def test_calendars_have_id_and_name(self, client):
        calendars = client.get_calendars()
        assert len(calendars) >= 1, "Expected at least one calendar on Cyrus for user1"
        for cal in calendars:
            assert cal.id, f"Calendar missing id: {cal}"
            assert cal.name, f"Calendar has empty name: {cal}"


class TestJMAPEventIntegration:
    def test_event_create_get(self, client, created_event_id):
        obj = client.get_event(created_event_id)
        ical = jscal_to_ical(obj.get_data())
        assert "BEGIN:VCALENDAR" in ical
        assert "Integration Test Event" in ical

    def test_event_update(self, client, created_event_id):
        client.update_event(created_event_id, _minimal_ical("Updated Title"))
        obj = client.get_event(created_event_id)
        assert "Updated Title" in jscal_to_ical(obj.get_data())

    def test_event_delete(self, client, calendar_id):
        event_id = client.create_event(calendar_id, _minimal_ical("To Be Deleted"))
        client.delete_event(event_id)
        with pytest.raises(JMAPMethodError):
            client.get_event(event_id)

    def test_event_query_time_range(self, client, calendar_id, created_event_id):
        results = client.search_events(
            calendar_id=calendar_id,
            start="2026-06-01T00:00:00",
            end="2026-06-02T00:00:00",
        )
        assert len(results) >= 1
        assert any("Integration Test Event" in jscal_to_ical(r.get_data()) for r in results)

    def test_event_sync(self, client, calendar_id):
        token_before = client.get_sync_token()
        event_id = client.create_event(calendar_id, _minimal_ical("Sync Test Event"))
        try:
            added, _modified, _deleted = client.get_objects_by_sync_token(token_before)
            assert any("Sync Test Event" in jscal_to_ical(a.get_data()) for a in added)
        finally:
            client.delete_event(event_id)

    def test_ical_roundtrip(self, client, calendar_id):
        start = datetime(2026, 7, 15, 9, 0, 0, tzinfo=timezone.utc)
        event_id = client.create_event(calendar_id, _minimal_ical("Roundtrip Event", start=start))
        try:
            fetched = jscal_to_ical(client.get_event(event_id).get_data())
            assert "Roundtrip Event" in fetched
            assert "20260715" in fetched
        finally:
            client.delete_event(event_id)


class TestAsyncJMAPEventIntegration:
    @pytest.mark.asyncio
    async def test_event_create_get(self, async_client, async_created_event_id):
        obj = await async_client.get_event(async_created_event_id)
        ical = jscal_to_ical(obj.get_data())
        assert "BEGIN:VCALENDAR" in ical
        assert "Async Integration Test Event" in ical

    @pytest.mark.asyncio
    async def test_event_update(self, async_client, async_created_event_id):
        await async_client.update_event(
            async_created_event_id, _minimal_ical("Async Updated Title")
        )
        obj = await async_client.get_event(async_created_event_id)
        assert "Async Updated Title" in jscal_to_ical(obj.get_data())

    @pytest.mark.asyncio
    async def test_event_delete(self, async_client, async_calendar_id):
        event_id = await async_client.create_event(
            async_calendar_id, _minimal_ical("Async To Be Deleted")
        )
        await async_client.delete_event(event_id)
        with pytest.raises(JMAPMethodError):
            await async_client.get_event(event_id)

    @pytest.mark.asyncio
    async def test_event_query_time_range(
        self, async_client, async_calendar_id, async_created_event_id
    ):
        results = await async_client.search_events(
            calendar_id=async_calendar_id,
            start="2026-06-01T00:00:00",
            end="2026-06-02T00:00:00",
        )
        assert len(results) >= 1
        assert any("Async Integration Test Event" in jscal_to_ical(r.get_data()) for r in results)

    @pytest.mark.asyncio
    async def test_event_sync(self, async_client, async_calendar_id):
        token_before = await async_client.get_sync_token()
        event_id = await async_client.create_event(
            async_calendar_id, _minimal_ical("Async Sync Test Event")
        )
        try:
            added, _modified, _deleted = await async_client.get_objects_by_sync_token(token_before)
            assert any("Async Sync Test Event" in jscal_to_ical(a.get_data()) for a in added)
        finally:
            await async_client.delete_event(event_id)

    @pytest.mark.asyncio
    async def test_ical_roundtrip(self, async_client, async_calendar_id):
        start = datetime(2026, 7, 15, 9, 0, 0, tzinfo=timezone.utc)
        event_id = await async_client.create_event(
            async_calendar_id, _minimal_ical("Async Roundtrip Event", start=start)
        )
        try:
            fetched = jscal_to_ical((await async_client.get_event(event_id)).get_data())
            assert "Async Roundtrip Event" in fetched
            assert "20260715" in fetched
        finally:
            await async_client.delete_event(event_id)


@_stalwart_skip
class TestStalwartJMAPCalendarListIntegration:
    def test_list_calendars_returns_list(self, stalwart_client):
        calendars = stalwart_client.get_calendars()
        assert isinstance(calendars, list)

    def test_calendars_have_id_and_name(self, stalwart_client):
        calendars = stalwart_client.get_calendars()
        assert len(calendars) >= 1, "Expected at least one calendar on Stalwart for user1"
        for cal in calendars:
            assert cal.id, f"Calendar missing id: {cal}"
            assert cal.name, f"Calendar has empty name: {cal}"


@_stalwart_skip
class TestStalwartJMAPEventIntegration:
    def test_event_create_get(self, stalwart_client, stalwart_event_id):
        obj = stalwart_client.get_event(stalwart_event_id)
        ical = jscal_to_ical(obj.get_data())
        assert "BEGIN:VCALENDAR" in ical
        assert "Stalwart Test Event" in ical

    def test_event_update(self, stalwart_client, stalwart_event_id):
        stalwart_client.update_event(stalwart_event_id, _minimal_ical("Stalwart Updated Title"))
        obj = stalwart_client.get_event(stalwart_event_id)
        assert "Stalwart Updated Title" in jscal_to_ical(obj.get_data())

    def test_event_delete(self, stalwart_client, stalwart_calendar_id):
        event_id = stalwart_client.create_event(
            stalwart_calendar_id, _minimal_ical("Stalwart To Be Deleted")
        )
        stalwart_client.delete_event(event_id)
        with pytest.raises(JMAPMethodError):
            stalwart_client.get_event(event_id)

    def test_event_query_time_range(self, stalwart_client, stalwart_event_id):
        # Stalwart does not support the inCalendars filter; query without calendar_id.
        results = stalwart_client.search_events(
            start="2026-06-01T00:00:00",
            end="2026-06-02T00:00:00",
        )
        assert len(results) >= 1
        assert any("Stalwart Test Event" in jscal_to_ical(r.get_data()) for r in results)

    def test_ical_roundtrip(self, stalwart_client, stalwart_calendar_id):
        start = datetime(2026, 7, 15, 9, 0, 0, tzinfo=timezone.utc)
        event_id = stalwart_client.create_event(
            stalwart_calendar_id, _minimal_ical("Stalwart Roundtrip Event", start=start)
        )
        try:
            fetched = jscal_to_ical(stalwart_client.get_event(event_id).get_data())
            assert "Stalwart Roundtrip Event" in fetched
            assert "20260715" in fetched
        finally:
            stalwart_client.delete_event(event_id)
