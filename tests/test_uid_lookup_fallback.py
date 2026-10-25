"""
Unit tests for the fallback in get_object_by_uid() when the server fails
the UID search (issue #783: iCloud answers it with 412).
"""

import asyncio
from unittest import mock

import pytest

from caldav.async_davclient import AsyncDAVClient
from caldav.calendarobjectresource import Event, Todo
from caldav.collection import Calendar
from caldav.davclient import DAVClient
from caldav.elements import cdav, dav
from caldav.lib import error
from caldav.response import DAVResponse

CAL_URL = "https://caldav.example.com/calendars/user/cal/"
UID = "c0ffee-1234@example.com"
SLASH_UID = "imported/slash uid"


def ical(uid, comp="VEVENT"):
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//test//EN\r\n"
        f"BEGIN:{comp}\r\nUID:{uid}\r\nDTSTAMP:20261019T120000Z\r\n"
        "DTSTART:20261025T090000Z\r\nSUMMARY:test\r\n"
        f"END:{comp}\r\nEND:VCALENDAR\r\n"
    )


def multistatus(*objects):
    responses = "".join(
        f"""<d:response><d:href>{href}</d:href><d:propstat><d:prop>
<cal:calendar-data>{data}</cal:calendar-data></d:prop>
<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"""
        for href, data in objects
    )
    return (
        '<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">'
        f"{responses}</d:multistatus>"
    )


def response(status, body="", headers=None):
    resp = mock.MagicMock()
    resp.status_code = status
    resp.reason = resp.reason_phrase = "test"
    resp.headers = headers or {}
    resp.content = body
    return DAVResponse(resp)


PRECONDITION_FAILED = (412, "")
SERVER_ERROR = (500, "<html><body>Internal Server Error</body></html>")
NOT_FOUND = (404, "")
EMPTY = (207, multistatus())


class ScriptedDAVClient(DAVClient):
    """Answers each request with the next entry of a script: a (status,
    body[, headers]) tuple, or an exception to raise the way the real client
    raises on 401/403/429.  Records (method, url) of every request."""

    def __init__(self, script, features=None):
        self.script = list(script)
        self.requests = []
        DAVClient.__init__(self, url="https://caldav.example.com/", features=features)

    def request(self, url, method="GET", body="", headers=None):
        self.requests.append((method, str(url)))
        answer = self.script.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return response(*answer)


class AsyncScriptedDAVClient(ScriptedDAVClient, AsyncDAVClient):
    async def request(self, url, method="GET", body="", headers=None):
        return ScriptedDAVClient.request(self, url, method, body, headers)


def calendar(script, features=None, is_async=False):
    client = ScriptedDAVClient(script, features=features)
    if is_async:
        client.__class__ = AsyncScriptedDAVClient
    return Calendar(client, url=CAL_URL)


def methods(cal):
    return [method for method, _ in cal.client.requests]


def forbidden():
    return error.AuthorizationError(CAL_URL, "Forbidden")


class TestUidLookupFallback:
    def test_get_by_uid_name(self):
        cal = calendar(
            [PRECONDITION_FAILED, (200, ical(UID), {"Etag": '"etag-1"'})],
        )
        obj = cal.get_event_by_uid(UID)
        assert isinstance(obj, Event)
        assert obj.id == UID
        assert obj.props[dav.GetEtag.tag] == '"etag-1"'
        assert obj.raw_data == ical(UID).encode()
        assert methods(cal) == ["REPORT", "GET"]
        assert cal.client.requests[1][1] == CAL_URL + "c0ffee-1234%40example.com.ics"
        assert str(obj.url) == CAL_URL + "c0ffee-1234%40example.com.ics"

    def test_scan_when_not_found_by_name(self):
        cal = calendar(
            [
                PRECONDITION_FAILED,
                NOT_FOUND,
                (
                    207,
                    multistatus(
                        ("/calendars/user/cal/other.ics", ical("other")),
                        ("/calendars/user/cal/imported-1.ics", ical(SLASH_UID)),
                    ),
                ),
            ]
        )
        obj = cal.get_event_by_uid(SLASH_UID)
        assert obj.id == SLASH_UID
        assert str(obj.url) == CAL_URL + "imported-1.ics"
        assert methods(cal) == ["REPORT", "GET", "REPORT"]

    @pytest.mark.parametrize(
        "get_answer",
        [
            (200, ical("some-other-uid")),
            SERVER_ERROR,
            forbidden(),
        ],
        ids=["other-uid", "500", "403"],
    )
    def test_scan_when_get_gives_something_else(self, get_answer):
        cal = calendar(
            [
                PRECONDITION_FAILED,
                get_answer,
                (207, multistatus(("/calendars/user/cal/ev.ics", ical(UID)))),
            ]
        )
        assert cal.get_event_by_uid(UID).id == UID
        assert methods(cal) == ["REPORT", "GET", "REPORT"]

    def test_get_of_wrong_type_is_not_taken(self):
        cal = calendar([PRECONDITION_FAILED, (200, ical(UID)), EMPTY])
        with pytest.raises(error.NotFoundError):
            cal.get_todo_by_uid(UID)
        assert methods(cal) == ["REPORT", "GET", "REPORT"]

    def test_no_comp_class_gives_the_right_class(self):
        cal = calendar([PRECONDITION_FAILED, (200, ical(UID, "VTODO"), {"Etag": '"t"'})])
        obj = cal.get_object_by_uid(UID)
        assert isinstance(obj, Todo)
        assert obj.props[dav.GetEtag.tag] == '"t"'

    def test_no_get_when_get_by_url_is_unsupported(self):
        cal = calendar(
            [PRECONDITION_FAILED, (207, multistatus(("/calendars/user/cal/ev.ics", ical(UID))))],
            features={"save-load.get-by-url": {"support": "unsupported"}},
        )
        assert cal.get_event_by_uid(UID).id == UID
        assert methods(cal) == ["REPORT", "REPORT"]

    def test_server_error_falls_back(self):
        cal = calendar([SERVER_ERROR, (200, ical(UID))])
        assert cal.get_event_by_uid(UID).id == UID
        assert methods(cal)[-1] == "GET"

    @pytest.mark.parametrize(
        "search_failure, raised",
        [
            (forbidden(), error.AuthorizationError),
            (error.RateLimitError(CAL_URL, "Too Many Requests"), error.RateLimitError),
            (NOT_FOUND, error.NotFoundError),
        ],
        ids=["403", "429", "404"],
    )
    def test_search_failures_that_are_raised(self, search_failure, raised):
        cal = calendar([search_failure])
        with pytest.raises(raised):
            cal.get_event_by_uid(UID)
        assert methods(cal) == ["REPORT"]

    def test_empty_search_result_is_not_found(self):
        cal = calendar([EMPTY])
        with pytest.raises(error.NotFoundError):
            cal.get_event_by_uid(UID)
        assert methods(cal) == ["REPORT"]

    def test_failing_scan_raises_its_own_error(self):
        cal = calendar([PRECONDITION_FAILED, NOT_FOUND, forbidden()])
        with pytest.raises(error.AuthorizationError) as excinfo:
            cal.get_event_by_uid(UID)
        assert "412" in str(excinfo.value.__context__)

    def test_comp_filter_is_not_retried(self):
        cal = calendar([PRECONDITION_FAILED])
        with pytest.raises(error.ReportError):
            cal.get_object_by_uid(UID, comp_filter=cdav.CompFilter("VEVENT"))
        assert methods(cal) == ["REPORT"]


class TestUidLookupFallbackAsync:
    def test_get_by_uid_name(self):
        cal = calendar([PRECONDITION_FAILED, (200, ical(UID), {"Etag": '"etag-1"'})], is_async=True)
        obj = asyncio.run(cal.get_event_by_uid(UID))
        assert obj.id == UID
        assert obj.props[dav.GetEtag.tag] == '"etag-1"'
        assert methods(cal) == ["REPORT", "GET"]

    def test_scan_when_not_found_by_name(self):
        cal = calendar(
            [
                PRECONDITION_FAILED,
                NOT_FOUND,
                (207, multistatus(("/calendars/user/cal/imported-1.ics", ical(SLASH_UID)))),
            ],
            is_async=True,
        )
        assert asyncio.run(cal.get_event_by_uid(SLASH_UID)).id == SLASH_UID
        assert methods(cal) == ["REPORT", "GET", "REPORT"]
