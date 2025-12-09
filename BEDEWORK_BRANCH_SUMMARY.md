# Summary: bedework branch vs master

The bedework branch contains **8 commits** with **+487/-130 lines** across 14 files.

## Commits in bedework branch (not in master)

1. `33f7097` - style and minor bugfixes to the test framework
2. `c29c142` - Fix testRecurringDateWithExceptionSearch to be order-independent
3. `0e0c4e7` - Fix auto-connect URL construction for ecloud with email username
4. `5746af4` - style
5. `eef9e42` - Add disable_fallback parameter to objects_by_sync_token
6. `00810b7` - work on bedework
7. `2e549c6` - Downgrade HTML response log from CRITICAL to INFO
8. `12d47ec` - Add Bedework CalDAV server to GitHub Actions test suite

## Key Differences

### 1. Bedework Server Support (Primary Goal)
- Added Bedework CalDAV server to GitHub Actions test suite
- New Docker test infrastructure: `tests/docker-test-servers/bedework/` with:
  - docker-compose.yml
  - start.sh and stop.sh scripts
  - README.md documentation
- GitHub Actions workflow updated to run tests against Bedework

### 2. Compatibility Hints Expansion (Major Changes)
**File**: `caldav/compatibility_hints.py` (+141/-130 lines)

New feature flags added:
- `save-load.event.timezone` - timezone handling support (related to issue #372)
- `search.comp-type` - component type filtering correctness
- `search.text.by-uid` - UID-based search support

Enhancements:
- Enhanced documentation and behavior descriptions for existing flags
- Refined server-specific compatibility hints for multiple servers
- Added deprecation notice to old-style compatibility flag list
- Fixed RFC reference (5538 → 6638 for freebusy scheduling)

### 3. Bug Fixes
- **ecloud auto-connect URL**: Fixed URL construction when username is an email address (`caldav/davclient.py`)
- **Order-independent tests**: Fixed `testRecurringDateWithExceptionSearch` to not assume result ordering (`tests/test_caldav.py`)
- **Log level**: Downgraded HTML response log from CRITICAL to INFO

### 4. New Features
- Added `disable_fallback` parameter to `objects_by_sync_token()` method (`caldav/collection.py`)

### 5. Test Suite Improvements
**Files modified**:
- `tests/test_caldav.py` (+173 lines changed) - Refactored for Bedework compatibility
- `tests/conf.py` (+43 lines) - Enhanced test configuration with Bedework-specific settings
- `tests/test_caldav_unit.py` (+36 lines) - New unit tests for ecloud auto-connect
- `tests/test_substring_workaround.py` (+6 lines) - Minor fixes
- `tox.ini` (+6 lines) - Test configuration updates

### 6. Search Functionality
**File**: `caldav/search.py` (+48 lines changed)
- Improved search robustness and server compatibility

## Files Changed Summary

```
.github/workflows/tests.yaml                       |  53 lines
caldav/collection.py                               |  13 lines
caldav/compatibility_hints.py                      | 141 lines
caldav/davclient.py                                |   8 lines
caldav/search.py                                   |  48 lines
tests/conf.py                                      |  43 lines
tests/docker-test-servers/bedework/README.md       |  28 lines (new)
tests/docker-test-servers/bedework/docker-compose.yml | 14 lines (new)
tests/docker-test-servers/bedework/start.sh        |  36 lines (new)
tests/docker-test-servers/bedework/stop.sh         |  12 lines (new)
tests/test_caldav.py                               | 173 lines
tests/test_caldav_unit.py                          |  36 lines
tests/test_substring_workaround.py                 |   6 lines
tox.ini                                            |   6 lines
```

**Total**: 14 files changed, 487 insertions(+), 130 deletions(-)

## Important Note

The bedework branch does **NOT** have the issue #587 bug (duplicate `sort_keys` parameter with invalid `*kwargs2` syntax) because the `search()` method in `caldav/collection.py` has been refactored differently than master. The problematic `kwargs2` pattern does not exist in this branch.
