# Ruff Remaining Issues for Async Files

Generated after initial Ruff setup on new async files (v2.2.2+).

## Summary

- **Total issues**: 20
- **Auto-fixed**: 13
- **Remaining**: 20 (some require manual fixes)

## Remaining Issues by Category

### 1. Type Annotation Modernization (UP006, UP035)
**Count**: 8 issues

Replace deprecated `typing` types with builtin equivalents:
- `Dict` → `dict`
- `List` → `list`
- `Tuple` → `tuple`

**Files**: `caldav/async_davclient.py`

**Action**: Can be fixed with `--unsafe-fixes` flag, or manually replace throughout the file.

### 2. Exception Handling (B904, E722)
**Count**: 4 issues

- **B904**: Use `raise ... from err` or `raise ... from None` in except clauses
- **E722**: Replace bare `except:` with specific exception types

**Files**: `caldav/async_davclient.py`

**Action**: Requires manual review to determine appropriate exception types.

### 3. String Formatting (UP031)
**Count**: 4 issues

Replace old `%` formatting with f-strings:
```python
# Old
log.debug("server responded with %i %s" % (r.status_code, r.reason))

# New
log.debug(f"server responded with {r.status_code} {r.reason}")
```

**Files**: `caldav/async_davclient.py`

**Action**: Can be auto-fixed with `--unsafe-fixes`.

### 4. Version Block (UP036)
**Count**: 1 issue

Remove outdated Python version check (since min version is 3.9):
```python
if sys.version_info < (3, 9):
    from collections.abc import Mapping
else:
    from collections.abc import Mapping
```

**Files**: `caldav/async_davclient.py`

**Action**: Simplify to unconditional import since we require Python 3.9+.

### 5. Missing Import (F821)
**Count**: 1 issue

Undefined name `niquests` in exception handler:
```python
self.session = niquests.AsyncSession()
```

**Files**: `caldav/async_davclient.py`

**Action**: Import `niquests` at module level (currently only imported in try/except).

### 6. Variable Redefinition (F811)
**Count**: 1 issue

`raw` defined as class variable and redefined as property:
```python
class AsyncDAVResponse:
    raw = ""  # Line 58

    @property
    def raw(self) -> str:  # Line 139 - redefinition
        ...
```

**Files**: `caldav/async_davclient.py`

**Action**: Remove the class-level `raw = ""` line (property is sufficient).

### 7. Missing Type Annotations (ANN003)
**Count**: 1 issue

Function signature missing type annotation for `**kwargs`:
```python
def aio_client(..., **kwargs,) -> AsyncDAVClient:
```

**Files**: `caldav/async_davclient.py`

**Action**: Add type annotation like `**kwargs: Any` or be more specific.

## Commands to Fix

### Auto-fix safe issues
```bash
ruff check --fix .
```

### Auto-fix with unsafe fixes (type replacements, formatting)
```bash
ruff check --fix --unsafe-fixes .
```

### Format code
```bash
ruff format .
```

## Recommendation

1. **Now**: Commit the Ruff config and auto-fixes already applied
2. **Next**: Fix remaining issues gradually, or all at once with:
   ```bash
   ruff check --fix --unsafe-fixes .
   ```
3. **Review**: Manually review exception handling (E722, B904) changes

## Notes

- These issues only apply to files added after v2.2.2
- Old/existing code is excluded from Ruff checks
- Can expand `include` list in `pyproject.toml` as more files are refactored
