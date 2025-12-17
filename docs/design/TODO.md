# Known Issues and TODO Items

## Nextcloud UNIQUE Constraint Violations

**Status**: Known issue, needs upstream investigation
**Priority**: Low (doesn't block caldav work)
**Estimated research time**: 6-12 hours

### Problem
Nextcloud occasionally gets into an inconsistent internal state where it reports UNIQUE constraint violations when trying to save calendar objects:

```
SQLSTATE[23000]: Integrity constraint violation: 19 UNIQUE constraint failed:
oc_calendarobjects.calendarid, oc_calendarobjects.calendartype, oc_calendarobjects.uid
```

### Observations
- **Server-specific**: Only affects Nextcloud, not Radicale, Baikal, Xandikos, etc.
- **Intermittent**: Happens during `caldav_server_tester.ServerQuirkChecker.check_all()`
- **Workaround**: Taking down and restarting the ephemeral Docker container resolves it
- **Hypothesis**: Internal state corruption in Nextcloud, not a caldav library issue
- **Pre-existing**: Test was already failing before starting to work on the async support

### Example Failure
```
tests/test_caldav.py::TestForServerNextcloud::testCheckCompatibility
E   caldav.lib.error.PutError: PutError at '500 Internal Server Error
E   <s:message>An exception occurred while executing a query: SQLSTATE[23000]:
    Integrity constraint violation: 19 UNIQUE constraint failed:
    oc_calendarobjects.calendarid, oc_calendarobjects.calendartype,
    oc_calendarobjects.uid</s:message>
```

### Hypothesis to Test
**Nextcloud may not allow deleting an object and then reinserting an object with the same UID later**
- This could explain the UNIQUE constraint violations if tests are deleting and recreating objects
- Easy to test: Create object with UID, delete it, try to recreate with same UID
- If confirmed, this is a Nextcloud limitation/bug that should be reported upstream

### Investigation Steps (when prioritized)
1. **Test the UID reuse hypothesis** (30 min - quick win)
   - Create simple test: create object with UID "test-123", delete it, recreate with same UID
   - Check if this reproduces the UNIQUE constraint violation
2. Search Nextcloud issue tracker for known UNIQUE constraint issues
3. Reproduce reliably with minimal test case from caldav_server_tester
4. Examine Nextcloud's CalDAV/SabreDAV code for UID and transaction handling
5. Understand why container restart fixes it (in-memory cache? transaction state?)
6. Create minimal reproduction outside caldav_server_tester
7. File upstream bug report with Nextcloud if confirmed as their issue

### References
- Test: `tests/test_caldav.py::TestForServerNextcloud::testCheckCompatibility`
- Discussion: Session on 2025-12-17

---

## Phase 2 Remaining Work

### Test Suite Status
- **Radicale**: 42 passed, 13 skipped ✓
- **Baikal**: Some tests passing after path/auth fixes
- **Nextcloud**: testCheckCompatibility failing (see above)
- **Other servers**: Status unknown

### Known Limitations (to be addressed in Phase 3)
- AsyncPrincipal not implemented → path matching warnings for Principal objects
- Async collection methods (event_by_uid, etc.) not implemented → no_create/no_overwrite validation done in sync wrapper
- Recurrence handling done in sync wrapper → will move to async in Phase 3

### Recently Fixed
- ✓ Infinite redirect loop in multiplexing retry
- ✓ Path matching assertion failures
- ✓ HTTPDigestAuth sync→async conversion
- ✓ UID generation issues
- ✓ Async class type mapping (Event→AsyncEvent, etc.)
- ✓ no_create/no_overwrite validation moved to sync wrapper
- ✓ Recurrence handling moved to sync wrapper
