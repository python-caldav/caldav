"""
Tests for the DAVObject operations module.

These tests verify the Sans-I/O business logic for DAVObject operations
like getting properties, listing children, and delete validation.
"""

import pytest

from caldav.operations.davobject_ops import (
    CALDAV_CALENDAR,
    DAV_DISPLAYNAME,
    DAV_RESOURCETYPE,
)
from caldav.operations.davobject_ops import (
    _build_children_query as build_children_query,
)
from caldav.operations.davobject_ops import (
    _convert_protocol_results_to_properties as convert_protocol_results_to_properties,
)
from caldav.operations.davobject_ops import (
    _find_object_properties as find_object_properties,
)
from caldav.operations.davobject_ops import (
    _process_children_response as process_children_response,
)
from caldav.operations.davobject_ops import (
    _validate_delete_response as validate_delete_response,
)
from caldav.operations.davobject_ops import (
    _validate_proppatch_response as validate_proppatch_response,
)


class TestBuildChildrenQuery:
    """Tests for build_children_query function."""

    def test_builds_query(self):
        """Builds a ChildrenQuery with correct defaults."""
        query = build_children_query("/calendars/user/")
        assert query.url == "/calendars/user/"
        assert query.depth == 1
        assert DAV_DISPLAYNAME in query.props
        assert DAV_RESOURCETYPE in query.props


class TestProcessChildrenResponse:
    """Tests for process_children_response function."""

    def test_excludes_parent(self):
        """Parent URL is excluded from results."""
        props = {
            "/calendars/": {
                DAV_RESOURCETYPE: ["{DAV:}collection"],
                DAV_DISPLAYNAME: "Calendars",
            },
            "/calendars/work/": {
                DAV_RESOURCETYPE: ["{DAV:}collection", CALDAV_CALENDAR],
                DAV_DISPLAYNAME: "Work",
            },
        }
        children = process_children_response(props, "/calendars/")
        assert len(children) == 1
        assert children[0].display_name == "Work"

    def test_filters_by_type(self):
        """Filter by resource type works."""
        props = {
            "/calendars/": {
                DAV_RESOURCETYPE: ["{DAV:}collection"],
                DAV_DISPLAYNAME: "Calendars",
            },
            "/calendars/work/": {
                DAV_RESOURCETYPE: ["{DAV:}collection", CALDAV_CALENDAR],
                DAV_DISPLAYNAME: "Work Calendar",
            },
            "/calendars/other/": {
                DAV_RESOURCETYPE: ["{DAV:}collection"],
                DAV_DISPLAYNAME: "Other Collection",
            },
        }
        children = process_children_response(props, "/calendars/", filter_type=CALDAV_CALENDAR)
        assert len(children) == 1
        assert children[0].display_name == "Work Calendar"

    def test_handles_trailing_slash_difference(self):
        """Parent with/without trailing slash is handled."""
        props = {
            "/calendars": {
                DAV_RESOURCETYPE: ["{DAV:}collection"],
                DAV_DISPLAYNAME: "Calendars",
            },
            "/calendars/work/": {
                DAV_RESOURCETYPE: ["{DAV:}collection", CALDAV_CALENDAR],
                DAV_DISPLAYNAME: "Work",
            },
        }
        # Parent has trailing slash, response doesn't
        children = process_children_response(props, "/calendars/")
        assert len(children) == 1
        assert children[0].display_name == "Work"

    def test_handles_string_resource_type(self):
        """Single string resource type is handled."""
        props = {
            "/calendars/": {
                DAV_RESOURCETYPE: "{DAV:}collection",
                DAV_DISPLAYNAME: "Calendars",
            },
            "/calendars/work/": {
                DAV_RESOURCETYPE: CALDAV_CALENDAR,
                DAV_DISPLAYNAME: "Work",
            },
        }
        children = process_children_response(props, "/calendars/")
        assert len(children) == 1

    def test_handles_none_resource_type(self):
        """None resource type is handled."""
        props = {
            "/calendars/": {
                DAV_RESOURCETYPE: None,
                DAV_DISPLAYNAME: "Calendars",
            },
            "/calendars/work/": {
                DAV_RESOURCETYPE: [CALDAV_CALENDAR],
                DAV_DISPLAYNAME: "Work",
            },
        }
        children = process_children_response(props, "/calendars/")
        # Parent excluded, work included
        assert len(children) == 1


class TestFindObjectProperties:
    """Tests for find_object_properties function."""

    def test_exact_match(self):
        """Exact path match works."""
        props = {
            "/calendars/user/": {"prop": "value"},
        }
        result = find_object_properties(props, "/calendars/user/")
        assert result.properties == {"prop": "value"}
        assert result.matched_path == "/calendars/user/"

    def test_trailing_slash_mismatch(self):
        """Trailing slash mismatch is handled."""
        props = {
            "/calendars/user": {"prop": "value"},
        }
        result = find_object_properties(props, "/calendars/user/")
        assert result.properties == {"prop": "value"}
        assert result.matched_path == "/calendars/user"

    def test_full_url_as_key(self):
        """Full URL as properties key works."""
        props = {
            "https://example.com/calendars/": {"prop": "value"},
        }
        result = find_object_properties(props, "https://example.com/calendars/")
        assert result.properties == {"prop": "value"}

    def test_double_slash_workaround(self):
        """Double slash in path is normalized."""
        props = {
            "/calendars/user/": {"prop": "value"},
        }
        result = find_object_properties(props, "/calendars//user/")
        assert result.properties == {"prop": "value"}

    def test_single_result_fallback(self):
        """Single result is used as fallback."""
        props = {
            "/some/other/path/": {"prop": "value"},
        }
        result = find_object_properties(props, "/expected/path/")
        assert result.properties == {"prop": "value"}

    def test_icloud_principal_workaround(self):
        """iCloud /principal/ workaround works."""
        props = {
            "/principal/": {"prop": "value"},
        }
        result = find_object_properties(props, "/12345/principal/")
        assert result.properties == {"prop": "value"}

    def test_no_match_raises(self):
        """ValueError raised when no match found."""
        props = {
            "/path/a/": {"prop": "a"},
            "/path/b/": {"prop": "b"},
        }
        with pytest.raises(ValueError, match="Could not find properties"):
            find_object_properties(props, "/path/c/")

    def test_principal_no_warning(self):
        """Principal objects don't warn on trailing slash mismatch."""
        props = {
            "/principal": {"prop": "value"},
        }
        # Should not log warning for principals
        result = find_object_properties(props, "/principal/", is_principal=True)
        assert result.properties == {"prop": "value"}


class TestConvertProtocolResults:
    """Tests for convert_protocol_results_to_properties function."""

    def test_converts_results(self):
        """Converts PropfindResult-like objects to dict."""

        class FakeResult:
            def __init__(self, href, properties):
                self.href = href
                self.properties = properties

        results = [
            FakeResult("/cal/", {DAV_DISPLAYNAME: "Calendar"}),
            FakeResult("/cal/event.ics", {DAV_DISPLAYNAME: "Event"}),
        ]
        converted = convert_protocol_results_to_properties(results)
        assert "/cal/" in converted
        assert converted["/cal/"][DAV_DISPLAYNAME] == "Calendar"
        assert "/cal/event.ics" in converted

    def test_initializes_requested_props(self):
        """Requested props initialized to None."""

        class FakeResult:
            def __init__(self, href, properties):
                self.href = href
                self.properties = properties

        results = [FakeResult("/cal/", {DAV_DISPLAYNAME: "Calendar"})]
        converted = convert_protocol_results_to_properties(
            results, requested_props=[DAV_DISPLAYNAME, "{DAV:}getetag"]
        )
        assert converted["/cal/"][DAV_DISPLAYNAME] == "Calendar"
        assert converted["/cal/"]["{DAV:}getetag"] is None


class TestValidateDeleteResponse:
    """Tests for validate_delete_response function."""

    def test_accepts_200(self):
        """200 OK is accepted."""
        validate_delete_response(200)  # No exception

    def test_accepts_204(self):
        """204 No Content is accepted."""
        validate_delete_response(204)  # No exception

    def test_accepts_404(self):
        """404 Not Found is accepted (already deleted)."""
        validate_delete_response(404)  # No exception

    def test_rejects_500(self):
        """500 raises ValueError."""
        with pytest.raises(ValueError, match="Delete failed"):
            validate_delete_response(500)

    def test_rejects_403(self):
        """403 Forbidden raises ValueError."""
        with pytest.raises(ValueError, match="Delete failed"):
            validate_delete_response(403)


class TestValidatePropatchResponse:
    """Tests for validate_proppatch_response function."""

    def test_accepts_200(self):
        """200 OK is accepted."""
        validate_proppatch_response(200)  # No exception

    def test_accepts_207(self):
        """207 Multi-Status is accepted."""
        validate_proppatch_response(207)  # No exception

    def test_rejects_400(self):
        """400 raises ValueError."""
        with pytest.raises(ValueError, match="PROPPATCH failed"):
            validate_proppatch_response(400)

    def test_rejects_403(self):
        """403 Forbidden raises ValueError."""
        with pytest.raises(ValueError, match="PROPPATCH failed"):
            validate_proppatch_response(403)
