#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from datetime import datetime
import urlparse
import logging
import threading
import time
from nose.tools import assert_equal, assert_not_equal, assert_raises

from conf import caldav_servers, proxy, proxy_noport
from proxy import ProxyHandler, NonThreadingHTTPServer

from caldav.davclient import DAVClient
from caldav.objects import Principal, Calendar, Event, DAVObject, CalendarSet
from caldav.lib.url import URL
from caldav.lib import error
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
testcal_id2 = "pythoncaldav-test2"

class RepeatedFunctionalTestsBaseClass(object):
    """
    This is a class with functional tests (tests that goes through
    basic functionality and actively communicates with third parties)
    that we want to repeat for all configured caldav_servers.
    
    (what a truely ugly name for this class - any better ideas?)
    """
    def setup(self):
        logging.debug("############## test setup")
        self.conn_params = self.server_params.copy()
        for x in self.conn_params.keys():
            if not x in ('url', 'proxy', 'username', 'password'):
                self.conn_params.pop(x)
        self.caldav = DAVClient(**self.conn_params)
        self.principal = Principal(self.caldav)
        try:                        
            cal = self.principal.calendar(name="Yep", cal_id=testcal_id)
            cal.delete()
        except:
            pass
        logging.debug("############## test setup done")

    def teardown(self):
        logging.debug("############## test teardown")
        try:                        
            cal = self.principal.calendar(name="Yep", cal_id=testcal_id)
            cal.delete()
        except:
            pass
        try:                        
            cal = self.principal.calendar(name="Yep", cal_id=testcal_id2)
            cal.delete()
        except:
            pass
        logging.debug("############## test teardown done")
 

    def testPropfind(self):
        """
        Test of the propfind methods. (This is sort of redundant, since
        this is implicitly run by the setup)
        """
        ## first a raw xml propfind to the root URL
        foo = self.caldav.propfind(self.principal.url, props="""<?xml version="1.0" encoding="UTF-8"?>
<D:propfind xmlns:D="DAV:">
  <D:allprop/>
        </D:propfind>""")
        assert('resourcetype' in foo.raw)
        
        ## next, the internal _query_properties, returning an xml tree ...
        foo2 = self.principal._query_properties([dav.Status(),])
        assert('resourcetype' in foo.raw)
        ## TODO: more advanced asserts

    def testGetCalendarHomeSet(self):
        chs = self.principal.get_properties([cdav.CalendarHomeSet()])
        assert '{urn:ietf:params:xml:ns:caldav}calendar-home-set' in chs

    def testGetCalendars(self):
        assert_not_equal(len(self.principal.calendars()), 0)

    def testProxy(self):
        if self.caldav.url.scheme == 'https':
            logging.info("Skipping %s.testProxy as the TinyHTTPProxy implementation doesn't support https")
            return

        server_address = ('127.0.0.1', 8080)
        proxy_httpd = NonThreadingHTTPServer (server_address, ProxyHandler, logging.getLogger ("TinyHTTPProxy"))

        threadobj = threading.Thread(target=proxy_httpd.serve_forever)
        try:
            threadobj.start()
            assert(threadobj.is_alive())
            conn_params = self.conn_params.copy()
            conn_params['proxy'] = proxy
            c = DAVClient(**conn_params)
            p = Principal(c)
            assert_not_equal(len(p.calendars()), 0)
        finally:
            proxy_httpd.shutdown()
            ## this should not be necessary, but I've observed some failures
            if threadobj.is_alive():
                time.sleep(0.05)
            assert(not threadobj.is_alive())

        threadobj = threading.Thread(target=proxy_httpd.serve_forever)
        try:
            threadobj.start()
            assert(threadobj.is_alive())
            conn_params = self.conn_params.copy()
            conn_params['proxy'] = proxy_noport
            c = DAVClient(**conn_params)
            p = Principal(c)
            assert_not_equal(len(p.calendars()), 0)
            assert(threadobj.is_alive())
        finally:
            proxy_httpd.shutdown()
            ## this should not be necessary
            if threadobj.is_alive():
                time.sleep(0.05)
            assert(not threadobj.is_alive())

    def testPrincipal(self):
        collections = self.principal.calendars()
        if 'principal_url' in self.server_params:
            assert_equal(self.principal.url, self.server_params['principal_url'])
        for c in collections:
            assert_equal(c.__class__.__name__, "Calendar")

    def testCreateDeleteCalendar(self):
        c = self.principal.make_calendar(name="Yep", cal_id=testcal_id)
        assert_not_equal(c.url, None)
        events = c.events()
        assert_equal(len(events), 0)
        events = self.principal.calendar(name="Yep", cal_id=testcal_id).events()
        assert_equal(len(events), 0)
        c.delete()
        
        ## verify that calendar does not exist - this breaks with zimbra :-(
        if 'zimbra' not in str(c.url):
            assert_raises(error.NotFoundError, self.principal.calendar(name="Yep", cal_id=testcal_id).events)

    def testSetCalendarProperties(self):
        c = self.principal.make_calendar(name="Yep", cal_id=testcal_id)
        assert_not_equal(c.url, None)

        props = c.get_properties([dav.DisplayName(),])
        assert_equal("Yep", props[dav.DisplayName.tag])

        ## Creating a new calendar with different ID but with existing name - fails on zimbra only
        if 'zimbra' in str(c.url):
            assert_raises(Exception, self.principal.make_calendar, "Yep", testcal_id2)

        c.set_properties([dav.DisplayName("hooray"),])
        props = c.get_properties([dav.DisplayName(),])
        assert_equal(props[dav.DisplayName.tag], "hooray")

        ## Creating a new calendar with different ID and old name - should never fail
        cc = self.principal.make_calendar(name="Yep", cal_id=testcal_id2).save()
        assert_not_equal(cc.url, None)
        cc.delete()

    def testEvent(self):
        """
        Run through various things - testing that it's possible to put,
        search and fetch calendar events from a calendar
        """
        c = self.principal.make_calendar(name="Yep", cal_id=testcal_id)
        assert_not_equal(c.url, None)

        ## This apparently fails on zimbra.  I get "201" back from it, and then 404 on the following GET :-(
        e1 = c.add_event(ev1)
        assert_not_equal(e1.url, None)

        logging.info(e1.url)

        e2 = c.event_by_url(e1.url)
        e3 = c.event_by_uid("20010712T182145Z-123401@example.com")
        assert_equal(e2.instance.vevent.uid, e1.instance.vevent.uid)
        assert_equal(e3.instance.vevent.uid, e1.instance.vevent.uid)

        assert_equal(e1.instance.vevent.uid, e2.instance.vevent.uid)

        r = c.date_search(datetime(2006,7,13,17,00,00),
                          datetime(2006,7,15,17,00,00))

        assert_equal(e1.instance.vevent.uid, r[0].instance.vevent.uid)
        assert_equal(len(r), 1)

    def _testCalendar(self):
        c = self.principal.make_calendar(name="Yep", cal_id=testcal_id)
        assert_not_equal(c.url, None)

        all = c.events()
        assert_equal(len(all), 1)

        e2 = Event(self.caldav, data = ev2, parent = c).save()
        assert_not_equal(e.url, None)

        tmp = c.event("20010712T182145Z-123401@example.com")
        assert_equal(e2.instance.vevent.uid, tmp.instance.vevent.uid)

        r = c.date_search(datetime(2006,7,13,17,00,00),
                          datetime(2006,7,15,17,00,00))
        assert_equal(len(r), 1)

        e.data = ev2
        e.save()

        r = c.date_search(datetime(2006,7,13,17,00,00),
                          datetime(2006,7,15,17,00,00))
        assert_equal(len(r), 1)

        e.instance = e2.instance
        e.save()
        r = c.date_search(datetime(2006,7,13,17,00,00),
                          datetime(2006,7,15,17,00,00))
        assert_equal(len(r), 1)

    def testObjects(self):
        ## TODO: description ... what are we trying to test for here?
        o = DAVObject(self.caldav)
        assert_raises(Exception, o.save)

# We want to run all tests in the above class through all caldav_servers;
# and I don't really want to create a custom nose test loader.  The
# solution here seems to be to generate one child class for each
# caldav_url, and inject it into the module namespace. TODO: This is
# very hacky.  If there are better ways to do it, please let me know.
# (maybe a custom nose test loader really would be the better option?)
# -- Tobias Brox <t-caldav@tobixen.no>, 2013-10-10

_servernames = set()
for _caldav_server in caldav_servers:
    # create a unique identifier out of the server domain name
    _parsed_url = urlparse.urlparse(_caldav_server['url'])
    _servername = _parsed_url.hostname.replace('.','_') + str(_parsed_url.port or '')
    while _servername in _servernames:
        _servername = _servername + '_'
    _servernames.add(_servername)

    # create a classname and a class
    _classname = 'TestForServer_' + _servername

    # inject the new class into this namespace
    vars()[_classname] = type(_classname, (RepeatedFunctionalTestsBaseClass,), {'server_params': _caldav_server})

class TestCalDAV:
    """
    Test class for "pure" unit tests (small internal tests, testing that
    a small unit of code works as expected, without any no third party
    dependencies)
    """
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
        client = DAVClient(url="http://me:hunter2@calendar.example:80/")
        principal = Principal(client, "http://me:hunter2@calendar.example:80/me/")
        principal.calendar_home_set = "http://me:hunter2@calendar.example:80/me/calendars/"
        ## calendar_home_set is actually a CalendarSet object
        assert(isinstance(principal.calendar_home_set, CalendarSet))
        calendar1 = principal.calendar(name="foo", cal_id="bar")
        calendar2 = principal.calendar_home_set.calendar(name="foo", cal_id="bar")
        assert_equal(calendar1.url, calendar2.url)
        assert_equal(calendar1.url, "http://calendar.example:80/me/calendars/bar")

        ## principal.calendar_home_set can also be set to an object
        ## This should be noop
        principal.calendar_home_set = principal.calendar_home_set
        calendar1 = principal.calendar(name="foo", cal_id="bar")
        assert_equal(calendar1.url, calendar2.url)

    def testDefaultClient(self):
        """When no client is given to a DAVObject, but the parent is given, parent.client will be used"""
        client = DAVClient(url="http://me:hunter2@calendar.example:80/")
        calhome = CalendarSet(client, "http://me:hunter2@calendar.example:80/me/")
        calendar = Calendar(parent=calhome)
        assert_equal(calendar.client, calhome.client)

    def testURL(self):
        """Excersising the URL class"""

        ## 1) URL.objectify should return a valid URL object almost no matter what's thrown in
        url1 = URL.objectify("http://foo:bar@www.example.com:8080/caldav.php/?foo=bar")
        url2 = URL.objectify(url1)
        url3 = URL.objectify("/bar")
        url4 = URL.objectify(urlparse.urlparse(str(url1)))
        url5 = URL.objectify(urlparse.urlparse("/bar"))
    
        ## 2) __eq__ works well
        assert_equal(url1, url2)
        assert_equal(url1, url4)
        assert_equal(url3, url5)

        ## 3) str will always return the URL
        assert_equal(str(url1), "http://foo:bar@www.example.com:8080/caldav.php/?foo=bar")
        assert_equal(str(url3), "/bar")
        assert_equal(str(url4), "http://foo:bar@www.example.com:8080/caldav.php/?foo=bar")
        assert_equal(str(url5), "/bar")

        ## 4) join method
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

        ## 5) all urlparse methods will work.  always.
        assert_equal(url1.scheme, 'http')
        assert_equal(url2.path, '/caldav.php/')
        assert_equal(url7.username, 'foo')
        assert_equal(url5.path, '/bar')
        urlC = URL.objectify("https://www.example.com:443/foo")
        assert_equal(urlC.port, 443)

        ## 6) is_auth returns True if the URL contains a username.  
        assert_equal(urlC.is_auth(), False)
        assert_equal(url7.is_auth(), True)

        ## 7) unauth() strips username/password
        assert_equal(url7.unauth(), 'http://www.example.com:8080/bar')
        
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
