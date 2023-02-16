#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
Rule: None of the tests in this file should initiate any internet
communication, and there should be no dependencies on a working caldav
server for the tests in this file.  We use the Mock class when needed
to emulate server communication.
"""
import pickle
from datetime import date
from datetime import datetime
from datetime import timedelta

import caldav
import icalendar
import lxml.etree
import pytest
import vobject
from caldav.davclient import DAVClient
from caldav.davclient import DAVResponse
from caldav.elements import cdav
from caldav.elements import dav
from caldav.elements import ical
from caldav.lib import error
from caldav.lib import url
from caldav.lib.python_utilities import to_normal_str
from caldav.lib.python_utilities import to_wire
from caldav.lib.url import URL
from caldav.objects import Calendar
from caldav.objects import CalendarObjectResource
from caldav.objects import CalendarSet
from caldav.objects import DAVObject
from caldav.objects import Event
from caldav.objects import FreeBusy
from caldav.objects import Journal
from caldav.objects import Principal
from caldav.objects import Todo
from six import PY3


if PY3:
    from urllib.parse import urlparse
    from unittest import mock
else:
    from urlparse import urlparse
    import mock

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


def MockedDAVResponse(text):
    """
    For unit testing - a mocked DAVResponse with some specific content
    """
    resp = mock.MagicMock()
    resp.status_code = 207
    resp.reason = "multistatus"
    resp.headers = {}
    resp.content = text
    return DAVResponse(resp)


def MockedDAVClient(xml_returned):
    """
    For unit testing - a mocked DAVClient returning some specific content every time
    a request is performed
    """
    client = DAVClient(url="https://somwhere.in.the.universe.example/some/caldav/root")
    client.request = mock.MagicMock(return_value=MockedDAVResponse(xml_returned))
    return client


class TestExpandRRule:
    """
    Tests the expand_rrule method
    """

    def setup_method(self):
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        self.yearly = Event(client, data=evr)
        self.todo = Todo(client, data=todo6)

    def testZero(self):
        ## evr has rrule yearly and dtstart DTSTART 1997-11-02
        ## This should cause 0 recurrences:
        self.yearly.expand_rrule(start=datetime(1998, 4, 4), end=datetime(1998, 10, 10))
        assert len(self.yearly.icalendar_instance.subcomponents) == 0

    def testOne(self):
        self.yearly.expand_rrule(
            start=datetime(1998, 10, 10), end=datetime(1998, 12, 12)
        )
        assert len(self.yearly.icalendar_instance.subcomponents) == 1
        assert not "RRULE" in self.yearly.icalendar_component
        assert "UID" in self.yearly.icalendar_component
        assert "RECURRENCE-ID" in self.yearly.icalendar_component

    def testThree(self):
        self.yearly.expand_rrule(
            start=datetime(1996, 10, 10), end=datetime(1999, 12, 12)
        )
        assert len(self.yearly.icalendar_instance.subcomponents) == 3
        data1 = self.yearly.icalendar_instance.subcomponents[0].to_ical()
        data2 = self.yearly.icalendar_instance.subcomponents[1].to_ical()
        assert data1.replace(b"199711", b"199811") == data2

    def testThreeTodo(self):
        self.todo.expand_rrule(start=datetime(1996, 10, 10), end=datetime(1999, 12, 12))
        assert len(self.todo.icalendar_instance.subcomponents) == 3
        data1 = self.todo.icalendar_instance.subcomponents[0].to_ical()
        data2 = self.todo.icalendar_instance.subcomponents[1].to_ical()
        assert data1.replace(b"19970", b"19980") == data2

    def testSplit(self):
        self.yearly.expand_rrule(
            start=datetime(1996, 10, 10), end=datetime(1999, 12, 12)
        )
        events = self.yearly.split_expanded()
        assert len(events) == 3
        assert len(events[0].icalendar_instance.subcomponents) == 1
        assert (
            events[1].icalendar_component["UID"]
            == "19970901T130000Z-123403@example.com"
        )

    def test241(self):
        """
        Ref https://github.com/python-caldav/caldav/issues/241

        This seems like sort of a duplicate of testThreeTodo, but the ftests actually started failing
        """
        assert len(self.todo.data) > 128
        self.todo.expand_rrule(
            start=datetime(1997, 4, 14, 0, 0), end=datetime(2015, 5, 14, 0, 0)
        )
        assert len(self.todo.data) > 128


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

        if PY3:
            response = client.put(
                "/foo/møøh/bar".encode("utf-8"),
                "bringebærsyltetøy 北京 пиво".encode("utf-8"),
                {},
            )
        else:
            response = client.put(u"/foo/møøh/bar", "bringebærsyltetøy 北京 пиво", {})  # fmt: skip
        assert response.status == 200
        assert response.tree is None

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
        assert bernards_calendars.url == URL(
            "http://cal.example.com/home/bernard/calendars/"
        )

    @mock.patch("caldav.CalendarObjectResource.is_loaded")
    def testDateSearch(self, mocked):
        """
        ## ref https://github.com/python-caldav/caldav/issues/133
        """
        mocked.__bool__ = lambda self: True
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
        calendar = Calendar(
            client, url="/principals/calendar/home@petroski.example.com/963/"
        )
        results = calendar.date_search(
            datetime(2021, 2, 1), datetime(2021, 2, 7), expand=False
        )
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
        assert len(calendar.events()) == 0

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
        assert len(calendar_home_set.calendars()) == 1

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
        expected_result = {
            "/": {"{DAV:}current-user-principal": "/17149682/principal/"}
        }

        assert (
            MockedDAVResponse(xml).expand_simple_props(
                props=[dav.CurrentUserPrincipal()]
            )
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
            "/principals/users/frank/": {
                "{DAV:}current-user-principal": "/principals/users/frank/"
            }
        }
        assert (
            MockedDAVResponse(xml).expand_simple_props(
                props=[dav.CurrentUserPrincipal()]
            )
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
        expected_result = {
            "/": {"{DAV:}current-user-principal": "/17149682/principal/"}
        }
        assert (
            MockedDAVResponse(xml).expand_simple_props(
                props=[dav.CurrentUserPrincipal()]
            )
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
        lines_orig = (
            ev1.replace("Bastille Day Party", "yet another summary").strip().split("\n")
        )
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
        lines_orig = (
            ev1.replace("Bastille Day Party", "yet another summary").strip().split("\n")
        )
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

    def testTodoDuration(self):
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        my_todo1 = Todo(client, data=todo)
        my_todo2 = Todo(client, data=todo_implicit_duration)
        my_todo3 = Todo(client, data=todo_explicit_duration)
        assert my_todo1.get_duration() == timedelta(0)
        assert my_todo1.get_due() == date(2007, 5, 1)
        assert my_todo2.get_duration() == timedelta(days=6)
        assert my_todo2.get_due() == date(2007, 5, 1)
        assert my_todo3.get_duration() == timedelta(days=5)
        foo6 = my_todo3.get_due().strftime("%s") == "1177945200"
        some_date = date(2011, 1, 1)

        my_todo1.set_due(some_date)
        assert my_todo1.get_due() == some_date

        ## set_due has "only" one if, so two code paths, one where dtstart is actually moved and one where it isn't
        my_todo2.set_due(some_date, move_dtstart=True)
        assert my_todo2.icalendar_instance.subcomponents[0][
            "DTSTART"
        ].dt == some_date - timedelta(days=6)

        ## set_duration at the other hand has 5 code paths ...
        ## 1) DUE and DTSTART set, DTSTART as the movable component
        my_todo1.set_duration(timedelta(1))
        assert my_todo1.get_due() == some_date
        assert my_todo1.icalendar_instance.subcomponents[0][
            "DTSTART"
        ].dt == some_date - timedelta(1)

        ## 2) DUE and DTSTART set, DUE as the movable component
        my_todo1.set_duration(timedelta(2), movable_attr="DUE")
        assert my_todo1.get_due() == some_date + timedelta(days=1)
        assert my_todo1.icalendar_instance.subcomponents[0][
            "DTSTART"
        ].dt == some_date - timedelta(1)

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
        assert (
            urlA == "http://foo:bar@www.example.com:8080/caldav.php/someuser/calendar"
        )
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
        assert (
            urlA == "http://foo:bar@www.example.com:8080/caldav.php/someuser/calendar"
        )
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
                    cdav.PropFilter("UID").append(
                        [cdav.TextMatch("pouet", negate=True)]
                    )
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
        for (ical, class_) in (
            (ev1, Event),
            (todo, Todo),
            (journal, Journal),
            (None, CalendarObjectResource),
            ("random rantings", CalendarObjectResource),
        ):  ## TODO: freebusy, time zone
            assert calendar._calendar_comp_class_by_data(ical) == class_
            if ical != "random rantings" and ical:
                assert (
                    calendar._calendar_comp_class_by_data(
                        icalendar.Calendar.from_ical(ical)
                    )
                    == class_
                )

    def testContextManager(self):
        """
        ref https://github.com/python-caldav/caldav/pull/175
        """
        cal_url = "http://me:hunter2@calendar.example:80/"
        with DAVClient(url=cal_url) as client_ctx_mgr:
            assert isinstance(client_ctx_mgr, DAVClient)
