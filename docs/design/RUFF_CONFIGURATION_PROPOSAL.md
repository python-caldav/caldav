# Ruff Configuration for Partial Codebase

## Goal

Apply Ruff formatting/linting only to new/rewritten async files while leaving existing code untouched.

## icalendar-searcher Configuration (Reference)

From `/home/tobias/icalendar-searcher/pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "ANN"]
ignore = ["E501", "ANN401"]

[tool.ruff.lint.isort]
known-first-party = ["icalendar_searcher"]
```

## Option 1: Include/Exclude Patterns (RECOMMENDED)

Use `include` or `extend-include` to specify which files Ruff should check:

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py39"  # caldav supports 3.9+

# Only apply Ruff to these files/directories
include = [
    "caldav/async_davclient.py",
    "caldav/async_davobject.py",
    "caldav/async_collection.py",
    "caldav/aio/*.py",           # If we use a submodule
    "tests/test_async_*.py",
]

# OR use extend-include to add to defaults
extend-include = ["*.pyi"]  # Also check stub files

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "ANN"]
ignore = [
    "E501",    # Line too long (handled by formatter)
    "ANN401",  # Any type annotation
]

[tool.ruff.lint.isort]
known-first-party = ["caldav"]
```

## Option 2: Exclude Patterns (Alternative)

Instead of listing files to include, exclude everything except new files:

```toml
[tool.ruff]
line-length = 100
target-version = "py39"

# Exclude everything except async files
extend-exclude = [
    "caldav/davclient.py",      # Exclude until rewritten
    "caldav/davobject.py",      # Exclude until rewritten
    "caldav/collection.py",     # Exclude until rewritten
    "caldav/calendarobjectresource.py",
    "caldav/search.py",
    "caldav/objects.py",
    "caldav/config.py",
    "caldav/discovery.py",
    "caldav/compatibility_hints.py",
    "caldav/requests.py",
    # Keep excluding old files...
]
```

**Problem with Option 2**: Harder to maintain - need to list every old file.

## Option 3: Directory Structure (CLEANEST)

Organize new async code in a separate directory:

```
caldav/
├── __init__.py
├── aio/                    # NEW: async module
│   ├── __init__.py
│   ├── client.py          # AsyncDAVClient
│   ├── davobject.py       # AsyncDAVObject
│   └── collection.py      # Async collections
├── davclient.py           # Old/sync code (no Ruff)
├── davobject.py           # Old code (no Ruff)
└── collection.py          # Old code (no Ruff)
```

Then configure Ruff:

```toml
[tool.ruff]
line-length = 100
target-version = "py39"

# Only apply to aio/ directory
include = ["caldav/aio/**/*.py", "tests/test_aio_*.py"]
```

**Advantages**:
- Very clear separation
- Easy to configure
- Easy to understand what's "new" vs "old"

**Disadvantages**:
- Different import structure
- May need to reorganize later

## Option 4: Per-File Ruff Control (For Gradual Migration)

Use `# ruff: noqa` at the top of files you don't want Ruff to check:

```python
# caldav/davclient.py (old file)
# ruff: noqa
"""Old davclient - excluded from Ruff until rewrite"""
...
```

Then Ruff applies to everything by default, but old files opt out.

## Recommended Approach for caldav

**Use Option 1 (Include Patterns)** with explicit file list:

### Phase 1: Initial Async Files

```toml
[tool.ruff]
line-length = 100
target-version = "py39"

# Explicitly list new async files
include = [
    "caldav/async_davclient.py",
    "caldav/async_davobject.py",
    "caldav/async_collection.py",
    "tests/test_async_davclient.py",
    "tests/test_async_collection.py",
]

[tool.ruff.lint]
# Based on icalendar-searcher config
select = [
    "E",    # pycodestyle errors
    "F",    # pyflakes
    "W",    # pycodestyle warnings
    "I",    # isort
    "UP",   # pyupgrade (modernize code)
    "B",    # flake8-bugbear (find bugs)
    "ANN",  # type annotations
]
ignore = [
    "E501",    # Line too long (formatter handles this)
    "ANN401",  # Any type (sometimes necessary)
]

[tool.ruff.format]
# Use Ruff's formatter (Black-compatible)
quote-style = "double"
indent-style = "space"

[tool.ruff.lint.isort]
known-first-party = ["caldav"]
```

### Phase 2: After Sync Wrapper Rewrite

Add the rewritten sync files:

```toml
include = [
    # Async files
    "caldav/async_davclient.py",
    "caldav/async_davobject.py",
    "caldav/async_collection.py",
    # Rewritten sync wrappers
    "caldav/davclient.py",          # Added after rewrite
    # Tests
    "tests/test_async_*.py",
    "tests/test_davclient.py",      # Added after rewrite
]
```

### Phase 3+: Gradually Expand

As other files are refactored, add them to the `include` list.

## Integration with pre-commit (Optional)

From icalendar-searcher's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.4  # Use latest version
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

This will:
1. Auto-fix issues Ruff can fix
2. Format code on commit
3. Only run on files in `include` list

## Commands

```bash
# Check files (no changes)
ruff check caldav/async_davclient.py

# Fix issues automatically
ruff check --fix caldav/async_davclient.py

# Format files
ruff format caldav/async_davclient.py

# Check all included files
ruff check .

# Format all included files
ruff format .
```

## Summary

**Recommendation**: Use **Option 1 with explicit `include` list** in `pyproject.toml`:

✅ Clear control over which files use Ruff
✅ Easy to expand as files are refactored
✅ No risk of accidentally formatting old code
✅ Works with pre-commit hooks
✅ Can run `ruff check .` safely (only checks included files)

Start minimal (just async files) and expand as needed.
