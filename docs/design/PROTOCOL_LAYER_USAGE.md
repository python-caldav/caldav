# Protocol Layer Usage Guide

This guide explains how to use the Sans-I/O protocol layer directly for advanced use cases.

## Overview

The protocol layer provides a clean separation between:
- **Protocol logic**: Building requests, parsing responses (no I/O)
- **I/O layer**: Actually sending/receiving HTTP (thin wrapper)

This architecture enables:
- Easy testing without HTTP mocking
- Pluggable HTTP libraries
- Clear separation of concerns

## Quick Start

### Using the High-Level Protocol Client

For most use cases, use `SyncProtocolClient` or `AsyncProtocolClient`:

```python
from caldav.protocol_client import SyncProtocolClient

# Create client
client = SyncProtocolClient(
    base_url="https://cal.example.com",
    username="user",
    password="pass",
)

# Use as context manager for proper cleanup
with client:
    # List calendars
    calendars = client.propfind("/calendars/", ["displayname"], depth=1)
    for cal in calendars:
        print(f"{cal.href}: {cal.properties}")

    # Search for events
    from datetime import datetime
    events = client.calendar_query(
        "/calendars/user/cal/",
        start=datetime(2024, 1, 1),
        end=datetime(2024, 12, 31),
        event=True,
    )
    for event in events:
        print(f"Event: {event.href}")
        print(f"Data: {event.calendar_data[:100]}...")
```

### Async Version

```python
from caldav.protocol_client import AsyncProtocolClient
import asyncio

async def main():
    async with AsyncProtocolClient(
        base_url="https://cal.example.com",
        username="user",
        password="pass",
    ) as client:
        calendars = await client.propfind("/calendars/", ["displayname"], depth=1)
        for cal in calendars:
            print(f"{cal.href}: {cal.properties}")

asyncio.run(main())
```

## Low-Level Protocol Access

For maximum control, use the protocol layer directly:

### Building Requests

```python
from caldav.protocol import CalDAVProtocol, DAVMethod

# Create protocol instance (no I/O happens here)
protocol = CalDAVProtocol(
    base_url="https://cal.example.com",
    username="user",
    password="pass",
)

# Build a PROPFIND request
request = protocol.propfind_request(
    path="/calendars/",
    props=["displayname", "resourcetype"],
    depth=1,
)

print(f"Method: {request.method}")      # DAVMethod.PROPFIND
print(f"URL: {request.url}")            # https://cal.example.com/calendars/
print(f"Headers: {request.headers}")    # {'Content-Type': '...', 'Authorization': '...', 'Depth': '1'}
print(f"Body: {request.body[:100]}...")  # XML body
```

### Executing Requests

```python
from caldav.io import SyncIO

# Create I/O handler
io = SyncIO(timeout=30.0, verify=True)

# Execute request
response = io.execute(request)

print(f"Status: {response.status}")     # 207
print(f"Headers: {response.headers}")
print(f"Body: {response.body[:100]}...")

io.close()
```

### Parsing Responses

```python
# Parse the response
results = protocol.parse_propfind(response)

for result in results:
    print(f"Resource: {result.href}")
    print(f"Properties: {result.properties}")
    print(f"Status: {result.status}")
```

## Available Request Builders

The `CalDAVProtocol` class provides these request builders:

| Method | Description |
|--------|-------------|
| `propfind_request()` | PROPFIND to get resource properties |
| `proppatch_request()` | PROPPATCH to set properties |
| `calendar_query_request()` | calendar-query REPORT for searching |
| `calendar_multiget_request()` | calendar-multiget REPORT |
| `sync_collection_request()` | sync-collection REPORT |
| `freebusy_request()` | free-busy-query REPORT |
| `mkcalendar_request()` | MKCALENDAR to create calendars |
| `get_request()` | GET to retrieve resources |
| `put_request()` | PUT to create/update resources |
| `delete_request()` | DELETE to remove resources |
| `options_request()` | OPTIONS to query capabilities |

## Available Response Parsers

| Method | Returns |
|--------|---------|
| `parse_propfind()` | `List[PropfindResult]` |
| `parse_calendar_query()` | `List[CalendarQueryResult]` |
| `parse_calendar_multiget()` | `List[CalendarQueryResult]` |
| `parse_sync_collection()` | `SyncCollectionResult` |

## Result Types

### PropfindResult

```python
@dataclass
class PropfindResult:
    href: str                    # Resource URL/path
    properties: Dict[str, Any]   # Property name -> value
    status: int = 200            # HTTP status for this resource
```

### CalendarQueryResult

```python
@dataclass
class CalendarQueryResult:
    href: str                    # Calendar object URL
    etag: Optional[str]          # ETag for conditional updates
    calendar_data: Optional[str] # iCalendar data
    status: int = 200
```

### SyncCollectionResult

```python
@dataclass
class SyncCollectionResult:
    changed: List[CalendarQueryResult]  # Changed/new items
    deleted: List[str]                   # Deleted hrefs
    sync_token: Optional[str]            # New sync token
```

## Testing with Protocol Layer

The protocol layer makes testing easy - no HTTP mocking required:

```python
from caldav.protocol import CalDAVProtocol, DAVResponse

def test_propfind_parsing():
    protocol = CalDAVProtocol()

    # Create a fake response (no network needed)
    response = DAVResponse(
        status=207,
        headers={},
        body=b'''<?xml version="1.0"?>
        <D:multistatus xmlns:D="DAV:">
            <D:response>
                <D:href>/calendars/</D:href>
                <D:propstat>
                    <D:prop><D:displayname>Test</D:displayname></D:prop>
                    <D:status>HTTP/1.1 200 OK</D:status>
                </D:propstat>
            </D:response>
        </D:multistatus>''',
    )

    # Test parsing
    results = protocol.parse_propfind(response)
    assert len(results) == 1
    assert results[0].href == "/calendars/"
```

## Using a Custom HTTP Library

The I/O layer is pluggable. To use a different HTTP library:

```python
from caldav.protocol import DAVRequest, DAVResponse
import httpx  # or any HTTP library

class HttpxIO:
    def __init__(self):
        self.client = httpx.Client()

    def execute(self, request: DAVRequest) -> DAVResponse:
        response = self.client.request(
            method=request.method.value,
            url=request.url,
            headers=request.headers,
            content=request.body,
        )
        return DAVResponse(
            status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    def close(self):
        self.client.close()

# Use with protocol
protocol = CalDAVProtocol(base_url="https://cal.example.com")
io = HttpxIO()

request = protocol.propfind_request("/calendars/", ["displayname"])
response = io.execute(request)
results = protocol.parse_propfind(response)

io.close()
```

## Using response.results with DAVClient

The standard `DAVClient` and `AsyncDAVClient` now expose parsed results via `response.results`:

```python
from caldav import get_davclient

# Use get_davclient() factory method (recommended)
client = get_davclient(url="https://cal.example.com", username="user", password="pass")

with client:
    # propfind returns DAVResponse with parsed results
    response = client.propfind("/calendars/", depth=1)

    # New interface: use response.results for pre-parsed values
    if response.results:
        for result in response.results:
            print(f"Resource: {result.href}")
            print(f"Display name: {result.properties.get('{DAV:}displayname')}")

    # Deprecated: find_objects_and_props() still works but shows warning
    # objects = response.find_objects_and_props()  # DeprecationWarning
```

### Async version

```python
from caldav.aio import get_async_davclient
import asyncio

async def main():
    # Use get_async_davclient() factory method (recommended)
    client = get_async_davclient(url="https://cal.example.com", username="user", password="pass")

    async with client:
        response = await client.propfind("/calendars/", depth=1)

        for result in response.results:
            print(f"{result.href}: {result.properties}")

asyncio.run(main())
```

## Comparison with Standard Client

| Feature | DAVClient | SyncProtocolClient |
|---------|-----------|-------------------|
| Ease of use | High | Medium |
| Control | Medium | High |
| Testability | Needs mocking | Pure unit tests |
| HTTP library | requests/niquests | Pluggable |
| Feature completeness | Full | Core operations |

**Use `DAVClient`** for:
- Most applications
- Full feature set (scheduling, freebusy, etc.)
- Automatic discovery

**Use `SyncProtocolClient`** for:
- Advanced use cases
- Custom HTTP handling
- Maximum testability
- Learning the CalDAV protocol

## File Structure

```
caldav/
├── protocol/                    # Sans-I/O protocol layer
│   ├── __init__.py             # Exports
│   ├── types.py                # DAVRequest, DAVResponse, result types
│   ├── xml_builders.py         # Pure XML construction
│   ├── xml_parsers.py          # Pure XML parsing
│   └── operations.py           # CalDAVProtocol class
│
├── io/                          # I/O implementations
│   ├── __init__.py
│   ├── base.py                 # Protocol definitions
│   ├── sync.py                 # SyncIO (requests)
│   └── async_.py               # AsyncIO (aiohttp)
│
└── protocol_client.py          # High-level protocol clients
```
