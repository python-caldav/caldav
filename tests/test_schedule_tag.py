#!/usr/bin/env python
"""
Unit and integration tests for Schedule-Tag support (RFC 6638).

Unit tests (class TestScheduleTagUnit) use mocks and require no server.

Integration tests are added to _TestSchedulingBase in test_caldav.py;
see testScheduleTag* methods there.

RFC refs:
  https://datatracker.ietf.org/doc/html/rfc6638#section-3.2
  https://datatracker.ietf.org/doc/html/rfc6638#section-3.3
"""

import uuid
from unittest import mock

import pytest

try:
    from niquests.structures import CaseInsensitiveDict
except ImportError:
    from requests.structures import CaseInsensitiveDict

from caldav import Calendar, Event
from caldav.davclient import DAVClient
from caldav.elements import cdav, dav
from caldav.lib import error

## Minimal scheduling event with ORGANIZER and ATTENDEE so that a server
## will treat it as a scheduling object resource and return Schedule-Tag.
SCHED_ICAL = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:20260101T000000Z
DTSTART:20320601T100000Z
DURATION:PT1H
SUMMARY:Schedule-Tag test event
ORGANIZER:mailto:organizer@example.com
ATTENDEE;RSVP=TRUE;PARTSTAT=NEEDS-ACTION:mailto:attendee@example.com
END:VEVENT
END:VCALENDAR
"""


def _make_put_response(status_code, headers=None):
    """Return a minimal mock requests.Response for a PUT."""
    r = mock.MagicMock()
    r.status_code = status_code
    r.headers = CaseInsensitiveDict(headers or {})
    r.reason = "OK" if status_code in (200, 201, 204) else "Precondition Failed"
    r.content = b""
    return r


def _make_event_with_tag(schedule_tag='"tag-abc"'):
    """
    Return an Event object that already has a schedule-tag cached in props,
    as would happen after a load() or save() that received a Schedule-Tag header.
    """
    client = DAVClient(url="http://cal.example.com/")
    cal = Calendar(client=client, url="http://cal.example.com/cal/")
    event = Event(
        client=client,
        url="http://cal.example.com/cal/event.ics",
        data=SCHED_ICAL.format(uid=str(uuid.uuid4())),
        parent=cal,
    )
    if schedule_tag:
        event.props[cdav.ScheduleTag.tag] = schedule_tag
    return event


class TestScheduleTagUnit:
    """
    Pure unit tests — no server communication.
    All tests in this class are expected to FAIL until the implementation is complete.
    """

    # ------------------------------------------------------------------ #
    # 1. Public property                                                   #
    # ------------------------------------------------------------------ #

    def test_schedule_tag_property_returns_cached_value(self):
        """
        CalendarObjectResource.schedule_tag should expose the cached tag.

        Currently fails because the property does not exist.
        """
        event = _make_event_with_tag('"tag-xyz"')
        assert event.schedule_tag == '"tag-xyz"'

    def test_schedule_tag_property_returns_none_when_absent(self):
        """
        schedule_tag should return None when the tag has never been received.
        """
        client = DAVClient(url="http://cal.example.com/")
        cal = Calendar(client=client, url="http://cal.example.com/cal/")
        event = Event(
            client=client,
            url="http://cal.example.com/cal/event.ics",
            data=SCHED_ICAL.format(uid=str(uuid.uuid4())),
            parent=cal,
        )
        assert event.schedule_tag is None

    # ------------------------------------------------------------------ #
    # 2. Schedule-Tag captured from response headers                       #
    # ------------------------------------------------------------------ #

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_schedule_tag_captured_from_put_response(self, mocked):
        """
        After a PUT that returns a Schedule-Tag header, the tag should be
        stored in event.props and accessible via event.schedule_tag.

        Currently fails because _put() does not read the Schedule-Tag header.
        (Actually it DOES store it via self.props — but only after load(), not
        after _put().  Verify the full round-trip here.)
        """
        put_resp = _make_put_response(201, {"Schedule-Tag": '"initial-tag"'})
        mocked.return_value = put_resp

        client = DAVClient(url="http://cal.example.com/")
        cal = Calendar(client=client, url="http://cal.example.com/cal/")
        uid = str(uuid.uuid4())
        event = Event(
            client=client,
            url=f"http://cal.example.com/cal/{uid}.ics",
            data=SCHED_ICAL.format(uid=uid),
            parent=cal,
        )
        event.save()

        assert event.schedule_tag == '"initial-tag"'

    # ------------------------------------------------------------------ #
    # 3. If-Schedule-Tag-Match sent on save()                             #
    # ------------------------------------------------------------------ #

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_if_schedule_tag_match_header_sent_when_tag_cached(self, mocked):
        """
        save() must send an If-Schedule-Tag-Match
        request header equal to the cached schedule-tag.
        """
        ok_resp = _make_put_response(204, {"Schedule-Tag": '"tag-abc"'})
        mocked.return_value = ok_resp

        event = _make_event_with_tag('"tag-abc"')
        event.save()

        # Inspect the actual HTTP call
        call_kwargs = mocked.call_args
        # requests.Session.request is called as (method, url, **kwargs)
        # headers end up in call_args.kwargs["headers"] or positional args
        sent_headers = call_kwargs[1].get(
            "headers", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else {}
        )
        assert "If-Schedule-Tag-Match" in sent_headers, (
            "If-Schedule-Tag-Match header was not sent; save() is still a no-op"
        )
        assert sent_headers["If-Schedule-Tag-Match"] == '"tag-abc"'

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_if_schedule_tag_match_not_sent_when_flag_false(self, mocked):
        """
        save() without if_schedule_tag_match=True must NOT send the header,
        even when a tag is cached.
        """
        ok_resp = _make_put_response(204)
        mocked.return_value = ok_resp

        event = _make_event_with_tag(None)
        event.save()

        call_kwargs = mocked.call_args
        sent_headers = call_kwargs[1].get(
            "headers", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else {}
        )
        assert "If-Schedule-Tag-Match" not in sent_headers

    # ------------------------------------------------------------------ #
    # 4. Load before PUT when tag not yet cached                           #
    # ------------------------------------------------------------------ #

    ## Removed, it's moot with the current design

    # ------------------------------------------------------------------ #
    # 5. 412 raises ScheduleTagMismatchError                               #
    # ------------------------------------------------------------------ #

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_stale_schedule_tag_raises_mismatch_error(self, mocked):
        """
        When the server returns 412 in response to an If-Schedule-Tag-Match
        PUT, the client must raise ScheduleTagMismatchError (a subclass of
        PutError).

        Currently fails: ScheduleTagMismatchError does not exist, and the
        generic PutError is raised instead (or not at all because the header
        is never sent).
        """
        mocked.return_value = _make_put_response(412)

        event = _make_event_with_tag('"stale-tag"')
        with pytest.raises(error.ScheduleTagMismatchError):
            event.save()

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_412_without_schedule_tag_raises_put_error(self, mocked):
        """
        A plain 412 (not from If-Schedule-Tag-Match) should still raise
        the generic PutError, not ScheduleTagMismatchError.
        """
        mocked.return_value = _make_put_response(412)

        event = _make_event_with_tag(None)
        # save() without if_schedule_tag_match — any 412 is a plain PutError
        with pytest.raises(error.PutError):
            event.save()

    # ------------------------------------------------------------------ #
    # 6. Tag updated in props after successful conditional save            #
    # ------------------------------------------------------------------ #

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_schedule_tag_updated_in_props_after_successful_save(self, mocked):
        """
        After a successful conditional PUT the server may return a new
        Schedule-Tag.  The updated tag must replace the old cached value.
        """
        new_tag = '"tag-after-save"'
        mocked.return_value = _make_put_response(204, {"Schedule-Tag": new_tag})

        event = _make_event_with_tag('"tag-before-save"')
        event.save()

        assert event.schedule_tag == new_tag, (
            "schedule_tag prop not updated after successful conditional save"
        )
