=========================================
Migrating from caldav 2.x to 3.x
=========================================

v3.x is mostly backward-compatible with v2.x.  Existing code should
generally continue to run.  New method names and usage patterns exists
alongside the old ones.  The purpose of this document is to give a
primer on the "best current usage practice" as of v3.x.

.. contents:: Contents
   :local:
   :depth: 2


Breaking Changes
================

Python version
--------------

Python 3.10 or later is now required.  Python 3.8 and 3.9 are no longer
supported.

``caldav.objects`` import shim removed
---------------------------------------

The ``caldav/objects.py`` backward-compatibility re-export module has been
deleted.  If you have:

.. code-block:: python

    from caldav.objects import Event, Todo, Calendar   # REMOVED

replace it with:

.. code-block:: python

    from caldav import Event, Todo, Calendar           # OK

All public symbols that were in ``caldav.objects`` should remain available directly
from the ``caldav`` namespace

Wildcard import into caldav.* removed
-------------------------------------
Earlier a wildcard import ``from caldav.objects import *`` was done into the ``caldav`` namespace.  This has been removed.  In normal circumstances, your imports should continue to work - but there are no guarantees that all imports will continue working.  If you have any issues, see :doc:`contact`.

Config-file parse errors now raise exceptions
---------------------------------------------

``read_config()`` used to log and return an empty dict on YAML/JSON parse
errors.  It now raises ``ValueError``.  This means misconfigured files fail
loudly rather than silently.


Recommended API Changes
========================

The changes below are not yet breaking — the old names still work.  Some of them
emits ``DeprecationWarning``, others will do so in an upcoming release.  New code
should use the new names.


Factory function instead of direct instantiation
-------------------------------------------------

.. list-table::
   :widths: 45 55
   :header-rows: 1

   * - v2.x
     - v3.x (recommended)
   * - ``DAVClient(url=..., username=..., password=...)``
     - ``get_davclient(url=..., username=..., password=...)``

:func:`caldav.get_davclient` reads credentials from environment variables and
config files, selects an appropriate HTTP library, and handles server-specific
compatibility hints automatically:

.. code-block:: python

    from caldav import get_davclient

    # Credentials from env vars or ~/.config/caldav/calendar.conf
    # This is considered best practice!
    with get_davclient() as client:
        principal = client.get_principal()
	...

    # Or supply them explicitly
    with get_davclient(url="https://caldav.example.com/",
                       username="alice", password="secret") as client:
        principal = client.get_principal()
	...

    # Use a named compatibility profile (ecloud, baikal, posteo, …)
    with get_davclient(features="ecloud",
                       username="alice@icloud.com", password="...") as client:
        ...

Calendars may be configured in the config file, and it's also possible to get a calendar directly through factory method:

.. code-block:: python

    from caldav import get_calendar
    with my_calendar as get_calendar(config_section='work_calendar'):
        ...

See :doc:`configfile` for the config-file format and the full list of
parameters.


Principal and calendar access
------------------------------

Quite some methods have been renamed for consistency both within the package and with the python ecosystem as such.

.. list-table::
   :widths: 45 55
   :header-rows: 1

   * - v2.x
     - v3.x
   * - ``client.principal()``
     - ``client.get_principal()``
   * - ``principal.calendars()``
     - ``principal.get_calendars()``
   * - ``client.principals(name=...)``
     - ``client.search_principals(name=...)``

.. code-block:: python

    # v2.x
    principal = client.principal()
    calendars = principal.calendars()

    # v3.x
    principal = client.get_principal()
    calendars = principal.get_calendars()

Rationale: Those methods are actively querying the server for data, hence a verb is more fitting.

Adding calendar objects
------------------------

The ``save_*`` family is deprecated.  Use ``add_*`` for adding *new* objects:

.. list-table::
   :widths: 45 55
   :header-rows: 1

   * - v2.x
     - v3.x
   * - ``calendar.save_event(ical_str)``
     - ``calendar.add_event(ical_str)``
   * - ``calendar.save_todo(ical_str)``
     - ``calendar.add_todo(ical_str)``
   * - ``calendar.save_journal(ical_str)``
     - ``calendar.add_journal(ical_str)``
   * - ``calendar.save_object(ical_str)``
     - ``calendar.add_object(ical_str)``

To **update** an existing object, fetch it and call ``object.save()``:

.. code-block:: python

    event = calendar.get_event_by_uid("some-uid")
    event.data = new_ical_string
    event.save()

Rationale: In the tests, documentation and examples I'm always adding new content with those methods, so add feels more right than save.  This is a revert of a change that was done in v0.7.0.  See  https://github.com/python-caldav/caldav/issues/71 for details.  While the ``add_object``-method possibly MAY be used for updating an object, it SHOULD not be used for this purpose.

Listing and fetching objects
-----------------------------

.. list-table::
   :widths: 45 55
   :header-rows: 1

   * - v2.x
     - v3.x
   * - ``calendar.events()``
     - ``calendar.get_events()``
   * - ``calendar.todos()``
     - ``calendar.get_todos()``
   * - ``calendar.journals()``
     - ``calendar.get_journals()``
   * - ``calendar.event_by_uid(uid)``
     - ``calendar.get_event_by_uid(uid)``
   * - ``calendar.todo_by_uid(uid)``
     - ``calendar.get_todo_by_uid(uid)``
   * - ``calendar.journal_by_uid(uid)``
     - ``calendar.get_journal_by_uid(uid)``
   * - ``calendar.object_by_uid(uid)``
     - ``calendar.get_object_by_uid(uid)``
   * - ``calendar.objects_by_sync_token()``
     - ``calendar.get_objects_by_sync_token()``

Rationale: Those methods are actively querying the server for data, hence a verb is more fitting.

Searching
----------

``date_search()`` is deprecated.  Use ``search()`` instead:

.. code-block:: python

    from datetime import datetime

    # v2.x
    events = calendar.date_search(start=datetime(2024,1,1),
                                  end=datetime(2024,12,31),
                                  expand=True)

    # v3.x — note the keyword arguments and the explicit event=True flag
    events = calendar.search(start=datetime(2024,1,1),
                             end=datetime(2024,12,31),
                             event=True, expand=True)

``search()`` also accepts ``todo=True``, ``journal=True``, ``comp_class=Event``,
free-text filters, category filters, and more.  See the API reference for the
full signature.

Rationale: ``date_search`` has actually been deprecated since 2.0, if not longer.  It's just a special case of ``search``.

Capability checks
-----------------

.. list-table::
   :widths: 45 55
   :header-rows: 1

   * - v2.x
     - v3.x
   * - ``client.check_dav_support()``
     - ``client.supports_dav()``
   * - ``client.check_cdav_support()``
     - ``client.supports_caldav()``
   * - ``client.check_scheduling_support()``
     - ``client.supports_scheduling()``

Rationale: Those methods are also querying the server actively, and not just looking up things in a feature-matrix, hnence a verb is more fitting.

Accessing and editing calendar data
=====================================

This is the most significant new API in v3.x, addressing a long-standing
ambiguity in how calendar object data was accessed and modified.

The old ``vobject_instance``, ``icalendar_instance``, ``icalendar_component`` are now deprecated.

The Problem with the 2.x API
------------------------------

In 2.x, the properties ``data``, ``icalendar_instance``, and
``vobject_instance`` on a ``CalendarObjectResource`` all shared a single
internal slot.  Accessing one representation could silently invalidate another:

.. code-block:: python

    # 2.x — silent bug
    event = calendar.search(...)[0]
    comp = event.icalendar_component       # get a reference
    _ = event.data                         # accessing data invalidates comp!
    comp["SUMMARY"] = "Updated"
    event.save()                           # change is NOT saved

The 3.x Solution: read and edit methods
-----------------------------------------

v3.x adds explicit read-only getters that always return **copies**, and
context-manager "borrow" methods that give exclusive, safe write access.

**Read-only access** (safe at any time, returns a copy):

.. code-block:: python

    # Get raw iCalendar string
    raw = event.get_data()

    # Get a copy of the icalendar.Calendar object — changes are NOT saved
    cal_copy = event.get_icalendar_instance()
    summary = cal_copy.subcomponents[0]["SUMMARY"]

    # Get a copy of the vobject component — changes are NOT saved
    vobj_copy = event.get_vobject_instance()
    summary = vobj_copy.vevent.summary.value

    # Quick access to the inner VEVENT/VTODO/VJOURNAL component
    summary = event.component["SUMMARY"]   # component is always a copy

**Editing with icalendar** (borrowing pattern):

.. code-block:: python

    with event.edit_icalendar_instance() as cal:
        for comp in cal.subcomponents:
            if comp.name == "VEVENT":
                comp["SUMMARY"] = "Updated summary"
    event.save()

**Editing with vobject** (borrowing pattern):

.. code-block:: python

    with event.edit_vobject_instance() as vobj:
        vobj.vevent.summary.value = "Updated summary"
    event.save()

While inside the ``with`` block, the borrowed representation is the
single source of truth.  Attempting to borrow a *different*
representation raises ``RuntimeError``.  This means the current
pattern is not completely thread-safe as of v3.x - but an explicit
error is often better than updates silently being dropped.

**The data representation remains the same:**

The interface for the string representation is still the same.  Strings are immutable, so the concern above is not relevant for strings.  (Of course, the code below will have bad side effects if the event was modified simultaneously by another thread, as well as if the event was modified on the server by another client).

.. code-block:: python

    ## Get the raw iCalendar string
    ical_string = event.data
    new_ical_string = modify_ical(ical_string)

    # Replace all data from a raw iCalendar string
    event.data = new_ical_string
    event.save()

**Summary of the new data API:**

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Method / property
     - Purpose
   * - ``event.get_data()``
     - Raw iCalendar string, always a copy
   * - ``event.get_icalendar_instance()``
     - icalendar.Calendar copy, safe for read-only use
   * - ``event.get_vobject_instance()``
     - vobject component copy, safe for read-only use
   * - ``event.component``
     - Alias for the inner VEVENT/VTODO/VJOURNAL component (copy)
   * - ``event.edit_icalendar_instance()``
     - Context manager — exclusive write access via icalendar
   * - ``event.edit_vobject_instance()``
     - Context manager — exclusive write access via vobject
   * - ``event.data = "..."``
     - Replace all data from a raw string


New in v3.x
============

Async client
-------------

Async operations are often the "best current practice" in the Python world.  Now it's possible also with the CalDAV library.

A new :class:`caldav.async_davclient.AsyncDAVClient` provides the same API
with ``async/await`` support.  All domain objects (``Calendar``, ``Event``,
``Todo``, …) work with both the sync and async clients:

.. code-block:: python

    from caldav.async_davclient import get_davclient

    async def main():
        async with await get_davclient(url="...", username="...",
                                       password="...") as client:
            principal = await client.get_principal()
            calendars = await principal.get_calendars()
            for cal in calendars:
                events = await cal.get_events()

See :doc:`async` for more details.

JMAP client (experimental)
---------------------------

A new ``caldav.jmap`` package provides ``JMAPClient`` and ``AsyncJMAPClient``
for servers implementing :rfc:`8620` (JMAP Core) and :rfc:`8984` (JMAP Calendars).
The public API may change in minor releases.  See :doc:`jmap`.

Advanced search
---------------

The new ``CalDAVSearcher`` / ``calendar.searcher()`` API allows building
composite search queries:

.. code-block:: python

    from caldav import CalDAVSearcher, Todo

    searcher = calendar.searcher()
    searcher.add_property_filter("category", "WORK")
    searcher.add_property_filter("status", "NEEDS-ACTION")
    todos = searcher.search(calendar)

    # Or as a one-liner
    searcher = CalDAVSearcher(comp_class=Todo)
    searcher.add_property_filter("category", "WORK", case_sensitive=False)
    results = searcher.search(calendar)

Compatibility hints / ``features`` parameter
--------------------------------------------

Server-specific quirks are now encoded in named profiles in
``caldav/compatibility_hints.py``.  Pass the profile name via the ``features``
parameter to get automatic workarounds:

.. code-block:: python

    client = get_davclient(url="https://...", features="nextcloud",
                           username="alice", password="secret")

You can also override individual flags:

.. code-block:: python

    client = get_davclient(url="https://...",
                           features={"search.text": {"support": "unsupported"}})

In the config file it's possible to combine a base profile with overrides in the config file:

.. code-block:: yaml

    my-server:
        caldav_url: https://caldav.example.com/
        caldav_username: alice
        caldav_password: secret
        features:
            base: nextcloud
            search.text: unsupported

See :ref:`about:Compatibility` for more on the compatibility hints system.

Object UID as ``.id``
----------------------

``CalendarObjectResource.id`` is now available as a shortcut for the
``UID`` property:

.. code-block:: python

    event = calendar.add_event(ical_string)
    print(event.id)   # same as event.icalendar_component["UID"]

Other notable changes
---------------------

caldav 3.x uses **niquests** by default for HTTP communication.  Niquests is a
backward-compatible fork of requests that adds HTTP/2, HTTP/3, and async
support.  If you need to switch to ``requests`` or ``httpx``, see
:doc:`http-libraries`.

Rate-limit support is now built into the CalDAV library.  Pass
``rate_limit_handle=True`` to automatically sleep and retry on ``429
Too Many Requests`` / ``503 Service Unavailable`` responses that
include a ``Retry-After`` header:

.. code-block:: python

    client = get_davclient(url="...", rate_limit_handle=True)

This may also be configured:

.. code-block:: yaml

    my-server:
        caldav_url: https://caldav.example.com/
        caldav_username: alice
        caldav_password: secret
        features:
	    rate_limit:
	        enable: True
		default_sleep: 4
		max_sleep: 120

If the server gives a `retry-after`-header on 429 or 530 it will be respected, otherwise the `default_sleep` will be utilized on 429.  This happens in a loop, the sleep period will be multiplied with 1.5 on every retry.

The total sleep period will never exceed 120, no matter if retry-after is given or not.

Deprecated in v3.x
==================

The following emit ``DeprecationWarning`` and may be removed in v4.0:

* ``calendar.date_search()`` — use ``calendar.search()``
* ``client.principals()`` — use ``client.search_principals()``
* ``obj.split_expanded`` attribute
* ``obj.expand_rrule`` attribute
* ``.instance`` property on calendar objects — use ``.vobject_instance``
* ``response.find_objects_and_props()`` — use ``response.results``

The following are deprecated, do **not yet** emit warnings and may be removed in v5.0:

* All ``save_*`` methods → use ``add_*``
* All ``*_by_uid()`` methods → use ``get_*_by_uid()``
* ``principal.calendars()`` → ``principal.get_calendars()``
* ``calendar.events()`` → ``calendar.get_events()``
* ``calendar.todos()`` → ``calendar.get_todos()``
* ``calendar.journals()`` → ``calendar.get_journals()``
* ``calendar.objects_by_sync_token()`` → ``calendar.get_objects_by_sync_token()``
* ``client.principal()`` → ``client.get_principal()``
* ``client.check_dav_support()`` → ``client.supports_dav()``
* ``client.check_cdav_support()`` → ``client.supports_caldav()``
* ``client.check_scheduling_support()`` → ``client.supports_scheduling()``
