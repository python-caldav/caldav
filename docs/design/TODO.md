# Known Issues and TODO Items

## Server-side negated searches

`search()` decides the `!=` / `<>`, `!contains` and `def` operators client-side and leaves them out of the server query (https://github.com/python-caldav/caldav/issues/568).  A caldav-server-tester probe for `negate-condition` support, and the compatibility_hints flag it would feed, would let `search()` send `!contains` as a negated `text-match` to the servers that honour it.

## Completing an all-day fixed-time recurring task

`Todo._next()` in `caldav/calendarobjectresource.py` raises `TypeError` (naive vs aware) for a task with `DTSTART;VALUE=DATE` and `BY*` parts in its `RRULE`: dateutil turns the date into a naive datetime and compares it with the UTC completion timestamp, so `complete(handle_rrule=True)` fails for such tasks.  Fix: convert a date DTSTART to an aware datetime (or the timestamp to a date) before both the comparison and `rrulestr()`, with a unit test.  Found in the review of the fix for https://github.com/python-caldav/caldav/issues/782.

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

## calendar_multiget() fails on an async client

`Calendar.calendar_multiget()` in `caldav/collection.py` does `list(self.multiget(...))`, but `multiget()` returns a coroutine for an async client, so the call raises `TypeError`.  `calendar_multiget()` has no return annotation, so a type checker does not catch it.  Fix: return `self.multiget(...)` for an async client (or annotate it like `multiget()`), with an async unit test.  Found in the review of the fix for https://github.com/python-caldav/caldav/issues/799.

## The UID-conflict check compares URLs as strings

`save(no_overwrite=True)` in `caldav/calendarobjectresource.py`, when caldav searches for the UID itself, compares the found object's URL with the target URL as plain strings (`existing.url != target`).  A server that returns the object's own URL spelled differently (`%40` against `@`, or a canonicalised URL, as OX does) gets it reported as `UidConflictConsistencyError` instead of a plain `ConsistencyError`.  Harmless for `except ConsistencyError`, as it is a subclass.  Fix: compare normalised URLs.  Found in the review of https://github.com/python-caldav/caldav/pull/807.

## iCloud misses a moved recurrence by its new date

iCloud leaves a moved instance (`RECURRENCE-ID` 2026-10-31, `DTSTART` 2026-10-17) out of a time-range search that covers only the new date, against RFC 4791 sections 7.4 and 9.9 (https://github.com/python-caldav/caldav/issues/784).  Suggested fix:

* Two new features, with a check in caldav-server-tester (one series, its first instance moved weeks earlier, searched on the new date and on the original one).  A moved instance is an override with its own `RECURRENCE-ID`, not an implicit RRULE instance, so it goes under `search.recurrences.exception` rather than `includes-implicit`:
  * `search.recurrences.exception.by-moved-dt`: found by a time-range search over its new `DTSTART`.  `unsupported` for iCloud once the check confirms it.  Other servers may well fail it too.
  * `search.recurrences.exception`: `quirk` for iCloud, as the instance can still be found, by its `RECURRENCE-ID`.
* Workaround when `by-moved-dt` is unsupported: an extra query for VEVENTs that have a `RECURRENCE-ID`.  In CalDAV that is an empty `prop-filter` (RFC 4791 section 9.7.2; there is no `is-defined` element).  `search()` decides `def` client-side and leaves it out of the server query, so the filter must be sent server-side (`post_filter=False`, or a raw query), or the extra query fetches every event.  Filter the results client-side and merge them in, deduplicated on the resource URL, or on UID and `RECURRENCE-ID` when the search expands.  The `_TIME_RANGE_MARGIN` widening can't do it, as an instance may be moved any distance.  The tester check should probe the empty prop-filter on iCloud directly (`search.is-not-defined` being `fragile` there says little about it); else fall back to fetching all recurring events.
* Cost: without a time range, the extra query downloads every event with overrides in the calendar, on every event time-range search, and that grows without bound.  Bound it (a range covering the RRULE horizon) or cache it, and make it opt-out.  Report it to Apple too.
* The reporter (Home Assistant, https://github.com/home-assistant/core/issues/179125) offered to test.
