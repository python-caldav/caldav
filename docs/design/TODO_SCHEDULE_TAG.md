# Schedule-Tag TODO

## What Schedule-Tag is (RFC 6638)

Schedule-Tag is an opaque token attached to each scheduling object resource (an event/todo
that carries an ORGANIZER or ATTENDEE).  It works like ETag for scheduling, but changes on
a different cadence: ETag changes on every PUT; Schedule-Tag changes only when the
**scheduling-significant** content changes.

- **Organizer's copy**: tag changes on direct HTTP modifications (PUT/COPY/MOVE), but
  **not** when the server auto-processes an attendee reply back onto the organizer's
  resource.
- **Attendee's copy**: tag changes when the organizer sends an update, but **not** when
  the attendee updates only their own participation status (PARTSTAT).

The `If-Schedule-Tag-Match` request header lets a client say "only save this if my copy
has not been updated by the organizer since I fetched it".  Without it, the classic race
is:

1. Attendee fetches event (schedule-tag = "X").
2. Organizer sends an update; server writes new data onto attendee's resource
   (schedule-tag = "Y").
3. Attendee PUTs their PARTSTAT change, unknowingly wiping out step 2.

With `If-Schedule-Tag-Match: "X"`, step 3 returns 412 and the attendee client knows to
re-fetch and merge.

References:
- https://datatracker.ietf.org/doc/html/rfc6638#section-3.2
- https://datatracker.ietf.org/doc/html/rfc6638#section-3.3
- https://datatracker.ietf.org/doc/html/rfc6638#section-8

## Current state in the codebase

The infrastructure is half-built:

- `cdav.ScheduleTag` element exists (`caldav/elements/cdav.py:202`).
- GET/load responses capture the `Schedule-Tag` response header into
  `self.props[cdav.ScheduleTag.tag]` (`calendarobjectresource.py:873`, `918`).
- `save()` accepts `if_schedule_tag_match: bool = False` but the docstring says
  *"is currently ignored"* — it is merely forwarded to `_async_save`, which also ignores
  it (`calendarobjectresource.py:1136`).
- `_reply_to_invite_request` calls `get_property(ScheduleTag)` to populate the prop but
  then never uses the value.
- `_put` / `_async_put` send a hardcoded header dict containing only `Content-Type` — no
  conditional headers at all (not even `If-Match` / `If-None-Match` for ETag).

## Suggested implementation

### 1. Add extra-headers support to `_put` / `_async_put`

`_put` needs to accept an optional extra-headers dict so callers can inject
`If-Schedule-Tag-Match` (and, in the future, `If-Match`):

```python
def _put(self, retry_on_failure=True, extra_headers=None):
    headers = {"Content-Type": 'text/calendar; charset="utf-8"'}
    if extra_headers:
        headers.update(extra_headers)
    r = self.client.put(self.url, self.data, headers)
    ...
```

### 2. Wire `if_schedule_tag_match` through `save()` → `_put()`

In `save()` / `_async_save()`, when `if_schedule_tag_match=True`, look up the cached
schedule-tag property and inject the header:

```python
if if_schedule_tag_match:
    tag = self.props.get(cdav.ScheduleTag.tag)
    if tag is None:
        self.load()   # fetch tag before sending conditional PUT
        tag = self.props.get(cdav.ScheduleTag.tag)
    if tag is not None:
        extra_headers["If-Schedule-Tag-Match"] = tag
```

A missing cached tag is a notable edge case.  The safest default is to do a `load()`
first so the tag is available; alternatively raise `ValueError` to surface the caller
error explicitly.

### 3. Fix `_reply_to_invite_request`

This method already calls `get_property(ScheduleTag)` but never uses the result.  After
the fix to `save()`, the reply path should call `self.save(if_schedule_tag_match=True)`
so that the attendee's PARTSTAT update is protected against a racing organizer update.

The current fallback logic in that method is also confused: it re-fetches the schedule-tag
and then recurses with `calendar=outbox`, which bypasses the conditional header entirely.
This needs a clean rewrite once the basic wiring is in place.

### 4. Expose `schedule_tag` as a public property

The tag is currently buried in `self.props[cdav.ScheduleTag.tag]`.  A simple property
would be cleaner and avoid callers importing `cdav`:

```python
@property
def schedule_tag(self) -> str | None:
    return self.props.get(cdav.ScheduleTag.tag)
```

### 5. Raise a specific exception on 412 schedule-tag mismatch

When the server returns 412 for a schedule-tag mismatch, `_put` raises a generic
`PutError`.  A more specific exception lets callers handle the "re-fetch and merge" case:

```python
class ScheduleTagMismatchError(PutError):
    """Server returned 412 because If-Schedule-Tag-Match did not match."""
```

Distinguishing a schedule-tag 412 from an ETag 412 may require inspecting the response
body or a `Schedule-Tag` precondition code.

### 6. Add a `scheduling.schedule-tag` compatibility hint

Not all RFC 6638 servers implement schedule-tag (it is a SHOULD, not a MUST).  A feature
entry should be added and detected by checking for the `Schedule-Tag` header in a GET
response on a scheduling object resource.

## What to test

- `save(if_schedule_tag_match=True)` on a stale object (tag changed server-side) → 412
  → `ScheduleTagMismatchError`.
- `save(if_schedule_tag_match=True)` on a fresh object → 204 → tag updated in props.
- `_reply_to_invite_request` sends `If-Schedule-Tag-Match` and succeeds without wiping
  an organizer's concurrent update.
- PARTSTAT-only update does **not** change the schedule-tag (server compliance check).
