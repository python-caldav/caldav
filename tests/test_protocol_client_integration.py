"""
Integration tests for Sans-I/O protocol clients.

These tests verify that SyncProtocolClient and AsyncProtocolClient
work correctly against real CalDAV servers.
"""

from datetime import datetime
from typing import Any

import pytest
import pytest_asyncio

from caldav.protocol_client import SyncProtocolClient, AsyncProtocolClient
from .test_servers import TestServer, get_available_servers


# Test iCalendar data
TEST_EVENT = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Protocol Client//EN
BEGIN:VEVENT
UID:protocol-test-event-001@example.com
DTSTAMP:20240101T120000Z
DTSTART:20240115T100000Z
DTEND:20240115T110000Z
SUMMARY:Protocol Test Event
END:VEVENT
END:VCALENDAR"""


class ProtocolClientTestsBaseClass:
    """
    Base class for protocol client integration tests.

    Subclasses are dynamically generated for each configured test server.
    """

    server: TestServer

    @pytest.fixture(scope="class")
    def test_server(self) -> TestServer:
        """Get the test server for this class."""
        server = self.server
        server.start()
        yield server
        server.stop()

    @pytest.fixture
    def sync_client(self, test_server: TestServer) -> SyncProtocolClient:
        """Create a sync protocol client connected to the test server."""
        client = SyncProtocolClient(
            base_url=test_server.url,
            username=test_server.username,
            password=test_server.password,
        )
        yield client
        client.close()

    @pytest_asyncio.fixture
    async def async_client(self, test_server: TestServer) -> AsyncProtocolClient:
        """Create an async protocol client connected to the test server."""
        client = AsyncProtocolClient(
            base_url=test_server.url,
            username=test_server.username,
            password=test_server.password,
        )
        yield client
        await client.close()

    # ==================== Sync Protocol Client Tests ====================

    def test_sync_propfind_root(self, sync_client: SyncProtocolClient) -> None:
        """Test PROPFIND on server root."""
        results = sync_client.propfind("/", ["displayname", "resourcetype"], depth=0)

        # Should get at least one result for the root resource
        assert len(results) >= 1
        # Root should have an href
        assert results[0].href is not None

    def test_sync_propfind_depth_1(self, sync_client: SyncProtocolClient) -> None:
        """Test PROPFIND with depth=1 to list children."""
        results = sync_client.propfind("/", ["displayname", "resourcetype"], depth=1)

        # Should get the root and its children
        assert len(results) >= 1

    def test_sync_options(self, sync_client: SyncProtocolClient) -> None:
        """Test OPTIONS request."""
        response = sync_client.options("/")

        # OPTIONS should return 200 or 204
        assert response.status in (200, 204)
        # Should have DAV header (optional but common)
        # Some servers don't return Allow header for OPTIONS on root
        assert response.ok

    def test_sync_calendar_operations(
        self, sync_client: SyncProtocolClient, test_server: TestServer
    ) -> None:
        """Test creating and deleting a calendar."""
        # Create a unique calendar path
        calendar_name = f"protocol-test-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        calendar_path = f"/{calendar_name}/"

        # Create calendar
        response = sync_client.mkcalendar(
            calendar_path,
            displayname=f"Protocol Test Calendar {calendar_name}",
        )
        # MKCALENDAR should return 201 Created
        assert response.status == 201

        try:
            # Verify calendar exists with PROPFIND
            results = sync_client.propfind(calendar_path, ["displayname"], depth=0)
            assert len(results) >= 1
        finally:
            # Clean up - delete the calendar
            response = sync_client.delete(calendar_path)
            assert response.status in (200, 204)

    def test_sync_put_get_delete_event(
        self, sync_client: SyncProtocolClient
    ) -> None:
        """Test PUT, GET, DELETE workflow for an event."""
        # Create a unique calendar for this test
        calendar_name = f"protocol-event-test-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        calendar_path = f"/{calendar_name}/"
        event_path = f"{calendar_path}test-event.ics"

        # Create calendar first
        sync_client.mkcalendar(calendar_path)

        try:
            # PUT event
            put_response = sync_client.put(event_path, TEST_EVENT)
            assert put_response.status in (201, 204)

            # GET event
            get_response = sync_client.get(event_path)
            assert get_response.status == 200
            assert b"VCALENDAR" in get_response.body

            # DELETE event
            delete_response = sync_client.delete(event_path)
            assert delete_response.status in (200, 204)
        finally:
            # Clean up calendar
            sync_client.delete(calendar_path)

    # ==================== Async Protocol Client Tests ====================

    @pytest.mark.asyncio
    async def test_async_propfind_root(
        self, async_client: AsyncProtocolClient
    ) -> None:
        """Test async PROPFIND on server root."""
        results = await async_client.propfind(
            "/", ["displayname", "resourcetype"], depth=0
        )

        assert len(results) >= 1
        assert results[0].href is not None

    @pytest.mark.asyncio
    async def test_async_options(self, async_client: AsyncProtocolClient) -> None:
        """Test async OPTIONS request."""
        response = await async_client.options("/")

        assert response.status in (200, 204)
        assert response.ok

    @pytest.mark.asyncio
    async def test_async_calendar_operations(
        self, async_client: AsyncProtocolClient
    ) -> None:
        """Test async calendar creation and deletion."""
        calendar_name = f"async-protocol-test-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        calendar_path = f"/{calendar_name}/"

        # Create calendar
        response = await async_client.mkcalendar(
            calendar_path,
            displayname=f"Async Protocol Test {calendar_name}",
        )
        assert response.status == 201

        try:
            # Verify with PROPFIND
            results = await async_client.propfind(calendar_path, ["displayname"], depth=0)
            assert len(results) >= 1
        finally:
            # Clean up
            response = await async_client.delete(calendar_path)
            assert response.status in (200, 204)

    @pytest.mark.asyncio
    async def test_async_put_get_delete(
        self, async_client: AsyncProtocolClient
    ) -> None:
        """Test async PUT, GET, DELETE workflow."""
        calendar_name = f"async-event-test-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        calendar_path = f"/{calendar_name}/"
        event_path = f"{calendar_path}test-event.ics"

        # Create calendar
        await async_client.mkcalendar(calendar_path)

        try:
            # PUT event
            put_response = await async_client.put(event_path, TEST_EVENT)
            assert put_response.status in (201, 204)

            # GET event
            get_response = await async_client.get(event_path)
            assert get_response.status == 200
            assert b"VCALENDAR" in get_response.body

            # DELETE event
            delete_response = await async_client.delete(event_path)
            assert delete_response.status in (200, 204)
        finally:
            # Clean up
            await async_client.delete(calendar_path)


# ==================== Dynamic Test Class Generation ====================

_generated_classes: dict[str, type] = {}

for _server in get_available_servers():
    _classname = f"TestProtocolClientFor{_server.name.replace(' ', '')}"

    if _classname in _generated_classes:
        continue

    _test_class = type(
        _classname,
        (ProtocolClientTestsBaseClass,),
        {"server": _server},
    )

    vars()[_classname] = _test_class
    _generated_classes[_classname] = _test_class
