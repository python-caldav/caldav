.. python-caldav documentation master file, created by
   sphinx-quickstart on Thu Jun  3 10:47:52 2010.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

=================================
 Documentation: caldav |release|
=================================

Contents
========

.. toctree::
   :maxdepth: 1

   caldav/davclient
   caldav/objects

Python 3
========

The caldav library should work well with python3, but there is one dependency on vobject, a library that doesn't work out of the box in python3 as of 2015-04-21.  There exists forks.  See `issue #41 - vobject dependency situation <https://bitbucket.org/cyrilrbt/caldav/issue/41/vobject-dependency-situation>` for details.

Quickstart
==========

.. code-block:: python

  from datetime import datetime
  import caldav
  from caldav.elements import dav, cdav
  
  # Caldav url
  url = "https://user:pass@hostname/caldav.php/"
  
  vcal = """BEGIN:VCALENDAR
  VERSION:2.0
  PRODID:-//Example Corp.//CalDAV Client//EN
  BEGIN:VEVENT
  UID:1234567890
  DTSTAMP:20100510T182145Z
  DTSTART:20100512T170000Z
  DTEND:20100512T180000Z
  SUMMARY:This is an event
  END:VEVENT
  END:VCALENDAR
  """
  
  client = caldav.DAVClient(url)
  principal = client.principal()
  calendars = principal.calendars()
  if len(calendars) > 0:
      calendar = calendars[0]
      print "Using calendar", calendar
  
      print "Renaming"
      calendar.set_properties([dav.DisplayName("Test calendar"),])
      print calendar.get_properties([dav.DisplayName(),])
  
      event = calendar.add_event(vcal)
      print "Event", event, "created"
  
      print "Looking for events in 2010-05"
      results = calendar.date_search(
          datetime(2010, 5, 1), datetime(2010, 6, 1))

      for event in results:
          print "Found", event

More examples
=============

See the `test code <https://bitbucket.org/cyrilrbt/caldav/src/default/tests/test_caldav.py?at=default>`_ for more usage examples.  Tobias Brox is also working on a `command line interface <https://github.com/tobixen/calendar-cli>`_  built around the caldav library.

Notable classes and workflow
============================

 * You'd always start by initiating a :class:`caldav.davclient.DAVClient`
   object, this object holds the authentication details for the
   server.

 * From the client object one can get hold of a
   :class:`caldav.objects.Principal`
   object representing the logged in principal.

 * From the principal object one can fetch / generate
   :class:`caldav.objects.Calendar` objects.  Calendar objects can also be
   instantiated directly from an absolute or relative URL and the client 
   object.

 * From the calendar object one can fetch / generate
   :class:`caldav.objects.Event` objects and
   :class:`caldav.objects.Todo` objects.  Event objects can also be
   instantiated directly from an absolute or relative URL and the client
   object.

Note that those are also available as :class:`caldav.DAVClient`,
:class:`caldav.Principal`, :class:`caldav.Calendar`,
:class:`caldav.Event` and :class:`caldav.Todo`.


Compatibility
=============

The test suite is regularly run against SoGO, Baikal, DAViCal, Zimbra
and OwnCloud.  Some compatibility issues have been found, search the
test code for "COMPATIBILITY" for details.  Notably;

 * You may want to avoid non-ASCII characters in the calendar name, or
   Zimbra may behave a bit unexpectedly.

 * How would you expect the result to be when doing date searches
   spanning multiple instances of a recurring event?  Would you expect
   one ical object for each occurrence (and maybe that's why
   open-ended date searches tend to break at some implementations) or
   one recurring ical object?  Different servers behave a bit
   differently (but more research is needed on this one).

 * Zimbra seems to be the least compatible server, there are some
   special hacks in the code to work around compatibility issues in
   Zimbra.

 * iCloud - we've managed read-only access to iCloud so far - see
   https://bitbucket.org/cyrilrbt/caldav/issue/40/icloud-not-fully-supported
   for details.

Unit testing
============

To start the tests code, run:

.. code-block:: bash

  $ python setup.py nosetests

Note that there is a big bug in the functional tests; if the test
suite is run in parallell towards the same servers/principals, some
tests will fail or raise exceptions, and this may very well happen if
multiple developers runs the tests at the same time.  This hasn't been
a problem so far.

It will run some unit tests and some functional tests against a
dedicated baikal server hosted by Tobias Brox.  You may add your own
private servers into tests/conf_private.py, like this:

.. code-block:: python

  caldav_servers = [{
      "url": "https://myserver.example.com:80/caldav.php/",
      'username': 'testuser',
      'password': 'hunter2'}]

the dict may contain:
 * username and password (if not embedded in the URL)
 * principal_url (used to verify client.principal().url)
 * backwards_compatibility_url (deprecated - URLs that worked with caldav versions prior to 0.2 goes here)

Documentation
=============

To build the documentation, install sphinx and run:

.. code-block:: bash

  $ python setup.py build_sphinx


====================
 Indices and tables
====================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

