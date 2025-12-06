# Changelog

## IMPORTANT - niquests vs requests - flapping changeset

The requests library is stagnant, from 2.0.0 niquests has been in use.  It's a very tiny changeset, which resolved three github issues (and created a new one - see https://github.com/python-caldav/caldav/issues/564), fixed support for HTTP/2 and may open the door for an upcoming async proejct.  While I haven't looked much "under the bonnet", niquests seems to be a major upgrade of requests.  However, the niquest author has apparently failed cooperating well with some significant parts of the python community, so niquests pulls in a lot of other forked libraries as for now.  Shortly after releasing 2.0 I was requested to revert back to requests and release 2.0.1.  After 2.0.1, the library has been fixed so that it will always use niquests if niquests is available, and requests if niquests is not available.

You are encouraged to make an informed decision on weather you are most comfortable with the stable but stagnant requests, or the niquests fork.  I hope to settle down on some final decision when I'm starting to work on 3.0 (which will support async requests).  httpx may be an option.  **Your opinion is valuable for me**.  Feel free to comment on https://github.com/python-caldav/caldav/issues/457,  https://github.com/python-caldav/caldav/issues/530 or https://github.com/jawah/niquests/issues/267 - if you have a github account, and if not you can reach out at python-http@plann.no.

So far the most common recommendation seems to be to go for httpx.  See also https://github.com/python-caldav/caldav/pull/565

## Meta

This file should adhere to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), but it's manually maintained, and I have some extra sections in it.  Notably an executive summary at the top,  "Breaking Changes" or "Potentially Breaking Changes", list of GitHub issues/pull requests closed/merged, information on changes in the test framework, credits to people assisting, an overview of how much time I've spent on each release, and an overview of calendar servers the release has been tested towards.

Changelogs prior to v1.2 is pruned, but available in the v1.2 release

This project should adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html), though some earlier releases may be incompatible with the SemVer standard.

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

### Breaking Changes

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
  * Improved tests (but no test for inheritance yet).
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

## [1.6.0] - 2025-05-30

This will be the last minor release before 2.0.  The scheduling support has been fixed up a bit, and saving a single recurrence does what it should do, rather than messing up the whole series.

### Fixed

* Save single recurrence.  I can't find any information in the RFCs on this, but all servers I've tested does the wrong thing - when saving a single recurrence (with RECURRENCE-ID set but without RRULE), then the original event (or task) will be overwritten (and the RRULE disappear), which is most likely not what one wants.  New logic in place (with good test coverage) to ensure only the single instance is saved. Issue https://github.com/python-caldav/caldav/issues/379, pull request https://github.com/python-caldav/caldav/pull/500
* Scheduling support.  It was work in progress many years ago, but uncompleted work was eventually committed to the project.  I managed to get a DAViCal test server up and running with three test accounts, ran through the tests, found quite some breakages, but managed to fix up.  https://github.com/python-caldav/caldav/pull/497

### Added

* New option `event.save(all_recurrences=True)` to edit the whole series when saving a modified recurrence.  Part of https://github.com/python-caldav/caldav/pull/500
* New methods `Event.set_dtend` and `CalendarObjectResource.set_end`. https://github.com/python-caldav/caldav/pull/499

### Refactoring and tests

* Partially tossed out all internal usage of vobject, https://github.com/python-caldav/caldav/issues/476.  Refactoring and removing unuseful code.  Parts of this work was accidentally committed directly to master, 2f61dc7adbe044eaf43d0d2c78ba96df09201542, the rest was piggybaced in through  https://github.com/python-caldav/caldav/pull/500.
* Server-specific setup- and teardown-methods (used for spinning up test servers in the tests) is now executed through the DAVClient context manager.  This will allow doctests to run easily.
* Made exception for new `task.uncomplete`-check for GMX server - https://github.com/python-caldav/caldav/issues/525

### Time spent and roadmap

Maintainer put down ten hours of effort for the 1.6-release.  The estimate was 12 hours.

## [1.5.0] - 2025-05-24

Version 1.5 comes with support for alarms (searching for alarms if the server permits and easy interface for adding alamrs when creating events), lots of workarounds and fixes ensuring compatibility with various servers, refactored some code, and done some preparations for the upcoming server compatibility hints project.

### Deprecated

Python 3.7 is no longer tested (dependency problems) - but it should work.  Please file a bug report if it doesn't work.  (Note that the caldav library pulls in many dependencies, and not all of them supports dead snakes).

### Fixed

* Servers that return a quoted URL in their path will now be parsed correctly by @edel-macias-cubix in https://github.com/python-caldav/caldav/pull/473
* Compatibility workaround: If `event.load()` fails, it will retry the load by doing a multiget - https://github.com/python-caldav/caldav/pull/460 and  https://github.com/python-caldav/caldav/pull/475 - https://github.com/python-caldav/caldav/issues/459
* Compatibility workaround: A problem with a wiki calendar fixed by @soundstorm in https://github.com/python-caldav/caldav/pull/469
* Blank passwords should be acceptable - https://github.com/python-caldav/caldav/pull/481
* Compatibility workaround: Accept XML content from calendar server even if it's marked up with content-type text/plain by @niccokunzmann in https://github.com/python-caldav/caldav/pull/465
* Bugfix for saving component failing on multi-component recurrence objects - https://github.com/python-caldav/caldav/pull/467
* Some exotic servers may return object URLs on search, but it does not work out to fetch the calendar data.  Now it will log an error instead of raising an error in such cases.
* Some workarounds and fixes for getting tests passing on all the test servers I had at hand in https://github.com/python-caldav/caldav/pull/492
* Search for todo-items would ignore recurring tasks with COMPLETED recurrence instances, ref https://github.com/python-caldav/caldav/issues/495, fixed in https://github.com/python-caldav/caldav/pull/496

### Changed

* The `tests/compatibility_issues.py` has been moved to `caldav/compatibility_hints.py`, this to make it available for a caldav-server-tester-tool that I'm splitting off to a separate project/repository, and also to make https://github.com/python-caldav/caldav/issues/402 possible.

#### Refactoring

* Minor code cleanups by github user @ArtemIsmagilov in https://github.com/python-caldav/caldav/pull/456
* The very much overgrown `objects.py`-file has been split into three - https://github.com/python-caldav/caldav/pull/483
* Refactor compatibility issues https://github.com/python-caldav/caldav/pull/484
* Refactoring of `multiget` in https://github.com/python-caldav/caldav/pull/492

### Documentation

* Add more project links to PyPI by @niccokunzmann in https://github.com/python-caldav/caldav/pull/464
* Document how to use tox for testing by @niccokunzmann in https://github.com/python-caldav/caldav/pull/466
* Readthedocs integration has been repaired (https://github.com/python-caldav/caldav/pull/453 - but eventually the fix was introduced directly in the master branch)

#### Test framework

* Radicale tests have been broken for a while, but now it's fixed ... and github will be running those tests as well.  https://github.com/python-caldav/caldav/pull/480 plus commits directly to the main branch.
* Python 3.13 is officially supported by github user @ArtemIsmagilov in https://github.com/python-caldav/caldav/pull/454
* Functional test framework has been refactored in https://github.com/python-caldav/caldav/pull/450
  * code for setting up and rigging down xandikos/radicale servers have been moved from `tests/test_caldav.py` to `tests/conf.py`.  This allows for:
    * Adding code (including system calls or remote API calls) for Setting up and tearing down calendar servers in `conf_private.py`
    * Creating a local xandikos or radicale server in the `tests.client`-method, which is also used in the `examples`-section.
    * Allows offline testing of my upcoming `check_server_compatibility`-script
  * Also added the possibility to tag test servers with a name
* Many changes done to the compatibility flag list (due to work on the server-checker project)
* Functional tests for multiget in https://github.com/python-caldav/caldav/pull/489

### Added

* Methods for verifying and adding reverse relations - https://github.com/python-caldav/caldav/pull/336
* Easy creation of events and tasks with alarms, search for alarms - https://github.com/python-caldav/caldav/pull/221
* Work in progress: `auto_conn`, `auto_calendar` and `auto_calendars` may read caldav connection and calendar configuration from a config file, environmental variables or other sources.  Currently I've made the minimal possible work to be able to test the caldav-server-tester script.
* By now `calendar.search(..., sort_keys=("DTSTART")` will work.  Sort keys expects a list or a tuple, but it's easy to send an attribute by mistake.  https://github.com/python-caldav/caldav/issues/448 https://github.com/python-caldav/caldav/pull/449
* The `class_`-parameter now works when sending data to `save_event()` etc.
* Search method now takes parameter `journal=True`.  ref https://github.com/python-caldav/caldav/issues/237 and https://github.com/python-caldav/caldav/pull/486

### Time spent and roadmap

A roadmap was made in May 2025: https://github.com/python-caldav/caldav/issues/474 - the roadmap includes time estimates.

Since the roadmap was made, the maintainer has spent 39 hours working on the CalDAV project - this includes a bit of documentation, quite some communication, reading on the RFCs, code reviewing, but mostly just coding.  This is above estimate due to new issues coming in.


## [1.4.0] - 2024-11-05

* Lots of work lifting the project up to more modern standards and improving code, thanks to Georges Toth (github @sim0nx), Matthias Urlichs (github @smurfix) and @ArtemIsmagilov.  While this shouldn't matter for existing users, it will make the library more future-proof.
* Quite long lists of fixes, improvements and some few changes, nothing big, main focus is on ensuring compatibility with as many server implementations as possible.  See below.

### Fixed

* Partial workaround for https://github.com/python-caldav/caldav/issues/401 - some servers require comp-type in the search query
* At least one bugfix, possibly fixing #399 - the `accept_invite`-method not working - https://github.com/python-caldav/caldav/pull/403
* Fix/workaround for servers sending MAILTO in uppercase - https://github.com/python-caldav/caldav/issues/388,  https://github.com/python-caldav/caldav/issues/399 and https://github.com/python-caldav/caldav/pull/403
* `get_duration`: make sure the algorithm doesn't raise an exception comparing dates with timestamps - https://github.com/python-caldav/caldav/pull/381
* `set_due`: make sure the algorithm doesn't raise an exception comparing naive timestamps with timezone timestamps - https://github.com/python-caldav/caldav/pull/381
* Code formatting / style fixes.
* Jason Yau introduced the possibility to add arbitrary headers - but things like User-Agent would anyway always be overwritten.  Now the custom logic takes precedence.  Pull request https://github.com/python-caldav/caldav/pull/386, issue https://github.com/python-caldav/caldav/issues/385
* Search method has some logic handling non-conformant servers (loading data from the server if the search response didn't include the icalendar data, ignoring trash from the Google server when it returns data without a VTODO/VEVENT/VJOURNAL component), but it was inside an if-statement and applied only if Expanded-flag was set to True.  Moved the logic out of the if, so it always applies.
* Revisited a problem that Google sometimes delivers junk when doing searches - credits to github user @zhwei in https://github.com/python-caldav/caldav/pull/366
* There were some compatibility-logic loading objects if the server does not deliver icalendar data (as it's suppsoed to do according to the RFC), but only if passing the `expand`-flag to the `search`-method.  Fixed that it loads regardless of weather `expand` is set or not.  Also in https://github.com/python-caldav/caldav/pull/366
* Tests - lots of work getting as much test code as possible to pass on different servers, and now testing also for Python 3.12 - ref https://github.com/python-caldav/caldav/pull/368 https://github.com/python-caldav/caldav/issues/360 https://github.com/python-caldav/caldav/pull/447 https://github.com/python-caldav/caldav/pull/369 https://github.com/python-caldav/caldav/pull/370  https://github.com/python-caldav/caldav/pull/441 https://github.com/python-caldav/caldav/pull/443a
* The vcal fixup method was converting implicit dates into timestamps in the COMPLETED property, as it should be a timestamp according to the RFC - however, the regexp failed on explicit dates.  Now it will take explicit dates too.  https://github.com/python-caldav/caldav/pull/387
* Code cleanups and modernizing the code - https://github.com/python-caldav/caldav/pull/404 https://github.com/python-caldav/caldav/pull/405 https://github.com/python-caldav/caldav/pull/406 https://github.com/python-caldav/caldav/pull/407 https://github.com/python-caldav/caldav/pull/408 https://github.com/python-caldav/caldav/pull/409 https://github.com/python-caldav/caldav/pull/412 https://github.com/python-caldav/caldav/pull/414 https://github.com/python-caldav/caldav/pull/415 https://github.com/python-caldav/caldav/pull/418 https://github.com/python-caldav/caldav/pull/419 https://github.com/python-caldav/caldav/pull/417 https://github.com/python-caldav/caldav/pull/421 https://github.com/python-caldav/caldav/pull/423 https://github.com/python-caldav/caldav/pull/430 https://github.com/python-caldav/caldav/pull/431 https://github.com/python-caldav/caldav/pull/440 https://github.com/python-caldav/caldav/pull/365
* Doc - improved examples, https://github.com/python-caldav/caldav/pull/427
* Purelymail sends absolute URLs, which is allowed by the RFC but was not supported by the library.  Fixed in https://github.com/python-caldav/caldav/pull/442

### Changed

* In https://github.com/python-caldav/caldav/pull/366, I optimized the logic in `search` a bit, now all data from the server not containing a VEVENT, VTODO or VJOURNAL will be thrown away.  I believe this won't cause any problems for anyone, as the server should only deliver such components, but I may be wrong.
* Default User-Agent changed from `Mozilla/5` to `python-caldav/{__version__}` - https://github.com/python-caldav/caldav/pull/392
* Change fixup log lvl to warning and merge diff log messages into related parent log by @MrEbbinghaus in https://github.com/python-caldav/caldav/pull/438
* Mandatory fields are now added if trying to save incomplete icalendar data, https://github.com/python-caldav/caldav/pull/447

### Added

* Allow to reverse the sorting order on search function  by @twissell- in https://github.com/python-caldav/caldav/pull/433
* Work on integrating typing information. Details in https://github.com/python-caldav/caldav/pull/358
* Remove dependency on pytz. Details in https://github.com/python-caldav/caldav/issues/231 and https://github.com/python-caldav/caldav/pull/363
* Use setuptools-scm / pyproject.toml (modern packaging). Details in https://github.com/python-caldav/caldav/pull/364 and https://github.com/python-caldav/caldav/pull/367
* Debugging tool - an environment variable can be set, causing the library to spew out server communications into files under /tmp.  Details in https://github.com/python-caldav/caldav/pull/249 and https://github.com/python-caldav/caldav/issues/248
* Comaptibility matrix for posteo.de servers in `tests/compatibility_issues.py`
* Added sort_reverse option to the search function to reverse the sorting order of the found objects.
* It's now possible to specify if `expand` should be done on the server side or client side.  Default is as before, expanding on server side, then on the client side if unexpanded data is returned.  It was found that some servers does expanding, but does not add `RECURRENCE-ID`.  https://github.com/python-caldav/caldav/pull/447

### Security

The debug information gathering hook has been in the limbo for a long time, due to security concerns:

* An attacker that has access to alter the environment the application is running under may cause a DoS-attack, filling up available disk space with debug logging.
* An attacker that has access to alter the environment the application is running under, and access to read files under /tmp (files being 0600 and owned by the uid the application is running under), will be able to read the communication between the server and the client, communication that may be private and confidential.

Thinking it through three times, I'm not too concerned - if someone has access to alter the environment the process is running under and access to read files run by the uid of the application, then this someone should already be trusted and will probably have the possibility to DoS the system or gather this communication through other means.

### Credits

Georges Tooth, Крылов Александр, zhwei, Stefan Ollinger, Matthias Urlichs, ArtemIsmagilov, Tobias Brox has contributed directly with commits and pull requests included in this release.  Many more has contributed through reporting issues and code snippets.

### Test runs

Prior to release (commit 92de2e29276d3da2dcc721cbaef8da5eb344bd11), tests have been run successfully towards:

* radicale (internal tests)
* xandikos (internal tests)
* ecloud.global (NextCloud) - with flags `compatibility_issues.nextcloud + ['no_delete_calendar', 'unique_calendar_ids', 'rate_limited', 'broken_expand']` and with frequent manual "empty thrashcan"-operations in webui.
* Zimbra
* DAViCal
* Posteo
* Purelymail

## [1.3.9] - 2023-12-12

Some bugfixes.

### Fixed

* Some parts of the library would throw OverflowError on very weird dates/timestamps.  Now those are converted to the minimum or maximum accepted date/timestamp.  Credits to github user @tamarinvs19 in https://github.com/python-caldav/caldav/pull/327
* `DAVResponse.davclient` was always set to None, now it may be set to the `DAVClient` instance.  Credits to github user @sobolevn in https://github.com/python-caldav/caldav/pull/323
* `DAVResponse.davclient` was always set to None, now it may be set to the `DAVClient` instance.  Credits to github user @sobolevn in https://github.com/python-caldav/caldav/pull/323
* `examples/sync_examples.py`, the sync token needs to be saved to the database (credits to Savvas Giannoukas)
* Bugfixes in `set_relations`, credits to github user @Zocker1999NET in https://github.com/python-caldav/caldav/pull/335 and https://github.com/python-caldav/caldav/pull/333
* Dates that are off the scale are converted to `min_date` and `max_date` (and logging en error) rather than throwing OverflowError, credits to github user @tamarinvs19 in https://github.com/python-caldav/caldav/pull/327
* Completing a recurring task with a naïve or floating `DTSTART` would cause a runtime error
* Tests stopped working on python 3.7 and python 3.8 for a while.  This was only an issue with libraries used for the testing, and has been mended.
* Bugfix that a 500 internal server error could cause an recursion loop, credits to github user @bchardin in https://github.com/python-caldav/caldav/pull/344
* Compatibility-fix for Google calendar, credits to github user @e-katov in https://github.com/python-caldav/caldav/pull/344
* Spelling, grammar and removing a useless regexp, credits to github user @scop in https://github.com/python-caldav/caldav/pull/337
* Faulty icalendar code caused the code for fixing faulty icalendar code to break, credits to github user @yuwash in https://github.com/python-caldav/caldav/pull/347 and https://github.com/python-caldav/caldav/pull/350
* Sorting on uppercase attributes didn't work, ref issue https://github.com/python-caldav/caldav/issues/352 - credits to github user @ArtemIsmagilov.
* The sorting algorithm was dependent on vobject library - refactored to use icalendar library instead
* Lots more test code on the sorting, and fixed some corner cases
* Creating a task with a status didn't work

## [1.3.8] - 2023-12-10 [YANKED]

Why do I never manage to do releases right ..

## [1.3.7] - 2023-12-10 [YANKED]

I managed to tag the wrong commit

## [1.3.6] - 2023-07-20

Very minor test fix

### Fixed

One of the tests has been partially disabled, ref https://github.com/python-caldav/caldav/issues/300 , https://github.com/python-caldav/caldav/issues/320 and  https://github.com/python-caldav/caldav/pull/321

## [1.3.5] - 2023-07-19 [YANKED]

Seems like I've been using the wrong procedure all the time for doing pypi-releases

## [1.3.4] - 2023-07-19 [YANKED]

... GitHub has some features that it will merge pull requests only when all tests passes ... but somehow I can't get it to work, so 1.3.4 broke the style test again ...

## [1.3.3] - 2023-07-19

Summary: Some few workarounds to support yet more different calendar servers and cloud providers, some few minor enhancements needed by various contributors, and some minor bugfixes.

### Added
* Support for very big events, credits to github user @aaujon in https://github.com/python-caldav/caldav/pull/301
* Custom HTTP headers was added in v1.2, but documentation and unit test is added in v1.3, credits to github user @JasonSanDiego in https://github.com/python-caldav/caldav/pull/306
* More test code in https://github.com/python-caldav/caldav/pull/308
* Add props parameter to search function, credits to github user @ge-lem in https://github.com/python-caldav/caldav/pull/315
* Set an id field in calendar objects when populated through `CalendarSet.calendars()`, credits to github user @shikasta-net in https://github.com/python-caldav/caldav/pull/314
* `get_relatives`-method, https://github.com/python-caldav/caldav/pull/294
* `get_dtend`-method

### Fixed
* Bugfix in error handling, credits to github user @aaujon in https://github.com/python-caldav/caldav/pull/299
* Various minor bugfixes in https://github.com/python-caldav/caldav/pull/307
* Compatibility workaround for unknown caldav server in https://github.com/python-caldav/caldav/pull/303
* Google compatibility workaround, credits to github user @flozz in https://github.com/python-caldav/caldav/pull/312
* Documentation typos, credits to github user @FluxxCode in https://github.com/python-caldav/caldav/pull/317
* Improved support for cloud provider gmx.de in https://github.com/python-caldav/caldav/pull/318
* Don't yield errors on (potentially invalid) XML-parameters that are included in the RFC examples - https://github.com/python-caldav/caldav/issues/209 - https://github.com/python-caldav/caldav/pull/508

### Changed

* Refactored relation handling in `set_due`

## [1.3.2] - 2023-07-19 [YANKED]

One extra line in CHANGELOG.md caused style tests to break.  Can't have a release with broken tests.  Why is it so hard for me to do releases correctly?

## [1.3.1] - 2023-07-19 [YANKED]

I forgot bumping the version number from 1.3.0 to 1.3.1 prior to tagging

## [1.3.0] - 2023-07-19 [YANKED]

I accidentally tagged the wrong stuff in the git repo
