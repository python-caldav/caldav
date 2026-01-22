# Data Properties Usage Overview

This document provides an overview of where `obj.data`, `obj.icalendar_instance`,
`obj.icalendar_component`, `obj.vobject_instance`, and their aliases (`obj.component`,
`obj.instance`) are used throughout the codebase.

Related: See [DATA_REPRESENTATION_DESIGN.md](DATA_REPRESENTATION_DESIGN.md) for the design
discussion around these properties (GitHub issue #613).

## Property Definitions

All properties are defined in `caldav/calendarobjectresource.py`:

| Property | Line | Type | Notes |
|----------|------|------|-------|
| `data` | 1179 | `property()` | String representation of calendar data |
| `wire_data` | 1182 | `property()` | Raw wire format data |
| `vobject_instance` | 1235 | `property()` | vobject library object |
| `instance` | 1241 | `property()` | **Alias** for `vobject_instance` |
| `icalendar_instance` | 1274 | `property()` | icalendar library object (full calendar) |
| `icalendar_component` | 492 | `property()` | Inner component (VEVENT/VTODO/VJOURNAL) |
| `component` | 498 | N/A | **Alias** for `icalendar_component` |

---

## Library Code Usage (`caldav/`)

### `obj.data`

| File | Line | Context |
|------|------|---------|
| `calendarobjectresource.py` | 131 | `self.data = data` - Setting data in constructor |
| `calendarobjectresource.py` | 633 | `calendar.add_event(self.data)` - Adding event to calendar |
| `calendarobjectresource.py` | 656 | `data=self.data` - Passing data to copy operation |
| `calendarobjectresource.py` | 698 | `self.data = r.raw` - Setting data from HTTP response |
| `calendarobjectresource.py` | 724 | `self.data = r.raw` - Setting data from HTTP response |
| `calendarobjectresource.py` | 745 | `url, self.data = next(mydata)` - Unpacking data |
| `calendarobjectresource.py` | 752 | `error.assert_(self.data)` - Asserting data exists |
| `calendarobjectresource.py` | 808 | `self.url, self.data, {...}` - PUT request with data |
| `calendarobjectresource.py` | 830 | `str(self.data)` - Converting data to string |
| `calendarobjectresource.py` | 1130-1132 | `self.data.count("BEGIN:VEVENT")` - Counting components in data |
| `calendarobjectresource.py` | 1267 | `if not self.data:` - Checking if data exists |
| `calendarobjectresource.py` | 1270 | `to_unicode(self.data)` - Converting data to unicode |
| `collection.py` | 568 | `caldavobj.data` - Accessing data from calendar object |
| `collection.py` | 2083 | `old_by_url[url].data` - Comparing old data |
| `collection.py` | 2087 | `obj.data if hasattr(obj, "data")` - Safely accessing data |

### `obj.icalendar_instance`

| File | Line | Context |
|------|------|---------|
| `calendarobjectresource.py` | 189 | `self.icalendar_instance.subcomponents` - Getting subcomponents |
| `calendarobjectresource.py` | 199 | `obj.icalendar_instance.subcomponents = []` - Clearing subcomponents |
| `calendarobjectresource.py` | 201-202 | Appending to subcomponents |
| `calendarobjectresource.py` | 236 | `self.icalendar_instance, components=[...]` - Passing to function |
| `calendarobjectresource.py` | 249 | `calendar = self.icalendar_instance` - Assignment |
| `calendarobjectresource.py` | 460 | `if not self.icalendar_instance:` - Checking existence |
| `calendarobjectresource.py` | 465 | Iterating over subcomponents |
| `calendarobjectresource.py` | 481-490 | Manipulating subcomponents and properties |
| `calendarobjectresource.py` | 593 | `self.icalendar_instance.get("method", None)` - Getting METHOD |
| `calendarobjectresource.py` | 601 | `self.icalendar_instance.get("method", None)` - Getting METHOD |
| `calendarobjectresource.py` | 629 | `self.icalendar_instance.pop("METHOD")` - Removing METHOD |
| `calendarobjectresource.py` | 794 | Iterating over subcomponents |
| `calendarobjectresource.py` | 1025 | `obj.icalendar_instance` - Getting instance |
| `calendarobjectresource.py` | 1269 | `self.icalendar_instance = icalendar.Calendar.from_ical(...)` - Setting |
| `calendarobjectresource.py` | 1549 | `self.icalendar_instance.subcomponents` - Getting recurrences |
| `calendarobjectresource.py` | 1614 | Appending to subcomponents |
| `collection.py` | 898 | `obj.icalendar_instance.walk("vevent")[0]["uid"]` - Getting UID |
| `operations/search_ops.py` | 261 | Iterating over subcomponents in search |
| `operations/search_ops.py` | 265 | `o.icalendar_instance` - Getting instance |
| `operations/search_ops.py` | 274 | `new_obj.icalendar_instance` - Getting instance |

### `obj.icalendar_component`

| File | Line | Context |
|------|------|---------|
| `calendarobjectresource.py` | 133-134 | Popping and adding UID |
| `calendarobjectresource.py` | 145 | `i = self.icalendar_component` - Assignment |
| `calendarobjectresource.py` | 170 | Adding organizer |
| `calendarobjectresource.py` | 278 | Getting UID from other object |
| `calendarobjectresource.py` | 289 | Getting RELATED-TO |
| `calendarobjectresource.py` | 305 | Adding RELATED-TO |
| `calendarobjectresource.py` | 341 | Getting RELATED-TO list |
| `calendarobjectresource.py` | 392 | Getting UID |
| `calendarobjectresource.py` | 508 | `i = self.icalendar_component` - Assignment |
| `calendarobjectresource.py` | 584 | `ievent = self.icalendar_component` - Assignment |
| `calendarobjectresource.py` | 896 | `ical_obj = self.icalendar_component` - Assignment |
| `calendarobjectresource.py` | 965 | Getting UID |
| `calendarobjectresource.py` | 992 | Getting UID |
| `calendarobjectresource.py` | 1017 | Checking for RECURRENCE-ID |
| `calendarobjectresource.py` | 1028-1029 | Getting component for modification |
| `calendarobjectresource.py` | 1070-1076 | Working with RECURRENCE-ID |
| `calendarobjectresource.py` | 1080-1083 | Working with SEQUENCE |
| `calendarobjectresource.py` | 1126 | Checking if component exists |
| `calendarobjectresource.py` | 1302 | `i = self.icalendar_component` - Assignment |
| `calendarobjectresource.py` | 1461 | `i = self.icalendar_component` - Assignment |
| `calendarobjectresource.py` | 1492 | `i = self.icalendar_component` - Assignment |
| `calendarobjectresource.py` | 1515 | Popping RRULE |
| `calendarobjectresource.py` | 1520 | `i = self.icalendar_component` - Assignment |
| `calendarobjectresource.py` | 1643 | Checking for RRULE |
| `calendarobjectresource.py` | 1652 | `i = self.icalendar_component` - Assignment |
| `calendarobjectresource.py` | 1660 | `i = self.icalendar_component` - Assignment |
| `calendarobjectresource.py` | 1674-1678 | Working with status and completed |
| `calendarobjectresource.py` | 1691 | `i = self.icalendar_component` - Assignment |
| `calendarobjectresource.py` | 1727 | `i = self.icalendar_component` - Assignment |

### `obj.vobject_instance`

| File | Line | Context |
|------|------|---------|
| `calendarobjectresource.py` | 821 | `self.vobject_instance` - Getting instance for ics() |
| `calendarobjectresource.py` | 843 | `self.vobject_instance` - Getting instance for wire_data |

---

## Test Code Usage (`tests/`)

### `obj.data`

| File | Line | Context |
|------|------|---------|
| `test_caldav_unit.py` | 1135 | Docstring about data returning unicode |
| `test_caldav_unit.py` | 1143-1157 | Multiple assertions on `my_event.data` type |
| `test_caldav_unit.py` | 1165 | `"new summary" in my_event.data` |
| `test_caldav_unit.py` | 1170, 1186 | `my_event.data.strip().split("\n")` |
| `test_async_integration.py` | 272, 289 | Checking data content |
| `test_sync_token_fallback.py` | 40, 43, 109 | Setting and checking data |
| `test_caldav.py` | 1164 | `assert objects[0].data` |
| `test_caldav.py` | 1472, 1506, 1557 | Checking data is None or not None |
| `test_caldav.py` | 1637 | `"foobar" in ... .data` |
| `test_caldav.py` | 2477 | `j1_.data == journals[0].data` |
| `test_caldav.py` | 2744-2788 | Multiple checks for DTSTART in data |
| `test_caldav.py` | 3235, 3273 | Setting `e.data` |
| `test_caldav.py` | 3331-3405 | Multiple `.data.count()` assertions |
| `test_operations_calendar.py` | 336, 351 | Checking data value |

### `obj.icalendar_instance`

| File | Line | Context |
|------|------|---------|
| `test_caldav_unit.py` | 1146 | `my_event.icalendar_instance` - Accessing |
| `test_caldav_unit.py` | 1166 | `icalobj = my_event.icalendar_instance` |
| `test_caldav_unit.py` | 1208, 1212 | `target.icalendar_instance.subcomponents` |
| `test_caldav_unit.py` | 1236-1267 | Multiple subcomponent manipulations |
| `test_caldav.py` | 1096, 1104 | `object_by_id.icalendar_instance` |
| `test_caldav.py` | 1490, 1627 | Modifying subcomponents |
| `test_caldav.py` | 2475-2476, 2909 | Getting icalendar_instance |
| `test_search.py` | 338, 368 | Iterating over subcomponents |

### `obj.icalendar_component`

| File | Line | Context |
|------|------|---------|
| `test_caldav_unit.py` | 1182 | `my_event.icalendar_component` |
| `test_caldav_unit.py` | 1195 | Setting `my_event.icalendar_component` |
| `test_caldav_unit.py` | 1211 | Setting component from icalendar.Todo |
| `test_caldav.py` | 1274 | Getting UID from component |
| `test_caldav.py` | 1352 | Checking UID in events |
| `test_caldav.py` | 1960-1988 | Multiple DTSTART comparisons |
| `test_caldav.py` | 1996, 1998, 2037 | Getting UID from component |
| `test_caldav.py` | 2254-2298 | Working with RELATED-TO |
| `test_caldav.py` | 2356-2457 | Multiple DUE/DTSTART assertions |
| `test_caldav.py` | 3417-3529 | Working with RECURRENCE-ID and modifying |
| `test_search.py` | 239 | Getting SUMMARY |
| `test_search.py` | 288 | Getting STATUS |
| `test_search.py` | 487, 566, 575, 619-620 | Various component accesses |

### `obj.vobject_instance`

| File | Line | Context |
|------|------|---------|
| `test_caldav_unit.py` | 1150 | `my_event.vobject_instance` - Accessing |
| `test_caldav_unit.py` | 1164 | Modifying `vobject_instance.vevent.summary.value` |
| `test_caldav_unit.py` | 1168, 1184 | Asserting on vobject values |
| `test_caldav_unit.py` | 1197 | Accessing vtodo.summary.value |
| `test_caldav.py` | 1732-1742 | Multiple vobject manipulations |
| `test_caldav.py` | 1937, 1945, 1953 | Getting vevent.summary.value |
| `test_caldav.py` | 2564-2578 | Getting vtodo.uid and priority |
| `test_caldav.py` | 2835-2839 | Comparing vobject properties |
| `test_caldav.py` | 3072-3084 | Comparing vevent.uid |
| `test_caldav.py` | 3141-3154 | Modifying and comparing summary |
| `test_caldav.py` | 3220-3221 | Comparing vevent.uid |
| `test_caldav.py` | 3269 | Checking vfreebusy existence |

### `obj.component` (alias for icalendar_component)

| File | Line | Context |
|------|------|---------|
| `test_caldav_unit.py` | 1273-1285 | Working with component.start/end/duration |
| `test_caldav.py` | 1416 | `foo.component["summary"]` |
| `test_caldav.py` | 2156 | `t3.component.pop("COMPLETED")` |
| `test_caldav.py` | 2337-2338 | Getting UID from component |
| `test_caldav.py` | 2431, 2436 | Getting UID from component |
| `test_caldav.py` | 2631, 2635 | Getting summary from component |

### `obj.instance` (alias for vobject_instance)

| File | Line | Context |
|------|------|---------|
| `tests/_test_absolute.py` | 30 | `vobj = event.instance` |

---

## Summary Statistics

| Property | Library Uses | Test Uses | Total |
|----------|-------------|-----------|-------|
| `data` | ~15 | ~40 | ~55 |
| `icalendar_instance` | ~25 | ~20 | ~45 |
| `icalendar_component` | ~45 | ~50 | ~95 |
| `vobject_instance` | ~2 | ~25 | ~27 |
| `component` (alias) | 0 | ~12 | ~12 |
| `instance` (alias) | 0 | ~1 | ~1 |

## Key Observations

1. **`icalendar_component`** is the most heavily used property, especially for accessing
   and modifying individual properties like UID, DTSTART, SUMMARY, etc.

2. **`data`** is used for:
   - Raw string manipulation and comparisons
   - Passing to add/save operations
   - Checking for specific content (e.g., `"BEGIN:VEVENT" in data`)

3. **`icalendar_instance`** is used for:
   - Accessing the full calendar object
   - Working with subcomponents (timezones, multiple events)
   - Getting/setting the METHOD property

4. **`vobject_instance`** has limited use in library code (only in `ics()` and `wire_data`),
   but is used extensively in tests for accessing nested properties like `vevent.summary.value`.

5. **Aliases** (`component`, `instance`) are rarely used - mostly in tests.

6. **Modification patterns**:
   - Setting `data` directly: `obj.data = "..."`
   - Modifying via icalendar: `obj.icalendar_component["SUMMARY"] = "..."`
   - Modifying via vobject: `obj.vobject_instance.vevent.summary.value = "..."`
   - These can conflict if not handled carefully (see issue #613)
