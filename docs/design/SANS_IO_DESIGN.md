# Sans-I/O Design Plan for CalDAV Library

This document outlines how a Sans-I/O architecture could be implemented for the
caldav library. This is an **alternative approach** to the current playground
branch implementation, presented for comparison and future consideration.

## What is Sans-I/O?

Sans-I/O separates **protocol logic** from **I/O operations**:

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Code                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                 I/O Shell (Sync or Async)                    │
│  - Makes HTTP requests (requests/aiohttp)                    │
│  - Passes bytes to/from protocol layer                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Protocol Layer (Pure Python)               │
│  - Builds HTTP requests (method, headers, body)              │
│  - Parses HTTP responses                                     │
│  - Manages state and business logic                          │
│  - NO network I/O                                            │
└─────────────────────────────────────────────────────────────┘
```

## Current Codebase Analysis

### Already Sans-I/O (no changes needed)

These modules contain pure logic with no I/O:

| Module | Purpose |
|--------|---------|
| `caldav/elements/*.py` | XML element builders (CalendarQuery, Filter, etc.) |
| `caldav/lib/url.py` | URL manipulation and parsing |
| `caldav/lib/namespace.py` | XML namespace definitions |
| `caldav/lib/vcal.py` | iCalendar data handling |
| `caldav/lib/error.py` | Error classes |
| `caldav/response.py` | `BaseDAVResponse` XML parsing (partially) |

### Mixed I/O and Protocol Logic (needs separation)

| Module | I/O | Protocol Logic |
|--------|-----|----------------|
| `davclient.py` | HTTP session, request() | URL building, auth setup, header management |
| `collection.py` | Calls client methods | XML query building, response interpretation |
| `davobject.py` | Calls client methods | Property handling, iCal parsing |
| `search.py` | Calls `_request_report_build_resultlist` | `build_search_xml_query()`, filtering |

## Proposed Architecture

### Layer 1: Protocol Core (`caldav/protocol/`)

Pure Python, no I/O. Produces requests, consumes responses.

```
caldav/protocol/
├── __init__.py
├── requests.py      # Request builders
├── responses.py     # Response parsers
├── state.py         # Connection state, auth state
├── calendar.py      # Calendar protocol operations
├── principal.py     # Principal discovery protocol
└── objects.py       # CalendarObject protocol operations
```

#### Request Builder Example

```python
# caldav/protocol/requests.py
from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class DAVRequest:
    """Represents an HTTP request to be made."""
    method: str
    path: str
    headers: Dict[str, str]
    body: Optional[bytes] = None

@dataclass
class DAVResponse:
    """Represents an HTTP response received."""
    status: int
    headers: Dict[str, str]
    body: bytes

class CalDAVProtocol:
    """
    Sans-I/O CalDAV protocol handler.

    Builds requests and parses responses without doing any I/O.
    """

    def __init__(self, base_url: str, username: str = None, password: str = None):
        self.base_url = URL(base_url)
        self.username = username
        self.password = password
        self._auth_headers = self._build_auth_headers()

    def propfind_request(
        self,
        path: str,
        props: list[str],
        depth: int = 0
    ) -> DAVRequest:
        """Build a PROPFIND request."""
        body = self._build_propfind_body(props)
        return DAVRequest(
            method="PROPFIND",
            path=path,
            headers={
                **self._auth_headers,
                "Depth": str(depth),
                "Content-Type": "application/xml; charset=utf-8",
            },
            body=body.encode("utf-8"),
        )

    def parse_propfind_response(
        self,
        response: DAVResponse
    ) -> dict:
        """Parse a PROPFIND response into structured data."""
        if response.status not in (200, 207):
            raise DAVError(f"PROPFIND failed: {response.status}")

        tree = etree.fromstring(response.body)
        return self._extract_properties(tree)

    def calendar_query_request(
        self,
        path: str,
        start: datetime = None,
        end: datetime = None,
        expand: bool = False,
    ) -> DAVRequest:
        """Build a calendar-query REPORT request."""
        xml = self._build_calendar_query(start, end, expand)
        return DAVRequest(
            method="REPORT",
            path=path,
            headers={
                **self._auth_headers,
                "Depth": "1",
                "Content-Type": "application/xml; charset=utf-8",
            },
            body=etree.tostring(xml, encoding="utf-8"),
        )
```

#### Protocol State Machine

```python
# caldav/protocol/state.py
from enum import Enum, auto

class AuthState(Enum):
    UNAUTHENTICATED = auto()
    BASIC = auto()
    DIGEST = auto()
    BEARER = auto()

class CalDAVState:
    """
    Tracks protocol state across requests.

    Handles:
    - Authentication negotiation
    - Sync tokens
    - Discovered capabilities
    """

    def __init__(self):
        self.auth_state = AuthState.UNAUTHENTICATED
        self.sync_token: Optional[str] = None
        self.supported_features: set[str] = set()
        self.calendar_home_set: Optional[str] = None

    def handle_auth_challenge(self, response: DAVResponse) -> Optional[DAVRequest]:
        """
        Handle 401 response, return retry request if auth can be negotiated.
        """
        if response.status != 401:
            return None

        www_auth = response.headers.get("WWW-Authenticate", "")
        if "Digest" in www_auth:
            self.auth_state = AuthState.DIGEST
            # Return request with digest auth headers
            ...
        elif "Basic" in www_auth:
            self.auth_state = AuthState.BASIC
            ...

        return None  # Or retry request
```

### Layer 2: I/O Shells

Thin wrappers that perform actual HTTP I/O.

#### Sync Shell

```python
# caldav/sync_client.py
import requests
from caldav.protocol import CalDAVProtocol, DAVRequest, DAVResponse

class SyncDAVClient:
    """Synchronous CalDAV client using requests library."""

    def __init__(self, url: str, username: str = None, password: str = None):
        self.protocol = CalDAVProtocol(url, username, password)
        self.session = requests.Session()

    def _execute(self, request: DAVRequest) -> DAVResponse:
        """Execute a protocol request via HTTP."""
        response = self.session.request(
            method=request.method,
            url=self.protocol.base_url.join(request.path),
            headers=request.headers,
            data=request.body,
        )
        return DAVResponse(
            status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    def propfind(self, path: str, props: list[str], depth: int = 0) -> dict:
        """Execute PROPFIND and return parsed properties."""
        request = self.protocol.propfind_request(path, props, depth)
        response = self._execute(request)
        return self.protocol.parse_propfind_response(response)

    def search(self, path: str, start=None, end=None, **kwargs) -> list:
        """Search for calendar objects."""
        request = self.protocol.calendar_query_request(path, start, end, **kwargs)
        response = self._execute(request)
        return self.protocol.parse_calendar_query_response(response)
```

#### Async Shell

```python
# caldav/async_client.py
import aiohttp
from caldav.protocol import CalDAVProtocol, DAVRequest, DAVResponse

class AsyncDAVClient:
    """Asynchronous CalDAV client using aiohttp."""

    def __init__(self, url: str, username: str = None, password: str = None):
        self.protocol = CalDAVProtocol(url, username, password)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _execute(self, request: DAVRequest) -> DAVResponse:
        """Execute a protocol request via HTTP."""
        if self._session is None:
            self._session = aiohttp.ClientSession()

        async with self._session.request(
            method=request.method,
            url=self.protocol.base_url.join(request.path),
            headers=request.headers,
            data=request.body,
        ) as response:
            return DAVResponse(
                status=response.status,
                headers=dict(response.headers),
                body=await response.read(),
            )

    async def propfind(self, path: str, props: list[str], depth: int = 0) -> dict:
        """Execute PROPFIND and return parsed properties."""
        request = self.protocol.propfind_request(path, props, depth)
        response = await self._execute(request)
        return self.protocol.parse_propfind_response(response)
```

### Layer 3: High-Level API

User-facing classes that use either shell.

```python
# caldav/calendar.py
from typing import Union
from caldav.sync_client import SyncDAVClient
from caldav.async_client import AsyncDAVClient

class Calendar:
    """
    High-level Calendar interface.

    Works with either sync or async client.
    """

    def __init__(self, client: Union[SyncDAVClient, AsyncDAVClient], url: str):
        self.client = client
        self.url = url
        self._is_async = isinstance(client, AsyncDAVClient)

    def events(self, start=None, end=None):
        """Get events in date range."""
        if self._is_async:
            raise TypeError("Use 'await calendar.async_events()' for async client")
        return self.client.search(self.url, start=start, end=end, event=True)

    async def async_events(self, start=None, end=None):
        """Get events in date range (async)."""
        if not self._is_async:
            raise TypeError("Use 'calendar.events()' for sync client")
        return await self.client.search(self.url, start=start, end=end, event=True)
```

## Migration Path

### Phase 1: Extract Protocol Layer

1. Create `caldav/protocol/` package
2. Move XML building from `search.py` → `protocol/requests.py`
3. Move response parsing from `response.py` → `protocol/responses.py`
4. Keep existing API, have it use protocol layer internally

### Phase 2: Create I/O Shells

1. Create minimal `SyncDAVClient` using protocol layer
2. Create minimal `AsyncDAVClient` using protocol layer
3. Implement core operations (propfind, report, put, delete)

### Phase 3: Migrate Collection Classes

1. Refactor `Calendar` to use protocol + shell
2. Refactor `Principal` to use protocol + shell
3. Refactor `CalendarObjectResource` to use protocol + shell

### Phase 4: Deprecation

1. Deprecate old `DAVClient` class
2. Provide migration guide
3. Eventually remove old implementation

## File Structure

```
caldav/
├── protocol/                    # Sans-I/O protocol layer
│   ├── __init__.py
│   ├── requests.py             # Request builders
│   ├── responses.py            # Response parsers
│   ├── state.py                # Protocol state machine
│   ├── xml_builders.py         # XML construction helpers
│   └── xml_parsers.py          # XML parsing helpers
│
├── io/                          # I/O shells
│   ├── __init__.py
│   ├── sync.py                 # Sync client (requests)
│   └── async_.py               # Async client (aiohttp)
│
├── objects/                     # High-level objects
│   ├── __init__.py
│   ├── calendar.py
│   ├── principal.py
│   └── event.py
│
├── elements/                    # (existing, no changes)
├── lib/                         # (existing, no changes)
│
└── __init__.py                  # Public API exports
```

## Comparison with Current Playground Approach

| Aspect | Playground Branch | Sans-I/O |
|--------|-------------------|----------|
| Code duplication | None (async-first) | None (shared protocol) |
| Runtime overhead | Event loop per call | None |
| Complexity | Object conversion | Protocol abstraction |
| Testability | Needs mocked HTTP | Protocol testable without HTTP |
| Refactoring effort | Moderate (done) | High (full rewrite) |
| HTTP library coupling | aiohttp/requests | Pluggable |

## Advantages of Sans-I/O

1. **Testability**: Protocol layer can be tested with pure unit tests, no HTTP mocking
2. **No runtime overhead**: No event loop bridging between sync/async
3. **Pluggable I/O**: Could support httpx, urllib3, or any HTTP library
4. **Clear separation**: Protocol bugs vs I/O bugs are easier to isolate
5. **Reusability**: Protocol layer could be used by other projects

## Disadvantages of Sans-I/O

1. **Significant refactoring**: Requires restructuring most of the codebase
2. **Learning curve**: Pattern is less familiar to some developers
3. **Incremental migration is complex**: Need to maintain both old and new code during transition

## API Stability Analysis

**Key finding: Sans-I/O does NOT require public API changes.**

The Sans-I/O pattern is an *internal* architectural change. The user-facing API can
remain identical:

### Current Public API (unchanged)

```python
# Sync API - caldav module
from caldav import DAVClient, get_davclient

client = DAVClient(url="https://...", username="...", password="...")
principal = client.principal()
calendars = principal.calendars()
events = calendar.search(start=..., end=..., event=True)
event.save()

# Async API - caldav.aio module
from caldav.aio import AsyncDAVClient, get_async_davclient

client = await AsyncDAVClient.create(url="https://...")
principal = await client.principal()
calendars = await principal.calendars()
```

### How Sans-I/O Preserves This API

The change is purely internal. For example, `Calendar.search()` today:

```python
# Current implementation (simplified)
class Calendar:
    def search(self, start=None, end=None, **kwargs):
        xml = self._build_search_query(start, end, **kwargs)  # Protocol logic
        response = self.client.report(self.url, xml)           # I/O
        return self._parse_results(response)                   # Protocol logic
```

With Sans-I/O, same public API, different internals:

```python
# Sans-I/O implementation (simplified)
class Calendar:
    def search(self, start=None, end=None, **kwargs):
        # Protocol layer builds request
        request = self._protocol.calendar_query_request(
            self.url, start, end, **kwargs
        )
        # I/O shell executes it
        response = self._io.execute(request)
        # Protocol layer parses response
        return self._protocol.parse_calendar_query_response(response)
```

**Users see no difference** - the method signature, parameters, and return types
are identical.

### What COULD Change (Optional)

Some *optional* new APIs could be exposed for advanced users:

```python
# Optional: Direct protocol access for power users
from caldav.protocol import CalDAVProtocol

protocol = CalDAVProtocol()
request = protocol.calendar_query_request(url, start, end)
# User can inspect/modify request before execution
# User can use their own HTTP client
```

But this would be *additive*, not breaking existing code.

## Hybrid Approach: Gradual Migration

A hybrid approach allows incremental migration without breaking changes:

### Strategy: Protocol Extraction

Instead of a full rewrite, extract protocol logic piece by piece:

```
Phase 1: Create protocol module alongside existing code
         ├── caldav/protocol/          # NEW: Protocol layer
         ├── caldav/davclient.py       # EXISTING: Still works
         └── caldav/collection.py      # EXISTING: Still works

Phase 2: Migrate internals to use protocol layer
         ├── caldav/protocol/
         ├── caldav/davclient.py       # MODIFIED: Uses protocol internally
         └── caldav/collection.py      # MODIFIED: Uses protocol internally

Phase 3: (Optional) Expose protocol layer publicly
         ├── caldav/protocol/          # Now part of public API
         └── ...
```

### Concrete Hybrid Migration Plan

#### Step 1: Extract XML Building (Low Risk)

The `CalDAVSearcher.build_search_xml_query()` and element builders are already
mostly sans-I/O. Formalize this:

```python
# caldav/protocol/xml_builders.py
def build_propfind_body(props: list[str]) -> bytes:
    """Build PROPFIND request body. Pure function, no I/O."""
    ...

def build_calendar_query(start, end, expand, **filters) -> bytes:
    """Build calendar-query REPORT body. Pure function, no I/O."""
    ...
```

Current code can immediately use these, no API changes.

#### Step 2: Extract Response Parsing (Low Risk)

`BaseDAVResponse` already has parsing logic. Extract to pure functions:

```python
# caldav/protocol/xml_parsers.py
def parse_multistatus(body: bytes) -> list[dict]:
    """Parse multistatus response. Pure function, no I/O."""
    ...

def parse_calendar_data(body: bytes) -> list[CalendarObject]:
    """Parse calendar-query response. Pure function, no I/O."""
    ...
```

#### Step 3: Create Request/Response Types (Low Risk)

```python
# caldav/protocol/types.py
@dataclass
class DAVRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes | None

@dataclass
class DAVResponse:
    status: int
    headers: dict[str, str]
    body: bytes
```

#### Step 4: Refactor DAVClient Internals (Medium Risk)

```python
# caldav/davclient.py
class DAVClient:
    def propfind(self, url, props, depth=0):
        # OLD: Mixed protocol and I/O
        # NEW: Separate concerns
        body = build_propfind_body(props)  # Protocol
        response = self._http_request("PROPFIND", url, body, depth)  # I/O
        return parse_propfind_response(response.content)  # Protocol
```

#### Step 5: Create I/O Abstraction (Medium Risk)

```python
# caldav/io/base.py
class BaseIO(Protocol):
    def execute(self, request: DAVRequest) -> DAVResponse: ...

# caldav/io/sync.py
class SyncIO(BaseIO):
    def __init__(self, session: requests.Session): ...

# caldav/io/async_.py
class AsyncIO(BaseIO):
    async def execute(self, request: DAVRequest) -> DAVResponse: ...
```

### Timeline Estimate

| Phase | Effort | Risk | Can Be Done Incrementally |
|-------|--------|------|---------------------------|
| XML builders extraction | 1-2 days | Low | Yes |
| Response parsers extraction | 1-2 days | Low | Yes |
| Request/Response types | 1 day | Low | Yes |
| DAVClient refactor | 3-5 days | Medium | Yes, method by method |
| I/O abstraction | 2-3 days | Medium | Yes |
| Collection classes refactor | 5-7 days | Medium | Yes, class by class |
| Full async parity | 3-5 days | Low | Yes |

**Total: ~3-4 weeks of focused work**, but can be spread over time.

### Compatibility During Migration

During migration, both paths work:

```python
# Old path (still works)
client = DAVClient(url, username, password)
calendar.search(...)  # Uses refactored internals transparently

# New path (optional, for power users)
from caldav.protocol import CalDAVProtocol
from caldav.io import SyncIO

protocol = CalDAVProtocol()
io = SyncIO(session)
request = protocol.calendar_query_request(...)
response = io.execute(request)
results = protocol.parse_response(response)
```

## Long-Term Vision

### Phase 1: Current (Playground Branch)
- Async-first with sync wrapper
- Single source of truth
- Acceptable runtime overhead

### Phase 2: Protocol Extraction (6-12 months)
- Gradually extract protocol logic
- No public API changes
- Better testability
- Reduced coupling

### Phase 3: Full Sans-I/O (12-24 months)
- Complete separation of protocol and I/O
- Optional protocol-level API for power users
- Support for alternative HTTP libraries
- Community contributions to protocol layer

### Decision Points

**Move to Phase 2 when:**
- Test suite needs improvement (protocol tests are easier)
- Want to support httpx or other HTTP libraries
- Performance profiling shows overhead issues

**Move to Phase 3 when:**
- Demand for protocol-level access (custom HTTP handling)
- Major version bump planned (3.0)
- Community interest in contributing to protocol layer

## Recommendation

**Short-term:** The playground branch approach is a reasonable pragmatic choice that
delivers async support without major refactoring.

**Medium-term:** Begin gradual protocol extraction (Steps 1-3 above) as opportunities
arise. These low-risk changes improve testability and don't require API changes.

**Long-term:** Full Sans-I/O architecture remains a viable goal for a future major
version, achievable incrementally without breaking existing users.

The key insight is that **Sans-I/O and the current API are compatible** - Sans-I/O
is an internal architectural improvement, not a user-facing change.

## References

- [Building Protocol Libraries The Right Way](https://www.youtube.com/watch?v=7cC3_jGwl_U) - Cory Benfield, PyCon 2016
- [h11 - Sans-I/O HTTP/1.1](https://github.com/python-hyper/h11)
- [SYNC_ASYNC_PATTERNS.md](SYNC_ASYNC_PATTERNS.md) - Pattern comparison
- [PLAYGROUND_BRANCH_ANALYSIS.md](PLAYGROUND_BRANCH_ANALYSIS.md) - Current implementation analysis
- [SANS_IO_IMPLEMENTATION_PLAN.md](SANS_IO_IMPLEMENTATION_PLAN.md) - **Detailed implementation plan**
