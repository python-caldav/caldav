## Async CalDAV API

The caldav library provides a modern async/await API for CalDAV operations through the `caldav.aio` module.

### Features

- **True async I/O** using niquests.AsyncSession (HTTP/1.1, HTTP/2, HTTP/3)
- **Clean, Pythonic API** designed from scratch for async/await
- **Type hints** for better IDE support
- **Minimal dependencies** - reuses XML parsing and iCalendar logic from the sync library
- **No code duplication** - doesn't maintain backward compatibility with the sync API

### Requirements

The async API requires niquests:

```bash
pip install -U niquests
```

### Quick Start

```python
import asyncio
from caldav import aio

async def main():
    async with aio.CalDAVClient(
        url="https://caldav.example.com",
        username="user",
        password="pass"
    ) as client:
        # Get all calendars
        calendars = await client.get_calendars()

        # Get a specific calendar
        cal = await client.get_calendar("Personal")

        # Fetch events
        events = await cal.get_events()
        for event in events:
            print(event.summary)

asyncio.run(main())
```

### API Reference

#### CalDAVClient

Main client class for async CalDAV operations.

```python
async with aio.CalDAVClient(
    url: str,                          # CalDAV server URL
    username: str | None = None,       # Username for authentication
    password: str | None = None,       # Password for authentication
    auth: AuthBase | None = None,      # Custom auth object
    timeout: int = 90,                 # Request timeout in seconds
    verify_ssl: bool = True,           # Verify SSL certificates
    ssl_cert: str | None = None,       # Client SSL certificate
    headers: dict | None = None,       # Additional HTTP headers
) as client:
    ...
```

**Methods:**

- `await get_calendars() -> List[Calendar]` - Get all calendars
- `await get_calendar(name: str) -> Calendar | None` - Get calendar by name
- `await get_principal_url() -> URL` - Get principal URL
- `await get_calendar_home_url() -> URL` - Get calendar home URL

**Low-level methods:**

- `await request(url, method, body, headers) -> Response` - Raw HTTP request
- `await propfind(url, props, depth) -> etree._Element` - PROPFIND request
- `await report(url, query, depth) -> etree._Element` - REPORT request

#### Calendar

Represents a CalDAV calendar.

**Properties:**

- `client: CalDAVClient` - The client this calendar belongs to
- `url: URL` - Calendar URL
- `name: str | None` - Display name of the calendar

**Methods:**

- `await get_events(start=None, end=None) -> List[Event]` - Get events
  - `start: date | datetime | None` - Filter by start date/time
  - `end: date | datetime | None` - Filter by end date/time

- `await create_event(ical_data: str, uid: str | None = None) -> Event` - Create event
  - `ical_data: str` - iCalendar data (VCALENDAR with VEVENT)
  - `uid: str | None` - Optional UID (generated if not provided)

#### Event

Represents a CalDAV event.

**Properties:**

- `client: CalDAVClient` - The client this event belongs to
- `url: URL` - Event URL
- `ical_data: str` - Raw iCalendar data
- `summary: str` - Event summary/title
- `uid: str` - Event UID
- `dtstart` - Start date/time
- `dtend` - End date/time

**Methods:**

- `await delete() -> None` - Delete this event
- `await update(ical_data: str) -> None` - Update this event

### Examples

#### List all calendars

```python
async with aio.CalDAVClient(url, username, password) as client:
    calendars = await client.get_calendars()
    for cal in calendars:
        print(f"{cal.name}: {cal.url}")
```

#### Get events for a date range

```python
from datetime import date, timedelta

async with aio.CalDAVClient(url, username, password) as client:
    cal = await client.get_calendar("Work")

    today = date.today()
    next_week = today + timedelta(days=7)

    events = await cal.get_events(start=today, end=next_week)
    for event in events:
        print(f"{event.summary} - {event.dtstart}")
```

#### Create an event

```python
ical_data = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//My App//EN
BEGIN:VEVENT
UID:unique-id-123
DTSTART:20250115T100000Z
DTEND:20250115T110000Z
SUMMARY:Team Meeting
DESCRIPTION:Weekly sync
END:VEVENT
END:VCALENDAR"""

async with aio.CalDAVClient(url, username, password) as client:
    cal = await client.get_calendar("Work")
    event = await cal.create_event(ical_data)
    print(f"Created: {event.summary}")
```

#### Parallel operations

```python
async with aio.CalDAVClient(url, username, password) as client:
    calendars = await client.get_calendars()

    # Fetch events from all calendars in parallel
    tasks = [cal.get_events() for cal in calendars]
    results = await asyncio.gather(*tasks)

    for cal, events in zip(calendars, results):
        print(f"{cal.name}: {len(events)} events")
```

#### Update an event

```python
async with aio.CalDAVClient(url, username, password) as client:
    cal = await client.get_calendar("Personal")
    events = await cal.get_events()

    if events:
        event = events[0]
        # Modify the iCalendar data
        new_ical = event.ical_data.replace(
            "SUMMARY:Old Title",
            "SUMMARY:New Title"
        )
        await event.update(new_ical)
        print("Event updated")
```

#### Delete an event

```python
async with aio.CalDAVClient(url, username, password) as client:
    cal = await client.get_calendar("Personal")
    events = await cal.get_events()

    if events:
        await events[0].delete()
        print("Event deleted")
```

### Design Philosophy

The async API (`caldav.aio`) is designed as a **separate, modern API** rather than a wrapper around the sync code:

1. **No backward compatibility burden** - Clean API without legacy constraints
2. **Minimal code** - ~400 lines vs thousands for the sync API
3. **Pythonic** - Uses modern Python idioms and conventions
4. **Fast** - Direct async I/O without thread pools or wrappers
5. **Maintainable** - Simple, focused codebase

### Comparison with Sync API

| Feature | Sync API | Async API |
|---------|----------|-----------|
| Import | `from caldav import DAVClient` | `from caldav import aio` |
| Style | Legacy, backward-compatible | Modern, clean |
| Code size | ~3000+ lines | ~400 lines |
| HTTP library | niquests/requests (sync) | niquests.AsyncSession |
| Complexity | High (20+ years of evolution) | Low (greenfield design) |
| Use case | Production, compatibility | New projects, async frameworks |

### When to Use

**Use the async API when:**
- Building new async applications (FastAPI, aiohttp, etc.)
- Need to handle many concurrent CalDAV operations
- Want a clean, modern Python API
- Performance is critical

**Use the sync API when:**
- Need backward compatibility
- Working with sync code
- Need advanced features not yet in async API
- Production stability is critical

### Future Development

The async API is a **minimal viable implementation**. Future additions may include:

- Full CalDAV feature parity (todos, journals, freebusy)
- CalDAV-search support
- WebDAV sync operations
- Advanced filtering and querying
- Batch operations

Contributions welcome!

### See Also

- [Full async example](../examples/async_example.py)
- [Sync API documentation](../README.md)
- [niquests documentation](https://niquests.readthedocs.io/)
