#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""
Rule: None of the tests in this file should initiate any internet
communication, and there should be no dependencies on a working caldav
server for the tests in this file.  We use the Mock class when needed
to emulate server communication.

"""

from six import PY3
from nose.tools import assert_equal, assert_not_equal, assert_raises, assert_true
import caldav
from caldav.davclient import DAVClient, DAVResponse
from caldav.objects import (Principal, Calendar, Journal, Event, DAVObject,
                            CalendarSet, FreeBusy, Todo, CalendarObjectResource)
from caldav.lib.url import URL
from caldav.lib import url, error, vcal
from caldav.elements import dav, cdav, ical
from caldav.lib.python_utilities import to_local, to_str
import vobject, icalendar
from datetime import datetime


if PY3:
    from urllib.parse import urlparse
    from unittest import mock
else:
    from urlparse import urlparse
    import mock

## Some example icalendar data copied from test_caldav.py
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

journal = """
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VJOURNAL
UID:19970901T130000Z-123405@example.com
DTSTAMP:19970901T130000Z
DTSTART;VALUE=DATE:19970317
SUMMARY:Staff meeting minutes
DESCRIPTION:1. Staff meeting: Participants include Joe\, Lisa
  and Bob. Aurora project plans were reviewed. There is currently
  no budget reserves for this project. Lisa will escalate to
  management. Next meeting on Tuesday.\n
END:VJOURNAL
END:VCALENDAR
"""


def MockedDAVResponse(text):
    """
    For unit testing - a mocked DAVResponse with some specific content
    """
    resp = mock.MagicMock()
    resp.status_code = 207
    resp.reason = 'multistatus'
    resp.headers = {}
    resp.content = text
    return DAVResponse(resp)

def MockedDAVClient(xml_returned):
    """
    For unit testing - a mocked DAVClient returning some specific content every time
    a request is performed
    """
    client = DAVClient(url='https://somwhere.in.the.universe.example/some/caldav/root')
    client.request = mock.MagicMock(return_value=MockedDAVResponse(xml_returned))
    return client


class TestCalDAV:
    """
    Test class for "pure" unit tests (small internal tests, testing that
    a small unit of code works as expected, without any third party
    dependencies, without accessing any caldav server)
    """
    @mock.patch('caldav.davclient.requests.Session.request')
    def testRequestNonAscii(self, mocked):
        """
        ref https://github.com/python-caldav/caldav/issues/83
        """
        mocked().status_code=200
        mocked().headers = {}
        cal_url = "http://me:hunter2@calendar.møøh.example:80/"
        client = DAVClient(url=cal_url)
        response = client.put('/foo/møøh/bar', 'bringebærsyltetøy 北京 пиво', {})
        assert_equal(response.status, 200)
        assert(response.tree is None)

        if PY3:
            response = client.put('/foo/møøh/bar'.encode('utf-8'), 'bringebærsyltetøy 北京 пиво'.encode('utf-8'), {})
        else:
            response = client.put(u'/foo/møøh/bar', u'bringebærsyltetøy 北京 пиво', {})
        assert_equal(response.status, 200)
        assert(response.tree is None)

    def testPathWithEscapedCharacters(self):
        xml=b"""<D:multistatus xmlns:D="DAV:" xmlns:caldav="urn:ietf:params:xml:ns:caldav" xmlns:cs="http://calendarserver.org/ns/" xmlns:ical="http://apple.com/ns/ical/">
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
        assert_equal(client.calendar(url="https://somwhere.in.the.universe.example/some/caldav/root/133bahgr6ohlo9ungq0it45vf8%40group.calendar.google.com/events/").get_supported_components(), ['VEVENT'])

    def testAbsoluteURL(self):
        """Version 0.7.0 does not handle responses with absolute URLs very well, ref https://github.com/python-caldav/caldav/pull/103"""
        ## none of this should initiate any communication
        client = DAVClient(url='http://cal.example.com/')
        principal = Principal(client=client, url='http://cal.example.com/home/bernard/')
        ## now, ask for the calendar_home_set, but first we need to mock up client.propfind
        mocked_response = mock.MagicMock()
        mocked_response.status_code = 207
        mocked_response.reason = 'multistatus'
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
        assert_equal(bernards_calendars.url, URL('http://cal.example.com/home/bernard/calendars/'))

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
        calendar = Calendar(client, url='/principals/calendar/home@petroski.example.com/963/')
        results = calendar.date_search(datetime(2021, 2, 1),datetime(2021, 2,7))
        assert_equal(len(results), 3)

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
        assert(isinstance(principal.calendar_home_set, CalendarSet))
        calendar1 = principal.calendar(name="foo", cal_id="bar")
        calendar2 = principal.calendar_home_set.calendar(
            name="foo", cal_id="bar")
        calendar3 = principal.calendar(cal_id="bar")
        assert_equal(calendar1.url, calendar2.url)
        assert_equal(calendar1.url, calendar3.url)
        assert_equal(
            calendar1.url, "http://calendar.example:80/me/calendars/bar/")

        # principal.calendar_home_set can also be set to an object
        # This should be noop
        principal.calendar_home_set = principal.calendar_home_set
        calendar1 = principal.calendar(name="foo", cal_id="bar")
        assert_equal(calendar1.url, calendar2.url)

        # When building a calendar from a relative URL and a client,
        # the relative URL should be appended to the base URL in the client
        calendar1 = Calendar(client, 'someoneelse/calendars/main_calendar')
        calendar2 = Calendar(client,
            'http://me:hunter2@calendar.example:80/someoneelse/calendars/main_calendar')
        assert_equal(calendar1.url, calendar2.url)

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
        calendar = Calendar(client, url='/17149682/calendars/testcalendar-485d002e-31b9-4147-a334-1d71503a4e2c/')
        assert_equal(len(calendar.events()), 0)

    def test_get_calendars(self):
        xml="""
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
        client=MockedDAVClient(xml)
        calendar_home_set = CalendarSet(client, url='/dav/tobias%40redpill-linpro.com/')
        assert_equal(len(calendar_home_set.calendars()), 1)

        def test_supported_components(self):
            xml="""
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
            assert_equal(Calendar(client=client, url="/17149682/calendars/testcalendar-0da571c7-139c-479a-9407-8ce9ed20146d/").get_supported_components(), ['VEVENT']);

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
        expected_result = {'/':
                            {'{DAV:}current-user-principal': '/17149682/principal/'}}
        
        assert_equal(MockedDAVResponse(xml).expand_simple_props(props=[dav.CurrentUserPrincipal()]),
                     expected_result)

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
        expected_result = {'/principals/users/frank/': {'{DAV:}current-user-principal': '/principals/users/frank/'}}
        assert_equal(MockedDAVResponse(xml).expand_simple_props(props=[dav.CurrentUserPrincipal()]),
                     expected_result)

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
        expected_result = {'/17149682/principal/':
                           {'{urn:ietf:params:xml:ns:caldav}calendar-home-set': 'https://p62-caldav.icloud.com:443/17149682/calendars/'}}
        assert_equal(MockedDAVResponse(xml).expand_simple_props(props=[cdav.CalendarHomeSet()]),
                     expected_result)

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
        expected_result = {'/': {'{DAV:}current-user-principal': '/17149682/principal/'}}
        assert_equal(MockedDAVResponse(xml).expand_simple_props(props=[dav.CurrentUserPrincipal()]),
                     expected_result)

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
        expected_result = {'/17149682/calendars/testcalendar-84439d0b-ce46-4416-b978-7b4009122c64/': {'{urn:ietf:params:xml:ns:caldav}calendar-data': None}, '/17149682/calendars/testcalendar-84439d0b-ce46-4416-b978-7b4009122c64/20010712T182145Z-123401@example.com.ics': {'{urn:ietf:params:xml:ns:caldav}calendar-data': 'BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Example Corp.//CalDAV Client//EN\nBEGIN:VEVENT\nUID:20010712T182145Z-123401@example.com\nDTSTAMP:20060712T182145Z\nDTSTART:20060714T170000Z\nDTEND:20060715T040000Z\nSUMMARY:Bastille Day Party\nEND:VEVENT\nEND:VCALENDAR\n'}}
        assert_equal(MockedDAVResponse(xml).expand_simple_props(props=[cdav.CalendarData()]),
                     expected_result)

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
            '/17149682/calendars/': {
                '{DAV:}resourcetype': ['{DAV:}collection'],
                '{DAV:}displayname': 'Ny Test'},
            '/17149682/calendars/06888b87-397f-11eb-943b-3af9d3928d42/':  {
                '{DAV:}resourcetype': ['{DAV:}collection', '{urn:ietf:params:xml:ns:caldav}calendar'],
                '{DAV:}displayname': 'calfoo3'},
            '/17149682/calendars/inbox/': {
                '{DAV:}resourcetype': ['{DAV:}collection', '{urn:ietf:params:xml:ns:caldav}schedule-inbox'],
                '{DAV:}displayname': None}, 
            '/17149682/calendars/testcalendar-e2910e0a-feab-4b51-b3a8-55828acaa912/': {
                '{DAV:}resourcetype': ['{DAV:}collection', '{urn:ietf:params:xml:ns:caldav}calendar'],
                '{DAV:}displayname': 'Yep'}}
        assert_equal(MockedDAVResponse(xml).expand_simple_props(props=[dav.DisplayName()], multi_value_props=[dav.ResourceType()]),
                     expected_result)
    
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
            '/17149682/calendars/testcalendar-f96b3bf0-09e1-4f3d-b891-3a25c99a2894/': {
                '{DAV:}getetag': '"kkkgopik"',
                '{urn:ietf:params:xml:ns:caldav}calendar-data': None},
            '/17149682/calendars/testcalendar-f96b3bf0-09e1-4f3d-b891-3a25c99a2894/1761bf8c-6363-11eb-8fe4-74e5f9bfd8c1.ics': {
                '{DAV:}getetag': '"kkkgorwx"',
                '{urn:ietf:params:xml:ns:caldav}calendar-data': None},
            '/17149682/calendars/testcalendar-f96b3bf0-09e1-4f3d-b891-3a25c99a2894/20010712T182145Z-123401@example.com.ics': {
                '{DAV:}getetag': '"kkkgoqqu"',
                '{urn:ietf:params:xml:ns:caldav}calendar-data': None}
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
        assert_raises(error.DAVError, calhome._query, query_method='unknown_method')

    def testDefaultClient(self):
        """When no client is given to a DAVObject, but the parent is given,
        parent.client will be used"""
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        calhome = CalendarSet(client, cal_url + "me/")
        calendar = Calendar(parent=calhome)
        assert_equal(calendar.client, calhome.client)

    def testInstance(self):
        cal_url = "http://me:hunter2@calendar.example:80/"
        client = DAVClient(url=cal_url)
        my_event = Event(client, data=ev1)
        my_event.vobject_instance.vevent.summary.value='new summary'
        assert('new summary' in my_event.data)
        icalobj = my_event.icalendar_instance
        icalobj.subcomponents[0]['SUMMARY']='yet another summary'
        assert_equal(my_event.vobject_instance.vevent.summary.value, 'yet another summary')
        ## Now the data has been converted from string to vobject to string to icalendar to string to vobject and ... will the string still match the original?
        lines_now = my_event.data.split('\r\n')
        lines_orig = ev1.replace('Bastille Day Party', 'yet another summary').split('\n')
        lines_now.sort()
        lines_orig.sort()
        assert_equal(lines_now, lines_orig)

    def testURL(self):
        """Exercising the URL class"""
        long_url = "http://foo:bar@www.example.com:8080/caldav.php/?foo=bar"

        # 1) URL.objectify should return a valid URL object almost no matter
        # what's thrown in
        url0 = URL.objectify(None)
        url0b= URL.objectify("")
        url1 = URL.objectify(long_url)
        url2 = URL.objectify(url1)
        url3 = URL.objectify("/bar")
        url4 = URL.objectify(urlparse(str(url1)))
        url5 = URL.objectify(urlparse("/bar"))

        # 2) __eq__ works well
        assert_equal(url1, url2)
        assert_equal(url1, url4)
        assert_equal(url3, url5)

        # 3) str will always return the URL
        assert_equal(str(url1), long_url)
        assert_equal(str(url3), "/bar")
        assert_equal(str(url4), long_url)
        assert_equal(str(url5), "/bar")

        ## 3b) repr should also be exercised.  Returns URL(/bar) now.
        assert("/bar" in repr(url5))
        assert("URL" in repr(url5))
        assert(len(repr(url5)) < 12)

        # 4) join method
        url6 = url1.join(url2)
        url7 = url1.join(url3)
        url8 = url1.join(url4)
        url9 = url1.join(url5)
        urlA = url1.join("someuser/calendar")
        urlB = url5.join(url1)
        assert_equal(url6, url1)
        assert_equal(url7, "http://foo:bar@www.example.com:8080/bar")
        assert_equal(url8, url1)
        assert_equal(url9, url7)
        assert_equal(urlA, "http://foo:bar@www.example.com:8080/caldav.php/someuser/calendar")
        assert_equal(urlB, url1)
        assert_raises(ValueError, url1.join, "http://www.google.com")

        # 4b) join method, with URL as input parameter
        url6 = url1.join(URL.objectify(url2))
        url7 = url1.join(URL.objectify(url3))
        url8 = url1.join(URL.objectify(url4))
        url9 = url1.join(URL.objectify(url5))
        urlA = url1.join(URL.objectify("someuser/calendar"))
        urlB = url5.join(URL.objectify(url1))
        url6b= url6.join(url0)
        url6c= url6.join(url0b)
        url6d= url6.join(None)
        for url6alt in (url6b, url6c, url6d):
            assert_equal(url6, url6alt)
        assert_equal(url6, url1)
        assert_equal(url7, "http://foo:bar@www.example.com:8080/bar")
        assert_equal(url8, url1)
        assert_equal(url9, url7)
        assert_equal(urlA, "http://foo:bar@www.example.com:8080/caldav.php/someuser/calendar")
        assert_equal(urlB, url1)
        assert_raises(ValueError, url1.join, "http://www.google.com")

        # 5) all urlparse methods will work.  always.
        assert_equal(url1.scheme, 'http')
        assert_equal(url2.path, '/caldav.php/')
        assert_equal(url7.username, 'foo')
        assert_equal(url5.path, '/bar')
        urlC = URL.objectify("https://www.example.com:443/foo")
        assert_equal(urlC.port, 443)

        # 6) is_auth returns True if the URL contains a username.
        assert_equal(urlC.is_auth(), False)
        assert_equal(url7.is_auth(), True)

        # 7) unauth() strips username/password
        assert_equal(url7.unauth(), 'http://www.example.com:8080/bar')

        # 8) strip_trailing_slash
        assert_equal(URL('http://www.example.com:8080/bar/').strip_trailing_slash(), URL('http://www.example.com:8080/bar'))
        assert_equal(URL('http://www.example.com:8080/bar/').strip_trailing_slash(), URL('http://www.example.com:8080/bar').strip_trailing_slash())

        # 9) canonical
        assert_equal(URL('https://www.example.com:443/b%61r/').canonical(), URL('//www.example.com/bar/').canonical())

    def testFilters(self):
        filter = \
            cdav.Filter().append(
                cdav.CompFilter("VCALENDAR").append(
                    cdav.CompFilter("VEVENT").append(
                        cdav.PropFilter("UID").append(
                            [cdav.TextMatch("pouet", negate=True)]))))
        # print(filter)

        crash = cdav.CompFilter()
        value = None
        try:
            value = str(crash)
        except:
            pass
        if value is not None:
            raise Exception("This should have crashed")

    def test_vcal_fixups(self):
        """
        There is an obscure function lib.vcal that attempts to fix up
        known ical standard breaches from various calendar servers.
        """
        broken_ical=[
            ## This first one contains duplicated DTSTART in the event data
            """BEGIN:VCALENDAR
X-EXPANDED:True
X-MASTER-DTSTART:20200517T060000Z
X-MASTER-RRULE:FREQ=YEARLY
BEGIN:VEVENT
DTSTAMP:20210205T101751Z
UID:20200516T060000Z-123401@example.com
DTSTAMP:20200516T060000Z
SUMMARY:Do the needful
DTSTART:20210517T060000Z
DTEND:20210517T230000Z
RECURRENCE-ID:20210517T060000Z
END:VEVENT
BEGIN:VEVENT
DTSTAMP:20210205T101751Z
UID:20200516T060000Z-123401@example.com
DTSTAMP:20200516T060000Z
SUMMARY:Do the needful
DTSTART:20220517T060000Z
DTEND:20220517T230000Z
RECURRENCE-ID:20220517T060000Z
END:VEVENT
BEGIN:VEVENT
DTSTAMP:20210205T101751Z
UID:20200516T060000Z-123401@example.com
DTSTAMP:20200516T060000Z
SUMMARY:Do the needful
DTSTART:20230517T060000Z
DTEND:20230517T230000Z
RECURRENCE-ID:20230517T060000Z
END:VEVENT
END:VCALENDAR"""] ## todo: add more broken ical here

        for ical in broken_ical:
            ## This should raise error
            assert_raises(vobject.base.ValidateError, vobject.readOne(ical).serialize)
            ## This should not raise error
            vobject.readOne(vcal.fix(ical)).serialize()

    def test_calendar_comp_class_by_data(self):
        calendar=Calendar()
        for (ical,class_) in ((ev1, Event), (todo, Todo), (journal, Journal), (None, CalendarObjectResource), ("random rantings", CalendarObjectResource)): ## TODO: freebusy, time zone
            assert_equal(
                calendar._calendar_comp_class_by_data(ical),
                class_)
            if (ical != "random rantings" and ical):
                assert_equal(
                    calendar._calendar_comp_class_by_data(icalendar.Calendar.from_ical(ical)),
                    class_)

    def testContextManager(self):
        """
        ref https://github.com/python-caldav/caldav/pull/175
        """
        cal_url = "http://me:hunter2@calendar.example:80/"
        with DAVClient(url=cal_url) as client_ctx_mgr:
            assert_true(isinstance(client_ctx_mgr, DAVClient))
