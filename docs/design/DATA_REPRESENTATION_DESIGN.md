# Data Representation Design for CalendarObjectResource

**Issue**: https://github.com/python-caldav/caldav/issues/613

**Status**: Implemented in v3.0-dev

## Implementation Summary

The core API has been implemented in `caldav/calendarobjectresource.py` with supporting
state classes in `caldav/datastate.py`:

**New Public API:**
- `get_data()` - Returns string, no side effects
- `get_icalendar_instance()` - Returns a COPY (safe for read-only)
- `get_vobject_instance()` - Returns a COPY (safe for read-only)
- `edit_icalendar_instance()` - Context manager for borrowing (exclusive editing)
- `edit_vobject_instance()` - Context manager for borrowing (exclusive editing)

**Internal Optimizations:**
- `_get_uid_cheap()` - Get UID without format conversion
- `_get_component_type_cheap()` - Get VEVENT/VTODO/VJOURNAL without parsing
- `_has_data()` - Check data existence without conversion
- `has_component()` - Optimized to use cheap accessors

**Legacy properties** (`data`, `icalendar_instance`, `vobject_instance`) continue to work
for backward compatibility.

## Problem Statement

The current `CalendarObjectResource` API has problematic side effects when accessing different representations of calendar data:

```python
my_event.data                    # Raw string
my_event.icalendar_instance      # Parsed icalendar object
my_event.vobject_instance        # Parsed vobject object
my_event.data                    # Back to string
```

Each access can trigger conversions, and the code has surprising behavior:

```python
my_event = calendar.search(...)[0]
icalendar_component = my_event.icalendar_component
my_event.data  # NOW icalendar_component is disconnected!
icalendar_component['summary'] = "New Summary"
my_event.save()  # Changes are NOT saved!
```

### Current Implementation

The class has three internal fields where only ONE can be non-null at a time:

- `_data` - raw iCalendar string
- `_icalendar_instance` - parsed icalendar.Calendar object
- `_vobject_instance` - parsed vobject object

Accessing one clears the others, causing the disconnection problem.

## The Fundamental Challenge

The core issue is **mutable aliasing**. When you have multiple mutable representations:

1. User gets `icalendar_instance` reference
2. User gets `vobject_instance` reference
3. User modifies one - the other is now stale
4. User calls `save()` - which representation should be used?

**Only one mutable object can be the "source of truth" at any time.**

## Proposed Solution: Strategy Pattern with Explicit Ownership

### Key Insight: Ownership Transfer

Accessing a mutable representation is an **ownership transfer**. Once you get an icalendar object and start modifying it, that object becomes the source of truth.

### Proposed API

```python
class CalendarObjectResource:
    # === Read-only access (always safe, returns copies) ===

    def get_data(self) -> str:
        """Get raw iCalendar data as string. Always safe."""
        ...

    def get_icalendar(self) -> icalendar.Calendar:
        """Get a COPY of the icalendar object. Safe for inspection."""
        ...

    def get_vobject(self) -> vobject.Component:
        """Get a COPY of the vobject object. Safe for inspection."""
        ...

    # === Write access (explicit ownership transfer) ===

    def set_data(self, data: str) -> None:
        """Set raw data. This becomes the new source of truth."""
        ...

    def set_icalendar(self, cal: icalendar.Calendar) -> None:
        """Set from icalendar object. This becomes the new source of truth."""
        ...

    def set_vobject(self, vobj: vobject.Component) -> None:
        """Set from vobject object. This becomes the new source of truth."""
        ...

    # === Edit access (ownership transfer, returns authoritative object) ===

    def edit_icalendar(self) -> icalendar.Calendar:
        """Get THE icalendar object for editing.

        This transfers ownership - the icalendar object becomes the
        source of truth. Previous vobject references become stale.
        """
        ...

    def edit_vobject(self) -> vobject.Component:
        """Get THE vobject object for editing.

        This transfers ownership - the vobject object becomes the
        source of truth. Previous icalendar references become stale.
        """
        ...

    # === Legacy properties (backward compatibility) ===

    @property
    def data(self) -> str:
        """Get raw data. Does NOT invalidate parsed objects."""
        return self._strategy.get_data()

    @data.setter
    def data(self, value: str) -> None:
        self.set_data(value)

    @property
    def icalendar_instance(self) -> icalendar.Calendar:
        """Returns the authoritative icalendar object.

        WARNING: This transfers ownership. Previous vobject references
        become stale. For read-only access, use get_icalendar().
        """
        return self.edit_icalendar()

    @property
    def vobject_instance(self) -> vobject.Component:
        """Returns the authoritative vobject object.

        WARNING: This transfers ownership. Previous icalendar references
        become stale. For read-only access, use get_vobject().
        """
        return self.edit_vobject()
```

### Strategy Pattern Implementation

```python
from abc import ABC, abstractmethod
from typing import Optional
import icalendar


class DataStrategy(ABC):
    """Abstract strategy for calendar data representation."""

    @abstractmethod
    def get_data(self) -> str:
        """Get raw iCalendar string."""
        pass

    @abstractmethod
    def get_icalendar_copy(self) -> icalendar.Calendar:
        """Get a fresh parsed copy (for read-only access)."""
        pass

    @abstractmethod
    def get_vobject_copy(self):
        """Get a fresh parsed copy (for read-only access)."""
        pass

    def get_uid(self) -> Optional[str]:
        """Extract UID without full parsing if possible.

        Default implementation parses, but subclasses can optimize.
        """
        cal = self.get_icalendar_copy()
        for comp in cal.subcomponents:
            if comp.name in ('VEVENT', 'VTODO', 'VJOURNAL') and 'UID' in comp:
                return str(comp['UID'])
        return None


class NoDataStrategy(DataStrategy):
    """Null Object pattern - no data loaded yet."""

    def get_data(self) -> str:
        return ""

    def get_icalendar_copy(self) -> icalendar.Calendar:
        return icalendar.Calendar()

    def get_vobject_copy(self):
        import vobject
        return vobject.iCalendar()

    def get_uid(self) -> Optional[str]:
        return None


class RawDataStrategy(DataStrategy):
    """Strategy when we have raw string data."""

    def __init__(self, data: str):
        self._data = data

    def get_data(self) -> str:
        return self._data

    def get_icalendar_copy(self) -> icalendar.Calendar:
        return icalendar.Calendar.from_ical(self._data)

    def get_vobject_copy(self):
        import vobject
        return vobject.readOne(self._data)

    def get_uid(self) -> Optional[str]:
        # Optimization: use regex instead of full parsing
        import re
        match = re.search(r'^UID:(.+)$', self._data, re.MULTILINE)
        return match.group(1).strip() if match else None


class IcalendarStrategy(DataStrategy):
    """Strategy when icalendar object is the source of truth."""

    def __init__(self, calendar: icalendar.Calendar):
        self._calendar = calendar

    def get_data(self) -> str:
        return self._calendar.to_ical().decode('utf-8')

    def get_icalendar_copy(self) -> icalendar.Calendar:
        # Parse from serialized form to get a true copy
        return icalendar.Calendar.from_ical(self.get_data())

    def get_authoritative_icalendar(self) -> icalendar.Calendar:
        """Returns THE icalendar object (not a copy)."""
        return self._calendar

    def get_vobject_copy(self):
        import vobject
        return vobject.readOne(self.get_data())


class VobjectStrategy(DataStrategy):
    """Strategy when vobject object is the source of truth."""

    def __init__(self, vobj):
        self._vobject = vobj

    def get_data(self) -> str:
        return self._vobject.serialize()

    def get_icalendar_copy(self) -> icalendar.Calendar:
        return icalendar.Calendar.from_ical(self.get_data())

    def get_vobject_copy(self):
        import vobject
        return vobject.readOne(self.get_data())

    def get_authoritative_vobject(self):
        """Returns THE vobject object (not a copy)."""
        return self._vobject
```

### CalendarObjectResource Integration

```python
class CalendarObjectResource:
    _strategy: DataStrategy

    def __init__(self, data: Optional[str] = None, ...):
        if data:
            self._strategy = RawDataStrategy(data)
        else:
            self._strategy = NoDataStrategy()  # Null Object pattern
        ...

    def _switch_strategy(self, new_strategy: DataStrategy) -> None:
        """Internal: switch to a new strategy."""
        self._strategy = new_strategy

    # Read-only access (Null Object pattern eliminates None checks)
    def get_data(self) -> str:
        return self._strategy.get_data()

    def get_icalendar(self) -> icalendar.Calendar:
        return self._strategy.get_icalendar_copy()

    def get_vobject(self):
        return self._strategy.get_vobject_copy()

    # Write access
    def set_data(self, data: str) -> None:
        self._strategy = RawDataStrategy(data)

    def set_icalendar(self, cal: icalendar.Calendar) -> None:
        self._strategy = IcalendarStrategy(cal)

    def set_vobject(self, vobj) -> None:
        self._strategy = VobjectStrategy(vobj)

    # Edit access (ownership transfer)
    def edit_icalendar(self) -> icalendar.Calendar:
        if not isinstance(self._strategy, IcalendarStrategy):
            cal = self._strategy.get_icalendar_copy()
            self._strategy = IcalendarStrategy(cal)
        return self._strategy.get_authoritative_icalendar()

    def edit_vobject(self):
        if not isinstance(self._strategy, VobjectStrategy):
            vobj = self._strategy.get_vobject_copy()
            self._strategy = VobjectStrategy(vobj)
        return self._strategy.get_authoritative_vobject()

    # Legacy properties
    @property
    def data(self) -> Optional[str]:
        return self.get_data()

    @data.setter
    def data(self, value: str) -> None:
        self.set_data(value)

    @property
    def icalendar_instance(self) -> Optional[icalendar.Calendar]:
        return self.edit_icalendar()

    @property
    def vobject_instance(self):
        return self.edit_vobject()

    @property
    def icalendar_component(self):
        """Get the VEVENT/VTODO/VJOURNAL component."""
        cal = self.edit_icalendar()
        for comp in cal.subcomponents:
            if comp.name in ('VEVENT', 'VTODO', 'VJOURNAL'):
                return comp
        return None
```

## State Transitions

```
                    ┌─────────────────┐
   set_data()       │ RawDataStrategy │
   ─────────────────►│ (_data="...")   │
                    └────────┬────────┘
                             │
                             │ edit_icalendar()
                             ▼
                    ┌─────────────────┐
                    │IcalendarStrategy│
                    │ (_calendar=...) │
                    └────────┬────────┘
                             │
                             │ edit_vobject()
                             ▼
                    ┌─────────────────┐
                    │ VobjectStrategy │
                    │ (_vobject=...)  │
                    └─────────────────┘

Note: get_data() works from ANY strategy without switching.
      get_icalendar() / get_vobject() return COPIES without switching.
      Only edit_*() methods cause strategy switches.
```

## Handling Internal Uses

For internal operations that need to peek at the data without changing ownership:

```python
def _find_uid(self) -> Optional[str]:
    # Use strategy's optimized method - no ownership change
    return self._strategy.get_uid() if self._strategy else None

def _get_component_type(self) -> Optional[str]:
    # Use a copy - don't transfer ownership
    cal = self._strategy.get_icalendar_copy()
    for comp in cal.subcomponents:
        if comp.name in ('VEVENT', 'VTODO', 'VJOURNAL'):
            return comp.name
    return None
```

## Migration Path

### Phase 1 (3.0)
- Add `get_*()`, `set_*()`, `edit_*()` methods
- Keep legacy properties working with current semantics
- Document the ownership transfer behavior clearly
- Add deprecation warnings for confusing usage patterns

### Phase 2 (3.x)
- Add warnings when legacy properties cause ownership transfer
- Encourage migration to explicit methods

### Phase 3 (4.0)
- Consider making legacy properties read-only
- Or remove implicit ownership transfer from properties

## Usage Examples

### Safe Read-Only Access
```python
event = calendar.search(...)[0]

# Just inspecting - use get_*() methods
summary = event.get_icalendar().subcomponents[0]['summary']
print(f"Event summary: {summary}")

# Multiple formats at once - all are copies, no conflict
ical_copy = event.get_icalendar()
vobj_copy = event.get_vobject()
raw_data = event.get_data()
```

### Modifying with icalendar
```python
event = calendar.search(...)[0]

# Get authoritative icalendar object for editing
cal = event.edit_icalendar()
cal.subcomponents[0]['summary'] = 'New Summary'

# Save uses the icalendar object
event.save()
```

### Modifying with vobject
```python
event = calendar.search(...)[0]

# Get authoritative vobject object for editing
vobj = event.edit_vobject()
vobj.vevent.summary.value = 'New Summary'

# Save uses the vobject object
event.save()
```

### Setting from External Source
```python
# Set from string
event.set_data(ical_string)

# Set from icalendar object created elsewhere
event.set_icalendar(my_calendar)

# Set from vobject object created elsewhere
event.set_vobject(my_vobject)
```

## Open Questions

1. **Should `get_data()` cache the serialized string?** This could avoid repeated serialization but adds complexity.

2. **Should we support jcal (JSON) format?** The strategy pattern makes this easy to add.

3. **Should `edit_*()` be renamed to `as_*()`?** e.g., `event.as_icalendar()` might be more intuitive.

4. **What about component-level access?** Should we have `edit_icalendar_component()` that returns just the VEVENT/VTODO?

5. **Thread safety?** The current design is not thread-safe. Should it be?

## Alternative: Borrowing Pattern with Context Managers

*Suggested by @niccokunzmann in issue #613*

A cleaner approach inspired by Rust's borrowing semantics: use context managers
to explicitly "borrow" a representation for editing.

### Concept

```python
# Explicit borrowing with context managers
with my_event.icalendar_instance as calendar:
    calendar.subcomponents[0]['summary'] = 'New Summary'
    # Exclusive access - can't access vobject here

# Changes committed, can now use other representations
with my_event.vobject_instance as vobj:
    # verification, etc.
```

### Benefits

1. **Clear ownership scope** - The `with` block clearly defines when you have edit access
2. **Prevents concurrent access** - Accessing another representation while one is borrowed raises an error
3. **Pythonic** - Context managers are idiomatic Python
4. **Explicit commit point** - Changes are committed when exiting the context

### State Machine

This is more of a **State pattern** than a Strategy pattern:

```
                     ┌──────────────────────────────────────────────────────┐
                     │                                                      │
                     ▼                                                      │
              ┌─────────────┐                                               │
              │  ReadOnly   │◄──────────────────────────────────────────────┤
              │   State     │                                               │
              └──────┬──────┘                                               │
                     │                                                      │
      ┌──────────────┼──────────────┐                                       │
      │              │              │                                       │
      │ with         │ with         │ with                                  │
      │ .data        │ .icalendar   │ .vobject                              │
      ▼              ▼              ▼                                       │
┌───────────┐ ┌─────────────┐ ┌─────────────┐                               │
│  Editing  │ │  Editing    │ │  Editing    │                               │
│  Data     │ │  Icalendar  │ │  Vobject    │                               │
│  (noop)   │ │  State      │ │  State      │                               │
└─────┬─────┘ └──────┬──────┘ └──────┬──────┘                               │
      │              │               │                                      │
      │ exit         │ exit          │ exit                                 │
      │ context      │ context       │ context                              │
      │              │               │                                      │
      └──────────────┴───────────────┴──────────────────────────────────────┘
```

### Implementation Sketch

```python
class CalendarObjectResource:
    _state: 'DataState'
    _borrowed: bool = False

    def __init__(self, data: Optional[str] = None):
        self._state = RawDataState(data) if data else NoDataState()
        self._borrowed = False

    @contextmanager
    def icalendar_instance(self):
        """Borrow the icalendar object for editing."""
        if self._borrowed:
            raise RuntimeError("Already borrowed - cannot access another representation")

        # Switch to icalendar state if needed
        if not isinstance(self._state, IcalendarState):
            cal = self._state.get_icalendar_copy()
            self._state = IcalendarState(cal)

        self._borrowed = True
        try:
            yield self._state.get_authoritative_icalendar()
        finally:
            self._borrowed = False

    @contextmanager
    def vobject_instance(self):
        """Borrow the vobject object for editing."""
        if self._borrowed:
            raise RuntimeError("Already borrowed - cannot access another representation")

        # Switch to vobject state if needed
        if not isinstance(self._state, VobjectState):
            vobj = self._state.get_vobject_copy()
            self._state = VobjectState(vobj)

        self._borrowed = True
        try:
            yield self._state.get_authoritative_vobject()
        finally:
            self._borrowed = False

    @contextmanager
    def data(self):
        """Borrow the data (read-only, strings are immutable)."""
        if self._borrowed:
            raise RuntimeError("Already borrowed - cannot access another representation")

        self._borrowed = True
        try:
            yield self._state.get_data()
        finally:
            self._borrowed = False

    # Read-only access (always safe, no borrowing needed)
    def get_data(self) -> str:
        return self._state.get_data()

    def get_icalendar(self) -> icalendar.Calendar:
        return self._state.get_icalendar_copy()

    def get_vobject(self):
        return self._state.get_vobject_copy()


class DataState(ABC):
    """Abstract state for calendar data."""

    @abstractmethod
    def get_data(self) -> str:
        pass

    @abstractmethod
    def get_icalendar_copy(self) -> icalendar.Calendar:
        pass

    @abstractmethod
    def get_vobject_copy(self):
        pass


class NoDataState(DataState):
    """Null Object pattern - no data loaded yet."""

    def get_data(self) -> str:
        return ""

    def get_icalendar_copy(self) -> icalendar.Calendar:
        return icalendar.Calendar()

    def get_vobject_copy(self):
        import vobject
        return vobject.iCalendar()


class RawDataState(DataState):
    """State when raw string data is the source of truth."""

    def __init__(self, data: str):
        self._data = data

    def get_data(self) -> str:
        return self._data

    def get_icalendar_copy(self) -> icalendar.Calendar:
        return icalendar.Calendar.from_ical(self._data)

    def get_vobject_copy(self):
        import vobject
        return vobject.readOne(self._data)


class IcalendarState(DataState):
    """State when icalendar object is the source of truth."""

    def __init__(self, calendar: icalendar.Calendar):
        self._calendar = calendar

    def get_data(self) -> str:
        return self._calendar.to_ical().decode('utf-8')

    def get_icalendar_copy(self) -> icalendar.Calendar:
        return icalendar.Calendar.from_ical(self.get_data())

    def get_authoritative_icalendar(self) -> icalendar.Calendar:
        return self._calendar

    def get_vobject_copy(self):
        import vobject
        return vobject.readOne(self.get_data())


class VobjectState(DataState):
    """State when vobject object is the source of truth."""

    def __init__(self, vobj):
        self._vobject = vobj

    def get_data(self) -> str:
        return self._vobject.serialize()

    def get_icalendar_copy(self) -> icalendar.Calendar:
        return icalendar.Calendar.from_ical(self.get_data())

    def get_vobject_copy(self):
        import vobject
        return vobject.readOne(self.get_data())

    def get_authoritative_vobject(self):
        return self._vobject
```

### Usage Examples with Borrowing

```python
# Read-only access (always safe, no borrowing)
summary = event.get_icalendar().subcomponents[0]['summary']

# Editing with explicit borrowing
with event.icalendar_instance as cal:
    cal.subcomponents[0]['summary'] = 'New Summary'
    # Can NOT access event.vobject_instance here - will raise RuntimeError

event.save()

# Now can use vobject
with event.vobject_instance as vobj:
    print(vobj.vevent.summary.value)

# Nested borrowing of same type works (with refcounting)
with event.icalendar_instance as cal:
    # some function that also needs icalendar
    def helper(evt):
        with evt.icalendar_instance as inner_cal:  # Works - same type
            return inner_cal.subcomponents[0]['uid']
    uid = helper(event)
```

### Comparison: Edit Methods vs Borrowing

| Aspect | edit_*() methods | with borrowing |
|--------|------------------|----------------|
| Ownership scope | Implicit (until next edit) | Explicit (with block) |
| Concurrent access | Silently replaces | Raises error |
| Pythonic | Less | More |
| Backward compatible | Easier | Harder |
| Thread safety | None | Could add locking |

## Recommendation

The **borrowing pattern with context managers** is the cleaner long-term solution,
but requires more breaking changes. For 3.0, consider:

1. Add `get_*()` methods for safe read-only access (non-breaking)
2. Add context manager support for `icalendar_instance` / `vobject_instance` (additive)
3. Deprecate direct property access for editing
4. In 4.0, make context managers the only way to edit

## Related Work

- Python's `io.BytesIO` / `io.StringIO` - similar "view" concept
- Django's `QuerySet` - lazy evaluation with clear ownership
- SQLAlchemy's Unit of Work - tracks dirty objects
- Rust's borrowing and ownership - inspiration for the context manager approach
- Python's `threading.Lock` - context manager for exclusive access
