# Code Review: urllib3.future

*Review date: 2026-01-31*

## Overview

urllib3.future is an advanced fork of urllib3 - a powerful, user-friendly HTTP client for Python with native support for HTTP/1.1, HTTP/2, and HTTP/3 protocols.

**Key Statistics:**
- ~35,756 LOC in src/urllib3
- 70 test files (59 actual test modules)
- Python Support: 3.7+ (including CPython and PyPy)
- Dependencies: h11 (HTTP/1.1), jh2 (HTTP/2), qh3 (HTTP/3/QUIC)

---

## Strengths

### 1. Comprehensive Protocol Support

- Clean abstraction over HTTP/1.1 (h11), HTTP/2 (jh2), and HTTP/3 (qh3)
- Transparent ALPN negotiation - users don't need to explicitly configure protocols
- Alt-Svc header handling for automatic HTTP/3 upgrades

### 2. Sophisticated Connection Pooling

- `TrafficPolice` custom queue handles HTTP/2+ multiplexing correctly
- `ResponsePromise` for lazy/deferred responses enables true concurrency
- Background keep-alive management prevents stale connections

### 3. Advanced DNS Resolution

- Pluggable resolver architecture (DOH, DOQ, DOT, DOU, system, manual)
- Async variants for all resolvers
- DNSSEC support

### 4. Backward Compatibility

- Drop-in urllib3 replacement (version 2.x.9PP scheme)
- Maintains API compatibility while extending functionality

### 5. Good Test Infrastructure

- Traefik-based integration tests with real HTTP/2 and HTTP/3
- Downstream compatibility tests (requests, niquests, boto3)
- 70 test files covering protocols, concurrency, and edge cases

---

## Areas of Concern

### 1. TrafficPolice Complexity (`util/traffic_police.py` - 1,014 LOC)

This is the most critical and complex component:

```python
# Complex state management:
class TrafficState(IntEnum):
    IDLE = 0      # Connection available
    USED = 1      # Active streams (HTTP/2)
    SATURATED = 2 # At max streams
```

**Issues:**
- Very difficult to reason about correctness
- Custom synchronization primitives (`PendingSignal`, `ActiveCursor`)
- No formal state machine documentation
- Risk of subtle race conditions

**Recommendation:** Add state machine diagrams and consider formal verification or extensive fuzz testing.

### 2. Large Monolithic Classes

| Class | LOC | Concern |
|-------|-----|---------|
| `HTTPConnectionPool` | 2,402 | Connection lifecycle, pooling, retries all in one |
| `HfaceBackend` | 1,838 | Protocol negotiation, ALPN, upgrade logic |
| `PoolManager` | 1,158 | Pool caching, routing, proxy handling |
| `AsyncHTTPResponse` | 20,229 | Extremely large - needs investigation |

**Recommendation:** Consider extracting focused classes (e.g., `ConnectionLifecycle`, `ProtocolNegotiator`, `PoolCache`).

### 3. Technical Debt (16 items found)

```python
# Examples from codebase:
"TODO(t-8ch): Stop inheriting from AssertionError in v2.0"  # ProxySchemeUnknown
"TODO: Remove this when we break backwards compatibility"   # URL handling
"FIXME: Can we do this without accessing private httplib _method?"
"FIXME: Is there a better way to differentiate between SSLErrors?"
```

**Recommendation:** Create a v3.0 roadmap to address these without breaking current compatibility.

### 4. Sync/Async Code Duplication

The async implementation is a near-complete mirror:

```
connection.py (1,130 LOC)     →  _async/connection.py (1,096 LOC)
connectionpool.py (2,402 LOC) →  _async/connectionpool.py (2,440 LOC)
poolmanager.py (1,158 LOC)    →  _async/poolmanager.py (1,005 LOC)
```

**Issues:**
- Maintenance burden - changes must be made twice
- Risk of drift between implementations
- ~7,000 LOC of near-duplicate code

**Recommendation:** Consider:
- Shared base classes with sync/async method variants
- Code generation from a single source
- Template-based approach (like aiofiles uses)

### 5. Circular Dependency Risk

```
util/ imports from backend
backend imports from util
contrib modules have interdependencies
```

Heavy use of `TYPE_CHECKING` blocks indicates this is already causing issues:

```python
if typing.TYPE_CHECKING:
    from .connection import HTTPConnection  # Avoid circular import
```

---

## Security Considerations

| Area | Status | Notes |
|------|--------|-------|
| TLS validation | Good | Proper certificate validation by default |
| ALPN negotiation | Good | Secure protocol selection |
| Fingerprint pinning | Good | Supported |
| Environment variables | Warning | `SSHKEYLOGFILE`, `QUICLOGDIR` should warn in production |
| Proxy auth headers | Good | `NOT_FORWARDABLE_HEADERS` filtering |
| DNS security | Good | DOH/DOQ/DOT options available |

---

## Specific Code Issues

1. **Exception inheritance oddity** (`exceptions.py`):
   ```python
   class ProxySchemeUnknown(AssertionError, ValueError):
       # TODO(t-8ch): Stop inheriting from AssertionError in v2.0
   ```

2. **Private API access** (`response.py`):
   ```python
   # FIXME: Can we do this without accessing private httplib _method?
   ```

3. **`AsyncHTTPResponse` at 20,229 LOC** - This needs investigation. Either it's including generated code, or there's significant complexity that should be refactored.

---

## Recommendations

### Priority 1: Critical

1. **Audit TrafficPolice** - Add comprehensive documentation and state machine diagrams
2. **Investigate AsyncHTTPResponse size** - 20K LOC for a response class is unusual
3. **Add race condition testing** - Fuzz testing for connection pool

### Priority 2: Maintainability

1. **Reduce code duplication** between sync/async
2. **Break up large classes** into focused components
3. **Address technical debt** - Plan v3.0 breaking changes

### Priority 3: Documentation

1. **Architecture overview** with diagrams
2. **Protocol negotiation flowchart**
3. **TrafficPolice state machine documentation**

---

## Project Structure

```
src/urllib3/
├── Core modules (sync):
│   ├── connection.py (1,130 LOC)
│   ├── connectionpool.py (2,402 LOC)
│   ├── poolmanager.py (1,158 LOC)
│   ├── response.py (1,086 LOC)
│   └── backend/
│       ├── _base.py (682 LOC) - Abstract base classes
│       ├── hface.py (1,838 LOC) - Main protocol handler
│       └── _async/ - Async equivalents
├── _async/ - Complete async mirror
├── contrib/ - Extensions:
│   ├── hface/ - HTTP protocol implementations
│   │   └── protocols/ (http1, http2, http3)
│   ├── resolver/ - Advanced DNS resolution
│   │   ├── doh/ - DNS over HTTPS
│   │   ├── doq/ - DNS over QUIC
│   │   ├── dot/ - DNS over TLS
│   │   └── dou/ - DNS over UDP
│   ├── webextensions/ - WebSocket, SSE
│   ├── socks.py - SOCKS proxy support
│   └── pyopenssl.py - OpenSSL backend
├── util/ - Utilities
│   ├── traffic_police.py (1,014 LOC)
│   ├── ssl_.py (864 LOC)
│   ├── timeout.py
│   └── retry.py (558 LOC)
└── exceptions.py - 30+ exception types
```

---

## Conclusion

urllib3.future is an ambitious and feature-rich HTTP client with excellent protocol support. The main concerns are:

- **Complexity** in `TrafficPolice` and protocol negotiation
- **Maintainability** due to large classes and sync/async duplication
- **Technical debt** accumulated from maintaining backward compatibility

The codebase is well-tested and shows good defensive programming practices, but would benefit from architectural documentation and potential refactoring of the largest components.
