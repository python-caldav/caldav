# Analysis: Eliminating HTTP Method Wrappers by Refactoring _query()

## Current Situation

`DAVObject._query()` uses **dynamic dispatch** (line 219):
```python
ret = getattr(self.client, query_method)(url, body, depth)
```

This requires method wrappers like `propfind()`, `proppatch()`, `mkcol()`, etc. to exist on `DAVClient`.

## Your Observation

**The wrappers could be eliminated** by having `_query()` call `self.client.request()` directly instead!

## Current Wrapper Implementation

Each wrapper is **just a thin adapter** that adds method-specific headers:

```python
def propfind(self, url=None, props="", depth=0):
    return self.request(
        url or str(self.url),
        "PROPFIND",
        props,
        {"Depth": str(depth)}
    )

def report(self, url, query="", depth=0):
    return self.request(
        url,
        "REPORT",
        query,
        {"Depth": str(depth), "Content-Type": 'application/xml; charset="utf-8"'}
    )

def proppatch(self, url, body, dummy=None):
    return self.request(url, "PROPPATCH", body)

def mkcol(self, url, body, dummy=None):
    return self.request(url, "MKCOL", body)

def mkcalendar(self, url, body="", dummy=None):
    return self.request(url, "MKCALENDAR", body)
```

**Total code**: ~100 lines of mostly boilerplate

## Proposed Refactoring

### Option 1: Map Method Names to HTTP Methods + Headers

```python
# In DAVClient:
_METHOD_HEADERS = {
    "propfind": lambda depth: {"Depth": str(depth)},
    "report": lambda depth: {
        "Depth": str(depth),
        "Content-Type": 'application/xml; charset="utf-8"'
    },
    "proppatch": lambda depth: {},
    "mkcol": lambda depth: {},
    "mkcalendar": lambda depth: {},
}

# In DAVObject._query():
def _query(
    self,
    root=None,
    depth=0,
    query_method="propfind",
    url=None,
    expected_return_value=None,
):
    body = ""
    if root:
        if hasattr(root, "xmlelement"):
            body = etree.tostring(
                root.xmlelement(),
                encoding="utf-8",
                xml_declaration=True,
                pretty_print=error.debug_dump_communication,
            )
        else:
            body = root

    if url is None:
        url = self.url

    # NEW: Build headers based on method
    headers = {}
    if query_method in DAVClient._METHOD_HEADERS:
        headers = DAVClient._METHOD_HEADERS[query_method](depth)

    # NEW: Call request() directly
    ret = self.client.request(
        url,
        query_method.upper(),  # "propfind" -> "PROPFIND"
        body,
        headers
    )

    # ... rest of error handling stays the same ...
```

**Result**: No method wrappers needed!

### Option 2: More Explicit Method Registry

```python
# In DAVClient:
class MethodConfig:
    def __init__(self, http_method, headers_fn=None):
        self.http_method = http_method
        self.headers_fn = headers_fn or (lambda depth: {})

_QUERY_METHODS = {
    "propfind": MethodConfig(
        "PROPFIND",
        lambda depth: {"Depth": str(depth)}
    ),
    "report": MethodConfig(
        "REPORT",
        lambda depth: {
            "Depth": str(depth),
            "Content-Type": 'application/xml; charset="utf-8"'
        }
    ),
    "proppatch": MethodConfig("PROPPATCH"),
    "mkcol": MethodConfig("MKCOL"),
    "mkcalendar": MethodConfig("MKCALENDAR"),
}

# In DAVObject._query():
def _query(self, root=None, depth=0, query_method="propfind", url=None, ...):
    # ... body preparation same as before ...

    if url is None:
        url = self.url

    # NEW: Look up method config
    method_config = self.client._QUERY_METHODS.get(query_method)
    if not method_config:
        raise ValueError(f"Unknown query method: {query_method}")

    headers = method_config.headers_fn(depth)

    # NEW: Call request() directly
    ret = self.client.request(
        url,
        method_config.http_method,
        body,
        headers
    )

    # ... error handling ...
```

### Option 3: Keep Wrappers but Make Them Optional

Compromise: Keep wrappers for public API, but make `_query()` not depend on them:

```python
# In DAVClient:
def _build_headers_for_method(self, method_name, depth=0):
    """Internal: build headers for a WebDAV method"""
    if method_name == "propfind":
        return {"Depth": str(depth)}
    elif method_name == "report":
        return {"Depth": str(depth), "Content-Type": 'application/xml; charset="utf-8"'}
    else:
        return {}

# Public wrappers still exist for direct use:
def propfind(self, url=None, body="", depth=0, headers=None):
    """Public API for PROPFIND"""
    merged_headers = self._build_headers_for_method("propfind", depth)
    if headers:
        merged_headers.update(headers)
    return self.request(url or str(self.url), "PROPFIND", body, merged_headers)

# In DAVObject._query():
def _query(self, root=None, depth=0, query_method="propfind", url=None, ...):
    # ... body preparation ...

    if url is None:
        url = self.url

    # Call request() directly via internal helper
    headers = self.client._build_headers_for_method(query_method, depth)
    ret = self.client.request(url, query_method.upper(), body, headers)

    # ... error handling ...
```

## Pros and Cons

### Pros of Eliminating Wrappers:

1. **Less code** - ~100 lines eliminated
2. **Less duplication** - single place to define method behavior
3. **Easier to add new methods** - just update the registry
4. **More maintainable** - all logic in one place
5. **Cleaner architecture** - no artificial methods just for dispatch

### Cons of Eliminating Wrappers:

1. **Breaking change for mocking** - tests that mock `client.propfind` will break
   ```python
   # Currently works:
   client.propfind = mock.MagicMock(return_value=response)

   # Would need to become:
   client.request = mock.MagicMock(...)
   ```

2. **Less discoverable API** - no auto-complete for `client.propfind()`
   ```python
   # Current (discoverable):
   client.propfind(...)
   client.report(...)

   # New (not discoverable):
   client.request(..., method="PROPFIND", ...)  # or hidden in _query()
   ```

3. **Not part of public API anyway** - these methods are rarely called directly (only 6 times in entire codebase)

4. **Could keep public wrappers** - eliminate the *dependency* in `_query()` but keep wrappers for convenience

## Impact Analysis

### Files that would need changes:

1. **davobject.py** - Refactor `_query()` (1 method)
2. **davclient.py** - Add method registry/helper (10-30 lines)
3. **tests/** - Update any mocks (unknown number)

### Files that would NOT need changes:

- **collection.py** - calls `_query()`, doesn't care about implementation
- **calendarobjectresource.py** - calls `client.put()` directly (keep wrapper)
- **Most other code** - uses high-level API

### Backward Compatibility

**Option 1 & 2**: Breaking change
- Method wrappers removed
- Tests that mock them will break

**Option 3**: Non-breaking
- Keep wrappers as public API
- `_query()` stops depending on them
- Tests continue to work

## Recommendation

### For Async Refactoring: **Option 3** (Keep wrappers, remove dependency)

**Why:**

1. **Non-breaking** - existing tests/mocks still work
2. **Better public API** - `client.propfind()` is more discoverable than `client.request(..., "PROPFIND", ...)`
3. **Best of both worlds**:
   - `_query()` uses `request()` directly (clean architecture)
   - Public wrappers exist for convenience and discoverability
   - Wrappers can be thin (5-10 lines each)

**Implementation:**

```python
# In async_davclient.py:

class AsyncDAVClient:

    @staticmethod
    def _method_headers(method: str, depth: int = 0) -> Dict[str, str]:
        """Build headers for a WebDAV method (internal helper)"""
        if method.upper() == "PROPFIND":
            return {"Depth": str(depth)}
        elif method.upper() == "REPORT":
            return {
                "Depth": str(depth),
                "Content-Type": 'application/xml; charset="utf-8"'
            }
        return {}

    async def request(
        self,
        url: Optional[str] = None,
        method: str = "GET",
        body: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """Low-level HTTP request"""
        # ... implementation ...

    # Public convenience wrappers (thin):
    async def propfind(
        self,
        url: Optional[str] = None,
        body: str = "",
        depth: int = 0,
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """PROPFIND request"""
        merged = {**self._method_headers("PROPFIND", depth), **(headers or {})}
        return await self.request(url, "PROPFIND", body, merged)

    async def report(
        self,
        url: Optional[str] = None,
        body: str = "",
        depth: int = 0,
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """REPORT request"""
        merged = {**self._method_headers("REPORT", depth), **(headers or {})}
        return await self.request(url, "REPORT", body, merged)

    # ... other methods ...

# In async_davobject.py:

class AsyncDAVObject:
    async def _query(
        self,
        root=None,
        depth=0,
        query_method="propfind",
        url=None,
        expected_return_value=None,
    ):
        """Internal query method - calls request() directly"""
        # ... body preparation ...

        if url is None:
            url = self.url

        # NEW: Call request() directly, not the method wrapper
        headers = self.client._method_headers(query_method, depth)
        ret = await self.client.request(url, query_method.upper(), body, headers)

        # ... error handling ...
```

## Summary

**YES, we can eliminate the dependency on method wrappers in `_query()`**, and we should!

**However**, we should **keep the wrappers as public convenience methods** because:
1. Better API discoverability
2. Maintains backward compatibility
3. Only ~50 lines of code each in async version
4. Makes testing easier (can mock specific methods)

The key insight: **remove the _dependency_ in `_query()`, not the wrappers themselves.**

This gives us:
- ✅ Clean internal architecture (`_query()` → `request()` directly)
- ✅ Nice public API (`client.propfind()` is clear and discoverable)
- ✅ No breaking changes
- ✅ Easy to test
