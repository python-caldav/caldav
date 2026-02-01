#!/usr/bin/env python
"""
Example: Using get_calendars() and get_calendar() convenience functions.

These functions provide a simple way to fetch calendars without
manually creating a client and principal object.

Configuration can come from:
1. Explicit parameters (url, username, password)
2. Environment variables (CALDAV_URL, CALDAV_USERNAME, CALDAV_PASSWORD)
3. Config files (~/.config/caldav/config.yaml)
"""

from caldav import get_calendar, get_calendars


def example_get_all_calendars():
    """Get all calendars from a CalDAV server."""
    print("=== Get All Calendars ===")

    # Option 1: Explicit credentials
    calendars = get_calendars(
        url="https://caldav.example.com/",
        username="alice",
        password="secret",
    )

    # Option 2: From environment variables (CALDAV_URL, CALDAV_USERNAME, CALDAV_PASSWORD)
    # calendars = get_calendars()

    for cal in calendars:
        print(f"  - {cal.name} ({cal.url})")

    return calendars


def example_get_calendar_by_name():
    """Get a specific calendar by name."""
    print("\n=== Get Calendar by Name ===")

    calendar = get_calendar(
        url="https://caldav.example.com/",
        username="alice",
        password="secret",
        calendar_name="Work",
    )

    if calendar:
        print(f"Found: {calendar.name}")
        # Now you can work with events
        events = calendar.get_events()
        print(f"  Contains {len(events)} events")
    else:
        print("Calendar 'Work' not found")

    return calendar


def example_get_multiple_calendars_by_name():
    """Get multiple specific calendars by name."""
    print("\n=== Get Multiple Calendars by Name ===")

    calendars = get_calendars(
        url="https://caldav.example.com/",
        username="alice",
        password="secret",
        calendar_name=["Work", "Personal", "Family"],  # List of names
    )

    for cal in calendars:
        print(f"  - {cal.name}")

    return calendars


def example_get_calendar_by_url():
    """Get a calendar by URL or ID."""
    print("\n=== Get Calendar by URL/ID ===")

    # By full path
    calendars = get_calendars(
        url="https://caldav.example.com/",
        username="alice",
        password="secret",
        calendar_url="/calendars/alice/work/",
    )

    # Or just by calendar ID (the last path segment)
    calendars = get_calendars(
        url="https://caldav.example.com/",
        username="alice",
        password="secret",
        calendar_url="work",  # No slash = treated as ID
    )

    for cal in calendars:
        print(f"  - {cal.name} at {cal.url}")

    return calendars


def example_error_handling():
    """Handle errors gracefully."""
    print("\n=== Error Handling ===")

    # With raise_errors=False (default), returns empty list on failure
    calendars = get_calendars(
        url="https://invalid.example.com/",
        username="alice",
        password="wrong",
        raise_errors=False,
    )
    print(f"Got {len(calendars)} calendars (errors suppressed)")

    # With raise_errors=True, raises exceptions
    try:
        calendars = get_calendars(
            url="https://invalid.example.com/",
            username="alice",
            password="wrong",
            raise_errors=True,
        )
    except Exception as e:
        print(f"Caught error: {type(e).__name__}: {e}")


def example_working_with_events():
    """Once you have a calendar, work with events."""
    print("\n=== Working with Events ===")

    import datetime

    calendar = get_calendar(
        url="https://caldav.example.com/",
        username="alice",
        password="secret",
        calendar_name="Work",
    )

    if not calendar:
        print("No calendar found")
        return

    # Create an event
    event = calendar.add_event(
        dtstart=datetime.datetime.now() + datetime.timedelta(days=1),
        dtend=datetime.datetime.now() + datetime.timedelta(days=1, hours=1),
        summary="Meeting created via get_calendar()",
    )
    print(f"Created event: {event.vobject_instance.vevent.summary.value}")

    # Search for events
    events = calendar.search(
        start=datetime.datetime.now(),
        end=datetime.datetime.now() + datetime.timedelta(days=7),
        event=True,
    )
    print(f"Found {len(events)} events in the next week")

    # Clean up
    event.delete()
    print("Deleted the test event")


if __name__ == "__main__":
    print("CalDAV get_calendars() Examples")
    print("================================")
    print()
    print("Note: These examples use placeholder URLs.")
    print("Set CALDAV_URL, CALDAV_USERNAME, CALDAV_PASSWORD environment")
    print("variables to test against a real server.")
    print()

    # Uncomment the examples you want to run:
    # example_get_all_calendars()
    # example_get_calendar_by_name()
    # example_get_multiple_calendars_by_name()
    # example_get_calendar_by_url()
    # example_error_handling()
    # example_working_with_events()
