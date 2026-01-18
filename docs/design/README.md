# CalDAV Design Documents

**Note:** Many of these documents were generated during exploration and may be outdated.
The authoritative documents are marked below.

## Current Status (January 2026)

**Branch:** `playground/sans_io_asynd_design`

### What's Working
- ✅ Protocol layer (`caldav/protocol/`) - XML building and parsing
- ✅ Sync client (`DAVClient`) - Full backward compatibility
- ✅ Async client (`AsyncDAVClient`) - Working but not yet released
- ✅ High-level classes work with both sync and async

### Current Problem
- ~65% code duplication between `davclient.py` and `async_davclient.py`
- See [SANS_IO_IMPLEMENTATION_PLAN.md](SANS_IO_IMPLEMENTATION_PLAN.md) for refactoring plan

## Authoritative Documents

### [SANS_IO_DESIGN.md](SANS_IO_DESIGN.md) ⭐
**Current architecture** - What Sans-I/O means for this project:
- Protocol layer separates XML logic from I/O
- Why we didn't implement a full I/O abstraction layer
- Testing benefits

### [SANS_IO_IMPLEMENTATION_PLAN.md](SANS_IO_IMPLEMENTATION_PLAN.md) ⭐
**Refactoring plan** to reduce duplication:
- Phase 1: Protocol layer ✅ Complete
- Phase 2: Extract shared utilities (current)
- Phase 3: Consolidate response handling

### [PROTOCOL_LAYER_USAGE.md](PROTOCOL_LAYER_USAGE.md)
How to use the protocol layer for testing and low-level access.

## Historical/Reference Documents

These documents capture analysis done during development. Some may be outdated.

| Document | Status | Notes |
|----------|--------|-------|
| `API_ANALYSIS.md` | Reference | API inconsistency analysis |
| `ASYNC_REFACTORING_PLAN.md` | Outdated | Original async-first plan |
| `PLAYGROUND_BRANCH_ANALYSIS.md` | Reference | Branch evaluation |
| `SYNC_ASYNC_PATTERNS.md` | Reference | Industry patterns |
| Others | Historical | Various analyses |

## Removed Components

The following were removed as orphaned/unused code:
- `caldav/io/` - I/O abstraction layer (never integrated)
- `caldav/protocol_client.py` - Redundant protocol client
- `caldav/protocol/operations.py` - CalDAVProtocol class (never used)
