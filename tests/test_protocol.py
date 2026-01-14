"""
Unit tests for Sans-I/O protocol layer.

These tests verify protocol logic without any HTTP mocking required.
All tests are pure - they test data transformations only.
"""

import pytest
from datetime import datetime

from caldav.protocol import (
    # Types
    DAVMethod,
    DAVRequest,
    DAVResponse,
    PropfindResult,
    CalendarQueryResult,
    MultistatusResponse,
    SyncCollectionResult,
    # Builders
    build_propfind_body,
    build_calendar_query_body,
    build_calendar_multiget_body,
    build_sync_collection_body,
    build_mkcalendar_body,
    # Parsers
    parse_multistatus,
    parse_propfind_response,
    parse_calendar_query_response,
    parse_sync_collection_response,
)


class TestDAVTypes:
    """Test core DAV types."""

    def test_dav_request_immutable(self):
        """DAVRequest should be immutable (frozen dataclass)."""
        request = DAVRequest(
            method=DAVMethod.GET,
            url="https://example.com/",
            headers={},
        )
        with pytest.raises(AttributeError):
            request.url = "https://other.com/"

    def test_dav_request_with_header(self):
        """with_header should return new request with added header."""
        request = DAVRequest(
            method=DAVMethod.GET,
            url="https://example.com/",
            headers={"Accept": "text/html"},
        )
        new_request = request.with_header("Authorization", "Bearer token")

        # Original unchanged
        assert "Authorization" not in request.headers
        # New has both headers
        assert new_request.headers["Accept"] == "text/html"
        assert new_request.headers["Authorization"] == "Bearer token"

    def test_dav_response_ok(self):
        """ok property should return True for 2xx status codes."""
        assert DAVResponse(status=200, headers={}, body=b"").ok
        assert DAVResponse(status=201, headers={}, body=b"").ok
        assert DAVResponse(status=207, headers={}, body=b"").ok
        assert not DAVResponse(status=404, headers={}, body=b"").ok
        assert not DAVResponse(status=500, headers={}, body=b"").ok

    def test_dav_response_is_multistatus(self):
        """is_multistatus should return True only for 207."""
        assert DAVResponse(status=207, headers={}, body=b"").is_multistatus
        assert not DAVResponse(status=200, headers={}, body=b"").is_multistatus


class TestXMLBuilders:
    """Test XML building functions."""

    def test_build_propfind_body_minimal(self):
        """Minimal propfind should produce valid XML."""
        body = build_propfind_body()
        assert b"propfind" in body.lower()

    def test_build_propfind_body_with_props(self):
        """Propfind with properties should include them."""
        body = build_propfind_body(["displayname", "resourcetype"])
        xml = body.decode("utf-8").lower()
        assert "displayname" in xml
        assert "resourcetype" in xml

    def test_build_calendar_query_with_time_range(self):
        """Calendar query with time range should include time-range element."""
        body, comp_type = build_calendar_query_body(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 12, 31),
            event=True,
        )
        xml = body.decode("utf-8").lower()
        assert "calendar-query" in xml
        assert "time-range" in xml
        assert comp_type == "VEVENT"

    def test_build_calendar_query_component_types(self):
        """Calendar query should set correct component type."""
        _, comp = build_calendar_query_body(event=True)
        assert comp == "VEVENT"

        _, comp = build_calendar_query_body(todo=True)
        assert comp == "VTODO"

        _, comp = build_calendar_query_body(journal=True)
        assert comp == "VJOURNAL"

    def test_build_calendar_multiget_body(self):
        """Calendar multiget should include hrefs."""
        body = build_calendar_multiget_body(["/cal/event1.ics", "/cal/event2.ics"])
        xml = body.decode("utf-8")
        assert "calendar-multiget" in xml.lower()
        assert "/cal/event1.ics" in xml
        assert "/cal/event2.ics" in xml

    def test_build_sync_collection_body(self):
        """Sync collection should include sync-token."""
        body = build_sync_collection_body(sync_token="token-123")
        xml = body.decode("utf-8")
        assert "sync-collection" in xml.lower()
        assert "token-123" in xml

    def test_build_mkcalendar_body(self):
        """Mkcalendar should include properties."""
        body = build_mkcalendar_body(
            displayname="My Calendar",
            description="A test calendar",
        )
        xml = body.decode("utf-8")
        assert "mkcalendar" in xml.lower()
        assert "My Calendar" in xml
        assert "A test calendar" in xml


class TestXMLParsers:
    """Test XML parsing functions."""

    def test_parse_multistatus_simple(self):
        """Parse simple multistatus response."""
        xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <D:multistatus xmlns:D="DAV:">
            <D:response>
                <D:href>/calendars/user/</D:href>
                <D:propstat>
                    <D:prop>
                        <D:displayname>My Calendar</D:displayname>
                    </D:prop>
                    <D:status>HTTP/1.1 200 OK</D:status>
                </D:propstat>
            </D:response>
        </D:multistatus>"""

        result = parse_multistatus(xml)

        assert isinstance(result, MultistatusResponse)
        assert len(result.responses) == 1
        assert result.responses[0].href == "/calendars/user/"
        assert "{DAV:}displayname" in result.responses[0].properties

    def test_parse_multistatus_with_sync_token(self):
        """Parse multistatus with sync-token."""
        xml = b"""<?xml version="1.0"?>
        <D:multistatus xmlns:D="DAV:">
            <D:response>
                <D:href>/cal/</D:href>
                <D:propstat>
                    <D:prop><D:displayname>Cal</D:displayname></D:prop>
                    <D:status>HTTP/1.1 200 OK</D:status>
                </D:propstat>
            </D:response>
            <D:sync-token>token-456</D:sync-token>
        </D:multistatus>"""

        result = parse_multistatus(xml)
        assert result.sync_token == "token-456"

    def test_parse_propfind_response(self):
        """Parse PROPFIND response."""
        xml = b"""<?xml version="1.0"?>
        <D:multistatus xmlns:D="DAV:">
            <D:response>
                <D:href>/calendars/</D:href>
                <D:propstat>
                    <D:prop>
                        <D:resourcetype><D:collection/></D:resourcetype>
                    </D:prop>
                    <D:status>HTTP/1.1 200 OK</D:status>
                </D:propstat>
            </D:response>
        </D:multistatus>"""

        results = parse_propfind_response(xml, status_code=207)

        assert len(results) == 1
        assert results[0].href == "/calendars/"

    def test_parse_propfind_404_returns_empty(self):
        """PROPFIND 404 should return empty list."""
        results = parse_propfind_response(b"", status_code=404)
        assert results == []

    def test_parse_calendar_query_response(self):
        """Parse calendar-query response with calendar data."""
        xml = b"""<?xml version="1.0"?>
        <D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:response>
                <D:href>/cal/event.ics</D:href>
                <D:propstat>
                    <D:prop>
                        <D:getetag>"etag-123"</D:getetag>
                        <C:calendar-data>BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:test@example.com
END:VEVENT
END:VCALENDAR</C:calendar-data>
                    </D:prop>
                    <D:status>HTTP/1.1 200 OK</D:status>
                </D:propstat>
            </D:response>
        </D:multistatus>"""

        results = parse_calendar_query_response(xml, status_code=207)

        assert len(results) == 1
        assert results[0].href == "/cal/event.ics"
        assert results[0].etag == '"etag-123"'
        assert "VCALENDAR" in results[0].calendar_data

    def test_parse_sync_collection_response(self):
        """Parse sync-collection response with changed and deleted items."""
        xml = b"""<?xml version="1.0"?>
        <D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:response>
                <D:href>/cal/new.ics</D:href>
                <D:propstat>
                    <D:prop>
                        <D:getetag>"new-etag"</D:getetag>
                    </D:prop>
                    <D:status>HTTP/1.1 200 OK</D:status>
                </D:propstat>
            </D:response>
            <D:response>
                <D:href>/cal/deleted.ics</D:href>
                <D:status>HTTP/1.1 404 Not Found</D:status>
            </D:response>
            <D:sync-token>new-token</D:sync-token>
        </D:multistatus>"""

        result = parse_sync_collection_response(xml, status_code=207)

        assert isinstance(result, SyncCollectionResult)
        assert len(result.changed) == 1
        assert result.changed[0].href == "/cal/new.ics"
        assert len(result.deleted) == 1
        assert result.deleted[0] == "/cal/deleted.ics"
        assert result.sync_token == "new-token"

    def test_parse_complex_properties(self):
        """Parse complex properties like supported-calendar-component-set."""
        xml = b"""<?xml version="1.0"?>
        <D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:response>
                <D:href>/calendars/user/calendar/</D:href>
                <D:propstat>
                    <D:prop>
                        <D:displayname>My Calendar</D:displayname>
                        <D:resourcetype>
                            <D:collection/>
                            <C:calendar/>
                        </D:resourcetype>
                        <C:supported-calendar-component-set>
                            <C:comp name="VEVENT"/>
                            <C:comp name="VTODO"/>
                            <C:comp name="VJOURNAL"/>
                        </C:supported-calendar-component-set>
                        <C:calendar-home-set>
                            <D:href>/calendars/user/</D:href>
                        </C:calendar-home-set>
                    </D:prop>
                    <D:status>HTTP/1.1 200 OK</D:status>
                </D:propstat>
            </D:response>
        </D:multistatus>"""

        results = parse_propfind_response(xml, status_code=207)

        assert len(results) == 1
        props = results[0].properties

        # Simple property
        assert props["{DAV:}displayname"] == "My Calendar"

        # resourcetype - list of child tags
        resourcetype = props["{DAV:}resourcetype"]
        assert "{DAV:}collection" in resourcetype
        assert "{urn:ietf:params:xml:ns:caldav}calendar" in resourcetype

        # supported-calendar-component-set - list of component names
        components = props["{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set"]
        assert components == ["VEVENT", "VTODO", "VJOURNAL"]

        # calendar-home-set - extracted href
        home_set = props["{urn:ietf:params:xml:ns:caldav}calendar-home-set"]
        assert home_set == "/calendars/user/"


