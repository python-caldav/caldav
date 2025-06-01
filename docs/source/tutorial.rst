========
Tutorial
========

The intention with this tutorial is that you should learn basic usage
of the python CalDAV client library.  You are encouraged to copy the
code examples into a python shell and play with the objects you get
returned.  To get it to work towards your own calendar server, it's
best to set the environment variables `CALDAV_URL`, `CALDAV_USER` and
`CALDAV_PASSWORD` to point to your personal calendar server.  (Also,
if you have your username and password in a `.netrc` file, it's
sufficient to specify the URL).

The examples here uses the `with`-statement, which is considered best
practice (and needed for automated testing), but it may be
inconvenient with with-blocks when experimenting in the python shell.
You may skip the with-blocks and just write `client = get_davclient()`.


As of 2.0, it's recommended to start initiating a
:class:`caldav.davclient.DAVClient` object using the `get_davclient`
function, go from there to get a
class:`caldav.collections.Principal`-object, and from there find a
:class:`caldav.objects.Calendar`-object.  (I'm planning to add a
`get_calendar` in version 3.0).  This is how to do it:

.. code-block:: python

    from caldav.davclient import get_davclient
    from caldav.lib.error import NotFoundError

    with get_davclient() as client:
        my_principal = client.principal()
        try:
            my_calendar = my_principal.calendar()
            print(f"A calendar was found at URL {my_calendar.url}")
        except NotFoundError:
            print("You don't seem to have any calendars")

A caveat with the code above - there is no communication with the
server when initializing the client, the first communication happens
in `client.principal()` - so that's where you'll get errors if the
username/password/url is wrong.

The `get_davclient` function will try to read username/password from
the environment or from a config file.  You may also specify
connection parmeters directly to the function, like
`get_davclient(username='alice', password='hunter2',
url='https://calendar.example.com/dav/')`.  There are some more
connection-related parameters that can be set if needed, see
:class:`caldav.davclient.DAVClient` for details.

The `calendar`-method above gives one calendar - if you have more
calendars, it will give you the first one it can find - which may not
be the correct one.  To filter there are parameters `name` and
`cal_id` - I recommend testing them:

.. code-block:: python

    from caldav.davclient import get_davclient
    from caldav.lib.error import NotFoundError

    with get_davclient() as client:
        my_principal = client.principal()
        try:
            my_calendar = my_principal.calendar(name="My Calendar")
        except NotFoundError:
            print("You don't seem to have a calendar named 'My Calendar'")

If you happen to know the URL or path for the calendar, you don't need
to go through the principal object.

.. code-block:: python

    from caldav.davclient import get_davclient

    with get_davclient() as client:
        my_calendar = client.calendar(url="/dav/calendars/mycalendar")

Note that in the example above, no communication is done.  If the URL is wrong, you will only know it when trying to save or get objects from the server!

For servers that supports it, it may be useful to create a dedicated test calendar - that way you can test freely without risking to mess up your calendar events.  Let's populate it with some events and tasks while we're at it:

.. code-block: python

    from caldav.davclient import get_davclient
    import datetime

    with get_davclient() as client:
        my_principal = client.principal()
        my_new_calendar = my_principal.make_calendar(name="Test calendar")
        may17 = my_new_calendar.save_event(
            dtstart=datetime.datetime(2020,5,17,8),
            dtend=datetime.datetime(2020,5,18,1),
            uid="may17",
            summary="Do the needful",
            rrule={'FREQ': 'YEARLY'})

You have icalendar code and want to put it into the calendar?  Easy!

.. code-block: python

    from caldav.davclient import get_davclient

    with get_davclient() as client:
        my_principal = client.principal()
        my_new_calendar = my_principal.make_calendar(name="Test calendar")
        may17 = my_new_calendar.save_event("""BEGIN:VCALENDAR
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

The best way of getting information out from the calendar is to use the search.  Currently most of the logic is done on the server side - and the different calendar servers tends to give different results given the same data and search query.  In future versions of the CalDAV library the intention is to do more workarounds and logic on the client side, allowing for more consistent results across different servers.

.. code-block: python

    from caldav.davclient import get_davclient
    from datetime import date

    with get_davclient() as client:
        my_principal = client.principal()
        my_new_calendar = my_principal.make_calendar(name="Test calendar")
        my_new_calendar.save_event(
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

`expand` causes the search results to be expanded.  Instead of getting returned the original event (with `DTSTART` set in 2020 and an `RRULE` set) it will return a *recurrence*.  Or, rather, a list of recurrences if there are more of them in the search interval.

`event` causes the search to only return events.  There are three kind of objects that can be saved to a calendar (but not all servers support all three) - events, journals and tasks (`VEVENT`, `VJOURNAL` and `VTODO`).  This is called Calendar Object Resources in the RFC (quite a mouthful!).  Without `event=True` explicitly set, in theory all objects should be returned - unfortunately many servers returns nothing.  In future versions of CalDAV there will be workarounds so `event=True` can be safely skipped.

The return type is an object of the type :class:`caldav.calendarobjectresource.Event` - for tasks and jornals there are additional classes Todo and Journal.

The `data` property delivers the icalendar data as a string.  It can be modified:

.. code-block: python

    from caldav.davclient import get_davclient
    from datetime import date

    with get_davclient() as client:
        my_principal = client.principal()
        my_new_calendar = my_principal.make_calendar(name="Test calendar")
        my_new_calendar.save_event(
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

As seen above, we can use `save()` to send a modified object back to the server.  In the case above, we've edited a recurrence.  Now that we've saved the object, you're encouraged to test with search with and without expand set and with different years and see what results you'll get.  The `save()`-method also takes a parameter `all_recurrences=True` if you want to edit the full series!

When I started using the caldav library, I didn't want to get my hands dirty with all the details and complexity of the CalDAV-protocol and iCalendar-protocol (and despite that I ended up with the maintainer hat, yay!).  You can easily get the iCalendar data packed into objects that can be manipulated: `myevent.instance`.  Now there exists two libraries making it easier to handle the iCalendar data, it's vobject and icalendar.  The CalDAV-library originally supported the first, but as the second seems more popular it's the recommended library.  As of 2.0, `myevent.instance` will return a vobject instance, this may be changed in 3.0.  As for now, the recommended practice is to always be explicit and use either `myevent.vobject_instance` or `myevent.icalendar_instance` - preferably the latter.  You're encouraged to test it out in the python shell.

Most of the time every event one gets out from the search contains one *component* - and it will always be like that when using `expand=True`.  To ease things out for users of the library that wants easy access to the event data there is an `my_events[9].icalendar_component` property.  From 2.0 also accessible simply as my_events[0].component`:

.. code-block: python

    from caldav.davclient import get_davclient
    from datetime import date

    with get_davclient() as client:
        my_principal = client.principal()
        my_new_calendar = my_principal.make_calendar(name="Test calendar")
        my_new_calendar.save_event(
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
        my_events[0].component['summary'] = "Norwegian national day celebrations"
        my_events[0].save()

How to do operations on components and instances in the vobject and icalendar library is outside the scope of this tutorial - The icalendar library documentaiton can be found [here](https://icalendar.readthedocs.io/) as of 2025-06.

Usually tasks and journals can be applied directly to the same calendar as the events - but some implementations (notably Zimbra) has "task lists" and "calendars" as distinct entities.  To create a task list, there is a parameter `supported_calendar_component_set` that can be set to `['VTODO']`.  Here is a quick example that features a task:

.. code-block: python

    from caldav.davclient import get_davclient
    from datetime import date

    with get_davclient() as client:
        my_principal = client.principal()
        my_new_calendar = my_principal.make_calendar(
            name="Test calendar", supported_calendar_component_set=['VTODO'])
        my_new_calendar.save_todo(
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

This concludes this tutorial.

There are some more examples in the examples folder, particularly `basic examples <https://github.com/python-caldav/caldav/blob/master/examples/basic_usage_examples.py>`_. There is also a `scheduling examples <https://github.com/python-caldav/caldav/blob/master/examples/scheduling_examples.py>`_ for sending, receiving and replying to invites, though this is not very well-tested so far.  The example code is currently not tested nor maintained.  Some of it will be moved into the documentation as tutorials or how-tos eventually.

The `test code <https://github.com/python-caldav/caldav/blob/master/tests/test_caldav.py>`_ also covers most of the features available, though it's not much optimized for readability (at least not as of 2025-05).

Tobias Brox is also working on a `command line interface <https://github.com/tobixen/plann>`_  built around the caldav library.
