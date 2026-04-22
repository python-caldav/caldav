# Audit: `operations/` and `protocol/` directories

**Date:** 2026-04-22
**Context:** Both directories were created during an attempted sans-IO refactoring
that was never completed. This document assesses what is dead, what is duplicated,
and what should happen next.

---

## `caldav/operations/` — ~85% dead code

### What is there

| File | Lines | Status |
|---|---|---|
| `base.py` | 189 | ~30 active (`_normalize_href`), rest test-only |
| `davobject_ops.py` | 293 | Entirely dead in production |
| `calendarobject_ops.py` | 540 | ~10 active (`_quote_uid`), rest dead/duplicate |
| `principal_ops.py` | 162 | ~60 active (`_extract_calendar_home_set_from_results`) |
| `calendarset_ops.py` | 245 | ~40 active (`_extract_calendars_from_propfind_results`) |
| `calendar_ops.py` | 261 | Entirely dead in production |
| `search_ops.py` | 453 | ~180 active, ~270 dead |
| `__init__.py` | 62 | Re-exports unused dataclasses |
| **Total** | **2,205** | **~340 active, ~1,860 dead** |

### The handful of functions that are actually used

| Function | Current home | Natural home |
|---|---|---|
| `_quote_uid` | `calendarobject_ops.py` | `calendarobjectresource.py` (already imported there) |
| `_extract_calendars_from_propfind_results` | `calendarset_ops.py` | `collection.py` (called from `_calendars_from_results`) |
| `_extract_calendar_home_set_from_results` | `principal_ops.py` | `davclient.py` / `async_davclient.py` |
| `_normalize_href` | `base.py` | `response.py` (already imported there; also duplicated in `protocol/xml_parsers.py`) |
| `_build_search_xml_query` | `search_ops.py` | `search.py` (reasonable as module-level helper) |
| `_filter_search_results` | `search_ops.py` | `search.py` |
| `_collation_to_caldav` | `search_ops.py` | `search.py` |

### What is dead

- `davobject_ops.py` (293 lines): no production callers; logic is reimplemented in the
  classes. Tests exercise the functions in isolation, but the main codebase never
  calls them.
- `calendar_ops.py` (261 lines): no production callers. `_generate_fake_sync_token`
  is duplicated verbatim in `Collection._generate_fake_sync_token()` in `collection.py`,
  which is what production code calls.
- ~530 lines of `calendarobject_ops.py`: duplicates class methods in
  `calendarobjectresource.py`. `_get_duration`, `_set_duration`, `_find_id_and_path`,
  `_calculate_next_recurrence`, `_mark_task_completed`, etc. all have counterparts
  in the class that are the ones actually called.
- ~270 lines of `search_ops.py`: `_determine_post_filter_needed`,
  `_should_remove_category_filter`, `_get_explicit_contains_properties`,
  `_needs_pending_todo_multi_search`, `SearchStrategy` — never called from anywhere,
  not even from tests.
- `QuerySpec`, `PropertyData`, `ChildrenQuery`, `ChildData`, `PropertiesResult`,
  `CalendarObjectData`, `PrincipalData`, `CalendarObjectInfo` exported from
  `__init__.py` — no production callers.
- 6 `test_operations_*.py` test files (2,176 lines total): they only exercise the dead
  functions. Actual behavior is covered by integration tests against the classes.

### What happened

The intended pattern was: extract logic from classes into pure functions → test in
isolation → re-wire classes to call functions. The extraction happened; the re-wiring
did not. So we now have two implementations of the same logic: the original class
methods (which production uses) and the extracted functions (which only unit tests use).

### Recommendation: delete the directory

1. Move the 7 live functions into their natural homes (listed above).
2. Delete `caldav/operations/` entirely.
3. Delete all `tests/test_operations_*.py` files.

The logic belongs in the classes, not as bare functions. Whether the future direction
is sans-IO or async-first-with-generated-sync, the `operations/` approach adds a
layer of indirection without being the authoritative implementation.

---

## `caldav/protocol/` — foundation of async client, but with duplication

### What is there

| File | Lines | Notes |
|---|---|---|
| `types.py` | 221 | `PropfindResult`, `CalendarQueryResult`, etc. |
| `xml_builders.py` | 346 | XML request body builders |
| `xml_parsers.py` | 468 | XML response parsers + 3 utility functions |
| `__init__.py` | 44 | Re-exports `types.py` |
| **Total** | **1,079** | |

### Who uses it

`async_davclient.py` is the primary consumer — it uses the builders for all its HTTP
request bodies and the parsers to populate `response.results` with typed objects.

`davclient.py` (sync) barely touches it:
- `_build_propfind_body` — used in one code path inside `propfind()`
- `_parse_propfind_response` — used in the same code path (late import, conditional)

`response.py` imports three utility functions from `xml_parsers.py`:
- `_normalize_href` — used when parsing `<href>` elements
- `_validate_status` — used when parsing status strings
- `_strip_to_multistatus` — delegated to from `BaseDAVResponse._strip_to_multistatus()`

### The duplication problem

`protocol/xml_builders.py` builds XML bodies from property name strings
(e.g. `"DAV:displayname"`). `davobject.py` builds them from element classes
(`dav.DisplayName()`). These are parallel implementations at different abstraction
levels. `davclient.py` uses the element-class approach; `async_davclient.py` uses the
string approach. They diverge and are not interchangeable.

`_normalize_href` exists in both `protocol/xml_parsers.py` and
`operations/base.py` with near-identical logic.

`response.py` is the stateful response object, but it delegates three internal
operations upward to `protocol/xml_parsers.py`, creating an inverted dependency:
the higher-level response object depends on the lower-level protocol module for
what are essentially private helpers.

### What is dead in `xml_builders.py`

- `_build_proppatch_body` — not called from `davclient.py` or `async_davclient.py`
- `_build_mkcalendar_body` — not called from anywhere
- `_prop_name_to_element` — not called from anywhere (only used internally by
  `_build_proppatch_body`)

### Recommendation

The right move depends on the architectural direction:

**Option A — Dissolve back into consumers (aligns with stated preference for
stateful response objects):**

1. Move `_normalize_href`, `_validate_status`, `_strip_to_multistatus` into
   `response.py` directly — that is where they are used.
2. Move `xml_builders.py` and `xml_parsers.py` into `async_davclient.py` as its
   private implementation (or a sibling `_async_davclient_xml.py`). They are
   already exclusively its implementation detail.
3. Inline the `types.py` dataclasses into `async_davclient.py`.
4. Remove `davclient.py`'s single use of `_build_propfind_body` /
   `_parse_propfind_response` — it should use the same XML-building path as
   everything else (via `davobject.py`'s element classes).
5. Delete `caldav/protocol/`.

**Option B — Keep as async client internals, make the boundary honest:**

Rename the module to `caldav/_async_xml.py` or similar, drop the "protocol" framing,
and make it explicit that this is the async client's XML implementation, not a
shared abstraction. Remove the dead builder functions. This is a smaller change that
preserves the separation without the false promise of a sans-IO layer.

Either way: delete the three dead builder functions (`_build_proppatch_body`,
`_build_mkcalendar_body`, `_prop_name_to_element`) immediately.

---

## Summary

| Directory | Total lines | Live in production | Recommendation |
|---|---|---|---|
| `operations/` | 2,205 | ~340 (7 functions) | Delete; inline live functions into classes |
| `protocol/` | 1,079 | ~800 | Keep as async client internals, or dissolve into consumers |
| `tests/test_operations_*.py` | 2,176 | 0 (tests dead code only) | Delete with `operations/` |
| `tests/test_protocol.py` | 319 | active | Keep (tests `async_davclient.py` behavior) |
