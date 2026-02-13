========
Tutorial
========

This tutorial covers basic usage of the python CalDAV client library.
Copy code examples into a file and add a ``breakpoint()`` inside the
with-block to inspect return objects. Do not name your file `caldav.py`
or `calendar.py`, as this may break imports.

Ad-hoc Configuration
--------------------

To run the tutorial examples against a test server, you need:

* The caldav source with tests: ``git clone https://github.com/python-caldav/caldav.git ; cd caldav``
* Radicale installed: ``pip install radicale``
* Environment variable set: ``export PYTHON_CALDAV_USE_TEST_SERVER=1``

With this setup, the with-blocks below will spin up a Radicale server.


Real Configuration
------------------

The recommended way to configure caldav is through a config file or
environment variables. Create ``~/.config/caldav/caldav.conf``:

.. code-block:: ini

    # ~/.config/caldav/caldav.conf
    [default]
    url = https://caldav.example.com/
    username = alice
    password = secret

Or set environment variables:

.. code-block:: bash

    # export CALDAV_URL=https://caldav.example.com/
    # export CALDAV_USERNAME=alice
    # export CALDAV_PASSWORD=secret

With configuration in place, you can use caldav without hardcoding credentials:

.. code-block:: python

    from caldav import get_calendars

    with get_calendars() as calendars:
        for cal in calendars:
            print(cal.get_display_name())

Getting Calendars
-----------------

Use :func:`caldav.get_calendars` to get all calendars or filter by name:

.. code-block:: python

    from caldav import get_calendars, get_calendar, get_davclient

    # First create a calendar to work with
    with get_davclient() as client:
        my_principal = client.principal()
        my_principal.make_calendar(name="Work")

    # Get all calendars
    with get_calendars() as calendars:
        for cal in calendars:
            print(cal.get_display_name())

    # Get a specific calendar by name
    with get_calendar(calendar_name="Work") as work_calendar:
        if work_calendar:
            events = work_calendar.search(event=True)

Creating Calendars and Events
-----------------------------

Create a test calendar and add an event:

.. code-block:: python

    from caldav import get_davclient
    import datetime

    with get_davclient() as client:
        my_principal = client.principal()
        my_new_calendar = my_principal.make_calendar(name="Test calendar")
        may17 = my_new_calendar.add_event(
            dtstart=datetime.datetime(2020,5,17,8),
            dtend=datetime.datetime(2020,5,18,1),
            uid="may17",
            summary="Do the needful",
            rrule={'FREQ': 'YEARLY'})

Add an event from icalendar data:

.. code-block:: python

    from caldav import get_davclient

    with get_davclient() as client:
        my_principal = client.principal()
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

Searching
---------

Use search to find events, tasks, or journals:

.. code-block:: python

    from caldav import get_davclient
    from datetime import date
    import datetime

    with get_davclient() as client:
        my_principal = client.principal()
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

The ``expand`` parameter expands recurring events into individual
occurrences within the search interval. The ``event=True`` parameter
filters results to events only (excluding tasks and journals).

Modifying Events
----------------

The ``data`` property contains icalendar data as a string:

.. code-block:: python

    from caldav import get_davclient
    from datetime import date
    import datetime

    with get_davclient() as client:
        my_principal = client.principal()
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
        my_events[0].data = my_events[0].data.replace("Do the needful", "Have fun!")
        my_events[0].save()

Better practice is to use the icalendar library. The ``component``
property gives access to the :class:`icalendar.cal.Event` object:

.. code-block:: python

    from caldav import get_davclient
    from datetime import date
    import datetime

    with get_davclient() as client:
        my_principal = client.principal()
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
        print(f"Event starts at {my_events[0].component.start}")
        with my_events[0].edit_icalendar_instance() as cal:
            cal.subcomponents[0]['summary'] = "Norwegian national day celebrations"
        my_events[0].save()

Tasks
-----

Create a task list and work with tasks:

.. code-block:: python

    from caldav import get_davclient
    from datetime import date

    with get_davclient() as client:
        my_principal = client.principal()
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

Further Reading
---------------

See the :ref:`examples:examples` folder for more code, including
`basic examples <https://github.com/python-caldav/caldav/blob/master/examples/basic_usage_examples.py>`_
and `scheduling examples <https://github.com/python-caldav/caldav/blob/master/examples/scheduling_examples.py>`_
for invites.

The `test code <https://github.com/python-caldav/caldav/blob/master/tests/test_caldav.py>`_
covers most features.

There is also a `command line interface <https://github.com/tobixen/plann>`_
built around the caldav library.
