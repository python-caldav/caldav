from datetime import datetime
import sys

## We'll try to use the local caldav library, not the system-installed
sys.path.insert(0, '..')

import caldav

## CONFIGURATION.  The minimum requirement is an URL.  Username and
## password is also probably nice to have.  The DAVClient object also
## supports a proxy (URL), an auth object (to be passed to the
## requests library, instead of using username and password) and a
## boolean ssl_verify_cert that can be set to False for self-signed
## certificates.
try:
    ## To make it easy to actually execute this test code, connection
    ## details to your caldav server can be given in the
    ## tests/conf_private.py file (check conf_private.py.EXAMPLE)
    from tests.conf_private import caldav_servers
    url = caldav_servers[0]['url']
    username = caldav_servers[0]['username']
    password = caldav_servers[0]['password']
    
except ImportError:
    ## ...or you can just edit this file and put your private details here
    url = 'https://example.com/caldav.php'
    username = 'somebody'
    password = 'hunter2'


## A DAVClient object should be set up with the connection details.
## Initiating the object does not cause any requests to the server.
client = caldav.DAVClient(url=url, username=username, password=password)

## You may list up the calendars you own through the principal-object
my_principal = client.principal()
calendars = my_principal.calendars()
if calendars:
    ## Some calendar servers will include all calendars you have
    ## access to in this list, and not only the calendars owned by
    ## this principal.  TODO: see if it's possible to find a list of
    ## calendars one has access to.
    print("your principal has %i calendars:" % len(calendars))
    for c in calendars:
        print("    Name: %-20s  URL: %s" % (c.name, c.url))
else:
    print("your principal has no calendars")

## Let's try to create a calendar.  (this may fail, calendar creation
## is not a mandatory feature according to the RFC)
my_new_calendar = my_principal.make_calendar(name="Test calendar")

## Let's add an event to our newly created calendar
my_event = my_new_calendar.save_event("""BEGIN:VCALENDAR
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

## Let's search for the newly added event.
print("Here is some icalendar data:")
events_fetched = my_new_calendar.date_search(
    start=datetime(2021, 1, 1), end=datetime(2024, 1, 1), expand=True)
print(events_fetched[0].data)

event = events_fetched[0]

## To modify an event, it's best to use either the vobject or icalendar module for it.  The caldav library has always been supporting vobject out of the box, but icalendar is more popular.  event.instance will as of version 0.x yield a vobject instance, but this may change in future versions.  Use .vobject_instance or .icalendar_instance instead.
event.vobject_instance.vevent.summary.value = 'Norwegian national day celebrations'
event.save()

## It's possible to access objects such as calendars without going
## through a Principal object, i.e. if one knows the URL
the_same_calendar = caldav.Calendar(client=client, url=my_new_calendar.url)

## to get all events from the calendar, it's also possible to use the
## events()-method.  Recurring events will not be expanded.
all_events = the_same_calendar.events()

## Let's check that the summary got right
assert all_events[0].vobject_instance.vevent.summary.value.startswith('Norwegian')

## This calendar should as a minimum support VEVENTs ... most likely
## it also supports VTODOs and maybe even VJOURNALs.  We can query the
## server what it can accept:
acceptable_component_types = my_new_calendar.get_supported_components()
assert 'VEVENT' in acceptable_component_types

## Clean up - remove the new calendar
my_new_calendar.delete()

## Let's try with a task list.  Some servers cannot combine events and todos in the same calendar.
my_new_tasklist = my_principal.make_calendar(
            name="Test tasklist", supported_calendar_component_set=['VTODO'])

## We'll add a task to the task list
my_new_tasklist.add_todo("""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:20070313T123432Z-456553@example.com
DTSTAMP:20070313T123432Z
DTSTART;VALUE=DATE:20200401
DUE;VALUE=DATE:20200501
RRULE:FREQ=YEARLY
SUMMARY:Deliver some data to the Tax authorities
CATEGORIES:FAMILY,FINANCE
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR""")

## Fetch the tasks
todos = my_new_tasklist.todos()
assert(len(todos) == 1)

print("Here is some more icalendar data:")
print(todos[0].data)

## date_search also works on task lists, but one has to be explicit to get them
todos_found = my_new_calendar.date_search(
    start=datetime(2021, 1, 1), end=datetime(2024, 1, 1),
    compfilter='VTODO', expand=True)
if not todos_found:
    print("Apparently your calendar server does not support searching for future instances of reoccurring tasks")
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
assert(len(todos) == 0)

## It's possible to fetch historic tasks too
todos = my_new_tasklist.todos(include_completed=True)
assert(len(todos) == 1)

## and it's possible to delete tasks completely
todos[0].delete()

my_new_tasklist.delete()
