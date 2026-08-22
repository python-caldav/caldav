# Changelog

## HTTP Library Dependencies

See also the documentation: [HTTP Library Configuration](docs/source/http-libraries.rst).

**niquests** is now the officially supported and recommended library for HTTP communication.  Some consumers would rather avoid having to drag in this extra dependency, hence fallbacks to httpx2 and requests have been implemented.  To allow consumers to add the caldav dependency without pulling in niquests, it has been decided to ship the caldav library with niquests as an *optional* dependency.  Going forward, it's recommended to depend on `caldav[niquests]` rather than just `caldav`.

This is a breaking change which will be introduced for good in version 4.0, but you are encouraged to change your dependency to `caldav[niquests]` already now.

Starting from 3.3.0, releases will be done in pairs: every *even* patch-release will come *without* any http-library dependency, while every *odd* patch-release will come *with* niquests in the dependency list.  Hence:
  * Consumers that don't want to drag in the niquests dependency may pin the caldav version to the latest even patch version.
  * Consumers that just depend on "the latest caldav version", will get an odd version and get niquests in the dependency list.  (Except, there is a risk that some project gets built just during an ongoing release process and will be stuck with an even version and no http-library - so please use the `caldav[niquests]`-dependency already today).

## Meta

This file should adhere to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), but I frequently add some sections in it.

Changelogs prior to v3.0 is pruned, but was available in the v3.1 release

This project should adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html), though for pre-releases PEP 440 takes precedence.

## [Unreleased]

This release is dominated by bug fixes.  A full code review of the codebase was
done in June 2026, and most of the findings from it are fixed here.

### Breaking changes

* **JMAP (experimental):** `get_objects_by_sync_token()` now returns a 4-tuple `(added, modified, deleted, new_sync_token)` rather than a 3-tuple.  The new sync token used to be thrown away, so chaining sync calls required an extra `get_sync_token()` round-trip - and any change landing in between was silently missed.  The JMAP API is still experimental and may keep changing.

### Added

* The async client can now use **httpx2** - Pydantic's continuation of httpx - as its HTTP library.  The async fallback chain is niquests, httpx2, httpxyz, then httpx; the first one installed wins, and niquests remains the default and the recommended choice.  httpx2 is a separate module rather than a new httpx release, so `pip install httpx2` is what enables it.  The httpx family is still not supported in *sync* mode.  See https://github.com/python-caldav/caldav/issues/611
* `caldav[niquests]` is now a valid install target, and the recommended way to depend on caldav from now on.  Requested in https://github.com/python-caldav/caldav/issues/690.  It changes nothing for a 3.3.0 install, but from 3.3.1 onwards `niquests` is only pulled in by odd patch-releases, and v4.0 drops it as a default dependency altogether - see *HTTP Library Dependencies* at the top of this file.  Depend on `caldav[niquests]` now and nothing changes for you later.  See https://github.com/python-caldav/caldav/issues/611
* JMAP clients now keep a persistent HTTP session instead of doing a fresh TCP+TLS handshake per call.  `JMAPClient` and `AsyncJMAPClient` can be used as (async) context managers, or closed explicitly with `close()` / `await aclose()`.
* Research on the Infomaniak calendar-as-a-service has been done, and `features='infomaniak'` will enable quirks for it.
* New `compatibility_workarounds=False` option on `Calendar.search()` and `async_search()`, sending the query verbatim with every server workaround disabled.  Mainly for the server-compatibility checker, to observe raw server behaviour.
* `caldav.config.extract_conn_params_from_section` is now public API (renamed from `_extract_conn_params_from_section`), so downstream tools like plann can map their own config sections to `DAVClient` parameters without duplicating the logic.
* New compatibility feature `create-calendar.stable-url`: whether a calendar stays addressable at the URL derived from `cal_id` after creation.  Zimbra and OX App Suite assign a different canonical URL; against those servers a newly created calendar now adopts the canonical URL, so it keeps its display name *and* remains reachable for every later operation.  Previously the display name was dropped instead.

### Fixed

#### Searching

* Time-range searches (`search(start=..., end=...)`) and property-filter searches (`search(category=...)`) with no `event`/`todo`/`journal`/`comp_class` failed towards some servers and silently returned nothing on others, and the misunderstanding of the RFC was on my side.  See https://github.com/python-caldav/caldav/issues/681 for details.
* `search(..., operator='==')` did not give the documented exact match - the server's substring semantics leaked through.
* `add_property_filter(..., operator='undef')` on `category` silently returned *all* objects instead of those without categories.
* A search combining a time range with a property filter returned everything in the time range, dropping the property filter, on servers needing the `search.combined-is-logical-and` workaround (e.g. Nextcloud).
* Some server-compatibility workarounds did not work as intended.
* Results from a component-type split are deduplicated by URL, since a resource holding both a `VEVENT` and a `VTODO` matches more than one query.

#### Calendars, objects and connections

* Looking up a calendar or object that does not exist now raises `NotFoundError` also when the server reports the 404 inside a `207 Multi-Status` instead of as a plain HTTP 404.  Previously e.g. `calendar.get_display_name()` on a non-existent calendar silently returned `None` with some servers, while `calendar.get_events()` on the same calendar raised.  Observed against Xandikos.
* A response body containing no iCalendar at all - an empty object, an HTML error page served with a 200 - now raises `caldav.lib.error.ResponseError` naming the URL and quoting what arrived, instead of an opaque `ValueError` from inside the icalendar library.
* Reading an object again after `load()` could serve the stale, pre-reload content.
* A `FreeBusy` object holding raw data was mis-detected as empty, so `save()` silently did nothing and `load(only_if_unloaded=True)` refetched on every call.
* A `302` response to a `PUT` raised `IndexError` instead of following the redirect.
* A calendar with empty display name would be dropped from `get_calendars()`
* Comparing two `URL` objects could leak credentials into the compared value, so an authenticated client URL never compared equal to a server-returned href.  Comparing or hashing a URL could also mutate it in place and make later requests target the wrong resource.
* `change_attendee_status()` raised a bare `KeyError` instead of `NotFoundError` on an event with no attendees, making the "principal is not invited" error unreachable; the error message also contained an unsubstituted `%s`.
* `add_attendee("MAILTO:someone@example.com")` crashed - URI schemes are case-insensitive.
* Completing a recurring task ignored the `completion_timestamp` argument and recorded the current time instead (sync client only).
* Completing a recurring VTODO with a timed `DTSTART` but no `DUE`/`DURATION` moved the next due date one day too far.
* Rate-limit retries crashed with a `TypeError` on the second `429` from a server that sends no usable `Retry-After`.
* `DAVClient(url='https://user@host/', password='secret')` crashed.  URL-embedded credentials also silently overrode explicit `username`/`password` arguments; explicit arguments now win, matching the async client.
* On async clients, `freebusy_request()` crashed when passed a `Principal` as attendee.
* On async clients, `principal.calendar(cal_id=...)` / `calendar(name=...)` crashed for a bare (non-URL) id or name.  A full URL still resolves without a server round-trip.
* On async clients, `get_calendars(calendar_name=...)` always returned nothing.
* On async clients, `get_calendars()` lacked the GMX fallback of using the principal URL as calendar home when `calendar-home-set` is missing, returning an empty list instead.
* On async clients, a connection abort could be silently swallowed and the wrong response returned in its place.
* The "server returned an HTML login page, consider setting auth_type" hint could never fire.
* A `WWW-Authenticate` header ending with a trailing comma (seen in the wild) raised `IndexError`.

#### Configuration

* `caldav.get_calendars()` crashed with `KeyError: 'default'` on a config with no `default` section.
* An unreadable config-file location - typically `$HOME` being unset, as in a Nix build sandbox - propagated an `OSError` out of what is an optional probe, breaking `get_davclient()`.  Thanks to @betaboon.
* `disable: true` was ignored for config sections fetched by explicit name or through a `contains` list.
* Explicit arguments such as `get_davclient(password='secret')` were silently dropped whenever the connection details came from an environment variable or a config file.  They are now overlaid on top of whatever source wins.  An argument that is `None` counts as "not supplied", so the common `get_davclient(url=args.url, username=args.user, password=args.password)` wrapper no longer wipes `CALDAV_URL` when only `--password` was given.
* Config sections with `features` but no `caldav_url` were rejected, even though the URL can be derived from the `auto-connect.url` compatibility hints.
* Using a named feature profile (`features='xandikos'`) handed out the shared profile dict itself, so anything mutating it corrupted every later client in the same process.

#### iCalendar handling

* A `COMPLETED` property stored as a plain date (e.g. by SOGo) swallowed the following line on every inbound object.
* Supplying both `alarm_*` properties and an `ical_fragment` placed the fragment inside the alarm rather than in the event.
* Trailing whitespace is now stripped per line rather than only at the end of the document - but deliberately not before a folded continuation line, where the space may belong to the value.
* A backslash before a lone `'` or `"` was left in place instead of being unescaped.
* Truncated iCalendar data (no `END:` line) hit a bare assertion, which gave no useful message and was skipped entirely under `python -O`.  It now logs a warning and returns the data unchanged.

#### JMAP (experimental)

* `update_event()` did not remove properties the caller had removed - a dropped `LOCATION` or `VALARM` silently survived on the server.  It now nulls absent properties explicitly, and copes with servers (observed with Stalwart) that reject a null for a property they do not support.
* An override that only changes e.g. the title was relocated to the master event's first occurrence, breaking display of every such override.
* Excluded occurrences reappeared on timezone-anchored events, because `EXDATE` and `RECURRENCE-ID` were emitted as floating date-times regardless of the event's timezone.
* A recurring series in a non-UTC timezone ended at the wrong time, since `UNTIL`, `EXDATE` and `RECURRENCE-ID` were emitted as UTC where the format requires event-local time.
* `STATUS` was dropped in both conversion directions, so `STATUS:CANCELLED` round-tripped as confirmed and cancelled meetings appeared active.
* `JMAPCalendar.search()` sent `start`/`end` in a format JMAP does not accept.
* `create_task()` raised a bare `KeyError` instead of `JMAPMethodError` when the server returned nothing created.

#### Compatibility hints

* Merging a plain-string feature value over an existing one crashed with a bare `AssertionError`, so any two-layer server configuration expressing the same feature failed.
* An unknown feature name in a config file warned but was stored anyway, causing a message-less `AssertionError` later, far from the config that caused it.
* OX App Suite does honour a display name given at calendar creation; the expectation was wrongly pinned to `unsupported`.
* Stalwart's server-side `expand` returns both the original occurrence and its override when `SEQUENCE` is present, so `search.recurrences.expanded.exception` is corrected to `fragile`.

#### Packaging

* The source distribution no longer ships stray local files.  hatchling only honours the *root* `.gitignore`, so files hidden by a nested `.gitignore` or by the packager's global git ignore file were invisible locally and packaged anyway - `caldav-3.2.1.tar.gz` contains `.claude/settings.json` and 1755 files under `venv/`.  Both artifacts are now checked during the release procedure and in CI.

### Changed

* Search results that need loading are fetched with a single `calendar-multiget` request instead of one `GET` per object - a 200-event search made 200 requests before.  If the multiget fails the library falls back to per-object loads, so the failure semantics of `search()` are unchanged.
* Results from a comp-type-split search come back grouped by component type rather than in server order.  Pass a sort key if the order matters.
* Fourteen compatibility features that are probed directly *and* have sub-features are now treated as independent, so e.g. `sync-token` stays `full` even when `sync-token.delete` is `unsupported`.

### Security

* The XML parser is now built with `resolve_entities=False, no_network=True`, so a malicious or MITM server cannot inject text into parsed property values through inline DOCTYPE entity definitions.  This was already the effective behaviour on most lxml versions, but lxml is an unpinned dependency and the parser should not rely on another project's defaults for this.
* `require_tls=True` was not enforced on the well-known URI redirect target, so a same-domain `Location: http://...` could silently downgrade the connection to plaintext.
* Setting the `PYTHON_CALDAV_COMMDUMP` debug environment variable now logs a warning at import time, as a reminder that request and response bodies - including credentials and calendar data - are written to files under `/tmp` with retention left for the OS/distribution.

### Test framework

* `XandikosServer.stop()` blocked for a full 10 seconds on every call, adding ~10s to each Xandikos test teardown.  Thanks to @betaboon.
* `testCheckCompatibility` could not see a conflict when a probed sub-feature's observed status happened to equal the type default and its declared status was only inherited from a parent.  The comparison is now a unit-tested `FeatureSet.compare()`.
* New server-peculiarity `write-delay`, for servers that process writes asynchronously - a `PUT`/`DELETE`/`MKCALENDAR` returns before the change is queryable, so an immediate read-back 404s or returns stale data.  The write-side counterpart of `search-cache`.  The integration test suites, sync and async, pause after every write on such a server; the library itself does not wait, so this only documents the server for anyone consulting `features.is_supported('write-delay', dict)`.  Infomaniak declares it.
* New compatibility flag `save-load.event.recurrences.exception.reschedule`: whether the server accepts moving a recurring event's master `DTSTART` while detached exceptions (`RECURRENCE-ID`) are attached.  OX App Suite rejects it with `409 Conflict`, so `testEditSingleRecurrence` skips that step there.
* Pre-test calendar cleanup in the async integration tests is centralised in `adelete_calendar_if_present()`, with a narrow `except` - it used to swallow every error and leave calendars behind.
* The `enabled: false` setting now actually disables a docker test server.
* `ruff` rule F841 is enabled, which surfaced several tests that computed a result and never asserted on it.

### Credits

The following people contributed to this release through issue reports, pull requests, and/or commits:

* @betaboon - two of the fixes above, plus test infrastructure
* Sashank Bhamidi (@SashankBhamidi) - JMAP review, including the timezone-anchored `UNTIL` bug
* @clarkewing - https://github.com/python-caldav/caldav/issues/690, behind the `caldav[niquests]` install target
* @ShawkMusic - https://github.com/python-caldav/caldav/issues/681 and https://github.com/python-caldav/caldav/issues/647, the comp-type-less search breakage
* @mamo79 - https://github.com/python-caldav/caldav/issues/684, behind the Infomaniak profile
* @hello-tty - https://github.com/python-caldav/caldav/issues/399, behind the attendee-partstat compatibility flag

The discussion on which HTTP library caldav should depend on (https://github.com/python-caldav/caldav/issues/611) shaped both the httpx2 support and the dependency plan described at the top of this file.  Thanks to @Callum027, @Ousret, @dotlambda, @lilydjwg and @s-at-ik.

## [3.2.1] - 2026-05-28

The changeset in 3.2.1 is predominently added async integration tests.  Those tests should now be replicating all the logic in the good old sync integration tests under `test_caldav.py`.  Some few more bugs were found while adding those tests.

There are two "feature commits" adding new parameters to existing functions.  Those are minor additions and was required while fixing things (test breakage plus observed crash due to weird real-world-data), hence I define this to be a patch-release rather than a minor-release.

### Added

* `Calendar.delete()` has had a "wipe-mode" since v2.2.0, deleting items from the calendar if it's not possible to delete the calendar itself.  Now a tristate `wipe` parameter has been added, `wipe=True` to wipe rather than delete the calendar, `wipe=False` to not wipe, and default behaviour (`wipe=None`) is still "wipe if needed".  (Useful for NextCloud tests, where events stuck on calendars in the "trashbin" pollutes the namespace preventing the same event to be added to a new calendar).
* `save()` `only_this_recurrence` parameter is now a tristate:
  * `True` (default) - unchanged, if the object is a recurrence it will be merged with the master event, making sure the saved recurrence is stored as an exception to the RRULE.  If the master object does not exist, then it will raise `NotFoundError`.
  * `None` (new) - same as True, except that if the master object does not exist, the recurrence will just be sent directly to the server as-is.
  * `False` - unchanged, the recurrence will be sent directly to the server as-is.
  `None` is used in the `add_object()`.  This change was needed to avoid a crash when trying to add a recurrence-object without a master to the server.  (So much ado for a very weird edge case).

### Fixed

* Async digest auth was broken when using niquests: `HTTPDigestAuth.handle_401()` calls `r.connection.send()` which returns a coroutine in async context, causing `AttributeError: 'coroutine' object has no attribute 'history'`.  Fixed by using `AsyncHTTPDigestAuth` for the async client.  See https://github.com/jawah/niquests/issues/387
* Several async code paths were not properly awaited or were missing parity with their sync counterparts:
  * `Calendar.freebusy_request()` was not async-aware.
  * `_async_complete()` raised `NotImplementedError` for `handle_rrule=True`.
  * `_async_put()` did not `await` the retry coroutine returned by `_post_put()`.
  * `_async_get_object_by_uid()` was missing `include_completed=True`, unlike the sync version.
  * `_async_search_with_comptypes()` did not skip component types unsupported by the server, unlike the sync version.
* Zimbra compatibility: `DisplayName` is now omitted from the `MKCALENDAR` request body when `create-calendar.set-displayname` is unsupported.

### Changed

* **httpxyz added as an async HTTP fallback**.  [httpxyz](https://codeberg.org/httpxyz/httpxyz) is a maintained fork of httpx that picked up where httpx stalled.  The async client fallback priority is now `niquests` (preferred) → `httpxyz` → `httpx`.  See https://github.com/python-caldav/caldav/issues/611

### Test framework

These changes are not part of the shipped library, but make up the bulk of the 3.2.1 changeset.

#### Async tests

* **Async integration tests greatly expanded** (`tests/test_async_integration.py` grew by ~1700 lines) to mirror the sync suite in `test_caldav.py`.  Part of `git bug bug show e44ee06` aka  https://github.com/python-caldav/caldav/issues/667
* **Test reliability on Nextcloud and others**: While I've been trying to insist on static readable UIDs during the last couple of years, Claude insists on using unique identifiers for each run using uuid4.  The latter does improve the reliability when it comes to i.e. Nextcloud that moves calendars to the trashbin rather than deleting them, while also rejecting duplicated UIDs.  I finally gave up on this one for some of the event/task/journal UIDs after restarting the nextcloud container every so often to avoid test breakages.  I still haven't given up the idea of having static calendar IDs to identify the test calendars.
* `testCheckCompatibility` no longer takes ~8 minutes on servers with a search-cache delay (e.g. Bedework) — two bugs causing repeated cache-delay waits were fixed, and some redundant Bedework compatibility-matrix entries were cleaned up.
* Added unit and integration tests for the orphaned-recurrence save behaviour (`test_caldav.py`, `test_caldav_unit.py`).
* `tests/test_servers/`: registered Baikal's `URL_ENV_VAR` so the async-httpx CI job can reach it, and added a `get_available_servers()` helper used by the async integration tests.

#### Docker test servers

* **Migrated the local test rig from Docker to rootless Podman**, which surfaced and fixed several issues:
  * The DAViCal setup script broke on Podman's `Emulate Docker CLI using podman` banner string.
  * Some health-checks were broken (probably under Docker too, just unnoticed) and were repaired.
  * Removed `uid=…,gid=…` tmpfs mount options that Podman does not support (CCS / CalendarServer runs as root inside the container, so the ownership hint wasn't needed).
* **Stalwart v0.16.6 breaking changes** handled: the server now enters bootstrap mode without config files (config files added), the admin API was reorganized (affecting setup calls and health-checks), simple usernames are rejected in favour of full email addresses (`testuser@example.org`), weak passwords are rejected, and a workaround was added for Stalwart advertising `https://` even when reached over `http://` in local dev.
* **Nextcloud**: added `mailto:` email addresses for the scheduling test users (so iTIP delivery works), and disabled the CalDAV trashbin (`calendarRetentionObligation=0`) so HTTP `DELETE` hard-deletes objects and re-using a UID doesn't hit a `UNIQUE` constraint violation.
* **Cyrus**: ship `imapd.conf` with `virtdomains: off` (the default `virtdomains: userid` caused 403s on iTIP delivery due to userid/ACL mismatch), unpinned from the March 2026 digest now that `:latest` is stable again, and pointed the health-check at the CalDAV port.
* Dropped some now-obsolete lines from the Xandikos (in)compatibility matrix following upstream bugfixes.

#### GitHub CI

* **More server coverage in the GitHub workflows**: Nextcloud and Cyrus are now configured for the scheduling tests, and a new async-httpx integration job runs against a real Baikal service (previously only unit tests exercised the httpx fallback path).
* Renamed the `async (niquests fallback)` job to `async (niquests)` to reflect that niquests is the default install, not a fallback.
* Added CI jobs verifying each async HTTP backend is picked up correctly when the others are absent: `async (niquests)`, `async (httpxyz fallback)` and `async (httpx fallback)`.
* **lychee link-checker upgraded to v0.24.1** (pre-commit hook bumped from v0.22.0).  v0.24.1 hard-errors on placeholder URLs like `scheme://hostname:port` instead of silently rewriting them, which the 30-day cache had been masking — placeholder URLs were replaced with concrete examples (`http://proxy.example.com:8080`) in `davclient.py` and `async_davclient.py`, and `.lycheeignore` was updated accordingly.

## [3.2.0] - 2026-04-24

The two most significant news in v3.2 are **relatively well-tested support for scheduling** (RFC6638) and **better-tested support for async**.  Care should still be taken, those features are backed by many tests, but lacks testing for how well they support real-world use-case scenarios.  While async support was added in version 3.0, it was not well-enough tested.  Still only a fraction of all the integration tests for sync usage has been duplicated in the async integration test, I expect to release 3.2.1 with symmetric async integration tests before 2025-07.

### Added

* `add_organizer()` now accepts an optional explicit *organizer* argument (a `Principal`, `vCalAddress`, or email string)
* Complete support for **Schedule-Tag** (RFC 6638 §3.2–3.3) and **Etag**.  Headers from upstream will be caught and stored in the properties.  If those properties exists, `If-Schedule-Tag-Match` or `If-Match` headers will be sent.  A `ScheduleTagMismatchError` or `ETagMismatchError` will be raised on 412.

### Changed

* **httpx deprecation** - earlier, in async mode, if httpx was installed it would be used (while niquests is listed in the requirements).  This have been reversed - now httpx will be used if it's installed while niquest isn't installed.  httpx seems like a dead end, destroyed by drama and intrigues, and now even flagged as a supply chain risk on Reddit.  See https://github.com/python-caldav/caldav/issues/611#issuecomment-4278875543
* **SEQUENCE property assumed to default to 0** when absent (RFC 5546 §2.1.4).  `save()` then inserts `SEQUENCE:1` unless the `increase_seqno` parameter is set to False.

### Fixed

* Bug with inconsistent `search()`-results - https://github.com/python-caldav/caldav/issues/650
* Compatibility fixing:
  * `_resolve_properties()` would crash for some disbehaving servers. https://github.com/pycalendar/calendar-cli/issues/114
  * `Calendar.get_supported_components()` would crash for some servers.  https://github.com/python-caldav/caldav/issues/653
  * Fallback code for `accept_invite()`, `decline_invite()` and `tentatively_accept_invite()` when the server does not expose the `calendar-user-address-set` property. https://github.com/python-caldav/caldav/issues/399
* Quite some code-paths with IO was async-unaware - found and fixed quite many of those.  Some places duplicating code seems to be most trivial - but it's something I really want to avoid.  There were already places in the code where the async and sync behaviour differed. I've done quite some refactoring to reduce the amount of duplicated code.
* Done some work on `get_object_by_uid()`, aligning it with the rest of the search API.  Closes https://github.com/python-caldav/caldav/issues/586

### AI transparency

I've been experimenting with Claude Code over the last few months, concerns have been raised that it may have negatively affected code quality - and indeed, this is probably a major reason why the async support in v3.0 was simply not good enough.  I've been working a bit more on the [AI-POLICY.md](AI-POLICY.md), some of the directions for the future looks like this:

* All work involving *new features* should primarily be done by hand (AI-assistance allowed for discussing different design decisions, reviewing and fixing trivial bugs in the new code, dealing with trivial TODO-nodes in the handwritten code, etc).
* All prompts should be logged.
* Prompts should be included in the commit message.
* Model and other relevant information on the AI-usage should be included.
* Commit messages should include information on what and how much is AI-generated (with default being "all" or "none" dependent on the commit message trailer)
* Commit messages should include information on why AI was used.
* The AI should be used for Code Review for every release.

The 3.2-release may not be fully up to those standards, as they were made while working on 3.2.

The branch v3.2-development contains "raw" commits, most of the commits are either AI-written (including commit message) or human-written.  I've done quite some work trying to squash the commits into fewer commits, in the main branch all the recent commit messages are handwritten, and most of the commits have some notes on how much is AI-generated and why AI-generation was chosen.  The manual walk-through of all the commits has been tedious, but useful for QA-purposes.  I'm considering this to be the way forward.

I have all relatively fresh communication with Claude in JSON-files, and I was considering to embed them into the repository for increased transparency.  Everything considered, I think it would involve too much noise, so I've skipped it as for now.  If you want it, I will publish it.

### Housekeeping and documentation

* **AI-POLICY.md** updated - see also the "AI Transparency" subsection
* **GitHub exit strategy**: Issues are now mirrored in the git repository itself using the [git-bug package](https://github.com/git-bug/git-bug).  I'm not intending to leave GitHub for the foreseeable future, but I don't want to be locked-in or dependent on GitHub - this is a first step towards an "exit strategy".
* **Code quality**: reduced ruff ignore list (https://github.com/python-caldav/caldav/issues/634) — removed unused imports (`copy`, `lxml.etree`, `CalendarSet`, `cdav/dav` re-exports, `Optional`, `timezone`, `Event`/`Todo` type stubs), replaced bare `except:` clauses with specific exception types (`KeyError`, `AttributeError`, `Exception` where broad catching is intentional), and removed unused local variables.
* async documentation brushed up a bit with bugfixes and disclaimers
* Examples and tests for finding calendar owners -  https://github.com/python-caldav/caldav/issues/544
* Added `funding.json` (https://fundingjson.org/) at the repository root.  Closes https://github.com/python-caldav/caldav/issues/608
* Some broken examples and documentation wasn't properly tested - https://github.com/python-caldav/caldav/issues/661

### Test framework, compatibility hints, documentation, examples

* Lots of new compatibility feaure hints added (with checking code in the caldav-server-tester tool), including RFC6638-relevant features.
* Some compatibility feature hints have been renamed and moved around.  See the "Breaking changes"-section below.
* `_AsyncTestSchedulingBase` added: async counterpart of `_TestSchedulingBase` with `test_invite_and_respond` and `test_freebusy`; `TestAsyncSchedulingFor<Server>` classes generated for each server with `scheduling_users` configured.
* Lots of new test code for the RFC6638-functionality, including setting up extra test users in the docker containers.

### Breaking changes

* Some compatibility feature hints have been moved a bit around.  This file is still not considered to be a "sharp" part of the libary, otherwise we'd need to bump the version number to 4.0.
  * freebusy-related flags.  The rfc6638-freebusy have been moved to `scheduling.freebusy`, rfc4791-freebusy have been collapsed down into `freebusy` (instead of `freebusy.rfc4791`).
  * `search.text.by-uid` was removed, there is (probably?) no servers supporting one but not the other.  (Though the checks on this may be wrong, as workarounds are automatically employed for servers not supporting text search).   https://github.com/python-caldav/caldav/issues/586

## [3.1.0] - 2026-03-19

Highlights:

* **Fixups on the async support**.  Perhaps the "sans-io" design concept wasn't such a great idea - quite some gaps in the async support has been identified and fixed,.
* **Multi-server `get_calendars()`:** a single `get_calendars()` call can now span multiple config-file sections (including glob/wildcard expansion), aggregating calendars from multiple servers into one `CalendarCollection`.  This was the idea (and has been implemented in my `plann` project for quite some time), but fell short of getting into the v3.0-release.
* Full async tutorial added to the documentation.

### Added

* `get_icalendar_component()` returns a deep-copy of the inner VEVENT/VTODO/VJOURNAL sub-component for read-only inspection, consistent with the `get_icalendar_instance()` naming convention.
* `edit_icalendar_component()` context manager yields the inner component for editing and delegates to `edit_icalendar_instance()` so all borrow/state/save machinery is reused.
* `get_calendars()` now accepts a `config_section` value that is expanded via `expand_config_section()`, so wildcards like `"work_*"` or `"all"` resolve to multiple leaf sections; each section gets its own `DAVClient` and all calendars are aggregated into a `CalendarCollection`.  `CalendarCollection` now closes all its clients on context-manager exit.
* New config helper: `get_all_file_connection_params(config_file, section)`.
* `PYTHON_CALDAV_USE_TEST_SERVER=1` (or `testconfig=True`) falls back to automatically starting the first available enabled server from the test-server registry when no `testing_allowed` config section is present.  Three new env vars (`PYTHON_CALDAV_TEST_EMBEDDED`, `PYTHON_CALDAV_TEST_DOCKER`, `PYTHON_CALDAV_TEST_EXTERNAL`) control which server categories are eligible.  Per-server `priority:` keys in config files are honoured.
* New `caldav/testing.py` (shipped with the package): `EmbeddedServer`, `XandikosServer`, `RadicaleServer` — so pip-installed users can use `PYTHON_CALDAV_USE_TEST_SERVER=1` without a source checkout.

### Fixed

* `get_object_by_uid()` (and `get_event_by_uid()`, `get_todo_by_uid()`, `get_journal_by_uid()`, and their deprecated aliases) raised `TypeError` with async clients because `search()` returned a coroutine that was iterated directly.  Fixes https://github.com/python-caldav/caldav/issues/642
* `complete()` and the save()-recurrence path were not awaited for async clients.
* `uncomplete()`, `set_relation()`, `get_relatives()`, and `invite()` lacked async dispatch.
* `_handle_reverse_relations()` called `get_relatives()` without `await`, silently returning a coroutine.
* `get_calendar()` and `get_calendars()` were missing from the `caldav.aio` re-export.
* `get_calendars(config_section=…)` silently ignored `calendar_name` and `calendar_url` keys in config sections — they were stripped before reaching the filter logic.
* `expand_config_section()` was not called when reading the config file, so `contains:`-style meta-sections had no effect.
* `date` objects passed to `calendar.search()` or `calendar.searcher()` as time-range boundaries now get coerced to UTC `datetime` before being forwarded to `icalendar_searcher`, silencing the "Date-range searches not well supported yet" warning.
* `XandikosServer.is_accessible()` now sends a minimal `PROPFIND` requesting only `{DAV:}resourcetype` instead of an implicit `allprop`, avoiding spurious `NotImplementedError` log lines from Xandikos during test-server startup.

### Tests and documentation

* Full async tutorial added: `docs/source/async_tutorial.rst`.  Covers the same ground as the sync tutorial plus a "Parallel Operations" section demonstrating `asyncio.gather()`.  The sync tutorial now links to it.
* `docs/source/configfile.rst` has been rewritten and extended; tests for `inherits` and env-var expansion added.
* `docs/source/tutorial.rst` rewritten and fixed.
* The caldav-server-tester tool is now documented in the config file guide.
* Design notes on the dual-mode sync/async pattern and its trade-offs added in `docs/source/`.
* Test server spin-up/teardown tweaked for reliability.
* CI: deptry and lychee link-checker fixups.

## [3.0.2] - 2026-03-15

Highlight: Reintroducing debug communication dump functionality.

### Fixed

* When environment variable `PYTHON_CALDAV_COMMDUMP` is given, caldav communication is dumped to /tmp - details in https://github.com/python-caldav/caldav/issues/248 .  This is regarded as "fix" rather than "feature" as it was introduced in v1.4.0 and accidentally dropped during the v3.0 refactoring.  Restored, with the dump logic extracted into a shared helper so both the sync and async code paths benefit.  Test code added to make sure it won't disappear again.  Fixes https://github.com/python-caldav/caldav/issues/638
* `search()` raised `NotImplementedError` when a full calendar-query XML was passed and the server does not support `search.comp-type.optional`.  This is a really rare and deprecated code path, but still `NotImplementedError` isn't good.  Now it falls back to a single REPORT with the XML as-is.  Fixes https://github.com/python-caldav/caldav/issues/637

### Tests and documentation

* All links to the RFC is now in a canonical format.  Links in docstrings and ReST-documentation follows the sphinx-standard.  Fixes https://github.com/python-caldav/caldav/issues/635 - pull request https://github.com/python-caldav/caldav/pull/636
* I've decided to try to stick to the conventionalcommits standard.  This is documented in CONTRIBUTING.md, and I've added a pre-commit hook for enforcing it (but it needs to be installed through pre-commit ... so I will most likely have to police pull requests manually)
* Some code refactoring in the test code.
* Improved the lychee link testing setup

## [3.0.1] - 2026-03-04

Highlights:

* Minor bugfix to support old versions of httpx
* New test server docker container: OX
* Minor other fixes and workarounds
* Started working on proper documentation for the 3.x-series

### Test runs before release

* Xandikos, Radicale, all docker servers (including OX), an external Zimbra server, but no other external servers.

### Added

* **OX App Suite** included in the docker test servers.  Compatibility hints added.  To get OX running it's needed to do an extra build step.  See `tests/docker-test-servers/ox/`.  However, OX is undertested as both the caldav-server-checker and the test suite does not play well with OX (events with historic DTSTART etc are used, OX doesn't support that).
* New `search.unlimited-time-range` feature flag with a workaround in `search.py` that injects a broad time range (1970–2126) for servers that return an empty result set when no time range is specified (but this still doesn't help to OX).

### Fixed

* `AsyncDAVClient` failed to initialize when using httpx < 0.23.0 because `proxy=None` was unconditionally passed to `httpx.AsyncClient` which did not accept a `proxy` keyword argument in older releases.  Fixes https://github.com/python-caldav/caldav/issues/632
* Stalwart (like purelymail) includes extra "not found" error data in some responses.  This could trigger a spurious `"Deviation from expectations found"` log error in production, or an assertion failure in debug mode.

### Security

* UUID1 was replaced with UUID4 before releasing v3.0 ... some places.  Unfortunately I forgot to grep for UUID1 before preparing the release.  When UIDs are generated by UUID1, it may embed the host MAC address in calendar data shared with third parties.  Switched to UUID4 throughout.

### Potentially Breaking Changes

* The compatibility-hint key `search.comp-type-optional` has been renamed to `search.comp-type.optional` for consistency with the dotted-key naming convention used elsewhere.  If you have this key set in a local server configuration, update it accordingly.

### Documentation

Some minor improvements, including a fix for https://github.com/python-caldav/caldav/issues/635 - use canonical RFC-links.

## [3.0.0] - 2026-03-03

Version 3.0 should be fully backward-compatible with version 2.x - but there are massive code changes in version 3.0, so if you're using the Python CalDAV client library in some sharp production environment, I would recommend to wait for two months before upgrading.

Highlights

* As always, lots of compatibility-tweaking.  This release have probably been tested on more server implementations than any earlier version.
* "Black Style" has been replaced with **ruff**.  This causes quite some minor changes to the code.
* **Full async support** -- New `AsyncDAVClient` and async domain objects using a Sans-I/O architecture.  The same `Calendar`, `Event`, `Todo`, etc. objects work with both sync and async clients.
* Experimental **JMAP client** -- New `caldav.jmap` package with `JMAPClient` and `AsyncJMAPClient` for servers implementing RFC 8620 (JMAP Core) and RFC 8984 (JMAP Calendars).  Note that this is experimental, and the public API may be changed in upcoming minor-releases.
* **Overhaul of the official API** -- v3.0 comes with an improved, more pythonic and more consistent API, but aims to be fully backeward compatible.  Some work has been done on the documentation, but full QA and updates will have to wait for an upcoming patch release.

### Test runs before release

* The built-in test-servers, of course: Radicale, Xandikos
* All the docker-based test servers: Nextcloud, Baikal, Bedework, CCS, Cyrus, DAViCal, Davis, SOGo, Stalwart, Zimbra
* External servers and SaaS-providers:
  * ECloud (NextCloud-based - big troubles due to ratelimiting and need for manually "emptying the trashbin")
  * Synology
  * Zimbra Enterprise, hosted by my employer
  * Robur (has some issues with transient errors)
  * Posteo
  * Purelymail (test run takes ages due to delays before search results are ready)

The tests broke with lots of AuthorizationErrors with GMX.  The tests were running successfully towards GMX before releasing the last alpha-release.  It's probably a transient issue.  I don't want to delay the release by doing more research into it.

### Breaking Changes

Be aware that some of the 2.x minor-versions also tagged some "Potentially Breaking Changes" - so if you're upgrading i.e. from 2.1, you may want to browse through the "Potentially Breaking Changes" for the intermediate minor releases too.

* **Minimum Python version**: Python 3.10+ is now required (was 3.8+).
* **Test Server Configuration**: `tests/conf.py` has been removed and `conf_private.py` will be ignored.  See the Test Framework section below.
* **`caldav/objects.py` removed** -- the backward-compatibility re-export shim has been deleted.  Any code doing `from caldav.objects import <something>` must be updated; all public symbols remain available directly via `caldav` or from their respective submodules.
* **Config file parse errors now raise exceptions** -- `caldav.config.read_config()` now raises `ValueError` on YAML/JSON parse errors instead of logging and returning an empty dict.  This ensures config errors are detected early.

### Deprecated

The following have been deprecated and emit `DeprecationWarning`:
* `calendar.date_search()` - use `calendar.search()` instead
* `client.principals()` - use `client.search_principals()` instead
* `obj.split_expanded` - may be removed in a future version
* `obj.expand_rrule` - may be removed in a future version
* `.instance` property on calendar objects - use `.vobject_instance` or `.icalendar_instance`
* `response.find_objects_and_props()` - use `response.results` instead

The `save_*`-methods are deprecated but do not yet emit warnings (see https://github.com/python-caldav/caldav/issues/71):
* `calendar.save_event()` - use `calendar.add_event()` instead
* `calendar.save_todo()` - use `calendar.add_todo()` instead
* `calendar.save_journal()` - use `calendar.add_journal()` instead
* `calendar.save_object()` - use `calendar.add_object()` instead

Methods that fetch data from the server should use the `get_` prefix (see https://github.com/python-caldav/caldav/issues/92). The following are deprecated but do not yet emit warnings:
* `calendar.event_by_uid()` - use `calendar.get_event_by_uid()` instead
* `calendar.todo_by_uid()` - use `calendar.get_todo_by_uid()` instead
* `calendar.journal_by_uid()` - use `calendar.get_journal_by_uid()` instead
* `calendar.object_by_uid()` - use `calendar.get_object_by_uid()` instead
* `principal.calendars()` - use `principal.get_calendars()` instead
* `calendar.events()` - use `calendar.get_events()` instead
* `calendar.todos()` - use `calendar.get_todos()` instead
* `calendar.journals()` - use `calendar.get_journals()` instead
* `calendar.objects_by_sync_token()` - use `calendar.get_objects_by_sync_token()` instead

The following `check_*_support()` methods are deprecated but do not yet emit warnings:
* `client.check_dav_support()` - use `client.supports_dav()` instead
* `client.check_cdav_support()` - use `client.supports_caldav()` instead
* `client.check_scheduling_support()` - use `client.supports_scheduling()` instead
(Those methods actively probe the server; `is_supported()` is a configuration lookup.)

Additionally, direct `DAVClient()` instantiation should migrate to `get_davclient()` factory method (see `docs/design/API_NAMING_CONVENTIONS.md`)

### Added

* Experimental **JMAP calendar client** — new `caldav.jmap` package providing a JMAP client
  for servers implementing RFC 8620 (JMAP Core) and RFC 8984 (JMAP Calendars).
  Features:
  - Synchronous `JMAPClient` and asynchronous `AsyncJMAPClient` with mirrored APIs
  - Full calendar + event CRUD (`create_event`, `get_event`, `update_event`,
    `delete_event`, `search_events`)
  - Incremental sync via `get_sync_token` / `get_objects_by_sync_token`
  - Task CRUD (draft-ietf-jmap-tasks) via `create_task`, `get_task`, `update_task`, `delete_task`
  - Bidirectional iCalendar ↔ JSCalendar conversion layer
  - `get_jmap_client()` factory reads from the same config sources as
    `get_davclient()` (env vars, config file)
  - Tested against Cyrus IMAP

* **Full async API** - New `AsyncDAVClient` and async-compatible domain objects:
  ```python
  from caldav.async_davclient import get_davclient

  async with await get_davclient(url="...", username="...", password="...") as client:
      principal = await client.get_principal()
      calendars = await client.get_calendars()
      for cal in calendars:
          events = await cal.get_events()
  ```
* **Retry-After / rate-limit handling** (RFC 6585 / RFC 9110) -- `DAVClient` and `AsyncDAVClient` now expose `rate_limit_handle`, `rate_limit_default_sleep`, and `rate_limit_max_sleep` parameters (this may be specified in the configuration file as well).  When `rate_limit_handle=True` the client automatically sleeps and retries on 429 Too Many Requests and 503 Service Unavailable responses that include a `Retry-After` header.  When `rate_limit_handle=False` (default) a `RateLimitError` is raised immediately so callers can implement their own back-off strategy.  New `caldav.lib.error.RateLimitError` has `retry_after` (raw header string) and `retry_after_seconds` (parsed float) attributes.  https://github.com/python-caldav/caldav/issues/627
* **`search.is-not-defined.category` and `search.is-not-defined.dtend`** -- new client-side workaround sub-features for servers that do not support the `CALDAV:is-not-defined` filter natively for these properties.
* **Base+override feature profiles** -- YAML config now supports inheriting from a base profile:
  ```yaml
  my-server:
      features:
          base: nextcloud
          search.comp-type: unsupported
  ```
* **Compatibility fixes**
  * New feature flags
    * `save-load.event.recurrences.exception` which is supported if the server stores master+exception VEVENTs as a single calendar object as per the RFC.  Stalwart splits them into separate objects. Stalwart recombines the data when doing an expanded search, so `expand=True` searches now automatically fall back to server-side `CALDAV:expand`.  (Arguably, `unsupported` here could also mean the exception data was simply discarded.  If needed, I'll refine this in a future version)
	* `save-load.journal.mixed-calendar` - some calendar servers offers a separate journal list.
	* `save-load.reuse-deleted-uid` - server allows immediate reuse of an uid if the old object has been deleted
    * `search.time-range.*.old-dates` - test data mostly have historic dates.  Calendars are primarily made for future happenings.  Some calendar servers does not support searching for things that happened 20 years ago, even for a very small calendar.
    * `search.is-not-defined.category` and `search.is-not-defined.dtend` - actually, those are artifacts.  The bug was on the client side, not server side.  I may delete them in a future release.
  * Fallback for missing calendar-home-set -- client now falls back to the principal URL when `calendar-home-set` property is not available (e.g. GMX).
  * Load fallback for changed URLs -- `CalendarObjectResource.load()` now falls back to UID-based lookup when servers change object URLs after a save.
  * Many other tweaks and fixings of the compatibility hints.
* Added python-dateutil and PyYAML as explicit dependencies (were transitive)
* Quite some methods have been renamed for consistency and to follow best current practices.  See the Deprecated section.
* `Calendar` class now accepts a `name` parameter in its constructor, addressing a long-standing API inconsistency (https://github.com/python-caldav/caldav/issues/128)
* **CalendarObjectResource.id property** - Returns the UID of calendar objects (https://github.com/python-caldav/caldav/issues/515)
* **calendar.searcher() API** - Factory method for advanced search queries (https://github.com/python-caldav/caldav/issues/590):
  ```python
  searcher = calendar.searcher()
  searcher.add_filter(...)
  results = searcher.search()
  ``
* Improved API for accessing the `CalendarObjectResource` properties (https://github.com/python-caldav/caldav/issues/613 ):
  * `get_data()`, `get_icalendar_instance`, `get_vobject_instance`, `get_icalendar_component`:
    * Returns COPIES of the data
  * `edit_*` (but no `edit_data` - the data is an immutable string, should use simply `object.data = foo` for editing it)
    * Returns a context manager
	* "Borowing pattern" - `with obj.get_foo`, the client may edit foo, and then `obj.save()` to send it to the server.

### Fixed

* RFC 4791 compliance: Don't send Depth header for calendar-multiget REPORT (clients SHOULD NOT send it, but servers MUST ignore it per §7.9)
* Lots of minor fixes and workarounds were done while trying to run the integration tests for v3.0, most of them fixing new bugs introduced in the development branch, but also new workarounds for server incompatibilities (and better fixing of old workarounds).  v3.0 was tested on quite many more servers than v2.2.6.
* Possibly other minor bugfixes adressing old previously unknown bugs - frankly, I've lost the overview.  v3.0 has a lot of code changes.
* The `is-not-defined` filter for CATEGORIES did not work, and for DTEND it did not work for full day events.  (this was fixes in the `icalendar-searcher`, version 1.0.5).

### Changed
* Optimilizations on data conversions in the `CalendarObjectResource` properties (https://github.com/python-caldav/caldav/issues/613 )
* Lazy imports (PEP 562) -- `import caldav` is now significantly faster.  Heavy dependencies (lxml, niquests, icalendar) are deferred until first use.  https://github.com/python-caldav/caldav/issues/621
* Search refactored to use generator-based Sans-I/O pattern -- `_search_impl` yields `(SearchAction, data)` tuples consumed by sync or async wrappers
* Configuration system expanded: `get_connection_params()` provides unified config discovery with clear priority (explicit params > test server config > env vars > config file)
* `${VAR}` and `${VAR:-default}` environment variable expansion in config values
* Test configuration migrated from legacy `tests/conf.py` to new `tests/test_servers/` framework
* Lots of refactored code.
* "Black Style" replaced with ruff
* Compatibility hint matrix has been updated a bit.  I'm a bit confused on weather it's due to changes in my caldav-server-tester tool, changed behaviour in newer versions of the servers, or other reasons.  Running the integration tests and debugging such issues takes a lot of time and effort.

### Security

* UUID1 usage in UID generation may embed the host MAC address in calendar UIDs.  Since calendar events are shared with third parties, this may be a privacy concern.  A switch to UUID4 has been made some places in the code.  (Running a grep just when doing the final touches on the CHANGELOG, I discovered that there is still some UUID1-instances left.  It should be safe to change it, but I don't want to delay the release of v3.0.0, so it will have to go into a future v3.0.1 release)

### Test Framework

* **New Docker test servers**:
  * Apple Calendar Server (CCS) - the project was discontinued long ago, but used to be a flagship of compatibility - and I suspect the iCloud server has inheritated some code from this project.
  * DAViCal - an old server, but maintained and one of the more standard-compliant servers.  It also has multi-user support.
  * Davis - it's a relative of Baikal
  * Stalwart - a quite new project, mail+calendar, supports JMAP and is funded through NLNet
  * Zimbra - multi-user mail+calendar.  Financed through having a non-free "enterprise" version with paid licenses.
* Fixed Nextcloud Docker test server tmpfs permissions race condition
* Added deptry for dependency verification in CI
* The test server framework has been refactored with a new `tests/test_servers/` module.  It provides **YAML-based server configuration**: see `tests/test_servers/__init__.py` for usage
* Added pytest-asyncio for async test support
* **Updated Docker configs**: Baikal, Cyrus, Nextcloud, SOGo
* Added lychee link-check workflow
* Added `convert_conf_private.py` migration tool for legacy config format
* New test files: `test_lazy_import.py`; expanded `test_async_davclient.py`, `test_async_integration.py`, `test_compatibility_hints.py`, `test_search.py`, `test_caldav_unit.py`
* Added async rate-limit unit tests matching the sync test suite
* caldav-server-tester: `CheckRecurrenceSearch` now also verifies implicit recurrence support for all-day (VALUE=DATE) recurring events, marking the feature as `fragile` (with behaviour description) when only datetime recurring events work.


### GitHub Pull Requests Merged

* #607 - Add deptry for dependency verification (also in 2.2.6) -- Tobias Brox (@tobixen)
* #610 - Development for the v3.0-branch - async support and misc -- Tobias Brox (@tobixen)
* #617 - Refactoring the `calendar.search` -- Tobias Brox (@tobixen)
* #618 - Deprecate DAVObject.name in favor of `get_display_name()` -- Tobias Brox (@tobixen)
* #622 - Fix overlong inline literal, replace hyphens with en-dashes -- @joshinils
* #623 - More v3.0 development -- Tobias Brox (@tobixen)
* #625 - feat(jmap): add caldav/jmap — JMAP calendar and task client -- Sashank Bhamidi (@SashankBhamidi)
* #626 - docs(jmap): JMAP usage documentation and autodoc stubs -- Sashank Bhamidi (@SashankBhamidi)
* #630 - More v3.0 development -- Tobias Brox (@tobixen)

### GitHub Pull Requests Closed (not merged)

* #565 - ADR: HTTPX Async-First Architecture with Thin Sync Wrappers (design exploration; superceded by #610) -- Chris Coutinho (@cbcoutinho)
* #588 - Fix duplicate parameter bug in search() recursive call (superseded by search refactoring in #617) -- Tobias Brox (@tobixen)
* #603 - Playground/new async api design (exploratory work, superceded by #610) -- Tobias Brox (@tobixen)
* #604 - mistake, pull request created from the wrong branch -- Tobias Brox (@tobixen)
* #628 - ISSUE-627: Add handling of Retry-After header for 429 and 503 status codes (code incorporated into master) -- Tema (@temsocial)

### GitHub Issues Closed

* #71 - `add_object` vs `save_object` (reopened, reverted and closed)
* #128 - Calendar constructor should accept name parameter (long-standing issue) -- Tobias Brox (@tobixen)
* #342 - need support asyncio -- @ArtemIsmagilov
* #424 - implement support for JMAP protocol -- @ArtemIsmagilov
* #457 - Replace requests with niquests or httpx? -- Tobias Brox (@tobixen)
* #509 - Refactor the test configuration again -- Tobias Brox (@tobixen)
* #515 - CalendarObjectResource.id property returns UID -- Tobias Brox (@tobixen)
* #518 - Test setup: try to mute expected error/warning logging -- Tobias Brox (@tobixen)
* #580 - search.py is already ripe for refactoring -- Tobias Brox (@tobixen)
* #589 - Replace "black style" with ruff -- Tobias Brox (@tobixen)
* #590 - calendar.searcher() API for advanced search queries -- Tobias Brox (@tobixen)
* #601 - `get_davclient` to be importable from caldav -- Tobias Brox (@tobixen)
* #609 - How to get original RRULE when search expand=True? -- JS Moore (@jakkarth)
* #613 - Data representation API for efficient data access -- Tobias Brox (@tobixen)
* #621 - Using niquests makes import unreasonably slow -- @rymdbar
* #627 - Rate-limit / Retry-After handling -- Tema (@temsocial)
* #631 - Cannot create calendar event by AsyncDAVClient (fix implemented, pending user confirmation) -- Oleg Yurchik (@OlegYurchik)

### Credits

The following people contributed to this release through issue reports, pull requests, and/or commits:

* @ArtemIsmagilov
* Chris Coutinho (@cbcoutinho)
* @joshinils
* JS Moore (@jakkarth)
* Oleg Yurchik (@OlegYurchik)
* @rymdbar
* Sashank Bhamidi (@SashankBhamidi)
* Tema (@temsocial)
* Tobias Brox (@tobixen)

### Time Spent

Since the 2.2.1-release and excluding the JMAP-work done by Sashank,
Tobias has spent around 132 hours on this project.

In the 3.0-release, AI-tools have been used for improving quality and
speed.  My first impression was very good.  It seemed like the AI
understood the project, and it could fix things faster and better than
what I could do myself - I really didn't expect it to create any good
code at all.  Well, sometimes it does, other times not.  Soon enough I
also learned that the AI is good at creating crap code, breaking
things and Claude is particularly good at duplicating code and code
paths.  In the end, despite using Claude I've spent more time on this
release than what I had estimated.  However, I believe I've done a
quite through work on preserving backward-compatibility while also
developing a better API.

From my roadmap, those are the estimates:

* [x] 50 hours for ASync + improved API - fully done
* [x] 23 hours for fixing/closing old issues - fully done
* [ ] 12 hours for documentation - partly done
* [ ] 40 hours for fixing/closing issues related with scheduling in 3.2 - done the davical test server, estimated to take 6 hours.

In addition, lots of time spent on things that aren't covered by the roadmap:

* The caldav-server-tester utility (but none of it into "polishing and releasing" as the roadmap says)
* More docker test servers
* Responding fast to inbound issues and pull requests
* Communication and collaboration
* The release itself (running tests towards lots of servers with quirks - like having to wait for several minutes from an event is edited until it can be found through a search operation - looking through and making sure the CHANGELOG is complete, etc) is quite tedious and easily takes several days - weeks if it's needed to tweak on workarounds and compatbility hints to get the tests passing.
