# Known Issues and TODO Items

## Server-side negated searches

`search()` decides the `!=` / `<>`, `!contains` and `def` operators client-side and leaves them out of the server query (https://github.com/python-caldav/caldav/issues/568).  A caldav-server-tester probe for `negate-condition` support, and the compatibility_hints flag it would feed, would let `search()` send `!contains` as a negated `text-match` to the servers that honour it.

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

## `towncrier check` in CI

towncrier was set up after 3.5.0 (`changes/README.md`).  Not done: a CI job running `towncrier check` on pull requests (with `--compare-with origin/master`, as towncrier defaults to `origin/main`), so that a missing changelog fragment is caught.  It needs a way to skip test/docs-only pull requests, which need no entry (e.g. a `no-changelog` label), and should not be enabled before the open pull requests have been moved to fragments.  Note that `towncrier check` also passes when `CHANGELOG.md` itself was edited, so it does not catch a pull request that still edits it directly.  Also consider `sphinxcontrib-towncrier`, as from 3.5.0 on there is no "Unreleased" section in `CHANGELOG.md`.

## An error response with a non-XML body labelled as XML

A response whose `Content-Type` says XML but whose body is not XML (an HTML error page sent as `application/xml`) makes `DAVResponse.__init__` raise an lxml parse error, on any status.  The caller never gets the `DAVError` (with `body` and `preconditions`, https://github.com/python-caldav/caldav/issues/756) that the status calls for.  Only the async client's 401/403 path was fixed (https://github.com/python-caldav/caldav/issues/738).  Fix: tolerate a parse failure on a 4xx/5xx response and keep the raw body.  Found in the review of the #756 fix.

## Search-cache delay misses writes from other clients

`tests/search_cache_delay.py` only resets its clock on writes through the one wrapped client.  Writes through another `DAVClient` in the same test (e.g. the scheduling users' clients) are not counted, so a filtered search right after one may wait less than the server's cache lag, and get flaky on servers like Purelymail or Bedework.  Fix: wrap `DAVClient.request` at class level for the duration of the test, or document the limitation.  Found in the review of https://github.com/python-caldav/caldav/pull/776.

## A waiting session-lock claim blocks other threads

`TestServer.claim_server()` in `tests/test_servers/base.py` polls for the flock (up to `PYTHON_CALDAV_TEST_SERVER_LOCK_TIMEOUT`, 30 minutes by default) while holding the module-wide `_session_locks_mutex`.  A thread waiting for one busy server therefore blocks every other thread claiming a different server, which contradicts "runs against different servers proceed in parallel".  Harmless for single-threaded pytest.  Fix: hold the mutex only around the `_session_locks` checks and inserts, with a per-name lock against double claims.  Found in the review of https://github.com/python-caldav/caldav/pull/776.
