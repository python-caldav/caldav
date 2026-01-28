# Sans-I/O Implementation Plan

**Last Updated:** January 2026
**Status:** Phase 1-3 Complete

## Current Architecture

The Sans-I/O refactoring has been significantly completed. Here's the current state:

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

### Remaining Duplication

After Phase 2-3 refactoring, duplication has been significantly reduced:

| Component | Status |
|-----------|--------|
| `extract_auth_types()` | ✅ Extracted to `caldav/lib/auth.py` |
| `select_auth_type()` | ✅ Extracted to `caldav/lib/auth.py` |
| `CONNKEYS` | ✅ Single source in `caldav/config.py` |
| Response initialization | ✅ Consolidated in `BaseDAVResponse._init_from_response()` |
| HTTP method wrappers | ~95% similar (acceptable - sync/async signatures differ) |
| Constructor logic | ~85% similar (acceptable - client setup differs) |

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

### Phase 2: Extract Shared Utilities ✅ COMPLETE

**Goal:** Reduce duplication without architectural changes.

**Completed:**

- `caldav/lib/auth.py` created with:
  - `extract_auth_types()` - Parse WWW-Authenticate headers
  - `select_auth_type()` - Choose best auth method from options
- `CONNKEYS` uses single source in `caldav/config.py`
- Both clients import and use these shared utilities

### Phase 3: Consolidate Response Handling ✅ COMPLETE

**Goal:** Move common response logic to `BaseDAVResponse`.

**Completed:**

- `BaseDAVResponse._init_from_response()` now contains all shared initialization:
  - Headers and status extraction
  - XML parsing with etree
  - Content-type validation
  - CRLF normalization
  - Error handling
- `BaseDAVResponse.raw` property moved from subclasses
- `DAVResponse.__init__` reduced to single delegation call
- `AsyncDAVResponse.__init__` reduced to single delegation call
- Eliminated ~150 lines of duplicated code

### Phase 4: Consider Base Client Class (Future)

**Status:** Deferred - evaluate after Phase 2-3.

A `BaseDAVClient` could reduce duplication further, but:
- Sync/async method signatures differ fundamentally
- May not be worth the complexity
- Evaluate after simpler refactoring is done

## Files Modified

| File | Changes |
|------|---------|
| `caldav/lib/auth.py` | ✅ NEW: Shared auth utilities |
| `caldav/config.py` | ✅ CONNKEYS single source |
| `caldav/davclient.py` | ✅ Uses shared utilities, simplified DAVResponse |
| `caldav/async_davclient.py` | ✅ Uses shared utilities, simplified AsyncDAVResponse |
| `caldav/response.py` | ✅ BaseDAVResponse with _init_from_response() and raw property |

## Files Removed (Cleanup Done)

These were from the abandoned io/ layer approach:

| File | Reason Removed |
|------|----------------|
| `caldav/io/` | Never integrated, io/ abstraction abandoned |
| `caldav/protocol_client.py` | Redundant with protocol layer |
| `caldav/protocol/operations.py` | CalDAVProtocol class never used |

## Success Criteria

1. ✅ Protocol layer is single source of truth for XML
2. ✅ No duplicate utility functions between clients (auth.py)
3. ✅ Shared constants accessible to both clients (config.py)
4. ✅ Common response logic in BaseDAVResponse
5. ✅ All existing tests pass
6. ✅ Backward compatibility maintained for sync API

## Timeline

- **Phase 1:** ✅ Complete
- **Phase 2:** ✅ Complete
- **Phase 3:** ✅ Complete
- **Phase 4:** Evaluate if further refactoring is needed
