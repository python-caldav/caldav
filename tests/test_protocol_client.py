"""
Tests for Sans-I/O protocol client classes.

These tests verify the protocol client works correctly, using mocked I/O.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from caldav.protocol import DAVResponse
from caldav.protocol_client import SyncProtocolClient, AsyncProtocolClient


class TestSyncProtocolClient:
    """Test SyncProtocolClient."""

    def test_init(self):
        """Client should initialize protocol and I/O correctly."""
        client = SyncProtocolClient(
            base_url="https://cal.example.com",
            username="user",
            password="pass",
            timeout=60.0,
        )
        try:
            assert client.protocol.base_url == "https://cal.example.com"
            assert client.protocol._auth_header is not None
            assert client.io.timeout == 60.0
        finally:
            client.close()

    def test_context_manager(self):
        """Client should work as context manager."""
        with SyncProtocolClient(
            base_url="https://cal.example.com",
        ) as client:
            assert client.protocol is not None
        # After exit, should be closed (io.close() called)

    def test_propfind_builds_correct_request(self):
        """propfind should build correct request and parse response."""
        client = SyncProtocolClient(base_url="https://cal.example.com")

        # Mock the I/O execute method
        mock_response = DAVResponse(
            status=207,
            headers={},
            body=b"""<?xml version="1.0"?>
            <D:multistatus xmlns:D="DAV:">
                <D:response>
                    <D:href>/calendars/</D:href>
                    <D:propstat>
                        <D:prop><D:displayname>Test</D:displayname></D:prop>
                        <D:status>HTTP/1.1 200 OK</D:status>
                    </D:propstat>
                </D:response>
            </D:multistatus>""",
        )
        client.io.execute = Mock(return_value=mock_response)

        try:
            results = client.propfind("/calendars/", ["displayname"], depth=1)

            # Check request was built correctly
            call_args = client.io.execute.call_args[0][0]
            assert call_args.method.value == "PROPFIND"
            assert "calendars" in call_args.url
            assert call_args.headers["Depth"] == "1"

            # Check response was parsed correctly
            assert len(results) == 1
            assert results[0].href == "/calendars/"
        finally:
            client.close()

    def test_calendar_query_builds_correct_request(self):
        """calendar_query should build correct request."""
        client = SyncProtocolClient(base_url="https://cal.example.com")

        mock_response = DAVResponse(
            status=207,
            headers={},
            body=b"""<?xml version="1.0"?>
            <D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:response>
                    <D:href>/cal/event.ics</D:href>
                    <D:propstat>
                        <D:prop>
                            <D:getetag>"etag"</D:getetag>
                            <C:calendar-data>BEGIN:VCALENDAR
END:VCALENDAR</C:calendar-data>
                        </D:prop>
                        <D:status>HTTP/1.1 200 OK</D:status>
                    </D:propstat>
                </D:response>
            </D:multistatus>""",
        )
        client.io.execute = Mock(return_value=mock_response)

        try:
            results = client.calendar_query(
                "/calendars/user/cal/",
                start=datetime(2024, 1, 1),
                end=datetime(2024, 12, 31),
                event=True,
            )

            # Check request was built correctly
            call_args = client.io.execute.call_args[0][0]
            assert call_args.method.value == "REPORT"
            assert b"calendar-query" in call_args.body.lower()
            assert b"time-range" in call_args.body.lower()

            # Check response was parsed correctly
            assert len(results) == 1
            assert results[0].href == "/cal/event.ics"
            assert results[0].calendar_data is not None
        finally:
            client.close()

    def test_put_request(self):
        """put should build correct request with body."""
        client = SyncProtocolClient(base_url="https://cal.example.com")

        mock_response = DAVResponse(status=201, headers={}, body=b"")
        client.io.execute = Mock(return_value=mock_response)

        try:
            ical = "BEGIN:VCALENDAR\nEND:VCALENDAR"
            response = client.put("/cal/event.ics", ical, etag='"old-etag"')

            call_args = client.io.execute.call_args[0][0]
            assert call_args.method.value == "PUT"
            assert call_args.headers.get("If-Match") == '"old-etag"'
            assert call_args.body == ical.encode("utf-8")
            assert response.status == 201
        finally:
            client.close()

    def test_delete_request(self):
        """delete should build correct request."""
        client = SyncProtocolClient(base_url="https://cal.example.com")

        mock_response = DAVResponse(status=204, headers={}, body=b"")
        client.io.execute = Mock(return_value=mock_response)

        try:
            response = client.delete("/cal/event.ics")

            call_args = client.io.execute.call_args[0][0]
            assert call_args.method.value == "DELETE"
            assert "event.ics" in call_args.url
            assert response.status == 204
        finally:
            client.close()

    def test_sync_collection(self):
        """sync_collection should parse changes and sync token."""
        client = SyncProtocolClient(base_url="https://cal.example.com")

        mock_response = DAVResponse(
            status=207,
            headers={},
            body=b"""<?xml version="1.0"?>
            <D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:response>
                    <D:href>/cal/new.ics</D:href>
                    <D:propstat>
                        <D:prop><D:getetag>"new"</D:getetag></D:prop>
                        <D:status>HTTP/1.1 200 OK</D:status>
                    </D:propstat>
                </D:response>
                <D:response>
                    <D:href>/cal/deleted.ics</D:href>
                    <D:status>HTTP/1.1 404 Not Found</D:status>
                </D:response>
                <D:sync-token>new-token</D:sync-token>
            </D:multistatus>""",
        )
        client.io.execute = Mock(return_value=mock_response)

        try:
            result = client.sync_collection("/cal/", sync_token="old-token")

            assert len(result.changed) == 1
            assert result.changed[0].href == "/cal/new.ics"
            assert len(result.deleted) == 1
            assert result.deleted[0] == "/cal/deleted.ics"
            assert result.sync_token == "new-token"
        finally:
            client.close()


class TestAsyncProtocolClient:
    """Test AsyncProtocolClient."""

    @pytest.mark.asyncio
    async def test_init(self):
        """Client should initialize protocol and I/O correctly."""
        client = AsyncProtocolClient(
            base_url="https://cal.example.com",
            username="user",
            password="pass",
        )
        try:
            assert client.protocol.base_url == "https://cal.example.com"
            assert client.protocol._auth_header is not None
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Client should work as async context manager."""
        async with AsyncProtocolClient(
            base_url="https://cal.example.com",
        ) as client:
            assert client.protocol is not None

    @pytest.mark.asyncio
    async def test_propfind_builds_correct_request(self):
        """propfind should build correct request and parse response."""
        client = AsyncProtocolClient(base_url="https://cal.example.com")

        mock_response = DAVResponse(
            status=207,
            headers={},
            body=b"""<?xml version="1.0"?>
            <D:multistatus xmlns:D="DAV:">
                <D:response>
                    <D:href>/calendars/</D:href>
                    <D:propstat>
                        <D:prop><D:displayname>Test</D:displayname></D:prop>
                        <D:status>HTTP/1.1 200 OK</D:status>
                    </D:propstat>
                </D:response>
            </D:multistatus>""",
        )
        client.io.execute = AsyncMock(return_value=mock_response)

        try:
            results = await client.propfind("/calendars/", ["displayname"], depth=1)

            # Check request was built correctly
            call_args = client.io.execute.call_args[0][0]
            assert call_args.method.value == "PROPFIND"

            # Check response was parsed correctly
            assert len(results) == 1
            assert results[0].href == "/calendars/"
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_calendar_query(self):
        """calendar_query should work asynchronously."""
        client = AsyncProtocolClient(base_url="https://cal.example.com")

        mock_response = DAVResponse(
            status=207,
            headers={},
            body=b"""<?xml version="1.0"?>
            <D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
                <D:response>
                    <D:href>/cal/event.ics</D:href>
                    <D:propstat>
                        <D:prop>
                            <C:calendar-data>BEGIN:VCALENDAR
END:VCALENDAR</C:calendar-data>
                        </D:prop>
                        <D:status>HTTP/1.1 200 OK</D:status>
                    </D:propstat>
                </D:response>
            </D:multistatus>""",
        )
        client.io.execute = AsyncMock(return_value=mock_response)

        try:
            results = await client.calendar_query(
                "/cal/",
                start=datetime(2024, 1, 1),
                end=datetime(2024, 12, 31),
                event=True,
            )

            assert len(results) == 1
            assert "VCALENDAR" in results[0].calendar_data
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_put_and_delete(self):
        """put and delete should work asynchronously."""
        client = AsyncProtocolClient(base_url="https://cal.example.com")

        client.io.execute = AsyncMock(
            return_value=DAVResponse(status=201, headers={}, body=b"")
        )

        try:
            # Test put
            response = await client.put("/cal/event.ics", "BEGIN:VCALENDAR\nEND:VCALENDAR")
            assert response.status == 201

            # Test delete
            client.io.execute.return_value = DAVResponse(status=204, headers={}, body=b"")
            response = await client.delete("/cal/event.ics")
            assert response.status == 204
        finally:
            await client.close()
