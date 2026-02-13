# Sans-I/O Refactoring Plan: Eliminating Sync/Async Duplication

## Status: 📋 PLANNING

## Problem Statement

Currently, the codebase has significant duplication between sync and async implementations:

| File Pair | Lines (Sync) | Lines (Async) | Estimated Duplication |
|-----------|--------------|---------------|----------------------|
| `davobject.py` / `async_davobject.py` | 405 | 945 | ~300 lines |
| `collection.py` / `async_collection.py` | 1,473 | 1,128 | ~700 lines |
| `calendarobjectresource.py` / (in async_davobject) | 1,633 | ~500 | ~400 lines |
| **Total** | ~3,500 | ~2,500 | **~1,400 lines (40%)** |

The previous refactoring made the protocol layer Sans-I/O for XML building/parsing, but the **business logic** in Calendar, Principal, DAVObject, and CalendarObjectResource is still duplicated.

## Goal

Extend the Sans-I/O pattern to high-level classes, resulting in:
1. **Single implementation** of all business logic
2. **Thin sync/async wrappers** for I/O only
3. **~40% code reduction** (~1,400 lines)
4. **Improved testability** - business logic tested without mocking HTTP

## User Requirements

1. **Sync API**: Full backward compatibility required
2. **Async API**: Can be changed freely (not yet released)
3. **No duplicated business logic**: Single source of truth
4. **Clean separation**: I/O vs business logic clearly separated

## Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Public API                             │
│  Sync:  client.principal().get_calendars()[0].get_events()          │
│  Async: await client.get_principal() → get_calendars → ...  │
├─────────────────────────────────────────────────────────────┤
│              Domain Objects (data containers)                │
│  Calendar, Principal, Event, Todo, Journal                  │
│  - Hold data (url, name, properties, ical_data)             │
│  - Sync: convenience methods delegate to client             │
│  - Async: no methods, use client directly                   │
│  - SAME classes for both sync and async                     │
├─────────────────────────────────────────────────────────────┤
│         DAVClient (sync)    │    AsyncDAVClient (async)     │
│  ┌─────────────────────────┐│┌─────────────────────────────┐│
│  │ get_events(calendar)    │││ await get_events(calendar)  ││
│  │ 1. ops.build_query()    │││ 1. ops.build_query()        ││
│  │ 2. self.report(...)     │││ 2. await self.report(...)   ││
│  │ 3. ops.process_result() │││ 3. ops.process_result()     ││
│  │ 4. return [Event(...)]  │││ 4. return [Event(...)]      ││
│  └─────────────────────────┘│└─────────────────────────────┘│
│         ↓ SAME ops ↓        │         ↓ SAME ops ↓          │
├─────────────────────────────────────────────────────────────┤
│              Operations Layer (NEW - Sans-I/O)              │
│  caldav/operations/                                         │
│  - Pure functions, NO I/O                                   │
│  - build_*_query() → QuerySpec (what to request)            │
│  - process_*_response() → List[DataClass] (parsed results)  │
│  - Server compatibility workarounds                         │
│  - Used by BOTH sync and async clients                      │
├─────────────────────────────────────────────────────────────┤
│              Protocol Layer (existing)                       │
│  caldav/protocol/                                           │
│  - xml_builders.py: Build XML request bodies                │
│  - xml_parsers.py: Parse XML responses                      │
│  - types.py: Result dataclasses                             │
└─────────────────────────────────────────────────────────────┘
```

**Key insight:** No async/sync bridging needed! Both clients:
1. Call the same operations layer (pure functions)
2. Do their own I/O (sync HTTP or async HTTP)
3. Return the same domain objects

## Design Principles

### 1. Operations as Pure Functions (Sans-I/O)

```python
# caldav/operations/calendar_ops.py

@dataclass(frozen=True)
class CalendarsQuery:
    """Query specification for listing calendars."""
    url: str
    props: List[str]
    depth: int = 1

@dataclass
class CalendarData:
    """Calendar metadata extracted from server response."""
    url: str
    name: Optional[str]
    color: Optional[str]
    supported_components: List[str]
    ctag: Optional[str]

def build_calendars_query(calendar_home_url: str) -> CalendarsQuery:
    """Build query params for listing calendars (Sans-I/O, no network)."""
    return CalendarsQuery(
        url=calendar_home_url,
        props=['displayname', 'resourcetype', 'supported-calendar-component-set'],
        depth=1,
    )

def process_calendars_response(
    results: List[PropfindResult],
    base_url: str,
) -> List[CalendarData]:
    """Process PROPFIND results into calendar list (Sans-I/O, no network)."""
    calendars = []
    for result in results:
        if _is_calendar_resource(result):
            calendars.append(CalendarData(
                url=result.href,
                name=result.properties.get('{DAV:}displayname'),
                # ... extract other properties
            ))
    return calendars
```

### 2. Both Clients Use Same Operations (No Bridging!)

```python
# caldav/davclient.py - SYNC client

class DAVClient:
    def get_calendars(self, calendar_home_url: str) -> List[Calendar]:
        """List calendars - sync implementation."""
        from caldav.operations import calendar_ops as ops

        # 1. Build query (Sans-I/O - same as async)
        query = ops.build_calendars_query(calendar_home_url)

        # 2. Execute I/O (SYNC)
        response = self.propfind(query.url, props=query.props, depth=query.depth)

        # 3. Process response (Sans-I/O - same as async)
        calendar_data = ops.process_calendars_response(response.results, str(self.url))

        # 4. Return domain objects
        return [Calendar(client=self, **cd.__dict__) for cd in calendar_data]
```

```python
# caldav/async_davclient.py - ASYNC client

class AsyncDAVClient:
    async def get_calendars(self, calendar_home_url: str) -> List[Calendar]:
        """List calendars - async implementation."""
        from caldav.operations import calendar_ops as ops

        # 1. Build query (Sans-I/O - SAME as sync)
        query = ops.build_calendars_query(calendar_home_url)

        # 2. Execute I/O (ASYNC)
        response = await self.propfind(query.url, props=query.props, depth=query.depth)

        # 3. Process response (Sans-I/O - SAME as sync)
        calendar_data = ops.process_calendars_response(response.results, str(self.url))

        # 4. Return domain objects (SAME Calendar class!)
        return [Calendar(client=self, **cd.__dict__) for cd in calendar_data]
```

**Note:** Steps 1 and 3 are identical between sync and async - that's the Sans-I/O pattern!
Only step 2 (the actual I/O) differs.

### 3. Domain Objects for Backward Compat (Sync Only)

```python
# caldav/collection.py

class Calendar:
    """Calendar - data container with sync convenience methods."""

    def __init__(self, client, url, name=None, **kwargs):
        self.client = client
        self.url = url
        self.name = name
        # ... store other data

    def events(self) -> List[Event]:
        """Sync convenience method - delegates to client."""
        return self.client.get_events(self)

    def search(self, **kwargs) -> List[CalendarObjectResource]:
        """Sync convenience method - delegates to client."""
        return self.client.search_calendar(self, **kwargs)
```

### 4. Async API is Client-Centric (Cleaner)

```python
# Async users call client methods directly - no Calendar.get_events()

async with AsyncDAVClient(url=...) as client:
    principal = await client.get_principal()
    calendars = await client.get_calendars(principal.calendar_home_set)
    events = await client.get_events(calendars[0])

    # Or with search:
    events = await client.search_calendar(calendars[0], start=..., end=...)
```

## Implementation Phases

### Phase 1: Create Operations Layer Foundation
**New files:** `caldav/operations/__init__.py`, `caldav/operations/base.py`

1. Create `caldav/operations/` package
2. Define base patterns:
   - Request dataclasses (frozen, immutable)
   - Result dataclasses (for processed data)
   - Pure function signatures
3. Add utility functions for common patterns

**Estimated: 100-150 lines**

### Phase 2: Extract DAVObject Operations
**New file:** `caldav/operations/davobject_ops.py`
**Modify:** `caldav/async_davobject.py`, `caldav/davobject.py`

Extract from DAVObject:
- `get_properties()` → `build_propfind_request()` + `process_propfind_response()`
- `set_properties()` → `build_proppatch_request()` + `process_proppatch_response()`
- `children()` → `build_children_request()` + `process_children_response()`
- `delete()` → `build_delete_request()` + `validate_delete_response()`

**Delete:** Most of `async_davobject.py` AsyncDAVObject (merge into operations)
**Result:** Single `DAVObject` class using operations, ~200 lines saved

### Phase 3: Extract CalendarObjectResource Operations
**New file:** `caldav/operations/calendarobject_ops.py`
**Modify:** `caldav/calendarobjectresource.py`, `caldav/async_davobject.py`

Extract pure logic (currently ~50% of CalendarObjectResource):
- `get_duration()`, `set_duration()` - duration calculations
- `add_attendee()`, `change_attendee_status()` - attendee management
- `expand_rrule()` - recurrence expansion
- `_find_id_path()`, `_generate_url()` - UID/URL handling
- `copy()` - object cloning
- Todo-specific: `complete()`, `is_pending()`, `_next()`, `_complete_recurring_*()`

Keep in CalendarObjectResource:
- `load()`, `save()`, `_put()` - I/O methods (delegate to operations for logic)

**Delete:** `AsyncCalendarObjectResource`, `AsyncEvent`, `AsyncTodo`, `AsyncJournal` from async_davobject.py
**Result:** Single implementation, ~400 lines saved

### Phase 4: Extract Principal Operations
**New file:** `caldav/operations/principal_ops.py`
**Modify:** `caldav/collection.py`, `caldav/async_collection.py`

Extract:
- `_discover_principal_url()` - current-user-principal discovery
- `_get_calendar_home_set()` - calendar-home-set resolution
- `calendar_user_address_set()` - address set extraction
- `get_vcal_address()` - vCalAddress creation

**Delete:** `AsyncPrincipal` from async_collection.py
**Result:** Single `Principal` class, ~80 lines saved

### Phase 5: Extract CalendarSet Operations
**New file:** `caldav/operations/calendarset_ops.py`
**Modify:** `caldav/collection.py`, `caldav/async_collection.py`

Extract:
- `calendars()` - list calendars logic
- `calendar()` - find calendar by name/id
- `make_calendar()` - calendar creation logic

**Delete:** `AsyncCalendarSet` from async_collection.py
**Result:** Single `CalendarSet` class, ~60 lines saved

### Phase 6: Extract Calendar Operations
**New file:** `caldav/operations/calendar_ops.py`
**Modify:** `caldav/collection.py`, `caldav/async_collection.py`

Extract:
- `_create()` - MKCALENDAR logic
- `get_supported_components()` - component type extraction
- `_calendar_comp_class_by_data()` - component class detection
- `_request_report_build_resultlist()` - report result processing
- `search()` integration - connect to CalDAVSearcher
- `multiget()`, `freebusy_request()` - specialized queries
- `objects_by_sync_token()` - sync logic

**Delete:** `AsyncCalendar` from async_collection.py
**Result:** Single `Calendar` class, ~400 lines saved

### Phase 7: Refactor CalDAVSearcher
**Modify:** `caldav/search.py`

Current state: `search()` and `async_search()` are ~320 lines each (duplicated)

Refactor:
1. Keep `build_search_xml_query()` (already Sans-I/O)
2. Extract `process_search_response()` as Sans-I/O function
3. Merge `search()` and `async_search()` into single implementation
4. Calendar.search() delegates to operations

**Result:** ~300 lines saved

### Phase 8: Add High-Level Methods to Both Clients
**Modify:** `caldav/davclient.py`, `caldav/async_davclient.py`

Add high-level methods that use operations layer:

**AsyncDAVClient:**
- `get_principal()` - returns Principal
- `get_calendars(principal)` - returns List[Calendar]
- `get_events(calendar)` - returns List[Event]
- `search_calendar(calendar, **kwargs)` - returns List[Event/Todo/Journal]

**DAVClient:**
- Same methods, using same operations layer
- Sync I/O instead of async I/O
- Backward compat: keep existing `principal()` method delegating to `get_principal()`

Both clients use **identical** operations layer calls - only the I/O differs.

**Result:** ~200 lines saved (remove duplicate logic from both)

### Phase 9: Delete Async Collection/Object Files
**Delete files:**
- `caldav/async_collection.py` (1,128 lines)
- `caldav/async_davobject.py` (945 lines - or most of it)

All functionality now in:
- `caldav/operations/*.py` - business logic
- `caldav/collection.py` - domain objects
- `caldav/calendarobjectresource.py` - calendar objects
- `caldav/davobject.py` - base class

### Phase 10: Update Public API (caldav/aio.py)
**Modify:** `caldav/aio.py`, `caldav/__init__.py`

Ensure async users can:
```python
from caldav.aio import AsyncDAVClient

async with AsyncDAVClient(url=...) as client:
    principal = await client.get_principal()
    calendars = await principal.get_calendars()  # Works with same Calendar class
    events = await calendars[0].get_events()     # Async iteration
```

Domain objects (Calendar, Event, etc.) work with both sync and async clients.

## Files Summary

### New Files
| File | Purpose | Est. Lines |
|------|---------|------------|
| `caldav/operations/__init__.py` | Package exports | 20 |
| `caldav/operations/base.py` | Common utilities | 50 |
| `caldav/operations/davobject_ops.py` | DAVObject logic | 150 |
| `caldav/operations/calendarobject_ops.py` | CalendarObjectResource logic | 300 |
| `caldav/operations/principal_ops.py` | Principal logic | 100 |
| `caldav/operations/calendarset_ops.py` | CalendarSet logic | 80 |
| `caldav/operations/calendar_ops.py` | Calendar logic | 250 |
| **Total new** | | **~950** |

### Files to Delete
| File | Lines Removed |
|------|---------------|
| `caldav/async_collection.py` | 1,128 |
| `caldav/async_davobject.py` | 945 |
| **Total deleted** | **~2,073** |

### Files to Simplify
| File | Current | After | Savings |
|------|---------|-------|---------|
| `caldav/search.py` | ~1,100 | ~500 | ~600 |
| `caldav/collection.py` | 1,473 | ~800 | ~673 |
| `caldav/davobject.py` | 405 | ~200 | ~205 |
| `caldav/calendarobjectresource.py` | 1,633 | ~800 | ~833 |
| **Total** | | | **~2,311** |

### Net Result
- **Lines added:** ~950 (operations layer)
- **Lines removed:** ~2,073 (async files) + ~2,311 (simplification) = ~4,384
- **Net reduction:** ~3,434 lines (~45% of current ~7,600 lines)

## Testing Strategy

1. **Unit tests for operations layer** (new)
   - Test each operation function in isolation
   - No HTTP mocking needed - pure functions
   - High coverage, fast execution

2. **Integration tests** (existing)
   - Run against Radicale, Xandikos, Docker servers
   - Verify backward compatibility
   - Test both sync and async APIs

3. **Backward compatibility tests** (existing)
   - All existing sync API tests must pass
   - `find_objects_and_props()` still works (deprecated)

## Migration Path for Users

### Sync API Users (no changes required)
```python
# Before and after - identical
from caldav import DAVClient

client = DAVClient(url=..., username=..., password=...)
principal = client.principal()
calendars = principal.get_calendars()
events = calendars[0].get_events()

# All existing code continues to work unchanged
```

### Async API Users (cleaner client-centric API)
```python
# Before (old async API - mirrored sync with Async* classes)
from caldav.aio import AsyncDAVClient, AsyncPrincipal
async with AsyncDAVClient(...) as client:
    principal = await AsyncPrincipal.create(client)
    calendars = await principal.get_calendars()
    events = await calendars[0].get_events()

# After (new async API - client-centric, cleaner)
from caldav.aio import AsyncDAVClient

async with AsyncDAVClient(...) as client:
    principal = await client.get_principal()       # Returns Principal (same class)
    calendars = await client.get_calendars(principal)  # Returns List[Calendar]
    events = await client.get_events(calendars[0])     # Returns List[Event]

    # Search example
    events = await client.search_calendar(
        calendars[0],
        start=datetime(2024, 1, 1),
        end=datetime(2024, 12, 31),
        event=True,
    )
```

**Benefits of new async API:**
- No more `AsyncPrincipal`, `AsyncCalendar`, `AsyncEvent` - just one set of classes
- Client methods are explicit about what I/O they do
- Easier to understand data flow
- Same domain objects work with both sync and async

## Success Criteria

1. ✅ All existing sync API tests pass (backward compat)
2. ✅ ~40% code reduction achieved
3. ✅ No business logic duplicated between sync/async
4. ✅ Operations layer has >90% test coverage
5. ✅ Async API is cleaner and well-documented
6. ✅ Integration tests pass on all supported servers

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking sync API | Extensive backward compat tests, gradual migration |
| Complex merge conflicts | Small, focused commits per phase |
| Missing edge cases in operations | Port all existing test assertions to operations tests |
| Server compatibility workarounds lost | Migrate all workarounds to operations layer with tests |

## Design Decisions (Resolved)

1. **Domain object style:** Keep current class style for backward compat. Sync API has convenience methods (`calendar.get_events()`), async API uses client methods directly.

2. **Sync/async bridging:** Not needed! True Sans-I/O means both clients use the same operations layer independently - no bridging required.

3. **Operations return type:** Return data classes (e.g., `CalendarData`), clients wrap them into domain objects (e.g., `Calendar`).

## Verification Plan

1. **Unit tests:** Test each operation function with synthetic data (no HTTP)
2. **Integration tests:** Run existing test suite against Radicale, Xandikos, Docker servers
3. **Backward compat:** All existing sync API tests must pass unchanged
4. **Async tests:** Write new tests for client-centric async API
5. **Manual testing:** Test examples from `examples/` directory
