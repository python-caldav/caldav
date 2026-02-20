"""
Integration tests for the caldav.jmap package against a live Cyrus IMAP server.

These tests require the Cyrus Docker container to be running:

    docker-compose -f tests/docker-test-servers/cyrus/docker-compose.yml up -d

If the server is not reachable on port 8802 the entire module is skipped
automatically — no failure, no noise.

Cyrus JMAP endpoint: http://localhost:8802/.well-known/jmap
Test credentials:    user1 / x
"""

import pytest

try:
    from niquests.auth import HTTPBasicAuth
except ImportError:
    from requests.auth import HTTPBasicAuth  # type: ignore[no-redef]

from caldav.jmap import JMAPClient
from caldav.jmap.constants import CALENDAR_CAPABILITY
from caldav.jmap.session import fetch_session

CYRUS_HOST = "localhost"
CYRUS_PORT = 8802
JMAP_URL = f"http://{CYRUS_HOST}:{CYRUS_PORT}/.well-known/jmap"
CYRUS_USERNAME = "user1"
CYRUS_PASSWORD = "x"


def _cyrus_reachable() -> bool:
    import socket

    try:
        with socket.create_connection((CYRUS_HOST, CYRUS_PORT), timeout=2):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _cyrus_reachable(),
    reason=f"Cyrus Docker not reachable on {CYRUS_HOST}:{CYRUS_PORT} — "
    "start it with: docker-compose -f tests/docker-test-servers/cyrus/docker-compose.yml up -d",
)


@pytest.fixture(scope="module")
def client():
    return JMAPClient(url=JMAP_URL, username=CYRUS_USERNAME, password=CYRUS_PASSWORD)


@pytest.fixture(scope="module")
def session():
    return fetch_session(JMAP_URL, auth=HTTPBasicAuth(CYRUS_USERNAME, CYRUS_PASSWORD))


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
