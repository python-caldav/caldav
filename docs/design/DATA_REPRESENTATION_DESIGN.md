# Data Representation Design for CalendarObjectResource

**Issue**: https://github.com/python-caldav/caldav/issues/613

**Status**: Draft / Under Discussion

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
            self._strategy = None
        ...

    def _switch_strategy(self, new_strategy: DataStrategy) -> None:
        """Internal: switch to a new strategy."""
        self._strategy = new_strategy

    # Read-only access
    def get_data(self) -> Optional[str]:
        return self._strategy.get_data() if self._strategy else None

    def get_icalendar(self) -> Optional[icalendar.Calendar]:
        return self._strategy.get_icalendar_copy() if self._strategy else None

    def get_vobject(self):
        return self._strategy.get_vobject_copy() if self._strategy else None

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

## Related Work

- Python's `io.BytesIO` / `io.StringIO` - similar "view" concept
- Django's `QuerySet` - lazy evaluation with clear ownership
- SQLAlchemy's Unit of Work - tracks dirty objects
