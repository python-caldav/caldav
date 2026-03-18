==============
Async Tutorial
==============

This tutorial covers async usage of the Python CalDAV client library.
It mirrors :doc:`tutorial`, but uses the ``caldav.aio`` module.  This
tutorial assumes you've already browsed through the sync tutorial.

Copy code examples into a Python file and run them with ``python``.  Do not
name your file ``caldav.py`` or ``calendar.py``, as this may break imports.

All examples run inside an ``async def`` function launched via
``asyncio.run()``.  You are encouraged to add a ``breakpoint()`` inside the
``async with`` blocks to inspect return objects.

Go through the tutorial twice, first against a Xandikos test server, and then
against a server of your own choice.

Configuration
-------------

The same applies here as in the sync tutorial, use ``export PYTHON_CALDAV_USE_TEST_SERVER=1`` and install Xandikos and the instructions below will give you a test server.  Unset ``PYTHON_CALDAV_USE_TEST_SERVER`` and edit ``~/.config/caldav/calendar.conf`` or adjust the environment variables to test with a real server.

Creating Calendars
------------------

The async API lives in ``caldav.aio``.  Obtain a client by awaiting
:func:`~caldav.aio.get_async_davclient`, then use it as an async context
manager.  When the ``async with`` block exits the HTTP session is closed.

.. code-block:: python

    import asyncio
    from caldav import aio

    async def main():
        client = await aio.get_async_davclient()
        async with client:
            my_principal = await client.get_principal()
            my_new_calendar = await my_principal.make_calendar(name="Teest calendar")
            ## Enable the debug breakpoint to investigate the calendar object
            #breakpoint()
            await my_new_calendar.delete()

    asyncio.run(main())

The delete step is unimportant when running towards an ephemeral test server.

The async version probes the server with an OPTIONS request by default (``probe=True``).  It may and may not cause an immediate failure on wrong credentials, depending on the server setup.  Feel free to play with it.  This code will never fail:

.. code-block:: python

    import asyncio
    from caldav import aio

    async def main():
        ## Invalid domain, invalid password ...
        ## ... this probably ought to raise an error?
        client = await aio.get_async_davclient(
            username='alice',
            password='hunter2',
            url='https://calendar.example.com/dav/',
            probe=False)
        async with client:
            ...

    asyncio.run(main())

Accessing Calendars
-------------------

Use :func:`aio.get_calendars` to list all calendars in one call.  Like the
sync version it returns a collection that can be used as an async context
manager — the HTTP session is terminated on exit:

.. code-block:: python

    import asyncio
    from caldav import aio

    async def main():
        async with await aio.get_calendars() as calendars:
            for calendar in calendars:
                print(f"Calendar \"{await calendar.get_display_name()}\" has URL {calendar.url}")

    asyncio.run(main())

:func:`aio.get_calendar` is the async counterpart of :func:`caldav.get_calendar`
and is the **recommended starting point** for most code:

.. code-block:: python

    import asyncio
    from caldav import aio

    async def main():
        async with await aio.get_calendar() as calendar:
            print(f"Calendar \"{await calendar.get_display_name()}\" has URL {calendar.url}")
            ## You may add a debugger breakpoint and investigate the object
            #breakpoint()

    asyncio.run(main())

The calendar has a ``.client`` property which gives the client.

Creating Events
---------------

From the :class:`~caldav.collection.Calendar` object, use
:meth:`~caldav.collection.Calendar.add_event` to create an event:

.. code-block:: python

    import asyncio
    import datetime
    from caldav import aio

    async def main():
        async with await aio.get_calendar() as cal:
            ## Add a may 17 event
            may17 = await cal.add_event(
                dtstart=datetime.datetime(2020,5,17,8),
                dtend=datetime.datetime(2020,5,18,1),
                uid="may17",
                summary="Do the needful",
                rrule={'FREQ': 'YEARLY'})
            ## You may want to inspect the event
            #breakpoint()

    asyncio.run(main())

You have icalendar code and want to put it into the calendar?  Easy!

.. code-block:: python

    import asyncio
    from caldav import aio

    async def main():
        async with await aio.get_calendar() as cal:
            may17 = await cal.add_event("""BEGIN:VCALENDAR
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
            #breakpoint()

    asyncio.run(main())


Searching
---------

The search API is identical to the sync version; just add ``await``:

.. code-block:: python

    import asyncio
    from caldav import aio
    from datetime import datetime, date

    async def main():
        async with await aio.get_calendar() as cal:
            await cal.add_event(
                dtstart=datetime(2023,5,17,8),
                dtend=datetime(2023,5,18,1),
                uid="may17",
                summary="Do the needful",
                rrule={'FREQ': 'YEARLY'})

            my_events = await cal.search(
                event=True,
                start=date(2026,5,1),
                end=date(2026,6,1),
                expand=True)

            print(my_events[0].data)
            #breakpoint()

    asyncio.run(main())

The ``expand``, ``event``, and other parameters work exactly as in the sync
API.  See the sync tutorial for a full explanation of the search options.

Investigating Events
--------------------

Use ``.data`` for raw icalendar data, or
:meth:`~caldav.calendarobjectresource.CalendarObjectResource.get_icalendar_component`
for convenient property access:

.. code-block:: python

    import asyncio
    from caldav import aio
    from datetime import datetime, date

    async def main():
        async with await aio.get_calendar() as cal:
            await cal.add_event(
                dtstart=datetime(2023,5,17,8),
                dtend=datetime(2023,5,18,1),
                uid="may17",
                summary="Do the needful",
                rrule={'FREQ': 'YEARLY'})

            my_events = await cal.search(
                event=True,
                start=date(2026,5,1),
                end=date(2026,6,1),
                expand=True)

            print(my_events[0].get_icalendar_component()['summary'])
            print(my_events[0].get_icalendar_component().duration)
            #breakpoint()

    asyncio.run(main())

The caveat about recurring events from the sync tutorial applies here too:
``get_icalendar_component()`` is safe after an expanded search.

Modifying Events
----------------

Replace the raw ``data`` string:

.. code-block:: python

    import asyncio
    from caldav import aio
    from datetime import date
    import datetime

    async def main():
        async with await aio.get_calendar() as cal:
            await cal.add_event(
                dtstart=datetime.datetime(2023,5,17,8),
                dtend=datetime.datetime(2023,5,18,1),
                uid="may17",
                summary="Do the needful",
                rrule={'FREQ': 'YEARLY'})

            my_events = await cal.search(
                event=True,
                start=date(2026,5,1),
                end=date(2026,6,1),
                expand=True)

            my_events[0].data = my_events[0].data.replace("Do the needful", "Have fun!")
            await my_events[0].save()
            #breakpoint()

    asyncio.run(main())

Best practice is to use
:meth:`~caldav.calendarobjectresource.CalendarObjectResource.edit_icalendar_component`:

.. code-block:: python

    import asyncio
    from caldav import aio
    from datetime import date
    import datetime

    async def main():
        async with await aio.get_calendar() as cal:
            await cal.add_event(
                dtstart=datetime.datetime(2023,5,17,8),
                dtend=datetime.datetime(2023,5,18,1),
                uid="may17",
                summary="Do the needful",
                rrule={'FREQ': 'YEARLY'})

            my_events = await cal.search(
                event=True,
                start=date(2026,5,1),
                end=date(2026,6,1),
                expand=True)

            ## Edit the summary using the "borrowing pattern":
            with my_events[0].edit_icalendar_component() as event_ical:
                ## "component" is always safe after an expanded search
                event_ical['summary'] = "Norwegian national day celebrations"
            await my_events[0].save()

            ## Let's take out the event again:
            may17 = await cal.get_event_by_uid('may17')

            ## Inspect may17 in a debug breakpoint
            #breakpoint()

    asyncio.run(main())

Note that ``edit_icalendar_component()`` is a plain (synchronous) context
manager — no ``await`` or ``async with`` needed there.

Tasks
-----

Tasks work just like events, with ``await`` added:

.. code-block:: python

    import asyncio
    from caldav import aio
    from datetime import date

    async def main():
        client = await aio.get_async_davclient()
        async with client:
            my_principal = await client.get_principal()
            ## This can be read as "create me a tasklist"
            cal = await my_principal.make_calendar(
                name="Test tasklist", supported_calendar_component_set=['VTODO'])
            ## ... but for most servers it's an ordinary calendar!
            await cal.add_todo(
                summary="prepare for the Norwegian national day", due=date(2025,5,16))

            my_tasks = await cal.search(todo=True)
            assert len(my_tasks) == 1
            await my_tasks[0].complete()
            my_tasks = await cal.search(todo=True)
            assert len(my_tasks) == 0
            my_tasks = await cal.search(todo=True, include_completed=True)
            assert my_tasks

    asyncio.run(main())

The :meth:`~caldav.calendarobjectresource.Todo.complete` method is awaitable in
async mode.  See the sync tutorial for a note on tasklist vs calendar support
differences between servers.

Parallel Operations
-------------------

The main benefit of the async API is the ability to run multiple I/O operations
*concurrently* using :func:`asyncio.gather`.  The following example fetches
events from all calendars at the same time, instead of one by one:

.. code-block:: python

    import asyncio
    from caldav import aio

    async def main():
        async with await aio.get_calendars() as calendars:
            ## Kick off all searches in parallel, then collect the results
            results = await asyncio.gather(
                *[cal.search(event=True) for cal in calendars])

            for cal, events in zip(calendars, results):
                print(f"{await cal.get_display_name()}: {len(events)} event(s)")

    asyncio.run(main())

``asyncio.gather`` runs all the coroutines concurrently.  For a single server
the speed gain is modest (one connection), but when talking to multiple servers
or doing many independent fetches the difference can be significant.

Further Reading
---------------

See the :ref:`examples:examples` folder for more code, including
`async examples <https://github.com/python-caldav/caldav/blob/master/examples/async_usage_examples.py>`_
and `sync examples <https://github.com/python-caldav/caldav/blob/master/examples/basic_usage_examples.py>`_
for comparison.

See :doc:`async` for the async API reference, including a migration guide from
the sync API.

The `integration tests <https://github.com/python-caldav/caldav/blob/master/tests/test_async_integration.py>`_
cover most async features.
