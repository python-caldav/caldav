# DAVClient API Analysis and Improvement Suggestions

## Current API Overview

### DAVClient Public Methods (caldav/davclient.py)

```python
class DAVClient:
    # Constructor
    __init__(url, proxy, username, password, auth, auth_type, timeout,
             ssl_verify_cert, ssl_cert, headers, huge_tree, features,
             enable_rfc6764, require_tls)

    # Context manager
    __enter__() -> Self
    __exit__(...) -> None
    close() -> None

    # High-level API
    principals(name=None) -> List[Principal]
    principal(*args, **kwargs) -> Principal
    calendar(**kwargs) -> Calendar

    # Capability checks
    check_dav_support() -> Optional[str]
    check_cdav_support() -> bool
    check_scheduling_support() -> bool

    # HTTP methods (CalDAV/WebDAV)
    propfind(url: Optional[str], props: str, depth: int) -> DAVResponse
    proppatch(url: str, body: str, dummy: None) -> DAVResponse
    report(url: str, query: str, depth: int) -> DAVResponse
    mkcol(url: str, body: str, dummy: None) -> DAVResponse
    mkcalendar(url: str, body: str, dummy: None) -> DAVResponse
    put(url: str, body: str, headers: Mapping[str, str]) -> DAVResponse
    post(url: str, body: str, headers: Mapping[str, str]) -> DAVResponse
    delete(url: str) -> DAVResponse
    options(url: str) -> DAVResponse

    # Low-level
    request(url: str, method: str, body: str, headers: Mapping[str, str]) -> DAVResponse
    extract_auth_types(header: str) -> Set[str]
    build_auth_object(auth_types: Optional[List[str]]) -> None
```

---

## API Inconsistencies

### 1. **Inconsistent URL Parameter Handling**

**Issue:** Some methods accept `Optional[str]`, others require `str`

```python
# Inconsistent:
propfind(url: Optional[str] = None, ...)  # Can be None, defaults to self.url
proppatch(url: str, ...)                   # Required
delete(url: str)                           # Required
```

**Research Finding:** (See URL_AND_METHOD_RESEARCH.md for full analysis)

The inconsistency exists for **good reasons**:
- `self.url` is the **base CalDAV URL** (e.g., `https://caldav.example.com/`)
- Query methods (`propfind`, `report`, `options`) often query the base URL ✓
- Resource methods (`put`, `delete`, `post`, etc.) always target **specific resources** ✗

Making `delete(url=None)` would be **dangerous** - could accidentally try to delete the entire CalDAV server!

**Recommendation:**
- **Query methods** (`propfind`, `report`, `options`): Optional URL, defaults to `self.url` ✓
- **Resource methods** (`put`, `delete`, `post`, `proppatch`, `mkcol`, `mkcalendar`): **Required URL** ✓

```python
# Proposed (async API):
# Query methods - safe defaults
async def propfind(url: Optional[str] = None, ...) -> DAVResponse:
async def report(url: Optional[str] = None, ...) -> DAVResponse:
async def options(url: Optional[str] = None, ...) -> DAVResponse:

# Resource methods - URL required for safety
async def put(url: str, ...) -> DAVResponse:
async def delete(url: str, ...) -> DAVResponse:  # MUST be explicit!
async def post(url: str, ...) -> DAVResponse:
async def proppatch(url: str, ...) -> DAVResponse:
async def mkcol(url: str, ...) -> DAVResponse:
async def mkcalendar(url: str, ...) -> DAVResponse:
```

### 2. **Dummy Parameters**

**Issue:** Several methods have `dummy: None = None` parameter

```python
proppatch(url: str, body: str, dummy: None = None)
mkcol(url: str, body: str, dummy: None = None)
mkcalendar(url: str, body: str = "", dummy: None = None)
```

**Background:** Appears to be for backward compatibility

**Recommendation:**
- **Remove in async API** - no need to maintain this backward compatibility
- Document as deprecated in current sync API

```python
# Proposed (async):
async def proppatch(url: Optional[str] = None, body: str = "") -> DAVResponse:
    ...
```

### 3. **Inconsistent Body Parameter Defaults**

**Issue:** Some methods have default empty body, others don't

```python
request(url: str, method: str = "GET", body: str = "", ...)  # Default ""
propfind(url: Optional[str] = None, props: str = "", ...)    # Default ""
mkcalendar(url: str, body: str = "", ...)                     # Default ""
proppatch(url: str, body: str, ...)                           # Required
mkcol(url: str, body: str, ...)                               # Required
```

**Recommendation:**
- Make body optional with default `""` for all methods
- This is more user-friendly

```python
# Proposed:
async def proppatch(url: Optional[str] = None, body: str = "") -> DAVResponse:
async def mkcol(url: Optional[str] = None, body: str = "") -> DAVResponse:
```

### 4. **Inconsistent Headers Parameter**

**Issue:** Only some methods accept headers parameter

```python
request(url, method, body, headers: Mapping[str, str] = None)
put(url, body, headers: Mapping[str, str] = None)
post(url, body, headers: Mapping[str, str] = None)
propfind(...)  # No headers parameter
report(...)    # Hardcodes headers internally
```

**Recommendation:**
- Add optional `headers` parameter to ALL HTTP methods
- Merge with default headers in `request()`

```python
# Proposed:
async def propfind(
    url: Optional[str] = None,
    props: str = "",
    depth: int = 0,
    headers: Optional[Mapping[str, str]] = None,
) -> DAVResponse:
```

### 5. **Method Naming Inconsistency**

**Issue:** Mix of snake_case and noun-based names, unclear distinction between important/unimportant methods

```python
# Good (verb-based, consistent):
propfind()
proppatch()
mkcol()

# Inconsistent (check_ prefix vs methods):
check_dav_support()
check_cdav_support()
check_scheduling_support()

# Getters without clear naming:
principal()    # IMPORTANT: Works on all servers, gets current user's principal
principals(name=None)  # UNIMPORTANT: Search/query, works on few servers
calendar()     # Factory method, no server interaction
```

**Background on principals():**
- Uses `PrincipalPropertySearch` REPORT (RFC3744)
- Currently filters by `DisplayName` when `name` is provided
- Could be extended to filter by other properties (email, etc.)
- Only works on servers that support principal-property-search
- Less commonly used than `principal()`

**Recommendation:**
- Keep existing names for backward compatibility in sync wrapper
- In async API, use clearer, more Pythonic names that indicate importance:

```python
# Proposed (async API only):
async def get_principal() -> Principal:
    """Get the current user's principal (works on all servers)"""

async def search_principals(
    name: Optional[str] = None,
    email: Optional[str] = None,
    # Future: other search filters
) -> List[Principal]:
    """Search for principals using PrincipalPropertySearch (may not work on all servers)"""

async def get_calendar(**kwargs) -> Calendar:
    """Create a Calendar object (no server interaction)"""

async def supports_dav() -> bool:
async def supports_caldav() -> bool:
async def supports_scheduling() -> bool:
```

### 6. **Return Type Inconsistencies**

**Issue:** Some methods return DAVResponse, others return domain objects

```python
propfind() -> DAVResponse          # Low-level
principals() -> List[Principal]    # High-level
principal() -> Principal           # High-level
```

**This is actually OK** - Clear separation between low-level HTTP and high-level domain methods

**Recommendation:** Keep this distinction, but document it clearly

### 7. **Parameter Naming: `props` vs `query` vs `body`**

**Issue:** XML content is named inconsistently

```python
propfind(url, props: str = "", depth)        # "props"
report(url, query: str = "", depth)          # "query"
proppatch(url, body: str, dummy)             # "body"
mkcol(url, body: str, dummy)                 # "body"
```

**Research Finding:**

DAVObject._query() uses dynamic dispatch:
```python
ret = getattr(self.client, query_method)(url, body, depth)
```

This means all methods must have compatible signatures for when called via `_query(propfind/proppatch/mkcol/mkcalendar)`.

**Recommendation:**
- Standardize on `body` for all methods to enable consistent dynamic dispatch
- More generic and works for all HTTP methods

```python
# Proposed (async API):
async def propfind(url=None, body: str = "", depth: int = 0) -> DAVResponse:
async def report(url=None, body: str = "", depth: int = 0) -> DAVResponse:
async def proppatch(url, body: str = "") -> DAVResponse:
async def mkcol(url, body: str = "") -> DAVResponse:
async def mkcalendar(url, body: str = "") -> DAVResponse:

# Sync wrapper maintains old names:
def propfind(self, url=None, props="", depth=0):  # "props" for backward compat
    return asyncio.run(self._async.propfind(url, props, depth))
```

### 8. **Depth Parameter Inconsistency**

**Issue:** Only some methods have depth parameter

```python
propfind(url, props, depth: int = 0)
report(url, query, depth: int = 0)
# But put(), post(), delete(), etc. don't have depth
```

**This is actually correct** - only PROPFIND and REPORT use Depth header

**Recommendation:** Keep as-is

### 9. **Auth Methods Are Public But Internal**

**Issue:** Methods that should be private are public

```python
extract_auth_types(header: str)  # Should be _extract_auth_types
build_auth_object(...)           # Should be _build_auth_object
```

**Recommendation:**
- Prefix with `_` in async API
- Keep public in sync wrapper for backward compatibility

### 10. **Type Hints Inconsistency**

**Issue:** Some parameters have type hints, some don't

```python
principals(self, name=None):           # No type hints
principal(self, *largs, **kwargs):     # No type hints
propfind(url: Optional[str] = None, ...)  # Has type hints
```

**Recommendation:**
- Add complete type hints to async API
- Improves IDE support and catches bugs

---

## Proposed Async API Design

### Core Principles

1. **Consistency first** - uniform parameter ordering and naming
2. **Pythonic** - follows Python naming conventions
3. **Type-safe** - complete type hints
4. **Clean** - no backward compatibility baggage
5. **Explicit** - clear parameter names

### Proposed Method Signatures

```python
class AsyncDAVClient:
    """Modern async CalDAV/WebDAV client"""

    def __init__(
        self,
        url: str,
        *,  # Force keyword arguments
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth: Optional[AuthBase] = None,
        auth_type: Optional[Literal["basic", "digest", "bearer"]] = None,
        proxy: Optional[str] = None,
        timeout: int = 90,
        verify_ssl: bool = True,
        ssl_cert: Optional[Union[str, Tuple[str, str]]] = None,
        headers: Optional[Dict[str, str]] = None,
        huge_tree: bool = False,
        features: Optional[Union[FeatureSet, Dict, str]] = None,
        enable_rfc6764: bool = True,
        require_tls: bool = True,
    ) -> None:
        ...

    # Context manager
    async def __aenter__(self) -> Self:
        ...

    async def __aexit__(self, *args) -> None:
        ...

    async def close(self) -> None:
        """Close the session"""
        ...

    # High-level API (Pythonic names)
    async def get_principal(self) -> Principal:
        """Get the current user's principal (works on all servers)"""
        ...

    async def search_principals(
        self,
        name: Optional[str] = None,
        email: Optional[str] = None,
        **filters,
    ) -> List[Principal]:
        """
        Search for principals using PrincipalPropertySearch.

        May not work on all servers. Uses REPORT with principal-property-search.

        Args:
            name: Filter by display name
            email: Filter by email address (if supported)
            **filters: Additional property filters for future extensibility
        """
        ...

    async def get_calendar(self, **kwargs) -> Calendar:
        """Create a Calendar object (no server interaction, factory method)"""
        ...

    # Capability checks (renamed for clarity)
    async def supports_dav(self) -> bool:
        """Check if server supports WebDAV (RFC4918)"""
        ...

    async def supports_caldav(self) -> bool:
        """Check if server supports CalDAV (RFC4791)"""
        ...

    async def supports_scheduling(self) -> bool:
        """Check if server supports CalDAV Scheduling (RFC6833)"""
        ...

    # HTTP methods - split by URL semantics (see URL_AND_METHOD_RESEARCH.md)

    # Query methods - URL optional (defaults to self.url)
    async def propfind(
        self,
        url: Optional[str] = None,  # Defaults to self.url
        body: str = "",
        depth: int = 0,
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """PROPFIND request. Defaults to querying the base CalDAV URL."""
        ...

    async def report(
        self,
        url: Optional[str] = None,  # Defaults to self.url
        body: str = "",
        depth: int = 0,
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """REPORT request. Defaults to querying the base CalDAV URL."""
        ...

    async def options(
        self,
        url: Optional[str] = None,  # Defaults to self.url
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """OPTIONS request. Defaults to querying the base CalDAV URL."""
        ...

    # Resource methods - URL required (safety!)
    async def proppatch(
        self,
        url: str,  # REQUIRED - targets specific resource
        body: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """PROPPATCH request to update properties of a specific resource."""
        ...

    async def mkcol(
        self,
        url: str,  # REQUIRED - creates at specific path
        body: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """MKCOL request to create a collection at a specific path."""
        ...

    async def mkcalendar(
        self,
        url: str,  # REQUIRED - creates at specific path
        body: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """MKCALENDAR request to create a calendar at a specific path."""
        ...

    async def put(
        self,
        url: str,  # REQUIRED - targets specific resource
        body: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """PUT request to create/update a specific resource."""
        ...

    async def post(
        self,
        url: str,  # REQUIRED - posts to specific endpoint
        body: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """POST request to a specific endpoint."""
        ...

    async def delete(
        self,
        url: str,  # REQUIRED - safety critical!
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """DELETE request to remove a specific resource. URL must be explicit for safety."""
        ...

    # Low-level request method
    async def request(
        self,
        url: Optional[str] = None,
        method: str = "GET",
        body: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """Low-level HTTP request"""
        ...

    # Internal methods (private)
    def _extract_auth_types(self, header: str) -> Set[str]:
        """Extract auth types from WWW-Authenticate header"""
        ...

    async def _build_auth_object(
        self, auth_types: Optional[List[str]] = None
    ) -> None:
        """Build auth object based on available auth types"""
        ...
```

---

## Summary of Changes

### High Priority (Consistency & Safety)

1. ✅ **Split URL requirements** (see URL_AND_METHOD_RESEARCH.md):
   - Optional for query methods: `propfind`, `report`, `options`
   - **Required for resource methods**: `put`, `delete`, `post`, `proppatch`, `mkcol`, `mkcalendar`
2. ✅ Remove `dummy` parameters
3. ✅ Make `body` parameter optional everywhere (default to `""`)
4. ✅ Add `headers` parameter to all HTTP methods
5. ✅ Standardize parameter naming (`body` instead of `props`/`query`) for dynamic dispatch compatibility

### Medium Priority (Pythonic)

6. ⚠️ Rename methods for clarity (only in async API):
   - `check_*` → `supports_*`
   - `principals()` → `search_principals()` (better reflects it's a search/query operation)
   - `principal()` → `get_principal()` (the important one that works everywhere)
   - `calendar()` → `get_calendar()` (or keep as factory method?)

7. ✅ Make internal methods private (`_extract_auth_types`, `_build_auth_object`)
8. ✅ Add complete type hints everywhere

### Low Priority (Nice to Have)

9. Add better defaults and validation
10. Improve docstrings with examples

---

## Backward Compatibility Strategy

The sync wrapper (`davclient.py`) will maintain 100% backward compatibility:

```python
class DAVClient:
    """Synchronous wrapper around AsyncDAVClient for backward compatibility"""

    def __init__(self, *args, **kwargs):
        self._async_client = AsyncDAVClient(*args, **kwargs)

    def propfind(self, url: Optional[str] = None, props: str = "", depth: int = 0):
        """Sync wrapper - maintains old signature with 'props' parameter name"""
        return asyncio.run(self._async_client.propfind(url, props, depth))

    def proppatch(self, url: str, body: str, dummy: None = None):
        """Sync wrapper - maintains old signature with dummy parameter"""
        return asyncio.run(self._async_client.proppatch(url, body))

    # ... etc for all methods
```

---

## Testing Strategy

### 1. New Async Tests

Create `tests/test_async_davclient.py`:
- Test all async methods
- Test context manager behavior
- Test authentication flows
- Test error handling

### 2. Existing Tests Must Pass

All existing tests in `tests/test_caldav.py`, `tests/test_caldav_unit.py`, etc. must continue to pass with the sync wrapper.

### 3. Integration Tests

Test against real CalDAV servers (Radicale, Baikal, etc.) using both:
- Sync API (backward compatibility)
- Async API (new functionality)

---

## Implementation Plan

### Phase 1: Preparation
1. ✅ Analyze current API (this document)
2. Create backup branch
3. Ensure all tests pass on current code

### Phase 2: Create Async Core
1. Copy `davclient.py` → `async_davclient.py`
2. Convert to async (add `async def`, use `AsyncSession`)
3. Clean up API inconsistencies
4. Add complete type hints
5. Write async tests

### Phase 3: Create Sync Wrapper
1. Rewrite `davclient.py` as thin sync wrapper
2. Maintain 100% backward compatibility
3. Verify all old tests still pass

### Phase 4: Documentation
1. Update README with async examples
2. Add migration guide
3. Document API improvements

---

## Questions for Discussion

1. **Method renaming**: Should we rename methods in async API (e.g., `check_dav_support` → `supports_dav`) or keep exact names?
   - **Recommendation**: Rename for clarity, maintain old names in sync wrapper

2. **URL parameter**: Should it be optional or required?
   - **Recommendation**: Optional with default `self.url` for convenience

3. **Type hints**: Should we use strict types (`str`) or flexible (`Union[str, URL]`)?
   - **Recommendation**: Accept `Union[str, URL]` for flexibility, normalize internally

4. **Auth handling**: Should auth retry logic stay in `request()` or be separate?
   - **Recommendation**: Keep in `request()` for consistency

5. **Error handling**: Should we create custom exception hierarchy?
   - **Recommendation**: Keep existing error classes, they work well
