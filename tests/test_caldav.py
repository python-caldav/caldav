#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from nose.tools import assert_equal, assert_not_equal

from conf import principal_url, principal_url_ssl

from caldav.davclient import DAVClient
from caldav.objects import Principal, Calendar, Event
from caldav.utils import url


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

ev2 = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:20010712T182145Z-123401@example.com
DTSTAMP:20070712T182145Z
DTSTART:20070714T170000Z
DTEND:20070715T040000Z
SUMMARY:Bastille Day Party +1year
END:VEVENT
END:VCALENDAR
"""

testcal_id = "pythoncaldav-test"


class TestCalDAV:
    def setup(self):
        self.caldav = DAVClient(principal_url)
        self.principal = Principal(self.caldav, principal_url)

    def teardown(self):
        p = url.make(self.principal.url)
        path = url.join(p, testcal_id)

        cal = Calendar(self.caldav, name="Yep", parent = self.principal, 
                       url = path)
        cal.delete()

    def testSSL(self):
        c = DAVClient(principal_url_ssl)

    def testPrincipal(self):
        assert_equal(url.make(self.principal.url), principal_url)

        collections = self.principal.calendars()
        for c in collections:
            assert_equal(c.__class__.__name__, "Calendar")

    def testCalendar(self):
        c = Calendar(self.caldav, name="Yep", parent = self.principal, 
                     id = testcal_id).save()
        assert_not_equal(c.url, None)
        print c
        # TODO: fail
        #props = c.properties([ns("D", "displayname"),])
        #assert_equal("Yep", props["{DAV:}displayname"])

        e = Event(self.caldav, data = ev1, parent = c).save()
        assert_not_equal(e.url, None)
        print e

        ee = Event(self.caldav, url = url.make(e.url), parent = c)
        ee.load()
        assert_equal(e.instance.vevent.uid, ee.instance.vevent.uid)

        r = c.date_search("20060713T170000Z", "20060715T170000Z")
        assert_equal(e.instance.vevent.uid, r[0].instance.vevent.uid)
        print r
        assert_equal(len(r), 1)

        all = c.events()
        assert_equal(len(all), 1)

        e2 = Event(self.caldav, data = ev2, parent = c).save()
        assert_not_equal(e.url, None)

        r = c.date_search("20060713T170000Z", "20060715T170000Z")
        assert_equal(len(r), 1)

        e.update(ev2)
        e.save()

        r = c.date_search("20060713T170000Z", "20060715T170000Z")
        assert_equal(len(r), 0)
