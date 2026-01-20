# Code Flow for Common CalDAV Operations

**Last Updated:** January 2026

This document explains how the caldav library processes common operations, showing the code flow through the layered architecture for both synchronous and asynchronous usage.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     User Application                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│              Domain Objects (Dual-Mode)                      │
│  Calendar, Principal, Event, Todo, Journal, FreeBusy        │
│  caldav/collection.py, caldav/objects/*.py                  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│              Operations Layer (Pure Python)                  │
│  caldav/operations/*.py                                      │
│  - Builds requests using Protocol Layer                      │
│  - Returns request descriptors (no I/O)                      │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│              Protocol Layer (Sans-I/O)                       │
│  caldav/protocol/                                            │
│  - xml_builders.py: Build XML bodies                         │
│  - xml_parsers.py: Parse XML responses                       │
│  - types.py: DAVRequest, DAVResponse, result dataclasses    │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│         DAVClient (Sync) / AsyncDAVClient (Async)           │
│  caldav/davclient.py, caldav/async_davclient.py             │
│  - Executes HTTP requests via niquests/httpx                │
│  - Handles authentication                                    │
└─────────────────────────────────────────────────────────────┘
```

## Flow 1: Fetching Calendars (Sync)

**User Code:**
```python
from caldav import DAVClient

client = DAVClient(url="https://server/dav/", username="user", password="pass")
principal = client.principal()
calendars = principal.get_calendars()
```

**Internal Flow:**

```
1. client.principal()
   └─► Principal(client=self, url=self.url)

2. principal.get_calendars()
   │
   ├─► _get_calendar_home_set()
   │   ├─► Protocol: build_propfind_body(["{DAV:}current-user-principal"])
   │   ├─► Client: propfind(url, body, depth=0)
   │   │   └─► HTTP PROPFIND → Response
   │   └─► Protocol: parse_propfind_response(response.body)
   │
   ├─► Protocol: build_propfind_body(["{DAV:}resourcetype", ...])
   │
   ├─► Client: propfind(calendar_home_url, body, depth=1)
   │   └─► HTTP PROPFIND → Response
   │
   ├─► Protocol: parse_propfind_response(response.body)
   │
   └─► Returns: [Calendar(...), Calendar(...), ...]
```

**Key Files:**
- `caldav/davclient.py:DAVClient.principal()` (line ~470)
- `caldav/collection.py:Principal.get_calendars()` (line ~290)
- `caldav/protocol/xml_builders.py:_build_propfind_body()`
- `caldav/protocol/xml_parsers.py:_parse_propfind_response()`

## Flow 2: Fetching Calendars (Async)

**User Code:**
```python
from caldav.aio import AsyncDAVClient

async with AsyncDAVClient(url="https://server/dav/", username="user", password="pass") as client:
    principal = await client.principal()
    calendars = await principal.get_calendars()
```

**Internal Flow:**

```
1. await client.principal()
   └─► Principal(client=self, url=self.url)
       (Principal detects async client, enables async mode)

2. await principal.get_calendars()
   │
   ├─► await _get_calendar_home_set()
   │   ├─► Protocol: build_propfind_body(...)  # Same as sync
   │   ├─► await Client: propfind(...)
   │   │   └─► async HTTP PROPFIND → Response
   │   └─► Protocol: parse_propfind_response(...)  # Same as sync
   │
   ├─► await Client: propfind(calendar_home_url, ...)
   │
   └─► Returns: [Calendar(...), Calendar(...), ...]
```

**Key Difference:** Domain objects (Calendar, Principal, etc.) are "dual-mode" - they detect whether they have a sync or async client and behave accordingly. The Protocol layer is identical for both.

## Flow 3: Creating an Event

**User Code (Sync):**
```python
calendar.add_event(
    dtstart=datetime(2024, 6, 15, 10, 0),
    dtend=datetime(2024, 6, 15, 11, 0),
    summary="Meeting"
)
```

**User Code (Async):**
```python
await calendar.add_event(
    dtstart=datetime(2024, 6, 15, 10, 0),
    dtend=datetime(2024, 6, 15, 11, 0),
    summary="Meeting"
)
```

**Internal Flow:**

```
1. calendar.add_event(dtstart, dtend, summary, ...)
   │
   ├─► Build iCalendar data (icalendar library)
   │   └─► VCALENDAR with VEVENT component
   │
   ├─► Generate URL: calendar.url + uuid + ".ics"
   │
   ├─► Client: put(url, data, headers={"Content-Type": "text/calendar"})
   │   └─► HTTP PUT → Response (201 Created)
   │
   └─► Returns: Event(client, url, data, parent=calendar)
```

**Key Files:**
- `caldav/collection.py:Calendar.add_event()` (line ~880)
- `caldav/objects/base.py:CalendarObjectResource.save()` (line ~230)

## Flow 4: Searching for Events

**User Code:**
```python
events = calendar.search(
    start=datetime(2024, 1, 1),
    end=datetime(2024, 12, 31),
    event=True
)
```

**Internal Flow:**

```
1. calendar.search(start, end, event=True)
   │
   ├─► Protocol: build_calendar_query_body(start, end, event=True)
   │   └─► Returns: (xml_body, "VEVENT")
   │
   ├─► Client: report(calendar.url, body, depth=1)
   │   └─► HTTP REPORT → Response (207 Multi-Status)
   │
   ├─► Protocol: parse_calendar_query_response(response.body)
   │   └─► Returns: [CalendarQueryResult(href, etag, calendar_data), ...]
   │
   ├─► Wrap results in Event objects
   │
   └─► Returns: [Event(...), Event(...), ...]
```

**Key Files:**
- `caldav/collection.py:Calendar.search()` (line ~670)
- `caldav/search.py:CalDAVSearcher` (handles complex search logic)
- `caldav/protocol/xml_builders.py:_build_calendar_query_body()`
- `caldav/protocol/xml_parsers.py:_parse_calendar_query_response()`

## Flow 5: Sync Token Synchronization

**User Code:**
```python
# Initial sync
sync_token, items = calendar.get_objects_by_sync_token()

# Incremental sync
sync_token, changed, deleted = calendar.get_objects_by_sync_token(sync_token=sync_token)
```

**Internal Flow:**

```
1. calendar.get_objects_by_sync_token(sync_token=None)
   │
   ├─► Protocol: build_sync_collection_body(sync_token="")
   │
   ├─► Client: report(calendar.url, body)
   │   └─► HTTP REPORT → Response (207)
   │
   ├─► Protocol: parse_sync_collection_response(response.body)
   │   └─► SyncCollectionResult(changed, deleted, sync_token)
   │
   └─► Returns: (new_sync_token, [objects...])

2. calendar.get_objects_by_sync_token(sync_token="token-123")
   │
   ├─► Protocol: build_sync_collection_body(sync_token="token-123")
   │
   ├─► Client: report(...)
   │
   ├─► Protocol: parse_sync_collection_response(...)
   │   └─► Returns changed items and deleted hrefs
   │
   └─► Returns: (new_sync_token, changed_objects, deleted_hrefs)
```

**Key Files:**
- `caldav/collection.py:Calendar.get_objects_by_sync_token()` (line ~560)
- `caldav/protocol/xml_builders.py:_build_sync_collection_body()`
- `caldav/protocol/xml_parsers.py:_parse_sync_collection_response()`

## Flow 6: Creating a Calendar

**User Code:**
```python
new_calendar = principal.make_calendar(
    name="Work",
    cal_id="work-calendar"
)
```

**Internal Flow:**

```
1. principal.make_calendar(name="Work", cal_id="work-calendar")
   │
   ├─► Build URL: calendar_home_set + cal_id + "/"
   │
   ├─► Protocol: build_mkcalendar_body(displayname="Work")
   │
   ├─► Client: mkcalendar(url, body)
   │   └─► HTTP MKCALENDAR → Response (201)
   │
   └─► Returns: Calendar(client, url, props={displayname: "Work"})
```

**Key Files:**
- `caldav/collection.py:Principal.make_calendar()` (line ~430)
- `caldav/protocol/xml_builders.py:_build_mkcalendar_body()`

## HTTP Methods Used

| CalDAV Operation | HTTP Method | When Used |
|-----------------|-------------|-----------|
| Get properties | PROPFIND | Discovery, getting calendar lists |
| Search events | REPORT | calendar-query, calendar-multiget, sync-collection |
| Create calendar | MKCALENDAR | Creating new calendars |
| Create/update item | PUT | Saving events, todos, journals |
| Delete item | DELETE | Removing calendars or items |
| Get item | GET | Fetching single item |

## Dual-Mode Domain Objects

Domain objects like `Calendar`, `Principal`, `Event` work with both sync and async clients:

```python
class Calendar(DAVObject):
    def calendars(self):
        if self._is_async:
            return self._calendars_async()
        return self._calendars_sync()

    async def _calendars_async(self):
        # Async implementation using await
        response = await self.client.propfind(...)
        ...

    def _calendars_sync(self):
        # Sync implementation
        response = self.client.propfind(...)
        ...
```

The `_is_async` property checks if `self.client` is an `AsyncDAVClient` instance.

## Protocol Layer Independence

The Protocol layer functions are pure and work identically for sync/async:

```python
# Same function used by both sync and async paths
body = _build_calendar_query_body(start=dt1, end=dt2, event=True)

# Same parser used by both paths
results = _parse_calendar_query_response(response.body, status_code=207)
```

This separation means:
1. Protocol logic can be unit tested without HTTP mocking
2. Any bug fixes in parsing benefit both sync and async
3. Adding new CalDAV features only requires changes in one place

## Error Handling Flow

```
1. Client makes HTTP request
   │
   ├─► Success (2xx/207): Parse response, return result
   │
   ├─► Auth required (401): Negotiate auth, retry
   │
   ├─► Not found (404): Raise NotFoundError or return empty
   │
   ├─► Server error (5xx): Raise DAVError with details
   │
   └─► Malformed response: Log warning, attempt recovery or raise
```

Errors are defined in `caldav/lib/error.py` and include:
- `AuthorizationError` - Authentication failed
- `NotFoundError` - Resource doesn't exist
- `DAVError` - General WebDAV/CalDAV errors
- `ReportError` - REPORT request failed
