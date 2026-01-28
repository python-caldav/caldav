"""
Tests for the Calendar operations module.

These tests verify the Sans-I/O business logic for Calendar operations
like component detection, sync tokens, and result processing.
"""

from caldav.operations.calendar_ops import CalendarObjectInfo
from caldav.operations.calendar_ops import (
    _build_calendar_object_url as build_calendar_object_url,
)
from caldav.operations.calendar_ops import (
    _detect_component_type as detect_component_type,
)
from caldav.operations.calendar_ops import (
    _detect_component_type_from_icalendar as detect_component_type_from_icalendar,
)
from caldav.operations.calendar_ops import (
    _detect_component_type_from_string as detect_component_type_from_string,
)
from caldav.operations.calendar_ops import (
    _generate_fake_sync_token as generate_fake_sync_token,
)
from caldav.operations.calendar_ops import _is_fake_sync_token as is_fake_sync_token
from caldav.operations.calendar_ops import _normalize_result_url as normalize_result_url
from caldav.operations.calendar_ops import (
    _process_report_results as process_report_results,
)
from caldav.operations.calendar_ops import (
    _should_skip_calendar_self_reference as should_skip_calendar_self_reference,
)


class TestDetectComponentTypeFromString:
    """Tests for detect_component_type_from_string function."""

    def test_detects_vevent(self):
        """Detects VEVENT component."""
        data = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Test\nEND:VEVENT\nEND:VCALENDAR"
        assert detect_component_type_from_string(data) == "Event"

    def test_detects_vtodo(self):
        """Detects VTODO component."""
        data = "BEGIN:VCALENDAR\nBEGIN:VTODO\nSUMMARY:Task\nEND:VTODO\nEND:VCALENDAR"
        assert detect_component_type_from_string(data) == "Todo"

    def test_detects_vjournal(self):
        """Detects VJOURNAL component."""
        data = "BEGIN:VCALENDAR\nBEGIN:VJOURNAL\nSUMMARY:Note\nEND:VJOURNAL\nEND:VCALENDAR"
        assert detect_component_type_from_string(data) == "Journal"

    def test_detects_vfreebusy(self):
        """Detects VFREEBUSY component."""
        data = "BEGIN:VCALENDAR\nBEGIN:VFREEBUSY\nEND:VFREEBUSY\nEND:VCALENDAR"
        assert detect_component_type_from_string(data) == "FreeBusy"

    def test_returns_none_for_unknown(self):
        """Returns None for unknown component types."""
        data = "BEGIN:VCALENDAR\nBEGIN:VTIMEZONE\nEND:VTIMEZONE\nEND:VCALENDAR"
        assert detect_component_type_from_string(data) is None

    def test_handles_whitespace(self):
        """Handles lines with extra whitespace."""
        data = "BEGIN:VCALENDAR\n  BEGIN:VEVENT  \nSUMMARY:Test\nEND:VEVENT\nEND:VCALENDAR"
        assert detect_component_type_from_string(data) == "Event"


class TestDetectComponentTypeFromIcalendar:
    """Tests for detect_component_type_from_icalendar function."""

    def test_detects_event(self):
        """Detects Event from icalendar object."""
        import icalendar

        cal = icalendar.Calendar()
        event = icalendar.Event()
        event.add("summary", "Test")
        cal.add_component(event)

        assert detect_component_type_from_icalendar(cal) == "Event"

    def test_detects_todo(self):
        """Detects Todo from icalendar object."""
        import icalendar

        cal = icalendar.Calendar()
        todo = icalendar.Todo()
        todo.add("summary", "Task")
        cal.add_component(todo)

        assert detect_component_type_from_icalendar(cal) == "Todo"

    def test_returns_none_for_empty(self):
        """Returns None for empty calendar."""
        import icalendar

        cal = icalendar.Calendar()
        assert detect_component_type_from_icalendar(cal) is None

    def test_returns_none_for_no_subcomponents(self):
        """Returns None when no subcomponents attribute."""
        obj = {"test": "value"}
        assert detect_component_type_from_icalendar(obj) is None


class TestDetectComponentType:
    """Tests for detect_component_type function."""

    def test_detects_from_string(self):
        """Detects from string data."""
        data = "BEGIN:VCALENDAR\nBEGIN:VTODO\nSUMMARY:Task\nEND:VTODO\nEND:VCALENDAR"
        assert detect_component_type(data) == "Todo"

    def test_detects_from_icalendar(self):
        """Detects from icalendar object."""
        import icalendar

        cal = icalendar.Calendar()
        cal.add_component(icalendar.Journal())

        assert detect_component_type(cal) == "Journal"

    def test_returns_none_for_none(self):
        """Returns None for None input."""
        assert detect_component_type(None) is None


class TestGenerateFakeSyncToken:
    """Tests for generate_fake_sync_token function."""

    def test_generates_deterministic_token(self):
        """Same input produces same token."""
        etags_urls = [("etag1", "/url1"), ("etag2", "/url2")]

        token1 = generate_fake_sync_token(etags_urls)
        token2 = generate_fake_sync_token(etags_urls)

        assert token1 == token2

    def test_prefix(self):
        """Token starts with 'fake-' prefix."""
        token = generate_fake_sync_token([("etag", "/url")])
        assert token.startswith("fake-")

    def test_different_input_different_token(self):
        """Different input produces different token."""
        token1 = generate_fake_sync_token([("etag1", "/url1")])
        token2 = generate_fake_sync_token([("etag2", "/url2")])

        assert token1 != token2

    def test_order_independent(self):
        """Order of inputs doesn't affect token."""
        etags1 = [("a", "/a"), ("b", "/b")]
        etags2 = [("b", "/b"), ("a", "/a")]

        assert generate_fake_sync_token(etags1) == generate_fake_sync_token(etags2)

    def test_uses_url_when_no_etag(self):
        """Uses URL as fallback when etag is None."""
        token = generate_fake_sync_token([(None, "/url1"), (None, "/url2")])
        assert token.startswith("fake-")

    def test_empty_list(self):
        """Handles empty list."""
        token = generate_fake_sync_token([])
        assert token.startswith("fake-")


class TestIsFakeSyncToken:
    """Tests for is_fake_sync_token function."""

    def test_detects_fake_token(self):
        """Detects fake sync tokens."""
        assert is_fake_sync_token("fake-abc123") is True

    def test_rejects_real_token(self):
        """Rejects tokens without fake- prefix."""
        assert is_fake_sync_token("http://example.com/sync/token123") is False

    def test_handles_none(self):
        """Handles None input."""
        assert is_fake_sync_token(None) is False

    def test_handles_non_string(self):
        """Handles non-string input."""
        assert is_fake_sync_token(12345) is False


class TestNormalizeResultUrl:
    """Tests for normalize_result_url function."""

    def test_quotes_relative_path(self):
        """Quotes special characters in relative paths."""
        result = normalize_result_url("/calendars/event with spaces.ics", "/calendars/")
        assert "%20" in result

    def test_preserves_full_url(self):
        """Preserves full URLs as-is."""
        url = "https://example.com/calendars/event.ics"
        result = normalize_result_url(url, "/calendars/")
        assert result == url


class TestShouldSkipCalendarSelfReference:
    """Tests for should_skip_calendar_self_reference function."""

    def test_skips_exact_match(self):
        """Skips when URLs match exactly."""
        assert should_skip_calendar_self_reference("/calendars/work/", "/calendars/work/") is True

    def test_skips_trailing_slash_difference(self):
        """Skips when URLs differ only by trailing slash."""
        assert should_skip_calendar_self_reference("/calendars/work", "/calendars/work/") is True
        assert should_skip_calendar_self_reference("/calendars/work/", "/calendars/work") is True

    def test_does_not_skip_different_urls(self):
        """Does not skip different URLs."""
        assert (
            should_skip_calendar_self_reference("/calendars/work/event.ics", "/calendars/work/")
            is False
        )


class TestProcessReportResults:
    """Tests for process_report_results function."""

    def test_processes_results(self):
        """Processes results into CalendarObjectInfo objects."""
        results = {
            "/cal/event1.ics": {
                "{urn:ietf:params:xml:ns:caldav}calendar-data": "BEGIN:VCALENDAR\nBEGIN:VEVENT\nEND:VEVENT\nEND:VCALENDAR",
                "{DAV:}getetag": '"etag1"',
            },
            "/cal/todo1.ics": {
                "{urn:ietf:params:xml:ns:caldav}calendar-data": "BEGIN:VCALENDAR\nBEGIN:VTODO\nEND:VTODO\nEND:VCALENDAR",
            },
        }

        objects = process_report_results(results, "/cal/")

        assert len(objects) == 2

        # Find event and todo
        event = next(o for o in objects if o.component_type == "Event")
        todo = next(o for o in objects if o.component_type == "Todo")

        assert event.etag == '"etag1"'
        assert todo.etag is None

    def test_skips_calendar_self_reference(self):
        """Filters out calendar self-reference."""
        results = {
            "/cal/": {  # Calendar itself - should be skipped
                "{DAV:}resourcetype": "{DAV:}collection",
            },
            "/cal/event.ics": {
                "{urn:ietf:params:xml:ns:caldav}calendar-data": "BEGIN:VCALENDAR\nBEGIN:VEVENT\nEND:VEVENT\nEND:VCALENDAR",
            },
        }

        objects = process_report_results(results, "/cal/")

        # Only the event should be returned
        assert len(objects) == 1
        assert "event" in objects[0].url

    def test_handles_empty_results(self):
        """Returns empty list for empty results."""
        assert process_report_results({}, "/cal/") == []


class TestBuildCalendarObjectUrl:
    """Tests for build_calendar_object_url function."""

    def test_builds_url(self):
        """Builds calendar object URL from calendar URL and ID."""
        result = build_calendar_object_url("https://example.com/calendars/work/", "event123")
        assert result == "https://example.com/calendars/work/event123.ics"

    def test_handles_trailing_slash(self):
        """Handles calendar URL with or without trailing slash."""
        result = build_calendar_object_url("https://example.com/calendars/work", "event123")
        assert result == "https://example.com/calendars/work/event123.ics"

    def test_doesnt_double_ics(self):
        """Doesn't add .ics if already present."""
        result = build_calendar_object_url("https://example.com/calendars/work/", "event123.ics")
        assert result == "https://example.com/calendars/work/event123.ics"
        assert ".ics.ics" not in result

    def test_quotes_special_chars(self):
        """Quotes special characters in object ID."""
        result = build_calendar_object_url("https://example.com/calendars/", "event with spaces")
        assert "%20" in result


class TestCalendarObjectInfo:
    """Tests for CalendarObjectInfo dataclass."""

    def test_creates_info(self):
        """Creates CalendarObjectInfo with all fields."""
        info = CalendarObjectInfo(
            url="/calendars/work/event.ics",
            data="BEGIN:VCALENDAR...",
            etag='"abc123"',
            component_type="Event",
            extra_props={"custom": "value"},
        )

        assert info.url == "/calendars/work/event.ics"
        assert info.data == "BEGIN:VCALENDAR..."
        assert info.etag == '"abc123"'
        assert info.component_type == "Event"
        assert info.extra_props == {"custom": "value"}

    def test_allows_none_values(self):
        """Allows None values for optional fields."""
        info = CalendarObjectInfo(
            url="/calendars/work/event.ics",
            data=None,
            etag=None,
            component_type=None,
            extra_props={},
        )

        assert info.data is None
        assert info.etag is None
        assert info.component_type is None
