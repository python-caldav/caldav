# Sync/Async Library Design Patterns Analysis

This document analyzes different approaches for Python libraries that need to support
both synchronous and asynchronous APIs, based on community discussions and real-world
library implementations.

## The Core Question

Is "sync compatibility by wrapping async code" an antipattern? Should we maintain
two separate codebases instead?

## TL;DR

**No, it's not inherently an antipattern** - but naive implementations are problematic.
There are several valid patterns used by production libraries, each with different
tradeoffs.

## The Problem Space

Python's asyncio has a fundamental constraint: "async all the way down". Once you're
in sync code, you can't easily call async code without either:
1. Starting a new event loop (blocks if one exists)
2. Using threads to run the async code
3. Restructuring your entire call stack

As noted in [Python discussions](https://discuss.python.org/t/wrapping-async-functions-for-use-in-sync-code/8606):
> "When you employ async techniques, they have to start at the bottom and go upwards.
> If they don't go all the way to the top, that's fine, but once you've switched to
> sync you can't switch back without involving threads."

## Common Approaches

### 1. Sans-I/O Pattern

**Used by:** h11, h2, wsproto, hyper

Separate protocol/business logic from I/O entirely. The core library is pure Python
with no I/O - it just processes bytes in and bytes out. Then thin sync and async
"shells" handle the actual I/O.

```
┌─────────────────────┐
│   Sync Interface    │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  Sans-I/O Protocol  │  ← Pure logic, no I/O
│       Layer         │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  Async Interface    │
└─────────────────────┘
```

**Pros:**
- No code duplication
- Highly testable (no mocking I/O)
- Works with any async framework

**Cons:**
- Requires significant refactoring
- Not always natural for all problem domains
- Can be overengineering for simpler libraries

**Reference:** [Building Protocol Libraries The Right Way](https://www.youtube.com/watch?v=7cC3_jGwl_U) - Cory Benfield, PyCon 2016

### 2. Unasync (Code Generation)

**Used by:** urllib3, httpcore

Write the async version of your code, then use a tool to automatically generate
the sync version by stripping `async`/`await` keywords and transforming types.

```python
# Source (async):
async def fetch(self) -> AsyncIterator[bytes]:
    async with self.session.get(url) as response:
        async for chunk in response.content:
            yield chunk

# Generated (sync):
def fetch(self) -> Iterator[bytes]:
    with self.session.get(url) as response:
        for chunk in response.content:
            yield chunk
```

**Pros:**
- Single source of truth
- No runtime overhead
- Generated code is debuggable

**Cons:**
- Build complexity
- Debugging can be confusing (errors point to generated code)
- Requires careful naming conventions

**Tool:** [python-trio/unasync](https://github.com/python-trio/unasync)

### 3. Async-First with Sync Wrapper

**Used by:** Some database drivers, HTTP clients

Write async code as the primary implementation. Sync interface delegates to async
by running coroutines in a thread with its own event loop.

```python
class SyncClient:
    def search(self, **kwargs):
        async def _async_search(async_client):
            return await async_client.search(**kwargs)
        return self._run_async(_async_search)

    def _run_async(self, coro_func):
        # Run in thread with dedicated event loop
        loop = asyncio.new_event_loop()
        try:
            async_client = self._get_async_client()
            return loop.run_until_complete(coro_func(async_client))
        finally:
            loop.close()
```

**Pros:**
- Single source of truth for business logic
- Easier to maintain than two codebases
- Natural for I/O-heavy libraries

**Cons:**
- Thread/event loop overhead
- More complex error handling
- Potential issues with nested event loops

### 4. Sync-First with Async Wrapper

**Used by:** Some legacy libraries adding async support

Write sync code, wrap it for async using `run_in_executor()`.

```python
async def async_method(self):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self.sync_method)
```

**Pros:**
- Easy migration path for existing sync libraries
- Minimal changes to existing code

**Cons:**
- Doesn't leverage async I/O benefits
- Thread pool overhead
- Can block if thread pool is exhausted

### 5. Separate Libraries

**Used by:** aiohttp (async) + requests (sync), aioredis + redis-py

Maintain completely separate libraries for sync and async.

**Pros:**
- Clean separation
- Each can be optimized independently
- No runtime overhead from bridging

**Cons:**
- Full code duplication
- Features can drift between versions
- Double maintenance burden

## Comparison Table

| Approach | Code Duplication | Runtime Overhead | Complexity | Used By |
|----------|------------------|------------------|------------|---------|
| Sans-I/O | None | None | High | h11, h2 |
| Unasync | None (generated) | None | Medium | urllib3 |
| Async-first wrapper | None | Medium | Medium | various |
| Sync-first wrapper | None | High | Low | legacy libs |
| Separate libraries | Full | None | Low per-lib | aiohttp/requests |

## What NOT to Do (The Actual Antipatterns)

These are the real antipatterns to avoid:

### 1. Blocking the Event Loop

```python
# BAD: Blocks other coroutines
async def bad_method(self):
    result = some_sync_blocking_call()  # Blocks everything!
    return result
```

### 2. Nested Event Loops

```python
# BAD: Fails if loop already running
def sync_wrapper(self):
    return asyncio.run(self.async_method())  # Crashes in Jupyter, etc.
```

### 3. Ignoring Thread Safety

```python
# BAD: asyncio objects aren't thread-safe
def sync_wrapper(self):
    # Using async client from wrong thread
    return self.shared_async_client.sync_call()
```

## Evaluation for CalDAV Library Design

When considering which pattern to use for a CalDAV library:

### Sans-I/O Applicability
CalDAV is an HTTP-based protocol with XML payloads. The protocol logic (XML parsing,
property handling, URL manipulation) could potentially be separated from I/O, but:
- Much of the complexity is in HTTP request/response handling
- The existing codebase would need significant restructuring
- The benefit may not justify the refactoring cost

### Unasync Applicability
This could work well:
- Write async code once, generate sync automatically
- No runtime overhead
- But requires build-time code generation setup
- Debugging generated code can be confusing

### Async-First Wrapper Applicability
This approach:
- Keeps single source of truth
- Works well for I/O-bound operations (which CalDAV is)
- Has thread/event loop overhead
- Requires careful handling of object conversion between sync/async

### Separate Libraries
- Maximum flexibility but double maintenance
- Not practical for a library with caldav's scope

## Recommendations

1. **For minimal code duplication with acceptable overhead:** Async-first with sync
   wrapper is reasonable for I/O-bound libraries like CalDAV clients.

2. **For zero runtime overhead:** Consider unasync to generate sync code at build
   time, eliminating runtime bridging overhead.

3. **For new greenfield projects:** Consider sans-I/O if the domain allows clean
   separation of protocol logic from I/O.

## References

- [Wrapping async functions for use in sync code](https://discuss.python.org/t/wrapping-async-functions-for-use-in-sync-code/8606) - Python Discussion
- [Mixing Synchronous and Asynchronous Code](https://bbc.github.io/cloudfit-public-docs/asyncio/asyncio-part-5.html) - BBC Cloudfit Docs
- [Designing Libraries for Async and Sync I/O](https://sethmlarson.dev/designing-libraries-for-async-and-sync-io) - Seth Larson
- [HTTPX Async Support](https://www.python-httpx.org/async/) - HTTPX Documentation
- [Building Protocol Libraries The Right Way](https://www.youtube.com/watch?v=7cC3_jGwl_U) - Cory Benfield, PyCon 2016
- [AnyIO Documentation](https://anyio.readthedocs.io/) - Multi-async-library support
