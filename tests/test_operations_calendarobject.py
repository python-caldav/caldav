"""
Tests for CalendarObjectResource operations module.

These tests verify the Sans-I/O business logic for calendar objects
without any network I/O.
"""

from datetime import datetime, timedelta, timezone

import icalendar

from caldav.operations.calendarobject_ops import (
    _copy_component_with_new_uid as copy_component_with_new_uid,
)
from caldav.operations.calendarobject_ops import _extract_relations as extract_relations
from caldav.operations.calendarobject_ops import (
    _extract_uid_from_path as extract_uid_from_path,
)
from caldav.operations.calendarobject_ops import _find_id_and_path as find_id_and_path
from caldav.operations.calendarobject_ops import _generate_uid as generate_uid
from caldav.operations.calendarobject_ops import _generate_url as generate_url
from caldav.operations.calendarobject_ops import _get_due as get_due
from caldav.operations.calendarobject_ops import _get_duration as get_duration
from caldav.operations.calendarobject_ops import (
    _get_non_timezone_subcomponents as get_non_timezone_subcomponents,
)
from caldav.operations.calendarobject_ops import (
    _get_primary_component as get_primary_component,
)
from caldav.operations.calendarobject_ops import (
    _get_reverse_reltype as get_reverse_reltype,
)
from caldav.operations.calendarobject_ops import (
    _has_calendar_component as has_calendar_component,
)
from caldav.operations.calendarobject_ops import (
    _is_calendar_data_loaded as is_calendar_data_loaded,
)
from caldav.operations.calendarobject_ops import _is_task_pending as is_task_pending
from caldav.operations.calendarobject_ops import (
    _mark_task_completed as mark_task_completed,
)
from caldav.operations.calendarobject_ops import (
    _mark_task_uncompleted as mark_task_uncompleted,
)
from caldav.operations.calendarobject_ops import (
    _reduce_rrule_count as reduce_rrule_count,
)
from caldav.operations.calendarobject_ops import _set_duration as set_duration


class TestGenerateUid:
    """Tests for generate_uid function."""

    def test_generates_unique_uids(self):
        """Each call generates a unique UID."""
        uids = {generate_uid() for _ in range(100)}
        assert len(uids) == 100

    def test_uid_is_string(self):
        """UID is a string."""
        assert isinstance(generate_uid(), str)


class TestGenerateUrl:
    """Tests for generate_url function."""

    def test_basic_url(self):
        """Generates correct URL from parent and UID."""
        url = generate_url("/calendars/user/cal/", "event-123")
        assert url == "/calendars/user/cal/event-123.ics"

    def test_adds_trailing_slash(self):
        """Adds trailing slash to parent if missing."""
        url = generate_url("/calendars/user/cal", "event-123")
        assert url == "/calendars/user/cal/event-123.ics"

    def test_quotes_special_chars(self):
        """Special characters in UID are quoted."""
        url = generate_url("/cal/", "event with spaces")
        assert "event%20with%20spaces.ics" in url

    def test_double_quotes_slashes(self):
        """Slashes in UID are double-quoted."""
        url = generate_url("/cal/", "event/with/slashes")
        assert "%252F" in url  # %2F is quoted again


class TestExtractUidFromPath:
    """Tests for extract_uid_from_path function."""

    def test_extracts_uid(self):
        """Extracts UID from .ics path."""
        uid = extract_uid_from_path("/calendars/user/cal/event-123.ics")
        assert uid == "event-123"

    def test_returns_none_for_non_ics(self):
        """Returns None for non-.ics paths."""
        assert extract_uid_from_path("/calendars/user/cal/") is None

    def test_handles_simple_path(self):
        """Handles simple filename."""
        uid = extract_uid_from_path("event.ics")
        assert uid == "event"


class TestFindIdAndPath:
    """Tests for find_id_and_path function."""

    def test_uses_given_id(self):
        """Given ID takes precedence."""
        comp = icalendar.Event()
        comp.add("UID", "old-uid")
        uid, path = find_id_and_path(comp, given_id="new-uid")
        assert uid == "new-uid"
        assert comp["UID"] == "new-uid"

    def test_uses_existing_id(self):
        """Uses existing_id if no given_id."""
        comp = icalendar.Event()
        uid, path = find_id_and_path(comp, existing_id="existing")
        assert uid == "existing"

    def test_extracts_from_component(self):
        """Extracts UID from component."""
        comp = icalendar.Event()
        comp.add("UID", "comp-uid")
        uid, path = find_id_and_path(comp)
        assert uid == "comp-uid"

    def test_extracts_from_path(self):
        """Extracts UID from path."""
        comp = icalendar.Event()
        uid, path = find_id_and_path(comp, given_path="event-from-path.ics")
        assert uid == "event-from-path"

    def test_generates_new_uid(self):
        """Generates new UID if none available."""
        comp = icalendar.Event()
        uid, path = find_id_and_path(comp)
        assert uid is not None
        assert len(uid) > 0

    def test_generates_path(self):
        """Generates path from UID."""
        comp = icalendar.Event()
        uid, path = find_id_and_path(comp, given_id="test-uid")
        assert path == "test-uid.ics"


class TestGetDuration:
    """Tests for get_duration function."""

    def test_from_duration_property(self):
        """Gets duration from DURATION property."""
        comp = icalendar.Event()
        comp.add("DURATION", timedelta(hours=2))
        assert get_duration(comp) == timedelta(hours=2)

    def test_from_dtstart_dtend(self):
        """Calculates duration from DTSTART and DTEND."""
        comp = icalendar.Event()
        comp.add("DTSTART", datetime(2024, 1, 1, 10, 0))
        comp.add("DTEND", datetime(2024, 1, 1, 12, 0))
        assert get_duration(comp, "DTEND") == timedelta(hours=2)

    def test_from_dtstart_due(self):
        """Calculates duration from DTSTART and DUE (for todos)."""
        comp = icalendar.Todo()
        comp.add("DTSTART", datetime(2024, 1, 1, 10, 0))
        comp.add("DUE", datetime(2024, 1, 1, 11, 0))
        assert get_duration(comp, "DUE") == timedelta(hours=1)

    def test_date_only_default_one_day(self):
        """Date-only DTSTART defaults to 1 day duration."""
        from datetime import date

        comp = icalendar.Event()
        comp.add("DTSTART", date(2024, 1, 1))
        assert get_duration(comp) == timedelta(days=1)

    def test_no_duration_returns_zero(self):
        """Returns zero if no duration info available."""
        comp = icalendar.Event()
        assert get_duration(comp) == timedelta(0)


class TestGetDue:
    """Tests for get_due function."""

    def test_from_due_property(self):
        """Gets due from DUE property."""
        comp = icalendar.Todo()
        due = datetime(2024, 1, 15, 17, 0)
        comp.add("DUE", due)
        assert get_due(comp) == due

    def test_from_dtend(self):
        """Falls back to DTEND."""
        comp = icalendar.Todo()
        dtend = datetime(2024, 1, 15, 17, 0)
        comp.add("DTEND", dtend)
        assert get_due(comp) == dtend

    def test_calculated_from_duration(self):
        """Calculates from DTSTART + DURATION."""
        comp = icalendar.Todo()
        comp.add("DTSTART", datetime(2024, 1, 15, 10, 0))
        comp.add("DURATION", timedelta(hours=7))
        assert get_due(comp) == datetime(2024, 1, 15, 17, 0)

    def test_returns_none(self):
        """Returns None if no due info."""
        comp = icalendar.Todo()
        assert get_due(comp) is None


class TestSetDuration:
    """Tests for set_duration function."""

    def test_with_dtstart_and_due(self):
        """Moves DUE when both set."""
        comp = icalendar.Todo()
        comp.add("DTSTART", datetime(2024, 1, 1, 10, 0))
        comp.add("DUE", datetime(2024, 1, 1, 11, 0))

        set_duration(comp, timedelta(hours=3), movable_attr="DUE")

        assert comp["DUE"].dt == datetime(2024, 1, 1, 13, 0)

    def test_move_dtstart(self):
        """Moves DTSTART when specified."""
        comp = icalendar.Todo()
        comp.add("DTSTART", datetime(2024, 1, 1, 10, 0))
        comp.add("DUE", datetime(2024, 1, 1, 12, 0))

        set_duration(comp, timedelta(hours=1), movable_attr="DTSTART")

        assert comp["DTSTART"].dt == datetime(2024, 1, 1, 11, 0)

    def test_adds_duration_if_no_dates(self):
        """Adds DURATION property if no dates set."""
        comp = icalendar.Todo()
        set_duration(comp, timedelta(hours=2))
        assert comp["DURATION"].dt == timedelta(hours=2)


class TestIsTaskPending:
    """Tests for is_task_pending function."""

    def test_needs_action_is_pending(self):
        """NEEDS-ACTION status is pending."""
        comp = icalendar.Todo()
        comp.add("STATUS", "NEEDS-ACTION")
        assert is_task_pending(comp) is True

    def test_in_process_is_pending(self):
        """IN-PROCESS status is pending."""
        comp = icalendar.Todo()
        comp.add("STATUS", "IN-PROCESS")
        assert is_task_pending(comp) is True

    def test_completed_is_not_pending(self):
        """COMPLETED status is not pending."""
        comp = icalendar.Todo()
        comp.add("STATUS", "COMPLETED")
        assert is_task_pending(comp) is False

    def test_cancelled_is_not_pending(self):
        """CANCELLED status is not pending."""
        comp = icalendar.Todo()
        comp.add("STATUS", "CANCELLED")
        assert is_task_pending(comp) is False

    def test_completed_property_is_not_pending(self):
        """COMPLETED property means not pending."""
        comp = icalendar.Todo()
        comp.add("COMPLETED", datetime.now(timezone.utc))
        assert is_task_pending(comp) is False

    def test_no_status_is_pending(self):
        """No status defaults to pending."""
        comp = icalendar.Todo()
        assert is_task_pending(comp) is True


class TestMarkTaskCompleted:
    """Tests for mark_task_completed function."""

    def test_marks_completed(self):
        """Sets STATUS to COMPLETED."""
        comp = icalendar.Todo()
        comp.add("STATUS", "NEEDS-ACTION")
        ts = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)

        mark_task_completed(comp, ts)

        assert comp["STATUS"] == "COMPLETED"
        assert comp["COMPLETED"].dt == ts

    def test_uses_current_time(self):
        """Uses current time if not specified."""
        comp = icalendar.Todo()
        mark_task_completed(comp)
        assert "COMPLETED" in comp


class TestMarkTaskUncompleted:
    """Tests for mark_task_uncompleted function."""

    def test_marks_uncompleted(self):
        """Removes completion and sets NEEDS-ACTION."""
        comp = icalendar.Todo()
        comp.add("STATUS", "COMPLETED")
        comp.add("COMPLETED", datetime.now(timezone.utc))

        mark_task_uncompleted(comp)

        assert comp["STATUS"] == "NEEDS-ACTION"
        assert "COMPLETED" not in comp


class TestReduceRruleCount:
    """Tests for reduce_rrule_count function."""

    def test_reduces_count(self):
        """Reduces COUNT by 1."""
        comp = icalendar.Todo()
        comp.add("RRULE", {"FREQ": "WEEKLY", "COUNT": 5})

        result = reduce_rrule_count(comp)

        assert result is True
        # icalendar stores COUNT as list via .get() or int via []
        count = comp["RRULE"].get("COUNT")
        count_val = count[0] if isinstance(count, list) else count
        assert count_val == 4

    def test_returns_false_at_one(self):
        """Returns False when COUNT reaches 1."""
        comp = icalendar.Todo()
        comp.add("RRULE", {"FREQ": "WEEKLY", "COUNT": 1})

        result = reduce_rrule_count(comp)

        assert result is False

    def test_no_count_returns_true(self):
        """Returns True if no COUNT in RRULE."""
        comp = icalendar.Todo()
        comp.add("RRULE", {"FREQ": "WEEKLY"})

        result = reduce_rrule_count(comp)

        assert result is True


class TestIsCalendarDataLoaded:
    """Tests for is_calendar_data_loaded function."""

    def test_loaded_with_data(self):
        """Returns True with valid data."""
        data = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nEND:VEVENT\nEND:VCALENDAR"
        assert is_calendar_data_loaded(data, None, None) is True

    def test_loaded_with_icalendar(self):
        """Returns True with icalendar instance."""
        assert is_calendar_data_loaded(None, None, icalendar.Calendar()) is True

    def test_not_loaded_empty(self):
        """Returns False with no data."""
        assert is_calendar_data_loaded(None, None, None) is False


class TestHasCalendarComponent:
    """Tests for has_calendar_component function."""

    def test_has_vevent(self):
        """Returns True for VEVENT."""
        data = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nEND:VEVENT\nEND:VCALENDAR"
        assert has_calendar_component(data) is True

    def test_has_vtodo(self):
        """Returns True for VTODO."""
        data = "BEGIN:VCALENDAR\nBEGIN:VTODO\nEND:VTODO\nEND:VCALENDAR"
        assert has_calendar_component(data) is True

    def test_has_vjournal(self):
        """Returns True for VJOURNAL."""
        data = "BEGIN:VCALENDAR\nBEGIN:VJOURNAL\nEND:VJOURNAL\nEND:VCALENDAR"
        assert has_calendar_component(data) is True

    def test_no_component(self):
        """Returns False for no component."""
        data = "BEGIN:VCALENDAR\nEND:VCALENDAR"
        assert has_calendar_component(data) is False

    def test_empty_data(self):
        """Returns False for empty data."""
        assert has_calendar_component(None) is False


class TestGetNonTimezoneSubcomponents:
    """Tests for get_non_timezone_subcomponents function."""

    def test_filters_timezone(self):
        """Filters out VTIMEZONE components."""
        cal = icalendar.Calendar()
        cal.add_component(icalendar.Event())
        cal.add_component(icalendar.Timezone())
        cal.add_component(icalendar.Todo())

        comps = get_non_timezone_subcomponents(cal)

        assert len(comps) == 2
        assert all(not isinstance(c, icalendar.Timezone) for c in comps)


class TestGetPrimaryComponent:
    """Tests for get_primary_component function."""

    def test_gets_event(self):
        """Gets VEVENT component."""
        cal = icalendar.Calendar()
        event = icalendar.Event()
        cal.add_component(event)

        assert get_primary_component(cal) is event

    def test_gets_todo(self):
        """Gets VTODO component."""
        cal = icalendar.Calendar()
        todo = icalendar.Todo()
        cal.add_component(todo)

        assert get_primary_component(cal) is todo

    def test_skips_timezone(self):
        """Skips VTIMEZONE."""
        cal = icalendar.Calendar()
        cal.add_component(icalendar.Timezone())
        event = icalendar.Event()
        cal.add_component(event)

        assert get_primary_component(cal) is event


class TestCopyComponentWithNewUid:
    """Tests for copy_component_with_new_uid function."""

    def test_copies_with_new_uid(self):
        """Creates copy with new UID."""
        comp = icalendar.Event()
        comp.add("UID", "old-uid")
        comp.add("SUMMARY", "Test Event")

        new_comp = copy_component_with_new_uid(comp, "new-uid")

        assert new_comp["UID"] == "new-uid"
        assert new_comp["SUMMARY"] == "Test Event"
        assert comp["UID"] == "old-uid"  # Original unchanged

    def test_generates_uid(self):
        """Generates UID if not provided."""
        comp = icalendar.Event()
        comp.add("UID", "old-uid")

        new_comp = copy_component_with_new_uid(comp)

        assert new_comp["UID"] != "old-uid"
        assert new_comp["UID"] is not None


class TestGetReverseReltype:
    """Tests for get_reverse_reltype function."""

    def test_parent_child(self):
        """PARENT reverses to CHILD."""
        assert get_reverse_reltype("PARENT") == "CHILD"

    def test_child_parent(self):
        """CHILD reverses to PARENT."""
        assert get_reverse_reltype("CHILD") == "PARENT"

    def test_sibling(self):
        """SIBLING reverses to SIBLING."""
        assert get_reverse_reltype("SIBLING") == "SIBLING"

    def test_unknown(self):
        """Unknown type returns None."""
        assert get_reverse_reltype("UNKNOWN") is None

    def test_case_insensitive(self):
        """Case insensitive matching."""
        assert get_reverse_reltype("parent") == "CHILD"


class TestExtractRelations:
    """Tests for extract_relations function."""

    def test_extracts_relations(self):
        """Extracts RELATED-TO properties."""
        comp = icalendar.Todo()
        comp.add("RELATED-TO", "parent-uid", parameters={"RELTYPE": "PARENT"})

        relations = extract_relations(comp)

        assert "PARENT" in relations
        assert "parent-uid" in relations["PARENT"]

    def test_filters_by_reltype(self):
        """Filters by relation type."""
        comp = icalendar.Todo()
        comp.add("RELATED-TO", "parent-uid", parameters={"RELTYPE": "PARENT"})
        comp.add("RELATED-TO", "child-uid", parameters={"RELTYPE": "CHILD"})

        relations = extract_relations(comp, reltypes={"PARENT"})

        assert "PARENT" in relations
        assert "CHILD" not in relations

    def test_default_parent(self):
        """Defaults to PARENT if no RELTYPE."""
        comp = icalendar.Todo()
        comp.add("RELATED-TO", "some-uid")

        relations = extract_relations(comp)

        assert "PARENT" in relations
