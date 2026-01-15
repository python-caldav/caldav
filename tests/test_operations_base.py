"""
Tests for the operations layer base module.

These tests verify the Sans-I/O utility functions work correctly
without any network I/O.
"""

import pytest

from caldav.operations.base import (
    PropertyData,
    QuerySpec,
    extract_resource_type,
    get_property_value,
    is_calendar_resource,
    is_collection_resource,
    normalize_href,
)


class TestQuerySpec:
    """Tests for QuerySpec dataclass."""

    def test_query_spec_defaults(self):
        """QuerySpec has sensible defaults."""
        spec = QuerySpec(url="/calendars/")
        assert spec.url == "/calendars/"
        assert spec.method == "PROPFIND"
        assert spec.depth == 0
        assert spec.props == ()
        assert spec.body is None

    def test_query_spec_immutable(self):
        """QuerySpec is immutable (frozen)."""
        spec = QuerySpec(url="/test")
        with pytest.raises(AttributeError):
            spec.url = "/other"

    def test_query_spec_with_url(self):
        """with_url() returns a new QuerySpec with different URL."""
        spec = QuerySpec(url="/old", method="REPORT", depth=1, props=("displayname",))
        new_spec = spec.with_url("/new")

        assert new_spec.url == "/new"
        assert new_spec.method == "REPORT"
        assert new_spec.depth == 1
        assert new_spec.props == ("displayname",)
        # Original unchanged
        assert spec.url == "/old"


class TestPropertyData:
    """Tests for PropertyData dataclass."""

    def test_property_data_defaults(self):
        """PropertyData has sensible defaults."""
        data = PropertyData(href="/item")
        assert data.href == "/item"
        assert data.properties == {}
        assert data.status == 200

    def test_property_data_with_properties(self):
        """PropertyData can store arbitrary properties."""
        data = PropertyData(
            href="/cal/",
            properties={"{DAV:}displayname": "My Calendar", "{DAV:}resourcetype": ["collection"]},
            status=200,
        )
        assert data.properties["{DAV:}displayname"] == "My Calendar"


class TestNormalizeHref:
    """Tests for normalize_href function."""

    def test_normalize_empty(self):
        """Empty href returns empty."""
        assert normalize_href("") == ""

    def test_normalize_double_slashes(self):
        """Double slashes are normalized."""
        assert normalize_href("/path//to//resource") == "/path/to/resource"

    def test_normalize_preserves_http(self):
        """HTTP URLs preserve double slashes in protocol."""
        result = normalize_href("https://example.com/path")
        assert result == "https://example.com/path"

    def test_normalize_with_base_url(self):
        """Relative URLs resolved against base."""
        result = normalize_href("/calendars/test/", "https://example.com/dav/")
        # Should resolve to full URL
        assert "calendars/test" in result


class TestExtractResourceType:
    """Tests for extract_resource_type function."""

    def test_extract_list(self):
        """Extract list of resource types."""
        props = {"{DAV:}resourcetype": ["{DAV:}collection", "{urn:ietf:params:xml:ns:caldav}calendar"]}
        result = extract_resource_type(props)
        assert "{DAV:}collection" in result
        assert "{urn:ietf:params:xml:ns:caldav}calendar" in result

    def test_extract_single_value(self):
        """Extract single resource type."""
        props = {"{DAV:}resourcetype": "{DAV:}collection"}
        result = extract_resource_type(props)
        assert result == ["{DAV:}collection"]

    def test_extract_none(self):
        """Missing resourcetype returns empty list."""
        props = {"{DAV:}displayname": "Test"}
        result = extract_resource_type(props)
        assert result == []

    def test_extract_explicit_none(self):
        """Explicit None resourcetype returns empty list."""
        props = {"{DAV:}resourcetype": None}
        result = extract_resource_type(props)
        assert result == []


class TestIsCalendarResource:
    """Tests for is_calendar_resource function."""

    def test_is_calendar(self):
        """Detect calendar resource."""
        props = {"{DAV:}resourcetype": ["{DAV:}collection", "{urn:ietf:params:xml:ns:caldav}calendar"]}
        assert is_calendar_resource(props) is True

    def test_is_not_calendar(self):
        """Non-calendar collection."""
        props = {"{DAV:}resourcetype": ["{DAV:}collection"]}
        assert is_calendar_resource(props) is False

    def test_empty_props(self):
        """Empty properties."""
        assert is_calendar_resource({}) is False


class TestIsCollectionResource:
    """Tests for is_collection_resource function."""

    def test_is_collection(self):
        """Detect collection resource."""
        props = {"{DAV:}resourcetype": ["{DAV:}collection"]}
        assert is_collection_resource(props) is True

    def test_is_not_collection(self):
        """Non-collection resource."""
        props = {"{DAV:}resourcetype": []}
        assert is_collection_resource(props) is False


class TestGetPropertyValue:
    """Tests for get_property_value function."""

    def test_get_exact_key(self):
        """Get property with exact key."""
        props = {"{DAV:}displayname": "Test Calendar"}
        assert get_property_value(props, "{DAV:}displayname") == "Test Calendar"

    def test_get_simple_key_dav_namespace(self):
        """Get property with simple key, DAV namespace."""
        props = {"{DAV:}displayname": "Test Calendar"}
        assert get_property_value(props, "displayname") == "Test Calendar"

    def test_get_simple_key_caldav_namespace(self):
        """Get property with simple key, CalDAV namespace."""
        props = {"{urn:ietf:params:xml:ns:caldav}calendar-data": "BEGIN:VCALENDAR..."}
        assert get_property_value(props, "calendar-data") == "BEGIN:VCALENDAR..."

    def test_get_missing_with_default(self):
        """Missing property returns default."""
        props = {"{DAV:}displayname": "Test"}
        assert get_property_value(props, "nonexistent", "default") == "default"

    def test_get_missing_no_default(self):
        """Missing property returns None by default."""
        props = {}
        assert get_property_value(props, "nonexistent") is None
