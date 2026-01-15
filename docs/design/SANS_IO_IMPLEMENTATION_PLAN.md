# Sans-I/O Implementation Plan

**Last Updated:** January 2026
**Status:** Phase 1 Complete, Phase 2 In Progress

## Current Architecture

The Sans-I/O refactoring has been partially completed. Here's the current state:

```
┌─────────────────────────────────────────────────────┐
│  High-Level Objects (Calendar, Principal, etc.)     │
│  → Use DAVResponse.results (parsed protocol types)  │
├─────────────────────────────────────────────────────┤
│  DAVClient (sync) / AsyncDAVClient (async)          │
│  → Handle HTTP via niquests                         │
│  → Use protocol layer for XML building/parsing      │
│  → ~65% code duplication (problem!)                 │
├─────────────────────────────────────────────────────┤
│  Protocol Layer (caldav/protocol/)                  │
│  → xml_builders.py: Pure functions for XML bodies   │
│  → xml_parsers.py: Pure functions for parsing       │
│  → types.py: DAVRequest, DAVResponse, result types  │
│  → NO I/O - just data transformations               │
└─────────────────────────────────────────────────────┘
```

### What's Working

1. **Protocol Layer** (`caldav/protocol/`):
   - `xml_builders.py` - All XML request body building
   - `xml_parsers.py` - All response parsing
   - `types.py` - DAVRequest, DAVResponse, PropfindResult, etc.
   - Used by both sync and async clients

2. **Response Parsing**:
   - `DAVResponse.results` provides parsed protocol types
   - `find_objects_and_props()` deprecated but still works

3. **Both Clients Work**:
   - `DAVClient` - Full sync API with backward compatibility
   - `AsyncDAVClient` - Async API (not yet released)

### The Problem: Code Duplication

`davclient.py` (959 lines) and `async_davclient.py` (1035 lines) share ~65% of their logic:

| Component | Duplication |
|-----------|-------------|
| `extract_auth_types()` | **100%** identical |
| HTTP method wrappers (put, post, delete, etc.) | ~95% |
| `build_auth_object()` | ~70% |
| Response initialization | ~80% |
| Constructor logic | ~85% |

## Refactoring Plan

### Approach: Extract Shared Code (Not Abstract I/O)

The original plan proposed an `io/` layer abstraction. This was **abandoned** because:
- Added complexity without clear benefit
- Both clients use niquests which handles sync/async natively
- The protocol layer already provides the "Sans-I/O" separation

**New approach:** Extract identical/similar code to shared modules.

### Phase 1: Protocol Layer ✅ COMPLETE

The protocol layer is working:
- `caldav/protocol/xml_builders.py` - XML request body construction
- `caldav/protocol/xml_parsers.py` - Response parsing
- `caldav/protocol/types.py` - Type definitions

### Phase 2: Extract Shared Utilities (Current)

**Goal:** Reduce duplication without architectural changes.

#### Step 2.1: Extract `extract_auth_types()`

This method is **100% identical** in both clients.

```python
# caldav/lib/auth.py (new file)
def extract_auth_types(www_authenticate: str) -> list[str]:
    """Extract authentication types from WWW-Authenticate header."""
    # ... identical implementation ...
```

Both clients import and use this function.

#### Step 2.2: Extract `CONNKEYS` Constant

Currently only in `davclient.py`, but needed by both.

```python
# caldav/lib/constants.py (new or existing)
CONNKEYS = frozenset([
    "url", "proxy", "username", "password", "timeout", "headers",
    "huge_tree", "ssl_verify_cert", "ssl_cert", "auth", "auth_type",
    "features", "enable_rfc6764", "require_tls",
])
```

#### Step 2.3: Extract Auth Type Selection Logic

The `build_auth_object()` method has ~70% duplication. Extract the selection logic:

```python
# caldav/lib/auth.py
def select_auth_method(
    auth_types: list[str],
    prefer_digest: bool = True
) -> str | None:
    """Select best auth method from available types."""
    if prefer_digest and "digest" in auth_types:
        return "digest"
    if "basic" in auth_types:
        return "basic"
    if "bearer" in auth_types:
        return "bearer"
    return None
```

Each client still creates its own auth object (sync vs async differ).

### Phase 3: Consolidate Response Handling

**Goal:** Move common response logic to `BaseDAVResponse`.

Currently both `DAVResponse` and `AsyncDAVResponse` have ~80% identical `__init__()` logic for:
- XML parsing with etree
- Exception handling
- Error status processing

#### Proposed Structure:

```python
# caldav/response.py
class BaseDAVResponse:
    """Base class with shared response handling."""

    def _parse_xml(self, raw: bytes) -> etree.Element | None:
        """Parse XML body - shared implementation."""
        # Move identical parsing logic here

    def _process_errors(self, status: int, tree: etree.Element) -> None:
        """Process error responses - shared implementation."""
        # Move identical error handling here

class DAVResponse(BaseDAVResponse):
    """Sync response - thin wrapper."""

    def __init__(self, response, client):
        self._init_from_response(response)  # Calls shared methods

class AsyncDAVResponse(BaseDAVResponse):
    """Async response - thin wrapper."""

    def __init__(self, response, client):
        self._init_from_response(response)  # Calls shared methods
```

### Phase 4: Consider Base Client Class (Future)

**Status:** Deferred - evaluate after Phase 2-3.

A `BaseDAVClient` could reduce duplication further, but:
- Sync/async method signatures differ fundamentally
- May not be worth the complexity
- Evaluate after simpler refactoring is done

## Files to Modify

| File | Changes |
|------|---------|
| `caldav/lib/auth.py` | NEW: Shared auth utilities |
| `caldav/lib/constants.py` | Add CONNKEYS if not present |
| `caldav/davclient.py` | Import shared utilities |
| `caldav/async_davclient.py` | Import shared utilities |
| `caldav/response.py` | Consolidate BaseDAVResponse |

## Files Removed (Cleanup Done)

These were from the abandoned io/ layer approach:

| File | Reason Removed |
|------|----------------|
| `caldav/io/` | Never integrated, io/ abstraction abandoned |
| `caldav/protocol_client.py` | Redundant with protocol layer |
| `caldav/protocol/operations.py` | CalDAVProtocol class never used |

## Success Criteria

1. ✅ Protocol layer is single source of truth for XML
2. ⏳ No duplicate utility functions between clients
3. ⏳ Shared constants accessible to both clients
4. ⏳ Common response logic in BaseDAVResponse
5. ✅ All existing tests pass
6. ✅ Backward compatibility maintained for sync API

## Testing Strategy

1. Run existing test suite after each change
2. Verify both sync and async integration tests pass
3. Test with real servers (Radicale, Xandikos, Nextcloud)

## Timeline

- **Phase 1:** ✅ Complete
- **Phase 2:** 1-2 days (extract utilities)
- **Phase 3:** 2-3 days (consolidate response handling)
- **Phase 4:** Evaluate after Phase 3
