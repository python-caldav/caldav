## Version 1.0 at a glance

Version 1.0 is no big gamechanger compared to version 0.x.  The biggest change is the commitment that there shouldn't be any breaking changes in any subsequent 1.x-releases.

I had some thoughts in https://github.com/python-caldav/caldav/issues/92 to introduce new API in version 1.0, but have reconsidered.  For one thing SEMVER states:

* If your software is being used in production, it should probably already be 1.0.0.
* If you have a stable API on which users have come to depend, you should be 1.0.0.
* If you’re worrying a lot about backwards compatibility, you should probably already be 1.0.0.

All three points apply and they have done that for a long time, hence a 1.0-release is way overdue, and any API changes will have to wait for 2.0.  I'm also intending that the only major breaking changes in 2.0 will be the removal of things that already is marked as deprecated in 1.0.  If your library depends on caldav, put "caldav<3.0" in the requirements.

### Breaking changes in v1.0

#### Python2 support is going away

Python2.x is now officially not supported - I've thrown in an assert that we're using python3.  In version 1.1, some code for supporting python2 will be cleaned away ... unless, if anyone screams out that they would like to run the newest caldav library version on an old python version, I may reconsider.

#### "Floating time" breakage

Timezones are difficult!  When an event is created through the "new" interface, and a datetime object without time zone is passed, version 0.x would send it over to the calendar servr without time zone information as a "floating time" - now it will be converted to UTC-time and sent to the server as such.

"Floating time" is defined at https://www.rfc-editor.org/rfc/rfc5545#section-3.3.5 and may be useful in some circumstances (like, from time to time, I'm trying to maintain a ritual "raise the flag on the boat at 08:00 local time every morning").  However, I believe that in a majority of cases the lack of time zone is unintentional and meant to be local time.  In recent versions of python, `dt.astimezone(utc)` will assume dt is in local time and convert it to UTC, which in most cases probably is the correct thing to do.

If one intentionally wants to create events or tasks with "floating time", then one may use the ical_fragment parameter.

This may have the unfortunate side effect that some clients that aren't aware of their time zone (possibly including my calendar-cli - I will have to look into that) will show events in UTC-time rather than local time.  I think the proper thing would be to either fix those clients to be timezone-aware, or even better, to always be explicit and always put the local time zone into the datetimes passed to `calendar.save_event()`.

### Major features

* Support for bearer token

### Some bugfixes and workarounds

* new parent/child-code had some issues
* creating an event by sending an ical fragment had some issues
* expansion of recurring todos broke when the recurring_ical_event was upgraded from 1.x to 2.x
* `len(calendar.objects())` did not work
* Some hacks that hopefully will allow to fetch information from DOCUframe
* We should 

### Documentation

Documentation now has sections on backward compatibility and "Schrodingers support" for old python versions.

The basic_usage_examples.py has been rewritten from scratch.

## Test code and housekeeping

As always, the test suite is an evergrowing everchanging beast.

## Pull requests

Almost all the work has been done through github pull requests this time - making it a lot easier to maintain the changelog.  Those pull requests have gone into 1.0:

* changing date_search to search in documentation and examples by @yeshwantthota in https://github.com/python-caldav/caldav/pull/236
* Python 3.11 should be tested for by @azmeuk in https://github.com/python-caldav/caldav/pull/242
* recurring_ical_event 2.0 does not expand tasks by default by @tobixen in https://github.com/python-caldav/caldav/pull/243
* New features needed for calendar_cli aka plann by @tobixen in https://github.com/python-caldav/caldav/pull/244
* Bugfixes, documentation and misc by @tobixen in https://github.com/python-caldav/caldav/pull/246 https://github.com/python-caldav/caldav/pull/254 https://github.com/python-caldav/caldav/pull/255 https://github.com/python-caldav/caldav/pull/247
* When events/tasks/journals are created, "naive" datetime objects will be converted to UTC - https://github.com/python-caldav/caldav/pull/258
* More test code by @tobixen in https://github.com/python-caldav/caldav/pull/245 and https://github.com/python-caldav/caldav/pull/259
* Bearer authentication support by @azmeuk in https://github.com/python-caldav/caldav/pull/260

Some few fixups were done to some of the pull requests after the pull request was added to the master branch - in those cases I've just pushed it directly to the master branch.

## Github issues and credits

I used to have a list of github issues that were touched by a release, and I also used to give credits to people that have contributed simply by raising issues.  It's a lot of work going through all the issues, so I will skip it this time.

## New Contributors

* @yeshwantthota made their first contribution in https://github.com/python-caldav/caldav/pull/236

**Full Changelog**: https://github.com/python-caldav/caldav/compare/v0.11.0...v1.0.0
