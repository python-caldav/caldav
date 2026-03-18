========
Tutorial
========

This tutorial covers basic usage of the python CalDAV client library.
Copy code examples into a file.  You are encouraged to add a
``breakpoint()`` inside the with-block to inspect return objects. Do
not name your file ``caldav.py`` or ``calendar.py``, as this may break
imports.

Go through the tutorial twice, first against a Xandikos test server,
and then against a server of your own choice.

This tutorial only covers the sync API.  The async API is quite
similar.  A tutorial on the async API will come soon.

Ad-hoc Configuration
--------------------

This is needed to get this tutorial working with Xandikos:

* Xandikos installed: ``pip install xandikos``
* Environment variable set: ``export PYTHON_CALDAV_USE_TEST_SERVER=1``

With this setup, the with-blocks below will spin up Xandikos servers.  The Xandikos server is by default populated with one calendar.

Real Configuration
------------------

Edit ``~/.config/caldav/calendar.conf``:

.. code-block:: yaml

    # ~/.config/caldav/calendar.conf
    ---
    default:
        caldav_url: https://caldav.example.com/
        caldav_username: alice
        caldav_password: secret
        features: xandikos

**Caveat:** De-facto, all CalDAV server implementations seem to have their own dialect of the CalDAV standard.  This tutorial has been tested with Xandikos.  It may or may not work with your server.  For instance, the RFC says "Support for MKCALENDAR on the server is only RECOMMENDED and not REQUIRED", so already on the "Creating Calendars"-section you may get into trouble.  There are some workarounds in the CalDAV library for some servers, you can try to put the name of your server implementation in the ``features``-field.  If it fails, leave the field blank.

Remember to unset the ``PYTHON_CALDAV_USE_TEST_SERVER`` environment variable, if set.

See :doc:`configfile` for the full config file format, including multiple
servers, section inheritance, glob patterns, and calendar selection by name or
URL.

Creating Calendars
------------------

Many servers will start with a "clean slate", with no calendars - so to get anything at all working, it's needed to first create a calendar.  Calendars have to be owned by a principal.  As of v3.0, the way to go is to use the :func:`~caldav.davclient.get_davclient` factory function to get a :class:`caldav.davclient.DAVClient` object, from there  use the :meth:`~caldav.davclient.DAVClient.get_principal` to get the :class:`caldav.collection.Principal`-object of the logged-in principal (user).

.. code-block:: python

    from caldav import get_davclient

    ## Get a client ...
    with get_davclient() as client:
        ## ... from the client get the principal ...
        my_principal = client.get_principal()
        ## ... from the principal we can create calendar ...
        my_new_calendar = my_principal.make_calendar(name="Teest calendar")
        ## Enable the debug breakpoint to investigate the calendar object
        #breakpoint()
        my_new_calendar.delete()

The delete-step is unimportant when running towards an ephemeral test server.

**Tip:** In test mode, the with-block ensures the test server is stopped when done.  It also ensures that the HTTP-session is terminated.  However, for testing things interactively in the python it's a pain.  Usage of the with-block is Best Recommended Practice, but the test server will anyway be terminated when the python process exits, and the HTTP-session will be terminated on timeout or when leaving the test server, whatever comes first.  Feel free to just use ``client = get_davclient()`` while you're testing things.

**Caveat:** In many settings, communication is done lazily when needed.  Things will eventually break if password/url/username is wrong, but perhaps not where you expect it to.  To test, you may try out:

.. code-block:: python

    from caldav import get_davclient
    ## Invalid domain, invalid password ...
    ## ... this probably ought to raise an error?
    with get_davclient(
        username='alice',
        password='hunter2',
        url='https://calendar.example.com/dav/') as client:
        ...

Accessing calendars
-------------------

Use the factory function :func:`caldav.davclient.get_calendars` for listing out all available calendars.  For the clean-slate Xandikos server, there should be one calendar.  You can pass ``url``, ``username`` and ``password`` to the method to test towards your own calendar servers.

.. code-block:: python

    from caldav import get_calendars

    with get_calendars() as calendars:
        for calendar in calendars:
            print(f"Calendar \"{calendar.get_display_name()}\" has URL {calendar.url}")

The :func:`caldav.davclient.get_calendar` will give you one calendar.  **``get_calendar`` should most often be your primary starting point.**  Now please go and play with it:

.. code-block:: python

    from caldav import get_calendar

    with get_calendar() as calendar:
        print(f"Calendar \"{calendar.get_display_name()}\" has URL {calendar.url}")
        ## You may add a debugger breakpoint and investigate the object
        #breakpoint()

The calendar has a ``.client`` property which gives the client.

Creating Events
---------------

From the :class:`caldav.collection.Calendar` object, it's possible to use :meth:`~caldav.collection.Calendar.add_event` (``add_todo``, ``add_object`` and others also exist) for adding an event:

.. code-block:: python

    from caldav import get_calendar
    import datetime

    with get_calendar() as cal:
        ## Add a may 17 event
        may17 = cal.add_event(
            dtstart=datetime.datetime(2020,5,17,8),
            dtend=datetime.datetime(2020,5,18,1),
            uid="may17",
            summary="Do the needful",
            rrule={'FREQ': 'YEARLY'})
        ## You may want to inspect the event
        #breakpoint()

You have icalendar code and want to put it into the calendar?  Easy!

.. code-block:: python

    from caldav import get_calendar

    with get_calendar() as cal:
        may17 = cal.add_event("""BEGIN:VCALENDAR
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


Searching
---------

The best way of getting information out from the calendar is to use the search.  CalDAV defines a way to construct and send search queries, but in reality there are huge problems with compatibility.  With correct configuration of ``features``, the library will work around misbehaving servers, falling back to client-side filtering if needed.

.. code-block:: python

    from caldav import get_calendar
    from datetime import datetime, date

    with get_calendar() as cal:
        cal.add_event(
            dtstart=datetime(2023,5,17,8),
            dtend=datetime(2023,5,18,1),
            uid="may17",
            summary="Do the needful",
            rrule={'FREQ': 'YEARLY'})

        my_events = cal.search(
            event=True,
            start=date(2026,5,1),
            end=date(2026,6,1),
            expand=True)

        print(my_events[0].data)
        #breakpoint()

The ``expand`` parameter matters for recurring objects.  When set it returns all *recurrences* within the search time span.  Try to set the end to 2028 with and without ``expand`` and you will probably understand.

``event`` causes the search to only return events.  There are three kinds of objects that can be saved to a calendar (but not all servers support all three) - events, journals and tasks (``VEVENT``, ``VJOURNAL`` and ``VTODO``).  This is called Calendar Object Resources in the RFC.  Now that's quite a mouthful!  To ease things, the word "event" is simply used in documentation and communication.  So when reading "event", be aware that most of the time it actually means "a CalendarObjectResource objects such as an event, but it could also be a task or a journal" - and if you contribute code, remember to work on objects of type ``CalendarObjectResource`` rather than ``Event``.

The return type is a list of objects of the type :class:`~caldav.calendarobjectresource.Event` - for tasks and journals there are similar classes :class:`~caldav.calendarobjectresource.Todo` and :class:`~caldav.calendarobjectresource.Journal`.

Investigating Events
--------------------

Above, ``.data`` is used to access the icalendar data directly.  There is also :meth:`~caldav.calendarobjectresource.CalendarObjectResource.get_vobject_instance`, :meth:`~caldav.calendarobjectresource.CalendarObjectResource.get_icalendar_instance` and :meth:`~caldav.calendarobjectresource.CalendarObjectResource.get_icalendar_component`, each yielding a copied object.


.. code-block:: python

    from caldav import get_calendar
    from datetime import datetime, date

    with get_calendar() as cal:
        cal.add_event(
            dtstart=datetime(2023,5,17,8),
            dtend=datetime(2023,5,18,1),
            uid="may17",
            summary="Do the needful",
            rrule={'FREQ': 'YEARLY'})

        my_events = cal.search(
            event=True,
            start=date(2026,5,1),
            end=date(2026,6,1),
            expand=True)

        print(my_events[0].get_icalendar_component()['summary'])
        print(my_events[0].get_icalendar_component().duration)
        #breakpoint()

``get_icalendar_component()`` is the easiest way of accessing event data, but there is a **big caveat** there.  Events may be recurring.  The recurring events may have been changed.  Say that you have a meeting every Wed at 10:00, this started in 2024, in 2025 the time was changed to 11:00, at one particular Wed in 2026 the time was pushed to 11:30, the next Wed it was cancelled.  This will be represented as *four* components.  ``.get_icalendar_component`` will only give you access to the original event!  The ``get_icalendar_component()`` is safe to use when doing ``.search(..., expand=True)``, as this will ensure every object is one and only one recurrence.

Modifying Events
----------------

The ``data`` property contains icalendar data as a string, and you can replace it:

.. code-block:: python

    from caldav import get_calendar
    from datetime import date
    import datetime

    with get_calendar() as cal:
        ## Create yearly event ...
        cal.add_event(
            dtstart=datetime.datetime(2023,5,17,8),
            dtend=datetime.datetime(2023,5,18,1),
            uid="may17",
            summary="Do the needful",
            rrule={'FREQ': 'YEARLY'})

        ## Search for a single recurrence
        my_events = cal.search(
            event=True,
            start=date(2026,5,1),
            end=date(2026,6,1),
            expand=True)

        ## Replace the old summary with a new one
        my_events[0].data = my_events[0].data.replace("Do the needful", "Have fun!")
        my_events[0].save()
        #breakpoint()

This is not best practice - the thing above may even break due to line wrapping, etc.  Best practice is to "borrow" an editable icalendar instance through :meth:`~caldav.calendarobjectresource.CalendarObjectResource.edit_icalendar_component` or :meth:`~caldav.calendarobjectresource.CalendarObjectResource.edit_icalendar_instance`.  Note that in the example below we're taking out one particular recurrence, so only that recurrence will be changed.

.. code-block:: python

    from caldav import get_calendar
    from datetime import date
    import datetime

    with get_calendar() as cal:
        ## Create a recurring event
        cal.add_event(
            dtstart=datetime.datetime(2023,5,17,8),
            dtend=datetime.datetime(2023,5,18,1),
            uid="may17",
            summary="Do the needful",
            rrule={'FREQ': 'YEARLY'})

        ## Find a particular recurrence
        my_events = cal.search(
            event=True,
            start=date(2026,5,1),
            end=date(2026,6,1),
            expand=True)

        ## Edit the summary using the "borrowing pattern":
        with my_events[0].edit_icalendar_component() as event_ical:
            ## "component" is always safe after an expanded search
            event_ical['summary'] = "Norwegian national day celebrations"
        my_events[0].save()

        ## Let's take out the event again:
        may17 = cal.get_event_by_uid('may17')

        ## Inspect may17 in a debug breakpoint
        #breakpoint()

How does the new may17-event look from a technical point of view, when we're editing only the 2026-edition?  Enable the breakpoint and find out!  Use ``.get_icalendar_instance()`` or ``.data``


Tasks
-----

Anything you can do with events can also be done with tasks.  You may try to use ``get_calendar()`` below instead of creating a calendar.  On most servers all calendars can be used for both tasks and events, however some servers (notably, Zimbra) differs between tasklists and calendars, and we need to create (or select) a tasklist and not a calendar.  The CalDAV standard allows to define this through the "supported calendar component set" parameter (ignored on most servers though).

There is some extra functionality around tasks, including the possibility to :meth:`~caldav.calendarobjectresource.Todo.complete` them.

.. code-block:: python

    from caldav import get_davclient
    from datetime import date

    with get_davclient() as client:
        my_principal = client.get_principal()
        ## This can be read as "create me a tasklist"
        cal = my_principal.make_calendar(
            name="Test tasklist", supported_calendar_component_set=['VTODO'])
        ## ... but for most servers it's an ordinary calendar!
        cal.add_todo(
            summary="prepare for the Norwegian national day", due=date(2025,5,16))

        my_tasks = cal.search(
            todo=True)
        assert len(my_tasks) == 1
        my_tasks[0].complete()
        my_tasks = cal.search(
            todo=True)
        assert len(my_tasks) == 0
        my_tasks = cal.search(
            todo=True, include_completed=True)
        assert my_tasks

Further Reading
---------------

See the :ref:`examples:examples` folder for more code, including
`basic examples <https://github.com/python-caldav/caldav/blob/master/examples/basic_usage_examples.py>`_
and `scheduling examples <https://github.com/python-caldav/caldav/blob/master/examples/scheduling_examples.py>`_
for invites.

The `integration tests <https://github.com/python-caldav/caldav/blob/master/tests/test_caldav.py>`_
covers most features, but is not much optimized for readability.

There is also a `command line interface <https://github.com/tobixen/plann>`_
built around the caldav library.
