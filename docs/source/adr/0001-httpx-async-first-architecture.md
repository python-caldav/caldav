# ADR 0001: HTTPX Async-First Architecture with Thin Sync Wrappers

## Status

**Proposed** - For caldav v3.0
**Supersedes** - #555

## Context

The caldav library currently uses `requests` (with optional `niquests` support) for HTTP communication. This synchronous-only approach limits the library's usefulness in modern async Python applications. A previous attempt to add async support via parallel implementations created significant code duplication and maintenance burden.

### Current Architecture

The library's HTTP layer is centralized in `DAVClient` (`davclient.py`), which provides:
- Core HTTP methods: `request()`, `propfind()`, `proppatch()`, `report()`, `mkcalendar()`, `put()`, `post()`, `delete()`, `options()`
- Session management via `requests.Session()`
- Authentication handling (Basic, Digest, Bearer)
- Response parsing via `DAVResponse`

All other classes (`DAVObject`, `Calendar`, `Principal`, `CalendarSet`, `CalendarObjectResource`, `Event`, `Todo`, `Journal`) delegate HTTP operations through `self.client` to `DAVClient`.

### Key Files and Structure

```
caldav/
├── davclient.py          # DAVClient, DAVResponse, HTTP layer (~1100 lines)
├── davobject.py          # DAVObject base class (~430 lines)
├── collection.py         # Principal, Calendar, CalendarSet (~1300 lines)
├── calendarobjectresource.py  # Event, Todo, Journal, FreeBusy (~1660 lines)
├── search.py             # CalDAVSearcher (~510 lines)
├── requests.py           # HTTPBearerAuth (~20 lines)
└── lib/
    ├── url.py            # URL handling
    ├── vcal.py           # iCalendar utilities
    └── error.py          # Exception classes
```

### Why HTTPX + AnyIO

HTTPX is a modern HTTP client built on top of **anyio**, providing:
- Both sync and async APIs from a single codebase
- Drop-in compatibility with requests API patterns
- HTTP/2 support
- Superior timeout handling
- Active maintenance and modern Python support (3.8+)
- Built-in authentication classes similar to requests

**AnyIO** is the async compatibility layer that httpx uses internally:
- Provides backend-agnostic async primitives (works with asyncio and trio)
- Offers `anyio.from_thread.run()` for cleanly running async code from sync contexts
- Handles event loop management automatically
- No need for `nest_asyncio` hacks - anyio's thread-based approach is cleaner
- Already a transitive dependency via httpx

## Decision

We will adopt an **async-first architecture using HTTPX**, where:

1. **Primary Implementation**: All core HTTP and DAV logic is written as async code
2. **Sync API**: Provided via thin wrappers that execute async code synchronously
3. **Single Source of Truth**: Only async code is maintained; sync wrappers are minimal

This differs from the previous ADR proposal which suggested code generation (unasync). Instead, we use runtime wrapping, which is simpler to implement and maintain.

## Implementation Strategy

### Phase 1: HTTP Layer (AsyncDAVClient)

Replace `requests`/`niquests` with `httpx.AsyncClient`:

```python
# caldav/_async/davclient.py
import httpx
from typing import Optional, Mapping

class AsyncDAVClient:
    """Async CalDAV client using httpx."""

    def __init__(
        self,
        url: str = "",
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth: Optional[httpx.Auth] = None,
        timeout: Optional[float] = None,
        ssl_verify_cert: bool = True,
        # ... other params
    ) -> None:
        self._client = httpx.AsyncClient(
            auth=auth or self._build_auth(username, password),
            timeout=timeout,
            verify=ssl_verify_cert,
            # ...
        )
        self.url = URL.objectify(url)
        # ...

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        url: str,
        method: str = "GET",
        body: str = "",
        headers: Mapping[str, str] = None,
    ) -> "DAVResponse":
        """Core HTTP request method."""
        combined_headers = {**self.headers, **(headers or {})}

        response = await self._client.request(
            method=method,
            url=str(url),
            content=to_wire(body) if body else None,
            headers=combined_headers,
        )

        return DAVResponse(response, self)

    async def propfind(self, url: str = None, props: str = "", depth: int = 0) -> "DAVResponse":
        return await self.request(url or str(self.url), "PROPFIND", props, {"Depth": str(depth)})

    async def report(self, url: str, query: str = "", depth: int = 0) -> "DAVResponse":
        return await self.request(url, "REPORT", query, {"Depth": str(depth), "Content-Type": 'application/xml; charset="utf-8"'})

    # ... other methods: proppatch, mkcalendar, put, post, delete, options
```

### Phase 2: DAV Object Layer

Convert `DAVObject` and subclasses to async:

```python
# caldav/_async/davobject.py

class AsyncDAVObject:
    """Async base class for DAV objects."""

    client: Optional["AsyncDAVClient"] = None

    async def _query_properties(self, props=None, depth: int = 0):
        """Internal propfind query."""
        root = None
        if props:
            prop = dav.Prop() + props
            root = dav.Propfind() + prop
        return await self._query(root, depth)

    async def _query(self, root=None, depth=0, query_method="propfind", url=None, expected_return_value=None):
        body = etree.tostring(root.xmlelement(), ...) if root else ""
        url = url or self.url
        ret = await getattr(self.client, query_method)(url, body, depth)
        # ... error handling
        return ret

    async def get_properties(self, props=None, depth: int = 0, ...):
        response = await self._query_properties(props, depth)
        # ... process response
        return properties

    async def set_properties(self, props=None):
        # ... build XML
        r = await self._query(root, query_method="proppatch")
        return self

    async def delete(self) -> None:
        if self.url:
            r = await self.client.delete(str(self.url))
            if r.status not in (200, 204, 404):
                raise error.DeleteError(errmsg(r))
```

### Phase 3: Thin Sync Wrappers

Create sync wrappers that delegate to async implementation using **anyio**:

```python
# caldav/_sync/davclient.py
import anyio
from caldav._async.davclient import AsyncDAVClient as _AsyncDAVClient
from caldav._async.davclient import DAVResponse

def _run_sync(async_fn, *args, **kwargs):
    """Execute an async function synchronously using anyio.

    Uses anyio.from_thread.run() which properly handles:
    - Running from a sync context (creates new event loop)
    - Running from within an async context (uses existing loop via thread)
    - Works with both asyncio and trio backends
    """
    return anyio.from_thread.run(async_fn, *args, **kwargs)


class DAVClient:
    """Synchronous CalDAV client - thin wrapper around AsyncDAVClient."""

    def __init__(self, *args, **kwargs):
        self._async_client = _AsyncDAVClient(*args, **kwargs)
        # Copy attributes for compatibility
        self.url = self._async_client.url
        self.headers = self._async_client.headers
        # ...

    def __enter__(self):
        _run_sync(self._async_client.__aenter__)
        return self

    def __exit__(self, *args):
        _run_sync(self._async_client.__aexit__, *args)

    def close(self) -> None:
        _run_sync(self._async_client.close)

    def request(self, url: str, method: str = "GET", body: str = "", headers=None) -> DAVResponse:
        return _run_sync(self._async_client.request, url, method, body, headers)

    def propfind(self, url: str = None, props: str = "", depth: int = 0) -> DAVResponse:
        return _run_sync(self._async_client.propfind, url, props, depth)

    def report(self, url: str, query: str = "", depth: int = 0) -> DAVResponse:
        return _run_sync(self._async_client.report, url, query, depth)

    # ... delegate all other methods

    def principal(self, *args, **kwargs):
        from caldav._sync.collection import Principal
        return Principal(client=self, *args, **kwargs)
```

### Phase 4: Collection Classes

Apply the same pattern to Calendar, Principal, CalendarSet:

```python
# caldav/_async/collection.py

class AsyncCalendar(AsyncDAVObject):
    """Async Calendar implementation."""

    async def save(self, method=None):
        if self.url is None:
            await self._create(id=self.id, name=self.name, method=method, **self.extra_init_options)
        return self

    async def search(self, **kwargs):
        # ... search implementation
        pass

    async def events(self):
        return await self.search(comp_class=Event)

    async def save_event(self, *args, **kwargs):
        return await self.save_object(Event, *args, **kwargs)


# caldav/_sync/collection.py

class Calendar(DAVObject):
    """Sync Calendar - thin wrapper around AsyncCalendar."""

    def __init__(self, client=None, *args, **kwargs):
        from caldav._async.collection import AsyncCalendar
        self._async = AsyncCalendar(client._async_client if client else None, *args, **kwargs)
        super().__init__(client=client, *args, **kwargs)

    def save(self, method=None):
        return _run_sync(self._async.save, method)

    def search(self, **kwargs):
        return _run_sync(self._async.search, **kwargs)

    def events(self):
        return _run_sync(self._async.events)
```

### Phase 5: Public API Structure

```python
# caldav/__init__.py - Default sync API (backward compatible)
from .davclient import DAVClient
from .collection import Calendar, Principal, CalendarSet
from .calendarobjectresource import Event, Todo, Journal, FreeBusy

# caldav/aio.py - Async API
from ._async.davclient import AsyncDAVClient as DAVClient
from ._async.collection import AsyncCalendar as Calendar
from ._async.collection import AsyncPrincipal as Principal
# ... etc
```

### Directory Structure

```
caldav/
├── __init__.py           # Re-exports sync API (backward compatible)
├── aio.py                # Re-exports async API
├── _async/
│   ├── __init__.py
│   ├── davclient.py      # AsyncDAVClient, DAVResponse (PRIMARY)
│   ├── davobject.py      # AsyncDAVObject (PRIMARY)
│   ├── collection.py     # AsyncCalendar, AsyncPrincipal, etc. (PRIMARY)
│   └── calendarobjectresource.py  # AsyncEvent, etc. (PRIMARY)
├── _sync/
│   ├── __init__.py
│   ├── davclient.py      # DAVClient (wrapper)
│   ├── davobject.py      # DAVObject (wrapper)
│   ├── collection.py     # Calendar, Principal, etc. (wrapper)
│   └── calendarobjectresource.py  # Event, Todo, Journal (wrapper)
├── davclient.py          # -> _sync/davclient.py (compatibility re-export)
├── davobject.py          # -> _sync/davobject.py (compatibility re-export)
├── collection.py         # -> _sync/collection.py (compatibility re-export)
├── calendarobjectresource.py  # -> _sync/calendarobjectresource.py
├── elements/             # Unchanged - XML elements
├── lib/                  # Unchanged - utilities
└── requests.py           # Replaced with httpx auth classes
```

## Consequences

### Positive

1. **Single Source of Truth**: All business logic lives in async code; sync is purely delegation
2. **Modern HTTP Client**: HTTPX provides HTTP/2, better timeouts, and async support
3. **Reduced Maintenance**: ~50% less code to maintain vs. parallel implementations
4. **Simple Implementation**: Runtime wrapping is simpler than code generation
5. **Backward Compatible**: Sync API remains unchanged for existing users
6. **Clean Async API**: `caldav.aio` provides first-class async support

### Negative

1. **Runtime Overhead**: Each sync call incurs thread-based async bridging overhead
2. **Dependency Change**: Adds httpx (with anyio), potentially removes requests
3. **Migration Effort**: Significant refactoring required (~4000 lines)

### Performance Considerations

The `anyio.from_thread.run()` overhead is typically negligible for network-bound operations like CalDAV. HTTP latency (typically 50-500ms) far exceeds the thread coordination overhead. Unlike `asyncio.run()`, anyio's approach:
- Reuses event loops when possible
- Works correctly in nested async contexts (Jupyter, etc.) without hacks
- Handles connection pooling efficiently via httpx

For performance-critical applications, users should migrate to the async API where they can:
- Perform concurrent calendar operations
- Share a single event loop
- Avoid `asyncio.run()` overhead

## Alternatives Considered

### Alternative 1: Code Generation (unasync)

The previous ADR proposed using `unasync` to generate sync code from async sources.

**Rejected because:**
- Adds build complexity
- Generated code can have subtle bugs
- Harder to debug (users see generated code)
- Thin wrappers are simpler and more maintainable

### Alternative 2: Keep requests, Add Async Separately

Maintain requests for sync, add httpx for async.

**Rejected because:**
- Two HTTP libraries to maintain
- Different behavior between sync/async
- Doesn't solve the code duplication problem

### Alternative 3: Sync Inherits from Async

Make sync classes inherit from async and override methods.

**Rejected because:**
- Inheritance creates tight coupling
- Still requires method-by-method implementation
- Confusing class hierarchy

## Migration Guide

### For Sync Users (No Changes Required)

```python
# Before (v2.x)
from caldav import DAVClient
client = DAVClient(url="...", username="...", password="...")
calendars = client.principal().calendars()

# After (v3.x) - identical
from caldav import DAVClient
client = DAVClient(url="...", username="...", password="...")
calendars = client.principal().calendars()
```

### New Async API (v3.x)

```python
from caldav.aio import DAVClient

async def main():
    async with DAVClient(url="...", username="...", password="...") as client:
        principal = await client.principal()
        calendars = await principal.calendars()

        for cal in calendars:
            events = await cal.events()
```

## Implementation Checklist

### Phase 1: Foundation (2-3 weeks)
- [ ] Add httpx and anyio dependencies to pyproject.toml
- [ ] Create `caldav/_async/` directory structure
- [ ] Implement `AsyncDAVClient` with core HTTP methods
- [ ] Implement `DAVResponse` (shared between sync/async)
- [ ] Create `_run_sync()` utility using `anyio.from_thread.run()`

### Phase 2: HTTP Layer Complete (2-3 weeks)
- [ ] Create `caldav/_sync/davclient.py` wrapper
- [ ] Implement all DAVClient methods in async
- [ ] Port authentication handling to httpx
- [ ] Add connection pooling configuration
- [ ] Unit tests for HTTP layer

### Phase 3: Object Model (4-6 weeks)
- [ ] Port `AsyncDAVObject` and `DAVObject` wrapper
- [ ] Port `AsyncPrincipal`, `AsyncCalendarSet`
- [ ] Port `AsyncCalendar` with all methods
- [ ] Port `AsyncCalendarObjectResource` and subclasses
- [ ] Port `CalDAVSearcher` to async

### Phase 4: Integration & Testing (3-4 weeks)
- [ ] Create `caldav/aio.py` with async exports
- [ ] Update `caldav/__init__.py` for backward compatibility
- [ ] Port all existing tests to work with new structure
- [ ] Add async-specific tests
- [ ] Integration tests with real CalDAV servers

### Phase 5: Documentation & Release (2-3 weeks)
- [ ] Update all documentation
- [ ] Write migration guide
- [ ] Update examples
- [ ] Beta release for community testing
- [ ] Final v3.0 release

## Dependencies

```toml
# pyproject.toml changes
[project]
dependencies = [
    "httpx>=0.25.0",  # Includes anyio as transitive dependency
    "anyio>=4.0.0",   # Explicit dependency for sync wrappers
    "lxml",
    "icalendar",
    # ... other existing deps
]

[project.optional-dependencies]
# requests no longer needed for core functionality
legacy = ["requests"]  # For users who need requests compatibility
trio = ["trio"]  # For users who prefer trio backend over asyncio
```

Note: `anyio` is already a transitive dependency of `httpx`, but we declare it explicitly since we use it directly in the sync wrappers.

## References

- [HTTPX Documentation](https://www.python-httpx.org/)
- [HTTPX Async Support](https://www.python-httpx.org/async/)
- [AnyIO Documentation](https://anyio.readthedocs.io/)
- [AnyIO - Running sync code from async](https://anyio.readthedocs.io/en/stable/threads.html)
- [RFC 4791 - CalDAV](https://tools.ietf.org/html/rfc4791)

## Decision Makers

- Proposed by: @cbcoutinho
- Requires review by: @tobixen (project maintainer)

## Changelog

- 2025-11-22: Updated to use anyio instead of asyncio/nest_asyncio for sync wrappers
- 2025-11-22: Initial draft proposing httpx + thin sync wrappers approach
