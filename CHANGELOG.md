# Changelog

All notable changes to this project starting from v1.2 will be documented in this file.

Changelogs prior to v1.2 has been removed, but are available in the
v1.2-release.  (The project started with a GNU ChangeLog, but it was
useless and horrible to maintain.  Then an improvised changelog format
was used, until the maintainer was pointed towards https://keepachangelog.com.
The format of this file should adhere to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This project should more or less adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2024-11-05

* Georges Toth (github @sim0nx) did a lot of efforts lifting up the project to more modern standards, @smurfix and ArtemIsmagilov has also done quite some efforts cleaning up old code
* A hook for collecting debug information has been in the pull request queue for ages.  I've decided to include it in 1.4.0.
* Many other fixes, improvements and some few changes, see below.

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
* Code cleanups and modernizing the code - https://github.com/python-caldav/caldav/pull/404 https://github.com/python-caldav/caldav/pull/405 https://github.com/python-caldav/caldav/pull/406 https://github.com/python-caldav/caldav/pull/407 https://github.com/python-caldav/caldav/pull/408 https://github.com/python-caldav/caldav/pull/409 https://github.com/python-caldav/caldav/pull/412 https://github.com/python-caldav/caldav/pull/414 https://github.com/python-caldav/caldav/pull/415 https://github.com/python-caldav/caldav/pull/418 https://github.com/python-caldav/caldav/pull/419 https://github.com/python-caldav/caldav/pull/417 https://github.com/python-caldav/caldav/pull/421 https://github.com/python-caldav/caldav/pull/423 https://github.com/python-caldav/caldav/pull/430 https://github.com/python-caldav/caldav/pull/431 https://github.com/python-caldav/caldav/pull/440
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
