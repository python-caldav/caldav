# Playground Branch: Sync/Async Implementation Analysis

This document analyzes the implementation approach taken in the `playground/new_async_api_design`
branch and compares it against the industry patterns documented in
[`SYNC_ASYNC_PATTERNS.md`](SYNC_ASYNC_PATTERNS.md).

## Branch Overview

The playground branch implements an **async-first architecture with sync wrapper** approach:

1. **Async classes are the primary implementation:**
   - `AsyncDAVClient` - HTTP client using aiohttp
   - `AsyncDAVObject`, `AsyncCalendarObjectResource` - Resource objects
   - `AsyncCalendar`, `AsyncCalendarSet`, `AsyncPrincipal` - Collection classes

2. **Sync classes delegate to async via event loop bridging:**
   - `DAVClient` creates `AsyncDAVClient` instances
   - Sync methods run async coroutines via `asyncio.run()` or a managed event loop
   - Results are converted from async types to sync types

## Implementation Details

### Event Loop Management

The branch uses two strategies for running async code from sync context:

**Strategy 1: Per-call `asyncio.run()` (simple mode)**
```python
async def _execute():
    async_client = self.client._get_async_client()
    async with async_client:
        async_obj = AsyncCalendar(client=async_client, ...)
        return await async_func(async_obj)

return asyncio.run(_execute())
```

**Strategy 2: Persistent loop with context manager (optimized mode)**
```python
# When DAVClient is used as context manager, reuse connections
if self.client._async_client is not None and self.client._loop_manager is not None:
    return self.client._loop_manager.run_coroutine(_execute_cached())
```

### Object Conversion

Async results are converted to sync equivalents:
```python
def _async_object_to_sync(self, async_obj):
    """Convert async calendar object to sync equivalent."""
    from .calendarobjectresource import Event, Journal, Todo
    # ... conversion logic
```

### Mock Client Handling

For unit tests with mocked clients, async delegation is bypassed:
```python
if hasattr(self.client, "_is_mocked") and self.client._is_mocked():
    raise NotImplementedError("Async delegation not supported for mocked clients")
    # Falls back to sync implementation
```

## Comparison with Industry Patterns

### Pattern Match: Async-First with Sync Wrapper

The playground branch follows the **Async-First with Sync Wrapper** pattern from
SYNC_ASYNC_PATTERNS.md. Here's how it compares:

| Aspect | Pattern Description | Playground Implementation |
|--------|---------------------|---------------------------|
| Primary implementation | Async code | ✅ AsyncDAVClient, AsyncCalendar, etc. |
| Sync interface | Delegates to async | ✅ Via `asyncio.run()` or managed loop |
| Event loop handling | Thread with dedicated loop | ⚠️ Uses `asyncio.run()` (simpler but more overhead) |
| Connection reuse | Optional optimization | ✅ Context manager mode reuses connections |

### Avoided Antipatterns

The implementation correctly avoids the antipatterns listed in SYNC_ASYNC_PATTERNS.md:

| Antipattern | Status | How Avoided |
|-------------|--------|-------------|
| Blocking the event loop | ✅ Avoided | Async code is truly async (aiohttp) |
| Nested event loops | ✅ Avoided | Uses `asyncio.run()` which creates fresh loop |
| Thread safety issues | ✅ Avoided | Each `asyncio.run()` creates isolated loop |

### Tradeoffs Accepted

**Overhead accepted:**
- Each sync call without context manager creates a new event loop
- Each call creates a new AsyncDAVClient and aiohttp session
- Connection pooling only works in context manager mode

**Complexity accepted:**
- Object conversion between async and sync types
- Dual code paths (mocked vs real clients)
- Feature set synchronization between sync and async classes

## Alternative Approaches Not Taken

### Why Not Sans-I/O?

The sans-I/O pattern would require separating protocol logic from I/O:
- CalDAV is HTTP-based, so "protocol logic" is largely XML parsing
- The existing codebase mixes HTTP operations with business logic
- Refactoring cost would be significant
- Benefit unclear for a library of this scope

### Why Not Unasync?

Unasync (code generation) could eliminate runtime overhead:
- Would require restructuring code for async-first naming
- Build-time generation adds complexity
- Generated code can be harder to debug
- Could be considered as a future optimization

### Why Not Separate Libraries?

Maintaining separate sync and async libraries:
- Would require full code duplication
- Feature drift risk between versions
- Double maintenance burden
- Not practical for the current team size

## Strengths of Current Approach

1. **Single source of truth** - Business logic lives in async classes only
2. **Backward compatible** - Existing sync API unchanged
3. **Incremental adoption** - Users can migrate to async gradually
4. **Testable** - Async code can be tested directly with pytest-asyncio
5. **Connection reuse** - Context manager mode optimizes repeated operations

## Weaknesses / Areas for Improvement

1. **Runtime overhead** - Each sync call (outside context manager) has loop creation cost
2. **Memory overhead** - Creates temporary async objects for each operation
3. **Complexity** - Object conversion logic adds maintenance burden
4. **Mock limitations** - Unit tests with mocked clients bypass async path

## Potential Future Optimizations

If the runtime overhead becomes problematic, consider:

1. **Thread-local event loop** - Reuse loop across sync calls in same thread
2. **Unasync adoption** - Generate sync code at build time
3. **Lazy async client** - Create async client once per DAVClient instance
4. **Connection pooling** - Share aiohttp session across calls

## Conclusion

The playground branch implements a valid and pragmatic approach to dual sync/async
support. It prioritizes:
- Maintainability (single codebase for logic)
- Backward compatibility (sync API unchanged)
- Correctness (proper async handling)

Over:
- Maximum performance (runtime overhead accepted)
- Simplicity (object conversion adds complexity)

This is a reasonable tradeoff for a library where I/O latency (network) dominates
over the overhead of event loop management.

## References

- [SYNC_ASYNC_PATTERNS.md](SYNC_ASYNC_PATTERNS.md) - Industry patterns analysis
- [ASYNC_REFACTORING_PLAN.md](ASYNC_REFACTORING_PLAN.md) - Original refactoring plan
- Branch: `playground/new_async_api_design`
