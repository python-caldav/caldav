# Sync vs Async Implementation Overview

This document provides an overview of what logic remains in the sync (old) files versus what has been moved to async and is wrapped.

## Executive Summary

The caldav library uses an **async-first architecture** where:
- `AsyncDAVClient` is the true HTTP implementation
- Sync versions are thin wrappers using `asyncio.run()` or `EventLoopManager`

| Component | Async Delegation | Status |
|-----------|------------------|--------|
| DAVClient (HTTP layer) | 100% | Complete |
| CalendarSet | ~60% | Partial |
| Principal | ~35% | Mostly sync |
| Calendar | ~40% | Mixed |
| CalendarObjectResource | ~30% | Mixed |

---

## 1. DAVClient Layer (85% Complete)

### Fully Delegated to Async ✓
All HTTP methods delegate to `AsyncDAVClient`:
- `propfind()`, `proppatch()`, `report()`, `options()`
- `mkcol()`, `mkcalendar()`, `put()`, `post()`, `delete()`
- `request()`

### Sync-Only Infrastructure
- `EventLoopManager` - manages persistent event loop for connection reuse
- `DAVResponse` - bridge class that can consume `AsyncDAVResponse`
- `_sync_request()` - fallback for mocked unit tests
- `_is_mocked()` - detects test mocking

---

## 2. Collection Layer

### CalendarSet (60% Delegated)
| Method | Status |
|--------|--------|
| `calendars()` | Async-delegated with fallback |
| `calendar()` | Partial delegation |
| `make_calendar()` | **Sync only** |

### Principal (35% Delegated)
| Method | Status |
|--------|--------|
| `__init__()` | **Sync only** (PROPFIND discovery) |
| `calendars()` | Delegates via calendar_home_set |
| `calendar_home_set` | **Sync only** (lazy PROPFIND) |
| `make_calendar()` | Sync-delegated |
| `freebusy_request()` | **Sync only** |

### Calendar (40% Delegated)
| Method | Status |
|--------|--------|
| `search()` | **Sync only** (see below) |
| `events()`, `todos()`, `journals()` | Via sync search |
| `save()`, `delete()` | **Sync only** |
| `object_by_uid()` | **Sync only** |
| `multiget()` | **Sync only** |

---

## 3. CalendarObjectResource Layer (30% Delegated)

| Method | Status |
|--------|--------|
| `load()` | Async-delegated |
| `save()` | Partial - validates sync, then delegates |
| `delete()` | Async-delegated (inherited) |
| `load_by_multiget()` | **Sync only** |
| Data manipulation methods | **Sync only** (correct - no I/O) |

---

## 4. What's Blocking Async Search Delegation

The sync `Calendar.search()` exists alongside `AsyncCalendar.search()` but doesn't delegate.

### Missing Infrastructure

1. **No `_run_async_calendar()` helper**
   - `CalendarSet` has `_run_async_calendarset()`
   - `Principal` has `_run_async_principal()`
   - `Calendar` has **no equivalent helper**

2. **No async-to-sync object converters**
   - `_async_calendar_to_sync()` exists for Calendar objects
   - **No equivalent for Event/Todo/Journal**
   - `AsyncEvent` → `Event` conversion needed

3. **CalDAVSearcher integration**
   - Both sync and async use `CalDAVSearcher` for query building
   - But sync calls `CalDAVSearcher.search()` which does its own HTTP
   - Async only uses `CalDAVSearcher` for XML building, does HTTP itself

### Required Changes to Enable Delegation

```python
# 1. Add helper to Calendar class
def _run_async_calendar(self, async_func):
    """Run async function with AsyncCalendar."""
    ...

# 2. Add object converters
def _async_event_to_sync(self, async_event) -> Event:
    """Convert AsyncEvent to Event."""
    return Event(
        client=self.client,
        url=async_event.url,
        data=async_event.data,
        parent=self,
        props=async_event.props,
    )

# 3. Update Calendar.search() to delegate
def search(self, **kwargs):
    async def _async_search(async_cal):
        return await async_cal.search(**kwargs)

    try:
        async_results = self._run_async_calendar(_async_search)
        return [self._async_event_to_sync(obj) for obj in async_results]
    except NotImplementedError:
        # Fallback to sync for mocked clients
        return self._sync_search(**kwargs)
```

### Why It Hasn't Been Done Yet

1. **Phased approach** - HTTP layer was prioritized first
2. **Test compatibility** - many tests mock at the search level
3. **Complex return types** - need to convert async objects back to sync
4. **CalDAVSearcher coupling** - sync version tightly coupled to searcher

---

## 5. Async Methods Without Sync Wrappers

These async methods exist but aren't called from sync code:

| Async Method | Sync Equivalent |
|--------------|-----------------|
| `AsyncCalendar.search()` | Uses own implementation |
| `AsyncCalendar.events()` | Uses own implementation |
| `AsyncCalendar.object_by_uid()` | Uses own implementation |
| `AsyncPrincipal.create()` | No equivalent (class method) |

---

## 6. Correctly Sync-Only Methods

These methods don't need async versions (no I/O):
- `add_attendee()`, `add_organizer()`
- `set_relation()`, `get_relatives()`
- `expand_rrule()`, `split_expanded()`
- Property accessors (`icalendar_instance`, `vobject_instance`)
- All icalendar/vobject manipulation

---

*Generated by Claude Code*
