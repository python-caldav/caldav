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

If you stumble upon problems and cannot easily resolve them, feel free
to get in touch, i.e. by the issue tracker.

The 1.x version series is not maintained anymore.

If serious problems are found with v2.2.6 during 2026, v2.2.7 will be
released.

The 3.x version series (released 2026-03) is almost
backwards-compatible with version 2.x.  Python 3.10+ is required
(Python 3.8 and 3.9 are no longer supported).  The
``caldav/objects.py`` backward-compatibility shim has been removed;
any code doing ``from caldav.objects import <something>`` must be
updated to import directly from ``caldav``.  The wildcard import has
also been removed, so if you were doing weird imports from ``caldav``,
things may break.

API deprecated with a warning in 2.x may be removed in a future 4.0 release.
API deprecated without a warning in 2.x will get a deprecation warning in 4.0.

If you have any suggestions on API-changes, please
comment on https://github.com/python-caldav/caldav/issues/92

Python compatibility notice
===========================

Most of the code is regularly tested towards different versions of
Python, the oldest being Python 3.10 (as of v3.0).

Support for Python2 was officially not supported starting from caldav
version 1.0.


RFC compliance
--------------

:rfc:`4791` (CalDAV) outlines the standard way of communicating with a
calendar server.  :rfc:`4791` is an extension of :rfc:`4918` (WebDAV).  The
scope of this library is basically to cover :rfc:`4791` and :rfc:`4918`, the actual
communication with the caldav server.  (The WebDAV standard also has
quite some extensions, this library supports some of the relevant
extensions as well).

There exists another library webdavclient3 for handling :rfc:`4918`
(WebDAV), ideally we should be depending on it rather than overlap it.

:rfc:`6638` and :rfc:`6047` extend the CalDAV and iCalendar protocols for
scheduling purposes, work is in progress to support :rfc:`6638`.  Support
for :rfc:`6047` is considered mostly outside the scope of this library,
though for convenience this library may contain methods like accept()
on a calendar invite (which involves fetching the invite from the
server, editing the calendar data and putting it to the server).

This library should make it trivial to fetch an event, modify the data
and save it back to the server - but to do that it's also needed to
support :rfc:`5545` (icalendar).  It's outside the scope of this library
to implement logic for parsing and modifying :rfc:`5545`, instead we
depend on another library for that.

:rfc:`5545` describes the icalendar format.  Constructing or parsing
icalendar data was considered out of the scope of this library, but we
do make exceptions - like, there is a method to complete a task - it
involves editing the icalendar data, and now the ``add_event``,
``add_todo`` and ``add_journal`` methods are able to construct icalendar
data if needed.

There exists two libraries supporting :rfc:`5545`, vobject and icalendar.
vobject was unmaintained for several years, but seems to be actively
maintained now.  The caldav library originally came with vobject
support, but as many people requested the vobject dependency to be
replaced with icalendar, both are now supported, and the icalendar
library is now consistently used internally

Misbehaving server implementations
----------------------------------

Some server implementations may have some "caldav"-support that either
doesn't implement all of :rfc:`4791`, breaks the standard a bit, or has
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
  server.  In 2.0 the function :func:`caldav.get_davclient` was added as the recommended way to get a client.

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

CalDAV server implementations vary widely in which optional RFC features they
support, and how gracefully they handle things they do not support.  The caldav
library contains a compatibility layer that works around known issues
automatically when the server is identified.

Compatibility hints system
--------------------------
..todo:: the sections about the compatibility hints should be moved somewhere else, maybe to a new document.

Server quirks and workarounds are encoded in ``caldav/compatibility_hints.py``.
Each feature has a *support level*:

* ``full`` — works (as expected or better than expected)
* ``quirk`` — supported, but needs special client-side handling
* ``fragile`` — sometimes works, sometimes not
* ``broken`` — server does something unexpected
* ``ungraceful`` — server raises an HTTP error instead of handling gracefully
* ``unsupported`` — feature is absent; attempts are silently skipped or adapted
* ``unknown`` — not yet tested

The library calls ``is_supported(feature)`` internally before issuing requests,
and applies workarounds where possible (for example, injecting an explicit time
range when ``search.unlimited-time-range`` is ``broken``).

Configuring compatibility hints
--------------------------------

The ``features`` parameter of :func:`caldav.get_davclient` (or
:class:`caldav.DAVClient`) selects a named server profile from
``compatibility_hints.py``, or accepts a dict of feature overrides:

.. code-block:: python

    # Use a named profile — workarounds are applied automatically
    client = get_davclient(url="https://caldav.icloud.com/", features="icloud", ...)

    # Override individual features
    client = get_davclient(url="https://...", features={"search.text": {"support": "unsupported"}}, ...)

(Best practice is to keep the configuration including passwords in a
configuration file rather than hard-coding it in the python code)

For well-known providers (iCloud, ecloud, etc.) the ``features`` string also
encodes the well-known CalDAV URL, so only the credentials are required.  See
:doc:`configfile` for how to specify ``features`` in the config file.

The test suite is regularly run against several calendar servers, see
https://github.com/python-caldav/caldav/issues/45 for the latest updates.
See ``compatibility_hints.py`` for the authoritative and up-to-date list of
known quirks.  Earlier versions of the library often had test failures that
indicated the library itself was wrong; nowadays failures more often indicate
that the server deviates from the standard.

Server-specific highlights
--------------------------

* **iCloud, Google, Zimbra** are notoriously incomplete in their CalDAV
  support — see the server profile names ``icloud``, ``google``, ``zimbra``
  in ``compatibility_hints.py`` for the current list of known issues.

  iCloud has not been tested for a while.  As the maintainer has no account there, YOUR help is needed to ensure iCloud-compatibility.

  Notable iCloud limitations (tracked in https://github.com/python-caldav/caldav/issues/3):

  * No support for freebusy, tasks, or journals.
  * Broken or absent support for recurring events.
  * Objects deleted from one client may reappear after recreating a
    calendar with the same name.
  * ``get_object_by_uid()`` does not work despite following the RFC example.

  Google's CalDAV adapter does not support creating calendars; use the Google
  API directly for that.  As with iCloud, Google support hasn't been tested for quite a while.

* **Radicale** will auto-create a calendar when accessing a URL that does not
  exist, and listing calendars owned by the user may fail.

* **Baikal** does not support date-range searches for todo tasks.

* **DAViCal** has slightly broken support for date-range searches on todos.

* **OX App Suite** applies a "sliding window" to all calendar REPORT queries:
  objects whose date lies too far in the past (or future) are invisible.
  There is no CalDAV mechanism to enumerate those objects — they are invisible
  to ``calendar.search()``, ``calendar.events()``,
  ``calendar.get_objects_by_sync_token()``, and ``calendar.get_object_by_uid()``;
  the only way to access them is a direct GET if the URL is already known.
  The library works around this by injecting an explicit 1970–2126 time range
  (``search.unlimited-time-range: broken``), which makes recurring events with
  future occurrences visible, but truly old non-recurring objects remain
  inaccessible.  OX also rejects VTODOs containing RRULE with HTTP 400, and
  VTODOs must be stored in a calendar explicitly created for the ``VTODO``
  component type.

* **Calendar creation** is not mandatory under :rfc:`4791`.  Most self-hosted
  servers support it; Google's CalDAV adapter does not.

* **Recurring events and tasks** are non-trivial to implement correctly on
  the server side.  DAViCal and Baikal are the only servers known to handle
  them correctly in the test suite.

Some notes on CalDAV URLs
=========================

From v2.1, well-known URLs were hard-coded into the compatibility_hints.  As of v2.2, auto-detection based on :rfc:`6764` is supported.  This protocol is widely used.  For servers supporting it, it's sufficient to add something like "demo2.nextcloud.com" in the URL.  For well-known calendar providers, it's not needed to enter anything in the URL, it suffices to put i.e. `features="ecloud"` into the connection parameters.

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

To run the tests, install the test dependencies and use pytest:

.. code-block:: bash

  $ pip install -e ".[test]"
  $ pytest

tox should also work:

.. code-block:: bash

  $ tox -e py

It will run some unit tests and some functional tests.  You may want to add your own
private servers into tests/caldav_test_servers.yaml, see tests/caldav_test_servers.yaml.example

Niquests vs Requests vs HTTPX
=============================

By default, CalDAV depends on the niquests library.  Some people are not happy with that, there exists fallbacks to utilize httpx and requests.  See the :doc:`http-libraries` document.

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
