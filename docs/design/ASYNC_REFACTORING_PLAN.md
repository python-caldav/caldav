# Async CalDAV Refactoring Plan - Final Decisions

## Overview

This document consolidates all decisions made during the API analysis phase. This is the blueprint for implementing the async-first CalDAV library.

## Key Decisions

### 1. Architecture: Async-First with Sync Wrapper ✅

**Decision**: Make the core async, create thin sync wrapper for backward compatibility.

```
async_davclient.py  (NEW)  - Core async implementation
davclient.py        (REWRITE) - Thin wrapper using asyncio.run()
```

**Rationale**:
- Future-proof (async is the future)
- No code duplication (sync wraps async)
- Can fix API inconsistencies in async version
- 100% backward compatibility via wrapper

**Backward Compatibility & Deprecation Strategy**:

Version 3.0 will maintain 100% backward compatibility while introducing the async API. The sync wrapper will support both old and new method names. Over subsequent releases, we'll gradually deprecate old patterns:

- **Easily duplicated functionality** (e.g., `get_principal()` vs `principal()`): Support both indefinitely
- **Commonly used methods** (e.g., `principal()`, old parameter names):
  - v3.0: Supported, deprecation noted in docstrings
  - v4.0: Deprecation warnings added
  - v5.0+: Consider removal
- **Less common patterns** (e.g., `dummy` parameters):
  - v3.0: Deprecation warnings added
  - v4.0+: Consider removal

This gives users ample time to migrate without breaking existing code.

**Code Style**: Switch from Black to Ruff formatter/linter. The configuration from the icalendar-searcher project can serve as a reference.

### 2. Primary Entry Point: get_davclient() ✅

**Decision**: Use factory function as primary entry point, not direct class instantiation.

```python
# Recommended (sync):
from caldav.davclient import get_davclient
with get_davclient(url="...", username="...", password="...") as client:
    ...

# Recommended (async):
from caldav import aio
async with await aio.get_davclient(url="...", username="...", password="...") as client:
    ...
```

**Rationale**:
- Already documented as best practice
- Supports env vars (CALDAV_*), config files
- 12-factor app compliant
- Future-proof (can add connection pooling, retries, etc.)

**Note**: Direct `DAVClient()` instantiation remains available for testing/advanced use.

### 3. Connection Probe ✅

**Decision**: Add optional `probe` parameter to verify connectivity.

```python
def get_davclient(..., probe: bool = False) -> DAVClient:  # Sync: False (backward compat)
async def get_davclient(..., probe: bool = True) -> AsyncDAVClient:  # Async: True (fail fast)
```

**Behavior**:
- Performs a simple OPTIONS request to verify the server is reachable and supports DAV methods
- Can be disabled via `probe=False` when needed (e.g., testing, offline scenarios)
- Default differs between sync and async:
  - Sync: `probe=False` (backward compatibility - no behavior change)
  - Async: `probe=True` (fail-fast principle - catch issues immediately)

**Rationale**:
- Early error detection - configuration issues discovered at connection time, not first use
- Better user experience - clear error messages about connectivity problems
- Name choice: `connect()` was rejected because `__init__()` doesn't actually establish a connection

### 4. Eliminate _query() ✅

**Decision**: Remove `DAVObject._query()` entirely. Callers use wrapper methods directly.

```python
# Current (complex):
ret = self._query(root, query_method="proppatch")

# New (simple):
ret = await self.client.proppatch(self.url, body)
```

**Rationale**:
- Unnecessary indirection
- Dynamic dispatch (`getattr()`) not needed
- Simpler, more explicit code

### 5. Keep HTTP Method Wrappers (Manual Implementation) ✅

**Decision**: Keep wrapper methods (`propfind`, `report`, etc.) with manual implementation + helper.

```python
class AsyncDAVClient:
    @staticmethod
    def _method_headers(method: str, depth: int = 0) -> Dict[str, str]:
        """Build headers for WebDAV methods"""
        # ... header logic ...

    async def propfind(self, url=None, body="", depth=0, headers=None):
        """PROPFIND request"""
        final_headers = {**self._method_headers("PROPFIND", depth), **(headers or {})}
        return await self.request(url or str(self.url), "PROPFIND", body, final_headers)

    # ... ~8 methods total
```

**Rationale**:
- Mocking capability (`client.propfind = mock.Mock()`)
- API discoverability (IDE auto-complete)
- Clear, explicit code
- ~320 lines (acceptable for 8 methods)

**Rejected**: Dynamic method generation - too complex for async + type hints, saves only ~200 lines.

### 6. URL Parameter: Split Requirements ✅

**Decision**: Different URL requirements based on method semantics.

**Query Methods** (URL optional, defaults to `self.url`):
```python
async def propfind(url: Optional[str] = None, ...) -> DAVResponse:
async def report(url: Optional[str] = None, ...) -> DAVResponse:
async def options(url: Optional[str] = None, ...) -> DAVResponse:
```

**Resource Methods** (URL required for safety):
```python
async def put(url: str, ...) -> DAVResponse:
async def delete(url: str, ...) -> DAVResponse:  # Safety critical!
async def post(url: str, ...) -> DAVResponse:
async def proppatch(url: str, ...) -> DAVResponse:
async def mkcol(url: str, ...) -> DAVResponse:
async def mkcalendar(url: str, ...) -> DAVResponse:
```

**Rationale**:
- `self.url` represents the base CalDAV server URL (e.g., `https://caldav.example.com/`)
- Query methods sometimes operate on the base URL (checking server capabilities, discovering principals)
- Resource methods always target specific resource paths (events, calendars, etc.)
- Safety consideration: `delete(url=None)` could be misinterpreted as attempting to delete the entire server. While servers would likely reject such a request, requiring an explicit URL prevents ambiguity and potential accidents

### 7. Parameter Standardization ✅

1. **Remove `dummy` parameters** - backward compat cruft
   ```python
   # Old: proppatch(url, body, dummy=None)
   # New: proppatch(url, body="")
   ```

2. **Standardize on `body` parameter** - not `props` or `query`
   ```python
   # Old: propfind(url, props="", depth)
   # New: propfind(url, body="", depth)
   ```

3. **Add `headers` to all methods**
   ```python
   async def propfind(url=None, body="", depth=0, headers=None):
   ```

4. **Make `body` optional everywhere** (default `""`)

**Rationale**:
- Consistency for readability
- Enables future extensibility
- `body` is generic and works for all methods

### 8. Method Naming (Async API Only) ⚠️

**Decision**: Improve naming in async API, maintain old names in sync wrapper.

**High-Level Methods**:
```python
# Old (sync):        # New (async):
principal()     →    get_principal()         # The important one (works everywhere)
principals(name) →   search_principals(name, email, ...)  # Search operation (limited servers)
calendar()      →    get_calendar()          # Factory method
```

**Capability Methods**:
```python
# Old (sync):              # New (async):
check_dav_support()    →   supports_dav()
check_cdav_support()   →   supports_caldav()
check_scheduling_support() → supports_scheduling()
```

**Rationale**:
- Clearer intent (get vs search)
- More Pythonic
- Backward compat maintained in sync wrapper

### 9. HTTP Library ✅

**Decision**: Use niquests for both sync and async.

```python
# Sync:
from niquests import Session

# Async:
from niquests import AsyncSession
```

**Rationale**:
- Already a dependency
- Native async support (not thread-based)
- HTTP/2 multiplexing support
- No need for httpx

## File Structure

### New Files to Create:
```
caldav/
├── async_davclient.py        (NEW) - AsyncDAVClient class
├── async_davobject.py         (NEW) - AsyncDAVObject base class
├── async_collection.py        (NEW) - Async collection classes
└── aio.py                     (EXISTS - can delete or repurpose)

caldav/davclient.py            (REWRITE) - Sync wrapper
caldav/davobject.py            (MINOR CHANGES) - May need async compatibility
```

### Modified Files:
```
caldav/__init__.py             - Export get_davclient
caldav/davclient.py            - Rewrite as sync wrapper
```

## Implementation Phases

### Phase 1: Core Async Client ✅ READY
1. Create `async_davclient.py` with `AsyncDAVClient`
2. Implement all HTTP method wrappers (propfind, report, etc.)
3. Add `get_davclient()` factory with probe support
4. Write unit tests

### Phase 2: Async DAVObject ✅ READY
1. Create `async_davobject.py` with `AsyncDAVObject`
2. Eliminate `_query()` - use wrapper methods directly
3. Make key methods async (get_properties, set_properties, delete)
4. Write tests

### Phase 3: Async Collections
1. Create `async_collection.py`
2. Async versions of Principal, CalendarSet, Calendar
3. Core functionality (calendars, events, etc.)
4. Tests

### Phase 4: Sync Wrapper
1. Rewrite `davclient.py` as thin wrapper
2. Use `asyncio.run()` to wrap async methods
3. Maintain 100% backward compatibility
4. Verify all existing tests pass

### Phase 5: Polish
1. Update documentation
2. Add examples for async API
3. Migration guide
4. Export `get_davclient` from `__init__.py`

## Testing Strategy

### New Async Tests:
```
tests/test_async_davclient.py  - Unit tests for AsyncDAVClient
tests/test_async_collection.py - Tests for async collections
tests/test_async_integration.py - Integration tests against real servers
```

### Existing Tests:
All tests in `tests/test_caldav.py` etc. must continue to pass with sync wrapper.

## Success Criteria

1. ✅ All existing tests pass (backward compatibility)
2. ✅ New async tests pass
3. ✅ Integration tests work against Radicale, Baikal, etc.
4. ✅ Examples updated to use `get_davclient()`
5. ✅ Documentation updated
6. ✅ Type hints complete
7. ✅ No mypy errors

## API Examples

### Sync (Backward Compatible):
```python
from caldav.davclient import get_davclient

with get_davclient(url="...", username="...", password="...") as client:
    principal = client.principal()
    calendars = principal.calendars()
    for cal in calendars:
        events = cal.events()
```

### Async (New):
```python
from caldav import aio

async with await aio.get_davclient(url="...", username="...", password="...") as client:
    principal = await client.get_principal()
    calendars = await principal.calendars()
    for cal in calendars:
        events = await cal.events()
```

## Timeline

This is research/planning phase. Implementation timeline TBD based on:
- Maintainer availability
- Community feedback
- Testing requirements

## Notes

- This plan is based on analysis in:
  - [`API_ANALYSIS.md`](API_ANALYSIS.md)
  - [`URL_AND_METHOD_RESEARCH.md`](URL_AND_METHOD_RESEARCH.md)
  - [`ELIMINATE_METHOD_WRAPPERS_ANALYSIS.md`](ELIMINATE_METHOD_WRAPPERS_ANALYSIS.md)
  - [`METHOD_GENERATION_ANALYSIS.md`](METHOD_GENERATION_ANALYSIS.md)
  - [`GET_DAVCLIENT_ANALYSIS.md`](GET_DAVCLIENT_ANALYSIS.md)

- All decisions are documented with rationale
- Trade-offs have been considered
- Focus on: clarity > cleverness, explicit > implicit

## Questions for Future Consideration

1. Should we add connection pooling?
2. Should we add retry logic with exponential backoff?
3. Should we support alternative async backends (trio, curio)?
4. How aggressive should the async API improvements be?

These can be addressed after initial async implementation is stable.
