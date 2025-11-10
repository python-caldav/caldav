# PR #555 Refactoring Proposal: Reducing Code Duplication

## Overview

Thank you for the comprehensive httpx migration and async support! The async functionality is well-implemented and the 100% backward compatibility is excellent. However, as noted in the review, there's significant code duplication (~1,500 lines across async_* files) that we can address through strategic refactoring.

## Current Code Metrics

```
File                          Lines   Purpose
─────────────────────────────────────────────────────────────
davobject.py                    430   Sync base class
async_davobject.py              234   Async base class (duplicates)

calendarobjectresource.py     1,649   Sync objects + business logic
async_objects.py                235   Async objects (duplicates patterns)

collection.py                 1,642   Sync collections
async_collection.py             479   Async collections (duplicates)
─────────────────────────────────────────────────────────────
Total async duplication:     ~1,500 lines
```

## Proposed Refactoring Strategy

### Phase 1: Eliminate `async_objects.py` (Simplest Win)

**Observation**: `objects.py` is just a backward-compatibility shim (18 lines). We don't need `async_objects.py` at all.

**Action**:
1. Move `AsyncEvent`, `AsyncTodo`, `AsyncJournal`, `AsyncFreeBusy` classes directly into `async_collection.py`
2. Delete `async_objects.py`
3. Update imports in `__init__.py`

**Benefit**: Eliminates 235 lines, simplifies module structure

### Phase 2: Extract Shared Business Logic (Biggest Impact)

The key insight: Most of `calendarobjectresource.py` (1,649 lines) contains business logic that's identical for both sync and async:
- iCalendar parsing and manipulation
- UID extraction
- Property validation
- Date/time handling
- Component type detection
- Relationship mapping

**Proposed Architecture**:

```python
# caldav/lib/ical_logic.py (NEW FILE)
class CalendarObjectLogic:
    """
    Shared business logic for calendar objects.
    Pure functions and stateless operations on iCalendar data.
    """

    @staticmethod
    def extract_uid(data: str) -> Optional[str]:
        """Extract UID from iCalendar data"""
        # Current implementation from async_objects.py:67-84
        ...

    @staticmethod
    def build_ical_component(comp_name: str, **kwargs):
        """Build an iCalendar component"""
        ...

    @staticmethod
    def get_duration(component):
        """Calculate duration from DTSTART/DTEND/DURATION"""
        ...

    # ... other pure business logic methods
```

**Updated class structure**:

```python
# caldav/calendarobjectresource.py
class CalendarObjectResource(DAVObject):
    """Sync calendar object resource"""
    _logic = CalendarObjectLogic()  # Shared logic

    def load(self) -> Self:
        response = self.client.get(str(self.url))
        self._data = response.text
        self.id = self._logic.extract_uid(self._data)
        return self

    def save(self, **kwargs):
        # Sync HTTP call
        response = self.client.put(str(self.url), data=self.data)
        return self

# caldav/async_collection.py
class AsyncCalendarObjectResource(AsyncDAVObject):
    """Async calendar object resource"""
    _logic = CalendarObjectLogic()  # Same shared logic

    async def load(self) -> Self:
        response = await self.client.get(str(self.url))
        self._data = response.text
        self.id = self._logic.extract_uid(self._data)  # Same logic!
        return self

    async def save(self, **kwargs):
        # Async HTTP call
        response = await self.client.put(str(self.url), data=self.data)
        return self
```

### Phase 3: Reduce Base Class Duplication

**Current Issue**: `davobject.py` (430 lines) and `async_davobject.py` (234 lines) duplicate property handling, URL management, etc.

**Option A: Shared Core with HTTP Protocol** (Recommended)

```python
# caldav/lib/dav_core.py (NEW FILE)
class DAVObjectCore:
    """
    Shared core functionality for DAV objects.
    No HTTP operations - only data management.
    """

    def __init__(self, client, url, parent, name, id, props, **extra):
        """Common initialization logic"""
        if client is None and parent is not None:
            client = parent.client
        self.client = client
        self.parent = parent
        self.name = name
        self.id = id
        self.props = props or {}
        self.extra_init_options = extra
        # URL handling (same for sync/async)
        ...

    @property
    def canonical_url(self) -> str:
        """Canonical URL (same for sync/async)"""
        return str(self.url.canonical())

    # Other shared non-HTTP methods
```

```python
# caldav/davobject.py
class DAVObject(DAVObjectCore):
    """Sync DAV object - adds HTTP operations"""

    def _query(self, root, depth=0):
        # Sync HTTP call
        return self.client.propfind(self.url, body, depth)

    def get_properties(self, props, **kwargs):
        # Uses _query (sync)
        ...

# caldav/async_davobject.py
class AsyncDAVObject(DAVObjectCore):
    """Async DAV object - adds async HTTP operations"""

    async def _query(self, root, depth=0):
        # Async HTTP call
        return await self.client.propfind(self.url, body, depth)

    async def get_properties(self, props, **kwargs):
        # Uses _query (async)
        ...
```

**Option B: Composition over Inheritance**

```python
# caldav/davobject.py
class DAVObject:
    def __init__(self, client, **kwargs):
        self._core = DAVObjectCore(**kwargs)  # Compose
        self._client = client  # Sync client

    def get_properties(self, props):
        response = self._client.propfind(...)  # Sync
        return self._core.parse_properties(response)

# caldav/async_davobject.py
class AsyncDAVObject:
    def __init__(self, client, **kwargs):
        self._core = DAVObjectCore(**kwargs)  # Same core
        self._client = client  # Async client

    async def get_properties(self, props):
        response = await self._client.propfind(...)  # Async
        return self._core.parse_properties(response)
```

### Phase 4: Collection Refactoring

Similar pattern for `collection.py` (1,642 lines) vs `async_collection.py` (479 lines):

```python
# caldav/lib/calendar_logic.py (NEW FILE)
class CalendarLogic:
    """Shared calendar business logic"""

    @staticmethod
    def parse_calendar_metadata(props_dict):
        """Extract calendar ID, name from properties"""
        ...

    @staticmethod
    def build_calendar_query(start, end, comp_filter):
        """Build calendar-query XML"""
        ...
```

Then both `Calendar` and `AsyncCalendar` use the same logic, differing only in HTTP operations.

## Refactoring Phases Summary

| Phase | Action | Lines Saved | Effort |
|-------|--------|-------------|--------|
| 1 | Eliminate `async_objects.py` | ~235 | Low |
| 2 | Extract iCalendar business logic | ~500+ | Medium |
| 3 | Share DAVObject core | ~150+ | Medium |
| 4 | Share Calendar logic | ~300+ | High |
| **Total** | | **~1,200 lines** | |

## Recommended Approach

**Incremental refactoring in this order**:

1. **Start with Phase 1** (eliminate `async_objects.py`) - quick win, low risk
2. **Then Phase 2** (extract CalendarObjectLogic) - highest impact
3. **Then Phase 3** (share DAVObject core) - architectural improvement
4. **Finally Phase 4** (Calendar logic) - polish

This approach:
- ✅ Maintains backward compatibility at each step
- ✅ Delivers incremental value
- ✅ Reduces risk of breaking changes
- ✅ Makes code review easier (smaller PRs)

## Alternative: Keep Current Structure

If you prefer to merge as-is for v3.0 and refactor later:

**Pros**:
- Get async support shipped faster
- Refactoring can be done incrementally post-merge
- Less risk of breaking backward compatibility

**Cons**:
- Technical debt compounds
- Harder to maintain two codebases
- Bug fixes need to be applied twice

## Implementation Example

Here's a concrete example showing the refactoring for UID extraction:

**Before** (duplicated):
```python
# caldav/calendarobjectresource.py (sync)
def load(self):
    # ... HTTP call ...
    for line in data.split("\n"):
        if line.strip().startswith("UID:"):
            uid = line.split(":", 1)[1].strip()
            self.id = uid
    # ...

# caldav/async_objects.py (async - duplicate!)
async def load(self):
    # ... HTTP call ...
    for line in data.split("\n"):
        if line.strip().startswith("UID:"):
            uid = line.split(":", 1)[1].strip()
            self.id = uid
    # ...
```

**After** (shared):
```python
# caldav/lib/ical_logic.py (NEW - shared)
class ICalLogic:
    @staticmethod
    def extract_uid(data: str) -> Optional[str]:
        for line in data.split("\n"):
            if line.strip().startswith("UID:"):
                return line.split(":", 1)[1].strip()
        return None

# caldav/calendarobjectresource.py (sync)
def load(self):
    response = self.client.get(str(self.url))
    self._data = response.text
    self.id = ICalLogic.extract_uid(self._data)  # Shared!
    return self

# caldav/async_collection.py (async)
async def load(self):
    response = await self.client.get(str(self.url))
    self._data = response.text
    self.id = ICalLogic.extract_uid(self._data)  # Same code!
    return self
```

## Questions for Discussion

1. **Timing**: Refactor before merge or after v3.0 release?
2. **Breaking changes**: Would major API changes be acceptable for v3.0?
3. **Testing**: Should we add property-based tests to ensure sync/async parity?
4. **Documentation**: Should we document the shared-logic pattern for contributors?

## Conclusion

The httpx migration is excellent work! The async support is well-designed and the backward compatibility is impressive. With strategic refactoring, we can:

- Reduce code duplication by ~1,200 lines (~80%)
- Improve maintainability (one place for business logic)
- Make bug fixes easier (fix once, not twice)
- Set up a clean architecture for future async additions

I'm happy to contribute to this refactoring effort or provide more detailed implementation guidance. What approach would you prefer?

---

## References

- PR #555: Migrate from niquests to httpx and add async support
- Issue #457, #342, #455: Related async support requests
- caldav/objects.py:1-18: Example of backward-compatibility pattern
