# Sans-I/O Design for CalDAV Library

**Last Updated:** January 2026
**Status:** Implemented (Protocol Layer), Refactoring In Progress

## What is Sans-I/O?

Sans-I/O separates **protocol logic** from **I/O operations**. The core idea is that
protocol handling (XML building, parsing, state management) should be pure functions
that don't do any I/O themselves.

## Current Implementation

The caldav library uses a **partial Sans-I/O** approach:

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Code                         │
│  (Calendar, Principal, Event, Todo, etc.)                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│            DAVClient / AsyncDAVClient                        │
│  - HTTP requests via niquests (sync or async)               │
│  - Auth negotiation                                          │
│  - Uses protocol layer for XML                               │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│               Protocol Layer (caldav/protocol/)              │
│  - xml_builders.py: Build XML request bodies (NO I/O)       │
│  - xml_parsers.py: Parse XML responses (NO I/O)             │
│  - types.py: DAVRequest, DAVResponse, result dataclasses    │
└─────────────────────────────────────────────────────────────┘
```

### Protocol Layer (`caldav/protocol/`)

The protocol layer is **pure Python with no I/O**. It provides:

#### Types (`types.py`)

```python
@dataclass(frozen=True)
class DAVRequest:
    """Immutable request descriptor - no I/O."""
    method: DAVMethod
    url: str
    headers: dict[str, str]
    body: bytes | None = None

@dataclass
class PropfindResult:
    """Parsed PROPFIND response item."""
    href: str
    properties: dict[str, Any]
    status: int

@dataclass
class CalendarQueryResult:
    """Parsed calendar-query response item."""
    href: str
    etag: str | None
    calendar_data: str | None
```

#### XML Builders (`xml_builders.py`)

Pure functions that return XML bytes:

```python
def build_propfind_body(props: list[str] | None = None) -> bytes:
    """Build PROPFIND request XML body."""

def build_calendar_query_body(
    start: datetime | None = None,
    end: datetime | None = None,
    event: bool = False,
    todo: bool = False,
) -> tuple[bytes, str]:
    """Build calendar-query REPORT body. Returns (xml_body, component_type)."""

def build_mkcalendar_body(
    displayname: str | None = None,
    description: str | None = None,
) -> bytes:
    """Build MKCALENDAR request body."""
```

#### XML Parsers (`xml_parsers.py`)

Pure functions that parse XML bytes into typed results:

```python
def parse_propfind_response(
    xml_body: bytes,
    status_code: int,
) -> list[PropfindResult]:
    """Parse PROPFIND multistatus response."""

def parse_calendar_query_response(
    xml_body: bytes,
    status_code: int,
) -> list[CalendarQueryResult]:
    """Parse calendar-query REPORT response."""

def parse_sync_collection_response(
    xml_body: bytes,
    status_code: int,
) -> SyncCollectionResult:
    """Parse sync-collection REPORT response."""
```

## Why Not Full Sans-I/O?

The original plan proposed a separate "I/O Shell" abstraction layer. This was
**abandoned** for practical reasons:

1. **niquests handles sync/async natively** - No need for a custom I/O abstraction
2. **Added complexity** - Extra layer without clear benefit
3. **Auth negotiation is I/O-dependent** - Hard to abstract cleanly

The current approach achieves the main Sans-I/O benefits:
- Protocol logic (XML) is testable without mocking HTTP
- Same XML builders/parsers work for sync and async
- Clear separation of concerns

## Remaining Work

### The Duplication Problem

`DAVClient` and `AsyncDAVClient` share ~65% identical code:

| Component | Duplication |
|-----------|-------------|
| `extract_auth_types()` | 100% identical |
| HTTP method wrappers | ~95% |
| `build_auth_object()` | ~70% |
| Response init logic | ~80% |

### Planned Refactoring

See [SANS_IO_IMPLEMENTATION_PLAN.md](SANS_IO_IMPLEMENTATION_PLAN.md) for details.

**Phase 2 (Current):** Extract shared utilities
- `caldav/lib/auth.py` - Auth helper functions
- `caldav/lib/constants.py` - Shared constants (CONNKEYS)

**Phase 3:** Consolidate response handling
- Move common logic to `BaseDAVResponse`

## Already Pure (No Changes Needed)

These modules are already Sans-I/O compliant:

| Module | Purpose |
|--------|---------|
| `caldav/elements/*.py` | XML element builders |
| `caldav/lib/url.py` | URL manipulation |
| `caldav/lib/namespace.py` | XML namespaces |
| `caldav/lib/vcal.py` | iCalendar handling |
| `caldav/lib/error.py` | Error classes |
| `caldav/protocol/*` | Protocol layer |

## Testing Benefits

The Sans-I/O protocol layer enables pure unit tests:

```python
def test_build_propfind_body():
    """Test XML building without HTTP mocking."""
    body = build_propfind_body(["displayname", "resourcetype"])
    xml = body.decode("utf-8").lower()
    assert "propfind" in xml
    assert "displayname" in xml

def test_parse_propfind_response():
    """Test XML parsing without HTTP mocking."""
    xml = b'''<?xml version="1.0"?>
    <D:multistatus xmlns:D="DAV:">
        <D:response>
            <D:href>/calendars/</D:href>
            <D:propstat>
                <D:prop><D:displayname>My Cal</D:displayname></D:prop>
                <D:status>HTTP/1.1 200 OK</D:status>
            </D:propstat>
        </D:response>
    </D:multistatus>'''

    results = parse_propfind_response(xml, status_code=207)
    assert len(results) == 1
    assert results[0].properties["{DAV:}displayname"] == "My Cal"
```

These tests run fast, don't require network access, and don't need HTTP mocking.
