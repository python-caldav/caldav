# Changelog

The format of this file should adhere to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Changelogs prior to v1.2 follows other formats and are available in the v1.2-release.

This project should adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html), though some earlier releases may be incompatible with the SemVer standard.

## [2.0.0] - [Unreleased]

In version 2.0, the requests library will be replaced with niquests or httpx.  See https://github.com/python-caldav/caldav/issues/457.  Master branch is currently running niquests.  Work by @ArtemIsmagilov, https://github.com/python-caldav/caldav/pull/455

In version 2.0, support for python 3.7 and python 3.8 will be officially dropped.  Master branch *should* support both as for now, but Python 3.7 is no longer tested.

## [1.6.0] - 2025-05-30

This will be the last minor release before 2.0.  The scheduling support has been fixed up a bit, and saving a single recurrence does what it should do, rather than messing up the whole series.

### Fixed

* Save single recurrence.  I can't find any information in the RFCs on this, but all servers I've tested does the wrong thing - when saving a single recurrence (with RECURRENCE-ID set but without RRULE), then the original event (or task) will be overwritten (and the RRULE disappear), which is most likely not what one wants.  New logic in place (with good test coverage) to ensure only the single instance is saved. Issue https://github.com/python-caldav/caldav/issues/379, pull request https://github.com/python-caldav/caldav/pull/500
* Scheduling support.  It was work in progress many years ago, but uncompleted work was eventually committed to the project.  I managed to get a DAViCal test server up and running with three test accounts, ran through the tests, found quite some breakages, but managed to fix up.  https://github.com/python-caldav/caldav/pull/497

### Added

* New option `event.save(all_recurrences=True)` to edit the whole series when saving a modified recurrence.  Part of https://github.com/python-caldav/caldav/pull/500
* New methods `Event.set_dtend` and `CalendarObjectResource.set_end`. by @tobixen in https://github.com/python-caldav/caldav/pull/499

### Refactoring

* Partially tossed out all internal usage of vobject, https://github.com/python-caldav/caldav/issues/476.  Refactoring and removing unuseful code.  Parts of this work was accidentally committed directly to master, 2f61dc7adbe044eaf43d0d2c78ba96df09201542, the rest was piggybaced in through  https://github.com/python-caldav/caldav/pull/500.

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
* Refactor compatibility issues by @tobixen in https://github.com/python-caldav/caldav/pull/484
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

* Partial workaround for https://github.com/python-caldav/caldav/issues/401 - some servers require comptype in the search query -
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

... Github has some features that it will merge pull requests only when all tests passes ... but somehow I can't get it to work, so 1.3.4 broke the style test again ...

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

### Changes
* Refactored relation handling in `set_due`

## [1.3.2] - 2023-07-19 [YANKED]

One extra line in CHANGELOG.md caused style tests to break.  Can't have a release with broken tests.  Why is it so hard for me to do releases correctly?

## [1.3.1] - 2023-07-19 [YANKED]

I forgot bumping the version number from 1.3.0 to 1.3.1 prior to tagging

## [1.3.0] - 2023-07-19 [YANKED]

I accidentally tagged the wrong stuff in the git repo
