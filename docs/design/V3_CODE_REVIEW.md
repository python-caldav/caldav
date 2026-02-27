# v3.0 Comprehensive Code Review

**Date:** February 2026
**Reviewer:** Claude Opus 4.6 (AI-assisted review)
**Branch:** v3.0-dev (119 commits since v2.2.6)
**Scope:** All changes between tags v2.2.6 and HEAD

> **Status update (commit ff6db30):** All "Must Fix" and "Should Fix" items from §8 have been
> resolved. Remaining open items are v3.1+ and v4.0 work.
>
> **Status update (commit f7c51c9):** Recommendation 11 largely addressed — sync/async
> duplication reduced by ~177 lines across five files (see §5 for details).
>
> **Status update (commit ad042bb):** §1.1 issues 2, 3, 4 fixed (dead code deleted,
> CalendarInfo collision resolved, response/xml_parsers duplication reduced).

## Executive Summary

The v3.0 release is a major architectural refactoring introducing Sans-I/O separation, full async support, and comprehensive API modernization -- all while maintaining backward compatibility with v2.x. The scope is large: 159 files changed, ~25,900 lines added, ~4,500 removed.

**Overall assessment:** The architecture is well-designed and the codebase is in good shape for an alpha release. The Sans-I/O protocol layer is clean and testable. However, there are several bugs that should be fixed before a stable release, significant code duplication between sync/async paths (~650 lines), and some test coverage gaps.

**Key findings:**
- ~~3 bugs that will cause runtime errors~~ **fixed**
- ~~1 security concern (UUID1 leaks MAC address in calendar UIDs)~~ **fixed**
- ~~650 lines of sync/async duplication across domain objects~~ reduced to ~475 lines (commit f7c51c9)
- Test coverage gaps in discovery module and sync client unit tests
- ~~`breakpoint()` left in production code~~ **fixed**

---

## 1. Architecture Changes

### 1.1 Sans-I/O Protocol Layer (`caldav/protocol/`)

The protocol layer separates XML construction/parsing from I/O. This is the strongest part of the refactoring.

| File | Lines | Rating | Purpose |
|------|-------|--------|---------|
| `types.py` | ~~243~~ 221 | 9/10 | Frozen dataclasses: DAVRequest, DAVResponse, PropfindResult, CalendarQueryResult |
| `xml_builders.py` | ~~428~~ 346 | 7/10 | Pure functions building XML for PROPFIND, calendar-query, MKCALENDAR, etc. |
| `xml_parsers.py` | ~~455~~ 467 | 6/10 | Parse XML responses into typed results |
| `__init__.py` | 46 | 8/10 | Clean re-exports |

**Issues found:**

1. ~~**BUG: NameError in `xml_parsers.py:260`**~~ **FIXED** -- `parse_calendar_multiget_response()` was calling `parse_calendar_query_response()` (missing leading underscore). Fixed by adding the `_` prefix.

2. ~~**Dead code in `xml_builders.py`**~~ **FIXED** -- Deleted `_build_freebusy_query_body`, `_build_mkcol_body`, and `_to_utc_date_string` (the last was a never-wired duplicate of the real `_to_utc_date_string` in `elements/cdav.py`).

3. ~~**`CalendarInfo` name collision**~~ **FIXED** -- Deleted `CalendarInfo` from `protocol/types.py` (it was never instantiated); the canonical one in `operations/calendarset_ops.py` is unaffected.

4. ~~**Heavy duplication with `response.py`**~~ **PARTIALLY FIXED** -- Extracted `_normalize_href()` (Confluence %2540 fix + absolute-URL-to-path) into `xml_parsers.py`; `response.py._strip_to_multistatus` and `validate_status` now delegate to their `xml_parsers` counterparts. The propstat-loop duplication (`_find_objects_and_props` vs `_extract_properties`) is intentionally left: converging them requires changing the return type of the public `expand_simple_props()` API.

### 1.2 Operations Layer (`caldav/operations/`)

Pure functions for CalDAV business logic. Well-structured but has some issues.

| File | Lines | Rating | Purpose |
|------|-------|--------|---------|
| `base.py` | 189 | 8/10 | QuerySpec dataclass, URL helpers |
| `davobject_ops.py` | 293 | 7/10 | DAV property CRUD operations |
| `calendarobject_ops.py` | 531 | 6/10 | Calendar object lifecycle |
| `calendar_ops.py` | 261 | 7/10 | Search and sync-token operations |
| `calendarset_ops.py` | 245 | 7/10 | Calendar collection management |
| `principal_ops.py` | 162 | 7/10 | Principal discovery |
| `search_ops.py` | 445 | 6/10 | Advanced search query building |

**Issues found:**

1. ~~**SECURITY: UUID1 leaks MAC address (`calendarobject_ops.py:55`)**~~ **FIXED** -- Replaced `uuid.uuid1()` with `uuid.uuid4()`.

2. **`search_ops.py` mutates inputs (line 381-389)** -- `_build_search_xml_query` calls `setattr(searcher, flag, True)` on the passed-in searcher object. This violates the "pure functions" contract and causes side effects in callers.

3. ~~**MD5 in FIPS environments (`calendar_ops.py:132`)**~~ **FIXED** -- Added `usedforsecurity=False` to both `calendar_ops.py` and `collection.py`.

4. ~~**Duplicate URL quoting**~~ **FIXED** -- Extracted `_quote_uid()` helper in `calendarobject_ops.py`; `_generate_url`, `_find_id_and_path`, and `calendarobjectresource.CalendarObjectResource._generate_url` all now call it. `quote` import removed from `calendarobjectresource.py`.

### 1.3 Data State Management (`caldav/datastate.py`)

**Rating: 9/10** -- Excellent implementation of the State pattern for managing calendar data representations (raw string, icalendar, vobject). Smart optimizations for lazy switching between formats. Addresses issue #613.

### 1.4 Response Handling (`caldav/response.py`)

**Rating: 7/10** -- `BaseDAVResponse` provides shared XML parsing for sync/async clients. The main duplication with the protocol layer has been reduced; remaining open item is thread-unsafe mutable state.

**Issues found:**

1. ~~**Unguarded index access (line 169)**~~ **FIXED** -- Added `len(tree) > 0` guard before `tree[0]` access in `_strip_to_multistatus`, matching the equivalent guard in `xml_parsers.py`.

2. **Thread-unsafe** -- `self.objects`, `self.results`, `self._responses` are mutable instance state set during parsing. If a response object is shared between threads, results could be corrupt.

---

## 2. Async Support and Client Architecture

### 2.1 Base Client (`caldav/base_client.py`)

**Rating: 7/10** -- Good ABC extracting shared auth logic, URL handling, and factory functions.

**Issues:**
- `CalendarResult.__getattr__` (line 255) hides `None` calendars behind `AttributeError` -- confusing error message
- Missing `__aenter__`/`__aexit__` on `CalendarCollection`/`CalendarResult` -- async `get_calendars()` returns a plain list with no cleanup mechanism
- `get_davclient` and `get_calendars` factory functions are duplicated in `async_davclient.py`

### 2.2 Async Client (`caldav/async_davclient.py`)

**Rating: 6/10** -- Functional but has bugs, duplication, and architectural concerns.

**Issues found:**

1. ~~**BUG: `HTTPBearerAuth` incompatible with httpx**~~ **FIXED** -- Added `_HttpxBearerAuth(httpx.Auth)` class with `auth_flow` generator inside the httpx import block. `build_auth_object` now uses it on the httpx path and falls back to `HTTPBearerAuth` for niquests.

2. ~~**BUG: Missing `url.unauth()` call**~~ **FIXED** -- Added `self.url = self.url.unauth()` after credentials are extracted from the URL, matching the sync client behaviour.

3. ~~**Rate-limit handling asymmetry**~~ **FIXED** -- `AsyncDAVClient.request()` now has `rate_limit_time_slept: float = 0`, the same adaptive backoff loop as the sync client (each retry adds half the already-slept time), and the same features-based auto-detect of `rate_limit_handle`. Retries recursively via `self.request()` instead of calling `_async_request()` directly.

4. **`_auto_url` blocks the event loop** -- RFC6764 discovery performs synchronous DNS lookups and HTTP requests inside `AsyncDAVClient.__init__()`, which is called from `async get_davclient()`. This blocks the event loop.

5. **Sync import dependency** -- `async_davclient.py:198` imports from `caldav.davclient`, pulling the sync HTTP stack into async contexts. `_auto_url` should live in `caldav/config.py` or `caldav/discovery.py`.

6. **Password encoding asymmetry** -- Sync client encodes password to bytes eagerly (`davclient.py:329`), async does not. This creates different code paths for auth building.

7. **Response parsing boilerplate** -- The pattern `if response.status in (200, 207) and response._raw: ...` is repeated in ~5 methods. Should be a helper.


### 2.3 Sync Client (`caldav/davclient.py`)

**Rating: 6/10** -- Mature but has accumulated technical debt.

**Issues found:**

1. ~~**Bare `except:` clauses (lines 367, 679)**~~ **FIXED** -- Narrowed to `except TypeError` for the test teardown fallback (the expected exception when `teardown()` takes an argument), and `except Exception` for `check_dav_support` (which intentionally catches anything from principal lookup and falls back to root URL).

2. ~~**Rate-limit auto-detect always enabled**~~ **FIXED** -- `is_supported('rate-limit', dict)` returns `{'enable': False}` (a truthy non-empty dict) for any unconfigured client; the `if rate_limit:` check was incorrectly auto-enabling rate limiting for everyone. Changed to `if rate_limit and rate_limit.get('enable'):`. Also fixed a `TypeError` crash when `rate_limit_max_sleep is None` and the `>` comparison was attempted.

3. ~~**`NotImplementedError` for auth failures (line 996)**~~ **ALREADY FIXED** -- Code already calls `self._raise_authorization_error()` which raises `AuthorizationError`. Issue was stale at time of review.

4. **Type annotation gaps** -- Multiple `headers: Mapping[str, str] = None` parameters where `None` is not in the union type.

5. **`propfind` API divergence** -- Sync version (line 754) takes `props=None` which can be either XML string or property list. Async version (line 512) has separate `body` and `props` parameters.

### 2.4 Lazy Imports (`caldav/__init__.py`)

**Rating: 8/10** -- Clean PEP 562 implementation. `import caldav` is now fast.

Minor: `_LAZY_SUBMODULES` could be `frozenset`. No `DAVResponse` export (probably intentional).

### 2.5 Async Entry Point (`caldav/aio.py`)

**Rating: 7/10** -- Clean re-export module with backward-compat `Async*` aliases.

Issue: No `get_calendars`/`get_calendar` re-export -- users must import from `async_davclient` directly.

### 2.6 Auth Utilities (`caldav/lib/auth.py`)

**Rating: 8/10** -- Clean, pure functions with good type annotations.

Minor: `WWW-Authenticate` parsing (line 31) splits on commas, which fails for headers with commas inside quoted strings (e.g., Bearer challenges with `error_description`).

---

## 3. Domain Object Changes

### 3.1 DAVObject (`caldav/davobject.py`)

**Rating: 7/10** -- Solid dual-mode foundation.

**Issues:**
1. ~~**Production-unsafe assert (`line 99`)**~~ **FIXED** -- Replaced `assert " " not in str(self.url)` with an explicit `ValueError` (also fixed the `url=None` case that the assert silently passed).
2. **Return type lies for async** -- Methods like `get_property()`, `get_properties()`, `delete()` return coroutines when used with async clients, but annotations say `str | None`, `dict`, `None`.
3. **`set_properties` regression** -- Changed from per-property status checking to HTTP status-only checking, losing ability to detect partial PROPPATCH failures.

### 3.2 Collection (`caldav/collection.py`)

**Rating: 6/10** -- Functional but at 2,054 lines is the largest file and could benefit from extraction.

**Issues:**
1. **Missing deprecation warnings** -- `calendars()`, `events()`, `todos()` etc. have docstring notes but no `warnings.warn()` calls (unlike `date_search` and `davobject.name` which do emit). *Comment:* This is intentional.  Those are "core features" that was suddenly changed between v2 and v3 - we want people to upgrade to v3 without getting a lot of deprecation warnings thrown in their face.  Those warnings will be added in v4.
2. ~~**`_generate_fake_sync_token` uses MD5 (line 1655)**~~ **FIXED** -- Added `usedforsecurity=False`.
3. **`Principal._async_get_property` overrides parent (line 352)** with incompatible implementation.

### 3.3 CalendarObjectResource (`caldav/calendarobjectresource.py`)

**Rating: 7/10** -- Good DataState integration but large (1,919 lines).

**Issues:**
1. ~~**BUG: `_set_deprecated_vobject_instance` (line 1248)**~~ **FIXED** -- Was calling `_get_vobject_instance(inst)` (getter, wrong number of arguments); fixed to call `_set_vobject_instance(inst)`.
2. **`id` setter is a no-op (line 123)** -- Intentional design: UID lives in the iCalendar data, not as a separate field. The setter exists to satisfy the parent class `__init__` without side effects; removing it would cause silent writes that don't take effect. Not a bug.
3. **`_async_load` missing multiget fallback** -- Sync `load()` has `load_by_multiget()` fallback, async does not.
4. **Dual data model risk** -- Old `_data`/`_vobject_instance`/`_icalendar_instance` coexist with new `_state`. Manual sync at lines 1206, 1279 could desynchronize.

### 3.4 Search (`caldav/search.py`)

**Rating: 7/10** -- Excellent generator-based Sans-I/O pattern.

**Issues:**
1. **Generator error handling (lines 516-545)** -- `except StopIteration: return []` silently swallows premature generator exits, masking bugs.
2. **Double-loading (lines 448-467)** -- Objects loaded twice as "partial workaround for #201" with `except Exception: pass` masking errors.
3. **`TypesFactory` shadowing (line 25)** -- Class shadowed by instance at module level.

---

## 4. Configuration and Compatibility

### 4.1 Config System (`caldav/config.py`)

**Rating: 7/10** -- Good centralized configuration with clear priority chain.

**Issues:**
1. **`config_section` name shadowing (line 329)** -- Parameter shadows module-level function.
2. **`_extract_conn_params_from_section` rejects URL-less configs (line 395)** -- Returns `None` for sections without URL, conflicting with feature-based auto-connect.
3. **`read_config` inconsistency** -- Returns `None` when searching defaults (line 91) but `{}` when explicit file not found (line 116).

### 4.2 Compatibility Hints (`caldav/compatibility_hints.py`)

**Rating: 7/10** -- Comprehensive server database.

**Issues:**
1. ~~**`breakpoint()` in production code (line 443)**~~ **FIXED** -- Replaced with `raise ValueError(f"Unknown feature type: {feature_type!r}")`.
2. **`incompatibility_description` dict still present (lines 660-778)** -- Marked "TO BE REMOVED" but still referenced by `test_caldav.py` (lines 722, 727, 754). Cannot be deleted until the test code is updated.
3. **`# fmt: off` for entire 1,366-line file** -- Should scope it to just the dict definitions.

---

## 5. Code Duplication Analysis

### 5.1 Sync/Async Client Duplication (~30 lines remaining)

| Code Section | davclient.py | async_davclient.py | Similarity | Status |
|---|---|---|---|---|
| `search_principals` | 376-435 | 1107-1168 | ~95% (copy-paste + await) | **FIXED** — build/parse hoisted to `BaseDAVClient` |
| `_get_calendar_home_set` | 548-568 | 974-994 | ~95% | open |
| `get_events` | 570-597 | 996-1023 | ~95% | **FIXED** — hoisted to `BaseDAVClient` |
| `get_todos` | 599-613 | 1025-1039 | ~95% | **FIXED** — hoisted to `BaseDAVClient` |
| `propfind` response parsing | 280-320 | 750-790 | ~90% | open |
| Auth type extraction | 180-210 | 420-450 | ~100% | already in `BaseDAVClient` |
| Factory functions | 1015-1078 | 1312-1431 | ~80% | open |

### 5.2 Domain Object Async/Sync Duplication (~445 lines remaining)

| File | Duplicated pairs | Approx. lines | Notes |
|---|---|---|---|
| davobject.py | 6 method pairs | ~~180~~ ~140 | `_build_xml_body` / `_build_propfind_root` extracted; `_query`/`_async_query` and `set_properties`/`_async_set_properties` shortened; `_query_properties`/`_async_query_properties` each now 1 line |
| collection.py | 8 method pairs | ~~250~~ ~215 | `CalendarSet.get_calendars` sync migrated to protocol layer; shared `_calendars_from_results` eliminates 30+ lines of duplication |
| calendarobjectresource.py | 4 method pairs | ~100 | open |
| search.py | 2 method pairs | ~50 | open |

### 5.3 Protocol/Response Duplication (partially resolved)

`response.py` and `protocol/xml_parsers.py` originally shared five pieces of nearly identical logic. Three have been consolidated:

| Piece | Status |
|---|---|
| Multistatus stripping | **FIXED** — `response._strip_to_multistatus` now delegates to `xml_parsers._strip_to_multistatus` |
| Status validation | **FIXED** — `response.validate_status` now delegates to `xml_parsers._validate_status` |
| `%2540` Confluence workaround + absolute-URL-to-path | **FIXED** — extracted as `xml_parsers._normalize_href`; called from both `_parse_response_element` and `response._parse_response` |
| Response element parsing (`_parse_response` vs `_parse_response_element`) | open — too much divergence in error handling to merge without risk |
| Propstat loops (`_find_objects_and_props` vs `_extract_properties`) | open — `_find_objects_and_props` must return raw `_Element` objects for `expand_simple_props()`; merging requires a public API change |

---

## 6. Test Coverage Assessment

| Module | Coverage | Rating | Notes |
|---|---|---|---|
| `caldav/protocol/` | Excellent | 9/10 | Pure unit tests in test_protocol.py |
| `caldav/operations/` | Excellent | 9/10 | 6 dedicated test files |
| `caldav/async_davclient.py` | Good | 8/10 | test_async_davclient.py; adaptive rate-limit tests added |
| `caldav/datastate.py` | Good | 7/10 | Covered through calendarobject tests |
| `caldav/search.py` | Good | 7/10 | test_search.py + integration tests |
| `caldav/davclient.py` | Low | 5/10 | Rate-limit unit tests added to test_caldav_unit.py; rest still integration-only |
| `caldav/collection.py` | Moderate | 6/10 | Integration tests cover most paths |
| `caldav/discovery.py` | None | 0/10 | Zero dedicated tests |
| `caldav/config.py` | Poor | 3/10 | Module docstring says "test coverage is poor" |

### Notable Test Gaps

- **Error handling scenarios** -- No tests for malformed XML, network timeouts, partial responses
- **Sync DAVClient unit tests** -- No `test_davclient.py` mirroring `test_async_davclient.py`
- **Discovery module** -- DNS-based discovery has zero test coverage despite security implications
- **Deprecation warnings** -- No tests verify that deprecated methods emit warnings

---

## 7. Bugs Summary (Ordered by Severity)

| # | Severity | Location | Description | Status |
|---|---|---|---|---|
| 1 | HIGH | `xml_parsers.py:260` | NameError: calls `parse_calendar_query_response` (missing underscore) | **FIXED** |
| 2 | HIGH | `async_davclient.py` | `HTTPBearerAuth` incompatible with httpx -- bearer auth broken on httpx path | **FIXED** |
| 3 | MEDIUM | `calendarobjectresource.py:1248` | `_set_deprecated_vobject_instance` passes arg to no-arg getter | **FIXED** |
| 4 | MEDIUM | `compatibility_hints.py:443` | `breakpoint()` in production code path | **FIXED** |
| 5 | MEDIUM | `async_davclient.py` | Missing `url.unauth()` -- credential leak in logs | **FIXED** |
| 6 | MEDIUM | `calendarobject_ops.py:55` | UUID1 leaks MAC address in calendar UIDs | **FIXED** |
| 7 | LOW | `davclient.py:367,679` | Bare `except:` catches SystemExit/KeyboardInterrupt | **FIXED** |
| 8 | LOW | `response.py:169` | Unguarded `tree[0]` access | **FIXED** |
| 9 | LOW | `davobject.py:99` | Production-unsafe `assert` for URL validation | **FIXED** |

---

## 8. Recommendations

### For v3.0 Stable Release (Must Fix) -- ALL DONE ✓

1. ~~Fix the NameError in `xml_parsers.py:260` (add underscore)~~
2. ~~Remove `breakpoint()` from `compatibility_hints.py:443`~~
3. ~~Fix `_set_deprecated_vobject_instance` to call setter not getter~~
4. ~~Replace `uuid.uuid1()` with `uuid.uuid4()` in `calendarobject_ops.py:55`~~
5. ~~Fix bare `except:` to narrower exception types in `davclient.py`~~
6. ~~Add `url.unauth()` call to `AsyncDAVClient.__init__`~~

### For v3.0 Stable Release (Should Fix) -- ALL DONE ✓

7. ~~Fix `HTTPBearerAuth` for httpx path~~
8. ~~Add guard for `tree[0]` access in `response.py:169`~~
9. ~~Replace production `assert` with proper validation in `davobject.py:99`~~
10. ~~Add `usedforsecurity=False` to MD5 calls for FIPS compliance~~

### For v3.1+

11. ~~Reduce sync/async client duplication (`search_principals`, `get_events`, `get_todos`)~~ **DONE** — all three hoisted to `BaseDAVClient`; XML build/parse extracted to `_build_principal_search_query` / `_parse_principal_search_response`; `_build_xml_body` / `_build_propfind_root` helpers added to `DAVObject`; `CalendarSet.get_calendars` sync path migrated to protocol layer
12. ~~Consolidate `response.py` and `protocol/xml_parsers.py` duplication~~ **PARTIALLY DONE** — three of five duplicated pieces consolidated (see §5.3); response-element parsing and propstat loops remain
13. Add sync DAVClient unit tests mirroring async test structure
14. Add discovery module tests
15. Add missing `warnings.warn()` to all deprecated methods
16. ~~Remove dead code in `xml_builders.py`~~ **DONE** — deleted `_build_freebusy_query_body`, `_build_mkcol_body`, `_to_utc_date_string`
17. Move `_auto_url` from `davclient.py` to shared module (also fixes event-loop blocking in async client)
18. Make `search_ops._build_search_xml_query` not mutate its input
19. Fix `NotImplementedError` for auth failures in `davclient.py` -- raise `AuthorizationError` instead
20. Fix `_auto_url` blocking the event loop in `AsyncDAVClient.__init__`

### For v4.0

21. Address implicit data conversion side effects (issue #613)
22. Consider splitting `collection.py` (2,054 lines) and `calendarobjectresource.py` (1,919 lines)
23. Fix return type annotations for async-capable methods (use `@overload`)
24. Remove `incompatibility_description` dict from compatibility_hints.py

---

## Appendix A: New Files Added

| File | Lines | Purpose |
|------|-------|---------|
| `caldav/async_davclient.py` | 1,431 | Async HTTP client |
| `caldav/base_client.py` | 480 | Shared client ABC |
| `caldav/response.py` | ~~390~~ 374 | Shared response parsing |
| `caldav/datastate.py` | 246 | Data representation state machine |
| `caldav/aio.py` | 93 | Async entry point |
| `caldav/lib/auth.py` | 69 | Shared auth utilities |
| `caldav/protocol/types.py` | ~~243~~ 221 | Request/response dataclasses |
| `caldav/protocol/xml_builders.py` | ~~428~~ 346 | XML construction |
| `caldav/protocol/xml_parsers.py` | ~~455~~ 467 | XML parsing |
| `caldav/operations/base.py` | 189 | Query specifications |
| `caldav/operations/search_ops.py` | 445 | Search query building |
| `caldav/operations/calendarobject_ops.py` | 531 | Calendar object ops |
| `caldav/operations/davobject_ops.py` | 293 | DAV object ops |
| `caldav/operations/calendar_ops.py` | 261 | Calendar search/sync ops |
| `caldav/operations/calendarset_ops.py` | 245 | Calendar set ops |
| `caldav/operations/principal_ops.py` | 162 | Principal ops |

## Appendix B: File Size Concerns

| File | Lines | Recommendation |
|------|-------|---------------|
| `collection.py` | 2,054 | Extract SynchronizableCalendarObjectCollection, ScheduleMailbox |
| `calendarobjectresource.py` | 1,919 | Extract Todo.complete() and recurring task logic |
| `async_davclient.py` | 1,431 | Reduce by moving shared code to operations layer |
| `compatibility_hints.py` | 1,366 | Consider YAML/JSON for server profiles |
| `davclient.py` | 1,089 | Reduce by moving shared code to operations layer |

## Appendix C: Test Files Added

| File | Lines | Purpose |
|------|-------|---------|
| `test_async_davclient.py` | 821 | Async client unit tests |
| `test_async_integration.py` | 466 | Async integration tests |
| `test_operations_calendarobject.py` | 529 | CalendarObject ops tests |
| `test_protocol.py` | 319 | Protocol layer tests |
| `test_operations_calendarset.py` | 277 | CalendarSet ops tests |
| `test_operations_davobject.py` | 288 | DAVObject ops tests |
| `test_operations_principal.py` | 242 | Principal ops tests |
| `test_operations_calendar.py` | 329 | Calendar ops tests |
| `test_operations_base.py` | 192 | Base ops tests |
| `test_lazy_import.py` | 141 | Lazy import verification |
