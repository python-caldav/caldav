# Changelog

All notable changes to this project starting from v1.2 will be documented in this file.

Changelogs prior to v1.2 has been removed, but are available in the
v1.2-release.  The project started with a GNU ChangeLog, but it was
useless and horrible to maintain.  Then I made up my own kind of
changelogs for a while, until someone pointed me towards
https://keepachangelog.com.  The format of this file is more or less
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This project should more or less adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [x.x.x] - unreleased

* Initial work at integrating typing information. Details in https://github.com/python-caldav/caldav/pull/358
* Remove dependency on pytz. Details in https://github.com/python-caldav/caldav/issues/231
* Use setuptools-scm / pyproject.toml (modern packaging). Details in https://github.com/python-caldav/caldav/pull/364

## [1.3.9] - 2023-12-12

Some bugfixes.

### Fixes

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
