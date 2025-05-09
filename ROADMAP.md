# Python CalDAV Client Library - Roadmap

Hopefully I will have some time to work on the Python CalDAV library in the upcoming months.  I'm now trying to make this "super issue" to prioritize the outstanding work, throw some estimates on the work tasks and break down the projects.

## Summary first

Estimated outstanding work:

* Close outstanding pull requests - 12h
* Outstanding issues slated for v1.5 - 22h
* Documentation work - 18h
* Server checker and server compatibility hints project - 28h
* Outstanding issues slated for v2.0 - 23h
* New interface + asyncio projects - 50h
* Outstanding issues slated for v3.0 - 12h
* Maintain and expand the test server list - 8h
* JMAP project - 40h

I do believe I can manage to contribute somewhere between 5 and 30 hours per month to the caldav project over the upcoming year.  That's between 60 and 360 hours.  In the very best scenario it will be possible to get everything above done.  Most likely something has to go out, most likely many outstanding issues slated for v1.5 will be procrastinated, same with the JMAP project and quite some of the v2.0-issues.

This being open source, I'm not doing everything alone, there is a steady stream of contributions from other contributors ticking in - but most of those contributions are related to new issues - unknown bugs and features I haven't think about.  Generally community contributions improve the overall quality of the project, but contributes negatively to the roadmap progress.  Most reported issues comes iwthout pull-requests, even when there are pull-requests it takes some time to do QA on the contributions, add missing test code, documentation and changelog entries.

## The higher goals

For all work that is done, it's important to consider if it's bringing the project in the right direction or not, defined as such:

* The library should offer high-level easy-to-use methods for doing interaction with CalDAV servers (but it should also offer lower-level methods).
* The library should just work - with a bare minimum of configuration (but it should also be possible to do advanced configuration).
* The high-level methods should be accessible for people who know nothing about the CalDAV standard nor the iCalendar standard (while the low-level methods should give power-users unlimited possibilities).
* The CalDAV standard is currently the only widely adopted standard for calendar access, though it's not a very good standard - when newer standards are evolving, the scope for the library may change.
* The library should work consistently towards different server implementations

## Outstanding pull requests

It's important to get done with some pull requests - many of them is work that I've started on and got partly or mostly done, but I never had time to complete it.  Some of it may be considered "low hanging fruit" as most or parts of the work is already done.

* [Support for alarms](https://github.com/python-caldav/caldav/issues/132) - several users have requested better support for alarms.  Work has been done to make high-level interface for creating events with alarms and searching for events based on alarms, but the functional tests were procrastinated as the test servers didn't support alarms.  Functionality for "find the next upcoming alarms" is also missing.  Estimate: 4h
* [Relationship validation](https://github.com/python-caldav/caldav/pull/336) - While the RFCs says nothing about it, I believe it's good practice to have a two-way linking in the `RELATED-TO`-property (if a "child" is pointing to a "parent", the "parent" should point back to the child).  The pull request should allow going through all events in the calendar and verify that no such links are missing, as well as fix missing links.  Estimate: 3h
* [Repairing the Readthedocs sync](https://github.com/python-caldav/caldav/pull/453) - https://caldav.readthedocs.io/en/latest/ is stuck on 1.3.6, while the latest release is 1.4, I need to figure out what's the problem here, fix it and verify that things are working.  Estimate: 2h.
* [Compatibility workaround: Accept XML content from calendar server even if it's marked up with content-type text/plain](https://github.com/python-caldav/caldav/pull/465).  Estimate: 1h
* [Server checker](https://github.com/python-caldav/caldav/pull/451) - this is part of the "server compatibility hints"-project, more information below.
* [Code cleanup](https://github.com/python-caldav/caldav/pull/437) - Estimate: 2h

## Documentation work

The documentation is not much good nor intuitive for new users.  People are encuraged to check some example code inside the repository, but this example code is not tested regularly.  The code should be embedded in the documentation and executed by the test suite.

* Make a way to embed code in the documentation and have it executed by functional tests.  Estimate: 2h
* Move the existing example code into documentation and improve it.  Estimate: 3h
* Look through the documentation, reorganize it, write more and better doc.  Estimate: 6h
* Loko through all the outstanding documentation issues.  Estimate: 3h
* Update the documentation again, after fixing all other issues mentioned here.  Estimate: 4h

### Related issues and pull requests

* https://github.com/python-caldav/caldav/issues/100
* https://github.com/python-caldav/caldav/issues/119
* https://github.com/python-caldav/caldav/issues/120
* https://github.com/python-caldav/caldav/issues/239
* https://github.com/python-caldav/caldav/issues/253
* https://github.com/python-caldav/caldav/issues/256
* https://github.com/python-caldav/caldav/issues/269
* https://github.com/python-caldav/caldav/issues/311

## Project: Server compatibility hints

There is a jungle of calendar servers out there, the RFCs are sometimes ambiguous, and quite a lot in the RFCs is optional to implement.  Ideally, a python program using the caldav library should behave the same even if the calendar servers behaves differently - for instance, if the calendar server does not support search, the search operation may work by downloading the whole calendar and do a client-side search.  A side-project (and requisite) here is a server-checker script that may run various tests towards a calendar server to check for compatibility issues.  The server checker script is partially done, but got derailed due to lack of time.

### Subtasks

* The current "quick list" is a mess and needs to be cleanded up and reorganized.  After doing that, the functional tests and the server checker script must be rewritten to comply with the new list.  Estimate: 5h
* The server checker script needs to be refactored - currently it's only possible to run all checks or nothing, it should be possible to check one quirk without running the full test suite.  This is slightly non-trivial as the current script sometimes needs data from one quirk test run before it can run another quirk test.  Estimate: 6h
* The server configuration for caldav should be improved
  * In "auto-mode" (default) the client should do a quick effort on figuring out compatibility quirks, guessing the correct URL, etc.  Estimate: 2h
  * In "probe-mode", the client should do extensive probing to figure out of things.  Estimate: 2h
  * In "manual" mode, the client should assume the configuration it gets is correct.
  * It should accept a parameter telling it what kind of server is in use ... i.e. `server_impementation=nextcloud` and it would know that all nextcloud-quirks should be applied.  It's complicated as version numbers also has to be taken into consideration.  Alternatively, it should be possible to pass a complete quirk-list.  Estimate: 3h
  * It should be possible to configure some few other things.  Estimate: 1h
    * Is it allowed to download the full calendar i.e. to do a client text search?
    * If an operation is known to fail due to the quirk-list, should the server raise an error, or should it try anyway?
    * Should we do work-arounds to ensure consistency across different calendar servers?  (this may break consistency towards elder versions of the library)
    * ... probably more options as well ..
  * Now that we have a quirk-list, it should be utilized:
    * Try to identify all the points in the code where we should do differently dependent on the quirk list and configuration.  Estimate: 3h
    * Try to mitigate as many of the quirks as possible, and raise errors when the server does not support the operation.  Estimate: 6h

### Related issues and pull requests

* https://github.com/python-caldav/caldav/pull/451
* https://github.com/python-caldav/caldav/issues/463
* https://github.com/python-caldav/caldav/issues/402
* https://github.com/python-caldav/caldav/issues/102
* https://github.com/python-caldav/caldav/issues/183
* https://github.com/python-caldav/caldav/issues/203
* https://github.com/python-caldav/caldav/issues/351
* https://github.com/python-caldav/caldav/issues/401

## Project: New interface

The current interface has grown organically and without much thought.  Method names are inconsistent, the workflow is inconsistent, in some places a property is in use while other places a method is in use.  The library was also made back when "Python 3k" was a long-in-the-future project, and while async operation meant one would have to understand the twisted "Twisted" framework.  I think it may be useful to think through things and make a new application interface from scratch.  I deem backward compatibility high, so the new and old application interface will live side by side (but eventually with deprecation warnings) for a while.  This involves quite a lot of thinking and documentation, some refactoring of current code, but should not involve duplicating code nor "writing things from scratch".

This should be done a bit in lockstep with the asyncio project.  One idea may be to create the new interface for async usage and leave the old interface for sync usage.  The estimate is set low because much of the actual work is done in the asyncio project.

Estimate: 10h

### Related issues and pull requests

* https://github.com/python-caldav/caldav/issues/92
* https://github.com/python-caldav/caldav/issues/128
* https://github.com/python-caldav/caldav/issues/180
* https://github.com/python-caldav/caldav/issues/232
* https://github.com/python-caldav/caldav/issues/240

## Project: asyncio

Modern Python applications should work asynchronously.

I haven't thought much about how to achieve this - but I give a very rough estimate that it will take me one working week to figure it out and implement it.

Estimate: 40h

### Related issues and pull requests

* https://github.com/python-caldav/caldav/issues/342
* https://github.com/python-caldav/caldav/pull/455
* https://github.com/python-caldav/caldav/issues/457

## Project: JMAP

JMAP is a new email protocol intended to replace IMAP - at FOSSDEM 2025 it appeared that both server developers and client developers found it superior compared to IMAP.  The JMAP protocol also supports the exchange of calendaring data.

I think it would be nice with a library where the high-level methods would work seamlessly for the end user no matter if the CalDAV protocol or the JMAP protocol is used.  The first step of this project would be to investigate if this is at all possible - if not, we may need to make changes to the high-level API.

Supporting JMAP may not be intuitive considering the naming of the library, but it may be important for future-proofing the library.

It's prerequisite to find calendar servers supporting JMAP for testing.

### Related issues and pull requests

* https://github.com/python-caldav/caldav/issues/424

Estimate: 40h

## Increase the list of test servers

This involves signing up at different cloud providers, begging for test accounts from people who are running calendar servers, setting up my own self-hosted servers, etc.  Trying to keep an overview at https://github.com/python-caldav/caldav/issues/45 and in my own private config file.

Estimate: 8h

## Other outstanding issues

I try to prioritize the issues in the github tracker by using the "milestone" concept.  The milestones correspond to some future release.  It's a very optimistic estimate on what release the issue will be fixed in, so in the end I freqeuently push the milestone target.

### 1.x milestone


* https://github.com/python-caldav/caldav/issues/458 - case sensitivity in http headers - Estimate: 1h
* https://github.com/python-caldav/caldav/issues/262 - look once more into setup.py vs pyproject.toml etc - Estimate: 2h
* https://github.com/python-caldav/caldav/issues/237 - search for journals - Estimate: 1h
* https://github.com/python-caldav/caldav/issues/115 - multiget - Estimate: 1h
* https://github.com/python-caldav/caldav/issues/120 - RFC6638 support - Estimate: 4h
https://github.com/python-caldav/caldav/issues/163 - Exception thrown in tentatively_accept_invite - Estimate: 2h
* https://github.com/python-caldav/caldav/issues/151 - Some Apple problems - Estimate: 1h
* https://github.com/python-caldav/caldav/issues/206 - trouble with .netrc - Estimate: 1h
* https://github.com/python-caldav/caldav/issues/309 - trouble with GMX - Estimate: 2h
* https://github.com/python-caldav/caldav/issues/330 - another path handling problem - Estimate: 1h
* https://github.com/python-caldav/caldav/issues/356 - a missing method - Estimate: 2h
* https://github.com/python-caldav/caldav/issues/379 - Edit a single occurence of a recurrent event - Estimate: 2h
* https://github.com/python-caldav/caldav/issues/476 - Verify that there are no internal dependencies on vobject - Estimate: 1h
* https://github.com/python-caldav/caldav/issues/478 - problem with Fastmail - Estimate: 1h

### 2.0 milestone

* https://github.com/python-caldav/caldav/issues/462 - better support for proxying, better tests, better doc - Estimate: 3h
* https://github.com/python-caldav/caldav/issues/93 - increase test coverage, again - Estimate: 4h
* https://github.com/python-caldav/caldav/issues/99 - documentation and refactoring of test runs - Estimate: 1h
* https://github.com/python-caldav/caldav/issues/96 - refactoring - Estimate: 2h
* https://github.com/python-caldav/caldav/issues/131 - cross-principal calendar search - Estimate: 4h
* https://github.com/python-caldav/caldav/issues/334 - some missing test code - Estimate: 1h
* https://github.com/python-caldav/caldav/issues/340 - google compatibility - Estimate: 2h
* https://github.com/python-caldav/caldav/issues/380 - intermedient test problem - Estimate: 1h
* https://github.com/python-caldav/caldav/issues/397 - Recurrence instances gets stripped when doing cal.object_by_uid(uid,comp_class=caldav.Event) - Estimate: 2h
* https://github.com/python-caldav/caldav/issues/439 - Test fails against radicale - Estimate: 2h
* https://github.com/python-caldav/caldav/issues/477 - Deprecation warnings on vobject - Estimate: 1h

### 3.0 milestone

* https://github.com/python-caldav/caldav/issues/372 - timezones problem - Estimate: 5h
* https://github.com/python-caldav/caldav/issues/398 - look more into recurrences - Estimate: 5h
* https://github.com/python-caldav/caldav/issues/399 - problems with accept_invite at some servers - Estimate: 2h

### Later

* https://github.com/python-caldav/caldav/issues/35
* https://github.com/python-caldav/caldav/issues/152
* https://github.com/python-caldav/caldav/issues/425
* https://github.com/python-caldav/caldav/issues/420
