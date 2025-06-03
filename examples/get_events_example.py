#!/usr/bin/env python3
import json

## Code contributed by Крылов Александр.  Minor changes and quite some
## comments by Tobias Brox.

## Set CALDAV_USERNAME, CALDAV_URL and CALDAV_PASSWORD through
## environment variables before running this example

from caldav.davclient import get_davclient

def fetch_and_print():
    with get_davclient() as client:
        print_calendars_demo(client.principal().calendars())

def print_calendars_demo(calendars):
    if not calendars:
        return
    events = []
    for calendar in calendars:
        for event in calendar.events():
            ## Most calendar events will have only one component,
            ## and it can be accessed simply as event.component
            ## The exception is special recurrences, to handle those
            ## we may need to do the walk:
            for component in event.icalendar_instance.walk():
                if component.name != "VEVENT":
                    continue
                events.append(fill_event(component, calendar))
    print(json.dumps(events, indent=2, ensure_ascii=False))

def fill_event(component, calendar) -> dict[str, str]:
    ## quite some data is tossed away here - like, the recurring rule.
    cur = {}
    cur["calendar"] = f"{calendar}"
    cur["summary"] = component.get("summary")
    cur["description"] = component.get("description")
    cur["start"] = component.start.strftime("%m/%d/%Y %H:%M")
    endDate = component.end
    if endDate:
        cur["end"] = endDate.strftime("%m/%d/%Y %H:%M")
    ## For me the following line breaks because some imported calendar events
    ## came without dtstamp.  But dtstamp is mandatory according to the RFC
    cur["datestamp"] = component.get("dtstamp").dt.strftime("%m/%d/%Y %H:%M")
    return cur

if __name__ == "__main__":
    fetch_and_print()
