# CalDAV Design Documents

## Current Status (January 2026)

**Branch:** `v3.0-dev`

### Architecture

The caldav library uses a **Sans-I/O** approach where protocol logic (XML building/parsing)
is separated from I/O operations. This allows the same protocol code to be used by both
sync and async clients.

```
┌─────────────────────────────────────────────────────┐
│  High-Level Objects (Calendar, Principal, etc.)     │
├─────────────────────────────────────────────────────┤
│  Operations Layer (caldav/operations/)              │
│  - Pure functions for building queries              │
│  - Pure functions for processing responses          │
├─────────────────────────────────────────────────────┤
│  DAVClient (sync) / AsyncDAVClient (async)          │
│  → Handle HTTP via niquests                         │
├─────────────────────────────────────────────────────┤
│  Protocol Layer (caldav/protocol/)                  │
│  - xml_builders.py: Build XML request bodies        │
│  - xml_parsers.py: Parse XML responses              │
└─────────────────────────────────────────────────────┘
```

## Design Documents

### [SANS_IO_DESIGN.md](SANS_IO_DESIGN.md)
**Current architecture** - What Sans-I/O means for this project:
- Protocol layer separates XML logic from I/O
- Testing benefits
- Why we didn't implement a full I/O abstraction layer

### [SANS_IO_IMPLEMENTATION_PLAN.md](SANS_IO_IMPLEMENTATION_PLAN.md)
**Implementation status** for reducing code duplication:
- Phase 1: Protocol layer ✅ Complete
- Phase 2: Extract shared utilities ✅ Complete
- Phase 3: Consolidate response handling ✅ Complete

### [SANS_IO_IMPLEMENTATION_PLAN2.md](SANS_IO_IMPLEMENTATION_PLAN2.md)
**Detailed plan** for eliminating sync/async duplication through the operations layer.

### [PROTOCOL_LAYER_USAGE.md](PROTOCOL_LAYER_USAGE.md)
How to use the protocol layer for testing and low-level access.

### [GET_DAVCLIENT_ANALYSIS.md](GET_DAVCLIENT_ANALYSIS.md)
Analysis of `get_davclient()` factory function vs direct `DAVClient()` instantiation.

### [TODO.md](TODO.md)
Known issues and remaining work items.

## API Design Analysis

These documents contain design rationale for API decisions that remain relevant:

### [API_ANALYSIS.md](API_ANALYSIS.md)
Analysis of DAVClient API inconsistencies and improvement recommendations:
- Parameter naming standardization (`body` vs `props`/`query`)
- URL parameter handling (optional vs required)
- Method naming conventions

### [URL_AND_METHOD_RESEARCH.md](URL_AND_METHOD_RESEARCH.md)
Research on URL parameter semantics:
- Why query methods (`propfind`, `report`) have optional URL
- Why resource methods (`put`, `delete`) require explicit URL

### [ELIMINATE_METHOD_WRAPPERS_ANALYSIS.md](ELIMINATE_METHOD_WRAPPERS_ANALYSIS.md)
Analysis of `_query()` method and HTTP wrappers - decision to keep them for mocking and discoverability.

### [METHOD_GENERATION_ANALYSIS.md](METHOD_GENERATION_ANALYSIS.md)
Analysis of manual vs generated HTTP method wrappers - decision to use manual implementation.

## Code Style

### [RUFF_CONFIGURATION_PROPOSAL.md](RUFF_CONFIGURATION_PROPOSAL.md)
Proposed Ruff configuration for linting and formatting.

### [RUFF_REMAINING_ISSUES.md](RUFF_REMAINING_ISSUES.md)
Remaining linting issues to address.

## Historical Note

Some design documents from the exploration phase were removed in January 2026 after
the Sans-I/O approach was chosen. Removed documents covered the abandoned async-first-
with-sync-wrapper approach (phase plans, sync wrapper demos, performance analysis of
event loop overhead, etc.). The API analysis documents were kept as they contain design
rationale that remains relevant regardless of the implementation approach.
