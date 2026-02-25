#!/usr/bin/env python
"""
Rule: None of the tests in this file should initiate any internet
communication, and there should be no dependencies on a working caldav
server for the tests in this file.  We use the Mock class when needed
to emulate server communication.
"""

import pickle
from datetime import date, datetime, timedelta, timezone
from unittest import mock
from urllib.parse import urlparse

import icalendar
import lxml.etree
import pytest

from caldav import (
    Calendar,
    CalendarObjectResource,
    CalendarSet,
    Event,
    Journal,
    Principal,
    Todo,
)
from caldav.davclient import DAVClient, DAVResponse
from caldav.elements import cdav, dav
from caldav.lib import error
from caldav.lib.python_utilities import to_normal_str, to_wire
from caldav.lib.url import URL

## Note on the imports - those two lines are equivalent:
# from caldav.objects import foo
# from caldav import foo
## This is due to a line like this in __init__.py:
# from .objects import *
## Said line should be deprecated at some point

## Some example icalendar data partly copied from test_caldav.py
ev1 = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:20010712T182145Z-123401@example.com
DTSTAMP:20060712T182145Z
DTSTART:20060714T170000Z
DTEND:20060715T040000Z
SUMMARY:Bastille Day Party
END:VEVENT
END:VCALENDAR
"""

todo = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:20070313T123432Z-456553@example.com
DTSTAMP:20070313T123432Z
DUE;VALUE=DATE:20070501
SUMMARY:Submit Quebec Income Tax Return for 2006
CLASS:CONFIDENTIAL
CATEGORIES:FAMILY,FINANCE
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""

todo_implicit_duration = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:20070313T123432Z-456553@example.com
DTSTAMP:20070313T123432Z
DTSTART;VALUE=DATE:20070425
DUE;VALUE=DATE:20070501
SUMMARY:Submit Quebec Income Tax Return for 2006
CLASS:CONFIDENTIAL
CATEGORIES:FAMILY,FINANCE
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""

todo_explicit_duration = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:20070313T123432Z-456553@example.com
DTSTAMP:20070313T123432Z
DTSTART:20070425T160000Z
DURATION:P5D
SUMMARY:Submit Quebec Income Tax Return for 2006
CLASS:CONFIDENTIAL
CATEGORIES:FAMILY,FINANCE
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""

todo_only_duration = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:20070313T123432Z-456553@example.com
DTSTAMP:20070313T123432Z
DURATION:P5D
SUMMARY:Submit Quebec Income Tax Return for 2006
CLASS:CONFIDENTIAL
CATEGORIES:FAMILY,FINANCE
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""

journal = """
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VJOURNAL
UID:19970901T130000Z-123405@example.com
DTSTAMP:19970901T130000Z
DTSTART;VALUE=DATE:19970317
SUMMARY:Staff meeting minutes
DESCRIPTION:1. Staff meeting: Participants include Joe\\, Lisa
  and Bob. Aurora project plans were reviewed. There is currently
  no budget reserves for this project. Lisa will escalate to
  management. Next meeting on Tuesday.\n
END:VJOURNAL
END:VCALENDAR
"""

# example from http://www.rfc-editor.org/rfc/rfc5545.txt
evr = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:19970901T130000Z-123403@example.com
DTSTAMP:19970901T130000Z
DTSTART;VALUE=DATE:19971102
SUMMARY:Our Blissful Anniversary
TRANSP:TRANSPARENT
CLASS:CONFIDENTIAL
CATEGORIES:ANNIVERSARY,PERSONAL,SPECIAL OCCASION
RRULE:FREQ=YEARLY
END:VEVENT
END:VCALENDAR"""

todo6 = """
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:19920901T130000Z-123408@host.com
DTSTAMP:19920901T130000Z
DTSTART:19920415T133000Z
DUE:19920516T045959Z
SUMMARY:Yearly Income Tax Preparation
RRULE:FREQ=YEARLY
CLASS:CONFIDENTIAL
CATEGORIES:FAMILY,FINANCE
PRIORITY:1
END:VTODO
END:VCALENDAR"""

## from https://github.com/python-caldav/caldav/issues/495
recurring_task_response = """<d:multistatus xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns" xmlns:cal="urn:ietf:params:xml:ns:caldav" xmlns:cs="http://calendarserver.org/ns/" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns">
  <d:response>
    <d:href>/remote.php/dav/calendars/oxi/personal/A9FFE819-5DDB-4947-A09C-308EEE5DA1F9.ics</d:href>
    <d:propstat>
      <d:prop>
        <cal:calendar-data>BEGIN:VCALENDAR
VERSION:2.0
PRODID:+//IDN bitfire.at//ical4android (at.techbee.jtx)
BEGIN:VTODO
DTSTAMP:20250522T075151Z
UID:8a8736b4-bc35-4085-a98b-89c2f52a5c51
SEQUENCE:23
CREATED:20250411T233004Z
LAST-MODIFIED:20250522T075137Z
SUMMARY:Clean Rosie filter
DTSTART;VALUE=DATE:20250415
RRULE:FREQ=WEEKLY;BYDAY=TU,FR
PRIORITY:0
END:VTODO
BEGIN:VTODO
DTSTAMP:20250522T075151Z
UID:8a8736b4-bc35-4085-a98b-89c2f52a5c51
SEQUENCE:1
CREATED:20250411T234336Z
LAST-MODIFIED:20250414T082134Z
SUMMARY:Clean Rosie filter
STATUS:COMPLETED
DTSTART;VALUE=DATE:20250415
RECURRENCE-ID;VALUE=DATE:20250415
COMPLETED:20250414T082134Z
PERCENT-COMPLETE:100
PRIORITY:0
END:VTODO
BEGIN:VTODO
DTSTAMP:20250522T075151Z
UID:8a8736b4-bc35-4085-a98b-89c2f52a5c51
SEQUENCE:1
CREATED:20250411T234336Z
LAST-MODIFIED:20250414T082134Z
SUMMARY:Clean Rosie filter
STATUS:CANCELLED
DTSTART;VALUE=DATE:20250418
RECURRENCE-ID;VALUE=DATE:20250418
PRIORITY:0
END:VTODO
BEGIN:VTODO
DTSTAMP:20250522T075151Z
UID:8a8736b4-bc35-4085-a98b-89c2f52a5c51
SEQUENCE:1
CREATED:20250411T234336Z
LAST-MODIFIED:20250414T082134Z
SUMMARY:Clean Rosie filter
STATUS:CANCELLED
DTSTART;VALUE=DATE:20250422
RECURRENCE-ID;VALUE=DATE:20250422
PRIORITY:0
END:VTODO
BEGIN:VTODO
DTSTAMP:20250522T075151Z
UID:8a8736b4-bc35-4085-a98b-89c2f52a5c51
SEQUENCE:1
CREATED:20250411T234336Z
LAST-MODIFIED:20250425T124511Z
SUMMARY:Clean Rosie filter
STATUS:COMPLETED
DTSTART;VALUE=DATE:20250425
RECURRENCE-ID;VALUE=DATE:20250425
COMPLETED:20250425T124511Z
PERCENT-COMPLETE:100
PRIORITY:0
END:VTODO
BEGIN:VTODO
DTSTAMP:20250522T075151Z
UID:8a8736b4-bc35-4085-a98b-89c2f52a5c51
SEQUENCE:1
CREATED:20250411T234336Z
LAST-MODIFIED:20250425T124511Z
SUMMARY:Clean Rosie filter
STATUS:CANCELLED
DTSTART;VALUE=DATE:20250429
RECURRENCE-ID;VALUE=DATE:20250429
COMPLETED:20250425T124511Z
PERCENT-COMPLETE:100
PRIORITY:0
END:VTODO
BEGIN:VTODO
DTSTAMP:20250522T075151Z
UID:8a8736b4-bc35-4085-a98b-89c2f52a5c51
SEQUENCE:1
CREATED:20250411T234336Z
LAST-MODIFIED:20250502T113705Z
SUMMARY:Clean Rosie filter
STATUS:COMPLETED
DTSTART;VALUE=DATE:20250502
RECURRENCE-ID;VALUE=DATE:20250502
COMPLETED:20250502T113705Z
PERCENT-COMPLETE:100
PRIORITY:0
END:VTODO
END:VCALENDAR
</cal:calendar-data>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""


def MockedDAVResponse(text, davclient=None):
    """
    For unit testing - a mocked DAVResponse with some specific content
    """
    resp = mock.MagicMock()
    resp.status_code = 207
    resp.reason = "multistatus"
    resp.headers = {}
    resp.content = text
    return DAVResponse(resp, davclient)


class MockedDAVClient(DAVClient):
    """
    For unit testing - a mocked DAVClient returning some specific content every time
    a request is performed
    """

    def __init__(self, xml_returned):
        self.xml_returned = xml_returned
        DAVClient.__init__(self, url="https://somwhere.in.the.universe.example/some/caldav/root")

    def request(self, *largs, **kwargs):
        return MockedDAVResponse(self.xml_returned)


class TestCalDAV:
    """
    Test class for "pure" unit tests (small internal tests, testing that
    a small unit of code works as expected, without any third party
    dependencies, without accessing any caldav server)
    """

    @mock.patch("caldav.davclient.requests.Session.request")
    def testRequestNonAscii(self, mocked):
        """
        ref https://github.com/python-caldav/caldav/issues/83
        """
        mocked().status_code = 200
        mocked().headers = {}
        cal_url = "http://me:hunter2@calendar.møøh.example:80/"
        client = DAVClient(url=cal_url)
        response = client.put("/foo/møøh/bar", "bringebærsyltetøy 北京 пиво", {})
        assert response.status == 200
        assert response.tree is None

        response = client.put(
            "/foo/møøh/bar".encode(),
            "bringebærsyltetøy 北京 пиво".encode(),
            {},
        )
        assert response.status == 200
        assert response.tree is None

    def testSearchForRecurringTask(self):
        client = MockedDAVClient(recurring_task_response)
        calendar = Calendar(client, url="/calendar/issue491/")
        mytasks = calendar.search(todo=True, expand=False, post_filter=True)
        assert len(mytasks) == 1
        mytasks = calendar.search(
            todo=True,
            expand=True,
            start=datetime(2025, 5, 5),
            end=datetime(2025, 6, 5),
        )
        assert len(mytasks) == 9

        ## It should not include the COMPLETED recurrences
        mytasks = calendar.search(
            todo=True,
            expand=True,
            start=datetime(2025, 1, 1),
            end=datetime(2025, 6, 5),
            ## TODO - TEMP workaround for compatibility issues!  post_filter should not be needed!
            post_filter=True,
        )
        assert len(mytasks) == 9

    def testLoadByMultiGet404(self):
        xml = """
<D:multistatus xmlns:D="DAV:">
  <D:response>
    <D:href>/calendars/pythoncaldav-test/20010712T182145Z-123401%40example.com.ics</D:href>
    <D:status>HTTP/1.1 404 Not Found</D:status>
  </D:response>
</D:multistatus>"""
        client = MockedDAVClient(xml)
        calendar = Calendar(client, url="/calendar/issue491/")
        object = Event(url="/calendar/issue491/notfound.ics", parent=calendar)
        with pytest.raises(error.NotFoundError):
            object.load_by_multiget()

    @mock.patch("caldav.davclient.requests.Session.request")
    def testRequestCustomHeaders(self, mocked):
        """
        ref https://github.com/python-caldav/caldav/issues/285
        also ref https://github.com/python-caldav/caldav/issues/385
        """
        mocked().status_code = 200
        mocked().headers = {}
        cal_url = "http://me:hunter2@calendar.møøh.example:80/"
        client = DAVClient(
            url=cal_url,
            headers={"X-NC-CalDAV-Webcal-Caching": "On", "User-Agent": "MyCaldavApp"},
        )
        assert client.headers["Content-Type"] == "text/xml"
        assert client.headers["X-NC-CalDAV-Webcal-Caching"] == "On"
        ## User-Agent would be overwritten by some boring default in earlier versions
        assert client.headers["User-Agent"] == "MyCaldavApp"

    @mock.patch("caldav.davclient.requests.Session.request")
    def testRequestUserAgent(self, mocked):
        """
        ref https://github.com/python-caldav/caldav/issues/391
        """
        mocked().status_code = 200
        mocked().headers = {}
        cal_url = "http://me:hunter2@calendar.møøh.example:80/"
        client = DAVClient(
            url=cal_url,
        )
        assert client.headers["Content-Type"] == "text/xml"
        assert client.headers["User-Agent"].startswith("python-caldav/")

    @mock.patch("caldav.davclient.requests.Session.request")
    def testEmptyXMLNoContentLength(self, mocked):
        """
        ref https://github.com/python-caldav/caldav/issues/213
        """
        mocked().status_code = 200
        mocked().headers = {"Content-Type": "text/xml"}
        mocked().content = ""
        client = DAVClient(url="AsdfasDF").request("/")

    @mock.patch("caldav.davclient.requests.Session.request")
    def testNonValidXMLNoContentLength(self, mocked):
        """
        If XML is expected but nonvalid XML is given, an error should be raised
        """
        mocked().status_code = 200
        mocked().headers = {"Content-Type": "text/xml"}
        mocked().content = "this is not XML"
        client = DAVClient(url="AsdfasDF")
        with pytest.raises(lxml.etree.XMLSyntaxError):
            client.request("/")

    def testPathWithEscapedCharacters(self):
        xml = b"""<D:multistatus xmlns:D="DAV:" xmlns:caldav="urn:ietf:params:xml:ns:caldav" xmlns:cs="http://calendarserver.org/ns/" xmlns:ical="http://apple.com/ns/ical/">
  <D:response xmlns:carddav="urn:ietf:params:xml:ns:carddav" xmlns:cm="http://cal.me.com/_namespace/" xmlns:md="urn:mobileme:davservices">
    <D:href>/some/caldav/root/133bahgr6ohlo9ungq0it45vf8%40group.calendar.google.com/events/</D:href>
    <D:propstat>
      <D:status>HTTP/1.1 200 OK</D:status>
      <D:prop>
        <caldav:supported-calendar-component-set>
          <caldav:comp name="VEVENT"/>
        </caldav:supported-calendar-component-set>
      </D:prop>
    </D:propstat>
  </D:response>
</D:multistatus>"""
        client = MockedDAVClient(xml)
        assert client.calendar(
            url="https://somwhere.in.the.universe.example/some/caldav/root/133bahgr6ohlo9ungq0it45vf8%40group.calendar.google.com/events/"
        ).get_supported_components() == ["VEVENT"]

    def testAbsoluteURL(self):
        """Version 0.7.0 does not handle responses with absolute URLs very well, ref https://github.com/python-caldav/caldav/pull/103"""
        ## none of this should initiate any communication
        client = DAVClient(url="http://cal.example.com/")
        principal = Principal(client=client, url="http://cal.example.com/home/bernard/")
        ## now, ask for the calendar_home_set, but first we need to mock up client.propfind
        mocked_response = mock.MagicMock()
        mocked_response.status_code = 207
        mocked_response.reason = "multistatus"
        mocked_response.headers = {}
        mocked_response.content = """
<xml>
<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
    <d:response>
        <d:href>http://cal.example.com/home/bernard/</d:href>
        <d:propstat>
            <d:prop>
                <c:calendar-home-set>
                    <d:href>http://cal.example.com/home/bernard/calendars/</d:href>
                </c:calendar-home-set>
            </d:prop>
            <d:status>HTTP/1.1 200 OK</d:status>
        </d:propstat>
    </d:response>
</d:multistatus>
</xml>"""
        mocked_davresponse = DAVResponse(mocked_response)
        client.propfind = mock.MagicMock(return_value=mocked_davresponse)
        bernards_calendars = principal.calendar_home_set
        assert bernards_calendars.url == URL("http://cal.example.com/home/bernard/calendars/")

    def _load(self, only_if_unloaded=True):
        self.data = todo6

    @mock.patch("caldav.calendarobjectresource.CalendarObjectResource.load", new=_load)
    def testDateSearch(self):
        """
        ## ref https://github.com/python-caldav/caldav/issues/133
        """
        xml = """<xml><multistatus xmlns="DAV:">
<response>
    <href>/principals/calendar/home@petroski.example.com/963/43B060B3-A023-48ED-B9E7-6FFD38D5073E.ics</href>
    <propstat>
      <prop/>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
    <propstat>
      <prop>
        <calendar-data xmlns="urn:ietf:params:xml:ns:caldav"/>
        <expand xmlns="urn:ietf:params:xml:ns:caldav"/>
      </prop>
      <status>HTTP/1.1 404 Not Found</status>
    </propstat>
  </response>
  <response>
    <href>/principals/calendar/home@petroski.example.com/963/114A4E50-8835-42E1-8185-8A97567B5C1A.ics</href>
    <propstat>
      <prop/>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
    <propstat>
      <prop>
        <calendar-data xmlns="urn:ietf:params:xml:ns:caldav"/>
        <expand xmlns="urn:ietf:params:xml:ns:caldav"/>
      </prop>
      <status>HTTP/1.1 404 Not Found</status>
    </propstat>
  </response>
  <response>
    <href>/principals/calendar/home@petroski.example.com/963/C20A8820-7156-4DD2-AD1D-17105D923145.ics</href>
    <propstat>
      <prop/>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
    <propstat>
      <prop>
        <calendar-data xmlns="urn:ietf:params:xml:ns:caldav"/>
        <expand xmlns="urn:ietf:params:xml:ns:caldav"/>
      </prop>
      <status>HTTP/1.1 404 Not Found</status>
    </propstat>
  </response>
</multistatus></xml>
"""
        client = MockedDAVClient(xml)
        calendar = Calendar(client, url="/principals/calendar/home@petroski.example.com/963/")
        with pytest.deprecated_call():
            results = calendar.date_search(datetime(2021, 2, 1), datetime(2021, 2, 7), expand=False)
            assert len(results) == 3

    def testCalendar(self):
        """
        Principal.calendar() and CalendarSet.calendar() should create
        Calendar objects without initiating any communication with the
        server.  Calendar.event() should create Event object without
        initiating any communication with the server.
        DAVClient.__init__ also doesn't do any communication
        Principal.__init__ as well, if the principal_url is given
        Principal.calendar_home_set needs to be set or the server will be queried
        """
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)

        principal = Principal(client, cal_url + "me/")
        principal.calendar_home_set = cal_url + "me/calendars/"
        # calendar_home_set is actually a CalendarSet object
        assert isinstance(principal.calendar_home_set, CalendarSet)
        calendar1 = principal.calendar(name="foo", cal_id="bar")
        calendar2 = principal.calendar_home_set.calendar(name="foo", cal_id="bar")
        calendar3 = principal.calendar(cal_id="bar")
        assert calendar1.url == calendar2.url
        assert calendar1.url == calendar3.url
        assert calendar1.url == "http://calendar.example:80/me/calendars/bar/"

        # principal.calendar_home_set can also be set to an object
        # This should be noop
        principal.calendar_home_set = principal.calendar_home_set
        calendar1 = principal.calendar(name="foo", cal_id="bar")
        assert calendar1.url == calendar2.url

        # When building a calendar from a relative URL and a client,
        # the relative URL should be appended to the base URL in the client
        calendar1 = Calendar(client, "someoneelse/calendars/main_calendar")
        calendar2 = Calendar(
            client,
            "http://me:hunter2@calendar.example:80/someoneelse/calendars/main_calendar",
        )
        assert calendar1.url == calendar2.url

    def test_get_events_icloud(self):
        """
        tests that some XML observed from the icloud returns 0 events found.
        """
        xml = """
<multistatus xmlns="DAV:">
  <response>
    <href>/17149682/calendars/testcalendar-485d002e-31b9-4147-a334-1d71503a4e2c/</href>
    <propstat>
      <prop>    </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
    <propstat>
      <prop>
        <calendar-data xmlns="urn:ietf:params:xml:ns:caldav"/>
      </prop>
      <status>HTTP/1.1 404 Not Found</status>
    </propstat>
  </response>
</multistatus>
        """
        client = MockedDAVClient(xml)
        calendar = Calendar(
            client,
            url="/17149682/calendars/testcalendar-485d002e-31b9-4147-a334-1d71503a4e2c/",
        )
        assert len(calendar.get_events()) == 0

    def test_get_calendars(self):
        xml = """
<D:multistatus xmlns:D="DAV:">
  <D:response>
    <D:href>/dav/tobias%40redpill-linpro.com/</D:href>
    <D:propstat>
      <D:status>HTTP/1.1 200 OK</D:status>
      <D:prop>
        <D:resourcetype>
          <D:collection/>
        </D:resourcetype>
        <D:displayname>USER_ROOT</D:displayname>
      </D:prop>
    </D:propstat>
  </D:response>
  <D:response>
    <D:href>/dav/tobias%40redpill-linpro.com/Inbox/</D:href>
    <D:propstat>
      <D:status>HTTP/1.1 200 OK</D:status>
      <D:prop>
        <D:resourcetype>
          <D:collection/>
          <C:schedule-inbox xmlns:C="urn:ietf:params:xml:ns:caldav"/>
        </D:resourcetype>
        <D:displayname>Inbox</D:displayname>
      </D:prop>
    </D:propstat>
  </D:response>
  <D:response>
    <D:href>/dav/tobias%40redpill-linpro.com/Emailed%20Contacts/</D:href>
    <D:propstat>
      <D:status>HTTP/1.1 200 OK</D:status>
      <D:prop>
        <D:resourcetype>
          <D:collection/>
          <C:addressbook xmlns:C="urn:ietf:params:xml:ns:carddav"/>
        </D:resourcetype>
        <D:displayname>Emailed Contacts</D:displayname>
      </D:prop>
    </D:propstat>
  </D:response>
  <D:response>
    <D:href>/dav/tobias%40redpill-linpro.com/Calendarc5f1a47c-2d92-11e3-b654-0016eab36bf4.ics</D:href>
    <D:propstat>
      <D:status>HTTP/1.1 200 OK</D:status>
      <D:prop>
        <D:resourcetype/>
        <D:displayname>Calendarc5f1a47c-2d92-11e3-b654-0016eab36bf4.ics</D:displayname>
      </D:prop>
    </D:propstat>
  </D:response>
  <D:response>
    <D:href>/dav/tobias%40redpill-linpro.com/Yep/</D:href>
    <D:propstat>
      <D:status>HTTP/1.1 200 OK</D:status>
      <D:prop>
        <D:resourcetype>
          <D:collection/>
          <C:calendar xmlns:C="urn:ietf:params:xml:ns:caldav"/>
        </D:resourcetype>
        <D:displayname>Yep</D:displayname>
      </D:prop>
    </D:propstat>
  </D:response>
</D:multistatus>
"""
        client = MockedDAVClient(xml)
        calendar_home_set = CalendarSet(client, url="/dav/tobias%40redpill-linpro.com/")
        assert len(calendar_home_set.get_calendars()) == 1

        def test_supported_components(self):
            xml = """
<multistatus xmlns="DAV:">
  <response xmlns="DAV:">
    <href>/17149682/calendars/testcalendar-0da571c7-139c-479a-9407-8ce9ed20146d/</href>
    <propstat>
      <prop>
        <supported-calendar-component-set xmlns="urn:ietf:params:xml:ns:caldav">
          <comp xmlns="urn:ietf:params:xml:ns:caldav" name="VEVENT"/>
        </supported-calendar-component-set>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
</multistatus>"""
            client = MockedDAVClient(xml)
            assert Calendar(
                client=client,
                url="/17149682/calendars/testcalendar-0da571c7-139c-479a-9407-8ce9ed20146d/",
            ).get_supported_components() == ["VEVENT"]

    def test_xml_parsing(self):
        """
        DAVResponse has quite some code to parse the XML received from the
        server.  This test contains real XML received from various
        caldav servers, and the expected result from the parse
        methods.
        """
        xml = """
<multistatus xmlns="DAV:">
  <response xmlns="DAV:">
    <href>/</href>
    <propstat>
      <prop>
        <current-user-principal xmlns="DAV:">
          <href xmlns="DAV:">/17149682/principal/</href>
        </current-user-principal>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
</multistatus>
"""
        expected_result = {"/": {"{DAV:}current-user-principal": "/17149682/principal/"}}

        assert (
            MockedDAVResponse(xml).expand_simple_props(props=[dav.CurrentUserPrincipal()])
            == expected_result
        )

        ## This duplicated response is observed in the real world -
        ## see https://github.com/python-caldav/caldav/issues/136
        ## (though I suppose there was an email address instead of
        ## simply "frank", the XML I got was obfuscated)
        xml = """<multistatus xmlns="DAV:">
  <response>
    <href>/principals/users/frank/</href>
    <propstat>
      <prop>
        <current-user-principal>
          <href>/principals/users/frank/</href>
        </current-user-principal>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
  <response>
    <href>/principals/users/frank/</href>
    <propstat>
      <prop>
        <current-user-principal>
          <href>/principals/users/frank/</href>
        </current-user-principal>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
</multistatus>
"""
        expected_result = {
            "/principals/users/frank/": {"{DAV:}current-user-principal": "/principals/users/frank/"}
        }
        assert (
            MockedDAVResponse(xml).expand_simple_props(props=[dav.CurrentUserPrincipal()])
            == expected_result
        )

        xml = """
<multistatus xmlns="DAV:">
  <response xmlns="DAV:">
    <href>/17149682/principal/</href>
    <propstat>
      <prop>
        <calendar-home-set xmlns="urn:ietf:params:xml:ns:caldav">
          <href xmlns="DAV:">https://p62-caldav.icloud.com:443/17149682/calendars/</href>
        </calendar-home-set>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
</multistatus>"""
        expected_result = {
            "/17149682/principal/": {
                "{urn:ietf:params:xml:ns:caldav}calendar-home-set": "https://p62-caldav.icloud.com:443/17149682/calendars/"
            }
        }
        assert (
            MockedDAVResponse(xml).expand_simple_props(props=[cdav.CalendarHomeSet()])
            == expected_result
        )

        xml = """
<multistatus xmlns="DAV:">
  <response xmlns="DAV:">
    <href>/</href>
    <propstat>
      <prop>
        <current-user-principal xmlns="DAV:">
          <href xmlns="DAV:">/17149682/principal/</href>
        </current-user-principal>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
</multistatus>"""
        expected_result = {"/": {"{DAV:}current-user-principal": "/17149682/principal/"}}
        assert (
            MockedDAVResponse(xml).expand_simple_props(props=[dav.CurrentUserPrincipal()])
            == expected_result
        )

        xml = """
<multistatus xmlns="DAV:">
  <response>
    <href>/17149682/calendars/testcalendar-84439d0b-ce46-4416-b978-7b4009122c64/</href>
    <propstat>
      <prop>
                </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
    <propstat>
      <prop>
        <calendar-data xmlns="urn:ietf:params:xml:ns:caldav"/>
      </prop>
      <status>HTTP/1.1 404 Not Found</status>
    </propstat>
  </response>
  <response>
    <href>/17149682/calendars/testcalendar-84439d0b-ce46-4416-b978-7b4009122c64/20010712T182145Z-123401%40example.com.ics</href>
    <propstat>
      <prop>
        <calendar-data xmlns="urn:ietf:params:xml:ns:caldav">BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:20010712T182145Z-123401@example.com
DTSTAMP:20060712T182145Z
DTSTART:20060714T170000Z
DTEND:20060715T040000Z
SUMMARY:Bastille Day Party
END:VEVENT
END:VCALENDAR
</calendar-data>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
</multistatus>
"""
        expected_result = {
            "/17149682/calendars/testcalendar-84439d0b-ce46-4416-b978-7b4009122c64/": {
                "{urn:ietf:params:xml:ns:caldav}calendar-data": None
            },
            "/17149682/calendars/testcalendar-84439d0b-ce46-4416-b978-7b4009122c64/20010712T182145Z-123401@example.com.ics": {
                "{urn:ietf:params:xml:ns:caldav}calendar-data": "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Example Corp.//CalDAV Client//EN\nBEGIN:VEVENT\nUID:20010712T182145Z-123401@example.com\nDTSTAMP:20060712T182145Z\nDTSTART:20060714T170000Z\nDTEND:20060715T040000Z\nSUMMARY:Bastille Day Party\nEND:VEVENT\nEND:VCALENDAR\n"
            },
        }
        assert (
            MockedDAVResponse(xml).expand_simple_props(props=[cdav.CalendarData()])
            == expected_result
        )

        xml = """
<multistatus xmlns="DAV:">
  <response xmlns="DAV:">
    <href>/17149682/calendars/</href>
    <propstat>
      <prop>
        <resourcetype xmlns="DAV:">
          <collection/>
        </resourcetype>
        <displayname xmlns="DAV:">Ny Test</displayname>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
  <response xmlns="DAV:">
    <href>/17149682/calendars/06888b87-397f-11eb-943b-3af9d3928d42/</href>
    <propstat>
      <prop>
        <resourcetype xmlns="DAV:">
          <collection/>
          <calendar xmlns="urn:ietf:params:xml:ns:caldav"/>
        </resourcetype>
        <displayname xmlns="DAV:">calfoo3</displayname>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
  <response xmlns="DAV:">
    <href>/17149682/calendars/inbox/</href>
    <propstat>
      <prop>
        <resourcetype xmlns="DAV:">
          <collection/>
          <schedule-inbox xmlns="urn:ietf:params:xml:ns:caldav"/>
        </resourcetype>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
    <propstat>
      <prop>
        <displayname xmlns="DAV:"/>
      </prop>
      <status>HTTP/1.1 404 Not Found</status>
    </propstat>
  </response>
  <response xmlns="DAV:">
    <href>/17149682/calendars/testcalendar-e2910e0a-feab-4b51-b3a8-55828acaa912/</href>
    <propstat>
      <prop>
        <resourcetype xmlns="DAV:">
          <collection/>
          <calendar xmlns="urn:ietf:params:xml:ns:caldav"/>
        </resourcetype>
        <displayname xmlns="DAV:">Yep</displayname>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
</multistatus>
"""
        expected_result = {
            "/17149682/calendars/": {
                "{DAV:}resourcetype": ["{DAV:}collection"],
                "{DAV:}displayname": "Ny Test",
            },
            "/17149682/calendars/06888b87-397f-11eb-943b-3af9d3928d42/": {
                "{DAV:}resourcetype": [
                    "{DAV:}collection",
                    "{urn:ietf:params:xml:ns:caldav}calendar",
                ],
                "{DAV:}displayname": "calfoo3",
            },
            "/17149682/calendars/inbox/": {
                "{DAV:}resourcetype": [
                    "{DAV:}collection",
                    "{urn:ietf:params:xml:ns:caldav}schedule-inbox",
                ],
                "{DAV:}displayname": None,
            },
            "/17149682/calendars/testcalendar-e2910e0a-feab-4b51-b3a8-55828acaa912/": {
                "{DAV:}resourcetype": [
                    "{DAV:}collection",
                    "{urn:ietf:params:xml:ns:caldav}calendar",
                ],
                "{DAV:}displayname": "Yep",
            },
        }
        assert (
            MockedDAVResponse(xml).expand_simple_props(
                props=[dav.DisplayName()], multi_value_props=[dav.ResourceType()]
            )
            == expected_result
        )

        xml = """
<multistatus xmlns="DAV:">
  <response xmlns="DAV:">
    <href>/17149682/calendars/testcalendar-f96b3bf0-09e1-4f3d-b891-3a25c99a2894/</href>
    <propstat>
      <prop>
        <getetag xmlns="DAV:">"kkkgopik"</getetag>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
  <response xmlns="DAV:">
    <href>/17149682/calendars/testcalendar-f96b3bf0-09e1-4f3d-b891-3a25c99a2894/1761bf8c-6363-11eb-8fe4-74e5f9bfd8c1.ics</href>
    <propstat>
      <prop>
        <getetag xmlns="DAV:">"kkkgorwx"</getetag>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
  <response xmlns="DAV:">
    <href>/17149682/calendars/testcalendar-f96b3bf0-09e1-4f3d-b891-3a25c99a2894/20010712T182145Z-123401%40example.com.ics</href>
    <propstat>
      <prop>
        <getetag xmlns="DAV:">"kkkgoqqu"</getetag>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
  <sync-token>HwoQEgwAAAh4yw8ntwAAAAAYAhgAIhUIopml463FieB4EKq9+NSn04DrkQEoAA==</sync-token>
</multistatus>
"""
        expected_results = {
            "/17149682/calendars/testcalendar-f96b3bf0-09e1-4f3d-b891-3a25c99a2894/": {
                "{DAV:}getetag": '"kkkgopik"',
                "{urn:ietf:params:xml:ns:caldav}calendar-data": None,
            },
            "/17149682/calendars/testcalendar-f96b3bf0-09e1-4f3d-b891-3a25c99a2894/1761bf8c-6363-11eb-8fe4-74e5f9bfd8c1.ics": {
                "{DAV:}getetag": '"kkkgorwx"',
                "{urn:ietf:params:xml:ns:caldav}calendar-data": None,
            },
            "/17149682/calendars/testcalendar-f96b3bf0-09e1-4f3d-b891-3a25c99a2894/20010712T182145Z-123401@example.com.ics": {
                "{DAV:}getetag": '"kkkgoqqu"',
                "{urn:ietf:params:xml:ns:caldav}calendar-data": None,
            },
        }

    def testHugeTreeParam(self):
        """
        With dealing with a huge XML response, such as event containing attachments, XMLParser will throw an exception
        huge_tree parameters allows to handle this kind of events.
        """

        xml = """
<multistatus xmlns="DAV:">
  <response>
    <href>/17149682/calendars/testcalendar-84439d0b-ce46-4416-b978-7b4009122c64/</href>
    <propstat>
      <prop>
                </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
    <propstat>
      <prop>
        <calendar-data xmlns="urn:ietf:params:xml:ns:caldav"/>
      </prop>
      <status>HTTP/1.1 404 Not Found</status>
    </propstat>
  </response>
  <response>
    <href>/17149682/calendars/testcalendar-84439d0b-ce46-4416-b978-7b4009122c64/20010712T182145Z-123401%40example.com.ics</href>
    <propstat>
      <prop>
        <calendar-data xmlns="urn:ietf:params:xml:ns:caldav">

BEGIN:VCALENDAR
PRODID:-//MDaemon Technologies Ltd//MDaemon 21.5.2
VERSION:2.0
METHOD:PUBLISH
BEGIN:VEVENT
UID:
 040000008200E0007000B7101A82E0080000000050BF99B19D31
SEQUENCE:0
DTSTAMP:20230213T142930Z
SUMMARY:This a summary of a very bug event
DESCRIPTION:Description of this very big event
LOCATION:Somewhere
ORGANIZER:MAILTO:noreply@test.com
PRIORITY:5
ATTACH;VALUE=BINARY;ENCODING=BASE64;FMTTYPE=image/jpeg;
 X-FILENAME=image001.jpg;X-ORACLE-FILENAME=image001.jpg:
"""
        xml += (
            "gIyIoLTkwKCo2KyIjM4444449QEBAJjBGS0U+Sjk/QD3/2wBDAQsLCw8NDx0QEB09KSMpPT09\n" * 153490
        )
        xml += """
 /Z
DTSTART;TZID="Europe/Paris":20230310T140000
DTEND;TZID="Europe/Paris":20230310T150000
END:VEVENT
END:VCALENDAR
</calendar-data>
      </prop>
      <status>HTTP/1.1 200 OK</status>
    </propstat>
  </response>
</multistatus>
"""
        davclient = MockedDAVClient(xml)
        resp = mock.MagicMock()
        resp.headers = {"Content-Type": "text/xml"}
        resp.content = xml

        ## It seems like the huge_tree flag is not necessary in all
        ## environments as of 2023-07.  Perhaps versioning issues with
        ## the lxml library.
        # davclient.huge_tree = False
        # try:
        #    import pdb; pdb.set_trace()
        #    DAVResponse(resp, davclient=davclient)
        #    assert False
        # except Exception as e:
        #    assert type(e) == lxml.etree.XMLSyntaxError

        davclient.huge_tree = True
        try:
            DAVResponse(resp, davclient=davclient)
            assert True
        except:
            assert False

    def testFailedQuery(self):
        """
        ref https://github.com/python-caldav/caldav/issues/54
        """
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        calhome = CalendarSet(client, cal_url + "me/")

        ## syntesize a failed response
        class FailedResp:
            pass

        failedresp = FailedResp()
        failedresp.status = 400
        failedresp.reason = "you are wrong"
        failedresp.raw = "your request does not adhere to standards"

        ## synthesize a new http method
        calhome.client.unknown_method = lambda url, body, depth: failedresp

        ## call it.
        with pytest.raises(error.DAVError):
            calhome._query(query_method="unknown_method")

    def testDefaultClient(self):
        """When no client is given to a DAVObject, but the parent is given,
        parent.client will be used"""
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        calhome = CalendarSet(client, cal_url + "me/")
        calendar = Calendar(parent=calhome)
        assert calendar.client == calhome.client

    def testData(self):
        """
        Event.data should always return a unicode string, without \r
        Event.wire_data should always return a byte string, with \r\n
        """
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        my_event = Event(client, data=ev1)
        ## bytes on py3, normal string on py2 (but nobody uses python2, I hope?)
        bytestr = b"".__class__
        assert isinstance(my_event.data, str)
        assert isinstance(my_event.wire_data, bytestr)
        ## this may have side effects, as it converts the internal storage
        my_event.icalendar_instance
        assert isinstance(my_event.data, str)
        assert isinstance(my_event.wire_data, bytestr)
        ## this may have side effects, as it converts the internal storage
        my_event.vobject_instance
        assert isinstance(my_event.data, str)
        assert isinstance(my_event.wire_data, bytestr)
        my_event.wire_data = to_wire(ev1)
        assert isinstance(my_event.data, str)
        assert isinstance(my_event.wire_data, bytestr)
        my_event.data = to_normal_str(ev1)
        assert isinstance(my_event.data, str)
        assert isinstance(my_event.wire_data, bytestr)

    def testInstance(self):
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        my_event = Event(client, data=ev1)
        my_event.vobject_instance.vevent.summary.value = "new summary"
        assert "new summary" in my_event.data
        icalobj = my_event.icalendar_instance
        icalobj.subcomponents[0]["SUMMARY"] = "yet another summary"
        assert my_event.vobject_instance.vevent.summary.value == "yet another summary"
        ## Now the data has been converted from string to vobject to string to icalendar to string to vobject and ... will the string still match the original?
        lines_now = my_event.data.strip().split("\n")
        lines_orig = ev1.replace("Bastille Day Party", "yet another summary").strip().split("\n")
        lines_now.sort()
        lines_orig.sort()
        assert lines_now == lines_orig

    def testComponent(self):
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        my_event = Event(client, data=ev1)
        icalcomp = my_event.icalendar_component
        icalcomp["SUMMARY"] = "yet another summary"
        assert my_event.vobject_instance.vevent.summary.value == "yet another summary"
        ## will the string still match the original?
        lines_now = my_event.data.strip().split("\n")
        lines_orig = ev1.replace("Bastille Day Party", "yet another summary").strip().split("\n")
        lines_now.sort()
        lines_orig.sort()
        assert lines_now == lines_orig
        ## Can we replace the component?  (One shouldn't do things like this in normal circumstances though ... both because the uid changes and because the component type changes - we're putting a vtodo into an Event class ...)
        icalendar_component = icalendar.Todo.from_ical(todo).subcomponents[0]
        my_event.icalendar_component = icalendar_component
        assert (
            my_event.vobject_instance.vtodo.summary.value
            == "Submit Quebec Income Tax Return for 2006"
        )

    def testComponentSet(self):
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        target = Event(client, data=evr)

        ## Creating some dummy data such that the target has more than one subcomponent
        with pytest.deprecated_call():
            target.expand_rrule(start=datetime(1996, 10, 10), end=datetime(1999, 12, 12))
            assert len(target.icalendar_instance.subcomponents) == 3

        ## The following should not fail within _set_icalendar_component
        target.icalendar_component = icalendar.Todo.from_ical(todo).subcomponents[0]
        assert len(target.icalendar_instance.subcomponents) == 1

    def testNewDataAPI(self):
        """Test the new safe data access API (issue #613).

        The new API provides:
        - get_data() / get_icalendar_instance() / get_vobject_instance() for read-only access
        - edit_icalendar_instance() / edit_vobject_instance() context managers for editing
        """
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        event = Event(client, data=ev1)

        # Test get_data() returns string
        data = event.get_data()
        assert isinstance(data, str)
        assert "Bastille Day Party" in data

        # Test get_icalendar_instance() returns a COPY
        ical1 = event.get_icalendar_instance()
        ical2 = event.get_icalendar_instance()
        assert ical1 is not ical2  # Different objects (copies)

        # Modifying the copy should NOT affect the original
        for comp in ical1.subcomponents:
            if comp.name == "VEVENT":
                comp["SUMMARY"] = "Modified in copy"
        assert "Modified in copy" not in event.get_data()

        # Test get_vobject_instance() returns a COPY
        vobj1 = event.get_vobject_instance()
        vobj2 = event.get_vobject_instance()
        assert vobj1 is not vobj2  # Different objects (copies)

        # Test edit_icalendar_instance() context manager
        with event.edit_icalendar_instance() as cal:
            for comp in cal.subcomponents:
                if comp.name == "VEVENT":
                    comp["SUMMARY"] = "Edited Summary"

        # Changes should be reflected
        assert "Edited Summary" in event.get_data()

        # Test edit_vobject_instance() context manager
        with event.edit_vobject_instance() as vobj:
            vobj.vevent.summary.value = "Vobject Edit"

        assert "Vobject Edit" in event.get_data()

        # Test that nested borrowing of different types raises error
        with event.edit_icalendar_instance() as cal:
            with pytest.raises(RuntimeError):
                with event.edit_vobject_instance() as vobj:
                    pass

    def testDataAPICheapAccessors(self):
        """Test the cheap internal accessors for issue #613.

        These accessors avoid unnecessary format conversions when we just
        need to peek at basic properties like UID or component type.
        """
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)

        # Test with event
        event = Event(client, data=ev1)
        assert event._get_uid_cheap() == "20010712T182145Z-123401@example.com"
        assert event._get_component_type_cheap() == "VEVENT"
        assert event._has_data() is True

        # Test with todo
        my_todo = Todo(client, data=todo)
        assert my_todo._get_uid_cheap() == "20070313T123432Z-456553@example.com"
        assert my_todo._get_component_type_cheap() == "VTODO"
        assert my_todo._has_data() is True

        # Test with journal
        my_journal = CalendarObjectResource(client, data=journal)
        assert my_journal._get_uid_cheap() == "19970901T130000Z-123405@example.com"
        assert my_journal._get_component_type_cheap() == "VJOURNAL"
        assert my_journal._has_data() is True

        # Test with no data
        empty_event = Event(client)
        assert empty_event._get_uid_cheap() is None
        assert empty_event._get_component_type_cheap() is None
        assert empty_event._has_data() is False

    def testDataAPIStateTransitions(self):
        """Test state transitions in the data API (issue #613).

        Verify that the internal state correctly transitions between
        RawDataState, IcalendarState, and VobjectState.
        """
        from caldav.datastate import (
            IcalendarState,
            RawDataState,
            VobjectState,
        )

        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        event = Event(client, data=ev1)

        # Initial state should be RawDataState (or lazy init)
        event._ensure_state()
        assert isinstance(event._state, RawDataState)

        # get_data() should NOT change state
        _ = event.get_data()
        assert isinstance(event._state, RawDataState)

        # get_icalendar_instance() should NOT change state (returns copy)
        _ = event.get_icalendar_instance()
        assert isinstance(event._state, RawDataState)

        # edit_icalendar_instance() SHOULD change state to IcalendarState
        with event.edit_icalendar_instance() as cal:
            pass
        assert isinstance(event._state, IcalendarState)

        # edit_vobject_instance() SHOULD change state to VobjectState
        with event.edit_vobject_instance() as vobj:
            pass
        assert isinstance(event._state, VobjectState)

        # get_data() should still work from VobjectState
        data = event.get_data()
        assert "Bastille Day Party" in data

    def testDataAPINoDataState(self):
        """Test NoDataState behavior (issue #613).

        When an object has no data, the NoDataState should provide
        sensible defaults without raising errors.
        """
        from caldav.datastate import NoDataState

        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        event = Event(client)  # No data

        # Ensure state is NoDataState
        event._ensure_state()
        assert isinstance(event._state, NoDataState)

        # get_data() should return empty string
        assert event.get_data() == ""

        # get_icalendar_instance() should return empty Calendar
        ical = event.get_icalendar_instance()
        assert ical is not None
        assert len(list(ical.subcomponents)) == 0

        # Cheap accessors should return None
        assert event._get_uid_cheap() is None
        assert event._get_component_type_cheap() is None
        assert event._has_data() is False

    def testDataAPIEdgeCases(self):
        """Test edge cases in the data API (issue #613)."""
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)

        # Test with folded UID line (UID split across lines)
        folded_uid_data = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:this-is-a-very-long-uid-that-might-be-folded-across-multiple-lines-in-r
 eal-world-icalendar-files@example.com
DTSTAMP:20060712T182145Z
DTSTART:20060714T170000Z
SUMMARY:Folded UID Test
END:VEVENT
END:VCALENDAR
"""
        event = Event(client, data=folded_uid_data)
        # The cheap accessor uses regex which might not handle folded lines
        # So we test that it falls back to full parsing when needed
        uid = event._get_uid_cheap()
        # Either the regex works or it falls back - either way we should get a UID
        assert uid is not None
        assert "this-is-a-very-long-uid" in uid

        # Test that nested borrowing (even same type) raises error
        # This prevents confusing ownership semantics
        event2 = Event(client, data=ev1)
        with event2.edit_icalendar_instance() as cal1:
            with pytest.raises(RuntimeError):
                with event2.edit_icalendar_instance() as cal2:
                    pass

        # Test sequential edits work fine
        event3 = Event(client, data=ev1)
        with event3.edit_icalendar_instance() as cal:
            for comp in cal.subcomponents:
                if comp.name == "VEVENT":
                    comp["SUMMARY"] = "First Edit"
        assert "First Edit" in event3.get_data()

        # Second edit after first is complete
        with event3.edit_icalendar_instance() as cal:
            for comp in cal.subcomponents:
                if comp.name == "VEVENT":
                    comp["SUMMARY"] = "Second Edit"
        assert "Second Edit" in event3.get_data()

    def testTodoDuration(self):
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        my_todo1 = Todo(client, data=todo)
        my_todo2 = Todo(client, data=todo_implicit_duration)
        my_todo3 = Todo(client, data=todo_explicit_duration)
        my_todo4 = Todo(client, data=todo_only_duration)
        orig_start = date(2007, 5, 1)
        ## TODO: Check the RFC.  For events a whole-day event without duration/dtend defaults to lasting for one day.  Probably the same with tasks?
        assert my_todo1.get_duration() == timedelta(0)
        assert my_todo1.get_due() == orig_start
        assert my_todo2.get_duration() == timedelta(days=6)
        assert my_todo2.get_due() == orig_start
        assert my_todo3.get_duration() == timedelta(days=5)
        foo6 = my_todo3.get_due().strftime("%s") == "1177945200"
        some_date = date(2011, 1, 1)

        my_todo1.set_due(some_date)
        assert my_todo1.get_due() == some_date

        ## set_due has "only" one if, so two code paths, one where dtstart is actually moved and one where it isn't
        my_todo2.set_due(some_date, move_dtstart=True)
        assert my_todo2.icalendar_instance.subcomponents[0]["DTSTART"].dt == some_date - timedelta(
            days=6
        )

        ## set_duration at the other hand has 5 code paths ...
        ## 1) DTSTART set, DTSTART as the movable component
        my_todo1.set_duration(timedelta(1))
        assert my_todo1.get_due() == some_date
        assert my_todo1.icalendar_instance.subcomponents[0]["DTSTART"].dt == some_date - timedelta(
            1
        )

        ## 2) DUE and DTSTART set, DUE as the movable component
        my_todo1.set_duration(timedelta(2), movable_attr="DUE")
        assert my_todo1.get_due() == some_date + timedelta(days=1)
        assert my_todo1.icalendar_instance.subcomponents[0]["DTSTART"].dt == some_date - timedelta(
            1
        )

        ## 3) DUE set, DTSTART not set
        dtstart = my_todo1.icalendar_instance.subcomponents[0].pop("DTSTART").dt
        my_todo1.set_duration(timedelta(2))
        assert my_todo1.icalendar_instance.subcomponents[0]["DTSTART"].dt == dtstart

        ## 4) DTSTART set, DUE not set
        my_todo1.icalendar_instance.subcomponents[0].pop("DUE")
        my_todo1.set_duration(timedelta(1))
        assert my_todo1.get_due() == some_date

        ## 5) Neither DUE nor DTSTART set
        my_todo1.icalendar_instance.subcomponents[0].pop("DUE")
        my_todo1.icalendar_instance.subcomponents[0].pop("DTSTART")
        my_todo1.set_duration(timedelta(days=3))
        assert my_todo1.get_duration() == timedelta(days=3)

        ## 6) DUE and DTSTART set, DTSTART as the movable component (default)
        my_todo2 = Todo(client, data=todo_implicit_duration)
        orig_end = my_todo2.component.end
        my_todo2.set_duration(timedelta(2))
        assert my_todo2.component.start == orig_start - timedelta(2)
        assert my_todo2.component.end == orig_end

        ## 7) DURATION set, but neither DTSTART nor DTEND
        assert "DTSTART" not in my_todo4.component
        assert "DUE" not in my_todo4.component
        assert my_todo4.component["duration"].dt == timedelta(5)
        my_todo4.set_duration(timedelta(2))
        assert "DTSTART" not in my_todo4.component
        assert "DUE" not in my_todo4.component
        assert my_todo4.component["duration"].dt == timedelta(2)

    def testURL(self):
        """Exercising the URL class"""
        long_url = "http://foo:bar@www.example.com:8080/caldav.php/?foo=bar"

        # 1) URL.objectify should return a valid URL object almost no matter
        # what's thrown in
        url0 = URL.objectify(None)
        url0b = URL.objectify("")
        url1 = URL.objectify(long_url)
        url2 = URL.objectify(url1)
        url3 = URL.objectify("/bar")
        url4 = URL.objectify(urlparse(str(url1)))
        url5 = URL.objectify(urlparse("/bar"))

        # 2) __eq__ works well
        assert url1 == url2
        assert url1 == url4
        assert url3 == url5

        # 3) str will always return the URL
        assert str(url1) == long_url
        assert str(url3) == "/bar"
        assert str(url4) == long_url
        assert str(url5) == "/bar"

        ## 3b) repr should also be exercised.  Returns URL(/bar) now.
        assert "/bar" in repr(url5)
        assert "URL" in repr(url5)
        assert len(repr(url5)) < 12

        # 4) join method
        url6 = url1.join(url2)
        url7 = url1.join(url3)
        url8 = url1.join(url4)
        url9 = url1.join(url5)
        urlA = url1.join("someuser/calendar")
        urlB = url5.join(url1)
        assert url6 == url1
        assert url7 == "http://foo:bar@www.example.com:8080/bar"
        assert url8 == url1
        assert url9 == url7
        assert urlA == "http://foo:bar@www.example.com:8080/caldav.php/someuser/calendar"
        assert urlB == url1
        with pytest.raises(ValueError):
            url1.join("http://www.google.com")

        # 4b) join method, with URL as input parameter
        url6 = url1.join(URL.objectify(url2))
        url7 = url1.join(URL.objectify(url3))
        url8 = url1.join(URL.objectify(url4))
        url9 = url1.join(URL.objectify(url5))
        urlA = url1.join(URL.objectify("someuser/calendar"))
        urlB = url5.join(URL.objectify(url1))
        url6b = url6.join(url0)
        url6c = url6.join(url0b)
        url6d = url6.join(None)
        for url6alt in (url6b, url6c, url6d):
            assert url6 == url6alt
        assert url6 == url1
        assert url7 == "http://foo:bar@www.example.com:8080/bar"
        assert url8 == url1
        assert url9 == url7
        assert urlA == "http://foo:bar@www.example.com:8080/caldav.php/someuser/calendar"
        assert urlB == url1
        with pytest.raises(ValueError):
            url1.join("http://www.google.com")

        # 5) all urlparse methods will work.  always.
        assert url1.scheme == "http"
        assert url2.path == "/caldav.php/"
        assert url7.username == "foo"
        assert url5.path == "/bar"
        urlC = URL.objectify("https://www.example.com:443/foo")
        assert urlC.port == 443

        # 6) is_auth returns True if the URL contains a username.
        assert not urlC.is_auth()
        assert url7.is_auth()

        # 7) unauth() strips username/password
        assert url7.unauth() == "http://www.example.com:8080/bar"

        # 8) strip_trailing_slash
        assert URL("http://www.example.com:8080/bar/").strip_trailing_slash() == URL(
            "http://www.example.com:8080/bar"
        )
        assert (
            URL("http://www.example.com:8080/bar/").strip_trailing_slash()
            == URL("http://www.example.com:8080/bar").strip_trailing_slash()
        )

        # 9) canonical
        assert (
            URL("https://www.example.com:443/b%61r/").canonical()
            == URL("//www.example.com/bar/").canonical()
        )

        # 10) pickle
        assert pickle.loads(pickle.dumps(url1)) == url1

    def testFilters(self):
        filter = cdav.Filter().append(
            cdav.CompFilter("VCALENDAR").append(
                cdav.CompFilter("VEVENT").append(
                    cdav.PropFilter("UID").append([cdav.TextMatch("pouet", negate=True)])
                )
            )
        )
        # print(filter)

        crash = cdav.CompFilter()
        value = None
        try:
            value = str(crash)
        except:
            pass
        if value is not None:
            raise Exception("This should have crashed")

    def test_calendar_comp_class_by_data(self):
        calendar = Calendar()
        for ical, class_ in (
            (ev1, Event),
            (todo, Todo),
            (journal, Journal),
            (None, CalendarObjectResource),
            ("random rantings", CalendarObjectResource),
        ):  ## TODO: freebusy, time zone
            assert calendar._calendar_comp_class_by_data(ical) == class_
            if ical != "random rantings" and ical:
                assert (
                    calendar._calendar_comp_class_by_data(icalendar.Calendar.from_ical(ical))
                    == class_
                )

    def testContextManager(self):
        """
        ref https://github.com/python-caldav/caldav/pull/175
        """
        cal_url = "http://me:hunter2@calendar.example:80/"
        with DAVClient(url=cal_url) as client_ctx_mgr:
            assert isinstance(client_ctx_mgr, DAVClient)

    def testExtractAuth(self):
        """
        ref https://github.com/python-caldav/caldav/issues/289
        """
        cal_url = "http://me:hunter2@calendar.example:80/"
        with DAVClient(url=cal_url) as client:
            assert client.extract_auth_types("Basic\n") == {"basic"}
            assert client.extract_auth_types("Basic") == {"basic"}
            assert client.extract_auth_types('Basic Realm=foo;charset="UTF-8"') == {"basic"}
            assert client.extract_auth_types("Basic,dIGEST Realm=foo") == {
                "basic",
                "digest",
            }

    def testAutoUrlEcloudWithEmailUsername(self) -> None:
        """
        Test that auto-connect URL construction works correctly for ecloud
        when username is an email address and no URL is provided.

        Bug: When username is "tobixen@e.email" and no URL is provided,
        the auto-connect logic should use the domain from the ecloud hints
        (ecloud.global) rather than treating the username as a URL.

        Expected URL: https://ecloud.global/remote.php/dav

        The bug occurs when RFC6764 discovery is enabled (default behavior):
        1. Line 133-135 sets url = username for discovery
        2. RFC6764 discovery fails for the invalid email-as-domain
        3. Fallback logic (line 166-167) doesn't replace url with domain from hints
           because url is no longer empty
        4. Result: https://tobixen@e.email/remote.php/dav (wrong!)
           Should be: https://ecloud.global/remote.php/dav
        """
        from caldav.compatibility_hints import ecloud
        from caldav.davclient import _auto_url

        # Test with email username and no URL - should use ecloud domain from hints
        # RFC6764 is enabled by default, which triggers the bug
        url, discovered_username = _auto_url(
            url=None,
            username="tobixen@e.email",
            features=ecloud,
            enable_rfc6764=True,  # Default behavior - this triggers the bug
        )

        assert url == "https://ecloud.global/remote.php/dav", (
            f"Expected 'https://ecloud.global/remote.php/dav', got '{url}'"
        )
        assert discovered_username is None

    def testSearcherMethod(self):
        """Test that calendar.searcher() returns a properly configured CalDAVSearcher.

        This tests issue #590 - the new API for creating search objects.
        """
        from caldav.search import CalDAVSearcher

        client = MockedDAVClient(recurring_task_response)
        calendar = Calendar(client, url="/calendar/issue491/")

        # Test basic searcher creation
        searcher = calendar.searcher(event=True)
        assert isinstance(searcher, CalDAVSearcher)
        assert searcher._calendar is calendar
        assert searcher.event is True

        # Test with multiple parameters
        searcher = calendar.searcher(
            todo=True,
            start=datetime(2025, 1, 1),
            end=datetime(2025, 12, 31),
            expand=True,
        )
        assert searcher.todo is True
        assert searcher.start == datetime(2025, 1, 1)
        assert searcher.end == datetime(2025, 12, 31)
        assert searcher.expand is True

        # Test with sort keys
        searcher = calendar.searcher(sort_keys=["due", "priority"], sort_reverse=True)
        assert len(searcher._sort_keys) == 2

        # Test with property filters
        searcher = calendar.searcher(summary="meeting", location="office")
        assert "summary" in searcher._property_filters
        assert "location" in searcher._property_filters

        # Test with no_* filters (undef operator goes to _property_operator, not _property_filters)
        searcher = calendar.searcher(no_summary=True)
        assert searcher._property_operator.get("summary") == "undef"

        # Test that search() works without calendar argument
        # Note: post_filter is a parameter to search(), not the searcher
        mytasks = calendar.searcher(todo=True, expand=False).search(post_filter=True)
        assert len(mytasks) == 1

    def testSearcherWithoutCalendar(self):
        """Test that CalDAVSearcher.search() raises ValueError without calendar."""
        from caldav.search import CalDAVSearcher

        searcher = CalDAVSearcher(event=True)
        with pytest.raises(ValueError, match="No calendar provided"):
            searcher.search()

    def testGetObjectByUidUsesSelfSearch(self):
        """
        get_object_by_uid() must call self.search() (Calendar.search) rather than
        constructing a CalDAVSearcher directly.  This ensures that any
        monkey-patching of Calendar.search - such as the search-cache delay for
        servers with lazy search indexes (purelymail) - is also applied when
        looking up objects by UID.

        See also testObjectByUID in the integration tests for the exact-match
        guarantee.
        """
        uid = "20010712T182145Z-123401@example.com"
        # Build a minimal multistatus response containing ev1
        xml_response = f"""<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/calendar/ev1.ics</d:href>
    <d:propstat>
      <d:prop>
        <cal:calendar-data>{ev1}</cal:calendar-data>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>"""
        client = MockedDAVClient(xml_response)
        calendar = Calendar(client, url="/calendar/")

        # Patch Calendar.search to track calls, while still delegating to
        # the original implementation.
        search_calls = []
        original_search = Calendar.search

        def tracking_search(self_, *args, **kwargs):
            search_calls.append((args, kwargs))
            return original_search(self_, *args, **kwargs)

        Calendar.search = tracking_search
        try:
            result = calendar.get_object_by_uid(uid, comp_class=Event)
            assert result.id == uid
            assert search_calls, "Calendar.search was not called by get_object_by_uid"
        finally:
            Calendar.search = original_search

    def testGetObjectByUidExactMatch(self):
        """
        get_object_by_uid() must return only an object with the exact requested UID,
        even if the server (doing a substring search) returns objects with UIDs
        that merely contain the requested UID as a substring.
        """
        uid_exact = "20010712T182145Z-123401@example.com"
        uid_superstring = "20010712T182145Z-123401@example.com-extra"
        ev_superstring = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:{uid_superstring}
DTSTAMP:20060712T182145Z
DTSTART:20060714T170000Z
DTEND:20060715T040000Z
SUMMARY:Bastille Day Party extra
END:VEVENT
END:VCALENDAR
"""
        # Server returns both the exact-match event AND a superstring-UID event
        # (simulating a server that does substring matching)
        xml_response = f"""<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/calendar/ev1.ics</d:href>
    <d:propstat>
      <d:prop>
        <cal:calendar-data>{ev1}</cal:calendar-data>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/calendar/ev_superstring.ics</d:href>
    <d:propstat>
      <d:prop>
        <cal:calendar-data>{ev_superstring}</cal:calendar-data>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>"""
        client = MockedDAVClient(xml_response)
        calendar = Calendar(client, url="/calendar/")

        # Only the exact-UID match should be returned
        result = calendar.get_object_by_uid(uid_exact)
        assert result.id == uid_exact

        # Searching for a UID that exists only as a substring of another should fail
        with pytest.raises(error.NotFoundError):
            calendar.get_object_by_uid("20010712T182145Z-123401@example.com-nope")


class TestRateLimitHelpers:
    """Unit tests for the shared rate-limit helper functions in caldav.lib.error."""

    def test_parse_retry_after_integer(self):
        assert error.parse_retry_after("30") == 30.0

    def test_parse_retry_after_zero(self):
        assert error.parse_retry_after("0") == 0.0

    def test_parse_retry_after_http_date(self):
        from email.utils import format_datetime

        future = datetime.now(timezone.utc) + timedelta(seconds=60)
        result = error.parse_retry_after(format_datetime(future))
        assert result is not None
        assert 55 <= result <= 65

    def test_parse_retry_after_unparseable(self):
        assert error.parse_retry_after("banana") is None

    def test_parse_retry_after_empty(self):
        assert error.parse_retry_after("") is None

    def test_compute_sleep_server_value_used(self):
        assert error.compute_sleep_seconds(30.0, None, None) == 30.0

    def test_compute_sleep_default_fallback(self):
        assert error.compute_sleep_seconds(None, 5, None) == 5.0

    def test_compute_sleep_server_overrides_default(self):
        # Server-provided value takes priority over default
        assert error.compute_sleep_seconds(10.0, 5, None) == 10.0

    def test_compute_sleep_max_cap_applied(self):
        assert error.compute_sleep_seconds(3600.0, None, 60) == 60.0

    def test_compute_sleep_max_zero_returns_none(self):
        assert error.compute_sleep_seconds(30.0, None, 0) is None

    def test_compute_sleep_no_info_returns_none(self):
        assert error.compute_sleep_seconds(None, None, None) is None

    def test_compute_sleep_zero_seconds_returns_none(self):
        assert error.compute_sleep_seconds(0.0, None, None) is None

    def test_raise_if_rate_limited_429_no_header(self):
        with pytest.raises(error.RateLimitError) as exc_info:
            error.raise_if_rate_limited(429, "http://x/", None)
        assert exc_info.value.retry_after is None
        assert exc_info.value.retry_after_seconds is None

    def test_raise_if_rate_limited_429_with_header(self):
        with pytest.raises(error.RateLimitError) as exc_info:
            error.raise_if_rate_limited(429, "http://x/", "30")
        assert exc_info.value.retry_after == "30"
        assert exc_info.value.retry_after_seconds == 30.0

    def test_raise_if_rate_limited_503_with_header(self):
        with pytest.raises(error.RateLimitError):
            error.raise_if_rate_limited(503, "http://x/", "10")

    def test_raise_if_rate_limited_503_no_header_does_not_raise(self):
        # 503 without Retry-After should pass silently
        error.raise_if_rate_limited(503, "http://x/", None)

    def test_raise_if_rate_limited_200_does_not_raise(self):
        error.raise_if_rate_limited(200, "http://x/", None)


class TestRateLimiting:
    """
    Unit tests for 429/503 rate-limit handling (issue #627).
    No real server communication - uses mock.patch on the session.
    """

    def _make_response(self, status_code, headers=None):
        """Build a minimal mock HTTP response."""
        r = mock.MagicMock()
        r.status_code = status_code
        r.headers = headers or {}
        r.reason = "Too Many Requests" if status_code == 429 else "Service Unavailable"
        return r

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_429_no_retry_after_raises(self, mocked):
        """429 without Retry-After header always raises RateLimitError with retry_after_seconds=None."""
        mocked.return_value = self._make_response(429)
        client = DAVClient(url="http://cal.example.com/")
        with pytest.raises(error.RateLimitError) as exc_info:
            client.request("/")
        assert exc_info.value.retry_after is None
        assert exc_info.value.retry_after_seconds is None

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_429_with_integer_retry_after(self, mocked):
        """429 with integer Retry-After header parses the seconds correctly."""
        mocked.return_value = self._make_response(429, {"Retry-After": "30"})
        client = DAVClient(url="http://cal.example.com/")
        with pytest.raises(error.RateLimitError) as exc_info:
            client.request("/")
        assert exc_info.value.retry_after == "30"
        assert exc_info.value.retry_after_seconds == 30

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_429_with_http_date_retry_after(self, mocked):
        """429 with HTTP-date Retry-After header computes seconds from now."""
        from email.utils import format_datetime

        future = datetime.now(timezone.utc) + timedelta(seconds=60)
        retry_after_str = format_datetime(future)
        mocked.return_value = self._make_response(429, {"Retry-After": retry_after_str})
        client = DAVClient(url="http://cal.example.com/")
        with pytest.raises(error.RateLimitError) as exc_info:
            client.request("/")
        assert exc_info.value.retry_after == retry_after_str
        # Should be close to 60s (allow a few seconds tolerance)
        assert exc_info.value.retry_after_seconds is not None
        assert 55 <= exc_info.value.retry_after_seconds <= 65

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_429_with_unparseable_retry_after(self, mocked):
        """429 with a garbled Retry-After header still raises; retry_after_seconds is None."""
        mocked.return_value = self._make_response(429, {"Retry-After": "banana"})
        client = DAVClient(url="http://cal.example.com/")
        with pytest.raises(error.RateLimitError) as exc_info:
            client.request("/")
        assert exc_info.value.retry_after == "banana"
        assert exc_info.value.retry_after_seconds is None

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_503_without_retry_after_does_not_raise_rate_limit(self, mocked):
        """503 without Retry-After falls through as a normal (non-rate-limit) response."""
        mocked.return_value = self._make_response(503)
        client = DAVClient(url="http://cal.example.com/")
        # Should NOT raise RateLimitError; returns a DAVResponse with status 503
        response = client.request("/")
        assert response.status == 503

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_503_with_retry_after_raises(self, mocked):
        """503 with Retry-After header raises RateLimitError."""
        mocked.return_value = self._make_response(503, {"Retry-After": "10"})
        client = DAVClient(url="http://cal.example.com/")
        with pytest.raises(error.RateLimitError) as exc_info:
            client.request("/")
        assert exc_info.value.retry_after_seconds == 10

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_rate_limit_handle_sleeps_and_retries(self, mocked):
        """With rate_limit_handle=True the client sleeps then retries, returning the second response."""
        ok_response = mock.MagicMock()
        ok_response.status_code = 200
        ok_response.headers = {}
        mocked.side_effect = [
            self._make_response(429, {"Retry-After": "5"}),
            ok_response,
        ]
        client = DAVClient(url="http://cal.example.com/", rate_limit_handle=True)
        with mock.patch("caldav.davclient.time.sleep") as mock_sleep:
            response = client.request("/")
        mock_sleep.assert_called_once_with(5)
        assert response.status == 200
        assert mocked.call_count == 2

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_rate_limit_handle_default_sleep_used_when_no_retry_after(self, mocked):
        """With rate_limit_default_sleep set, that value is used when server omits Retry-After."""
        ok_response = mock.MagicMock()
        ok_response.status_code = 200
        ok_response.headers = {}
        mocked.side_effect = [
            self._make_response(429),
            ok_response,
        ]
        client = DAVClient(
            url="http://cal.example.com/", rate_limit_handle=True, rate_limit_default_sleep=3
        )
        with mock.patch("caldav.davclient.time.sleep") as mock_sleep:
            response = client.request("/")
        mock_sleep.assert_called_once_with(3)
        assert response.status == 200

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_rate_limit_handle_no_sleep_info_raises(self, mocked):
        """rate_limit_handle=True but no Retry-After and no default sleep re-raises RateLimitError."""
        mocked.return_value = self._make_response(429)
        client = DAVClient(url="http://cal.example.com/", rate_limit_handle=True)
        with pytest.raises(error.RateLimitError):
            client.request("/")

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_rate_limit_max_sleep_caps_sleep_time(self, mocked):
        """rate_limit_max_sleep caps the sleep even when server requests longer."""
        ok_response = mock.MagicMock()
        ok_response.status_code = 200
        ok_response.headers = {}
        mocked.side_effect = [
            self._make_response(429, {"Retry-After": "3600"}),
            ok_response,
        ]
        client = DAVClient(
            url="http://cal.example.com/", rate_limit_handle=True, rate_limit_max_sleep=60
        )
        with mock.patch("caldav.davclient.time.sleep") as mock_sleep:
            client.request("/")
        mock_sleep.assert_called_once_with(60)

    @mock.patch("caldav.davclient.requests.Session.request")
    def test_rate_limit_max_sleep_zero_raises(self, mocked):
        """rate_limit_max_sleep=0 means never sleep, always raise."""
        mocked.return_value = self._make_response(429, {"Retry-After": "30"})
        client = DAVClient(
            url="http://cal.example.com/", rate_limit_handle=True, rate_limit_max_sleep=0
        )
        with pytest.raises(error.RateLimitError):
            client.request("/")
