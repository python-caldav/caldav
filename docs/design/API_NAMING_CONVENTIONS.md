# API Naming Conventions

This document describes the API naming conventions for the caldav library, including guidance on legacy vs recommended method names.

## Overview

The caldav library maintains backward compatibility while introducing cleaner API names. Both sync (`DAVClient`) and async (`AsyncDAVClient`) clients support the recommended API names.

## DAVClient Methods

### Principal Access

| Recommended | Legacy | Notes |
|-------------|--------|-------|
| `get_principal()` | `principal()` | Returns the Principal object for the authenticated user |
| `search_principals(name=None)` | `principals(name=None)` | Search for principals on the server |

**Example:**
```python
# Recommended
principal = client.get_principal()

# Legacy (still works, but not recommended for new code)
principal = client.principal()
```

### Capability Checks

| Recommended | Legacy | Notes |
|-------------|--------|-------|
| `supports_dav()` | `check_dav_support()` | Returns DAV support string or None |
| `supports_caldav()` | `check_cdav_support()` | Returns True if CalDAV is supported |
| `supports_scheduling()` | `check_scheduling_support()` | Returns True if RFC6638 scheduling is supported |

**Example:**
```python
# Recommended
if client.supports_caldav():
    calendars = client.get_calendars()

# Legacy (still works, but not recommended for new code)
if client.check_cdav_support():
    calendars = client.get_calendars()
```

### Calendar and Event Access

These methods use the recommended naming and are available in both sync and async clients:

| Method | Description |
|--------|-------------|
| `get_calendars(principal=None)` | Get all calendars for a principal |
| `get_events(calendar_url, start, end)` | Get events in a date range |
| `get_todos(calendar_url, ...)` | Get todos with optional filters |
| `search_calendar(calendar_url, ...)` | Search calendar with flexible criteria |

## Calendar Methods

### Search Methods

| Recommended | Legacy | Notes |
|-------------|--------|-------|
| `search(...)` | `date_search(...)` | `date_search` is deprecated; use `search` instead |

**Example:**
```python
# Recommended
events = calendar.search(
    start=datetime(2024, 1, 1),
    end=datetime(2024, 12, 31),
    event=True,
    expand=True
)

# Legacy (deprecated, emits DeprecationWarning)
events = calendar.date_search(
    start=datetime(2024, 1, 1),
    end=datetime(2024, 12, 31),
    expand=True
)
```

## Deprecation Timeline

### Deprecated in 3.0 (will be removed in 4.0)

- `Calendar.date_search()` - use `Calendar.search()` instead
- `DAVClient.principals()` - use `DAVClient.search_principals()` instead
- `CalendarObjectResource.expand_rrule()` - expansion is handled by `search(expand=True)`
- `CalendarObjectResource.split_expanded()` - expansion is handled by `search(expand=True)`

### Legacy but Supported

The following methods are considered "legacy" but will continue to work. New code should prefer the recommended alternatives:

- `DAVClient.principal()` - use `get_principal()` instead
- `DAVClient.principals()` - use `search_principals()` instead (deprecated with warning)
- `DAVClient.check_dav_support()` - use `supports_dav()` instead
- `DAVClient.check_cdav_support()` - use `supports_caldav()` instead
- `DAVClient.check_scheduling_support()` - use `supports_scheduling()` instead

## Rationale

The new naming conventions follow these principles:

1. **Consistency**: Same method names work in both sync and async clients
2. **Clarity**: `get_*` prefix for methods that retrieve data
3. **Readability**: `supports_*` is more natural than `check_*_support`
4. **Python conventions**: Method names follow PEP 8 style

## Migration Guide

### From caldav 2.x to 3.x

1. Replace `date_search()` with `search()`:
   ```python
   # Before
   events = calendar.date_search(start, end, expand=True)

   # After
   events = calendar.search(start=start, end=end, event=True, expand=True)
   ```

2. Optionally update to new naming conventions:
   ```python
   # Before
   principal = client.principal()
   if client.check_cdav_support():
       ...

   # After (recommended)
   principal = client.get_principal()
   if client.supports_caldav():
       ...
   ```

3. Remove usage of deprecated methods:
   - `expand_rrule()` - use `search(expand=True)` instead
   - `split_expanded()` - use `search(expand=True)` instead
