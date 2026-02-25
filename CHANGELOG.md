# Changelog

## HTTP Library Dependencies

As of v3.x, **niquests** is used for HTTP communication. It's a backward-compatible fork of requests that supports both sync and async operations, as well as HTTP/2 and HTTP/3 and many other things.  Fallbacks to other libraries are implemented - read more in [HTTP Library Configuration](docs/source/http-libraries.rst).

## Meta

This file should adhere to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), but it's manually maintained, and I have some extra sections in it.  Notably an executive summary at the top,  "Breaking Changes" or "Potentially Breaking Changes", list of GitHub issues/pull requests closed/merged, information on changes in the test framework, credits to people assisting, an overview of how much time I've spent on each release, and an overview of calendar servers the release has been tested towards.

Changelogs prior to v2.0 is pruned, but was available in the v2.x releases

This project should adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html), though for pre-releases PEP 440 takes precedence.

## [3.0.0a1] - 2026-02-01 (Alpha Release)

**This is an alpha release for testing purposes.** The API may change before the stable 3.0.0 release. Please report issues at https://github.com/python-caldav/caldav/issues

### Highlights

There shouldn't be many breaking changes in version 3.0, but there are massive code changes in version 3.0:

* **Full async support** using a Sans-I/O architecture. The same domain objects (Calendar, Event, Todo, etc.) now work with both synchronous and asynchronous clients. The async client uses niquests by default; httpx is also supported for projects that already have it as a dependency.
* **Sans-I/O architecture** -- internal refactoring separates protocol logic (XML building/parsing) from I/O into a layered architecture: protocol layer (`caldav/protocol/`), operations layer (`caldav/operations/`), and response handling (`caldav/response.py`). This enables code reuse between sync and async implementations and improves testability.
* **Lazy imports** -- `import caldav` is now significantly faster due to PEP 562 lazy loading. Heavy dependencies (lxml, niquests, icalendar) are deferred until first use. (https://github.com/python-caldav/caldav/issue/621)
* **API naming consistency** -- methods have been renamed for consistency. Server-fetching methods use `get_` prefix, capability checks use `supports_*()`. Old method names still work but are deprecated.
* **Ruff replaces Black** -- code formatting now uses ruff instead of Black, causing cosmetic changes throughout the codebase.
* **Expanded compatibility hints** -- server-specific workarounds added for Zimbra, Bedework, CCS (Apple CalendarServer), Davis, DAViCal, GMX, ecloud, Synology, Posteo, PurelyMail, and more.
* Quite some other refactoring work has been done.

### Breaking Changes

(Be aware that some of the 2.x minor-versions also tagged some "Potentially Breaking Changes")

* **Minimum Python version**: Python 3.10+ is now required (was 3.8+).
* **Test Server Configuration**: `tests/conf.py` has been removed and `conf_private.py` will be ignored.  See the Test Framework section below.
* **`object.py` has been removed** as well as the `from caldav.object import *` in `caldav/__init__.py`.  Some classes etc may appear to be missing, but the most important ones should still exist directly in the `caldav.*` namespace.
* **Config file parse errors now raise exceptions**: `caldav.config.read_config()` now raises `ValueError` on YAML/JSON parse errors instead of logging and returning an empty dict. This ensures config errors are detected early.

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
(Those methods do actively ask the server if they support the things.  In my caldav-server-tester script I define a `check` to be something that is actively probing, while `is_supported()` would be a configuration lookup).

Additionally, direct `DAVClient()` instantiation should migrate to `get_davclient()` factory method (see `docs/design/API_NAMING_CONVENTIONS.md`)

### Added

* **Full async API** -- New `AsyncDAVClient` and async-compatible domain objects:
  ```python
  from caldav.async_davclient import get_davclient

  async with await get_davclient(url="...", username="...", password="...") as client:
      principal = await client.get_principal()
      calendars = await client.get_calendars()
      for cal in calendars:
          events = await cal.get_events()
  ```
* **Sans-I/O architecture** -- Internal refactoring separates protocol logic from I/O:
  - Protocol layer (`caldav/protocol/`): Pure functions for XML building/parsing with typed dataclasses (DAVRequest, DAVResponse, PropfindResult, CalendarQueryResult)
  - Operations layer (`caldav/operations/`): Sans-I/O business logic for CalDAV operations (properties, search, calendar management, principal discovery)
  - Response layer (`caldav/response.py`): Shared `BaseDAVResponse` for sync/async
  - Data state (`caldav/datastate.py`): Strategy pattern for managing data representations (raw string, icalendar, vobject) -- avoids unnecessary parse/serialize cycles
* **Lazy imports (PEP 562)** -- `import caldav` is now fast. Heavy dependencies (lxml, niquests, icalendar) are deferred until first use. https://github.com/python-caldav/caldav/pull/621
* **`DAVObject.name` deprecated** -- use `get_display_name()` instead. The old `.name` property now emits `DeprecationWarning`.
* Added python-dateutil and PyYAML as explicit dependencies (were transitive)
* Quite some methods have been renamed for consistency and to follow best current practices.  See the deprecation section.
* `Calendar` class now accepts a `name` parameter in its constructor, addressing a long-standing API inconsistency (https://github.com/python-caldav/caldav/issues/128)
* **Data representation API** -- New efficient data access via `CalendarObjectResource` properties (https://github.com/python-caldav/caldav/issues/613):
  - `.icalendar_instance` -- parsed icalendar object (lazy loaded)
  - `.vobject_instance` -- parsed vobject object (lazy loaded)
  - `.data` -- raw iCalendar string
  - Context managers `edit_icalendar_instance()` and `edit_vobject_instance()` for safe mutable access
  - `get_data()`, `get_icalendar_instance()`, `get_vobject_instance()` return copies for read-only access
  - Internal `DataState` class manages caching between formats
* **CalendarObjectResource.id property** -- Returns the UID of calendar objects (https://github.com/python-caldav/caldav/issues/515)
* **calendar.searcher() API** -- Factory method for advanced search queries (https://github.com/python-caldav/caldav/issues/590):
  ```python
  searcher = calendar.searcher()
  searcher.add_filter(...)
  results = searcher.search()
  ```
* **`get_calendars()` and `get_calendar()` context managers** -- Module-level factory functions that create a client, fetch calendars, and clean up on exit:
  ```python
  with get_calendars(url="...", username="...", password="...") as calendars:
      for cal in calendars:
          ...
  ```
* **Base+override feature profiles** -- YAML config now supports inheriting from base feature profiles:
  ```yaml
  my-server:
      features:
          base: nextcloud
          search.comp-type: unsupported
  ```
* **Feature validation** -- `caldav.config` now validates feature configuration and raises errors on unknown feature names
* **URL space validation** -- `caldav.lib.url` now validates that URLs don't contain unquoted spaces
* **Fallback for missing calendar-home-set** -- Client falls back to principal URL when `calendar-home-set` property is not available
* **Load fallback for changed URLs** -- `CalendarObjectResource.load()` falls back to UID-based lookup when servers change URLs after save
* **Retry-After / rate-limit handling** (RFC 6585 / RFC 9110) -- `DAVClient` now exposes `rate_limit_handle`, `rate_limit_default_sleep`, and `rate_limit_max_sleep` parameters. When `rate_limit_handle=True` the client automatically sleeps and retries on 429 Too Many Requests and 503 Service Unavailable responses that carry a `Retry-After` header. When `rate_limit_handle=False` (default) a `RateLimitError` is raised immediately so callers can implement their own back-off strategy. https://github.com/python-caldav/caldav/issues/627

### Fixed

* RFC 4791 compliance: Don't send Depth header for calendar-multiget REPORT (clients SHOULD NOT send it, but servers MUST ignore it per §7.9)
* Fixed `ssl_verify_cert` not passed through in `get_sync_client` and `get_async_client`
* Fixed `_derive_from_subfeatures` partial-config derivation bug
* Fixed feature name parsing when names include `compatibility_hints.` prefix
* Fixed recursive `_search_with_comptypes` when `search.comp-type` is broken
* Fixed pending todo search on servers with broken comp-type filtering
* Fixed URL path quoting when extracting calendars from PROPFIND results
* Removed spurious warning on URL path mismatch, deduplicated `get_properties`
* Fixed `create-calendar` feature incorrectly derived as unsupported
* Fixed various async test issues (awaiting sync calls, missing feature checks, authorization error handling)
* Fixed `search.category` features to use correct `search.text.category` names

### Changed

* Sync client (`DAVClient`) now shares common code with async client via `BaseDAVClient`
* Response handling unified in `BaseDAVResponse` class
* Search refactored to use generator-based Sans-I/O pattern -- `_search_impl` yields `(SearchAction, data)` tuples consumed by sync or async wrappers
* Test configuration migrated from legacy `tests/conf.py` to new `tests/test_servers/` framework
* Configuration system expanded: `get_connection_params()` provides unified config discovery with clear priority (explicit params > test server config > env vars > config file)
* `${VAR}` and `${VAR:-default}` environment variable expansion in config values
* Ruff replaces Black for code formatting
* `caldav/objects.py` backward-compatibility shim removed (imports go directly to submodules)

### Test Framework

* **New `tests/test_servers/` module** -- Complete rewrite of test infrastructure:
  - `TestServer` base class hierarchy (EmbeddedTestServer, DockerTestServer, ExternalTestServer)
  - YAML-based server configuration (`tests/caldav_test_servers.yaml.example`)
  - `ServerRegistry` for server discovery and lifecycle management
  - `client_context()` and `has_test_servers()` helpers
* **New Docker test servers**: CCS (Apple CalendarServer), DAViCal, Davis, Zimbra
* **Updated Docker configs**: Baikal, Cyrus, Nextcloud, SOGo
* Added pytest-asyncio for async test support
* Added deptry for dependency verification in CI
* Added lychee link-check workflow
* Added `convert_conf_private.py` migration tool for old config format
* Removed `tests/conf.py`, `tests/conf_baikal.py`, `tests/conf_private.py.EXAMPLE`
* **New test suites**:
  - `test_async_davclient.py` (821 lines) -- Async client unit tests
  - `test_async_integration.py` (466 lines) -- Async integration tests
  - `test_operations_*.py` (6 files) -- Operations layer unit tests
  - `test_protocol.py` (319 lines) -- Protocol layer unit tests
  - `test_lazy_import.py` (141 lines) -- PEP 562 lazy import verification
* Fixed Nextcloud Docker test server tmpfs permissions race condition

### GitHub Pull Requests Merged

* #621 - Lazy-load heavy dependencies to speed up import caldav
* #622 - Fix overlong inline literal, replace hyphens with en-dashes
* #607 - Add deptry for dependency verification

### GitHub Issues Closed

* #613 - Data representation API for efficient data access
* #590 - calendar.searcher() API for advanced search queries
* #515 - CalendarObjectResource.id property returns UID
* #609 - How to get original RRULE when search expand=True?
* #128 - Calendar constructor should accept name parameter (long-standing issue)

### Security

* UUID1 usage in UID generation (`calendarobject_ops.py`) may embed the host MAC address in calendar UIDs. Since calendar events are shared with third parties, this is a privacy concern. Planned fix: switch to UUID4.

### Compatibility Hints Expanded

Server-specific workarounds have been significantly expanded. Profiles added or updated for:

* **Zimbra** -- search.is-not-defined, delete-calendar, recurrences.count, case-sensitive search
* **Bedework** -- save-load.journal, save-load.todo.recurrences.thisandfuture, search.recurrences.expanded.todo, search.time-range.alarm
* **CCS (Apple CalendarServer)** -- save-load.journal unsupported, various search hints
* **Davis** -- principal-search at parent level, mixed-calendar features
* **GMX** -- rate-limit, basepath correction
* **ecloud** -- create-calendar unsupported, search.is-not-defined, case-sensitive
* **Synology** -- is-not-defined, wipe-calendar cleanup
* **SOGo** -- save-load.journal ungraceful, case-insensitive, delete-calendar
* **Posteo** -- search.combined-is-logical-and unsupported
* **PurelyMail** -- search.time-range.todo ungraceful
* **DAViCal** -- various search and sync hints
* **Xandikos** -- freebusy-query now supported in v0.3.3
* **Baikal/Radicale** -- case-sensitive search, principal-search features

## [2.2.6] - [2026-02-01]

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

## [2.2.3] - [2025-12-06]

### Fixed

* Some servers did not support the combination of HTTP/2-multiplexing and authentication.  Two workarounds fixed; baikal will specifically not use multiplexing, and an attempt to authenticate without multiplexing will be made upon authentication problems.  Fixes https://github.com/python-caldav/caldav/issues/564
* The DTSTAMP is mandatory in icalendar data.  The `vcal.fix`-scrubber has been updated to make up a DTSTAMP if it's missing.  Fixes https://github.com/python-caldav/caldav/issues/504

## [2.2.2] - [2025-12-04]

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

@ArtemIsmagilov, @cbcoutinho, @cdce8p, @dieterbahr, @dozed, @Ducking2180, @edel-macias-cubix, @erahhal, @greve, @jannistpl, @julien4215, @Kreijstal, @lbt, @lothar-mar, @mauritium, @moi90, @niccokunzmann, @oxivanisher, @paramazo, @pessimo, @Savvasg35, @seanmills1020, @siderai, @slyon, @smurfix, @soundstorm, @thogitnet, @thomasloven, @thyssentishman, @ugniusslev, @whoamiafterall, @yuwash, @zealseeker, @Zhx-Chenailuoding, @Zocker1999NET, @Sashank, @Claude and @tobixen

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

## [2.1.2] - [2025-11-08]

Version 2.1.0 comes without niquests in the dependency file.  Version 2.1.2 come with niquests in the dependency file.  Also fixed up some minor mistakes in the CHANGELOG.

## [2.1.1] - [2025-11-08] [YANKED]

Version 2.1.0 comes without niquests in the dependency file.  Version 2.1.1 should come with niquests in the dependency file, but I made a mistake.

## [2.1.0] - [2025-11-08]

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

## [2.0.1] - [2025-06-24]

Due to feedback we've fallen back from niquests to requests again.

## Changes

* I was told in https://github.com/python-caldav/caldav/issues/530 that the niquests dependency makes it impossible to package the library, so I've reverted the requests -> niquests changeset.

## [2.0.0] - [2025-06-23]

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
