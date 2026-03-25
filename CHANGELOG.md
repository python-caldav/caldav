# Changelog

## HTTP Library Dependencies

As of v3.x, **niquests** is used for HTTP communication. It's a backward-compatible fork of requests that supports both sync and async operations, as well as HTTP/2 and HTTP/3 and many other things.  Fallbacks to other libraries are implemented - read more in [HTTP Library Configuration](docs/source/http-libraries.rst).

## Meta

This file should adhere to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), but I do have some extra sections in it.  Notably an executive summary at the top,  "Breaking Changes" or "Potentially Breaking Changes", list of GitHub issues/pull requests closed/merged, information on changes in the test framework, list of tests run, my work effort, credits to people assisting, an overview of how much time I've spent on each release, and an overview of calendar servers the release has been tested towards.

Changelogs prior to v2.0 is pruned, but was available in the v2.x releases

This project should adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html), though for pre-releases PEP 440 takes precedence.

## [Unreleased]

### Fixed

* Reusing a `CalDAVSearcher` across multiple `search()` calls could yield inconsistent results: the first call would return only pending tasks (correct), but subsequent calls would change behaviour because `icalendar_searcher.Searcher.check_component()` mutated the `include_completed` field from `None` to `False` as a side-effect.  Fixed by passing a copy with `include_completed` already resolved to `filter_search_results()`, leaving the original searcher object unchanged.  Fixes https://github.com/python-caldav/caldav/issues/650
* `Calendar.get_supported_components()` raised `KeyError` when the server did not include the `supported-calendar-component-set` property in its response.  RFC 4791 section 5.2.3 states this property is optional and that its absence means all component types are accepted; the method now returns `["VEVENT", "VTODO", "VJOURNAL"]` in that case.  Fixes https://github.com/python-caldav/caldav/issues/653

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

## [2.2.6] - 2026-02-01

### Fixed

* Fixed potential IndexError in URL path joining when path is empty
* Fixed NameError in search.py caused by missing import of `logging` module, which was masking actual errors when handling malformed iCalendar data.  https://github.com/python-caldav/caldav/issues/614

### Changed

* Updated example files to use the recommended `get_davclient()` factory function instead of `DAVClient()` directly

### Test Framework

* Added deptry for dependency verification in CI

### GitHub Pull Requests Merged

* #607 - Add deptry for dependency verification
* #605 - Update examples to use get_davclient() instead of DAVClient()

### GitHub Issues Closed

* #612 - Export get_davclient from caldav package
* #614 - Missing import logging in search.py causes NameError masking actual errors

(2.2.4 is without niquests in the dependencies.  2.2.5 is with niquests.  2.2.6 is with niquests and a tiny CHANGELOG-fix)

### Added

* `get_davclient` is now exported from the `caldav` package, allowing `from caldav import get_davclient`.  https://github.com/python-caldav/caldav/issues/612

## [2.2.3] - 2025-12-06]
### Fixed

* Some servers did not support the combination of HTTP/2-multiplexing and authentication.  Two workarounds fixed; baikal will specifically not use multiplexing, and an attempt to authenticate without multiplexing will be made upon authentication problems.  Fixes https://github.com/python-caldav/caldav/issues/564
* The DTSTAMP is mandatory in icalendar data.  The `vcal.fix`-scrubber has been updated to make up a DTSTAMP if it's missing.  Fixes https://github.com/python-caldav/caldav/issues/504

## [2.2.2] - 2025-12-04]
2.2.1 is released with requests support (mispelled riquests in 2.2.0), 2.2.2 with niquests support

## [2.2.1] - [2025-12-04]

Highlights:

* New ways to set up client connections:
  - For cloud-based services, it should suffice to pass username, password and the name of the service, no URL needed (though, just some few providers supported so far)
  - If the username is in email format, then it's generally not needed to pass a URL.
* v2.2 comes with lots of workarounds around lack of feature support in the servers - notably the sync-token API will work also towards servers not supporting sync-tokens.  In some cases lack of server functionality is detected, but as for now it may be needed to specify what server one is user through the `features` configuration flag.
* v2.2 supports more complex searches.  Client-side filtering will be utilized for the things that aren't supported on the server side.

### Potentially Breaking Changes

(More information on the changes in the Changed section)

* **Search results may differ** due to workarounds for various server compatibility problems.  For some use cases this may be a breaking change.  https://xkcd.com/1172/
* **New dependencies**.  As far as I understand the SemVer standard, new dependencies can be added without increasing the major version number - but for some scenarios where it's hard to add new dependencies, this may be a breaking change.
  - The python-dns package is used for RFC6764 discovery.    This is a well-known package, so the security impact should be low.  This library is only used when doing such a recovery.  If anyone minds this dependency, I can change the project so this becomes an optional dependency.
  - Some code has been split out into a new package - `icalendar-searcher`. so this may also break if you manage the dependencies manually.  As this package was made by the maintainer of the CalDAV package, the security impact of adding this dependency should be low.
* Potentially major **performance problems**: rather than throwing errors, the sync-token-API may now fetch the full calendar.  This change is intended to be un-breaking, but for people having very big calendars and syncing them to a mobile device with limited memory, bandwidth, CPU and battery, this change may be painful.  (If a servers is marked to have "fragile" support for sync-tokens, the fallback will apply to those servers too).
* **Very slow test suite** due to lots of docker-containers spun up with verious server implementations.  See the "Test Suite" section below.

### Changed

* Transparent handling of calendar servers not supporting sync-tokens.  The API will yield the same result, albeit with more bandwidth and memory consumption.
* I'm still working on "compatibility hints".  Unfortunately, documentation is still missing.
* **Major refactoring!**  Some of the logic has been pushed out of the CalDAV package and into a new package, icalendar-searcher.  New logic for doing client-side filtering of search results have also been added to that package.  This refactoring enables possibilities for more advanced search queries as well as client-side filtering.
  * For advanced search queries, it's needed to create a `caldav.CalDAVSearcher` object, add filters and do a `searcher.search(cal)` instead of doing `cal.search(...)`.
* **Server compatibility improvements**: Significant work-arounds added for inconsistent CalDAV server behavior, aiming for consistent search results regardless of the server in use. Many of these work-arounds require proper server compatibility configuration via the `features` / `compatibility_hints` system. This may be a **breaking change** for some use cases, as backward-bug-compatibility is not preserved - searches may return different results if the previous behavior was relying on server quirks.

### Fixed

* As noted above, quite some changes have been done to searches.  One may argue if this is breaking changes, changes or bugfixes.  At least github issues #434, #461, #566 and #509 has been closed in the process.
* A minor bug in the FeatureSet constructor was fixed, sometimes information could be lost.
* Downgraded a CRITICAL error message to INFO, for some conditions that clearly wasn't CRITICAL (HTML error responses from server or wrong content-type given, when XML was expected)
* Probably some other minor bug fixes (though, most of the bugs fixed in this release was introduced after 2.1.2)
* A user managed to trigger a crash bug in the search in https://github.com/python-caldav/caldav/issues/587 - this has indirectly been fixed through the refactorings.

### Added

* **New ways to configure the client connection, new parameters**
  - **RFC 6764 DNS-based service discovery**: Automatic CalDAV/CardDAV service discovery using DNS SRV/TXT records and well-known URIs. Users can now provide just a domain name or email address (e.g., `DAVClient(username='user@example.com')`) and the library will automatically discover the CalDAV service endpoint. The discovery process follows RFC 6764 specification.  This involves a new required dependency: `dnspython` for DNS queries.  DNS-based discovery can be disabled in the davclient connection settings, but I've opted against implementing a fallback if the dns library is not installed.
  - Use `features: posteo` instead of `url: https://posteo.de:8443/` in the connection configuration.
  - Use `features: nextcloud` and `url: my.nextcloud.provider.eu` instead of `url: https://my.nextcloud.provider.eu/remote.php/dav`
  - Or even easier, use `features: nextcloud` and `username: tobixen@example.com`
  - New `require_tls` parameter (default: `True`) prevents DNS-based downgrade attacks
  - The client connection parameter `features` may now simply be a string label referencing a well-known server or cloud solution - like `features: posteo`.  https://github.com/python-caldav/caldav/pull/561
  - The client connection parameter `url` is no longer needed when referencing a well-known cloud solution. https://github.com/python-caldav/caldav/pull/561
  * The client connection parameter `url` may contain just the domain name (without any slashes).  It may then either look up the URL path in the known caldav server database, or through RFC6764
* **New interface for searches**  `mysearcher = caldav.CalDAVSearcher(...) ; mysearcher.add_property_filter(...) ; mysearcher.search(calendar)`.  It's a bit harder to use, but opens up the possibility to do more complicated searches.
* **Collation support for CalDAV text-match queries (RFC 4791 § 9.7.5)**: CalDAV searches may now pass different collation attributes to the server, enabling case-insensitive searches. (but more work on this may be useful, see https://github.com/python-caldav/caldav/issues/567).  The `CalDAVSearcher.add_property_filter()` method now accepts `case_sensitive` and `collation` parameters. Supported collations include:
  - `i;octet` (case-sensitive, binary comparison) - default
  - `i;ascii-casemap` (case-insensitive for ASCII characters, RFC 4790)
  - `i;unicode-casemap` (Unicode case-insensitive, RFC 5051 - server support may vary)
* Client-side filtering method: `CalDAVSearcher.filter()` provides comprehensive client-side filtering, expansion, and sorting of calendar objects with full timezone preservation support.
* Example code: New `examples/collation_usage.py` demonstrates case-sensitive and case-insensitive calendar searches.

### Security

There is a major security flaw with the RFC6764 discovery.  If the DNS is not trusted (public hotspot, for instance), someone can highjack the connection by spoofing the service records.  The protocol also allows to downgrade from https to http.  Utilizing this it may be possible to steal the credentials.  Mitigations:
 * DNSSEC is the ultimate soluion, but DNSSEC is not widely used.  I tried implementing robust DNSSEC validation, but it was too complicated.
 * Require TLS.  By default, connections through the autodiscovery is required to use TLS.
 * Decline domain change.  If acme.com forwards to caldav.acme.com, it will be accepted, if it forward to evil.hackers.are.us the connection is declined.

Also, the RFC6764 discovery may not always be robust, causing fallbacks and hence a non-deterministic behaviour.

### Deprecated

* `Event.expand_rrule` will be removed in some future release, unless someone protests.
* `Event.split_expanded` too.  Both of them were used internally, now it's not.  It's dead code, most likely nobody and nothing is using them.

### GitHub Issues Closed

- #574 - SECURITY: check domain name on auto-discovery (2025-11-29) - https://github.com/python-caldav/caldav/issues/574 - fixes issues introduced after previous release
- #532 - Replace compatibility flags list with compatibility matrix dict (2025-11-10) https://github.com/python-caldav/caldav/issues/532 - this process is not completely done, a new issue has been raised for mopping up the rest
- #402 - Server compatibility hints (2025-12-03) https://github.com/python-caldav/caldav/issues/402 - sort of duplicate of #532
- #463 - Try out paths to find caldav base URL (2025-11-10) https://github.com/python-caldav/caldav/issues/463 - sort of solved through the compatbility hints file.
- #461 - Path handling error with non-standard URL formats (2025-12-02) https://github.com/python-caldav/caldav/issues/461 - the issue ended up identifying the need to work around missing server-side support for sync-token, this has been fixed
- #434 - Search event with summary (2025-11-27) https://github.com/python-caldav/caldav/issues/434 - the new search interface contains work-arounds for server-side incompatibilities as well as advanced client-side filtering
- #401 - Some server needs explicit event or task when doing search (2025-07-19) https://github.com/python-caldav/caldav/issues/401 - code now contains clean workarounds for fetching everything regardless of server side support
- #102 - Support for RFC6764 - find CalDAV URL through DNS lookup (created 2020, closed 2025-11-27) - https://github.com/python-caldav/caldav/issues/102
- #311 - Google calendar - make authentication simpler and document it (created 2023, closed 2025-06-16) - https://github.com/python-caldav/caldav/issues/311 - no work on Google has been done, but user-contributed examples and documentation has been refactored, polished and published.
- #372 - Server says "Forbidden" when creating event with timezone (created 2024, closed 2025-12-03) - https://github.com/python-caldav/caldav/issues/372 - it's outside the scope supporting the old dateutil.tz objects in the CalDAV library.  Checks have been added to the caldav-server-checker script to verify that the new-style Timezone objects work.
- #351 - `calendar.search`-method with timestamp filters yielding too much (created 2023, closed 2025-12-02) - https://github.com/python-caldav/caldav/issues/351 the new search interface may do client-side filtering
- #340 - 507 error during collection sync (created 2023, closed 2025-12-03) - https://github.com/python-caldav/caldav/issues/340 - this should be fixed by the new sync-tokens workaround
- #587 - Calendar.search broken with TypeError: Calendar.search() got multiple values for argument 'sort_keys' (created 2025-12-04, closed 2025-12-04) -  https://github.com/python-caldav/caldav/issues/587 - this bug has indirectly been fixed through the refactorings.

### GitHub Pull Requests Merged

- #584 - Bedework server support (2025-12-04) - https://github.com/python-caldav/caldav/pull/584
- #583 - Transparent fallback for servers not supporting sync tokens (2025-12-02) - https://github.com/python-caldav/caldav/pull/583
- #582 - Fix docstrings in Principal and Calendar classes (2025-12-02) - https://github.com/python-caldav/caldav/pull/582
- #581 - SOGo server support (2025-12-02) - https://github.com/python-caldav/caldav/pull/581
- #579 - Sync-tokens compatibility feature flags (2025-11-29) - https://github.com/python-caldav/caldav/pull/579
- #578 - Docker server testing cyrus (2025-12-02) - https://github.com/python-caldav/caldav/pull/578
- #576 - Add RFC 6764 domain validation to prevent DNS hijacking attacks (2025-11-29) - https://github.com/python-caldav/caldav/pull/576
- #575 - Add automated Nextcloud CalDAV/CardDAV testing framework (2025-11-29) - https://github.com/python-caldav/caldav/pull/575
- #573 - Add Baikal Docker test server framework for CI/CD (2025-11-28) - https://github.com/python-caldav/caldav/pull/573
- #570 - Add RFC 6764 DNS-based service discovery (2025-11-27) - https://github.com/python-caldav/caldav/pull/570
- #569 - Improved substring search (2025-11-27) - https://github.com/python-caldav/caldav/pull/569
- #566 - More compatibility work (2025-11-27) - https://github.com/python-caldav/caldav/pull/566
- #563 - Refactoring search and filters (2025-11-19) - https://github.com/python-caldav/caldav/pull/563
- #561 - Connection details in the server hints (2025-11-10) - https://github.com/python-caldav/caldav/pull/561
- #560 - Python 3.14 support (2025-11-09) - https://github.com/python-caldav/caldav/pull/560

### Test Framework

* **Automated Docker testing framework** using Docker containers, if docker is available.
  * Cyrus, NextCloud and Baikal added so far.
  * For all of those, automated setups with a well-known username/password combo was a challenge.  I had planned to add more servers, but this proved to be too much work.
  * The good thing is that test coverage is increased a lot for every pull request, I hope this will relieving me of a lot of pain learning that the tests fails towards real-world servers when trying to do a release.
  * The bad thing is that the test runs takes a lot more time.  Use `pytest -k Radicale` or `pytest -k Xandikos` - or run the tests in an environment not having access to docker if you want a quicker test run - or set up a local `conf_private.py` where you specify what servers to test.  It may also be a good idea to run `start.sh` and `stop.sh` in `tests/docker-test-servers/*` manually so the container can stay up for the whole duration of the testing rather than being taken up and down for every test.
  * **Docker volume cleanup**: All teardown functions should automatically prune ephemeral Docker volumes to prevent `/var/lib/docker/volumes` from filling up with leftover test data. This applies to Cyrus, Nextcloud, and Baikal test servers.
* Since the new search code now can work around different server quirks, quite some of the test code has been simplified.  Many cases of "make a search, if server supports this, then assert correct number of events returned" could be collapsed to "make a search, then assert correct number of events returned" - meaning that **the library is tested rather than the server**.
* Some of the old "compatibility_flags" that is used by the test code has been moved into the new "features"-structure in `caldav/compatibility_hints.py`.  Use the package caldav-server-checker to check the feature-set of your CalDAV server (though, as for now the last work done is on a separate branch.  A relase will be made soon).
* Note, the `testCheckCompatibility` will be run if and only if the caldav-server-checker package is installed and available.  If the package is installed, the version of it has to correspond exactly to the caldav version - and even then, it may break for various reasons (the caldav server tester is still under development, no stable release exists yet).  The corresponding version of the package has not been released yet (it's even not merged to the main branch).  I hope to improve on this somehow before the next release.  It can be a very useful test - if the compatibility configuration is wrong, tests may break or be skipped for the wrong reasons.

### Time Spent

(The "Time Spent"-section was missing from the 2.1-release, so this includes everything since 2.0)

The maintainer has spent around 230 hours since version 2.0.0, plus paid some money for AI-assistance from Claude.  This time includes work on the two sub-projects icalendar-searcher and caldav-server-tester (not released yet).

The estimation given at the road map was 28h for "Server checker and server compatibility hints project", 8h for "Maintain and expand the test server list", and 12h for "Outstanding issues slated for v3.0".  Including the Claude efforts, consider this to be 5x as much time as estimated.

Some few reasons of the overrun:

* Quite much of this time has been put down into the  caldav-server-tester project, and the icalendar-search project also took me a few days to complete.
* "Let's make sure to support both case-sensitive and case-insensitive search" may sound like a simple task, but collations is a major tarpit!  Now I know that the correct uppercase version of "istanbul" depends on the locale used ...
* The test framework with docker contained servers was also a major tarpit.  "Why not just spin up server X in a docker container" - it sounded trivial, but then come the hard realites:
  - Most of the servers needs some extra configuration to get a test user with well-known username and password in place
  - Some servers are optimized for manual "installation and configuration", rather than automated setup with an epheremal disk volume.
  - Some servers have external requirements, like a stand-alone database server, requiring significant amounts of configuration for connecting the database and the calendar server (database username, password, connection details, +++)
  - Docker services in the "GitHub Actions" that I use for automated external testing has to be set up completely different and independently from the local tests.  This is also a tarpit as I cannot inspect and debug problems so easily, every test run takes very long time and generates several megabytes of logs.
  - Luckily, with the new caldav-server-tester script it's easy to get the compatibility configuration readily set up.  In theory.  In practice, I need to do quite some work on the caldav-server-tester to correctly verify all the unique quirks of the new server.
  - In practice, the test suite will still be breaking, requiring lots of debugging figuring out of the problems.
* Quite many other rabbit holes and tarpits have been found on the way, but I digress.  This is quite a bit outside the scope of a CHANGELOG.

### Credits

The following contributors (by GitHub username) have assisted by reporting issues, submitting pull requests and provided feedback:

@ArtemIsmagilov, @cbcoutinho, @cdce8p, @dieterbahr, @dozed, @Ducking2180, @edel-macias-cubix, @erahhal, @greve, @jannistpl, @julien4215, @Kreijstal, @lbt, @lothar-mar, @mauritium, @moi90, @niccokunzmann, @oxivanisher, @paramazo, @pessimo, @Savvasg35, @seanmills1020, @siderai, @slyon, @smurfix, @soundstorm, @thogitnet, @thomasloven, @thyssentishman, @ugniusslev, @whoamiafterall, @yuwash, @zealseeker, @Zhx-Chenailuoding, @Zocker1999NET, @SashankBhamidi, @Claude and @tobixen

### Test runs before release

Local docker containers and python server instances:

* Radicale
* Xandikos
* Nextcloud
* Baikal
* Cyrus
* SOGo
* Bedework

External servers tested:

* eCloud (NextCloud)
* Zimbra
* Synology
* Posteo
* Baikal
* Robur

Servers and platforms not tested this time:

* PurelyMail (partly tested - but test runs takes EXTREMELY long time due to the search-cache server peculiarity, and the test runs still frequently fails in non-deterministic ways).
* GMX (It throws authorization errors, didn't figure out of it yet)
* DAViCal (my test server is offline)

I should probably look more into the breakages with PurelyMail and GMX.

Those servers ought to be tested, but I'm missing accounts/capacity to do it at the moment:

* Google
* iCloud
* FastMail
* calendar.mail.ru
* Lark
* all-inkl.com
* OX

## [2.1.2] - 2025-11-08

Version 2.1.0 comes without niquests in the dependency file.  Version 2.1.2 come with niquests in the dependency file.  Also fixed up some minor mistakes in the CHANGELOG.

## [2.1.1] - 2025-11-08 [YANKED]

Version 2.1.0 comes without niquests in the dependency file.  Version 2.1.1 should come with niquests in the dependency file, but I made a mistake.

## [2.1.0] - 2025-11-08

I'm working on a [caldav compatibility checker](https://github.com/tobixen/caldav-server-tester) side project.  While doing so, I'm working on redefining the "compatibility matrix".  This should only affect the test code.  **If you maintain a file `tests/conf_private.py`, chances are that the latest changesets will break**  Since "running tests towards private CalDAV servers" is not considered to be part of the public API, I deem this to be allowed without bumping the major version number.  If you are affected and can't figure out of it, reach out by email, GitHub issue or GitHub discussions.  (Frankly, I'm interessted if anyone except me uses this, so feel free to reach out also if you can figure out of it).

As always, the new release comes with quite some bugfixes, compatibility fixes and workarounds improving the support for various calendar servers observed in the wild.

### Potentially Breaking Changes

* As mentioned above, if you maintain a file `tests/conf_private.py`, chances are that your test runs will break.  Does anyone except me maintain a `tests/conf_private.py`-file?  Please reach out by email, GitHub issues or GitHub discussions.

### Changed

* The search for pending tasks will not do send any complicated search requests to the server if it's flagged that the server does not support such requests. (automatically setting such flags will come in a later version)
* If the server is flagged not to support MKCALENDAR but supporting MKCOL instead (baikal), then it will use MKCOL when creating a calendar. (automatically setting such flags will come in a later version)
* In 1.5.0, I moved the compability matrix from the tests directory and into the project itself - now I'm doing a major overhaul of it.  This change is much relevant for end users yet - but already now it's possible to configure "compatibility hints" when setting up the davclient, and the idea is that different kind of workarounds may be applied depending on the compatibility-matrix.  Search without comp-type is wonky on many servers, now the `search`-method will automatically deliver a union of a search of the three different comp-types if a comp-type is not set in the parameters *and* it's declared that the compatibility matrix does not work.  In parallel I'm developing a stand-alone tool caldav-server-tester to check the compatibility of a caldav server.  https://github.com/python-caldav/caldav/issues/532 / https://github.com/python-caldav/caldav/pull/537
* Littered the code with `try: import niquests as requests except: import requests`, making it easier to flap between requests and niquests.
* Use the "caldav" logger consistently instead of global logging.  https://github.com/python-caldav/caldav/pull/543 - fixed by Thomas Lovden

### Fixes

* A search without filtering on comp-type on a calendar containing a mix of events, journals and tasks should return a mix of such.  (All the examples in the RFC includes the comp-type filter, so many servers does not support this).  There were a bug in the auto-detection of comp-type, so tasks would typically be wrapped as events or vice-versa.  https://github.com/python-caldav/caldav/pull/540
* Tweaks to support upcoming version 7 of the icalendar library.
* Compatibility-tweaks for baikal, but as for now manual intervention is needed - see https://github.com/python-caldav/caldav/pull/556 and https://github.com/python-caldav/caldav/issues/553
* @thyssentishman found a missing import after the old huge `objects.py` was broken up in smaller files.  Which again highlights that I probably have some dead, moot code in the project.  https://github.com/python-caldav/caldav/pull/554
* Bugfix on authentication - things broke on Baikal if authentication method (i.e. digest) was set in the config.  I found a quite obvious bug, I did not investigate why the test code has been passing on all the other servers.  Weird thing.
* Bugfix in the `davclient.principals`-method, allowing it to work on more servers - https://github.com/python-caldav/caldav/pull/559
* Quite some compatibility-fixing of the test code

### Added

* Support for creating a `CalendarObjectResource` from an icalendar `Event`, `Todo` etc, and not only `Calendar`.  Arguably a bugfix as it would be silently accepted and throw some arbitrary error, very confusing for end users.  https://github.com/python-caldav/caldav/issues/546

### Other

* Example code: Basic usage examples have been brushed up, thanks to David Greaves - https://github.com/python-caldav/caldav/pull/534
* PEP 639 conforming license expression in the pyproject.toml, thanks to Marc Mueller - https://github.com/python-caldav/caldav/pull/538

## [2.0.1] - 2025-06-24
Due to feedback we've fallen back from niquests to requests again.

### Changes

* I was told in https://github.com/python-caldav/caldav/issues/530 that the niquests dependency makes it impossible to package the library, so I've reverted the requests -> niquests changeset.

## [2.0.0] - 2025-06-23

Here are the most important changes in 2.0:

* Version 2.0 drops support for old python versions and replaces requests 2.x with niquests 3.x, a fork of requests.
* Major overhaul of the documentation
* Support for reading configuration from a config file or environmental variables - I didn't consider that to be within the scope of the caldav library, but why not - why should every application reinvent some configuration file format, and if an end-user have several applications based on python-caldav, why should he need to configure the caldav credentials explicitly for each of them?
* New method `davclient.principals()` to search for other principals on the server - and from there it's possible to do calendar searches and probe what calendars one have access to.  If the server will allow it.

### Deprecated

* `calendar.date_search` - use `calendar.search` instead.  (this one has been deprecated for a while, but only with info-logging).  This is almost a drop-in replacement, except for two caveats:
  * `date_search` does by default to recurrence-expansion when doing searches on closed time ranges.  The default value is `False` in search (this gives better consistency - no surprise differences when changing between open-ended and closed-ended searches, but it's recommended to use `expand=True` when possible).
  * In `calendar.search`, `split_expanded` is set to `True`.  This may matter if you have any special code for handling recurrences in your code.  If not, probably the recurrences that used to be hidden will now be visible in your search results.
* I introduced the possibility to set `expand='server'` and `expand='client'` in 1.x to force through expansion either at the server side or client side (and the default was to try server side with fallback to client side).  The four possible values "`True`/`False`/`client`/`server`" does not look that good in my opinion so the two latter is now deprecated, a new parameter `server_expand=True` will force server-side expansion now (see also the Changes section)
* The `event.instance` property currently yields a vobject.  For quite many years people have asked for the python vobject library to be replaced with the python icalendar objects, but I haven't been able to do that due to backward compatibility.  In version 2.0 deprecation warnings will be given whenever someone uses the `event.instance` property.  In 3.0, perhaps `event.instance` will yield a `icalendar` instance.  Old test code has been updated to use `.vobject_instance` instead of `.instance`.
* `davclient.auto_conn` that was introduced just some days ago has already been renamed to `davclient.get_davclient`.

### Added

* `event.component` is now an alias for `event.icalendar_component`.
* `get_davclient` (earlier called `auto_conn`) is more complete now - https://github.com/python-caldav/caldav/pull/502 - https://github.com/python-caldav/caldav/issues/485 - https://github.com/python-caldav/caldav/pull/507
  * It can read from environment (including environment variable for reading from test config and for locating the config file).
  * It can read from a config file.  New parameter `check_config_file`, defaults to true
  * It will probe default locations for the config file (`~/.config/caldav/calendar.conf`, `~/.config/caldav/calendar.yaml`, `~/.config/caldav/calendar.json`, `~/.config/calendar.conf`, `/etc/calendar.conf`, `/etc/caldav/calendar.conf` as for now)
  * Improved tests (but no test for configuration section inheritance yet).
  * Documentation, linked up from the reference section of the doc.
  * It's allowable with a yaml config file, but the yaml module is not included in the dependencies yet ... so late imports as for now, and the import is wrapped in a try/except-block
* New method `davclient.principals()` will return all principals on server - if server permits.  It can also do server-side search for a principal with a given user name - if server permits - https://github.com/python-caldav/caldav/pull/514 / https://github.com/python-caldav/caldav/issues/131
* `todo.is_pending` returns a bool.  This was an internal method, but is now promoted to a public method.  Arguably, it belongs to icalendar library and not here.  Piggybacked in through https://github.com/python-caldav/caldav/pull/526
* Support for shipping `auth_type` in the connection parameters.  With this it's possible to avoid an extra 401-request just to probe the authentication types.  https://github.com/python-caldav/caldav/pull/529 / https://github.com/python-caldav/caldav/issues/523
* If a server returns a HTML page together with the 401, there will now be another warning encouraging the user to use the new `auth_type` parameter.  https://github.com/python-caldav/caldav/pull/522 / https://github.com/python-caldav/caldav/issues/517, by edel-macias-cubix.

### Documentation and examples

* Documentation has been through a major overhaul.
* Added some information on how to connect to Google in the doc and examples.
* Looked through and brushed up the examples, two of them are now executed by the unit tests.  Added a doc section on the examples.
* Documentation issues https://github.com/python-caldav/caldav/issues/253 https://github.com/python-caldav/caldav/issues/311 https://github.com/python-caldav/caldav/issues/119 has been closed

### Fixed

* Support for Lark/Feishu got broken in the 1.6-release.  Issue found and fixed by Hongbin Yang (github user @zealseeker) in https://github.com/python-caldav/caldav/issues/505 and https://github.com/python-caldav/caldav/pull/506

### Changed

* https://github.com/python-caldav/caldav/issues/477 / https://github.com/python-caldav/caldav/pull/527 - vobject has been removed from the dependency list.  If you are using `event.vobject_instance` then you need to include the vobject dependency explicitly in your project.
* The request library has been in a feature freeze for ages and may seem like a dead end.  There exists a fork of the project niquests, we're migrating to that one.  This means nothing except for one additional dependency.  (httpx was also considered, but it's not a drop-in replacement for the requests library, and it's a risk that such a change will break compatibility with various other servers - see https://github.com/python-caldav/caldav/issues/457 for details).  Work by @ArtemIsmagilov, https://github.com/python-caldav/caldav/pull/455.
* Expanded date searches (using either `event.search(..., expand=True)` or the deprecated `event.date_search`) will now by default do a client-side expand.  This gives better consistency and probably improved performance, but makes 2.0 bug-incompatible with 1.x.
* To force server-side expansion, a new parameter server_expand can be used

### Removed

If you disagree with any of this, please raise an issue and I'll consider if it's possible to revert the change.

* Support for python 3.7 and 3.8
* Dependency on the requests library.
* The `calendar.build_date_search_query` was ripped out. (it was deprecated for a while, but only with info-logging - however, this was an obscure internal method, probably not used by anyone?)

### Changes in test framework

* Proxy test has been rewritten.  https://github.com/python-caldav/caldav/issues/462 / https://github.com/python-caldav/caldav/pull/514
* Some more work done on improving test coverage
* Fixed a test issue that would break arbitrarily doe to clock changes during the test run - https://github.com/python-caldav/caldav/issues/380 / https://github.com/python-caldav/caldav/pull/520
* Added test code for some observed problem that I couldn't reproduce - https://github.com/python-caldav/caldav/issues/397 - https://github.com/python-caldav/caldav/pull/521
* Wrote up some test code to improve code coverage - https://github.com/python-caldav/caldav/issues/93 - https://github.com/python-caldav/caldav/pull/526

### Time Spent

The maintainer has spent around 49 hours totally since 1.6.  That is a bit above estimate.  For one thing, the configuration file change was not in the original road map for 2.0.
