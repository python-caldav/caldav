# Code Review: Niquests

*Review date: 2026-01-31*

## Overview

Niquests is a modern HTTP client library for Python that serves as a drop-in replacement for the Requests library. It maintains API compatibility with Requests while adding advanced features like HTTP/2, HTTP/3 over QUIC, async/await support, and enterprise-grade security features.

**Key Stats:**
- 41 Python modules in main source
- 23 test files
- Version: 3.17+ (Production Ready)
- Python Support: 3.7+ (including Python 3.14 and PyPy)

---

## Strengths

### 1. Clean Architecture

Well-separated sync/async stacks with parallel class hierarchies. The adapter pattern allows for flexible transport customization.

```
Public API Layer (api.py / async_api.py)
         │
         ▼
Session Classes (Session / AsyncSession)
         │
         ▼
Adapter Classes (HTTPAdapter / AsyncHTTPAdapter)
         │
         ▼
Request/Response Classes (Request, PreparedRequest, Response, AsyncResponse)
```

### 2. Type Safety

Extensive use of type hints with `TypeAlias` and `@overload` decorators. Strict mypy configuration enforces correctness.

### 3. Backward Compatibility

Maintains full Requests API compatibility while adding modern features - a smart migration path for users.

### 4. Comprehensive Test Suite

23 test files covering unit tests, integration tests, and live network tests. Good coverage of edge cases.

### 5. Modern Python Practices

Uses `from __future__ import annotations`, lazy imports, contextvars for thread/task safety.

---

## Areas for Improvement

### 1. `_compat.py` - Consider consolidating compatibility logic

The urllib3/urllib3_future detection is complex. Consider documenting the decision tree more explicitly.

### 2. `models.py` - Large file (~1600+ lines)

Contains `Request`, `PreparedRequest`, `Response`, and `AsyncResponse`. Could potentially be split into `request.py` and `response.py` for maintainability.

### 3. Duplicate code patterns in sync/async

`HTTPAdapter` and `AsyncHTTPAdapter` share significant logic. Consider a mixin or base class to reduce duplication. Same applies to `Session` vs `AsyncSession`.

### 4. Hook system complexity

`hooks.py` handles both sync and async dispatch with runtime detection. The `iscoroutinefunction` checks add overhead. Consider documenting performance implications.

### 5. Exception hierarchy

`exceptions.py` has many exception types. Some inherit from multiple bases (e.g., `SSLError` from both `ConnectionError` and `IOError`). The hierarchy could be documented better.

---

## Minor Issues

| File | Issue |
|------|-------|
| `sessions.py:474` | `hasattr(app, "__call__")` - all callables have `__call__`, consider `callable(app)` |
| `models.py` | Multiple `# type: ignore` comments - could benefit from more specific ignores |
| `utils.py` | Large utility file - consider splitting by domain (url utils, auth utils, etc.) |

---

## Security Considerations

- **Good**: OS truststore by default (no outdated certifi bundles)
- **Good**: OCSP/CRL support for certificate revocation
- **Good**: No eval/exec usage found
- **Note**: `trust_env=True` reads `.netrc` - documented but worth highlighting in security docs

---

## Recommendations

1. **Documentation**: Add architecture diagrams to docs showing the sync/async class relationships
2. **Deprecation tracking**: Consider a `DEPRECATIONS.md` file tracking Python version-specific changes
3. **Performance benchmarks**: Add benchmarks comparing sync/async and HTTP/1.1 vs HTTP/2 vs HTTP/3

---

## Conclusion

Overall, this is a well-maintained, production-ready codebase with thoughtful design choices. The Python 3.14+ compatibility work demonstrates active maintenance.
