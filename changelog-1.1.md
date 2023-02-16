## What's Changed from 1.0 to 1.1

### Potential breaking change

I consider this to be a very minor breakage of my promise not to do changes to the API in 1.x - the behaviour of  `str(calendar_obj)` and `repr(calendar_obj)` has changed slightly.

* `str(cal)` was non-deterministic, would sometimes return an URL and sometimes the calendar name, but would never initiate server traffic.  Now it's deterministic, always returning the calendar name (if the server supports it).
* `repr(cal)` was also deterministic, and based on `str(cal)`.  A repr should ideally give all the data needed to rebuild the object, hence the URL is important, while the name is not.

### Bugfixes, workarounds and annoyances
* Potential fix for error "dictionary changed size during iteration", ref https://github.com/python-caldav/caldav/issue/267 by @tobixen in https://github.com/python-caldav/caldav/pull/268
* misc bugfixes by @tobixen in https://github.com/python-caldav/caldav/pull/265
* rate-limiting of error messages when encountering broken ical by @tobixen in https://github.com/python-caldav/caldav/pull/272
* DAViCal workaround - set STATUS=NEEDS-ACTION by default by @tobixen in https://github.com/python-caldav/caldav/pull/263
* Remove annoying assert from icalendar_component by @tobixen in https://github.com/python-caldav/caldav/pull/274
* cal_obj.__str__ and cal_obj.__repr__ should be deterministic by @tobixen in https://github.com/python-caldav/caldav/pull/278
* keep canonical URLs in synchronization objects by @tobixen in https://github.com/python-caldav/caldav/pull/279
* compatibility fix: objects returned by search should always be loaded by @tobixen in https://github.com/python-caldav/caldav/pull/280

### Documentation
* Tweaking the examples by @tobixen in https://github.com/python-caldav/caldav/pull/271

### New features
* Allow principle.calendar(calendar_url=...) by @tobixen in https://github.com/python-caldav/caldav/pull/273
* Allow checking DUE on dependent before moving DUE by @tobixen in https://github.com/python-caldav/caldav/pull/275
* allow conditional load by @tobixen in https://github.com/python-caldav/caldav/pull/276

### Other
Lots of work on the test suite, by @tobixen in https://github.com/python-caldav/caldav/pull/264 and https://github.com/python-caldav/caldav/pull/281

**Full Changelog**: https://github.com/python-caldav/caldav/compare/v1.0.1...v1.1.0
