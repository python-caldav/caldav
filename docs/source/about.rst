======================================
About the Python CalDAV Client Library
======================================


Project home
============

The project currently lives on github,
https://github.com/python-caldav/caldav - if you have problems using
the library (including problems understanding the documentation),
please feel free to report it on the issue tracker there or send email
to caldav@plann.no.

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

Backward compatibility support
==============================

The 1.x version series is intended to be maintained at least until
2026-01.

The 2.x version series (not released as of 2025-06-01) is supposed to
be fully backwards-compatible with version 1.x, and is intended to be
maintained at least until 2027.

2.0 sheds compatibility with python 3.7 and python 3.8, and one
obscure deprecated method has been ripped out.

API that is marked as deprecated 2.x will most likely be removed in version 3.0
If you have any suggestions on API-changes, please
comment on https://github.com/python-caldav/caldav/issues/92

Warnings will be issued when using legacy interface.


Python compatibility notice
===========================

Most of the code is regularly tested towards different versions of
Python, the oldest being Python 3.9.

Support for Python2 was officially not supported starting from caldav
version 1.0.


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
involves editing the icalendar data, and now the ``save_event``,
``save_todo`` and ``save_journal`` methods are able to construct icalendar
data if needed.

There exists two libraries supporting RFC 5545, vobject and icalendar.
vobject was unmaintained for several years, but seems to be actively
maintained now.  The caldav library originally came with vobject
support, but as many people requested the vobject dependency to be
replaced with icalendar, both are now supported, and the icalendar
library is now consistently used internally

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


Notable classes and workflow
============================

* You'd always start by initiating a :class:`caldav.davclient.DAVClient`
  object, this object holds the authentication details for the
  server.  In 2.0 there is a function :class:`caldav.davclient.get_davclient` that can be used.

* From the client object one can get hold of a
  :class:`caldav.collection.Principal` object representing the logged-in
  principal.

* From the principal object one can fetch / generate
  :class:`caldav.collection.Calendar` objects.

* From the calendar object one can fetch / generate
  :class:`caldav.calendarobjectresource.Event` objects and
  :class:`caldav.calendarobjectresource.Todo` objects (as well as :class:`caldav.calendarobjectresource.Journal` objects - does anyone use Journal objects?).  Eventually the library may also spew out objects of the base class (:class:`caldav.calendarobjectresource.CalendarObjectResource`) if the object type is unknown when the object is instantiated.

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

.. todo::
   This section should be moved into separate HOWTOs for each calendar server/provider.
   Check if comment "to be released" can be removed

From v2.1, well-known URLs were hard-coded into the compatibility_hints.  As of v2.2 (to be released 2025-12) auto-detection based on RFC6764 is supported.  This protocol is widely used.  For servers supporting it, it's sufficient to add something like "demo2.nextcloud.com" in the URL.  For well-known calendar providers, it's not needed to enter anything in the URL, it suffices to put i.e. `features="ecloud"` into the connection parameters.

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
  There is some information in https://github.com/python-caldav/caldav/issues/119 on how to connect to Google, and there are two contributed :ref:`examples:examples` on how to obtain a bearer token and use it in the caldav lbirary.  There is also a `blog post <https://blog.lasall.dev/post/tell-me-why-google-and-caldav/>`_ describing the process.

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

Code of Conduct
===============

While I hope we never will need to refer to it, the `Contributor Covenant <https://www.contributor-covenant.org/version/2/1/code_of_conduct/>`_ applies to this project, see also `CODE_OF_CONDUCT <https://github.com/python-caldav/caldav/blob/master/CODE_OF_CONDUCT>`_.  Avoid toxic negativity in general, but Tobias Brox can probably handle some blunt criticism if it may help getting the project on a better track.

License
=======

Caldav is dual-licensed under the GNU GENERAL PUBLIC LICENSE Version 3 or the Apache License 2.0.
