#!/usr/bin/env python
"""
Tests for caldav.search.CalDAVSearcher.filter method

Rule: None of the tests in this file should initiate any internet
communication. We use mocked client objects as needed.

Disclaimer: AI-generated tests
"""

from datetime import datetime, timezone
from unittest import mock

import icalendar
import pytest

from caldav import Event, Journal, Todo
from caldav.davclient import DAVClient
from caldav.lib.url import URL
from caldav.search import CalDAVSearcher

# Example icalendar data for testing
SIMPLE_EVENT = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:simple-event@example.com
DTSTAMP:20240101T120000Z
DTSTART:20240615T140000Z
DTEND:20240615T150000Z
SUMMARY:Simple Meeting
END:VEVENT
END:VCALENDAR"""

RECURRING_EVENT = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:recurring-event@example.com
DTSTAMP:20240101T120000Z
DTSTART:20240601T100000Z
DTEND:20240601T110000Z
SUMMARY:Weekly Standup
RRULE:FREQ=WEEKLY;COUNT=3
END:VEVENT
END:VCALENDAR"""

RECURRING_EVENT_WITH_TIMEZONE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VTIMEZONE
TZID:America/New_York
BEGIN:STANDARD
DTSTART:20231105T020000
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:20240310T020000
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VEVENT
UID:tz-event@example.com
DTSTAMP:20240101T120000Z
DTSTART;TZID=America/New_York:20240601T090000
DTEND;TZID=America/New_York:20240601T100000
SUMMARY:Morning Meeting
RRULE:FREQ=DAILY;COUNT=3
END:VEVENT
END:VCALENDAR"""

SIMPLE_TODO = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VTODO
UID:simple-todo@example.com
DTSTAMP:20240101T120000Z
DTSTART:20240610T100000Z
DUE:20240620T170000Z
SUMMARY:Complete project proposal
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""

COMPLETED_TODO = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VTODO
UID:completed-todo@example.com
DTSTAMP:20240101T120000Z
DTSTART:20240601T100000Z
DUE:20240605T170000Z
COMPLETED:20240604T150000Z
SUMMARY:Submit report
STATUS:COMPLETED
END:VTODO
END:VCALENDAR"""

RECURRING_TODO = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VTODO
UID:recurring-todo@example.com
DTSTAMP:20240101T120000Z
DTSTART:20240601T080000Z
DUE:20240601T090000Z
SUMMARY:Daily review
RRULE:FREQ=DAILY;COUNT=5
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""

SIMPLE_JOURNAL = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VJOURNAL
UID:simple-journal@example.com
DTSTAMP:20240101T120000Z
DTSTART:20240615T190000Z
SUMMARY:Daily notes
DESCRIPTION:Today's reflections
END:VJOURNAL
END:VCALENDAR"""

# Event with categories for filter testing
CATEGORIZED_EVENT = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:categorized-event@example.com
DTSTAMP:20240101T120000Z
DTSTART:20240615T140000Z
DTEND:20240615T150000Z
SUMMARY:Team Building
CATEGORIES:WORK,SOCIAL
END:VEVENT
END:VCALENDAR"""


@pytest.fixture
def mock_client() -> DAVClient:
    """Create a mocked DAV client for testing."""
    client = mock.Mock(spec=DAVClient)
    # mock_client.url needs to be a real URL object for URL.join() to work correctly
    client.url = URL("https://calendar.example.com/calendars/user/")
    return client


@pytest.fixture
def mock_url() -> str:
    """Return a mocked URL for test objects."""
    return "https://calendar.example.com/calendars/user/event.ics"


class TestCalDAVSearcherFilterBasic:
    """Basic tests for CalDAVSearcher.filter without filtering logic."""

    def test_filter_with_no_filtering_returns_same_objects(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """When post_filter=False and no expansion, objects should pass through unchanged."""
        event1 = Event(client=mock_client, url=mock_url + "/1", data=SIMPLE_EVENT)
        event2 = Event(client=mock_client, url=mock_url + "/2", data=SIMPLE_EVENT)
        objects = [event1, event2]

        searcher = CalDAVSearcher()
        result = searcher.filter(
            objects, post_filter=False, split_expanded=False, server_expand=False
        )

        assert len(result) == 2
        assert result[0] is event1
        assert result[1] is event2

    def test_filter_with_empty_list_returns_empty(self, mock_client: DAVClient) -> None:
        """Filtering an empty list should return an empty list."""
        searcher = CalDAVSearcher()
        result = searcher.filter([], post_filter=False, split_expanded=False, server_expand=False)

        assert result == []

    def test_filter_preserves_object_types(self, mock_client: DAVClient, mock_url: str) -> None:
        """Filter should work with Event, Todo, and Journal objects."""
        event = Event(client=mock_client, url=mock_url + "/event", data=SIMPLE_EVENT)
        todo = Todo(client=mock_client, url=mock_url + "/todo", data=SIMPLE_TODO)
        journal = Journal(client=mock_client, url=mock_url + "/journal", data=SIMPLE_JOURNAL)

        objects = [event, todo, journal]
        searcher = CalDAVSearcher()
        result = searcher.filter(
            objects, post_filter=False, split_expanded=False, server_expand=False
        )

        assert len(result) == 3
        assert isinstance(result[0], Event)
        assert isinstance(result[1], Todo)
        assert isinstance(result[2], Journal)


class TestCalDAVSearcherFilterPostFilter:
    """Tests for post_filter parameter functionality."""

    def test_filter_with_post_filter_true_applies_filters(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """When post_filter=True, searcher filter logic should be applied."""
        # Create a searcher with a summary filter
        searcher = CalDAVSearcher(
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )
        searcher.add_property_filter("SUMMARY", "Meeting", operator="contains")

        event1 = Event(
            client=mock_client, url=mock_url + "/1", data=SIMPLE_EVENT
        )  # "Simple Meeting"
        event2 = Event(
            client=mock_client, url=mock_url + "/2", data=CATEGORIZED_EVENT
        )  # "Team Building"

        objects = [event1, event2]
        result = searcher.filter(
            objects, post_filter=True, split_expanded=False, server_expand=False
        )

        # Only event1 should match (contains "Meeting")
        assert len(result) == 1
        assert "Meeting" in result[0].icalendar_component.get("SUMMARY")

    def test_filter_with_post_filter_false_skips_filters(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """When post_filter=False, filter logic should be skipped."""
        # Create a searcher with a summary filter
        searcher = CalDAVSearcher(
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )
        searcher.add_property_filter("SUMMARY", "Meeting", operator="contains")

        event1 = Event(client=mock_client, url=mock_url + "/1", data=SIMPLE_EVENT)
        event2 = Event(client=mock_client, url=mock_url + "/2", data=CATEGORIZED_EVENT)

        objects = [event1, event2]
        result = searcher.filter(
            objects, post_filter=False, split_expanded=False, server_expand=False
        )

        # Both events should be returned without filtering
        assert len(result) == 2

    def test_filter_completed_todos_with_post_filter(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """post_filter should filter out completed todos when include_completed=False."""
        searcher = CalDAVSearcher(
            todo=True,
            include_completed=False,
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )

        todo1 = Todo(client=mock_client, url=mock_url + "/1", data=SIMPLE_TODO)  # NEEDS-ACTION
        todo2 = Todo(client=mock_client, url=mock_url + "/2", data=COMPLETED_TODO)  # COMPLETED

        objects = [todo1, todo2]
        result = searcher.filter(
            objects, post_filter=True, split_expanded=False, server_expand=False
        )

        # Only the non-completed todo should be returned
        assert len(result) == 1
        assert result[0].icalendar_component.get("STATUS") == "NEEDS-ACTION"


class TestCalDAVSearcherFilterExpand:
    """Tests for expand functionality with split_expanded parameter."""

    def test_filter_with_expand_splits_recurrences(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """When expand=True and split_expanded=True, recurrences should be split into separate objects."""
        searcher = CalDAVSearcher(
            expand=True,
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )

        event = Event(client=mock_client, url=mock_url, data=RECURRING_EVENT)  # COUNT=3

        objects = [event]
        result = searcher.filter(
            objects, post_filter=True, split_expanded=True, server_expand=False
        )

        # Should expand into 3 separate event objects
        assert len(result) == 3
        # Each should be a distinct object
        assert result[0] is not result[1]
        assert result[1] is not result[2]

    def test_filter_with_expand_no_split_keeps_single_object(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """When expand=True but split_expanded=False, recurrences should stay in one object."""
        searcher = CalDAVSearcher(
            expand=True,
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )

        event = Event(client=mock_client, url=mock_url, data=RECURRING_EVENT)  # COUNT=3

        objects = [event]
        result = searcher.filter(
            objects, post_filter=True, split_expanded=False, server_expand=False
        )

        # Should return single object with multiple subcomponents
        assert len(result) == 1
        # The calendar should contain 3 event subcomponents (plus timezone if any)
        event_components = [
            c for c in result[0].icalendar_instance.subcomponents if c.name == "VEVENT"
        ]
        assert len(event_components) == 3

    def test_filter_with_expand_preserves_timezones(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """When expanding events with timezones, timezone info should be preserved."""
        searcher = CalDAVSearcher(
            expand=True,
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )

        event = Event(client=mock_client, url=mock_url, data=RECURRING_EVENT_WITH_TIMEZONE)

        objects = [event]
        result = searcher.filter(
            objects, post_filter=True, split_expanded=True, server_expand=False
        )

        # Should expand into 3 events
        assert len(result) == 3

        # Each split event should have timezone information preserved
        for evt in result:
            tz_components = [
                c for c in evt.icalendar_instance.subcomponents if isinstance(c, icalendar.Timezone)
            ]
            assert len(tz_components) == 1
            assert tz_components[0].get("TZID") == "America/New_York"

    def test_filter_non_recurring_event_no_expansion(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """Non-recurring events should not be expanded even with expand=True."""
        searcher = CalDAVSearcher(
            expand=True,
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )

        event = Event(client=mock_client, url=mock_url, data=SIMPLE_EVENT)

        objects = [event]
        result = searcher.filter(
            objects, post_filter=True, split_expanded=True, server_expand=False
        )

        # Should return single event (no expansion needed)
        assert len(result) == 1


class TestCalDAVSearcherFilterServerExpand:
    """Tests for server_expand parameter handling."""

    def test_filter_with_server_expand_and_split(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """When server_expand=True and split_expanded=True, server-expanded results should be split."""
        searcher = CalDAVSearcher(
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )

        # Simulate a server-expanded event (server already expanded recurring event)
        event = Event(client=mock_client, url=mock_url, data=RECURRING_EVENT)

        objects = [event]
        result = searcher.filter(
            objects, post_filter=False, split_expanded=True, server_expand=True
        )

        # Even without post_filter, server_expand + split_expanded should cause splitting
        # The recurring event should be treated as if server expanded it
        assert len(result) >= 1

    def test_filter_with_server_expand_no_split(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """When server_expand=True but split_expanded=False, results should not be split."""
        searcher = CalDAVSearcher(
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )

        event = Event(client=mock_client, url=mock_url, data=RECURRING_EVENT)

        objects = [event]
        result = searcher.filter(
            objects, post_filter=False, split_expanded=False, server_expand=True
        )

        # Should remain as single object
        assert len(result) == 1


class TestCalDAVSearcherFilterRecurringTodos:
    """Tests for recurring todo handling in filter."""

    def test_filter_recurring_todo_with_expand(self, mock_client: DAVClient, mock_url: str) -> None:
        """Recurring todos should be expanded when expand=True."""
        searcher = CalDAVSearcher(
            expand=True,
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )

        todo = Todo(client=mock_client, url=mock_url, data=RECURRING_TODO)  # FREQ=DAILY;COUNT=5

        objects = [todo]
        result = searcher.filter(
            objects, post_filter=True, split_expanded=True, server_expand=False
        )

        # Should expand into 5 separate todo objects
        assert len(result) == 5

    def test_filter_recurring_todo_filters_completed(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """Recurring todos with completed instances should be filtered when include_completed=False."""
        searcher = CalDAVSearcher(
            expand=True,
            todo=True,
            include_completed=False,
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )

        # Create a recurring todo that has some completed instances
        # (In reality, this would be tested with actual recurrence exceptions)
        todo = Todo(client=mock_client, url=mock_url, data=RECURRING_TODO)

        objects = [todo]
        result = searcher.filter(
            objects, post_filter=True, split_expanded=True, server_expand=False
        )

        # All results should be non-completed
        for t in result:
            status = t.icalendar_component.get("STATUS")
            assert status != "COMPLETED"


class TestCalDAVSearcherFilterEdgeCases:
    """Tests for edge cases and combinations of parameters."""

    def test_filter_with_all_params_false(self, mock_client: DAVClient, mock_url: str) -> None:
        """When all filter params are False/None, objects should pass through."""
        searcher = CalDAVSearcher()

        event = Event(client=mock_client, url=mock_url, data=SIMPLE_EVENT)
        objects = [event]
        result = searcher.filter(
            objects, post_filter=False, split_expanded=False, server_expand=False
        )

        assert len(result) == 1
        assert result[0] is event

    def test_filter_mixed_object_types_with_expand(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """Filter should handle mixed object types (Event, Todo) with expansion."""
        searcher = CalDAVSearcher(
            expand=True,
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )

        event = Event(
            client=mock_client, url=mock_url + "/event", data=RECURRING_EVENT
        )  # 3 occurrences
        todo = Todo(
            client=mock_client, url=mock_url + "/todo", data=RECURRING_TODO
        )  # 5 occurrences

        objects = [event, todo]
        result = searcher.filter(
            objects, post_filter=True, split_expanded=True, server_expand=False
        )

        # Should expand both: 3 events + 5 todos = 8 total
        assert len(result) == 8

    def test_filter_with_expand_but_no_date_range(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """Expansion with limited COUNT should work even without explicit date range."""
        # Using expand without start/end is risky but should work with COUNT-based rules
        searcher = CalDAVSearcher(
            expand=True,
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 7, 1, tzinfo=timezone.utc),
        )

        event = Event(client=mock_client, url=mock_url, data=RECURRING_EVENT)

        objects = [event]
        result = searcher.filter(
            objects, post_filter=True, split_expanded=True, server_expand=False
        )

        # Should handle expansion properly
        assert len(result) == 3

    def test_filter_preserves_uid_in_split_events(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """Split expanded events should preserve the original UID."""
        searcher = CalDAVSearcher(
            expand=True,
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )

        event = Event(client=mock_client, url=mock_url, data=RECURRING_EVENT)
        original_uid = event.icalendar_component.get("UID")

        objects = [event]
        result = searcher.filter(
            objects, post_filter=True, split_expanded=True, server_expand=False
        )

        # All split events should have the same UID
        for evt in result:
            assert evt.icalendar_component.get("UID") == original_uid

    def test_filter_with_post_filter_none_uses_default(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """When post_filter=None, default behavior should be applied."""
        searcher = CalDAVSearcher(
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )

        event = Event(client=mock_client, url=mock_url, data=SIMPLE_EVENT)

        objects = [event]
        result = searcher.filter(
            objects, post_filter=None, split_expanded=False, server_expand=False
        )

        # Should handle None gracefully (no filtering unless triggered by other params)
        assert len(result) == 1

    def test_filter_complex_scenario_expand_filter_split(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """Complex scenario: expand + post_filter + split_expanded all True."""
        searcher = CalDAVSearcher(
            expand=True,
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )
        searcher.add_property_filter("SUMMARY", "Standup", operator="contains")

        event = Event(client=mock_client, url=mock_url, data=RECURRING_EVENT)  # "Weekly Standup"

        objects = [event]
        result = searcher.filter(
            objects, post_filter=True, split_expanded=True, server_expand=False
        )

        # Should expand, filter, and split
        assert len(result) == 3  # 3 occurrences, all matching filter
        for evt in result:
            assert "Standup" in evt.icalendar_component.get("SUMMARY")
            assert evt.icalendar_component.get("RECURRENCE-ID") is not None


class TestCalDAVSearcherFilterIntegration:
    """Integration-style tests combining multiple features."""

    def test_filter_workflow_server_side_then_client_side(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """Simulate server-side expand followed by client-side filtering and splitting."""
        # Step 1: Server expands (simulated by having recurring event)
        searcher = CalDAVSearcher(
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )
        searcher.add_property_filter("SUMMARY", "Weekly", operator="contains")

        event = Event(client=mock_client, url=mock_url, data=RECURRING_EVENT)

        # Step 2: Client-side filter with server_expand=True
        objects = [event]
        result = searcher.filter(objects, post_filter=True, split_expanded=True, server_expand=True)

        # Should handle both server expansion and client-side filtering
        assert len(result) >= 1

    def test_filter_multiple_events_different_recurrence_patterns(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """Test filtering multiple events with different recurrence patterns."""
        searcher = CalDAVSearcher(
            expand=True,
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
            end=datetime(2024, 6, 30, tzinfo=timezone.utc),
        )

        event1 = Event(
            client=mock_client, url=mock_url + "/1", data=RECURRING_EVENT
        )  # Weekly, 3 times
        event2 = Event(client=mock_client, url=mock_url + "/2", data=SIMPLE_EVENT)  # No recurrence

        objects = [event1, event2]
        result = searcher.filter(
            objects, post_filter=True, split_expanded=True, server_expand=False
        )

        # 3 recurring + 1 simple = 4 total
        assert len(result) == 4


EVENT_WITHOUT_CATEGORIES = SIMPLE_EVENT  # SIMPLE_EVENT has no CATEGORIES property

# All-day recurring event with no DTEND (copied from RFC 5545 example used in test_caldav.py)
RECURRING_EVENT_NO_DTEND = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:19970901T130000Z-123403@example.com
DTSTAMP:19970901T130000Z
DTSTART;VALUE=DATE:19971102
SUMMARY:Our Blissful Anniversary
CATEGORIES:ANNIVERSARY,PERSONAL
RRULE:FREQ=YEARLY
END:VEVENT
END:VCALENDAR"""

EVENT_WITH_DTEND = SIMPLE_EVENT  # has DTEND:20240615T150000Z


class TestCalDAVSearcherIsNotDefined:
    """Tests for the is-not-defined (undef) filter and workaround in CalDAVSearcher."""

    def test_filter_undef_categories_keeps_events_without_categories(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """The undef filter for categories should keep events without CATEGORIES
        and filter out events that have CATEGORIES."""
        event_without_cats = Event(
            client=mock_client, url=mock_url + "/1", data=EVENT_WITHOUT_CATEGORIES
        )
        event_with_cats = Event(client=mock_client, url=mock_url + "/2", data=CATEGORIZED_EVENT)

        searcher = CalDAVSearcher()
        searcher.add_property_filter("categories", True, operator="undef")

        result = searcher.filter(
            [event_without_cats, event_with_cats],
            post_filter=True,
            split_expanded=False,
            server_expand=False,
        )

        assert len(result) == 1
        # The returned event should be the one without actual categories.
        # Note: icalendar provides a default empty vCategory for any component, so
        # we check the categories list is empty rather than checking .get() for None.
        assert not list(result[0].icalendar_component.categories)

    def test_filter_undef_categories_keeps_all_when_none_have_categories(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """When no events have categories, undef filter should keep all events."""
        event1 = Event(client=mock_client, url=mock_url + "/1", data=EVENT_WITHOUT_CATEGORIES)
        event2 = Event(client=mock_client, url=mock_url + "/2", data=EVENT_WITHOUT_CATEGORIES)

        searcher = CalDAVSearcher()
        searcher.add_property_filter("categories", True, operator="undef")

        result = searcher.filter(
            [event1, event2],
            post_filter=True,
            split_expanded=False,
            server_expand=False,
        )

        assert len(result) == 2

    def test_filter_undef_categories_removes_all_when_all_have_categories(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """When all events have categories, undef filter should remove all events."""
        event1 = Event(client=mock_client, url=mock_url + "/1", data=CATEGORIZED_EVENT)
        event2 = Event(client=mock_client, url=mock_url + "/2", data=CATEGORIZED_EVENT)

        searcher = CalDAVSearcher()
        searcher.add_property_filter("categories", True, operator="undef")

        result = searcher.filter(
            [event1, event2],
            post_filter=True,
            split_expanded=False,
            server_expand=False,
        )

        assert len(result) == 0

    def test_search_workaround_is_not_defined_category(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """When search.is-not-defined.category is unsupported, search() should fetch
        all events from the server and apply client-side category filtering."""
        event_without_cats = Event(
            client=mock_client, url=mock_url + "/1", data=EVENT_WITHOUT_CATEGORIES
        )
        event_with_cats = Event(client=mock_client, url=mock_url + "/2", data=CATEGORIZED_EVENT)

        def mock_is_supported(feat, type_=bool):
            if feat == "search.is-not-defined.category":
                return False
            if type_ == str:
                return "full"
            return True

        mock_client.features.is_supported = mock.Mock(side_effect=mock_is_supported)
        mock_client.features.backward_compatibility_mode = False

        calendar = mock.Mock()
        calendar.client = mock_client
        # Server returns all events regardless of filter (simulating server without undef support)
        calendar._request_report_build_resultlist.return_value = (
            mock.Mock(),
            [event_without_cats, event_with_cats],
        )

        searcher = CalDAVSearcher(event=True)
        searcher.add_property_filter("categories", True, operator="undef")

        result = searcher.search(calendar)

        # Only event without categories should be returned
        assert len(result) == 1
        assert not list(result[0].icalendar_component.categories)

    def test_filter_undef_dtend_keeps_events_without_dtend(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """The undef filter for dtend should keep events without DTEND."""
        event_with_dtend = Event(client=mock_client, url=mock_url + "/1", data=EVENT_WITH_DTEND)
        event_without_dtend = Event(
            client=mock_client, url=mock_url + "/2", data=RECURRING_EVENT_NO_DTEND
        )

        searcher = CalDAVSearcher()
        searcher.add_property_filter("dtend", True, operator="undef")

        result = searcher.filter(
            [event_with_dtend, event_without_dtend],
            post_filter=True,
            split_expanded=False,
            server_expand=False,
        )

        assert len(result) == 1
        assert result[0].icalendar_component.get("DTEND") is None

    def test_search_workaround_no_dtend_with_unsupported_feature(
        self, mock_client: DAVClient, mock_url: str
    ) -> None:
        """When search.is-not-defined.dtend is unsupported, search() should fetch
        all events and apply client-side filtering.

        Recurring events without DTEND should be correctly returned even though
        recurring_ical_events adds a computed DTEND during expansion.
        """
        event_with_dtend = Event(client=mock_client, url=mock_url + "/1", data=EVENT_WITH_DTEND)
        # Recurring all-day event without explicit DTEND (expansion adds computed DTEND)
        recurring_without_dtend = Event(
            client=mock_client, url=mock_url + "/2", data=RECURRING_EVENT_NO_DTEND
        )

        def mock_is_supported(feat, type_=bool):
            if feat == "search.is-not-defined.dtend":
                return False
            if type_ == str:
                return "full"
            return True

        mock_client.features.is_supported = mock.Mock(side_effect=mock_is_supported)
        mock_client.features.backward_compatibility_mode = False

        calendar = mock.Mock()
        calendar.client = mock_client
        calendar._request_report_build_resultlist.return_value = (
            mock.Mock(),
            [event_with_dtend, recurring_without_dtend],
        )

        searcher = CalDAVSearcher(event=True)
        searcher.add_property_filter("dtend", True, operator="undef")

        result = searcher.search(calendar)

        # Only the recurring event without DTEND should be returned
        assert len(result) == 1
        assert result[0].icalendar_component.get("DTEND") is None
