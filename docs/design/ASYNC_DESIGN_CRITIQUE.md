# Async Design: Current Approach and Its Problems

**Written:** March 2026
**Context:** Bug hunt following commit e819a3a5 (async save/complete fixes)

---

## The Current Approach

The library adds async support through a **dual-mode single-class** pattern:

- `DAVClient` and `AsyncDAVClient` are separate classes at the HTTP layer.
- `Calendar`, `Event`, `Todo`, and friends are **shared** between sync and async use.
- Methods detect at runtime whether they are being called from an async context
  via the `is_async_client` property, then either do the work directly or delegate
  to a private `_async_*` counterpart that uses `await`.

Example (simplified):

```python
def save(self, ...):
    if self.is_async_client:
        return self._async_save(...)   # returns a coroutine
    # ... sync implementation ...
    self._create(...)
    return self

async def _async_save(self, ...):
    # ... same logic, with await ...
    await self._async_create(...)
    return self
```

The caller then does either `obj.save()` or `await obj.save()` depending on context.

---

## Why This Is Fragile

### Silent coroutine discard

The single biggest problem: **if a method calls `self.save()` internally and
forgets the async check, the coroutine is silently discarded with no error**.

```python
def uncomplete(self):
    ...ical manipulation...
    self.save()          # BUG: returns a coroutine in async mode, discarded silently
```

The object appears to work — `uncomplete()` returns `None` as expected — but the
change is never written to the server.  There is no exception, no warning, nothing.

Commit e819a3a5 fixed `save()` and `complete()`.  The subsequent commit fixed
`uncomplete()`, `set_relation()`, `get_relatives()`, and the invite-reply methods.
Each was caught only because someone wrote an explicit unit test checking
`asyncio.iscoroutine(result)`.

### Every new I/O method is a latent bug

The pattern requires that **every** method touching I/O has:

1. An async check at the top.
2. A corresponding `_async_*` method.
3. A unit test verifying the coroutine is returned.

Miss any one of these three and you have a silent bug.  There is no compiler
enforcement, no type checker that catches it (the return type annotations currently
lie — `-> None` but actually `-> Coroutine | None`), and no runtime warning.

### Type annotations are incorrect

`save()` is annotated `-> Self`.  In async mode it actually returns
`Coroutine[Any, Any, Self]`.  These are not the same type.  Any type-checked
caller (`mypy`, `pyright`) that writes:

```python
obj = event.save()
obj.icalendar_component  # AttributeError: Coroutine has no attribute icalendar_component
```

will get a runtime error that mypy would not catch.

### Growing method count

Each I/O-touching method produces a pair: the public method and its `_async_*`
twin.  As the feature surface grows, so does the duplication.  Helpers like
`_add_relation_to_ical()` and `_parse_relatives_from_ical()` reduce *some* of the
duplication, but the structural problem remains.

---

## Alternative Approaches

### 1. Separate async classes (the "motor" pattern)

Create `AsyncCalendar`, `AsyncEvent`, `AsyncTodo` etc. that inherit all the pure
ical-manipulation logic from the base classes but override every I/O method as
`async def`:

```python
class AsyncEvent(Event):
    async def save(self, ...): ...
    async def load(self, ...): ...
    async def complete(self, ...): ...
    # etc.
```

Pros:
- Correct type annotations — `AsyncEvent.save()` returns `Coroutine`, `Event.save()` returns `Self`.
- No runtime branching — no `if self.is_async_client`.
- Missing overrides become obvious (the sync version just works, perhaps wrongly, but at least it's detectable).
- Familiar pattern (aiohttp vs requests, motor vs pymongo, etc.).

Cons:
- Breaking API change for anyone currently using `Calendar` and `AsyncDAVClient` together.
- More class hierarchy to maintain.
- Factory functions (`get_calendar()`, `get_calendars()`) would need to return the right subclass.

### 2. Full Sans-I/O at the object level

Push all I/O out of `CalendarObjectResource` entirely.  Methods like `save()` and
`load()` would produce **request descriptors** that the caller passes to the client:

```python
req = event.build_save_request()
response = await client.execute(req)
event.apply_save_response(response)
```

Pros: Completely decoupled, fully testable without mocks, one code path.
Cons: Very different API, massive refactor, probably not worth it for a library
at this level of abstraction.

### 3. asyncio.run() wrapper (rejected)

Wrap all async methods with `asyncio.run()` for the sync case.  Rejected because
nested event loops are forbidden, and `asyncio.run()` cannot be called from an
already-running loop.

---

## Recommendation

The dual-mode pattern is pragmatic and probably good enough for the near term,
but it needs systematic guarding:

1. **Every public method that does I/O must have a unit test** asserting
   `asyncio.iscoroutine(result)` for async clients.  The test should also assert
   that awaiting the coroutine produces the expected side-effect (not just that it
   returned a coroutine).

2. **Fix the type annotations** — either accept that they are wrong and document
   it, or use an overload:
   ```python
   @overload
   def save(self: "SyncSelf", ...) -> Self: ...
   @overload
   def save(self: "AsyncSelf", ...) -> Coroutine[Any, Any, Self]: ...
   ```
   This is verbose but gives type checkers a chance.

3. **Consider a linting rule or metaclass hook** that walks all `CalendarObjectResource`
   subclass methods looking for `self.save()`, `self.load()`, `self.parent.*()` calls
   without a preceding `is_async_client` guard.  This could be a simple AST check run
   in CI.

4. **Long-term**: if async use grows significantly, the separate-class approach is
   cleaner.  The migration could be done incrementally — `AsyncCalendar` delegates to
   `Calendar` for now, then gradually overrides methods.

---

## Methods Still Missing Async Support (as of March 2026)

The following methods call I/O internally but do **not** yet have async support.
They will silently misbehave when called on objects associated with an async client:

- `_complete_recurring_safe()` — calls `self.complete()` and `completed.save()` and
  `completed.complete()`.  Protected by the `handle_rrule=True → NotImplementedError`
  guard in `_async_complete()`, but the underlying methods are not async-safe.
- `_complete_recurring_thisandfuture()` — same protection, same underlying issue.
- `accept_invite()` / `decline_invite()` / `tentatively_accept_invite()` — now raise
  `NotImplementedError` for async clients.  A proper async implementation would need
  to await `load()`, `add_event()`, `schedule_outbox()`, and `save()`.
- `_handle_reverse_relations()` / `check_reverse_relations()` / `fix_reverse_relations()`
  — call `get_relatives()` (now async-aware) and `set_relation()` (now async-aware), but
  the methods themselves are not async-aware and will get a coroutine back from
  `get_relatives()` and try to iterate it synchronously.
- `is_invite_request()` / `is_invite_reply()` — call `self.load(only_if_unloaded=True)`,
  which returns a coroutine in async mode; these return the wrong thing silently.
