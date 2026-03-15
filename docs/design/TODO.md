# Known Issues and TODO Items

## Calendar cleanup in integration tests

For servers where calendars cannot be created, the test will take the first available calendar it finds and wipe it.  That is not acceptable without the user explicitly configuring that this is OK.

## Nextcloud UNIQUE Constraint Violations

**Status**: Known issue, needs upstream investigation
**Priority**: Low (doesn't block caldav work)

### Problem
Nextcloud does not allow reusing a UID after deletion — the internal database retains the constraint even after the CalDAV object is deleted.  This causes intermittent UNIQUE constraint violation errors (500) when `ServerQuirkChecker.check_all()` deletes and recreates test objects with the same UID.

This violates CalDAV RFC expectations and is a Nextcloud bug.  Restarting the Docker container resolves it by clearing internal state.

### Next Steps
1. Search Nextcloud issue tracker for similar reports
2. File upstream bug report with reproduction steps
3. Consider adding server quirk detection in caldav_server_tester
4. Document workaround: avoid UID reuse with Nextcloud, or restart container between test runs
