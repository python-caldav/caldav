#!/usr/bin/env python
"""
Example demonstrating case-sensitive and case-insensitive calendar searches.

This example shows how to perform text searches on calendar events with
different case sensitivity settings. The collation settings are automatically
passed to the CalDAV server.
"""

import sys
from datetime import datetime

sys.path.insert(0, "..")
sys.path.insert(0, ".")

from caldav import get_davclient
from caldav.search import CalDAVSearcher


def run_examples():
    """Run all examples with a real CalDAV server."""
    print("=" * 80)
    print("CalDAV Case-Sensitive and Case-Insensitive Search Examples")
    print("=" * 80)

    with get_davclient() as client:
        calendar = client.principal().get_calendars()[0]

        # Create some test events with different cases
        print("\nCreating test events...")
        calendar.add_event(
            dtstart=datetime(2025, 6, 1, 10, 0),
            dtend=datetime(2025, 6, 1, 11, 0),
            summary="Team Meeting",
        )
        calendar.add_event(
            dtstart=datetime(2025, 6, 2, 14, 0),
            dtend=datetime(2025, 6, 2, 15, 0),
            summary="team meeting",
        )
        calendar.add_event(
            dtstart=datetime(2025, 6, 3, 9, 0),
            dtend=datetime(2025, 6, 3, 10, 0),
            summary="MEETING with clients",
            location="Conference Room A",
        )

        # Example 1: Case-sensitive search (default)
        print("\n" + "=" * 80)
        print("Example 1: Case-Sensitive Search (Default)")
        print("=" * 80)
        print("Using calendar.search() - default is case-sensitive")
        events = calendar.search(
            start=datetime(2025, 6, 1),
            end=datetime(2025, 6, 30),
            event=True,
            summary="meeting",  # Only matches lowercase "meeting"
        )
        print(f"Found {len(events)} event(s) matching 'meeting' (case-sensitive)")
        for event in events:
            print(f"  - {event.icalendar_component['SUMMARY']}")

        # Example 2: Case-insensitive search using CalDAVSearcher
        print("\n" + "=" * 80)
        print("Example 2: Case-Insensitive Search")
        print("=" * 80)
        print("Using CalDAVSearcher with case_sensitive=False")
        searcher = CalDAVSearcher(
            event=True,
            start=datetime(2025, 6, 1),
            end=datetime(2025, 6, 30),
        )
        searcher.add_property_filter("SUMMARY", "meeting", case_sensitive=False)
        events = searcher.search(calendar)
        print(f"Found {len(events)} event(s) matching 'meeting' (case-insensitive)")
        for event in events:
            print(f"  - {event.icalendar_component['SUMMARY']}")

        # Example 3: Mixed case sensitivity
        print("\n" + "=" * 80)
        print("Example 3: Mixed Case Sensitivity")
        print("=" * 80)
        print("Different properties with different case sensitivities")
        searcher = CalDAVSearcher(
            event=True,
            start=datetime(2025, 6, 1),
            end=datetime(2025, 6, 30),
        )
        searcher.add_property_filter("SUMMARY", "meeting", case_sensitive=True)
        searcher.add_property_filter("LOCATION", "room", case_sensitive=False)

        events = searcher.search(calendar)
        print(f"Found {len(events)} event(s) with 'meeting' (case-sensitive) in summary")
        print("  AND 'room' (case-insensitive) in location")
        for event in events:
            comp = event.icalendar_component
            print(f"  - {comp.get('SUMMARY', 'N/A')} @ {comp.get('LOCATION', 'N/A')}")

    print("\n" + "=" * 80)
    print("Summary:")
    print("- By default, searches are case-sensitive")
    print("- For case-insensitive searches, use CalDAVSearcher with case_sensitive=False")
    print("- The CalDAVSearcher API allows mixing case sensitivities on different properties")
    print("=" * 80)


if __name__ == "__main__":
    run_examples()
