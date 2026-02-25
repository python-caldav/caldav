# Known Issues and TODO Items

## Calendar creation/location in integration tests

* Currently there is quite some logic for the sync integration tests for fixing calendars (`test_caldav.py`).  All boilerplate should be moved to the `fixture_helper.py` file - or simply removed if it's irrelevant.
* In the `fixture_helpers.py` there is an `aget_or_create_test_calendar` and a `get_or_create_test_calendar`.  There is quite much duplicated logic here.  Work should be done to consolidate common code.
* If the default calendar already exists, make sure to delete and recreate or wipe it (dependent on relevant features supported/configured) to avoid pollution from old test runs fouling the new test run.

## Calendar cleanup in integration tests

Calendar cleanup in the integration tests is a bit of a mess and should be cleaned up.  Also, the sync and async integration code now have different code paths, that's not acceptable, that should be cleaned up.

Currently unsupported scenarios:

* Test run towards read-only calendars (there exists service providers that have a partial caldav interface for read-only access to a calendar) ... maybe a future feature, but as for now it doesn't really work out, so let's ignore this possibility as for now.
* Test runs towards a calendar that already has data in it, and without deleting the data in the calendar.  I had the idea to allow this, but ... no, it doesn't work out, and let's keep it that way.  BUT: currently, for servers where calendars cannot be created, the test will take the first available calendar it finds and wipe it.  That's also not acceptable, not without the user explicitly confguring that this is OK.

Server compatibility to consider:

* Some servers disallows calendar creation.
* On some servers calendar creation is not reliable (i.e. quota for how many calendars one can have.  Workaround: manual creation of test calendar and explicitly specifying what calendar to use in the configuration).
* On some servers calendar deletion is not possible or not reliable.  (i.e. calendar "moved" to thrash bin rather than deleted).
* On some servers, objects on the calendar are "sticky", not fully deleted (and is polluting the UID name space) even if the calendar is deleted. (perhaps due to the thrash-bin-issue above)
* Sometimes separate calendars has to be used for tasks, events and journals.
* In some situations the user may want to point testing towards one (or several) specific calendars - either due to the issues above or for other reasons

There are also different modes of cleanup:

* Wipe all "known objects", objects created by the tests (old "through" mode, it was needed for running tests towards existing production calendars without wiping the original content - but now I've decided not to support this.  It may be needed if having problems with "sticky" events, but probably better to just "wipe" the calendar).
* Wiping the calendar after every test (like, take out the list of objects, and delete every single event - `[x.delete() for x in calendar.search()]`)
* Deleting the whole calendar after every test.
* Do the same before every test

The first option is needed if one wants to run the tests towards a "live" calendar without deleting content on the live calendar.  Since this is anyway not supported, I think this code may as well be yanked out.

Deleting a calendar is much faster than deleting every item on the calendar.  However, for "sticky" objects wiping is necessary.  For calendars not supporting calendar deletion, a "delete"-operation towards a calendar will automatically wipe it.

Probably test cleanups should be done after the server run, but also before if needed.

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

### Test Results: Hypothesis CONFIRMED ✓

**Date**: 2025-12-17
**Test script**: `/tmp/test_nextcloud_uid_reuse.py`

**Finding**: Nextcloud does NOT allow reusing a UID after deletion. This is a **Nextcloud bug**.

**Test steps**:
1. Created event with UID `test-uid-reuse-hypothesis-12345` ✓
2. Deleted the event ✓
3. Confirmed deletion with `get_event_by_uid()` (throws NotFoundError) ✓
4. Attempted to create new event with same UID → **FAILED with UNIQUE constraint** ✗

**Error received**:
```
500 Internal Server Error
SQLSTATE[23000]: Integrity constraint violation: 19 UNIQUE constraint failed:
oc_calendarobjects.calendarid, oc_calendarobjects.calendartype, oc_calendarobjects.uid
```

**Conclusion**:
- This violates CalDAV RFC expectations - UIDs should be reusable after deletion
- Nextcloud's internal database retains constraint even after CalDAV object is deleted
- This explains why `ServerQuirkChecker.check_all()` fails - it likely deletes and recreates test objects
- Container restart fixes it because it clears the internal state

### Next Steps (when prioritized)
1. ✓ ~~Test the UID reuse hypothesis~~ - **CONFIRMED**
2. Search Nextcloud issue tracker for similar reports
3. Create minimal bug report with reproduction steps
4. File upstream bug report with Nextcloud
5. Consider adding server quirk detection in caldav_server_tester
6. Document workaround: avoid UID reuse with Nextcloud, or restart container between test runs

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
- Async collection methods (get_event_by_uid, etc.) not implemented → no_create/no_overwrite validation done in sync wrapper
- Recurrence handling done in sync wrapper → will move to async in Phase 3

### Known Test Limitations

#### MockedDAVClient doesn't work with async delegation
**Status**: Known limitation in Phase 2
**Affected test**: `tests/test_caldav_unit.py::TestCalDAV::testPathWithEscapedCharacters`

MockedDAVClient overrides `request()` to return mocked responses without network calls.
However, with async delegation, `_run_async()` creates a new async client that makes
real HTTP connections, bypassing the mock.

**Options to fix**:
1. Make MockedDAVClient override `_get_async_client()` to return a mocked async client
2. Update tests to use `@mock.patch` on async client methods
3. Implement a fallback sync path for mocked clients

**Current approach**: Raise clear NotImplementedError when mocked client tries to use
async delegation, documenting that mocking needs to be updated for async support.

### Recently Fixed
- ✓ Infinite redirect loop in multiplexing retry
- ✓ Path matching assertion failures
- ✓ HTTPDigestAuth sync→async conversion
- ✓ UID generation issues
- ✓ Async class type mapping (Event→AsyncEvent, etc.)
- ✓ no_create/no_overwrite validation moved to sync wrapper
- ✓ Recurrence handling moved to sync wrapper
- ✓ Unit tests without client (load with only_if_unloaded)
- ✓ Mocked client detection for unit tests (testAbsoluteURL)
- ✓ Sync fallback in get_properties() for mocked clients
