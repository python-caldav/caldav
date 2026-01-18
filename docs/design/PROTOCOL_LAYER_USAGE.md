# Protocol Layer Usage Guide

This guide explains how to use the Sans-I/O protocol layer for testing and advanced use cases.

## Overview

The protocol layer (`caldav/protocol/`) provides pure functions for:
- **XML Building**: Construct request bodies without I/O
- **XML Parsing**: Parse response bodies without I/O

This separation enables:
- Easy testing without HTTP mocking
- Same code works for sync and async
- Clear separation of concerns

## Module Structure

```
caldav/protocol/
├── __init__.py      # Public exports
├── types.py         # DAVRequest, DAVResponse, result dataclasses
├── xml_builders.py  # Pure functions to build XML
└── xml_parsers.py   # Pure functions to parse XML
```

## Testing Without HTTP Mocking

The main benefit of the protocol layer is testability:

```python
from caldav.protocol import (
    build_propfind_body,
    build_calendar_query_body,
    parse_propfind_response,
    parse_calendar_query_response,
)

def test_propfind_body_building():
    """Test XML building - no HTTP needed."""
    body = build_propfind_body(["displayname", "resourcetype"])
    xml = body.decode("utf-8")

    assert "propfind" in xml.lower()
    assert "displayname" in xml.lower()
    assert "resourcetype" in xml.lower()

def test_propfind_response_parsing():
    """Test XML parsing - no HTTP needed."""
    xml = b'''<?xml version="1.0"?>
    <D:multistatus xmlns:D="DAV:">
        <D:response>
            <D:href>/calendars/user/</D:href>
            <D:propstat>
                <D:prop>
                    <D:displayname>My Calendar</D:displayname>
                </D:prop>
                <D:status>HTTP/1.1 200 OK</D:status>
            </D:propstat>
        </D:response>
    </D:multistatus>'''

    results = parse_propfind_response(xml, status_code=207)

    assert len(results) == 1
    assert results[0].href == "/calendars/user/"
    assert results[0].properties["{DAV:}displayname"] == "My Calendar"
```

## Available Functions

### XML Builders

```python
from caldav.protocol import (
    build_propfind_body,
    build_proppatch_body,
    build_calendar_query_body,
    build_calendar_multiget_body,
    build_sync_collection_body,
    build_mkcalendar_body,
    build_mkcol_body,
    build_freebusy_query_body,
)

# PROPFIND
body = build_propfind_body(["displayname", "resourcetype"])

# Calendar query with time range
body, comp_type = build_calendar_query_body(
    start=datetime(2024, 1, 1),
    end=datetime(2024, 12, 31),
    event=True,  # or todo=True, journal=True
)

# Multiget specific items
body = build_calendar_multiget_body([
    "/cal/event1.ics",
    "/cal/event2.ics",
])

# MKCALENDAR
body = build_mkcalendar_body(
    displayname="My Calendar",
    description="A test calendar",
)
```

### XML Parsers

```python
from caldav.protocol import (
    parse_multistatus,
    parse_propfind_response,
    parse_calendar_query_response,
    parse_calendar_multiget_response,
    parse_sync_collection_response,
)

# Parse PROPFIND response
results = parse_propfind_response(xml_body, status_code=207)
for result in results:
    print(f"href: {result.href}")
    print(f"props: {result.properties}")

# Parse calendar-query response
results = parse_calendar_query_response(xml_body, status_code=207)
for result in results:
    print(f"href: {result.href}")
    print(f"etag: {result.etag}")
    print(f"data: {result.calendar_data}")

# Parse sync-collection response
result = parse_sync_collection_response(xml_body, status_code=207)
print(f"changed: {result.changed}")
print(f"deleted: {result.deleted}")
print(f"sync_token: {result.sync_token}")
```

## Result Types

The parsers return typed dataclasses:

```python
from caldav.protocol import (
    PropfindResult,
    CalendarQueryResult,
    SyncCollectionResult,
    MultistatusResponse,
)

# PropfindResult
@dataclass
class PropfindResult:
    href: str
    properties: dict[str, Any]
    status: int = 200

# CalendarQueryResult
@dataclass
class CalendarQueryResult:
    href: str
    etag: str | None
    calendar_data: str | None

# SyncCollectionResult
@dataclass
class SyncCollectionResult:
    changed: list[CalendarQueryResult]
    deleted: list[str]
    sync_token: str | None
```

## Using with Custom HTTP

If you want to use the protocol layer with a different HTTP library:

```python
import httpx  # or any HTTP library
from caldav.protocol import build_propfind_body, parse_propfind_response

# Build request body
body = build_propfind_body(["displayname"])

# Make request with your HTTP library
response = httpx.request(
    "PROPFIND",
    "https://cal.example.com/calendars/",
    content=body,
    headers={
        "Content-Type": "application/xml",
        "Depth": "1",
    },
    auth=("user", "pass"),
)

# Parse response
results = parse_propfind_response(response.content, response.status_code)
```

## Integration with DAVClient

The protocol layer is used internally by `DAVClient` and `AsyncDAVClient`.
You can access parsed results via `response.results`:

```python
from caldav import DAVClient

client = DAVClient(url="https://cal.example.com", username="user", password="pass")
response = client.propfind(url, props=["displayname"], depth=1)

# Access pre-parsed results
for result in response.results:
    print(f"{result.href}: {result.properties}")

# Legacy method (deprecated but still works)
objects = response.find_objects_and_props()
```
