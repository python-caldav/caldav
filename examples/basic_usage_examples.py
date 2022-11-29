import sys
from datetime import date
from datetime import datetime

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

## When using the caldav library, one should always start off with initiating a
## DAVClient object, which should contain connection details and credentials.
## Initiating the object does not cause any requests to the server, so this
## will not break even if caldav url is set to example.com
client = caldav.DAVClient(url=caldav_url, username=username, password=password)

## For the convenience, if things are correctly set up in test config,
## the code below may replace the client object with one that works.
if "example.com" in caldav_url and password == "hunter2":
    from tests.conf import client as client_

    client = client_()

## Typically the next step is to fetch a principal object.
## This will cause communication with the server.
my_principal = client.principal()

## The principals calendars can be fetched like this:
calendars = my_principal.calendars()
if calendars:
    ## Some calendar servers will include all calendars you have
    ## access to in this list, and not only the calendars owned by
    ## this principal.
    print("your principal has %i calendars:" % len(calendars))
    for c in calendars:
        print("    Name: %-20s  URL: %s" % (c.name, c.url))
else:
    print("your principal has no calendars")

## Let's try to find or create a calendar ...
try:
    ## This will raise a NotFoundError if calendar does not exist
    my_new_calendar = my_principal.calendar(name="Test calendar")
    assert my_new_calendar
    ## calendar did exist, probably it was made on an earlier run
    ## of this script
except caldav.error.NotFoundError:
    ## Let's create a calendar
    my_new_calendar = my_principal.make_calendar(name="Test calendar")

## Let's add an event to our newly created calendar
## (This usage pattern is new from v0.9.
## Earlier save_event would only accept some ical data)
my_event = my_new_calendar.save_event(
    dtstart=datetime(2020, 5, 17, 8),
    dtend=datetime(2020, 5, 18, 1),
    summary="Do the needful",
    rrule={"FREQ": "YEARLY"},
)

## Let's search for the newly added event.
## (this may fail if the server doesn't support expand)
print("Here is some icalendar data:")
try:
    events_fetched = my_new_calendar.search(
        start=datetime(2021, 5, 16), end=datetime(2024, 1, 1),event= True, expand=True
    )
    ## Note: obj.data will always return a normal string, with normal line breaks
    ## obj.wire_data will return a byte string with CRLN
    print(events_fetched[0].data)
except:
    print("Your calendar server does apparently not support expanded search")
    events_fetched = my_new_calendar.search(
        start=datetime(2020, 5, 16), end=datetime(2024, 1, 1),event=True, expand=False
    )
    print(events_fetched[0].data)

event = events_fetched[0]

## To modify an event, it's best to use either the vobject or icalendar module for it.
## The caldav library has always been supporting vobject out of the box, but icalendar is more popular.
## event.instance will as of version 0.x yield a vobject instance, but this may change in future versions.
## Both event.vobject_instance and event.icalendar_instance works from 0.7.
event.vobject_instance.vevent.summary.value = "Norwegian national day celebratiuns"
event.icalendar_instance.subcomponents[0][
    "summary"
] = event.icalendar_instance.subcomponents[0]["summary"].replace(
    "celebratiuns", "celebrations"
)
event.save()

## Please note that the proper way to save new icalendar data
## to the calendar is calendar.save_event(ics_data),
## while the proper way to update a calendar event is
## event.save().  Doing calendar.save_event(event.data)
## may break.  See https://github.com/python-caldav/caldav/issues/153
## for details.

## It's possible to access objects such as calendars without going
## through a Principal object if one knows the calendar URL
the_same_calendar = client.calendar(url=my_new_calendar.url)

## to get all events from the calendar, it's also possible to use the
## events()-method.  Recurring events will not be expanded.
all_events = the_same_calendar.events()

## It's also possible to use .objects.
all_objects = the_same_calendar.objects()

## since we have only added events (and neither todos nor journals), those
## should be equal ... except, all_objects is an iterator and not a list.
assert len(all_events) == len(list(all_objects))

## Let's check that the summary got right
assert all_events[0].vobject_instance.vevent.summary.value.startswith("Norwegian")
assert all_events[0].vobject_instance.vevent.summary.value.endswith("celebrations")

## This calendar should as a minimum support VEVENTs ... most likely
## it also supports VTODOs and maybe even VJOURNALs.  We can query the
## server what it can accept:
acceptable_component_types = my_new_calendar.get_supported_components()
assert "VEVENT" in acceptable_component_types

## Clean up - remove the new calendar
my_new_calendar.delete()

## Let's try with a task list.  Some servers cannot combine events and todos in the same calendar.
my_new_tasklist = my_principal.make_calendar(
    name="Test tasklist", supported_calendar_component_set=["VTODO"]
)

## We'll add a task to the task list
my_new_tasklist.add_todo(
    ics="RRULE:FREQ=YEARLY",
    summary="Deliver some data to the Tax authorities",
    dtstart=date(2020, 4, 1),
    due=date(2020, 5, 1),
    categories=["family", "finance"],
    status="NEEDS-ACTION",
)

## Fetch the tasks
todos = my_new_tasklist.todos()
assert len(todos) == 1
assert "FREQ=YEARLY" in todos[0].data

print("Here is some more icalendar data:")
print(todos[0].data)

## date_search also works on task lists, but one has to be explicit to get them
todos_found = my_new_tasklist.search(
    start=datetime(2021, 1, 1),
    end=datetime(2024, 1, 1),
    compfilter="VTODO",
    event=True,
    expand=True,
)
if not todos_found:
    print(
        "Apparently your calendar server does not support searching for future instances of reoccurring tasks"
    )
else:
    print("Here is even more icalendar data:")
    print(todos_found[0].data)

## Mark the task as completed
todos[0].complete()

## This is a yearly task.  Completing it for one year should probably
## spawn a new task recurrence instance for the next year.  The RFC
## says nothing about it, it seems like it's up to the clients weather
## to implement such logic or not.  I've implemented such logic in the
## calendar-cli project, perhaps it should be moved into the caldav
## library, but as for now ... completing the task will cause the task
## list to be emptied.
todos = my_new_tasklist.todos()
assert len(todos) == 0

## It's possible to fetch historic tasks too
todos = my_new_tasklist.todos(include_completed=True)
assert len(todos) == 1

## and it's possible to delete tasks completely
todos[0].delete()

my_new_tasklist.delete()
