========
Tutorial
========

In this tutorial you should learn basic usage of the python CalDAV
client library.  You are encouraged to copy the code examples into a
file and add a ``breakpoint()`` inside the with-block so you can
inspect the return objects you get from the library calls.  Do not
name your file `caldav.py` or `calendar.py`, this may break some
imports.

To follow this tutorial as intended, each code block should be run
towards a clean-slate Radicale server.  To do this, you need:

* The source code of caldav with tests: ``git clone https://github.com/python-caldav/caldav.git ; cd caldav``
* The Radicale python package: ``pip install radicale``
* An environmental variable set: ``export PYTHON_CALDAV_USE_TEST_SERVER=1``

With this setup, the with-blocks in the code sections below will spin
up a Radicale server.

When you've run the tutorial as intended, I recommend going through the examples again towards your own calendar server:

* Set the environment variables ``CALDAV_URL``, ``CALDAV_USER`` and ``CALDAV_PASSWORD`` to point to your personal calendar server.
* Be aware that different calendar servers may behave differently.  For instance, not all of them allows you to create a calendar.  Some are even read-only.
* You will need to revert all changes done.  The code examples below do not do any cleanup.  If your calendar server supports creating and deleting calendars, then it should be easy enough: ``my_new_calendar.delete()`` inside the with-block.  Events also has a ``.delete()``-method.  Beware that there is no ``undo``.  You're advised to have a local backup of your calendars.  I'll probably write a HOWTO on that one day.
* Usage of a context manager is considered best practice, but not really needed – you may skip the with-statement and write just ``client = get_davclient()``.  This will make it easier to test code from the python shell.

Quick Start: Getting Calendars Directly
---------------------------------------

As of 3.0, there are convenience functions to get calendars directly
without manually creating a client and principal:

.. code-block:: python

    from caldav import get_calendars, get_calendar

    # Get all calendars
    calendars = get_calendars(
        url="https://caldav.example.com/",
        username="alice",
        password="secret"
    )
    for cal in calendars:
        print(f"Found calendar: {cal.name}")

    # Get a specific calendar by name
    work_calendar = get_calendar(
        url="https://caldav.example.com/",
        username="alice",
        password="secret",
        calendar_name="Work"
    )

    # Get calendars by URL or ID
    calendars = get_calendars(
        url="https://caldav.example.com/",
        username="alice",
        password="secret",
        calendar_url="/calendars/alice/personal/"  # or just "personal"
    )

These functions also support reading configuration from environment
variables (``CALDAV_URL``, ``CALDAV_USERNAME``, ``CALDAV_PASSWORD``)
or config files, so you can simply call:

.. code-block:: python

    from caldav import get_calendars
    calendars = get_calendars()  # Uses env vars or config file

The Traditional Approach
------------------------

As of 2.0, it's recommended to start initiating a
:class:`caldav.davclient.DAVClient` object using the ``get_davclient``
function, go from there to get a
:class:`caldav.collection.Principal`-object, and from there find a
:class:`caldav.collection.Calendar`-object.  This is how to do it:

.. code-block:: python

    from caldav import get_davclient
    from caldav.lib.error import NotFoundError

    with get_davclient() as client:
        my_principal = client.get_principal()
        try:
            my_calendar = my_principal.calendar()
            print(f"A calendar was found at URL {my_calendar.url}")
        except NotFoundError:
            print("You don't seem to have any calendars")

Caveat: Things will break if password/url/username is wrong, but
perhaps not where you expect it to.  To test, you may try out
``get_davclient(username='alice', password='hunter2', url='https://calendar.example.com/dav/')``.

The ``calendar``-method above gives one calendar – if you have more
calendars, it will give you the first one it can find – which may not
be the correct one.  To filter there are parameters ``name`` and
``cal_id`` – I recommend testing them:

.. code-block:: python

    from caldav import get_davclient
    from caldav.lib.error import NotFoundError

    with get_davclient() as client:
        my_principal = client.get_principal()
        try:
            my_calendar = my_principal.calendar(name="My Calendar")
        except NotFoundError:
            print("You don't seem to have a calendar named 'My Calendar'")

If you happen to know the URL or path for the calendar, you don't need
to go through the principal object.

.. code-block:: python

    from caldav import get_davclient

    with get_davclient() as client:
        my_calendar = client.calendar(url="/dav/calendars/mycalendar")

Note that in the example above, no communication is done.  If the URL is wrong, you will only know it when trying to save or get objects from the server!

For servers that support it, it may be useful to create a dedicated test calendar – that way you can test freely without risking to mess up your calendar events.  Let's populate it with an event while we're at it:

.. code-block:: python

    from caldav import get_davclient
    import datetime

    with get_davclient() as client:
        my_principal = client.get_principal()
        my_new_calendar = my_principal.make_calendar(name="Test calendar")
        may17 = my_new_calendar.add_event(
            dtstart=datetime.datetime(2020,5,17,8),
            dtend=datetime.datetime(2020,5,18,1),
            uid="may17",
            summary="Do the needful",
            rrule={'FREQ': 'YEARLY'})

You have icalendar code and want to put it into the calendar?  Easy!

.. code-block:: python

    from caldav import get_davclient

    with get_davclient() as client:
        my_principal = client.get_principal()
        my_new_calendar = my_principal.make_calendar(name="Test calendar")
        may17 = my_new_calendar.add_event("""BEGIN:VCALENDAR
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

The best way of getting information out from the calendar is to use the search.  Currently most of the logic is done on the server side – and the different calendar servers tend to give different results given the same data and search query.  In future versions of the CalDAV library the intention is to do more workarounds and logic on the client side, allowing for more consistent results across different servers.

.. code-block:: python

    from caldav import get_davclient
    from datetime import date

    with get_davclient() as client:
        my_principal = client.get_principal()
        my_new_calendar = my_principal.make_calendar(name="Test calendar")
        my_new_calendar.add_event(
            dtstart=datetime.datetime(2023,5,17,8),
            dtend=datetime.datetime(2023,5,18,1),
            uid="may17",
            summary="Do the needful",
            rrule={'FREQ': 'YEARLY'})

        my_events = my_new_calendar.search(
            event=True,
            start=date(2026,5,1),
            end=date(2026,6,1),
            expand=True)

        assert len(my_events) == 1
        print(my_events[0].data)

``expand`` matters for recurring events and tasks, instead of getting returned the original event (with ``DTSTART`` set in 2023 and an ``RRULE`` set) it will return the *recurrence* for year 2026.  Or, rather, a list of recurrences if there are more of them in the search interval.

``event`` causes the search to only return events.  There are three kinds of objects that can be saved to a calendar (but not all servers support all three) – events, journals and tasks (``VEVENT``, ``VJOURNAL`` and ``VTODO``).  This is called Calendar Object Resources in the RFC.  Now that's quite a mouthful!  To ease things, the word "event" is simply used in documentation and communication.  So when reading "event", be aware that it actually means "a CalenderObjectResource objects such as an event, but it could also be a task or a journal" – and if you contribute code, remember to use ``CalendarObjectResource`` rather than ``Event``.

Without ``event=True`` explicitly set, all kinds of objects *should* be returned.  Unfortunately many servers returns nothing – so as of 2.0, it's important to always specify if you want events, tasks or journals.  In future versions of CalDAV there will be workarounds for this so ``event=True`` can be safely skipped, regardless what server is used.

The return type is a list of objects of the type :class:`caldav.calendarobjectresource.Event` – for tasks and journals there are similar classes Todo and Journal.

The ``data`` property delivers the icalendar data as a string.  It can be modified:

.. code-block:: python

    from caldav import get_davclient
    from datetime import date

    with get_davclient() as client:
        my_principal = client.get_principal()
        my_new_calendar = my_principal.make_calendar(name="Test calendar")
        my_new_calendar.add_event(
            dtstart=datetime.datetime(2023,5,17,8),
            dtend=datetime.datetime(2023,5,18,1),
            uid="may17",
            summary="Do the needful",
            rrule={'FREQ': 'YEARLY'})

        my_events = my_new_calendar.search(
            start=date(2026,5,1),
            end=date(2026,6,1),
            expand=True)

        assert len(my_events) == 1
        my_events[0].data = my_events[0].data.replace("Do the needful", "Have fun!")
        my_events[0].save()

As seen above, we can use ``save()`` to send a modified object back to
the server.  In the case above, we've edited a recurrence.  Now that
we've saved the object, you're encouraged to test with search with and
without expand set and with different years, print out
``my_event[0].data`` and see what results you'll get.  The
``save()``-method also takes a parameter ``all_recurrences=True`` if
you want to edit the full series!

The code above is far from "best practice".  You should not try to
parse or modify ``event.data`` directly.  Use the icalendar library instead.

Most events contain one *component* (always true when using ``expand=True``).
The ``event.component`` property gives easy access to the
:class:`icalendar.cal.Event`-object.  To edit, use ``edit_icalendar_instance()``:

.. code-block:: python

    from caldav import get_davclient
    from datetime import date

    with get_davclient() as client:
        my_principal = client.get_principal()
        my_new_calendar = my_principal.make_calendar(name="Test calendar")
        my_new_calendar.add_event(
            dtstart=datetime.datetime(2023,5,17,8),
            dtend=datetime.datetime(2023,5,18,1),
            uid="may17",
            summary="Do the needful",
            rrule={'FREQ': 'YEARLY'})

        my_events = my_new_calendar.search(
            start=date(2026,5,1),
            end=date(2026,6,1),
            expand=True)

        assert len(my_events) == 1
        print(f"Event starts at {my_events[0].component.start}")
        with my_events[0].edit_icalendar_instance() as cal:
            cal.subcomponents[0]['summary'] = "Norwegian national day celebrations"
        my_events[0].save()

How to do operations on components in the icalendar library is outside the scope of this tutorial.

Usually tasks and journals can be applied directly to the same calendar as the events – but some implementations (notably Zimbra) have "task lists" and "calendars" as distinct entities.  To create a task list, there is a parameter ``supported_calendar_component_set`` that can be set to ``['VTODO']``.  Here is a quick example that features a task:

.. code-block:: python

    from caldav import get_davclient
    from datetime import date

    with get_davclient() as client:
        my_principal = client.get_principal()
        my_new_calendar = my_principal.make_calendar(
            name="Test calendar", supported_calendar_component_set=['VTODO'])
        my_new_calendar.add_todo(
            summary="prepare for the Norwegian national day", due=date(2025,5,16))

        my_tasks = my_new_calendar.search(
            todo=True)
        assert len(my_tasks) == 1
        my_tasks[0].complete()
        my_tasks = my_new_calendar.search(
            todo=True)
        assert len(my_tasks) == 0
        my_tasks = my_new_calendar.search(
            todo=True, include_completed=True)
        assert len(my_tasks) == 1


There are more functionality, but if you've followed the tutorial to this point, you should already know eough to deal with the very most use-cases.

There are some more :ref:`examples:examples` in the examples folder, particularly `basic examples <https://github.com/python-caldav/caldav/blob/master/examples/basic_usage_examples.py>`_. There is also a `scheduling examples <https://github.com/python-caldav/caldav/blob/master/examples/scheduling_examples.py>`_ for sending, receiving and replying to invites, though this is not very well-tested so far.  The example code is currently not tested nor maintained.  Some of it will be moved into the documentation as tutorials or how-tos eventually.

The `test code <https://github.com/python-caldav/caldav/blob/master/tests/test_caldav.py>`_ also covers most of the features available, though it's not much optimized for readability (at least not as of 2025-05).

Tobias Brox is also working on a `command line interface <https://github.com/tobixen/plann>`_  built around the caldav library.
