=================================
 Documentation: caldav |release|
=================================

.. module:: caldav

Contents
========

.. toctree::
   :maxdepth: 1

   caldav/davclient
   caldav/objects

Project home
============

The project currently lives on github,
https://github.com/python-caldav/caldav - if you have problems using
the library (including problems understanding the documentation),
please feel free to report it on the issue tracker there or send email
to caldav@plann.no.

Backward compatibility support
==============================

The 1.x version series is supposed to be fully backwards-compatible
with version 0.x, and is intended to be maintained at least
until 2026.

API-changes will be slowly introduced in 1.x.  API marked as
deprecated in 0.x or 1.0 will most likely be removed in version 2.0,
API marked with deprecating-warnings in 1.x or 2.0 will most likely be
removed in 3.0.  If you have any suggestions on API-changes, please
comment on https://github.com/python-caldav/caldav/issues/92

Notices will be logged when using legacy interface.  (See also
https://github.com/python-caldav/caldav/issues/240)


Python compatibility notice
===========================

Most of the code is regularly tested towards different versions of
Python, the oldest being Python 3.7.

Support for Python2 was officially not supported starting from caldav
version 1.0.

Please report issues if you have problems running the caldav library
with old python versions.  If it's easy to find a work-around I will
do so (like I did reverting new-style `f"{foo}"` strings into
old-style `"%s" % foo` strings).  If it's non-trivial to fix things,
we will officially abandon legacy support.

Objective and scope
===================

The python caldav library should make interactions with calendar servers
simple and easy.  Simple operations (like find a list of all calendars
owned, inserting a new event into a calendar, do a simple date
search, etc) should be trivial to accomplish even if the end-user of
the library has no or very little knowledge of the caldav, webdav or
icalendar standards.  The library should be agile enough to allow
"power users" to do more advanced stuff.

The library aims to take a pragmatic approach towards compatibility -
it should work as well as possible for as many as possible.  This also
means the library will modify icalendar data to get around known
compatibility issues - so no guarantee is given on the immutability of
icalendar data.

RFC 4791, 2518, 5545, 6638 et al
--------------------------------

RFC 4791 (CalDAV) outlines the standard way of communicating with a
calendar server.  RFC 4791 is an extension of RFC 4918 (WebDAV).  The
scope of this library is basically to cover RFC 4791/4918, the actual
communication with the caldav server.  (The WebDAV standard also has
quite some extensions, this library supports some of the relevant
extensions as well).

There exists another library webdavclient3 for handling RFC 4918
(WebDAV), ideally we should be depending on it rather than overlap it.

RFC 6638/RFC 6047 is extending the CalDAV and iCalendar protocols for
scheduling purposes, work is in progress to support RFC 6638.  Support
for RFC 6047 is considered mostly outside the scope of this library,
though for convenience this library may contain methods like accept()
on a calendar invite (which involves fetching the invite from the
server, editing the calendar data and putting it to the server).

This library should make it trivial to fetch an event, modify the data
and save it back to the server - but to do that it's also needed to
support RFC 5545 (icalendar).  It's outside the scope of this library
to implement logic for parsing and modifying RFC 5545, instead we
depend on another library for that.

RFC 5545 describes the icalendar format.  Constructing or parsing
icalendar data was considered out of the scope of this library, but we
do make exceptions - like, there is a method to complete a task - it
involves editing the icalendar data, and now the `save_event`,
`save_todo` and `save_journal` methods are able to construct icalendar
data if needed.

There exists two libraries supporting RFC 5545, vobject and icalendar.
The icalendar library seems to be more popular.  Version 1.0 depends
on both, but we're slowly moving towards using icalendar internally.

Misbehaving server implementations
----------------------------------

Some server implementations may have some "caldav"-support that either
doesn't implement all of RFC 4791, breaks the standard a bit, or has
extra features.  As long as it doesn't add too much complexity to the
code, hacks and workarounds for "badly behaving caldav servers" are
considered to be within the scope.  Ideally, users of the caldav
library should be able to download all the data from one calendar
server or cloud provider, upload it to another server type or cloud
provider, and continue using the library without noticing any
differences.  To get there, it may be needed to add tweaks in the
library covering the things the servers are doing wrong.

There exists an extension to the standard covering calendar color and
calendar order, allegedly with an xml namespace
``http://apple.com/ns/ical/``. That URL gives (301 https and
then) 404.  I've so far found no documentation at all
on this extension - however, it seems to be supported by several
caldav libraries, clients and servers.  As of 0.7, calendar colors and
order is available for "power users".

Quickstart
==========

All code examples below was snippets from the basic_usage_examples.py,
but the documentation and the examples may have drifted apart (TODO:
does there exist some good system for this?  Just use docstrings and doctests?)

Setting up a caldav client object and a principal object:

.. code-block:: python

  with caldav.DAVClient(url=url, username=username, password=password) as client:
      my_principal = client.principal()
      ...

Note that if a .netrc file exists, it will be honored and the username
and password may be omitted.  (Known bug: .netrc will be honoed even
if username and password is given - ref
https://github.com/python-caldav/caldav/issues/206)

Fetching calendars:

.. code-block:: python

  calendars = my_principal.calendars()

Creating a calendar:

.. code-block:: python

  my_new_calendar = my_principal.make_calendar(name="Test calendar")

Adding an event to the calendar, v0.9 adds this interface:

.. code-block:: python

  my_event = my_new_calendar.save_event(
      dtstart=datetime.datetime(2020,5,17,8),
      dtend=datetime.datetime(2020,5,18,1),
      summary="Do the needful",
      rrule={'FREQ': 'YEARLY'})

Adding an event described through some ical text:

.. code-block:: python

  my_event = my_new_calendar.save_event("""BEGIN:VCALENDAR
  VERSION:2.0
  PRODID:-//Example Corp.//CalDAV Client//EN
  BEGIN:VEVENT
  UID:20200516T060000Z-123401@example.com
  DTSTAMP:20200516T060000Z
  DTSTART:20200517T060000Z
  DTEND:20200517T230000Z
  RRULE:FREQ=YEARLY
  SUMMARY:Do the needful
  END:VEVENT
  END:VCALENDAR
  """)

Do a date search in a calendar:

.. code-block:: python

  events_fetched = my_new_calendar.search(
      start=datetime(2021, 1, 1), end=datetime(2024, 1, 1),event=True, expand=True)

To modify an event:

    event.vobject_instance.vevent.summary.value = 'Norwegian national day celebrations'
    event.save()

.. code-block:: python

  event.icalendar_instance

is also supported.

Find a calendar with a known URL without going through the Principal-object:

.. code-block:: python

  the_same_calendar = client.calendar(url=my_new_calendar.url)

Get all events from a calendar:

.. code-block:: python

  all_events = the_same_calendar.events()

Deleting a calendar (or, basically, any object):

.. code-block:: python

  my_new_calendar.delete()

Create a task list:

.. code-block:: python

  my_new_tasklist = my_principal.make_calendar(
              name="Test tasklist", supported_calendar_component_set=['VTODO'])

Adding a task to a task list.  The ics parameter may be some complete ical text string or a fragment.

.. code-block:: python

  my_new_tasklist.save_todo(
      ics = "RRULE:FREQ=YEARLY",
      summary="Deliver some data to the Tax authorities",
      dtstart=date(2020, 4, 1),
      due=date(2020,5,1),
      categories=['family', 'finance'],
      status='NEEDS-ACTION')

Fetching tasks:

.. code-block:: python

  todos = my_new_tasklist.todos()

Date_search also works on task lists, but one has to be explicit to get the tasks:

.. code-block:: python

  todos = my_new_calendar.search(
      start=datetime(2021, 1, 1), end=datetime(2024, 1, 1),
      compfilter='VTODO',event=True, expand=True)

Mark a task as completed:

.. code-block:: python

  todos[0].complete()


More examples
=============

Check the examples folder, particularly `basic examples <https://github.com/python-caldav/caldav/blob/master/examples/basic_usage_examples.py>`_. There is also a `scheduling examples <https://github.com/python-caldav/caldav/blob/master/examples/scheduling_examples.py>`_ for sending, receiving and replying to invites, though this is not very well-tested so far.  The `test code <https://github.com/python-caldav/caldav/blob/master/tests/test_caldav.py>`_ also covers lots of stuff, though it's not much optimized for readability (at least not as of 2020-05).  Tobias Brox is also working on a `command line interface <https://github.com/tobixen/calendar-cli>`_  built around the caldav library.

Notable classes and workflow
============================

* You'd always start by initiating a :class:`caldav.davclient.DAVClient`
  object, this object holds the authentication details for the
  server.

* From the client object one can get hold of a
  :class:`caldav.objects.Principal` object representing the logged-in
  principal.

* From the principal object one can fetch / generate
  :class:`caldav.objects.Calendar` objects.

* From the calendar object one can fetch / generate
  :class:`caldav.objects.Event` objects and
  :class:`caldav.objects.Todo` objects (as well as :class:`caldav.objects.Journal` objects - does anyone use Journal objects?).  Eventually the library may also spew out objects of the base class (:class:`caldav.objects.CalendarObjectResource`) if the object type is unknown when the object is instantiated.

* If one happens to know the URLs, objects like calendars, principals
  and events can be instantiated without going through the
  Principal-object of the logged-in user.  A path, relative URL or
  full URL should work, but the URL should be without authentication
  details.

For convenience, the classes above are also available as
:class:`caldav.DAVClient`, :class:`caldav.Principal`,
:class:`caldav.Calendar`, :class:`caldav.Event`,
:class:`caldav.Todo` etc.

Compatibility
=============

(This will probably never be completely up-to-date.  CalDAV-servers
tend to be a moving target, and I rarely recheck if things works in
newer versions of the software after I find an incompatibility)

The test suite is regularly run against several calendar servers, see https://github.com/python-caldav/caldav/issues/45 for the latest updates.  See ``compatibility_hints.py`` for the most up-to-date list of compatibility issues.  In early versions of this library test breakages was often an indication that the library did not conform well enough to the standards, but as of today it mostly indicates that the servers does not support the standard well enough.  It may be an option to add tweaks to the library code to cover some of the missing functionality.

Here are some known issues:

* iCloud, Google and Zimbra are notoriously bad on their CalDAV-support.

* You may want to avoid non-ASCII characters in the calendar name, or
  some servers (at least Zimbra) may behave a bit unexpectedly.

* It's non-trivial to fix proper support for recurring events and
  tasks on the server side.  DAViCal and Baikal are the only one I
  know of that does it right, all other calendar implementations that
  I've tested fails (but in different ways) on the tests covering
  recurrent events and tasks.  Xandikos developer claims that it
  should work, I should probably revisit it again.

* Baikal does not support date search for todo tasks.  DAViCal has
  slightly broken support for such date search.

* There are some special hacks both in the code and the tests to work
  around compatibility issues in Zimbra (this should be solved differently)

* Not all servers supports task lists, not all servers supports
  freebusy, and not all servers supports journals.  Xandikos and
  Baikal seems to support them all.

* Calendar creation is actually not a mandatory feature according to
  the RFC, but the tests depends on it.  The google calendar does
  support creating calendars, but not through their CalDAV adapter.

* iCloud may be a bit tricky, this is tracked in issue
  https://github.com/python-caldav/caldav/issues/3 - the list of incompatibilities found includes:

  * No support for freebusy-requests, tasks or journals (only support for basic events).

  * Broken (or no) support for recurring events

  * We've observed information reappearing even if it has been deleted (i.e. recreating a calendar with the same name as a deleted calendar, and finding that the old events are still there)

  * Seems impossible to have the same event on two calendars

  * Some problems observed with the propfind method

  * object_by_uid does not work (and my object_by_uid follows the example in the RFC)

* Google seems to be the new Microsoft, according to the issue
  tracker it seems like their CalDAV-support is rather lacking.  At least they have a list ... https://developers.google.com/calendar/caldav/v2/guide

* radicale will auto-create a calendar if one tries to access a calendar that does not exist.  The normal method of accessing a list of the calendars owned by the user seems to fail.

Some notes on CalDAV URLs
=========================

CalDAV URLs can be quite confusing, some software requires the URL to the calendar, other requires the URL to the principal.  The Python CalDAV library does support accessing calendars and principals using such URLs, but the recommended practice is to configure up the CalDAV root URL and tell the library to find the principal and calendars from that.  Typical examples of CalDAV URLs:

* iCloud: ``https://caldav.icloud.com/``.  Note that there is no
  template for finding the calendar URL and principal URL for iCloud -
  such URLs contains some ID numbers, by simply sticking to the
  recommended practice the caldav library will find those URLs.  A
  typical icloud calendar URL looks like
  ``https://p12-caldav.icloud.com/12345/calendars/CALNAME``.
  If you encounter troubles with iCloud, try toggling
  between IPv4 and IPv6 (see [issue 393](https://github.com/python-caldav/caldav/issues/393))

* Google - legacy:  ``https://www.google.com/calendar/dav/``,
  The calendar URL for the primary personal calendar seems to be of the
  format ``https://www.google.com/calendar/dav/donald%40gmail.com/events``. When
  creating new calendars, they seem to end up under a global
  namespace.

* Google - new api: see https://developers.google.com/calendar/caldav/v2/guide.
  Please comment in https://github.com/python-caldav/caldav/issues/119 if you manage to connect to Google calendar.

* DAViCal: The caldav URL typically seems to be on the format ``https://your.server.example.com/caldav.php/``, though it depends on how the web server is configured.  The primary calendars have URLs like ``https://your.server.example.com/caldav.php/donald/calendar`` and other calendars have names like ``https://your.server.example.com/caldav.php/donald/golfing_calendar``.

* Zimbra: The caldav URL is typically on the format ``https://mail.example.com/dav/``, calendar URLs can be on the format ``https://mail.example.com/dav/donald@example.com/My%20Golfing%20Calendar``.  Display name always matches the last part of the URL.

* Fastmail: ``https://caldav.fastmail.com/dav/`` - note that the trailing dash is significant (ref https://github.com/home-assistant/core/issues/66599)

* GMX: `f"https://caldav.gmx.net/begenda/dav/{userid}@gmx.net/calendar`"`

* Purelymail: `https://purelymail.com/webdav/`

* Posteo: `https://posteo.de:8443/`

* all-inkl: `https://webmail.all-inkl.com/calendars/`

* Lark: `https://caldav-jp.larksuite.com` - note that Lark offers a very limited read-only access through the CalDAV protocol.

Unit testing
============

To start the tests code, install everything from the setup.tests_requires list and run:

.. code-block:: bash

  $ python setup.py test

tox should also work:

.. code-block:: bash

  $ tox -e py

It will run some unit tests and some functional tests.  You may want to add your own
private servers into tests/conf_private.py, see tests/conf_private.py.EXAMPLE

Documentation
=============

To build the documentation, install sphinx and run:

.. code-block:: bash

  $ python setup.py build_sphinx


License
=======

Caldav is dual-licensed under the GNU GENERAL PUBLIC LICENSE Version 3 and the Apache License 2.0.

====================
 Indices and tables
====================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
