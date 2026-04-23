# fmt: off
"""
This file serves as a database of different compatibility issues we've
encountered while working on the caldav library, and descriptions on
how the well-known servers behave.

TODO: it should probably be split with the "feature definitions",
"server implementation details" and "feature database logic" in three separate files.
"""
import copy
import warnings

# Valid support levels for features
VALID_SUPPORT_LEVELS = frozenset({
    "full",        # Feature works as expected
    "unsupported", # Feature not available (may be silently ignored)
    "fragile",     # Sometimes works, sometimes not
    "quirk",       # Supported but needs special handling
    "broken",      # Server does unexpected things
    "ungraceful",  # Server throws errors (actually most graceful for error handling)
    "unknown",     # Not yet tested/determined
})

## TODO: this file should probably be split in two (or three) as there
## are three different concerns in this file - the "feature
## definitions", some code logic, and the "database" of known server
## implementation compatibilities.

## TODO: Lots of silly comments in the compatibility matrixes now as I
## at one point managed to check out the wrong version of the
## caldav_server_checker, and things got messy from there.  We should
## double-check the values where there is any doubt, and clean up.

## NEW STYLE
## (we're gradually moving stuff from the good old
## "incompatibility_description" below over to
## "compatibility_features")

class FeatureSet:
    """Work in progress ... TODO: write a better class description.

    This class holds the description of different behaviour observed in
    a class constant.

    An object of this class describes the feature set of a server.

    TODO: use enums?  TODO: describe the different types  TODO: think more through the different types, consolidate?
      type -> "client-feature", "client-hints", "server-peculiarity", "tests-behaviour", "server-observation", "server-feature" (last is default)
      support -> "full" (default), "unsupported", "fragile", "quirk", "broken", "ungraceful"

    unsupported means that attempts to use the feature will be silently ignored (this may actually be the worst option, as it may cause data loss).  quirk means that the feature is suppored, but special handling needs to be done towards the server.  fragile means that it sometimes works and sometimes not - either it's arbitrary, or we didn't spend enough time doing research into the patterns.  My idea behind broken was that the server should do completely unexpected things.  Probably a lot of things classified as "unsupported" today should rather be classified as "broken".  Some AI-generated code is using"broken".  TODO: look through and clean up.  "ungraceful" means the server will throw some error (this may indeed be the most graceful, as the client may catch the error and handle it in the best possible way).

    types:
     * client-feature means the client is supposed to do special things (like, rate-limiting).  While the need for rate-limiting may be set by the server, it may not be possible to reliably establish it by probling the server, and the value may differ for different clients.
     * server-peculiarity - weird behaviour detected at the server side, behaviour that is too odd to be described as "missing support for a feature".  Example: there is some cache working, causing a delay from some object is sent to the server and until it can be retrieved.  The difference between an "unsupported server-feature" and a "server-peculiarity" may be a bit floating - like, arguably "instant updates" may be considered a feature.
     * tests-behaviour - configuration for the tests.  Like, it's OK to wipe everyhting from the test calendar, location of test calendar, rate-limiting that only should apply to test runs, etc.
     * server-observation - not features, but other facts found about the server
     * server-feature - some feature (preferably rooted with a pointer to some specific section of the RFC)
       * "support" -> "quirk" if we have a server-peculiarity where it's needed with special care to get the request through.

    IMPORTANT NOTE: The dotted format sort of represents a hierarchy - say, one may have foo.bar and foo.zoo.  If foo has an explicit default given in the FEATURES below, it will be considered an independent feature, otherwise it will be considered to only exist to group bar and zoo together.  This matters if bar and zoo is not supported.  Without an explicit default below, the default for foo will also be "unsupported".
    """
    FEATURES = {
        "auto-connect": {
            ## Nothing here - everything is under auto-connect.url as for now.
            ## Other connection details - like what auth method to use - could also
            ## be under the auto-connect umbrella
            "type": "client-hints",
        },
        "auto-connect.url": {
            "description": "Instruction for how to access DAV.  I.e. `/remote.php/dav` - see also https://github.com/python-caldav/caldav/issues/463.  To be used in the get_davclient method if the URL only contains a domain",
            "type": "client-hints",
            "extra_keys": {
                "basepath": "The path to append to the domain",
                "domain": "Domain name may be given through the features - useful for well-known cloud solutions",
                "scheme": "The scheme to prepend to the domain.  Defaults to https",
                ## TODO: in the future, templates for the principal URL, calendar URLs etc may also be added.
            }
        },
        "get-current-user-principal": {
            "description": "Support for RFC5397, current principal extension.  Most CalDAV servers have this, but it is an extension to the DAV standard.  Possibly observed missing on mail.ru, DavMail gateway and it is possible to configure the support in some sabre-based servers",
            "links": ["https://datatracker.ietf.org/doc/html/rfc5397"],
        },
        "get-current-user-principal.has-calendar": {
            "type": "server-observation",
            "description": "Principal has one or more calendars.  Some servers and providers comes with a pre-defined calendar for each user, for other servers a calendar has to be explicitly created (supported means there exists a calendar - it may be because the calendar was already provisioned together with the principal, or it may be because a calendar was created manually, the checks can't see the difference)"},
        "get-supported-components": {
            "description": "Server returns the supported-calendar-component-set property (RFC 4791 section 5.2.3).  The property is optional: when absent the RFC mandates that all component types are accepted, so 'unsupported' here is not a protocol violation, but the client cannot determine the actual supported set without trying.",
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-5.2.3"],
        },
        "create-calendar.with-supported-component-types": {
            "description": "Server honours the supported-calendar-component-set restriction set at MKCALENDAR time.  When 'full', the server both advertises (or enforces) the restriction; when 'unsupported', the restriction is silently ignored (wrong-type objects can be saved to the calendar).  When 'ungraceful', the MKCALENDAR request itself fails when a component set is specified.",
        },
        "rate-limit": {
            "type": "client-feature",
            "description": "client (or test code) must sleep a bit between requests.  Pro-active rate limiting is done through interval and count, server-flagged rate-limiting is controlled through default_sleep/max_sleep",
            "extra_keys": {
                "interval": "Rate limiting window, in seconds",
                "count": "Max number of requests to send within the interval",
                "max_sleep": "Max sleep when hitting a 429 or 503 with retry-after, in seconds",
                "default_sleep": "Sleep for this long when hitting a 429, in seconds"
            }},
        "search-cache": {
            "type": "server-peculiarity",
            "description": "The server delivers search results from a cache which is not immediately updated when an object is changed.  Hence recent changes may not be reflected in search results",
            "extra_keys": {
                "delay": "after this number of seconds, we may be reasonably sure that the search results are updated",
            }
        },
        "tests-cleanup-calendar": {
            "type": "tests-behaviour",
            "description": "Deleting a calendar does not delete the objects, or perhaps create/delete of calendars does not work at all.  For each test run, every calendar resource object should be deleted for every test run",
        },
        "create-calendar": {
            "default": { "support": "full" },
            "description": "RFC4791 section 5.3.1 says that \"support for MKCALENDAR on the server is only RECOMMENDED and not REQUIRED because some calendar stores only support one calendar per user (or principal), and those are typically pre-created for each account\".  Hence a conformant server may opt to not support creating calendars, this is often seen for cloud services (some services allows extra calendars to be made, but not through the CalDAV protocol).  (RFC5689 extended MKCOL may also be used to create calendar collections as an alternative to MKCALENDAR.  We should consider testing this as well)",
            "links": [
                "https://datatracker.ietf.org/doc/html/rfc4791#section-5.3.1",
                "https://datatracker.ietf.org/doc/html/rfc5689",
            ],
        },
        "create-calendar.auto": {
            "default": { "support": "unsupported" },
            "description": "Accessing a calendar which does not exist automatically creates it",
        },
        "create-calendar.set-displayname": {
            "description": "It's possible to set the displayname on a calendar upon creation"
        },
        "delete-calendar": {
            "description": "RFC4791 says nothing about deletion of calendars, so the server implementation is free to choose weather this should be supported or not.  Section 3.2.3.2 in RFC 6638 says that if a calendar is deleted, all the calendarobjectresources on the calendar should also be deleted - but it's a bit unclear if this only applies to scheduling objects or not.  Some calendar servers moves the object to a trashcan rather than deleting it",
            "links": ["https://datatracker.ietf.org/doc/html/rfc6638#section-3.2.3.2"],
        },
        "delete-calendar.free-namespace": {
            "description": "The delete operations clears the namespace, so that another calendar with the same ID/name can be created"
        },
        "http": { },
        "http.multiplexing": {
            "description": "chulka/baikal:nginx is having Problems with using HTTP/2 with multiplexing, ref https://github.com/python-caldav/caldav/issues/564.  I haven't (yet) been able to reproduce this locally, so no check for this yet.  Due to caution and friendly advice from the niquests team, the default now is to NOT support http multiplexing.",
            "default": { "support": "fragile" },
        },
        "save-load": {
            "description": "it's possible to save and load objects to the calendar"
        },
        "save-load.event": {"description": "it's possible to save and load events to the calendar"},
        "save-load.event.recurrences": {"description": "it's possible to save and load recurring events to the calendar - events with an RRULE property set, including recurrence sets", "default": {"support": "full"}},
        "save-load.event.recurrences.count": {"description": "The server will receive and store a recurring event with a count set in the RRULE", "default": {"support": "full"}},
        ## This was Claude's suggestion and it works as of today, the
        ## "unsupported" description matches the behaviour of the Stalwart server.
        ## Stalwart apparently (in a breach with the RFC) stores the exception
        ## information as a separate CalendarObjectResource.
        ## Currently the search logic will do server-side expansion
        ## if this flag is set to "unsupported", which is the correct behaviour for Stalwart.
        ## The problem is that logically, this feature would also be "unsupported" if the exception
        ## information was simply discarded, and the current search behaviour would in
        ## such a case be incorrect if the exception is simply discarded.
        "save-load.event.recurrences.exception": {"description": "When a VCALENDAR containing a master VEVENT (with RRULE) and exception VEVENT(s) (with RECURRENCE-ID) is stored, the server keeps them together as a single calendar object resource. When unsupported, the server splits exception VEVENTs into separate calendar objects, making client-side expansion unreliable (the master expands without knowing about its exceptions)."},
        "save-load.todo": {"description": "it's possible to save and load tasks to the calendar"},
        "save-load.todo.recurrences": {"description": "it's possible to save and load recurring tasks to the calendar"},
        "save-load.todo.recurrences.count": {"description": "The server will receive and store a recurring task with a count set in the RRULE", "default": {"support": "full"}},
        "save-load.todo.recurrences.thisandfuture": {"description": "Completing a recurring task with rrule_mode='thisandfuture' works (modifies RRULE and saves back to server)", "default": {"support": "full"}},
        "save-load.todo.mixed-calendar": {"description": "The same calendar may contain both events and tasks (Zimbra only allows tasks to be placed on special task lists)", "default": {"support": "full"}},
        "save-load.journal": {"description": "The server will even accept journals"},
        ## TODO: zimbra cannot mix events and tasks, but then davis surprised me by not allowing journals on the same calendar.  But this may be a miss in the checking script - it may be that mixing is allowed, but that the calendar has to be set up from scratch with explicit support for both VJOURNAL and other things
        "save-load.journal.mixed-calendar": {"description": "The same calendar may contain events, tasks and journals (some servers require journals on a dedicated VJOURNAL calendar)", "default": {"support": "full"}},
        "save-load.get-by-url": {
            "description": "GET requests to calendar object resource URLs work correctly. When unsupported, the server returns 404 on GET even for valid object URLs. The client works around this by falling back to UID-based lookup.",
        },
        "save-load.reuse-deleted-uid": {
            "description": "After deleting an event, the server allows creating a new event with the same UID. When 'broken', the server keeps deleted events in a trashbin with a soft-delete flag, causing unique constraint violations on UID reuse. See https://github.com/nextcloud/server/issues/30096"
        },
        "save-load.event.timezone": {
            "description": "The server accepts events with non-UTC timezone information. When unsupported or broken, the server may reject events with timezone data (e.g., return 403 Forbidden). Related to GitHub issue https://github.com/python-caldav/caldav/issues/372."
        },
        "save-load.icalendar": {"description": "Is it possible to save icalendar data to the calendar?  (Most likely yes - but we need a parent to collect all icalendar compatibility problems that aren't specific to one kind of object resource types"},
        "save-load.icalendar.related-to": {
            "description": "The server preserves RELATED-TO properties (RFC5545 section 3.8.4.5) when saving and loading calendar objects. When 'unsupported', the server may typically silently strip all RELATED-TO lines",
            "default": {"support": "full"},
            "links": ["https://datatracker.ietf.org/doc/html/rfc5545#section-3.8.4.5"],
        },
        "search": {
            "description": "calendar MUST support searching for objects using the REPORT method, as specified in RFC4791, section 7",
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-7"],
        },
        "search.comp-type.optional": {
            "description": "In all the search examples in the RFC, comptype is given during a search, the client specifies if it's event or tasks or journals that is wanted.  However, as I read the RFC this is not required.  If omitted, the server should deliver all objects.  Many servers will not return anything if the COMPTYPE filter is not set.  Other servers will return 404"
        },
        "search.comp-type": {
            "description": "Server correctly filters calendar-query results by component type. When 'broken', server may misclassify component types (e.g., returning TODOs when VEVENTs are requested). The library will perform client-side filtering to work around this issue",
            "default": {"support": "full"}
        },
        ## TODO - there is still quite a lot of search-related
        ## stuff that hasn't been moved from the old "quirk list"
        "search.time-range": {
            "description": "Search for time or date ranges should work.  This is specified in RFC4791, section 7.4 and section 9.9",
            "links": [
                "https://datatracker.ietf.org/doc/html/rfc4791#section-7.4",
                "https://datatracker.ietf.org/doc/html/rfc4791#section-9.9",
            ],
        },
        "search.time-range.accurate": {
            "description": "Time-range searches should only return events/todos that actually fall within the requested time range. Some servers incorrectly return recurring events whose recurrences fall outside (after) the search interval, or events with no recurrences in the requested time range at all. RFC4791 section 9.9 specifies that a VEVENT component overlaps a time range if the condition (start < search_end AND end > search_start) is true.",
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.9"],
        },
        "search.time-range.todo": {"description": "basic time range searches for tasks works", "default": {"support": "full"}},
        "search.time-range.todo.old-dates": {"description": "time range searches for tasks with old dates (e.g. year 2000) work - some servers enforce a min-date-time restriction"},
        "search.time-range.todo.strict": {
            "description": "Bounded VTODO time-range searches do not return tasks whose time span falls entirely outside the searched range (no false positives).",
            "default": {"support": "full"},
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.9"],
        },
        "search.time-range.open": {
            "description": "Open-ended time-range searches (with only one bound) work correctly. RFC4791 section 9.9: the CALDAV:time-range 'start' and 'end' attributes are optional; if absent, assume -infinity and +infinity respectively. At least one attribute must be present.",
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.9"],
        },
        "search.time-range.open.end": {
            "description": "Searches with only a start bound (end assumed +infinity) correctly return components whose time span overlaps the start. RFC4791 section 9.9: for a VTODO with DTSTART+DUE and absent end bound, the overlap condition is (start < DUE) OR (start <= DTSTART). When 'unsupported', such queries return no results.",
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.9"],
        },
        "search.time-range.open.start": {
            "description": "Searches with only an end bound (start assumed -infinity) correctly exclude components whose DTSTART is after the end bound. RFC4791 section 9.9: a VTODO with DTSTART+DUE should not overlap if its DTSTART > search_end. When 'broken', the server incorrectly returns future tasks.",
            "default": {"support": "full"},
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.9"],
        },
        "search.time-range.open.start.duration": {
            "description": "Time-range searches correctly handle components that specify their interval via DTSTART+DURATION (without DTEND/DUE). RFC4791 section 9.9: a VEVENT with DURATION (end > 0s) overlaps [start, end] if (start < DTSTART+DURATION) AND (end > DTSTART); a VTODO with DTSTART+DURATION overlaps if (start <= DTSTART+DURATION) AND ((end > DTSTART) OR (end >= DTSTART+DURATION)). Tested for both VTODO and VEVENT; if support is asymmetric across component types the feature is marked 'broken' with a behaviour note.",
            "default": {"support": "full"},
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.9"],
        },
        "search.time-range.event": {"description": "basic time range searches for event works", "default": {"support": "full"}},
        "search.time-range.event.old-dates": {"description": "time range searches for events with old dates (e.g. year 2000) work - some servers enforce a min-date-time restriction"},
        "search.time-range.journal": {"description": "basic time range searches for journal works"},
        "search.time-range.alarm": {
            "description": "Time range searches for alarms work. The server supports searching for events based on when their alarms trigger, as specified in RFC4791 section 9.9",
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.9"],
        },
        "search.unlimited-time-range": {
            "description": "A REPORT without a time-range filter should return all matching objects regardless of when they occur. Some servers (e.g. OX App Suite) use a sliding window for REPORT requests without a time range, returning only objects within approximately ±1 year of now and potentially missing older or far-future objects.",
            "default": {"support": "full"},
        },
        "search.is-not-defined": {
            "description": "Supports searching for objects where properties is-not-defined according to rfc4791 section 9.7.4",
            "default": {"support": "full"},
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.7.4"],
        },
        "search.is-not-defined.category": { ## TODO: this should most likely be removed - it was a client bug fixed in icalendar-search 1.0.5, not a server error. (Discovered in the last minute before releasing caldav v3.0.0 - I won't touch it now)
            "description": "Supports searching for objects where the CATEGORIES property is not defined (RFC4791 section 9.7.4). Some servers support is-not-defined for other properties (e.g. CLASS) but silently return wrong results or nothing when applied to CATEGORIES",
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.7.4"],
        },
        "search.is-not-defined.dtend": { ## TODO: this should most likely be removed - it was a client bug fixed in icalendar-search 1.0.5, not a server error. (Discovered in the last minute before releasing caldav v3.0.0 - I won't touch it now)
            "description": "Supports searching for objects where the DTEND property is not defined (RFC4791 section 9.7.4). Some servers support is-not-defined for some properties but not DTEND",
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.7.4"],
        },
        "search.is-not-defined.class": {
            "description": "Supports searching for objects where the CLASS property is not defined (RFC4791 section 9.7.4). Some servers support is-not-defined for CLASS but not for other properties like CATEGORIES",
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.7.4"],
        },
        "search.text": {
            "description": "Search for text attributes should work"
        },
        "search.text.case-sensitive": {
            "description": "In RFC4791, section-9.7.5, a text-match may pass a collation, and i;ascii-casemap MUST be the default, this is not checked (yet - TODO) by the caldav-server-checker project.  Section 7.5 describes that the servers also are REQUIRED to support i;octet.  The definitions of those collations are given in RFC4790, i;octet is a case-sensitive byte-by-byte comparition (fastest).  search.text.case-sensitive is supported if passing the i;octet collation to search causes the search to be case-sensitive.",
            "links": [
                "https://datatracker.ietf.org/doc/html/rfc4791#section-9.7.5",
                "https://datatracker.ietf.org/doc/html/rfc4791#section-7.5",
                "https://datatracker.ietf.org/doc/html/rfc4790",
            ],
        },
        "search.text.case-insensitive": {
            "description": "The i;ascii-casemap requires ascii-characters to be case-insensitive, while non-ascii characters are compared byte-by-byte (case-sensitive).  Proper unicode case-insensitive searches may be supported by the server, but it's not a requirement in the RFC.  As for now, we consider case-insensitive searches to be supported if the i;ascii-casemap collation does what it's supposed to do..  In the future we may consider adding a search.text.case-insensitive.unicode. (i;unicode-casemap is defined in RFC5051)",
            "links": [
                "https://datatracker.ietf.org/doc/html/rfc4791#section-9.7.5",
                "https://datatracker.ietf.org/doc/html/rfc5051",
            ],
        },
        "search.text.substring": {
            "description": "According to RFC4791 the search done should be a substring search.  The search.text.substring feature is set if the calendar server does this (as opposed to only return full matches).  Substring matches does not always make sense, but it's mandated by the RFC.  When a server does a substring match on some properties but an exact match on others, the support should be marked as fragile.  Except for categories, which are handled in search.text.category.substring",
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.7.5"],
        },
        "search.text.category": {
            "description": "Search for category should work.  This is not explicitly specified in RFC4791, but covered in section 9.7.5.  No examples targets categories explicitly, but there are some text match examples in section 7.8.6 and following sections",
            "links": [
                "https://datatracker.ietf.org/doc/html/rfc4791#section-9.7.5",
                "https://datatracker.ietf.org/doc/html/rfc4791#section-7.8.6",
            ],
        },
        "search.text.category.substring": {
            "description": "Substring search for category should work according to the RFC.  I.e., search for mil should match family,finance",
        },
        "search.recurrences": {
            "description": "Support for recurrences in search"
        },
        "search.recurrences.includes-implicit": {
            "description": "RFC 4791, section 7.4 says that the server MUST expand recurring components to determine whether any recurrence instances overlap the specified time range.  Considered supported i.e. if a search for 2005 yields a yearly event happening first time in 2004.",
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-7.4"],
        },
        "search.recurrences.includes-implicit.todo": {
            "description": "tasks can also be recurring"
        },
        "search.recurrences.includes-implicit.todo.pending": {
            "description": "a future recurrence of a pending task should always be pending and appear in searches for pending tasks",
            "default": {"support": "full"},
        },
        "search.recurrences.includes-implicit.event": {
            "description": "support for events"
        },
        "search.recurrences.includes-implicit.infinite-scope": {
            "description": "Needless to say, search on any future date range, no matter how far out in the future, should yield the recurring object"
        },
        "search.combined-is-logical-and": {
            "description": "Multiple search filters should yield only those that passes all filters"
            ## For "unsupported", we could also add a "behaviour" (returns everything, returns nothing, returns logical OR, etc).
        },
        "search.recurrences.expanded": {
            "description": "According to RFC 4791, the server MUST expand recurrence objects if asked for it - but many server doesn't do that.  Some servers don't do expand at all, others deliver broken data, typically missing RECURRENCE-ID.  The python caldav client library (from 2.0) does the expand-operation client-side no matter if it's supported or not",
            "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.6.5"],
        },
        "search.recurrences.expanded.todo": {
            "description": "expanding tasks"
        },
        "search.recurrences.expanded.event": {
            "description": "exanding events"
        },
        "search.recurrences.expanded.exception": {
            "description": "Server expand should work correctly also if a recurrence set with exceptions is given"
        },
        "sync-token": {
            "description": "RFC6578 sync-collection reports are supported. Server provides sync tokens that can be used to efficiently retrieve only changed objects since last sync. Support can be 'full', 'fragile' (occasionally returns more content than expected), or 'unsupported'. Behaviour 'time-based' indicates second-precision tokens requiring sleep(1) between operations",
            "links": ["https://datatracker.ietf.org/doc/html/rfc6578"],
        },
        "sync-token.delete": {
            "description": "Server correctly handles sync-collection reports after objects have been deleted from the calendar (solved in Nextcloud in https://github.com/nextcloud/server/pull/44130)"
        },
        "scheduling": {
            "description": "Server supports CalDAV Scheduling (RFC6638). Detected via the presence of 'calendar-auto-schedule' in the DAV response header.",
            "links": ["https://datatracker.ietf.org/doc/html/rfc6638"],
        },
        "scheduling.mailbox": {
            "description": "Server provides schedule-inbox and schedule-outbox collections for the principal (RFC6638 sections 2.1-2.2). When unsupported, calls to schedule_inbox() or schedule_outbox() raise NotFoundError.",
            "links": [
                "https://datatracker.ietf.org/doc/html/rfc6638#section-2.1",
                "https://datatracker.ietf.org/doc/html/rfc6638#section-2.2",
            ],
            "default": {"support": "full"},
        },
        "scheduling.calendar-user-address-set": {
            "description": "Server provides the calendar-user-address-set property on the principal (RFC6638 section 2.4.1), used to identify a user's email/URI for scheduling purposes. When unsupported, calendar_user_address_set() raises NotFoundError.",
            "links": ["https://datatracker.ietf.org/doc/html/rfc6638#section-2.4.1"],
        },
        "scheduling.mailbox.inbox-delivery": {
            "description": "Server delivers incoming scheduling REQUEST messages to the attendee's schedule-inbox (RFC6638 section 4.1). See also scheduling.auto-schedule for whether the server additionally auto-processes invitations into the attendee's calendar.",
            "links": [
                "https://datatracker.ietf.org/doc/html/rfc6638#section-4.1",
            ],
        },
        "scheduling.auto-schedule": {
            "description": "Server automatically processes incoming iTIP REQUEST messages and adds the event directly to the attendee's calendar without requiring explicit acceptance from the inbox (RFC6638 SCHEDULE-AGENT=SERVER behaviour). When False/unsupported, the attendee must process inbox items manually. Note: only detectable from the caldav-server-tester with a cross-user probe (extra_principals configured).",
            "links": [
                "https://datatracker.ietf.org/doc/html/rfc6638",
            ],
            "default": {"support": "full"},
        },
        "scheduling.schedule-tag": {
            "description": "Server returns a Schedule-Tag response header on GET of a scheduling object resource (a calendar object with an ORGANIZER property) and exposes the schedule-tag DAV property via PROPFIND (RFC6638 sections 3.2-3.3). Clients use the Schedule-Tag for conditional PUT requests to detect concurrent scheduling changes.",
            "default": {"support": "full"},
            "links": [
                "https://datatracker.ietf.org/doc/html/rfc6638#section-3.2",
                "https://datatracker.ietf.org/doc/html/rfc6638#section-3.3",
            ],
        },
        "scheduling.schedule-tag.stable-partstat": {
            "description": "Server keeps the Schedule-Tag stable when an attendee performs a PARTSTAT-only update (RFC6638 section 3.2 requirement). Non-compliant servers change the tag even when only PARTSTAT is updated, breaking conditional-PUT logic for other attendees.",
            "links": ["https://datatracker.ietf.org/doc/html/rfc6638#section-3.2"],
        },
        "scheduling.freebusy-query": {
            "description": "Server supports the RFC6638 freebusy query: the organizer POSTs a VFREEBUSY REQUEST to the schedule outbox and the server returns free/busy information for the listed attendees.",
            "links": ["https://datatracker.ietf.org/doc/html/rfc6638#section-5"],
        },
        'freebusy-query': {
            'description': "Server supports the RFC4791 free/busy-query REPORT (section 7.10): a REPORT sent directly to a calendar collection to retrieve free/busy time for a range. See also scheduling.freebusy-query for the RFC6638 variant which POSTs a VFREEBUSY to the schedule outbox.",
            "links": [
                "https://datatracker.ietf.org/doc/html/rfc4791#section-7.10",
            ],
        },
        "principal-search": {
            "description": "Server supports searching for principals (CalDAV users). Principal search may be restricted for privacy/security reasons on many servers.  (not to be confused with get-current-user-principal)"
        },
        "principal-search.by-name": {
            "description": "Server supports searching for principals by display name. Testing this properly requires setting up another user with a known name, so this check is not yet implemented"
        },
        "principal-search.by-name.self": {
            "description": "Server allows searching for own principal by display name. Some servers block this for privacy reasons even when general principal search works"
        },
        "principal-search.list-all": {
            "description": "Server allows listing all principals without a name filter. Often blocked for privacy/security reasons"
        },
        "wrong-password-check": { ## TODO: reconsider this one.  The name should be reconsidered, perhaps it should be removed at all as it's specific for some test servers, and those test servers should be marked with a special password in the config for tests to pass.
            "description": "Server rejects requests with wrong password by returning an authorization error. Some servers may not properly reject wrong passwords in certain configurations."
        },
        "save": {},
        "save.duplicate-uid": {},
        "save.duplicate-uid.cross-calendar": {
            "description": "Server allows events with the same UID to exist in different calendars and treats them as separate entities. Support can be 'full' (allowed), 'ungraceful' (rejected with error), or 'unsupported' (silently ignored or moved). Behaviour 'silently-ignored' means the duplicate is not saved but no error is thrown. Behaviour 'moved-instead-of-copied' means the event is moved from the original calendar to the new calendar (Zimbra behavior)"
        },
        ## TODO: as for now, the tests will run towards the first calendar it will find, and most of the tests will assume the calendar is empty.  This is bad.
        "test-calendar": {
            "type": "tests-behaviour",
            "description": "if the server does not allow creating new calendars, then use the calendar with the given name for running tests (NOT SUPPORTED YET!), wipe the calendar between each test run (alternative for calendars not supporting the creation of new calendars is a very expensive delete objects one-by-one by uid)",
            "extra_keys": { "name": "calendar name", "cleanup-regime": "thorough|pre|post|light|wipe-calendar" }
        },
        "test-calendar.compatibility-tests": {
            "type": "tests-behaviour",
            "description": "if the server does not allow creating new calendars, then use the calendar with the given name for running the compatibility tests",
            "extra_keys": { "name": "calendar name", "cleanup": "Set to True to clean up the calendar after compatibility run" } ## if needed, pad up with cal_id, url, etc
        } ## if needed we may pad up with test-calendar.compatibility-tests.events, etc, etc
    }

    def __init__(self, feature_set_dict=None):
        """
        TODO: describe the feature_set better.

        Should be a dict on the same style as self.FEATURES, but different.

        Shortcuts accepted in the dict, like:

        {
            "recurrences.search-includes-implicit-recurrences.infinite-scope":
                "unsupported" }

        is equivalent with

        {
           "recurrences": {
               "features": {
                   "search-includes-inplicit-recurrences": {
                       "infinite-scope":
                           "support": "unsupported" }}}}

        (TODO: is this sane?  Am I reinventing a configuration language?)
        """
        if isinstance(feature_set_dict, FeatureSet):
            self._server_features = copy.deepcopy(feature_set_dict._server_features)
            self.backward_compatibility_mode = feature_set_dict.backward_compatibility_mode
            self._old_flags = copy.copy(feature_set_dict._old_flags) if hasattr(feature_set_dict, '_old_flags') else []
            return

        ## TODO: copy the FEATURES dict, or just the feature_set dict?
        ## (anyways, that is an internal design decision that may be
        ## changed ... but we need test code in place)
        self.backward_compatibility_mode = feature_set_dict is None
        self._server_features = {}
        ## TODO: remove this when it can be removed
        self._old_flags = []
        if feature_set_dict:
            self.copyFeatureSet(feature_set_dict, collapse=False)


    def set_feature(self, feature, value=True):
        if isinstance(value, dict):
            fc = {feature: value}
        elif isinstance(value, str):
            fc = {feature: {"support": value}}
        elif value is True:
            fc = {feature: {"support": "full"}}
        elif value is False:
            fc = {feature: {"support": "unsupported"}}
        elif value is None:
            fc = {feature: {"support": "unknown"}}
        else:
            raise AssertionError
        self.copyFeatureSet(fc, collapse=False)


    ## TODO: Why is this camelCase while every other method is with under_score?  rename ...
    def copyFeatureSet(self, feature_set, collapse=True):
        for feature in feature_set:
            ## TODO: temp - should be removed
            if feature == 'old_flags':
                self._old_flags = feature_set[feature]
                continue
            try:
                feature_info = self.find_feature(feature)
            except (AssertionError, KeyError):
                warnings.warn(
                    f"Unknown feature '{feature}' in configuration. "
                    "This might be a typo. Check caldav/compatibility_hints.py for valid features.",
                    UserWarning,
                    stacklevel=3,
                )
            value = feature_set[feature]
            if feature not in self._server_features:
                self._server_features[feature] = {}
            server_node = self._server_features[feature]
            if isinstance(value, bool):
                server_node['support'] = "full" if value else "unsupported"
            elif isinstance(value, str) and 'support' not in server_node:
                self._validate_support_level(value, feature)
                server_node['support'] = value
            elif isinstance(value, dict):
                if 'support' in value:
                    self._validate_support_level(value['support'], feature)
                server_node.update(value)
            else:
                raise AssertionError
        if collapse:
            self.collapse()

    def _validate_support_level(self, level, feature_name):
        """Validate that a support level is valid, warn if not."""
        if level not in VALID_SUPPORT_LEVELS:
            warnings.warn(
                f"Feature '{feature_name}' has invalid support level '{level}'. "
                f"Valid levels: {', '.join(sorted(VALID_SUPPORT_LEVELS))}",
                UserWarning,
                stacklevel=4,
            )

    def _collapse_key(self, feature_dict):
        """
        Extract the key part of a feature dictionary for comparison during collapse.

        For collapse purposes, we compare the 'support' level (or 'enable', 'behaviour', 'observed')
        but ignore differences in detailed behaviour messages, as those are often implementation-specific
        error messages that shouldn't prevent collapsing.
        """
        if not isinstance(feature_dict, dict):
            return feature_dict

        # Return a tuple of the main status fields, ignoring detailed messages
        return (
            feature_dict.get('support'),
            feature_dict.get('enable'),
            feature_dict.get('observed'),
        )

    def collapse(self):
        """
        If all subfeatures are the same, it should be collapsed into the parent

        Messy and complex logic :-(
        """
        features = list(self._server_features.keys())
        parents = set()
        for feature in features:
            if '.' in feature:
                parents.add(feature[:feature.rfind('.')])
        parents = list(parents)
        ## Parents needs to be ordered by the number of dots.  We proceed those with most dots first.
        parents.sort(key = lambda x: (-x.count('.'), x))
        for parent in parents:
            parent_info = self.find_feature(parent)

            if len(parent_info['subfeatures']):
                foo = self.is_supported(parent, return_type=dict, return_defaults=False)
                if len(parent_info['subfeatures']) > 1 or foo is not None:
                    dont_collapse = False
                    foo_key = self._collapse_key(foo) if foo is not None else None
                    for sub in parent_info['subfeatures']:
                        bar = self._server_features.get(f"{parent}.{sub}")
                        if bar is None:
                            dont_collapse = True
                            break
                        bar_key = self._collapse_key(bar)
                        if foo is None:
                            foo = bar
                            foo_key = bar_key
                        elif bar_key != foo_key:
                            dont_collapse = True
                            break
                    if not dont_collapse:
                        if parent not in self._server_features:
                            self._server_features[parent] = {}
                        for sub in parent_info['subfeatures']:
                            self._server_features.pop(f"{parent}.{sub}")
                        self.copyFeatureSet({parent: foo})

    def _default(self, feature_info):
        if isinstance(feature_info, str):
            feature_info = self.find_feature(feature_info)
        if 'default' in feature_info:
            return feature_info['default']
        feature_type = feature_info.get('type', 'server-feature')
        ## TODO: move the default values up to some constant dict probably, like self.DEFAULTS = { "server-feature": {...}}
        if feature_type == 'server-feature':
            return { "support": "full" }
        elif feature_type == 'client-feature':
            return { "enable": False }
        elif feature_type == 'server-peculiarity':
            return { "behaviour": "normal" }
        elif feature_type == 'server-observation':
            return { "observed": True }
        elif feature_type in ('tests-behaviour', 'client-hints'):
            return { }
        else:
            raise ValueError(f"Unknown feature type: {feature_type!r}")

    def is_supported(self, feature, return_type=bool, return_defaults=True, accept_fragile=False):
        """Work in progress

        TODO: write a better docstring

        The dotted features is essentially a tree.  If feature foo
        is unsupported it basically means that feature foo.bar is also
        unsupported.  Hence the extra logic visiting "nodes".
        """
        feature_info = self.find_feature(feature)
        feature_ = feature
        while True:
            if feature_ in self._server_features:
                return self._convert_node(self._server_features[feature_], feature_info, return_type, accept_fragile)
            # Try deriving status from subfeatures at this level
            current_info = feature_info if feature_ == feature else self.find_feature(feature_)
            if 'default' not in current_info:
                derived = self._derive_from_subfeatures(feature_, current_info, return_type, accept_fragile)
                if derived is not None:
                    return derived
            if '.' not in feature_:
                if not return_defaults:
                    return None
                # For features WITHOUT an explicit default (i.e. pure grouping features),
                # derive status from subfeatures.  Features WITH a default represent
                # independent capabilities and their default should not be overridden
                # by subfeature statuses (e.g. create-calendar is supported even if
                # create-calendar.set-displayname is not).
                if 'default' not in feature_info:
                    derived = self._derive_from_subfeatures(feature_, feature_info, return_type, accept_fragile)
                    if derived is not None:
                        return derived
                return self._convert_node(self._default(feature_info), feature_info, return_type, accept_fragile)
            feature_ = feature_[:feature_.rfind('.')]

    _POSITIVE_STATUSES = frozenset({'full', 'quirk'})

    def _derive_from_subfeatures(self, feature, feature_info, return_type, accept_fragile=False):
        """
        Derive parent feature status from explicitly set subfeatures.

        Logic:
        - Only consider subfeatures WITHOUT explicit defaults (those are independent features)
        - If ANY relevant subfeature has a positive status (full/quirk) → derive as that status
          (any support means the parent has some support)
        - If ALL relevant subfeatures are set AND all have the same negative status → use that status
        - If only a PARTIAL set of subfeatures is configured with all negative statuses →
          return None (incomplete information, fall through to default)
        - Mixed statuses (some positive, some negative) → "unknown"

        Returns None if no relevant subfeatures are explicitly set or if
        derivation is inconclusive due to partial information.
        """
        if 'subfeatures' not in feature_info or not feature_info['subfeatures']:
            return None

        # Count relevant subfeatures (those without explicit defaults) and collect statuses
        total_relevant = 0
        subfeature_statuses = []
        for sub in feature_info['subfeatures']:
            subfeature_key = f"{feature}.{sub}"
            # Skip subfeatures with explicit defaults - they represent independent behaviors
            try:
                subfeature_info = self.find_feature(subfeature_key)
                if 'default' in subfeature_info:
                    continue
            except Exception:
                pass

            total_relevant += 1

            if subfeature_key in self._server_features:
                sub_dict = self._server_features[subfeature_key]
                # Extract the support level (or enable/behaviour/observed)
                status = sub_dict.get('support', sub_dict.get('enable', sub_dict.get('behaviour', sub_dict.get('observed'))))
                if status:
                    subfeature_statuses.append(status)

        # If no relevant subfeatures are explicitly set, return None (use default)
        if not subfeature_statuses:
            return None

        has_positive = any(s in self._POSITIVE_STATUSES for s in subfeature_statuses)
        all_same = all(s == subfeature_statuses[0] for s in subfeature_statuses)
        is_complete = len(subfeature_statuses) >= total_relevant

        if has_positive:
            if all_same:
                derived_status = subfeature_statuses[0]
            else:
                # Mixed positive/negative → unknown
                derived_status = 'unknown'
        elif is_complete and all_same:
            # All relevant subfeatures set, all the same negative status
            derived_status = subfeature_statuses[0]
        elif is_complete:
            # All relevant subfeatures set, mixed non-positive statuses
            derived_status = 'unknown'
        else:
            # Partial set with only non-positive statuses → inconclusive,
            # the unset siblings might have different (positive) status
            return None

        # Create a node dict with the derived status
        derived_node = {'support': derived_status}
        return self._convert_node(derived_node, feature_info, return_type, accept_fragile)

    def _convert_node(self, node, feature_info, return_type, accept_fragile=False):
        """
        Return the information in a "node" given the wished return_type

        (The dotted feature format was an afterthought, the first
        iteration of this code the feature tree was actually a
        hierarchical dict, hence the naming of the method.  I
        considered it too complicated though)
        """
        if return_type is str:
            ## TODO: consider feature_info['type'], be smarter about it
            return node.get('support', node.get('enable', node.get('behaviour')))
        elif return_type is dict:
            return node
        elif return_type is bool:
            ## TODO: consider feature_info['type'], be smarter about this
            support = node.get('support', 'full')
            if support == 'quirk':
                return True
            if accept_fragile and support == 'fragile':
                support = 'full'
            if feature_info.get('type', 'server-feature') == 'server-feature':
                return support == 'full'
            else:
                ## TODO: this may be improved
                return not node.get('enable') and not node.get('behaviour') and not node.get('observed')
        else:
            raise AssertionError

    @classmethod
    def find_feature(cls, feature: str) -> dict:
        """
        Feature should be a string like feature.subfeature.subsubfeature.

        Looks through the FEATURES list and returns the relevant section.

        Will raise an Error if feature is not found

        (this is very simple now - used to be a hierarchy dict to be traversed)
        """
        assert feature in cls.FEATURES ## A feature in the configured feature-list does not exist.  TODO ... raise a better exception?
        if 'name' not in cls.FEATURES[feature]:
            cls.FEATURES[feature]['name'] = feature
        if '.' in feature and 'parent' not in cls.FEATURES[feature]:
            cls.FEATURES[feature]['parent'] = cls.find_feature(feature[:feature.rfind('.')])
        if 'subfeatures' not in cls.FEATURES[feature]:
            tree = cls.feature_tree()
            for x in feature.split('.'):
                tree = tree[x]
            cls.FEATURES[feature]['subfeatures'] = tree
        return cls.FEATURES[feature]

    @classmethod
    def _dots_to_tree(cls, target, source):
        for feat in source:
            node = target
            path = feat.split('.')
            for part in path:
                if part not in node:
                    node[part] = {}
                node = node[part]
        return target

    @classmethod
    def feature_tree(cls) -> dict:
        """TODO: is this in use at all?  Can it be deprecated already?

        TODO: the description may be outdated as I decided to refactor
        things from "overly complex" to "just sufficiently complex".
        Or maybe it's still a bit too complex.

        A "path" may have several "subpaths" in self.FEATURES
        (i.e. feat.subfeat.A, feat.subfeat.B, feat.subfeat.C)

        This method will return `{'feat': { 'subfeat': {'A': {}, ...}}}`
        making it possible to traverse the feature tree

        """
        ## I'm an old fart, grown up in an age where CPU-cycles was considered
        ## expensive ... so I always cache things when possible ...
        if hasattr(cls, '_feature_tree'):
            return cls._feature_tree
        cls._feature_tree = {}
        cls._dots_to_tree(cls._feature_tree, cls.FEATURES)
        return cls._feature_tree

    def dotted_feature_set_list(self, compact=False):
        ret = {}
        if compact:
            self.collapse()
        for x in self._server_features:
            feature = self._server_features[x]
            if compact and feature == self._default(x):
                continue
            ret[x] = feature.copy()
        return ret

#### OLD STYLE

## THE LIST BELOW IS TO BE REMOVED COMPLETELY.  DO NOT USE IT.

## It's not considered to be part of the public API (though, it should
## have been prefixed with _ to make it clear).  The list is being
## removed little-by-little, without regards of SemVer.

## The lists below are specifying what tests should be skipped or
## modified to accept non-conforming resultsets from the different
## calendar servers.  In addition there are some hacks in the library
## code itself to work around some known compatibility issues, like
## the caldav.lib.vcal.fix function.
## Here is a list of all observed (in)compatibility issues the test framework needs to know about
## TODO:
## * references to the relevant parts of the RFC would be nice.
## * Research should be done to triple-check that the issue is on the server side, and not on the client side
## * Some of the things below should be possible to probe the server for.
## * Perhaps some more readable format should be considered (yaml?).
## * Consider how to get this into the documentation
incompatibility_description = {
    'calendar_order':
        """Server supports (nonstandard) calendar ordering property""",

    'calendar_color':
        """Server supports (nonstandard) calendar color property""",

    'duplicates_not_allowed':
        """Duplication of an event in the same calendar not allowed """
        """(even with different uid)""",


    'event_by_url_is_broken':
        """A GET towards a valid calendar object resource URL will yield 404 (wtf?)""",

    'propfind_allprop_failure':
        """The propfind test fails ... """
        """it asserts DAV:allprop response contains the text 'resourcetype', """
        """possibly this assert is wrong""",

    'vtodo_datesearch_nodtstart_task_is_skipped':
        """date searches for todo-items will not find tasks without a dtstart""",

    'vtodo_datesearch_nodtstart_task_is_skipped_in_closed_date_range':
        """only open-ended date searches for todo-items will find tasks without a dtstart""",

    'vtodo_datesearch_notime_task_is_skipped':
        """date searches for todo-items will (only) find tasks that has either """
        """a dtstart or due set""",

    'vtodo_no_due_infinite_duration':
        """date search will find todo-items without due if dtstart is """
        """before the date search interval.  This is in breach of rfc4791"""
        """section 9.9""",

    'vtodo-cannot-be-uncompleted':
        """If a VTODO object has been set with STATUS:COMPLETE, it's not possible to delete the COMPLTEDED attribute and change back to STATUS:IN-ACTION""",

    'unique_calendar_ids':
        """For every test, generate a new and unique calendar id""",

    'sticky_events':
        """Events should be deleted before the calendar is deleted, """
        """and/or deleting a calendar may not have immediate effect""",

    'no_overwrite':
        """events cannot be edited""",

    'dav_not_supported':
        """when asked, the server may claim it doesn't support the DAV protocol.  Observed by one baikal server, should be investigated more (TODO) and robur""",

   'fastmail_buggy_noexpand_date_search':
        """The 'blissful anniversary' recurrent example event is returned when asked for a no-expand date search for some timestamps covering a completely different date""",

    'non_existing_raises_other':
        """Robur raises AuthorizationError when trying to access a non-existing resource (while 404 is expected).  Probably so one shouldn't probe a public name space?""",

    'robur_rrule_freq_yearly_expands_monthly':
        """Robur expands a yearly event into a monthly event.  I believe I've reported this one upstream at some point, but can't find back to it""",

}

## This is for Xandikos 0.2.12.
## Lots of development going on as of summer 2025, so expect the list to become shorter soon!
xandikos_v0_2_12 = {
    ## this only applies for very simple installations
    "auto-connect.url": {"domain": "localhost", "scheme": "http", "basepath": "/"},
    'search.recurrences.includes-implicit': {'support': 'unsupported'},
    'search.recurrences.expanded': {'support': 'unsupported'},
    'search.time-range.todo': {'support': 'unsupported'},
    'search.time-range.alarm': {'support': 'ungraceful', 'behaviour': '500 internal server error'},
    'search.comp-type.optional': {'support': 'ungraceful'},
    "search.text.substring": {"support": "unsupported"},
    "search.text.category.substring": {"support": "unsupported"},
    'principal-search': {'support': 'unsupported'},
    'freebusy-query': {'support': 'ungraceful', 'behaviour': '500 internal server error'},
    "scheduling": {"support": "unsupported"},
    ## https://github.com/jelmer/xandikos/issues/8
    'search.time-range.open.start.duration': {'support': 'unsupported'},
    'search.time-range.open.start': {'support': 'broken', 'behaviour': 'future tasks are returned when only an end bound is given'},
}

xandikos = {
    ## Principal property search returns 403 (not implemented)
    "principal-search": "ungraceful",

    ## Server-side recurrence expansion for event exceptions is still broken;
    ## VTODO RRULE expansion was fixed in xandikos PR #627 (released in 0.3.7).
    "search.recurrences.expanded.exception": "unsupported",

    ## Open-start time-range searches (no lower bound) crash xandikos 0.3.7 with a
    ## 500 Internal Server Error (OverflowError: date value out of range in icalendar.py
    ## _expand_rrule_component when computing adjusted_start = start - duration).
    "search.time-range.open.start": {"support": "ungraceful", "behaviour": "500 Internal Server Error (OverflowError in rrule expansion)"},
    "search.time-range.open.start.duration": True,

    ## this only applies for very simple installations
    "auto-connect.url": {"domain": "localhost", "scheme": "http", "basepath": "/"},

    "scheduling": {"support": "unsupported"},
}

## This seems to work as of version 3.5.4 of Radicale.
## There is much development going on at Radicale as of summar 2025,
## so I'm expecting this list to shrink a lot soon.
radicale = {
    "search.is-not-defined": {"support": "full"},
    "search.text.case-sensitive": {"support": "unsupported"},
    "search.recurrences.includes-implicit.todo.pending": {"support": "fragile", "behaviour": "inconsistent results between runs"},
    "search.recurrences.expanded.todo": {"support": "unsupported"},
    "search.recurrences.expanded.exception": {"support": "unsupported"},
    "principal-search": {"support": "unsupported"},
    ## this only applies for very simple installations
    "auto-connect.url": {"domain": "localhost", "scheme": "http", "basepath": "/"},
    "scheduling": {"support": "unsupported"},
    'old_flags': [
    ## extra features not specified in RFC4791
    "calendar_order",
    "calendar_color"
    ]
}

## Be aware that nextcloud by default have different rate limits, including how often a user is allowed to create a new calendar.  This may break test runs badly.
nextcloud = {
    'auto-connect.url': {
        'basepath': '/remote.php/dav',
    },
    ## I'm surprised, I'm quite sure this was reported ungraceful earlier.  Passed with caldav commit a98d50490b872e9b9d8e93e2e401c936ad193003, caldav server checker commit 3cae24cf99da1702b851b5a74a9b88c8e5317dad 2026-02-15.  The commit 3cae24cf99da1702b851b5a74a9b88c8e5317dad was however development done on the wrong branch and has been force-pushed awway.  It was again observed ungraceful at commits be26d42b1ca3ff3b4fd183761b4a9b024ce12b84 / 537a23b145487006bb987dee5ab9e00cdebb0492
    'search.comp-type.optional': {'support': 'ungraceful'},
    'search.recurrences.expanded.todo': {'support': 'unsupported'},
    'search.recurrences.expanded.exception': {'support': 'unsupported'}, ## TODO: verify
    "search.recurrences.includes-implicit.infinite-scope": False,
    'delete-calendar': {
        'support': 'fragile',
        'behaviour': 'Deleting a recently created calendar fails'},
    'delete-calendar.free-namespace': { ## TODO: not caught by server-tester
        'behaviour': "deleting a calendar moves it to a trashbin, thrashbin has to be manually 'emptied' from the web-ui before the namespace is freed up",
        'support': 'fragile',
    },
    'search.recurrences.includes-implicit.todo': {'support': 'unsupported'},
    #'save-load.todo.mixed-calendar': {'support': 'unsupported'}, ## Why?  It started complaining about this just recently.
    'principal-search.by-name.self': {'support': 'unsupported'},
    'principal-search': {'support': 'ungraceful'},
    'search.time-range.open.start.duration': 'broken',
    #'old_flags': ['unique_calendar_ids'],
    ## I'm surprised, I'm quite sure this was passing earlier.  Caldav commit a98d50490b872e9b9d8e93e2e401c936ad193003, caldav server checker commit 3cae24cf99da1702b851b5a74a9b88c8e5317dad
    'search.combined-is-logical-and': False,
    ## Observed with Nextcloud 33: server delivers iTIP notification to the inbox AND
    ## auto-schedules into the attendee's calendar.
    'scheduling.schedule-tag': False,
}

## TODO: Latest - mismatch between config and test script in delete-calendar.free-namespace ... and create-calendar.set-displayname?
ecloud = nextcloud | {
    #'search.is-not-defined': {'support': 'unsupported'}, ## observed to work at 4bc0de765a2b53e6f223e0b9ac51c653bac11fb7 (caldav) / 3cae24cf99da1702b851b5a74a9b88c8e5317dad (server checker)
    #'search.text.case-sensitive': {'support': 'unsupported'}, ## observed to work at 4bc0de765a2b53e6f223e0b9ac51c653bac11fb7 (caldav) / 3cae24cf99da1702b851b5a74a9b88c8e5317dad (server checker)
    ## TODO: this applies only to test runs, not to ordinary usage
    'rate-limit': {
        'enable': True,
        'interval': 2,
        'count': 1,
        'default_sleep': 4,
        'max_sleep': 120,
        'description': "It's needed to manually empty trashbin frequently when running tests.  Since this operation takes some time and/or there are some caches, it's needed to run tests slowly, even when hammering the 'empty thrashbin' frequently",
    },
    'auto-connect.url': {
        'basepath': '/remote.php/dav',
        'domain': 'ecloud.global',
        'scheme': 'https',
    },
}

## Zimbra is not very good at it's caldav support
zimbra = {
    'auto-connect.url': {'basepath': '/dav/'},
    'delete-calendar': {'support': 'fragile', 'behaviour': 'may move to trashbin instead of deleting immediately'},
    'save-load.get-by-url': {'support': 'fragile', 'behaviour': '404 most of the time - but sometimes 200.  Weird, should be investigated more'},
    ## Zimbra treats same-UID events across calendars as aliases of the same event
    'save.duplicate-uid.cross-calendar': {'support': 'unsupported'},
    'search.recurrences.expanded.exception': {'support': 'unsupported'}, ## TODO: verify
    'create-calendar.set-displayname': {'support': 'unsupported'},
    'save-load.todo.mixed-calendar': {'support': 'unsupported'},
    'save-load.todo.recurrences.count': {'support': 'unsupported'}, ## This is a new problem?
    'save-load.journal': {'support': 'ungraceful'},
    'sync-token': {'support': 'fragile'},
    'search.is-not-defined': {'support': 'unsupported'},
    'search.text': {'support': 'unsupported'},
    "search.recurrences.includes-implicit.infinite-scope": False,
    # sometimes throws a 500
    'search.text.category': {'support': 'ungraceful'},
    'search.recurrences.expanded.todo': { "support": "unsupported" },
    'search.comp-type.optional': {'support': 'fragile'}, ## TODO: more research on this, looks like a bug in the checker,
    'search.time-range.alarm': {'support': 'unsupported'},
    'principal-search': "unsupported",
    ## Zimbra implements server-side automatic scheduling: invitations are
    ## auto-processed into the attendee's calendar; no iTIP notification appears in the inbox.
    ## TODO: auto-scheduling did not work in the last test?  Check more around it
    #"scheduling.mailbox.inbox-delivery": False,
    "scheduling.schedule-tag": False,
    'save-load.icalendar.related-to': {'support': 'unsupported'},
    'search.time-range.open.start': {'support': 'broken'},

    "old_flags": [
    ## setting display name in zimbra does not work (display name,
    ## calendar-ID and URL is the same, the display name cannot be
    ## changed, it can only be given if no calendar-ID is given.  In
    ## earlier versions of Zimbra display-name could be changed, but
    ## then the calendar would not be available on the old URL
    ## anymore)
    ## 'event_by_url_is_broken' removed - works in zimbra/zcs-foss:latest
    'vtodo_datesearch_notime_task_is_skipped',

    ## TODO: I just discovered that when searching for a date some
    ## years after a recurring daily event was made, the event does
    ## not appear.

    ## extra features not specified in RFC5545
    "calendar_order",
    "calendar_color"
    ]
}

bedework = {
    ## If tests are yielding unexpected results, try to increase this:
    'search-cache': {'behaviour': 'delay', 'delay': 3},
    'scheduling.auto-schedule': {'support': 'unknown'},
    'scheduling.calendar-user-address-set': {'support': 'full'},
    'scheduling.freebusy-query': {'support': 'full'},
    'scheduling.mailbox': {'support': 'full'},
    'scheduling.mailbox.inbox-delivery': {'support': 'unsupported'},
    'scheduling.schedule-tag': {'support': 'full'},

    'test-calendar': {'cleanup-regime': 'wipe-calendar'},
    'auto-connect.url': {'basepath': '/ucaldav/'},
    'save-load.journal': {'support': 'ungraceful'},
    'save-load.todo.recurrences.thisandfuture': {'support': 'ungraceful'},
    'save-load.event.recurrences.exception': False,
    'search.time-range.alarm': {'support': 'unsupported'},
    "freebusy-query": True,
    "search.time-range.todo": False,
    "search.text": False, ## sometimes ungraceful
    "search.recurrences.includes-implicit": False,
    "sync-token": { "support": "fragile" },
    "search.recurrences.expanded.exception": False,
    "search.recurrences.expanded.event": False,
    "search.recurrences.expanded.todo": False,
    'search.comp-type': {'support': 'broken', 'behaviour': 'Server returns everything when searching for events and nothing when searching for todos'},
    'search.comp-type.optional': {'support': 'ungraceful'},
    'search.is-not-defined.dtend': False,
    "principal-search": {  "support": "ungraceful" },
    ## Bedework hides past non-recurring events from REPORT without a time-range filter,
    ## but still returns recurring events that have future occurrences.  The unlimited-time-range
    ## check probe is a past-only non-recurring event; it is not returned even though the
    ## PrepareCalendar recurring event (RRULE:FREQ=MONTHLY since 2000) is returned.
    ## Result: objects is non-empty but the probe event is absent → "broken".
    #"search.unlimited-time-range": {"support": "broken"},
    ## Bedework uses a pre-built Docker image with no easy way to add users, so
    ## cross-user scheduling tests cannot be run; inbox-delivery behaviour is unknown.
    ## (not expected to be working though)
    "scheduling": {"support": "unknown"},

    ## TODO: play with this and see if it's needed
    'save-load.icalendar.related-to': {'support': 'broken', 'behaviour': 'first RELATED-TO line is preserved but subsequent RELATED-TO lines are stripped'},
    'old_flags': [
    'propfind_allprop_failure',
    'duplicates_not_allowed',
    ],

}

synology = {
    'principal-search': False,
    'sync-token': 'fragile',
    'delete-calendar': False,
    'search.comp-type.optional': 'fragile',
    'search.is-not-defined': {'support': 'fragile', 'behaviour': 'works for CLASS but not for CATEGORIES'},
    'search.text.case-sensitive': {'support': 'unsupported'},
    'search.time-range.alarm': {'support': 'unsupported'},
    "search.recurrences.expanded.exception": False,
    'old_flags': ['vtodo_datesearch_nodtstart_task_is_skipped'],
    'test-calendar': {'cleanup-regime': 'wipe-calendar'},
}

baikal =  { ## version 0.10.1
    # Baikal (sabre/dav) delivers iTIP notifications to the attendee inbox AND auto-schedules
    # into their calendar.
    "scheduling.schedule-tag": False,
    "http.multiplexing": "fragile", ## ref https://github.com/python-caldav/caldav/issues/564
    'search.comp-type.optional': {'support': 'ungraceful'},
    'search.recurrences.expanded.todo': {'support': 'unsupported'},
    'search.recurrences.expanded.exception': {'support': 'unsupported'},
    'search.recurrences.includes-implicit.todo': {'support': 'unsupported'},
    "search.recurrences.includes-implicit.infinite-scope": False,
    'save-load.journal.mixed-calendar': {'support': 'unsupported'},
    'principal-search': {'support': 'ungraceful'},
    'principal-search.by-name.self': {'support': 'unsupported'},
    'principal-search.list-all': {'support': 'ungraceful'},
    #'sync-token.delete': {'support': 'unsupported'}, ## Perhaps on some older servers?
    'old_flags': [
        ## extra features not specified in RFC5545
        "calendar_order",
        "calendar_color",
    ],
    ## I'm surprised, I'm quite sure this was passing earlier.  Caldav commit a98d50490b872e9b9d8e93e2e401c936ad193003, caldav server checker commit 3cae24cf99da1702b851b5a74a9b88c8e5317dad
    'search.combined-is-logical-and': False
} ## TODO: testPrincipals, testWrongAuthType, testTodoDatesearch fails

## Some unknown version of baikal has this
baikal_old = baikal | {
    'create-calendar': {'support': 'quirk', 'behaviour': 'mkcol-required'},
    'create-calendar.auto': {'support': 'unsupported'}, ## this is the default, but the "quirk" from create-calendar overwrites it.  Hm.
}

cyrus = {
    "search.comp-type.optional": {"support": "ungraceful"},
    "search.recurrences.expanded.exception": {"support": "unsupported"},
    "search.recurrences.includes-implicit.infinite-scope": False,
    "search.time-range.alarm": {"support": "ungraceful"},
    'principal-search': {'support': 'ungraceful'},
    # Cyrus enforces unique UIDs across all calendars for a user
    "save.duplicate-uid.cross-calendar": {"support": "ungraceful"},
    # Ephemeral Docker container: wipe objects but keep calendar (avoids UID conflicts)
    "test-calendar": {"cleanup-regime": "wipe-calendar"},
    'delete-calendar': {
        'support': 'fragile',
        'behaviour': 'Deleting a recently created calendar fails'},
    # Cyrus changes the Schedule-Tag even on attendee PARTSTAT-only updates,
    # violating RFC6638 section 3.2 which requires the tag to remain stable.
    "scheduling.schedule-tag.stable-partstat": {"support": "unsupported"},
    # Cyrus may not properly reject wrong passwords in some configurations
    # Cyrus implements server-side automatic scheduling: for cross-user invites,
    # the server both auto-processes the invite into the attendee's calendar
    # AND delivers an iTIP notification copy to the attendee's schedule-inbox.
}

## See comments on https://github.com/python-caldav/caldav/issues/3
#icloud = [
#    'unique_calendar_ids',
#    'duplicate_in_other_calendar_with_same_uid_breaks',
#    'sticky_events',
#    'no_journal', ## it threw a 500 internal server error!
#    'no_todo',
#    "no_freebusy_rfc4791",
#    'no_recurring',
#    'propfind_allprop_failure',
#    'get_object_by_uid_is_broken'
#]

davical = {
    # Disable HTTP/2 multiplexing - davical doesn't support it well and niquests
    # lazy responses cause MultiplexingError when accessing status_code
    "http.multiplexing": { "support": "unsupported" },
    # DAViCal delivers iTIP notifications to the attendee inbox AND auto-schedules
    # into their calendar.
    "scheduling.schedule-tag": False,
    "search.comp-type.optional": { "support": "fragile" },
    "search.recurrences.expanded.exception": { "support": "unsupported" },
    "search.time-range.alarm": { "support": "unsupported" },
    'sync-token': {'support': 'fragile'},
    'principal-search': {'support': 'unsupported'},
    'principal-search.list-all': {'support': 'unsupported'},
    "old_flags": [
        #'no_journal', ## it threw a 500 internal server error! ## for old versions
        #'nofreebusy', ## for old versions
        ## 'fragile_sync_tokens' removed - covered by 'sync-token': {'support': 'fragile'}
        'vtodo_datesearch_nodtstart_task_is_skipped', ## no issue raised yet
        'calendar_color',
        'calendar_order',
        'vtodo_datesearch_notime_task_is_skipped',
    ],
}

sogo = {
    "scheduling.schedule-tag": False,
    "scheduling.mailbox.inbox-delivery": False,
    ## I'm surprised, I'm quite sure this was passing earlier.  reported unsupported with caldav commit a98d50490b872e9b9d8e93e2e401c936ad193003, caldav server checker commit 3cae24cf99da1702b851b5a74a9b88c8e5317dad 2026-02-15
    "search.text.category": False,
    "search.time-range.event.old-dates": False,
    "search.time-range.todo.old-dates": False,
    "save-load.journal": {"support": "ungraceful"},
    "search.is-not-defined": {"support": "unsupported"},
    "search.text.case-sensitive": {
        "support": "unsupported"
    },
    "search.text.case-insensitive": {
        "support": "unsupported"
    },
    "search.time-range.alarm": {
        "support": "unsupported"
    },
    ## was unsupported.  reported ungraceful with caldav commit a98d50490b872e9b9d8e93e2e401c936ad193003, caldav server checker commit 3cae24cf99da1702b851b5a74a9b88c8e5317dad 2026-02-15
    "search.comp-type.optional": {
        "support": "ungraceful"
    },
    ## includes-implicit.todo has been observed as both supported and unsupported
    ## across different test runs.  Other includes-implicit children are unsupported.
    ## Marking the parent as fragile to avoid cascading derivation issues.
    "search.recurrences.includes-implicit": {
        "support": "fragile"
    },
    "sync-token": {
        "support": "fragile"
    },
    "search.recurrences.expanded": {
        "support": "unsupported"
    },
    ## unsupported earlier, ungraceful at be26d42b1ca3ff3b4fd183761b4a9b024ce12b84 / 537a23b145487006bb987dee5ab9e00cdebb0492
    "freebusy-query": {"support": "ungraceful"},
    "principal-search": {
        "support": "ungraceful",
        "behaviour": "Search by name failed: ReportError at '501 Not Implemented - <?xml version=\"1.0\" encoding=\"ISO-8859-1\"?>\n<html xmlns=\"http://www.w3.org/1999/xhtml\">\n<body><h3>An error occurred during object publishing</h3><p>did not find the specified REPORT</p></body>\n</html>\n', reason no reason",
    },
    # Ephemeral Docker container: wipe objects (delete-calendar fragile)
    'test-calendar': {'cleanup-regime': 'wipe-calendar'},

}
## Old notes for sogo (todo - incorporate them in the structure above)
## https://www.sogo.nu/bugs/view.php?id=3065
## left a note about time-based sync tokens on https://www.sogo.nu/bugs/view.php?id=5163
## https://www.sogo.nu/bugs/view.php?id=5282
## https://bugs.sogo.nu/view.php?id=5693
## https://bugs.sogo.nu/view.php?id=5694
#sogo = [ ## and in addition ... the requests are efficiently rate limited, as it spawns lots of postgresql connections all until it hits a limit, after that it's 501 errors ...
#    "time_based_sync_tokens",
#    "search_needs_comptype",
#    "fastmail_buggy_noexpand_date_search",
#    "text_search_not_working",
#    "isnotdefined_not_working",
#    'no_journal',
#    'no_freebusoy_rfc4791'
#]



#google = [
#    'no_mkcalendar',
#    'no_overwrite',
#    'no_todo',
#]

#fastmail = [
#    'duplicates_not_allowed',
#    'duplicate_in_other_calendar_with_same_uid_breaks',
#    'no_todo',
#    'sticky_events',
#    'fastmail_buggy_noexpand_date_search',
#    'combined_search_not_working',
#    'text_search_is_exact_match_sometimes',
#    'rrule_takes_no_count',
#    'isnotdefined_not_working',
#]

robur = {
    "auto-connect.url": {
        'domain': 'calendar.robur.coop',
        'basepath': '/principals/', # TODO: this seems fishy
    },
    "save-load.journal": { "support": "ungraceful" },
    "delete-calendar": { "support": "unsupported" },
    "search.is-not-defined": { "support": "unsupported" },
    "search.time-range.todo": { "support": "unsupported" },
    "search.time-range.alarm": {'support': 'unsupported'},
    "search.text": { "support": "unsupported", "behaviour": "a text search ignores the filter and returns all elements" },
    "search.comp-type.optional": { "support": "ungraceful" },
    "search.recurrences.expanded.todo": { "support": "unsupported" },
    "search.recurrences.expanded.event": { "support": "fragile" },
    "search.recurrences.expanded.exception": { "support": "unsupported" },
    'search.recurrences.includes-implicit.todo': {'support': 'unsupported'},
    'principal-search': {'support': 'ungraceful'},
    'freebusy-query': {'support': 'ungraceful'},
    "scheduling": {"support": "unsupported"},
    'old_flags': [
        'non_existing_raises_other', ## AuthorizationError instead of NotFoundError
    ],
    'save-load.icalendar.related-to': {'support': 'unsupported'},
    'test-calendar': {'cleanup-regime': 'wipe-calendar'},
    "sync-token": {"support": "ungraceful"},
    "get-supported-components": {"support": "unsupported"},
}

posteo = {
    'auto-connect.url': {
        'scheme': 'https',
        'domain': 'posteo.de:8443',
        'basepath': '/',
    },
    'create-calendar': {'support': 'unsupported'},
    'save-load.journal': {'support': 'unsupported'},
    ## TODO1: we should ignore cases where observations are unknown while configuration is known
    ## TODO2: there are more calendars available at the posteo account, so it should be possible to check this.
    "save.duplicate-uid.cross-calendar": { "support": "unknown" },
    ## foo ... "full" observed for the next two, 70938dc1cbb6a839978eee4315699746d38ee5f0/3cae24cf99da1702b851b5a74a9b88c8e5317dad, 2026-02-17
    ## bar ... 3cae24cf99da1702b851b5a74a9b88c8e5317dad was probably the rotten commit, ungraceful again in  be26d42b1ca3ff3b4fd183761b4a9b024ce12b84 / 537a23b145487006bb987dee5ab9e00cdebb0492
    'search.comp-type.optional': {'support': 'ungraceful'},
    #'search.text.case-sensitive': {'support': 'unsupported'},
    ## Comment from claude:
    ## Text search precondition check returns unexpected results on posteo
    ## (possibly stale data on non-deletable calendar), so substring support
    ## cannot be reliably determined.
    ## perhaps the stale data was deleted, because "full" observed, 70938dc1cbb6a839978eee4315699746d38ee5f0/3cae24cf99da1702b851b5a74a9b88c8e5317dad, 2026-02-17
    #'search.text.substring': {'support': 'unknown'},
    ## search.time-range.todo was previously unsupported on posteo but
    ## is now observed as working for recent dates (as of 2026-02).
    ## Old dates (year 2000) still don't work.
    ## foo ... "full" observed, 70938dc1cbb6a839978eee4315699746d38ee5f0/3cae24cf99da1702b851b5a74a9b88c8e5317dad, 2026-02-17
    #'search.time-range.todo.old-dates': {'support': 'unsupported'},
    'search.recurrences.expanded.todo': {'support': 'unsupported'},
    'search.recurrences.expanded.exception': {'support': 'unsupported'},
    'search.recurrences.includes-implicit.todo': {'support': 'unsupported'},
    'search.combined-is-logical-and': {'support': 'unsupported'},
    'sync-token': {'support': 'ungraceful'},
    'principal-search': {'support': 'unsupported'},
    "scheduling": {"support": "unsupported"},
}

#calendar_mail_ru = [
#    'no_mkcalendar', ## weird.  It was working in early June 2024, then it stopped working in mid-June 2024.
#    'no_current-user-principal',
#    'no_todo',
#    'no_journal',
#    'search_always_needs_comptype',
#    'no_sync_token', ## don't know if sync tokens are supported or not - the sync-token-code needs some workarounds ref https://github.com/python-caldav/caldav/issues/401
#    'text_search_not_working',
#    'isnotdefined_not_working',
#    'no_scheduling_mailbox',
#    'no_freebusy_rfc4791',
#    'no_relships', ## mail.ru recreates the icalendar content, and strips everything it doesn't know anyhting about, including relationship info
#]

## Davis uses sabre/dav (same backend as Baikal), so hints are similar.
## TODO: consolidate, make a sabredav dict and let davis/baikal build on it
davis = {
    # Davis uses sabre/dav (same backend as Baikal): delivers iTIP notifications to the
    # attendee inbox AND auto-schedules into their calendar.
    "scheduling.schedule-tag": False,
    "search.recurrences.expanded.todo": {"support": "unsupported"},
    "search.recurrences.expanded.exception": {"support": "unsupported"},
    "search.recurrences.includes-implicit.todo": {"support": "unsupported"},
    "search.recurrences.includes-implicit.infinite-scope": False,
    "principal-search.by-name.self": {"support": "unsupported"},
    "principal-search": {"support": "ungraceful"},
    "save-load.journal.mixed-calendar": {"support": "unsupported"},
    "search.comp-type.optional": {"support": "ungraceful"},
    "old_flags": [
        "calendar_order",
        "calendar_color",
    ],
    ## I'm surprised, I'm quite sure this was passing earlier.  Caldav commit a98d50490b872e9b9d8e93e2e401c936ad193003, caldav server checker commit 3cae24cf99da1702b851b5a74a9b88c8e5317dad
    'search.combined-is-logical-and': False
}

## Apple CalendarServer (CCS) - archived 2019, Python 2/Twisted.
## MKCALENDAR always creates VEVENT-only calendars; supported-calendar-component-set
## cannot be changed.  The pre-provisioned "tasks" calendar supports VTODO only.
## VJOURNAL is not supported at all.
ccs = {
    "scheduling.freebusy-query": {"support": "ungraceful"},
    "scheduling.mailbox.inbox-delivery": True,
    "scheduling.auto-schedule": True,
    "scheduling.schedule-tag.stable-partstat": {"support": "unsupported"},
    "save-load.journal": {"support": "unsupported"},
    "save-load.todo.mixed-calendar": {"support": "unsupported"},
    # CCS enforces unique UIDs across ALL calendars for a user
    #"save.duplicate-uid.cross-calendar": {"support": "unsupported"},
    ## "unsupported" observed earlier.  "ungraceful" at  be26d42b1ca3ff3b4fd183761b4a9b024ce12b84 / 537a23b145487006bb987dee5ab9e00cdebb0492 2026-02-19.
    "save.duplicate-uid.cross-calendar": {"support": "ungraceful"},
    # CCS rejects multi-instance VTODOs (thisandfuture recurring completion)
    "save-load.todo.recurrences.thisandfuture": {"support": "unsupported"},
    "search.comp-type.optional": {"support": "ungraceful"},
    ## "full" observed, 70938dc1cbb6a839978eee4315699746d38ee5f0/3cae24cf99da1702b851b5a74a9b88c8e5317dad, 2026-02-17.
    ## However, this may be due to mess with the caldav-server-checker branches.  "unsupported" again at be26d42b1ca3ff3b4fd183761b4a9b024ce12b84 / 537a23b145487006bb987dee5ab9e00cdebb0492
    "search.text.case-sensitive": {"support": "unsupported"},
    "search.time-range.event": {"support": "full"},
    "search.time-range.event.old-dates": {"support": "ungraceful"},
    "search.time-range.todo": {"support": "full"},
    "search.time-range.todo.old-dates": {"support": "ungraceful"},
    "search.time-range.open": {"support": "ungraceful"},
    "search.time-range.alarm": {"support": "unsupported"},
    "search.recurrences": {"support": "unsupported"},
    "principal-search": {"support": "unsupported"},
    # Ephemeral Docker container: wipe objects (avoids UID conflicts across calendars)
    "test-calendar": {"cleanup-regime": "wipe-calendar"},
    ## Did pass earlier, ungraceful at be26d42b1ca3ff3b4fd183761b4a9b024ce12b84 / 537a23b145487006bb987dee5ab9e00cdebb0492
    'freebusy-query': {'support': 'ungraceful'},
    "old_flags": [
        "propfind_allprop_failure",
    ],
}

## Stalwart - all-in-one mail & collaboration server (CalDAV added 2024/2025)
## https://stalw.art/
## CalDAV served at /dav/cal/<username>/ over HTTP on port 8080.
## Feature support mostly unknown until tested; starting with empty hints.
stalwart = {
    'rate-limit': {
        'enable': True,
        'default_sleep': 3,
        'max_sleep': 60
    },
    'create-calendar.auto': True,
    'principal-search': {'support': 'ungraceful'},
    'search.time-range.alarm': False,
    ## Stalwart supports implicit recurrence for datetime events but not for
    ## all-day (VALUE=DATE) recurring events in time-range searches.
    'search.recurrences.includes-implicit.event': {'support': 'fragile', 'behaviour': 'broken for all-day (VALUE=DATE) events'},
    ## Stalwart returns the recurring todo in search results but doesn't return the
    ## RRULE intact, so client-side expansion can't expand it to specific occurrences.
    'search.recurrences.includes-implicit.todo': {'support': 'fragile'},
    ## Stalwart doesn't handle exceptions properly in server-side CALDAV:expand:
    ## returns 3 items instead of 2 for a recurring event with one exception
    ## (the exception is stored as a separate object and returned twice).
    'search.recurrences.expanded.exception': False,
    ## Stalwart stores master+exception VEVENTs as a single resource with 2 VEVENTs.
    'save-load.event.recurrences.exception': {'support': 'full'},
    'search.time-range.open': True,
    ## Stalwart delivers iTIP notifications to the attendee inbox AND auto-schedules
    ## into their calendar (verified by running CheckSchedulingInboxDelivery).
    "scheduling.mailbox.inbox-delivery": True,
    "scheduling.auto-schedule": True,
    'old_flags': [
        ## Stalwart does not return VTODO items without DTSTART in date searches
        'vtodo_datesearch_nodtstart_task_is_skipped',
    ],
}

## Lots of transient problems with purelymail
purelymail = {
    ## Purelymail claims that the search indexes are "lazily" populated,
    ## so search works some minutes after the event was created/edited.
    'search-cache': {'behaviour': 'delay', 'delay': 180},
    #'search-cache': {'behaviour': 'delay', 'delay': 0.3},
    ## Hmmm .... weird, this is flapping in the caldav-server-tester?
    "create-calendar.auto": {"support": "full"},
    ## 409 Conflict with <must-have-parent> when PUTting to a URL not under an existing calendar
    #'save-load.get-by-url': {'support': 'unknown'},
    #'save-load.todo': {'support': 'ungraceful'},
    'search.comp-type.optional': {'support': 'unsupported'},
    ## The search features below are unreliable on purelymail, likely due
    ## to the 160s search-cache delay.  Results flip between unsupported
    ## and ungraceful across runs.  Marked fragile so the checker skips them.
    ## was: (default, i.e. full) - observed ungraceful 2026-02
    'search.is-not-defined': {'support': 'fragile'},
    'search.time-range.alarm': {'support': 'unsupported'},
    ## was: unsupported - observed ungraceful 2026-02
    'search.time-range.event': {'support': 'fragile'},
    ## was: ungraceful - observed unsupported 2026-02 (for .old-dates)
    'search.time-range.todo': {'support': 'fragile'},
    'search.recurrences.expanded.exception': {'support': 'unsupported'},
    'principal-search': {'support': 'ungraceful'},
    'principal-search.by-name.self': {'support': 'ungraceful'},
    'principal-search.list-all': {'support': 'ungraceful'},
    'auto-connect.url': {
        'basepath': '/webdav/',
        'domain': 'purelymail.com',
    },
    ## Known, work in progress
    "scheduling": {"support": "unsupported"},
    ## Known, not a breach of standard
    "get-supported-components": {"support": "unsupported"},
}

gmx = {
    'auto-connect.url': {
        'scheme': 'https',
        'domain': 'caldav.gmx.net',
        'basepath': '/begenda/dav/{username}/',
    },
    'rate-limit': {
        'enable': True,
        'interval': 2,
        'count': 1,
        'default_sleep': 4,
        'max_sleep': 30
    },
    'search.comp-type.optional': {'support': 'fragile', 'description': 'unexpected results from date-search without comp-type - but only sometimes - TODO: research more'},
    'search.recurrences.expanded': {'support': 'unsupported'},
    ## TODO: flapping between ungraceful and unsupported?
    #'search.text.case-sensitive': {'support': 'ungraceful'},
    'search.text.case-sensitive': {'support': 'unsupported'},
    ## TODO: flapping between supported and unsupported?
    #'search.text.case-insensitive': {'support': 'unsupported'},
    ## TODO: flapping between unsupported and ungraceful?
    #'sync-token': {'support': 'unsupported'},
    'sync-token': {'support': 'ungraceful'},
    'principal-search': {'support': 'ungraceful'},
    'principal-search.by-name.self': {'support': 'unsupported'},
    ## TODO: flapping ...?
    #'freebusy-query': {'support': 'unsupported'},
    'freebusy-query': {'support': 'ungraceful'},
    ## flapping ...?
    #'search.is-not-defined.category': {'support': 'unsupported'},
    ## flapping ...?
    #'search.is-not-defined.dtend': {'support': 'unsupported'},
    'create-calendar': {'support': 'unknown' }, ## https://github.com/python-caldav/caldav/issues/624
    ## was apparently observed working for a while, possibly due to the master/more_checks split-brain git branching incident in the server-checker project.
    ## unsupported in be26d42b1ca3ff3b4fd183761b4a9b024ce12b84 / 537a23b145487006bb987dee5ab9e00cdebb0492 2026-02-19.  Supported when testing again short time after.  Either I'm confused or it's "fragile".
    #'search.time-range.alarm': {'support': 'unsupported'},
    ## GMX advertises calendar-auto-schedule but inbox/mailbox and
    ## calendar-user-address-set are not functional (RFC6638 sub-features).
    "scheduling": {"support": "full"},
    "scheduling.mailbox": {"support": "unsupported"},
    "scheduling.calendar-user-address-set": {"support": "unsupported"},
    ## GMX does not return results for open-end date searches (only start given)
    'search.time-range.open.end': {'support': 'unsupported'},
    "old_flags":  [
        #"text_search_is_case_insensitive",
        "vtodo-cannot-be-uncompleted",
    ]
}

## https://www.open-xchange.com/
## OX App Suite CalDAV served at /caldav/ (Apache proxies to /servlet/dav/caldav on port 8009).
## The Docker image must be built locally before use (see tests/docker-test-servers/ox/build.sh).
ox = {
    ## Renaming a calendar after creation via PROPPATCH is not supported
    'create-calendar.set-displayname': {'support': 'unsupported'},
    ## VTODOs must be in a dedicated VTODO-only calendar; mixed calendars not supported
    'save-load.todo.mixed-calendar': {'support': 'unsupported'},
    ## Basic VTODO support works fine; only recurrences are broken
    'save-load.todo': {'support': 'full'},
    ## Recurring VTODOs (RRULE in VTODO) are rejected with 400
    'save-load.todo.recurrences': {'support': 'ungraceful'},
    ## VJOURNAL is not supported
    'save-load.journal': {'support': 'unsupported'},
    ## Search limitations
    'search.time-range.event.old-dates': {'support': 'unsupported'},
    'search.time-range.todo.old-dates': {'support': 'unsupported'},
    'search.time-range.alarm': {'support': 'unsupported'},
    'search.unlimited-time-range': {'support': 'broken'},
    'search.comp-type.optional': {'support': 'ungraceful'},
    'search.text': {'support': 'unsupported'},
    'search.text.category': {'support': 'unsupported'},
    'search.text.case-sensitive': {'support': 'unsupported'},
    'search.text.case-insensitive': {'support': 'unsupported'},
    ## Recurrence searching broken (sliding window + old-dates limitation)
    'search.recurrences.includes-implicit': {'support': 'unsupported'},
    'search.recurrences.includes-implicit.todo.pending': {'support': 'unsupported'},
    'search.recurrences.expanded': {'support': 'unsupported'},
    ## is-not-defined for DTEND is not supported
    'search.is-not-defined.dtend': {'support': 'unsupported'},
    ## Freebusy queries are not supported (returns 400)
    'freebusy-query': {'support': 'ungraceful'},
    ## Principal search not supported
    'principal-search': {'support': 'unsupported'},
    'principal-search.by-name.self': {'support': 'unsupported'},
    'principal-search.list-all': {'support': 'unsupported'},
    ## Cross-calendar duplicate UID test fails (AuthorizationError creating second calendar)
    'save.duplicate-uid.cross-calendar': {'support': 'ungraceful'},
    'save-load.icalendar.related-to': {'support': 'broken'},
    ## OX App Suite has complex user provisioning; cross-user scheduling tests not yet set up.
    "scheduling": {"support": "unknown"},
    "scheduling.freebusy-query": "ungraceful",
    'search.time-range.open.start': "broken",
    'search.time-range.open.end': True,
    ## time-range.open is "broken", while time-range.open.start.duration is "unsupported"?
    ## this may possibly be some problems with the checker rather than with Ox
    'search.time-range.open.start.duration': "unsupported"
}

# fmt: on
