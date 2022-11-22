# Changelog v0.10 -> v0.11

## Warning

v0.10 and v0.11 does introduce some "bugfixes" and refactorings which are supposed to be harmless and which haven't caused any breakages in tests - but I cannot vouch for that it will not have unintended side effects in your environment.  If you're using the caldav library for production-critical tasks, you may want to hang on for a while before upgrading, or wait for v0.11.1.

## Summary

* Daniele Ricci has made support for client-side expanding.  Some calendar servers support recurrences and searching for recurrences, but does not support server-side expanding, the fix is mostly intended for those cases.
* When doing date searches with expand, rather than delivering a list of `caldav.Event` objects, the library would yield one `caldav.Event` with "subcomponents" in the icalendar data.  This may be a bit confusing and causing extra work when using the library.  A new method has been added for splitting one Event with subcomponents into several Events.
* The `search`-method will now by default use the method above and split an expanded event with subcomponents into multiple Event objects.  **This is slightly backward incompatible with v0.10**.  (According to the SemVer specification backward incompatible changes are allowed when doing 0.x-releases.  Anyway, according to my knowledge this is the first time a release contained things breaking backward-compatibility.  The rationale is that v0.10 hasn't been out for long, hence most likely most users will be using `calendar.date_search()` rather than `calendar.search()` for doing timerange searches.)
* **Another possibly breaking change**: Now `obj.data` will always return an ordinary string with ordinary line breaks, while `obj.wire_data` will always return a byte string with CRLN line endings.  While the return type of `obj.data` has been slightly unpredictable, it may still have been deterministic dependent on usage pattern - so the caller may have gotten some expectations which may now be broken.
* Bugfixes, some of the new code in v0.10 didn't handle icalendar data containing a timezone.  Some other minor bugfixes.

## Client-side expanding, and splitting of recurrence sets

I will use the word "event" below.  All code also works for todos and journals, but it's mainly events that are relevant to expand.

* The CalendarObjectResource class now has a method expand_rrule which will convert it from a recurring event to a recurrence set.
* There is also a new split_expanded method.  For a recurrence set, it will return a list of Event objects.  For an ordinary event, it will return a list object containing self (and only self).
* There was already some code in place in date_search raising errors or logging errors when the server didn't expand things as expected.  This is now replaced with the new expand-logic (and consolidated into the new search method).
* For the new search method, the default behaviour is to split an expanded recurrence set into separate objects.  For instance, if there is two objects in the calendar, one recurring daily task and a one-off event that will happen on Wednesday, then calendar.date_search(start=Monday, end=Sunday) will return two Event objects, with one of them having len(self.icalendar_instance.subcomponents)==5.  The calendar.search(start=Monday, end=Sunday, event=True) will return six Event objects, each with one subcomponent (which may be accessed through event.icalendar_object() - or event.icalendar_component in a future release, ref https://github.com/python-caldav/caldav/issues/232)
* The new search method can also deliver the recurrence set as one object, by passing the "split_expanded" attribute.

## Other

self._calendar_object() has been made into a public method self.calendar_object() - but it may be deprecated again already in v0.12, ref https://github.com/python-caldav/caldav/issues/233

## Deprecations

* There is a method build_date_search_query which was used internally.  I don't expect anyone is using it, and it will be removed in some future version.
* The date_search method is widely used and won't be removed any time soon - but it's redundant, consider using search instead.  Though, procrastinating dealing with doc and examples ... https://github.com/python-caldav/caldav/issues/233
* The date_search has a verify_expand attribute (because some Swede thought it was a great idea to throw an assert if the server didn't support expand).  By now it's moot, as we're doing client side expandation instead.  The attribute does nothing, but is kept there for backward compatibility.

## New dependencies

* The icalendar library was an optional requirement in v0.10 - but it's being used several places now and has become a normal requirement.
* The recurring_ical_events library is used for client-side expansion and has been added to the requirements.

## Test code

* A minor change in how things work with the new version of icalendar caused the tests to break.  This has been mended.
* All tests exercising the date_search method now also exercises the search method (and then I refactored the date_search method to be a thinnest possible wrapper over search)
* Done some work to get rid of warnings from pytest
* Excersising the client-side expansion for servers that does not support server-side expansion, but do support recurrences, and which do not throw errors when asked to expand.

## Github issues and pull requests

https://github.com/python-caldav/caldav/issues/232 - Create an CalendarObjectResource.icalendar_component property
https://github.com/python-caldav/caldav/issues/157 - Better support for broken caldav servers: do client-side parsing of rrules on expanded date searches
https://github.com/python-caldav/caldav/issues/230 - test_create_ical fails on v0.10
https://github.com/python-caldav/caldav/pull/229 - Remove nose dependency
https://github.com/python-caldav/caldav/pull/223 - obj.icalendar_instance.subcomponents[0] cannot be trusted

## Commits

... too many of them.  I will try harder to make better commits, perhaps put the master branch in protected mode, pull-requests only (but that's moot if I forget to squash the pull request before/when merging ...)
