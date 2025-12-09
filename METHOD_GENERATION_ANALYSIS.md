# Analysis: Generating HTTP Method Wrappers vs Manual Implementation

## Your Insights

1. **Option 3 loses mocking** - if `_query()` calls `request()` directly, we can't mock `client.propfind()`
2. **`_query()` could be eliminated** - callers could call methods directly instead
3. **Generate methods** - instead of writing them manually, generate them programmatically

## Current Usage of _query()

Let me trace where `_query()` is actually called:

```python
# davobject.py:191 - in _query_properties()
return self._query(root, depth)

# davobject.py:382 - in set_properties()
r = self._query(root, query_method="proppatch")

# collection.py:469 - in save() for creating calendars
r = self._query(root=mkcol, query_method=method, url=path, expected_return_value=201)

# collection.py:666, 784, 982 - in various search/report methods
response = self._query(root, 1, "report")
response = self._query(xml, 1, "report")
response = self._query(root, 1, "report")
```

### Key Observation

`_query()` is called with different `query_method` values:
- `"propfind"` (default)
- `"proppatch"`
- `"mkcol"` or `"mkcalendar"`
- `"report"`

**Your insight is correct**: These calls could be replaced with direct method calls!

```python
# Instead of:
r = self._query(root, query_method="proppatch")

# Could be:
r = self.client.proppatch(self.url, body)

# Instead of:
r = self._query(root=mkcol, query_method="mkcol", url=path, ...)

# Could be:
r = self.client.mkcol(path, body)
```

## Option Analysis

### Option A: Remove _query(), Keep Manual Wrappers ✓

**Implementation:**
```python
# In DAVObject - eliminate _query() entirely
def _query_properties(self, props=None, depth=0):
    """Query properties"""
    root = None
    if props is not None and len(props) > 0:
        prop = dav.Prop() + props
        root = dav.Propfind() + prop

    body = ""
    if root:
        body = etree.tostring(root.xmlelement(), encoding="utf-8", xml_declaration=True)

    # Direct call to method wrapper
    ret = self.client.propfind(self.url, body, depth)

    if ret.status == 404:
        raise error.NotFoundError(errmsg(ret))
    if ret.status >= 400:
        raise error.exception_by_method["propfind"](errmsg(ret))
    return ret

def set_properties(self, props=None):
    """Set properties"""
    prop = dav.Prop() + (props or [])
    set_elem = dav.Set() + prop
    root = dav.PropertyUpdate() + set_elem
    body = etree.tostring(root.xmlelement(), encoding="utf-8", xml_declaration=True)

    # Direct call to method wrapper
    r = self.client.proppatch(self.url, body)

    statuses = r.tree.findall(".//" + dav.Status.tag)
    for s in statuses:
        if " 200 " not in s.text:
            raise error.PropsetError(s.text)
    return self
```

**Pros:**
- ✅ Keeps mocking capability (`client.propfind = mock.Mock()`)
- ✅ Clear, explicit code
- ✅ Good discoverability
- ✅ Eliminates `_query()` complexity

**Cons:**
- ❌ ~50 lines of boilerplate per wrapper (8 wrappers = ~400 lines)
- ❌ Duplicate parameter handling in each wrapper

### Option B: Generate Wrappers Dynamically at Class Creation

**Implementation:**

```python
# In davclient.py

class DAVClient:
    """CalDAV client"""

    # Method specifications
    _WEBDAV_METHODS = {
        'propfind': {
            'http_method': 'PROPFIND',
            'has_depth': True,
            'has_body': True,
            'default_headers': lambda depth: {'Depth': str(depth)},
        },
        'report': {
            'http_method': 'REPORT',
            'has_depth': True,
            'has_body': True,
            'default_headers': lambda depth: {
                'Depth': str(depth),
                'Content-Type': 'application/xml; charset="utf-8"'
            },
        },
        'proppatch': {
            'http_method': 'PROPPATCH',
            'has_depth': False,
            'has_body': True,
            'url_required': True,
        },
        'mkcol': {
            'http_method': 'MKCOL',
            'has_depth': False,
            'has_body': True,
            'url_required': True,
        },
        'mkcalendar': {
            'http_method': 'MKCALENDAR',
            'has_depth': False,
            'has_body': True,
            'url_required': True,
        },
        'put': {
            'http_method': 'PUT',
            'has_depth': False,
            'has_body': True,
            'url_required': True,
            'has_headers': True,
        },
        'post': {
            'http_method': 'POST',
            'has_depth': False,
            'has_body': True,
            'url_required': True,
            'has_headers': True,
        },
        'delete': {
            'http_method': 'DELETE',
            'has_depth': False,
            'has_body': False,
            'url_required': True,
        },
        'options': {
            'http_method': 'OPTIONS',
            'has_depth': False,
            'has_body': False,
        },
    }

    def __init__(self, ...):
        # ... normal init ...

    async def request(self, url=None, method="GET", body="", headers=None):
        """Low-level HTTP request"""
        # ... implementation ...


# Generate wrapper methods dynamically
def _create_method_wrapper(method_name, method_spec):
    """Factory function to create a method wrapper"""

    def wrapper(self, url=None, body="", depth=0, headers=None):
        # Build the actual call
        final_url = url if method_spec.get('url_required') else (url or str(self.url))
        final_headers = headers or {}

        # Add default headers
        if method_spec.get('has_depth') and 'default_headers' in method_spec:
            final_headers.update(method_spec['default_headers'](depth))

        return self.request(
            final_url,
            method_spec['http_method'],
            body if method_spec.get('has_body') else "",
            final_headers
        )

    # Set proper metadata
    wrapper.__name__ = method_name
    wrapper.__doc__ = f"{method_spec['http_method']} request"

    return wrapper

# Attach generated methods to the class
for method_name, method_spec in DAVClient._WEBDAV_METHODS.items():
    setattr(DAVClient, method_name, _create_method_wrapper(method_name, method_spec))
```

**Usage is identical:**
```python
client.propfind(url, body, depth)  # Works the same
client.proppatch(url, body)         # Works the same
```

**Pros:**
- ✅ Keeps mocking capability
- ✅ DRY - single source of truth for method specs
- ✅ Easy to add new methods (just add to dict)
- ✅ ~100 lines instead of ~400 lines
- ✅ Still discoverable (methods exist on class)

**Cons:**
- ❌ Harder to debug (generated code)
- ❌ IDE auto-complete might not work as well
- ❌ Type hints would need `__init_subclass__` or stub file
- ❌ Less explicit (magic)

### Option C: Generate Wrappers with Explicit Signatures (Best of Both)

Use a decorator to generate methods but keep signatures explicit:

```python
# In davclient.py

def webdav_method(http_method, has_depth=False, url_required=False, headers_fn=None):
    """Decorator to create WebDAV method wrappers"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, url=None, body="", depth=0, headers=None):
            # Delegate to the decorated function for any custom logic
            return func(self, url, body, depth, headers, http_method, headers_fn)
        return wrapper
    return decorator

class DAVClient:

    @webdav_method("PROPFIND", has_depth=True,
                   headers_fn=lambda depth: {"Depth": str(depth)})
    def propfind(self, url, body, depth, headers, http_method, headers_fn):
        """PROPFIND request"""
        final_headers = {**headers_fn(depth), **(headers or {})}
        return self.request(url or str(self.url), http_method, body, final_headers)

    @webdav_method("REPORT", has_depth=True,
                   headers_fn=lambda depth: {
                       "Depth": str(depth),
                       "Content-Type": 'application/xml; charset="utf-8"'
                   })
    def report(self, url, body, depth, headers, http_method, headers_fn):
        """REPORT request"""
        final_headers = {**headers_fn(depth), **(headers or {})}
        return self.request(url or str(self.url), http_method, body, final_headers)

    @webdav_method("PROPPATCH", url_required=True)
    def proppatch(self, url, body, depth, headers, http_method, headers_fn):
        """PROPPATCH request"""
        return self.request(url, http_method, body, headers or {})
```

**Pros:**
- ✅ Explicit method signatures (good for IDE)
- ✅ Type hints work normally
- ✅ Can add docstrings
- ✅ DRY for common behavior
- ✅ Mocking works

**Cons:**
- ❌ Still somewhat repetitive
- ❌ Decorator makes it less obvious what's happening

### Option D: Keep Manual Methods, Add Helper

Simplest approach - keep methods but use helper:

```python
class DAVClient:

    def _build_headers(self, method, depth=0):
        """Helper to build method-specific headers"""
        if method == "PROPFIND":
            return {"Depth": str(depth)}
        elif method == "REPORT":
            return {
                "Depth": str(depth),
                "Content-Type": 'application/xml; charset="utf-8"'
            }
        return {}

    async def propfind(self, url=None, body="", depth=0, headers=None):
        """PROPFIND request"""
        final_headers = {**self._build_headers("PROPFIND", depth), **(headers or {})}
        return await self.request(url or str(self.url), "PROPFIND", body, final_headers)

    async def report(self, url=None, body="", depth=0, headers=None):
        """REPORT request"""
        final_headers = {**self._build_headers("REPORT", depth), **(headers or {})}
        return await self.request(url or str(self.url), "REPORT", body, final_headers)

    async def proppatch(self, url, body="", headers=None):
        """PROPPATCH request"""
        return await self.request(url, "PROPPATCH", body, headers or {})

    # ... etc for other methods
```

**Pros:**
- ✅ Explicit and clear
- ✅ Easy to debug
- ✅ Good IDE support
- ✅ Mocking works
- ✅ Simple to understand

**Cons:**
- ❌ ~300 lines for 8 methods
- ❌ Some repetition

## Recommendation: Option D (Manual + Helper)

For the **async refactoring**, I recommend **Option D**:

1. **Keep manual methods** - 8 methods × ~40 lines = ~320 lines
2. **Use helper for headers** - reduces duplication
3. **Eliminate `_query()`** - callers use methods directly
4. **Clear and explicit** - Pythonic, easy to understand

**Why not generated (Option B/C)?**
- Async/await makes generation more complex
- Type hints would be harder
- Debugging generated async code is painful
- Not that much code savings (~100 lines)

**Implementation in async:**

```python
class AsyncDAVClient:

    @staticmethod
    def _method_headers(method: str, depth: int = 0) -> Dict[str, str]:
        """Build headers for WebDAV methods (internal helper)"""
        headers_map = {
            "PROPFIND": {"Depth": str(depth)},
            "REPORT": {
                "Depth": str(depth),
                "Content-Type": 'application/xml; charset="utf-8"'
            },
        }
        return headers_map.get(method.upper(), {})

    # Query methods (URL optional)
    async def propfind(
        self,
        url: Optional[str] = None,
        body: str = "",
        depth: int = 0,
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """PROPFIND request - query properties"""
        final_headers = {
            **self._method_headers("PROPFIND", depth),
            **(headers or {})
        }
        return await self.request(url or str(self.url), "PROPFIND", body, final_headers)

    async def report(
        self,
        url: Optional[str] = None,
        body: str = "",
        depth: int = 0,
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """REPORT request - run reports"""
        final_headers = {
            **self._method_headers("REPORT", depth),
            **(headers or {})
        }
        return await self.request(url or str(self.url), "REPORT", body, final_headers)

    # Resource methods (URL required)
    async def proppatch(
        self,
        url: str,
        body: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """PROPPATCH request - update properties"""
        return await self.request(url, "PROPPATCH", body, headers or {})

    async def mkcol(
        self,
        url: str,
        body: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVResponse:
        """MKCOL request - create collection"""
        return await self.request(url, "MKCOL", body, headers or {})

    # ... etc
```

## What About _query()?

**Eliminate it!** Callers should use the methods directly:

```python
# In AsyncDAVObject:

async def _query_properties(self, props=None, depth=0):
    """Query properties via PROPFIND"""
    root = None
    if props:
        prop = dav.Prop() + props
        root = dav.Propfind() + prop

    body = ""
    if root:
        body = etree.tostring(root.xmlelement(), encoding="utf-8", xml_declaration=True)

    # Direct call - no _query() middleman
    ret = await self.client.propfind(self.url, body, depth)

    if ret.status == 404:
        raise error.NotFoundError(errmsg(ret))
    if ret.status >= 400:
        raise error.exception_by_method["propfind"](errmsg(ret))
    return ret

async def set_properties(self, props=None):
    """Set properties via PROPPATCH"""
    prop = dav.Prop() + (props or [])
    set_elem = dav.Set() + prop
    root = dav.PropertyUpdate() + set_elem
    body = etree.tostring(root.xmlelement(), encoding="utf-8", xml_declaration=True)

    # Direct call - no _query()
    r = await self.client.proppatch(self.url, body)

    statuses = r.tree.findall(".//" + dav.Status.tag)
    for s in statuses:
        if " 200 " not in s.text:
            raise error.PropsetError(s.text)
    return self
```

## Summary

1. **Eliminate `_query()`** - it's unnecessary indirection ✅
2. **Keep method wrappers** - for mocking and discoverability ✅
3. **Use manual implementation** - clear, explicit, debuggable ✅
4. **Add helper for headers** - reduce repetition ✅

**Code size**: ~320 lines for 8 methods (reasonable)
**Benefits**: Mocking works, clear code, easy to maintain
**Trade-off**: Some repetition, but Pythonic and explicit

For async API, this is the sweet spot between DRY and explicit.
