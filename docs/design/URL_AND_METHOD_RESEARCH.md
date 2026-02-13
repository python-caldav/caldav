# Research: URL Parameters and HTTP Method Wrappers

## Executive Summary

After analyzing the codebase, I found that:

1. **HTTP method wrappers are rarely called directly** - most calls go through `DAVObject._query()` using dynamic method dispatch
2. **URL parameters have different semantics** - `self.url` is a base URL that's inappropriate as default for some operations
3. **The wrappers serve important purposes** beyond convenience - they're used for mocking, dynamic dispatch, and API consistency

## Detailed Findings

### 1. HTTP Method Wrapper Usage Analysis

#### Direct Calls in caldav/ (excluding aio.py):

| Method | Direct Calls | Locations |
|--------|--------------|-----------|
| `propfind` | 0 | None (all via `_query()`) |
| `proppatch` | 0 | None (all via `_query()`) |
| `report` | 1 | `davclient.py:734` (in `principals()`) |
| `mkcol` | 0 | None (all via `_query()`) |
| `mkcalendar` | 0 | None (all via `_query()`) |
| `put` | 1 | `calendarobjectresource.py:771` (in `_put()`) |
| `post` | 1 | `collection.py:368` (in `get_freebusy()`) |
| `delete` | 1 | `davobject.py:409` (in `delete()`) |
| `options` | 2 | `davclient.py:805,807` (in `check_dav_support()`) |
| **TOTAL** | **6** | |

#### Key Discovery: Dynamic Method Dispatch

The most important finding: **`DAVObject._query()` uses `getattr()` for dynamic dispatch**:

```python
# davobject.py:219
ret = getattr(self.client, query_method)(url, body, depth)
```

This means methods like `propfind`, `proppatch`, `mkcol`, `mkcalendar` are invoked **by name as strings**:

```python
# Usage examples:
self._query(root, query_method="propfind", ...)    # Default
self._query(root, query_method="proppatch", ...)   # davobject.py:382
self._query(root, query_method="mkcol", ...)       # collection.py:470
self._query(root, query_method="mkcalendar", ...)  # collection.py:470
```

**Implication:** The method wrappers **cannot be removed** without breaking `_query()`'s dynamic dispatch.

### 2. URL Parameter Semantics

#### What is `self.url`?

`self.url` is the **base CalDAV server URL** or **principal URL**, for example:
- `https://caldav.example.com/`
- `https://caldav.example.com/principals/user/`

#### URL Usage Patterns by Method:

**Category A: Methods that operate on `self.url` (base URL)**
- `propfind(url=None)` - Can query self.url for server capabilities ✓
- `report(url=None)` - Used with self.url in `principals()` ✓
- `options(url=None)` - Checks capabilities of self.url ✓

**Category B: Methods that operate on resource URLs (NOT self.url)**
- `put(url)` - Always targets a specific resource (event, calendar, etc.)
- `delete(url)` - Always deletes a specific resource
- `post(url)` - Always posts to a specific URL (e.g., outbox)
- `proppatch(url)` - Always patches a specific resource
- `mkcol(url)` - Creates a collection at a specific path
- `mkcalendar(url)` - Creates a calendar at a specific path

#### Evidence from Actual Usage:

```python
# davobject.py:409 - delete() always passes a specific URL
r = self.client.delete(str(self.url))  # self.url here is the OBJECT url, not base

# calendarobjectresource.py:771 - put() always passes a specific URL
r = self.client.put(self.url, self.data, ...)  # self.url is event URL

# collection.py:368 - post() always to outbox
response = self.client.post(outbox.url, ...)  # specific outbox URL

# davclient.py:734 - report() with base URL for principal search
response = self.report(self.url, ...)  # self.url is client base URL

# davclient.py:805 - options() with principal URL
response = self.options(self.principal().url)  # specific principal URL
```

### 3. Current Signature Analysis

#### Methods with Optional URL (make sense with self.url):

```python
propfind(url: Optional[str] = None, props: str = "", depth: int = 0)
# Usage: client.propfind() queries client.url - MAKES SENSE ✓

report(url: str, query: str = "", depth: int = 0)
# Currently REQUIRED but could be optional
# Usage: client.report(client.url, ...) - could default to self.url ✓

options(url: str)
# Currently REQUIRED but could be optional
# Usage: client.options(str(self.url)) - could default to self.url ✓
```

#### Methods with Required URL (shouldn't default to self.url):

```python
put(url: str, body: str, headers: Mapping[str, str] = None)
# Always targets specific resource - url SHOULD be required ✓

delete(url: str)
# Always targets specific resource - url SHOULD be required ✓
# Deleting the base CalDAV URL would be catastrophic!

post(url: str, body: str, headers: Mapping[str, str] = None)
# Always targets specific endpoint - url SHOULD be required ✓

proppatch(url: str, body: str, dummy: None = None)
# Always targets specific resource - url SHOULD be required ✓

mkcol(url: str, body: str, dummy: None = None)
# Creates at specific path - url SHOULD be required ✓

mkcalendar(url: str, body: str = "", dummy: None = None)
# Creates at specific path - url SHOULD be required ✓
```

### 4. Why HTTP Method Wrappers Are Necessary

#### Reason #1: Dynamic Dispatch in `_query()`

```python
# davobject.py:219
ret = getattr(self.client, query_method)(url, body, depth)
```

The wrappers are looked up **by name at runtime**. Removing them would break this pattern.

#### Reason #2: Test Mocking

```python
# tests/test_caldav_unit.py:542
client.propfind = mock.MagicMock(return_value=mocked_davresponse)
```

Tests mock specific HTTP methods. Direct `request()` mocking would be harder to target specific operations.

#### Reason #3: Consistent Parameter Transformation

Each wrapper handles method-specific concerns:

```python
def propfind(self, url=None, props="", depth=0):
    return self.request(
        url or str(self.url),
        "PROPFIND",
        props,
        {"Depth": str(depth)}  # Adds Depth header
    )

def report(self, url, query="", depth=0):
    return self.request(
        url,
        "REPORT",
        query,
        {
            "Depth": str(depth),
            "Content-Type": 'application/xml; charset="utf-8"'  # Adds Content-Type
        },
    )
```

Without wrappers, callers would need to remember method-specific headers.

#### Reason #4: Discoverability and Documentation

```python
client.propfind(...)  # Clear what operation is happening
client.mkcalendar(...)  # Self-documenting
vs
client.request(..., method="PROPFIND", ...)  # Less clear
```

### 5. Signature Consistency Issue

Current signatures are **inconsistent** because they evolved organically:

```python
# Inconsistent depths:
propfind(url, props, depth)  # (depth as parameter)
report(url, query, depth)    # (depth as parameter)

# Inconsistent body names:
propfind(url, props, depth)      # "props"
report(url, query, depth)        # "query"
proppatch(url, body, dummy)      # "body"
put(url, body, headers)          # "body"
```

But **the depth issue is actually correct** - only PROPFIND and REPORT support the Depth header per RFC4918.

## Recommendations

### 1. Keep All HTTP Method Wrappers

**Verdict:** ✅ **KEEP WRAPPERS** - they serve multiple essential purposes:
- Dynamic dispatch in `_query()`
- Test mocking
- Method-specific header handling
- API discoverability

### 2. URL Parameter: Context-Specific Defaults

**Proposal:** Different defaults based on method semantics:

```python
class AsyncDAVClient:
    # Category A: Query methods - self.url is a sensible default
    async def propfind(
        self,
        url: Optional[str] = None,  # Defaults to self.url ✓
        body: str = "",
        depth: int = 0,
    ) -> DAVResponse:
        """PROPFIND request. Defaults to querying the base CalDAV URL."""
        ...

    async def report(
        self,
        url: Optional[str] = None,  # Defaults to self.url ✓
        body: str = "",
        depth: int = 0,
    ) -> DAVResponse:
        """REPORT request. Defaults to querying the base CalDAV URL."""
        ...

    async def options(
        self,
        url: Optional[str] = None,  # Defaults to self.url ✓
    ) -> DAVResponse:
        """OPTIONS request. Defaults to querying the base CalDAV URL."""
        ...

    # Category B: Resource methods - URL is REQUIRED
    async def put(
        self,
        url: str,  # REQUIRED - no sensible default ✓
        body: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """PUT request to create/update a resource."""
        ...

    async def delete(
        self,
        url: str,  # REQUIRED - no sensible default, dangerous if wrong! ✓
    ) -> DAVResponse:
        """DELETE request to remove a resource."""
        ...

    async def post(
        self,
        url: str,  # REQUIRED - always to specific endpoint ✓
        body: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """POST request."""
        ...

    async def proppatch(
        self,
        url: str,  # REQUIRED - always patches specific resource ✓
        body: str = "",
    ) -> DAVResponse:
        """PROPPATCH request."""
        ...

    async def mkcol(
        self,
        url: str,  # REQUIRED - always creates at specific path ✓
        body: str = "",
    ) -> DAVResponse:
        """MKCOL request."""
        ...

    async def mkcalendar(
        self,
        url: str,  # REQUIRED - always creates at specific path ✓
        body: str = "",
    ) -> DAVResponse:
        """MKCALENDAR request."""
        ...
```

### 3. Standardize Parameter Names

**Proposal:** Use `body` consistently, but keep depth only where it makes sense:

```python
# Before (inconsistent):
propfind(url, props, depth)      # "props"
report(url, query, depth)        # "query"
proppatch(url, body, dummy)      # "body" + dummy

# After (consistent):
propfind(url, body, depth)       # "body"
report(url, body, depth)         # "body"
proppatch(url, body)             # "body", no dummy
```

### 4. Add Headers Parameter to All

**Proposal:** Allow custom headers on all methods:

```python
async def propfind(
    url: Optional[str] = None,
    body: str = "",
    depth: int = 0,
    headers: Optional[Dict[str, str]] = None,  # NEW
) -> DAVResponse:
    ...
```

### 5. Alternative: Keep Low-Level, Add High-Level

Instead of removing wrappers, we could **add high-level methods** while keeping low-level ones:

```python
class AsyncDAVClient:
    # Low-level HTTP wrappers (keep for backward compat & _query())
    async def propfind(url, body, depth) -> DAVResponse: ...
    async def report(url, body, depth) -> DAVResponse: ...

    # High-level convenience methods
    async def query_properties(
        self,
        url: Optional[str] = None,
        properties: Optional[List[BaseElement]] = None,
        depth: int = 0,
    ) -> Dict:
        """
        High-level property query that returns parsed properties.
        Wraps propfind() with XML parsing.
        """
        ...
```

**Verdict:** This adds complexity without much benefit. Skip for now.

## Final Recommendations Summary

1. ✅ **Keep all HTTP method wrappers** - essential for dynamic dispatch and testing
2. ✅ **Split URL requirements**:
   - Optional (defaults to `self.url`): `propfind`, `report`, `options`
   - Required: `put`, `delete`, `post`, `proppatch`, `mkcol`, `mkcalendar`
3. ✅ **Standardize parameter name to `body`** (not `props` or `query`)
4. ✅ **Remove `dummy` parameters** in async API
5. ✅ **Add `headers` parameter to all methods**
6. ✅ **Keep `depth` only on methods that support it** (propfind, report)

## Impact on Backward Compatibility

The sync wrapper can maintain old signatures:

```python
class DAVClient:
    def propfind(self, url=None, props="", depth=0):
        """Sync wrapper - keeps 'props' parameter name"""
        return asyncio.run(self._async_client.propfind(url, props, depth))

    def proppatch(self, url, body, dummy=None):
        """Sync wrapper - keeps dummy parameter"""
        return asyncio.run(self._async_client.proppatch(url, body))

    def delete(self, url):
        """Sync wrapper - url required"""
        return asyncio.run(self._async_client.delete(url))
```

All existing code continues to work unchanged!
