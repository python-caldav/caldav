#!/usr/bin/env python
"""
Async CalDAV Usage Examples

This module demonstrates the async API for the caldav library.
For sync usage, see basic_usage_examples.py.

The async API is available through the caldav.aio module:

    from caldav import aio

    async with aio.AsyncDAVClient(url=..., username=..., password=...) as client:
        principal = await client.principal()
        calendars = await principal.calendars()
        for cal in calendars:
            events = await cal.events()

To run this example:

    env CALDAV_USERNAME=xxx@example.com \
        CALDAV_PASSWORD=xxx \
        CALDAV_URL=https://caldav.example.com/ \
    python ./examples/async_usage_examples.py
"""

import asyncio
import sys
from datetime import date, datetime, timedelta

# Use local caldav library, not system-installed
sys.path.insert(0, "..")
sys.path.insert(0, ".")

from caldav import aio, error


async def run_examples():
    """
    Run through all the async examples, one by one
    """
    # The async client is available via caldav.aio module
    # get_async_davclient() reads credentials from environment variables
    # and config file, just like the sync version
    async with aio.get_async_davclient() as client:
        # Fetch the principal object - this triggers server communication
        print("Connecting to the caldav server")
        my_principal = await client.principal()

        # Fetch the principal's calendars
        calendars = await my_principal.calendars()

        # Print calendar information
        await print_calendars_demo(calendars)

        # Clean up from previous runs if needed
        await find_delete_calendar_demo(my_principal, "Test calendar from async examples")

        # Create a new calendar to play with
        my_new_calendar = await my_principal.make_calendar(
            name="Test calendar from async examples"
        )

        # Add some events to our newly created calendar
        await add_stuff_to_calendar_demo(my_new_calendar)

        # Find the stuff we just added
        event = await search_calendar_demo(my_new_calendar)

        # Inspect and modify an event
        await read_modify_event_demo(event)

        # Access a calendar by URL
        await calendar_by_url_demo(client, my_new_calendar.url)

        # Clean up - delete the event and calendar
        await event.delete()
        await my_new_calendar.delete()


async def print_calendars_demo(calendars):
    """
    Print the name and URL for every calendar on the list
    """
    if calendars:
        print(f"your principal has {len(calendars)} calendars:")
        for c in calendars:
            print(f"    Name: {c.name:<36}  URL: {c.url}")
    else:
        print("your principal has no calendars")


async def find_delete_calendar_demo(my_principal, calendar_name):
    """
    Find a calendar by name and delete it if it exists.
    This cleans up from previous runs.
    """
    try:
        # calendar() is async in the new API
        demo_calendar = await my_principal.calendar(name=calendar_name)
        print(f"Found existing calendar '{calendar_name}', now deleting it")
        await demo_calendar.delete()
    except error.NotFoundError:
        # Calendar was not found - that's fine
        pass


async def add_stuff_to_calendar_demo(calendar):
    """
    Add some events and tasks to the calendar
    """
    # Add an event with some attributes
    print("Saving an event")
    may_event = await calendar.save_event(
        dtstart=datetime(2020, 5, 17, 6),
        dtend=datetime(2020, 5, 18, 1),
        summary="Do the needful",
        rrule={"FREQ": "YEARLY"},
    )
    print("Saved an event")

    # Check if tasks are supported
    acceptable_component_types = await calendar.get_supported_components()
    if "VTODO" in acceptable_component_types:
        print("Tasks are supported by your calendar, saving one")
        dec_task = await calendar.save_todo(
            ical_fragment="""DTSTART;VALUE=DATE:20201213
DUE;VALUE=DATE:20201220
SUMMARY:Chop down a tree and drag it into the living room
RRULE:FREQ=YEARLY
PRIORITY: 2
CATEGORIES:outdoor"""
        )
        print("Saved a task")
    else:
        print("Tasks are not supported by this calendar")


async def search_calendar_demo(calendar):
    """
    Examples of fetching objects from the calendar
    """
    # Date search for events with expand
    print("Searching for expanded events")
    events_fetched = await calendar.search(
        start=datetime.now(),
        end=datetime(date.today().year + 5, 1, 1),
        event=True,
        expand=True,
    )

    # The yearly event gives us one object per year when expanded
    if len(events_fetched) > 1:
        print(f"Found {len(events_fetched)} expanded events")
    else:
        print(f"Found {len(events_fetched)} event")

    print("Here is some ical data from the first one:")
    print(events_fetched[0].data)

    # Same search without expand - gets the "master" event
    print("Searching for unexpanded events")
    events_fetched = await calendar.search(
        start=datetime.now(),
        end=datetime(date.today().year + 5, 1, 1),
        event=True,
        expand=False,
    )
    print(f"Found {len(events_fetched)} event (master only)")

    # Search by category
    print("Searching for tasks by category")
    tasks_fetched = await calendar.search(todo=True, category="outdoor")
    print(f"Found {len(tasks_fetched)} task(s)")

    # Get all objects from the calendar
    print("Getting all events from the calendar")
    events = await calendar.events()

    print("Getting all todos from the calendar")
    tasks = await calendar.todos()

    print(f"Found {len(events)} events and {len(tasks)} tasks")

    # Mark tasks as complete
    if tasks:
        print("Marking a task completed")
        await tasks[0].complete()

        # Completed tasks disappear from the regular list
        remaining_tasks = await calendar.todos()
        print(f"Remaining incomplete tasks: {len(remaining_tasks)}")

        # But they're not deleted - can still find with include_completed
        all_tasks = await calendar.todos(include_completed=True)
        print(f"All tasks (including completed): {len(all_tasks)}")

        # Delete the task completely
        print("Deleting the task")
        await tasks[0].delete()

    return events_fetched[0]


async def read_modify_event_demo(event):
    """
    Demonstrate how to read and modify event properties
    """
    # event.data is the raw ical data
    print("Here comes some icalendar data:")
    print(event.data)

    # Modify using vobject
    event.vobject_instance.vevent.summary.value = "norwegian national day celebratiuns"

    # Get the UID using icalendar
    uid = event.component["uid"]

    # Fix the typo using icalendar
    event.component["summary"] = event.component["summary"].replace(
        "celebratiuns", "celebrations"
    )

    # Modify timestamps
    dtstart = event.component.get("dtstart")
    if dtstart:
        event.component["dtstart"].dt = dtstart.dt + timedelta(seconds=3600)

    # Fix casing
    event.data = event.data.replace("norwegian", "Norwegian")

    # Save the modifications to the server
    await event.save()

    # Verify the data was saved correctly
    calendar = event.parent
    same_event = await calendar.event_by_uid(uid)
    print(f"Event summary after save: {same_event.component['summary']}")


async def calendar_by_url_demo(client, url):
    """
    Access a calendar directly by URL without fetching the principal
    """
    # No network traffic for this - just creates the object
    calendar = client.calendar(url=url)

    # This will cause network activity
    events = await calendar.events()
    print(f"Calendar has {len(events)} event(s)")

    if events:
        event_url = events[0].url

        # Construct an event object from URL (no network traffic)
        same_event = aio.AsyncEvent(client=client, parent=calendar, url=event_url)

        # Load the data from the server
        await same_event.load()
        print(f"Loaded event: {same_event.component['summary']}")


async def parallel_operations_demo():
    """
    Demonstrate running multiple async operations in parallel.
    This is one of the main benefits of async - concurrent I/O.
    """
    async with aio.get_async_davclient() as client:
        principal = await client.principal()
        calendars = await principal.calendars()

        if len(calendars) >= 2:
            # Fetch events from multiple calendars in parallel
            print("Fetching events from multiple calendars in parallel...")
            results = await asyncio.gather(
                calendars[0].events(),
                calendars[1].events(),
            )
            for i, events in enumerate(results):
                print(f"Calendar {i}: {len(events)} events")


if __name__ == "__main__":
    asyncio.run(run_examples())
