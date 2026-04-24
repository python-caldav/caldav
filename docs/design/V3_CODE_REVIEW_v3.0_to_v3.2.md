# Code Review: v3.0.0 → v3.2 (current)

**Date:** April 2026
**Reviewer:** Claude Sonnet 4.6 (AI-assisted review)
**Branch:** v3.2-preparations (71 commits since tag v3.0.0)
**Scope:** `git diff v3.0.0..HEAD` — 120 files, ~10 600 insertions, ~8 100 deletions

---

## Overview

The major themes of this release cycle are:

1. **Async (dual-mode) expansion** — many more methods made async-aware via the
   `is_async_client` branch + `_async_*` companion pattern
2. **Architecture consolidation** — the `operations/` and `protocol/` sub-packages were
   deleted; their code was absorbed into `base_client.py`, `response.py`, `search.py`,
   and `collection.py`
3. **RFC 6638 scheduling support** — freebusy, invite accept/decline/tentative, organizer
   handling, Schedule-Tag / ETag conditional PUT
4. **New user-facing APIs** — `get_icalendar_component()`, `edit_icalendar_component()`,
   `etag` / `schedule_tag` properties, `get_calendars()` multi-server support
5. **Bug fixes and compatibility** — OX App Suite, Nextcloud 33, numerous async fixes,
   `get_supported_components()`, UUID v1→v4

---

## Architecture

### Positive: `operations/` and `protocol/` removal

Merging ~2 000 lines of thin wrappers back into the main classes was the right call.
The indirection added complexity without benefit.

### Concern: `response.py` is now a God-module

**Status:** Partially fixes, code duplication have been dealt with and squashd together with earlier work on this.

`response.py` grew from ~200 to ~900 lines and now contains result dataclasses, six XML
parse functions, *and* the `DAVResponse` class with its own parse path.  The file itself
notes:

```python
## TODO: _parse_response_element is a simplified version of DAVResponse._parse_response
## ... both of these could be unified into a single method.
```

There are now **two separate XML parse pipelines** that can diverge:

- Module-level `_parse_propfind_response()` used by the protocol-style methods
  (`parse_propfind()`, `parse_calendar_query()`)
- `DAVResponse._parse_response()` used by the legacy `_find_objects_and_props()` /
  `expand_simple_props()`

This is a technical-debt trap.  The TODO comment acknowledges it but there is no target
version.

### Concern: `base_client.py` XML builders are `@staticmethod`s on a class

**Status:** Ignored as for now.

The `_build_propfind_body`, `_build_calendar_query_body`, etc. methods are `@staticmethod`
on `BaseDAVClient`.  They do not use `self` or `cls`; they could be module-level functions.
Placing them on the class forces any caller to either hold a client reference or write
`BaseDAVClient._build_*()`.

---

## The Dual-Mode Async Pattern

### Positive

The "branch early, return coroutine, companion `_async_*` method" pattern is consistent
across the codebase.  The `_value_or_coroutine` hook for cache hits is a clever trick.

### Major concern: `is_async_client` uses a string class-name comparison

**Status:** Fixed

```python
# davobject.py:110
return type(self.client).__name__ == "AsyncDAVClient"
```

This is a string comparison against a class name.  If `AsyncDAVClient` is subclassed or
renamed, this silently falls back to sync mode with no error.  The existing TODO in
`docs/source/async.rst` (and `ASYNC_DESIGN_CRITIQUE.md`) calls this out.  At minimum this
should use `isinstance()` or a class-level flag attribute.

### Concern: dual-mode return types are misleading to type checkers

**Status:** Ignored as for now.

Methods like `get_calendars()` are typed as `list[Calendar] | Coroutine[...]`.  In
practice sync callers get a list and async callers get a coroutine — but nothing in the
type system enforces that the caller actually awaits it.  A sync caller who accidentally
uses an async client gets a coroutine silently dropped on the floor.  The pattern is
pragmatically reasonable for v3.x, but the design docs are correct that this needs a
proper solution in v4.0.

### Potential bug: `freebusy_request()` passes an unawaited coroutine

**Status:** **Needs attention in 3.2.1**

```python
# collection.py
outbox = self.schedule_outbox()   # returns a coroutine in async mode, not an outbox
caldavobj = FreeBusy(...)
...
if self.is_async_client:
    return self._async_freebusy_request(outbox, caldavobj)
```

`outbox` is an unawaited coroutine here; `_async_freebusy_request` does
`outbox = await outbox` to materialise it.  That works, but it is non-obvious — a
variable named `outbox` holds a coroutine.  The inline comment acknowledges this is messy.

### Bug: `_async_complete` with RRULE silently drops `save()`

**Status:** **Needs attention in 3.2.1**

```python
# calendarobjectresource.py — comment in _async_complete:
# _complete_recurring_* methods are sync-only for now; they internally
# call self.save() which would return an unawaited coroutine in async mode.
```

If a user calls `complete()` on a recurring VTODO with an async client the completion is
computed but never written to the server.  This is a **silent data-loss bug**.  It should
be a `raise NotImplementedError(...)` with a clear message rather than a silent no-op.

---

## RFC 6638 Scheduling — New Feature

### Positive

- `add_organizer()` now accepts an explicit `organizer` argument and properly replaces
  existing ORGANIZER fields (`_set_organizer` refactor is clean).
- Schedule-Tag / ETag conditional PUT in `_put()` follows RFC 6638 correctly.
- `accept_invite()` / `decline_invite()` / `tentatively_accept_invite()` handles both
  auto-scheduling and non-auto-scheduling servers.

### Concern: bare `assert` in `_parse_scheduling_response_objects()`

**Status:** Fixed

```python
assert self.tree.tag == cdav.ScheduleResponse.tag
assert response.tag == cdav.Response.tag
```

These are in a production code path.  Python's `-O` flag strips `assert` statements.
Use `error.assert_()` or explicit `if … raise` like the rest of the codebase does.

### Concern: repeated ETag / Schedule-Tag update block

**Status:** Should be fixed, perhaps in 3.2.1.  This code was hand-written by the guy who hates duplicated code.

```python
## consider refactoring - this is repeated many places now
if "Etag" in r.headers:
    self.props[dav.GetEtag.tag] = r.headers["Etag"]
if "Schedule-Tag" in r.headers:
    self.props[cdav.ScheduleTag.tag] = r.headers["Schedule-Tag"]
```

This block appears at least four times in `calendarobjectresource.py`.  Extract to a
`_update_tags_from_response(r)` helper method.

---

## `response.py` — New Parse Functions

### Positive

`_normalize_href`, `_validate_status`, `_status_to_code` are cleaner than what they
replaced.  The dataclasses (`PropfindResult`, `CalendarQueryResult`, etc.) are a good
model for structured parse results.

### Concern: `_element_to_value` fallback returns a raw lxml element

**Status:** Ignored as for now.  Should consider this.

```python
# end of _element_to_value()
return elem   # returns an lxml _Element as a "value"
```

Returning a raw `_Element` as a property value is surprising and will confuse callers
expecting strings or lists of strings.  This path should at minimum log a warning.

### Concern: `_strip_to_multistatus` return type is opaque

**Status:** Ignored as for now.  Should consider this.

```python
def _strip_to_multistatus(tree: _Element) -> "_Element | list[_Element]":
```

Returning either a single element or a list works because iterating an `_Element` iterates
its children — but the two cases iterate differently, and the type hint is misleading.  A
brief comment explaining why both types are iterable in the same `for` loop would help
future maintainers.

---

## `davobject.py` — Refactoring

### Positive

- `_async_get_properties` now delegates to `_post_get_properties()`, removing ~30 lines of
  duplicated logic.
- `get_property()` cache hit goes through `_value_or_coroutine`, correctly returning a
  coroutine in async mode.

### Concern: `_resolve_properties` dead-code path

**Status:** Ignored as for now.  Should consider this.

```python
error.assert_(False)
return {}   # newly added
```

`return {}` after `error.assert_(False)` is unreachable in debug mode (the assert raises)
but reached in production mode (assert is a no-op).  The intent is apparently "return a
safe fallback dict".  The `return {}` should be the actual fallback; `error.assert_(False)`
should be `log.warning(...)` instead.  As written, production mode silently returns an
empty dict while debug mode raises — the opposite of what you want.

---

## `config.py` — Test Server Registry

### Positive

Priority-based server ordering with `_collect_test_servers` is cleaner than the previous
if-chain.

### Minor: `_ConfiguredServer.start()` is a no-op, `is_accessible()` ignores reachability

**Status:** Ignored as for now.  Should consider this.

```python
def start(self) -> None:
    self._started = True  # external — assumed already running
```

`is_accessible()` always returns `True` if `url` is non-empty, even if the server is
actually unreachable.  Acceptable for external servers (the user configured them), but
worth documenting as a known limitation.

---

## `collection.py` — Helper Functions

### Positive

`_extract_calendars_from_propfind_results`, `_is_calendar_resource`, `_quote_url_path`,
etc. brought in from `operations/calendarset_ops.py` are now module-level helpers in
`collection.py`, which is logical.

### Concern: `_extract_calendar_id_from_url` swallows all exceptions

**Status:** Ignored as for now.  Should consider this.

```python
except Exception:
    log.error(f"Calendar has unexpected url {url}")
return None
```

Returns `None` on any URL parsing error, causing the calendar to be silently skipped
(`if not cal_id: continue`).  A user with a server that returns pathological URLs gets no
calendar list and no actionable error message.  Log the exception itself, or re-raise with
context.

---

## Minor / Style

| Item | Assessment |
|---|---|
| `except:` → `except KeyError:` in `error.py` | Good |
| `super(ClassName, self).__init__()` → `super().__init__()` throughout | Good cleanup |
| `Optional[X]` → `X \| None` throughout | Correct for Python ≥ 3.10 |
| `isinstance(obj, (str, bytes))` → `isinstance(obj, str \| bytes)` | Correct |
| `uuid.uuid1()` → `uuid.uuid4()` in `freebusy_request` | Correct; v1 leaks MAC address |
| `## double-hash` vs `# single-hash` comment style used inconsistently | Cosmetic; worth picking one |
| Unused import `niquests` removed from `async_davclient.py` | Good |

---

## Test Coverage Notes

- RFC 6638 scheduling is well-covered by the new integration test framework.
- `_async_complete` with recurring events (the silent-save bug) has **no async test
  coverage** for the RRULE path.
- `_element_to_value` fallback branch (returning a raw `_Element`) is likely untested.
- `_ConfiguredServer` in `config.py` has no unit tests.

---

## Issues by Severity

| Severity | Location | Issue |
|---|---|---|
| **Bug** | `calendarobjectresource.py` `_async_complete` | RRULE path silently drops `save()` in async mode — should raise `NotImplementedError` |
| **Bug** | `response.py` `_parse_scheduling_response_objects` | Bare `assert` stripped by `-O`; use `error.assert_()` |
| **Design** | `davobject.py` `is_async_client` | String class-name comparison is fragile; use `isinstance()` or a class flag |
| **Design** | `response.py` | Two parallel XML parse pipelines can diverge; the TODO needs a target version |
| **Design** | `calendarobjectresource.py` | Repeated ETag/Schedule-Tag update block (≥4 copies); extract to helper |
| **Minor** | `response.py` `_element_to_value` | Returning raw `_Element` as fallback is surprising |
| **Minor** | `davobject.py` `_resolve_properties` | `return {}` after `error.assert_(False)` has opposite behaviour in debug vs production |
| **Minor** | `collection.py` `_extract_calendar_id_from_url` | Swallows exceptions silently; log the exception or re-raise |
