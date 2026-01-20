====================
Async API
====================

The caldav library provides an async-first API for use with Python's
``asyncio``. This is useful when you need to:

* Make concurrent requests to the server
* Integrate with async web frameworks (FastAPI, aiohttp, etc.)
* Build responsive applications that don't block on I/O

Quick Start
===========

The async API is available through the ``caldav.aio`` module:

.. code-block:: python

    import asyncio
    from caldav import aio

    async def main():
        async with aio.get_async_davclient() as client:
            principal = await client.principal()
            calendars = await principal.get_calendars()
            for cal in calendars:
                print(f"Calendar: {cal.name}")
                events = await cal.get_events()
                print(f"  {len(events)} events")

    asyncio.run(main())

The async API mirrors the sync API, but all I/O operations are ``async``
methods that must be awaited.

Available Classes
=================

The ``caldav.aio`` module exports:

**Client:**

* ``AsyncDAVClient`` - The main client class
* ``AsyncDAVResponse`` - Response wrapper
* ``get_async_davclient()`` - Factory function (recommended)

**Calendar Objects:**

* ``AsyncEvent`` - Calendar event
* ``AsyncTodo`` - Task/todo item
* ``AsyncJournal`` - Journal entry
* ``AsyncFreeBusy`` - Free/busy information

**Collections:**

* ``AsyncCalendar`` - A calendar
* ``AsyncCalendarSet`` - Collection of calendars
* ``AsyncPrincipal`` - User principal

**Scheduling (RFC6638):**

* ``AsyncScheduleInbox`` - Incoming invitations
* ``AsyncScheduleOutbox`` - Outgoing invitations

Example: Working with Calendars
===============================

.. code-block:: python

    import asyncio
    from caldav import aio
    from datetime import datetime, date

    async def calendar_demo():
        async with aio.get_async_davclient() as client:
            principal = await client.principal()

            # Create a new calendar
            my_calendar = await principal.make_calendar(
                name="My Async Calendar"
            )

            # Add an event
            event = await my_calendar.add_event(
                dtstart=datetime(2025, 6, 15, 10, 0),
                dtend=datetime(2025, 6, 15, 11, 0),
                summary="Team meeting"
            )

            # Search for events
            events = await my_calendar.search(
                event=True,
                start=date(2025, 6, 1),
                end=date(2025, 7, 1)
            )
            print(f"Found {len(events)} events")

            # Clean up
            await my_calendar.delete()

    asyncio.run(calendar_demo())

Example: Parallel Operations
============================

One of the main benefits of async is the ability to run operations
concurrently:

.. code-block:: python

    import asyncio
    from caldav import aio

    async def fetch_all_events():
        async with aio.get_async_davclient() as client:
            principal = await client.principal()
            calendars = await principal.get_calendars()

            # Fetch events from all calendars in parallel
            tasks = [cal.get_events() for cal in calendars]
            results = await asyncio.gather(*tasks)

            for cal, events in zip(calendars, results):
                print(f"{cal.name}: {len(events)} events")

    asyncio.run(fetch_all_events())

Migration from Sync to Async
============================

The async API closely mirrors the sync API. Here are the key differences:

1. **Import from ``caldav.aio``:**

   .. code-block:: python

       # Sync
       from caldav import DAVClient, get_davclient

       # Async
       from caldav import aio
       # Use: aio.AsyncDAVClient, aio.get_async_davclient()

2. **Use ``async with`` for context manager:**

   .. code-block:: python

       # Sync
       with get_davclient() as client:
           ...

       # Async
       async with aio.get_async_davclient() as client:
           ...

3. **Await all I/O operations:**

   .. code-block:: python

       # Sync
       principal = client.principal()
       calendars = principal.get_calendars()
       events = calendar.get_events()

       # Async
       principal = await client.principal()
       calendars = await principal.get_calendars()
       events = await calendar.get_events()

4. **Property access for cached data remains sync:**

   Properties that don't require I/O (like ``url``, ``name``, ``data``)
   are still regular properties:

   .. code-block:: python

       # These work the same in both sync and async
       print(calendar.url)
       print(calendar.name)
       print(event.data)

Method Reference
================

The async classes have the same methods as their sync counterparts.
All methods that perform I/O are ``async`` and must be awaited:

**AsyncDAVClient:**

* ``await client.principal()`` - Get the principal
* ``client.calendar(url=...)`` - Get a calendar by URL (no await, no I/O)

**AsyncPrincipal:**

* ``await principal.get_calendars()`` - List all calendars
* ``await principal.make_calendar(name=...)`` - Create a calendar
* ``await principal.calendar(name=...)`` - Find a calendar

**AsyncCalendar:**

* ``await calendar.get_events()`` - Get all events
* ``await calendar.get_todos()`` - Get all todos
* ``await calendar.search(...)`` - Search for objects
* ``await calendar.add_event(...)`` - Create an event
* ``await calendar.add_todo(...)`` - Create a todo
* ``await calendar.get_event_by_uid(uid)`` - Find event by UID
* ``await calendar.delete()`` - Delete the calendar
* ``await calendar.get_supported_components()`` - Get supported types

**AsyncEvent, AsyncTodo, AsyncJournal:**

* ``await obj.load()`` - Load data from server
* ``await obj.save()`` - Save changes to server
* ``await obj.delete()`` - Delete the object
* ``await todo.complete()`` - Mark todo as complete

Backward Compatibility
======================

The sync API (``caldav.DAVClient``, ``caldav.get_davclient()``) continues
to work exactly as before. The sync API now uses the async implementation
internally, with a thin sync wrapper.

This means:

* Existing sync code works without changes
* You can migrate to async gradually
* Both sync and async code can coexist in the same project

Example Files
=============

See the ``examples/`` directory for complete examples:

* ``examples/async_usage_examples.py`` - Comprehensive async examples
* ``examples/basic_usage_examples.py`` - Sync examples (for comparison)
