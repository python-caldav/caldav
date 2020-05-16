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

Quickstart
==========

All code examples below are snippets from the basic_usage_examples.py.

Setting up a caldav client object and a principal object:

.. code-block:: python

  client = caldav.DAVClient(url=url, username=username, password=password)
  my_principal = client.principal()

Fetching calendars:
  
.. code-block:: python

  calendars = my_principal.calendars()

Creating a calendar:

.. code-block:: python

  my_new_calendar = my_principal.make_calendar(name="Test calendar")

Adding an event to the calendar:

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

  events_fetched = my_new_calendar.date_search(
  start=datetime(2021, 1, 1), end=datetime(2024, 1, 1), expand=True)

Find an object with a known URL, say, a calendar, without going through the Principal-object:

.. code-block:: python

  the_same_calendar = caldav.Calendar(client=client, url=my_new_calendar.url)

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

Adding a task to a task list:

.. code-block:: python

  my_new_tasklist.add_todo("""BEGIN:VCALENDAR
  VERSION:2.0
  PRODID:-//Example Corp.//CalDAV Client//EN
  BEGIN:VTODO
  UID:20070313T123432Z-456553@example.com
  DTSTAMP:20070313T123432Z
  DTSTART;VALUE=DATE:20200401
  DUE;VALUE=DATE:20200501
  RRULE:FREQ=YEARLY
  SUMMARY:Deliver some data to the Tax authorities
  CATEGORIES:FAMILY,FINANCE
  STATUS:NEEDS-ACTION
  END:VTODO
  END:VCALENDAR""")

Fetching tasks:

.. code-block:: python

  todos = my_new_tasklist.todos()

Date_search also works on task lists, but one has to be explicit to get the tasks:

.. code-block:: python

  todos = my_new_calendar.date_search(
      start=datetime(2021, 1, 1), end=datetime(2024, 1, 1),
      compfilter='VTODO', expand=True)

Mark a task as completed:

.. code-block:: python

  todos[0].complete()


More examples
=============

Check the examples folder, particularly `basic examples <https://github.com/python-caldav/caldav/blob/master/examples/basic_examples.py>`_.  The `test code <https://github.com/python-caldav/caldav/blob/master/tests/test_caldav.py>`_ also covers lots of stuff, though it's not much optimized for readability.  Tobias Brox is also working on a `command line interface <https://github.com/tobixen/calendar-cli>`_  built around the caldav library.

Notable classes and workflow
============================

 * You'd always start by initiating a :class:`caldav.davclient.DAVClient`
   object, this object holds the authentication details for the
   server.

 * From the client object one can get hold of a
   :class:`caldav.objects.Principal`
   object representing the logged-in principal.

 * From the principal object one can fetch / generate
   :class:`caldav.objects.Calendar` objects.  Calendar objects can also be
   instantiated directly from an absolute or relative URL and the client 
   object.

 * From the calendar object one can fetch / generate
   :class:`caldav.objects.Event` objects and
   :class:`caldav.objects.Todo` objects.

 * If one happens to know the URLs, objects like calendars, principals
   and events can be instantiated without going through the
   Principal-object of the logged-in user.

For convenience, the classes above are also available as
:class:`caldav.DAVClient`, :class:`caldav.Principal`,
:class:`caldav.Calendar`, :class:`caldav.Event` and
:class:`caldav.Todo`.


Compatibility
=============

The test suite is regularly run against several calendar servers, see https://github.com/python-caldav/caldav/issues/45 for the latest updates.  See `tests/compatibility_issues.py` for the most up-to-date list of compatibility issues.

 * You may want to avoid non-ASCII characters in the calendar name, or
   some servers (at least Zimbra) may behave a bit unexpectedly.

 * Not all servers supports searching for future instances of
   recurring events or tasks, nor expanding recurring events.

 * There are some special hacks both in the code and the tests to work
   around compatibility issues in Zimbra

 * Not all servers supports task lists, not all servers supports
   freebusy, and not all servers supports journals.

 * Calendar creation is actually not a mandatory feature according to
   the RFC, but the tests depends on it - and I haven't experienced
   any servers not supporting calendar creation.

 * iCloud may be a bit tricky, this is tracked in issue
   https://github.com/python-caldav/caldav/issues/3

 * Google seems to be the new Microsoft, according to the issue
   tracker it seems like their CalDAV-support is rather lacking.

Unit testing
============

To start the tests code, install everything from the setup.tests_requires list and run:

.. code-block:: bash

  $ python setup.py nosetests

(tox should also work, but it may be needed to look more into it)

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

