#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from datetime import datetime
import urlparse
from nose.tools import assert_equal, assert_not_equal

from conf import principal_url, principal_url_ssl, proxy, proxy_noport

from caldav.davclient import DAVClient
from caldav.objects import Principal, Calendar, Event, DAVObject
from caldav.lib import url
from caldav.lib.namespace import ns
from caldav.elements import dav, cdav


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
        p = Principal(c, principal_url_ssl)
        assert_not_equal(len(p.calendars()), 0)

    def testProxy(self):
        c = DAVClient(principal_url, proxy)
        p = Principal(c, principal_url)
        assert_not_equal(len(p.calendars()), 0)

        c = DAVClient(principal_url, proxy_noport)
        p = Principal(c, principal_url)
        assert_not_equal(len(p.calendars()), 0)

    def testPrincipal(self):
        assert_equal(url.make(self.principal.url), principal_url)

        collections = self.principal.calendars()
        for c in collections:
            assert_equal(c.__class__.__name__, "Calendar")

    def testCalendar(self):
        c = Calendar(self.caldav, name="Yep", parent = self.principal,
                     id = testcal_id).save()
        assert_not_equal(c.url, None)
        # TODO: fail
        #props = c.get_properties([dav.DisplayName(),])
        #assert_equal("Yep", props[dav.DisplayName.tag])

        c.set_properties([dav.DisplayName("hooray"),])
        props = c.get_properties([dav.DisplayName(),])
        assert_equal(props[dav.DisplayName.tag], "hooray")
        print c

        cc = Calendar(self.caldav, name="Yep", parent = self.principal).save()
        assert_not_equal(cc.url, None)
        cc.delete()

        e = Event(self.caldav, data = ev1, parent = c).save()
        assert_not_equal(e.url, None)
        print e, e.data

        ee = Event(self.caldav, url = url.make(e.url), parent = c)
        ee.load()
        assert_equal(e.instance.vevent.uid, ee.instance.vevent.uid)

        r = c.date_search(datetime(2006,7,13,17,00,00),
                          datetime(2006,7,15,17,00,00))
        assert_equal(e.instance.vevent.uid, r[0].instance.vevent.uid)
        for e in r: print e.data
        assert_equal(len(r), 1)

        all = c.events()
        print all
        assert_equal(len(all), 1)

        e2 = Event(self.caldav, data = ev2, parent = c).save()
        assert_not_equal(e.url, None)

        tmp = c.event("20010712T182145Z-123401@example.com")
        assert_equal(e2.instance.vevent.uid, tmp.instance.vevent.uid)

        r = c.date_search(datetime(2006,7,13,17,00,00),
                          datetime(2006,7,15,17,00,00))
        for e in r: print e.data
        assert_equal(len(r), 1)

        e.data = ev2
        e.save()

        r = c.date_search(datetime(2006,7,13,17,00,00),
                          datetime(2006,7,15,17,00,00))
        for e in r: print e.data
        assert_equal(len(r), 1)

        e.instance = e2.instance
        e.save()
        r = c.date_search(datetime(2006,7,13,17,00,00),
                          datetime(2006,7,15,17,00,00))
        for e in r: print e.data
        assert_equal(len(r), 1)


    def testFilters(self):
        filter = cdav.Filter()\
                    .append(cdav.CompFilter("VCALENDAR")\
                    .append(cdav.CompFilter("VEVENT")\
                    .append(cdav.PropFilter("UID")\
                    .append([cdav.TextMatch("pouet", negate = True)]))))
        print filter

        crash = cdav.CompFilter()
        value = None
        try:
            value = str(crash)
        except:
            pass
        if value is not None:
            raise Exception("This should have crashed")

    def testObjects(self):
        o = DAVObject(self.caldav)
        failed = False
        try:
            o.save()
        except:
            failed = True
        assert_equal(failed, True)

