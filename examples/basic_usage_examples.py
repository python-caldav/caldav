import sys
from datetime import date
from datetime import datetime
from datetime import timedelta

## We'll try to use the local caldav library, not the system-installed
sys.path.insert(0, "..")
sys.path.insert(0, ".")

import caldav

## DO NOT name your file calendar.py or caldav.py!  We've had several
## issues filed, things break because the wrong files are imported.
## It's not a bug with the caldav library per se.

## CONFIGURATION.  Edit here, or set up something in
## tests/conf_private.py (see tests/conf_private.py.EXAMPLE).
caldav_url = "https://calendar.example.com/dav"
username = "somebody"
password = "hunter2"
headers = {"X-MY-CUSTOMER-HEADER": "123"}


def run_examples():
    """
    Run through all the examples, one by one
    """
    ## We need a client object.
    ## The client object stores http session information, username, password, etc.
    ## As of 1.0, Initiating the client object will not cause any server communication,
    ## so the credentials aren't validated.
    ## The client object can be used as a context manager, like this:
    with caldav.DAVClient(
        url=caldav_url,
        username=username,
        password=password,
        headers=headers,  # Optional parameter to set HTTP headers on each request if needed
    ) as client:
        ## Typically the next step is to fetch a principal object.
        ## This will cause communication with the server.
        my_principal = client.principal()

        ## The principals calendars can be fetched like this:
        calendars = my_principal.calendars()

        ## print out some information
        print_calendars_demo(calendars)

        ## This cleans up from previous runs, if needed:
        find_delete_calendar_demo(my_principal, "Test calendar from caldav examples")

        ## Let's create a new calendar to play with.
        ## This may raise an error for multiple reasons:
        ## * server may not support it (it's not mandatory in the CalDAV RFC)
        ## * principal may not have the permission to create calendars
        ## * some cloud providers have a global namespace
        my_new_calendar = my_principal.make_calendar(
            name="Test calendar from caldav examples"
        )

        ## Let's add some events to our newly created calendar
        add_stuff_to_calendar_demo(my_new_calendar)

        ## Let's find the stuff we just added to the calendar
        event = search_calendar_demo(my_new_calendar)

        ## Inspecting and modifying an event
        read_modify_event_demo(event)

        ## Accessing a calendar by a calendar URL
        calendar_by_url_demo(client, my_new_calendar.url)

        ## Clean up - delete things
        ## (The event would normally be deleted together with the calendar,
        ## but different calendar servers may behave differently ...)
        event.delete()
        my_new_calendar.delete()


def calendar_by_url_demo(client, url):
    """Sometimes one may have a calendar URL.  Sometimes maybe one would
    not want to fetch the principal object from the server (it's not
    even required to support it by the caldav protocol).
    """
    ## No network traffic will be initiated by this:
    calendar = client.calendar(url=url)
    ## At the other hand, this will cause network activity:
    events = calendar.events()
    ## We should still have only one event in the calendar
    assert len(events) == 1

    event_url = events[0].url

    ## there is no similar method for fetching an event through
    ## a URL.  One may construct the object like this though:
    same_event = caldav.Event(client=client, parent=calendar, url=event_url)

    ## That was also done without any network traffic.  To get the same_event
    ## populated with data it needs to be loaded:
    same_event.load()

    assert same_event.data == events[0].data


def read_modify_event_demo(event):
    """This demonstrates how to edit properties in the ical object
    and save it back to the calendar.  It takes an event -
    caldav.Event - as input.  This event is found through the
    `search_calendar_demo`.  The event needs some editing, which will
    be done below.  Keep in mind that the differences between an
    Event, a Todo and a Journal is small, everything that is done to
    he event here could as well be done towards a task.
    """
    ## The objects (events, journals and tasks) comes with some properties that
    ## can be used for inspecting the data and modifying it.

    ## event.data is the raw data, as a string, with unix linebreaks
    print("here comes some icalendar data:")
    print(event.data)

    ## event.wire_data is the raw data as a byte string with CRLN linebreaks
    assert len(event.wire_data) >= len(event.data)

    ## Two libraries exists to handle icalendar data - vobject and
    ## icalendar.  The caldav library traditionally supported the
    ## first one, but icalendar is more popular.

    ## Here is an example
    ## on how to modify the summary using vobject:
    event.vobject_instance.vevent.summary.value = "norwegian national day celebratiuns"

    ## event.icalendar_instance gives an icalendar instance - which
    ## normally would be one icalendar calendar object containing one
    ## subcomponent.  Quite often the fourth property,
    ## icalendar_component is preferable - it gives us the component -
    ## but be aware that if the server returns a recurring events with
    ## exceptions, event.icalendar_component will ignore all the
    ## exceptions.
    uid = event.icalendar_component["uid"]

    ## Let's correct that typo using the icalendar library.
    event.icalendar_component["summary"] = event.icalendar_component["summary"].replace(
        "celebratiuns", "celebrations"
    )

    ## timestamps (DTSTAMP, DTSTART, DTEND for events, DUE for tasks,
    ## etc) can be fetched using the icalendar library like this:
    dtstart = event.icalendar_component.get("dtstart")

    ## but, dtstart is not a python datetime - it's a vDatetime from
    ## the icalendar package.  If you want it as a python datetime,
    ## use the .dt property.  (In this case dtstart is set - and it's
    ## pretty much mandatory for events - but the code here is robust
    ## enough to handle cases where it's undefined):
    dtstart_dt = dtstart and dtstart.dt

    ## We can modify it:
    if dtstart:
        event.icalendar_component["dtstart"].dt = dtstart.dt + timedelta(seconds=3600)

    ## And finally, get the casing correct
    event.data = event.data.replace("norwegian", "Norwegian")

    ## Note that this is not quite thread-safe:
    icalendar_component = event.icalendar_component
    ## accessing the data (and setting it) will "disconnect" the
    ## icalendar_component from the event
    event.data = event.data
    ## So this will not affect the event anymore:
    icalendar_component["summary"] = "do the needful"
    assert not "do the needful" in event.data

    ## The mofifications are still only saved locally in memory -
    ## let's save it to the server:
    event.save()

    ## NOTE: always use event.save() for updating events and
    ## calendar.save_event(data) for creating a new event.
    ## This may break:
    # event.save(event.data)
    ## ref https://github.com/python-caldav/caldav/issues/153

    ## Finally, let's verify that the correct data was saved
    calendar = event.parent
    same_event = calendar.event_by_uid(uid)
    assert (
        same_event.icalendar_component["summary"]
        == "Norwegian national day celebrations"
    )


def search_calendar_demo(calendar):
    """
    some examples on how to fetch objects from the calendar
    """
    ## It should theoretically be possible to find both the events and
    ## tasks in one calendar query, but not all server implementations
    ## supports it, hence either event, todo or journal should be set
    ## to True when searching.  Here is a date search for events, with
    ## expand:
    events_fetched = calendar.search(
        start=datetime.now(),
        end=datetime(date.today().year + 5, 1, 1),
        event=True,
        expand=True,
    )

    ## "expand" causes the recurrences to be expanded.
    ## The yearly event will give us one object for each year
    assert len(events_fetched) > 1

    print("here is some ical data:")
    print(events_fetched[0].data)

    ## We can also do the same thing without expand, then the "master"
    ## from 2020 will be fetched
    events_fetched = calendar.search(
        start=datetime.now(),
        end=datetime(date.today().year + 5, 1, 1),
        event=True,
        expand=False,
    )
    assert len(events_fetched) == 1

    ## search can be done by other things, i.e. keyword
    tasks_fetched = calendar.search(todo=True, category="outdoor")
    assert len(tasks_fetched) == 1

    ## This those should also work:
    all_objects = calendar.objects()
    # updated_objects = calendar.objects_by_sync_token(some_sync_token)
    # some_object = calendar.object_by_uid(some_uid)
    # some_event = calendar.event_by_uid(some_uid)
    children = calendar.children()
    events = calendar.events()
    tasks = calendar.todos()
    assert len(events) + len(tasks) == len(all_objects)
    assert len(children) == len(all_objects)
    ## TODO: Some of those should probably be deprecated.
    ## children is a good candidate.

    ## Tasks can be completed
    tasks[0].complete()

    ## They will then disappear from the task list
    assert not calendar.todos()

    ## But they are not deleted
    assert len(calendar.todos(include_completed=True)) == 1

    ## Let's delete it completely
    tasks[0].delete()

    return events_fetched[0]


def print_calendars_demo(calendars):
    """
    This example prints the name and URL for every calendar on the list
    """
    if calendars:
        ## Some calendar servers will include all calendars you have
        ## access to in this list, and not only the calendars owned by
        ## this principal.
        print("your principal has %i calendars:" % len(calendars))
        for c in calendars:
            print("    Name: %-36s  URL: %s" % (c.name, c.url))
    else:
        print("your principal has no calendars")


def find_delete_calendar_demo(my_principal, calendar_name):
    """
    This example takes a calendar name, finds the calendar if it
    exists, and deletes the calendar if it exists.
    """
    ## Let's try to find or create a calendar ...
    try:
        ## This will raise a NotFoundError if calendar does not exist
        demo_calendar = my_principal.calendar(name="Test calendar from caldav examples")
        assert demo_calendar
        print(
            f"We found an existing calendar with name {calendar_name}, now deleting it"
        )
        demo_calendar.delete()
    except caldav.error.NotFoundError:
        ## Calendar was not found
        pass


def add_stuff_to_calendar_demo(calendar):
    """
    This demo adds some stuff to the calendar

    Unfortunately the arguments that it's possible to pass to save_* is poorly documented.
    https://github.com/python-caldav/caldav/issues/253
    """
    ## Add an event with some certain attributes
    may_event = calendar.save_event(
        dtstart=datetime(2020, 5, 17, 6),
        dtend=datetime(2020, 5, 18, 1),
        summary="Do the needful",
        rrule={"FREQ": "YEARLY"},
    )

    ## not all calendars supports tasks ... but if it's supported, it should be
    ## told here:
    acceptable_component_types = calendar.get_supported_components()
    assert "VTODO" in acceptable_component_types

    ## Add a task that should contain some ical lines
    ## Note that this may break on your server:
    ## * not all servers accepts tasks and events mixed on the same calendar.
    ## * not all servers accepts tasks at all
    dec_task = calendar.save_todo(
        ical_fragment="""DTSTART;VALUE=DATE:20201213
DUE;VALUE=DATE:20201220
SUMMARY:Chop down a tree and drag it into the living room
RRULE:FREQ=YEARLY
PRIORITY: 2
CATEGORIES: outdoor"""
    )

    ## ical_fragment parameter -> just some lines
    ## ical parameter -> full ical object


def _please_ignore_this_hack():
    """
    This hack is to be used for the maintainer (or other people
    having set up testing servers in tests/private_conf.py) to be able
    to verify that this example code works, without editing the
    example code itself.
    """
    if password == "hunter2":
        from tests.conf import client as client_

        client = client_()

        def _wrapper(*args, **kwargs):
            return client

        caldav.DAVClient = _wrapper


if __name__ == "__main__":
    _please_ignore_this_hack()
    run_examples()
