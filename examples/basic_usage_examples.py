import sys
from datetime import date, datetime, timedelta

## We'll try to use the local caldav library, not the system-installed
sys.path.insert(0, "..")
sys.path.insert(0, ".")

import caldav
from caldav import get_davclient

## Connection parameters can be set in a configuration file or passed
## as environmental variables.  The format of the configuration file
## is described at
## https://caldav.readthedocs.io/stable/configfile.html

## To run this with environmental variables, you may do like this:

# env CALDAV_USERNAME=xxx@qq.com \
#       CALDAV_PASSWORD=xxx \
#       CALDAV_URL=https://dav.qq.com/ \
#  python ./examples/basic_usage_examples.py


## DO NOT name your file calendar.py or caldav.py!  We've had several
## issues filed, things break because the wrong files are imported.
## It's not a bug with the caldav library per se.


def run_examples():
    """
    Run through all the examples, one by one
    """
    ## We need a client object.
    ## The client object stores http session information, username, password, etc.
    ## As of 1.0, Initiating the client object will not cause any server communication,
    ## so the credentials aren't validated.
    ## get_davclient will try to read credentials and url from environment variables
    ## and config file.
    ## The client object can be used as a context manager, like this:
    with get_davclient() as client:
        ## Typically the next step is to fetch a principal object.
        ## This will cause communication with the server.
        print("Connecting to the caldav server")
        my_principal = client.principal()

        ## The principals calendars can be fetched like this:
        calendars = my_principal.get_calendars()

        ## print out some information
        print_calendars_demo(calendars)

        ## This cleans up from previous runs, if needed:
        find_delete_calendar_demo(my_principal, "Test calendar from caldav examples")

        ## Let's create a new calendar to play with.
        ## This may raise an error for multiple reasons:
        ## * server may not support it (it's not mandatory in the CalDAV RFC)
        ## * principal may not have the permission to create calendars
        ## * some cloud providers have a global namespace
        my_new_calendar = my_principal.make_calendar(name="Test calendar from caldav examples")

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
        demo_calendar = my_principal.calendar(name=calendar_name)
        assert demo_calendar
        print(f"We found an existing calendar with name {calendar_name}, now deleting it")
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
    print("Saving an event")
    may_event = calendar.add_event(
        dtstart=datetime(2020, 5, 17, 6),
        dtend=datetime(2020, 5, 18, 1),
        summary="Do the needful",
        rrule={"FREQ": "YEARLY"},
    )
    print("Saved an event")

    ## not all calendars supports tasks ... but if it's supported, it should be
    ## told here:
    acceptable_component_types = calendar.get_supported_components()
    assert "VTODO" in acceptable_component_types
    print("tasks are supported by your calendar, saving one")

    ## Add a task that should contain some ical lines
    ## Note that this may break on your server:
    ## * not all servers accepts tasks and events mixed on the same calendar.
    ## * not all servers accepts tasks at all
    dec_task = calendar.add_todo(
        ical_fragment="""DTSTART;VALUE=DATE:20201213
DUE;VALUE=DATE:20201220
SUMMARY:Chop down a tree and drag it into the living room
RRULE:FREQ=YEARLY
PRIORITY: 2
CATEGORIES:outdoor"""
    )
    print("Saved a task")

    ## ical_fragment parameter -> just some lines
    ## ical parameter -> full ical object


def search_calendar_demo(calendar):
    """
    some examples on how to fetch objects from the calendar
    """
    ## It should theoretically be possible to find both the events and
    ## tasks in one calendar query, but not all server implementations
    ## supports it, hence either event, todo or journal should be set
    ## to True when searching.  Here is a date search for events, with
    ## expand:
    print("Searching for expanded events")
    events_fetched = calendar.search(
        start=datetime.now(),
        end=datetime(date.today().year + 5, 1, 1),
        event=True,
        expand=True,
    )

    ## "expand" causes the recurrences to be expanded.
    ## The yearly event will give us one object for each year
    assert len(events_fetched) > 1
    print(f"Found {len(events_fetched)} events")

    print("here is some ical data from the first one:")
    print(events_fetched[0].data)

    ## We can also do the same thing without expand, then the "master"
    ## from 2020 will be fetched
    print("Searching for un expanded events")
    events_fetched = calendar.search(
        start=datetime.now(),
        end=datetime(date.today().year + 5, 1, 1),
        event=True,
        expand=False,
    )
    assert len(events_fetched) == 1
    print(f"Found {len(events_fetched)} event")

    ## search can be done by other things, i.e. keyword
    print("Searching for tasks")
    # Note that Radicale fails when specifying a category pending
    # https://github.com/Kozea/Radicale/pull/1277
    tasks_fetched = calendar.search(todo=True, category="outdoor")
    assert len(tasks_fetched) == 1
    print(f"Found {len(tasks_fetched)} task")

    ## This those should also work:
    print("Getting all objects from the calendar")
    all_objects = calendar.objects()
    # updated_objects = calendar.get_objects_by_sync_token(some_sync_token)
    # some_object = calendar.get_object_by_uid(some_uid)
    # some_event = calendar.get_event_by_uid(some_uid)
    print("Getting all children from the calendar")
    children = calendar.children()
    print("Getting all events from the calendar")
    events = calendar.get_events()
    print("Getting all todos from the calendar")
    tasks = calendar.get_todos()
    assert len(events) + len(tasks) == len(all_objects)
    print(f"Found {len(events)} events and {len(tasks)} tasks which is {len(all_objects)}")
    assert len(children) == len(all_objects)
    print(f"Found {len(children)} children which is also {len(all_objects)}")
    ## TODO: Some of those should probably be deprecated.
    ## children is a good candidate.

    ## Tasks can be completed
    print("Marking a task completed")
    tasks[0].complete()

    ## They will then disappear from the task list
    print("Getting remaining todos")
    assert not calendar.get_todos()
    print("There are no todos")

    ## But they are not deleted
    assert len(calendar.get_todos(include_completed=True)) == 1

    ## Let's delete it completely
    print("Deleting it completely")
    tasks[0].delete()

    return events_fetched[0]


def read_modify_event_demo(event):
    """This demonstrates how to edit properties in the ical object
    and save it back to the calendar.  It takes an event -
    caldav.Event - as input.  This event is found through the
    `search_calendar_demo`.  The event needs some editing, which will
    be done below.  Keep in mind that the differences between an
    Event, a Todo and a Journal is small, everything that is done to
    the event here could as well be done towards a task.
    """
    ## =========================================================
    ## RECOMMENDED: Safe data access API (3.0+)
    ## =========================================================
    ## As of caldav 3.0, use context managers to "borrow" objects for editing.
    ## This prevents confusing side effects where accessing one representation
    ## can invalidate references to another.

    ## For READ-ONLY access, use get_* methods (returns copies):
    print("here comes some icalendar data (using get_data):")
    print(event.get_data())

    ## For READ-ONLY inspection of icalendar object:
    ical_copy = event.get_icalendar_instance()
    for comp in ical_copy.subcomponents:
        if comp.name == "VEVENT":
            print(f"Event UID: {comp['UID']}")
            uid = str(comp["UID"])

    ## For EDITING, use context managers:
    print("Editing the event using edit_icalendar_instance()...")
    with event.edit_icalendar_instance() as cal:
        for comp in cal.subcomponents:
            if comp.name == "VEVENT":
                comp["SUMMARY"] = "norwegian national day celebratiuns"

    ## Or edit using vobject:
    print("Editing with vobject using edit_vobject_instance()...")
    with event.edit_vobject_instance() as vobj:
        vobj.vevent.summary.value = vobj.vevent.summary.value.replace(
            "celebratiuns", "celebrations"
        )

    ## Modify the start time using icalendar
    with event.edit_icalendar_instance() as cal:
        for comp in cal.subcomponents:
            if comp.name == "VEVENT":
                dtstart = comp.get("dtstart")
                if dtstart:
                    comp["dtstart"].dt = dtstart.dt + timedelta(seconds=3600)
                ## Fix the casing
                comp["SUMMARY"] = str(comp["SUMMARY"]).replace("norwegian", "Norwegian")

    ## Save to server
    event.save()

    ## =========================================================
    ## LEGACY: Property-based access (still works, but be careful)
    ## =========================================================
    ## The old property access still works for backward compatibility:
    ##   event.data, event.icalendar_instance, event.vobject_instance
    ##
    ## WARNING: These have confusing side effects! Accessing one
    ## can disconnect your references to another:
    ##
    ##   component = event.component
    ##   event.data = event.data  # This disconnects 'component'!
    ##   component["summary"] = "new"  # This won't be saved!
    ##
    ## Use the context managers above instead for safe editing.

    ## Verify the correct data was saved
    calendar = event.parent
    same_event = calendar.get_event_by_uid(uid)
    assert same_event.component["summary"] == "Norwegian national day celebrations"


def calendar_by_url_demo(client, url):
    """Sometimes one may have a calendar URL.  Sometimes maybe one would
    not want to fetch the principal object from the server (it's not
    even required to support it by the caldav protocol).
    """
    ## No network traffic will be initiated by this:
    calendar = client.calendar(url=url)
    ## At the other hand, this will cause network activity:
    events = calendar.get_events()
    ## We should still have only one event in the calendar
    assert len(events) == 1

    event_url = events[0].url

    ## there is no similar method for fetching an event through
    ## a URL.  One may construct the object like this though:
    same_event = caldav.Event(client=client, parent=calendar, url=event_url)

    ## That was also done without any network traffic.  To get the same_event
    ## populated with data it needs to be loaded:
    same_event.load()

    ## This should be true.  However,
    # assert same_event.data == events[0].data


if __name__ == "__main__":
    run_examples()
