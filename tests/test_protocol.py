"""
Unit tests for protocol XML builders and response parsers.

These tests verify XML building and parsing logic without any HTTP mocking.
All tests are pure - they test data transformations only.
"""

from datetime import datetime

import pytest

from caldav.base_client import BaseDAVClient

build_calendar_multiget_body = BaseDAVClient._build_calendar_multiget_body
build_calendar_query_body = BaseDAVClient._build_calendar_query_body
build_mkcalendar_body = BaseDAVClient._build_mkcalendar_body
build_propfind_body = BaseDAVClient._build_propfind_body
build_sync_collection_body = BaseDAVClient._build_sync_collection_body
from caldav.response import DAVResponse, SyncCollectionResult


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

    def test_parse_propfind_simple(self):
        """Parse simple multistatus response via DAVResponse."""
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

        results = DAVResponse.from_bytes(xml).parse_propfind()

        assert len(results) == 1
        assert results[0].href == "/calendars/user/"
        assert "{DAV:}displayname" in results[0].properties

    def test_parse_propfind_with_sync_token(self):
        """parse_propfind populates DAVResponse.sync_token when present."""
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

        response = DAVResponse.from_bytes(xml)
        response.parse_propfind()
        assert response.sync_token == "token-456"

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

        results = DAVResponse.from_bytes(xml).parse_propfind()

        assert len(results) == 1
        assert results[0].href == "/calendars/"

    def test_parse_propfind_404_returns_empty(self):
        """PROPFIND 404 should return empty list."""
        results = DAVResponse.from_bytes(b"", status_code=404).parse_propfind()
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

        results = DAVResponse.from_bytes(xml).parse_calendar_query()

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

        result = DAVResponse.from_bytes(xml).parse_sync_collection()

        assert isinstance(result, SyncCollectionResult)
        assert len(result.changed) == 1
        assert result.changed[0].href == "/cal/new.ics"
        assert len(result.deleted) == 1
        assert result.deleted[0] == "/cal/deleted.ics"
        assert result.sync_token == "new-token"

    def test_parse_sync_collection_generic_responsedescription(self):
        """A 404 <response> may carry an arbitrary <responsedescription>.

        Per RFC 4918 <responsedescription> is an optional child of
        <response>; its text is server-defined.  We must not hardcode
        any particular server's wording (e.g. Stalwart's "No resources
        found").
        """
        xml = b"""<?xml version="1.0"?>
        <D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
            <D:response>
                <D:href>/cal/gone.ics</D:href>
                <D:status>HTTP/1.1 404 Not Found</D:status>
                <D:responsedescription>The thing you asked for is not here anymore</D:responsedescription>
            </D:response>
            <D:sync-token>tok</D:sync-token>
        </D:multistatus>"""

        result = DAVResponse.from_bytes(xml).parse_sync_collection()

        assert result.deleted == ["/cal/gone.ics"]
        assert result.changed == []

    def test_parse_sync_collection_generic_error(self):
        """A 404 <response> may carry an arbitrary <error> element.

        Per RFC 4918 <error> is an optional child of <response> and its
        children are server-defined.  We must not hardcode any
        particular server's error condition (e.g. purelymail's
        {https://purelymail.com}does-not-exist).
        """
        xml = b"""<?xml version="1.0"?>
        <D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"
                       xmlns:X="https://example.com/ns">
            <D:response>
                <D:href>/cal/gone.ics</D:href>
                <D:status>HTTP/1.1 404 Not Found</D:status>
                <D:error><X:resource-must-be-null/></D:error>
            </D:response>
            <D:sync-token>tok</D:sync-token>
        </D:multistatus>"""

        result = DAVResponse.from_bytes(xml).parse_sync_collection()

        assert result.deleted == ["/cal/gone.ics"]
        assert result.changed == []

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

        results = DAVResponse.from_bytes(xml).parse_propfind()

        assert len(results) == 1
        props = results[0].properties

        assert props["{DAV:}displayname"] == "My Calendar"

        resourcetype = props["{DAV:}resourcetype"]
        assert "{DAV:}collection" in resourcetype
        assert "{urn:ietf:params:xml:ns:caldav}calendar" in resourcetype

        components = props["{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set"]
        assert components == ["VEVENT", "VTODO", "VJOURNAL"]

        # calendar-home-set - extracted href
        home_set = props["{urn:ietf:params:xml:ns:caldav}calendar-home-set"]
        assert home_set == "/calendars/user/"


class TestParserStackEquivalence:
    """Guard the shared propstat-collection logic (code-review §5.7).

    The dataclass parsers (parse_propfind -> _extract_properties) and the
    legacy _find_objects_and_props path must agree on the duplicated quirks
    that used to be implemented twice: the "a 404 propstat means the property
    is absent" skip and which prop elements get collected per href.
    """

    # one href with a found prop (200) and an absent prop (404 propstat),
    # plus a second href that 404s entirely.
    _xml = b"""<?xml version="1.0"?>
    <D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
        <D:response>
            <D:href>/cal/a/</D:href>
            <D:propstat>
                <D:prop><D:displayname>A</D:displayname></D:prop>
                <D:status>HTTP/1.1 200 OK</D:status>
            </D:propstat>
            <D:propstat>
                <D:prop><C:calendar-color/></D:prop>
                <D:status>HTTP/1.1 404 Not Found</D:status>
            </D:propstat>
        </D:response>
        <D:response>
            <D:href>/cal/missing/</D:href>
            <D:status>HTTP/1.1 404 Not Found</D:status>
        </D:response>
    </D:multistatus>"""

    def test_404_propstat_skipped_in_both_stacks(self):
        dataclass_props = DAVResponse.from_bytes(self._xml).parse_propfind()
        legacy = DAVResponse.from_bytes(self._xml)._find_objects_and_props()

        # dataclass stack: /cal/a/ keeps displayname, drops the 404 color prop
        a_result = next(r for r in dataclass_props if r.href == "/cal/a/")
        assert "{DAV:}displayname" in a_result.properties
        assert "{http://apple.com/ns/ical/}calendar-color" not in a_result.properties

        # legacy stack: same set of collected prop tags for the same href
        assert set(legacy["/cal/a/"].keys()) == set(a_result.properties.keys())
        # the entirely-404 href is present but carries no props in either stack
        assert legacy["/cal/missing/"] == {}
