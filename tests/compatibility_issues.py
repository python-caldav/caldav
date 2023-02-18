# fmt: off
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
    'no_expand':
        """Server may throw errors when asked to do a expanded date search (this is ignored by the tests now, as we're doing client-side expansion)""",

    'no_recurring':
        """Server is having issues with recurring events and/or todos. """
        """date searches covering recurrances may yield no results, """
        """and events/todos may not be expanded with recurrances""",

    'no_recurring_expandation':
        """Server will not expand recurring events (this is ignored by the tests now, as we're doing client-side expansion)""",

    'no_recurring_todo':
        """Recurring events are supported, but not recurring todos""",

    'no_recurring_todo_expand':
        """Recurring todos aren't expanded (this is ignored by the tests now, as we're doing client-side expansion)""",

    'no_scheduling':
        """RFC6833 is not supported""",

    'no_default_calendar':
        """The given user starts without an assigned default calendar """
        """(or without pre-defined calendars at all)""",

    'non_existing_calendar_found':
        """Server will not yield a 404 when accessing a random calendar URL """
        """(perhaps the calendar will be automatically created on access)""",

    'no_freebusy_rfc4791':
        """Server does not support a freebusy-request as per RFC4791""",

    'no_freebusy_rfc6638':
        """Server does not support a freebusy-request as per RFC6638""",

    'calendar_order':
        """Server supports (nonstandard) calendar ordering property""",

    'calendar_color':
        """Server supports (nonstandard) calendar color property""",

    'no_journal':
        """Server does not support journal entries""",

    'no_displayname':
        """The display name of a calendar cannot be set/changed """
        """(in zimbra, display name is given from the URL)""",

    'duplicates_not_allowed':
        """Duplication of an event in the same calendar not allowed """
        """(even with different uid)""",

    'duplicate_in_other_calendar_with_same_uid_is_lost':
        """Fetch an event from one calendar, save it to another ... """
        """and the duplicate will be ignored""",

    'duplicate_in_other_calendar_with_same_uid_breaks':
        """Fetch an event from one calendar, save it to another ... """
        """and get some error from the server""",

    'event_by_url_is_broken':
        """A GET towards a valid calendar object resource URL will yield 404 (wtf?)""",

    'no_sync_token':
        """RFC6578 is not supported, things will break if we try to do a sync-token report""",

    'time_based_sync_tokens':
        """A sync-token report depends on the unix timestamp, """
        """several syncs on the same second may cause problems, """
        """so we need to sleep a bit. """
        """(this is a neligible problem if sync returns too much, but may be """
        """disasterously if it returns too little). """,

    'fragile_sync_tokens':
        """Every now and then (or perhaps always), more content than expected """
        """will be returned on a simple sync request.  Possibly a race condition """
        """if the token is timstamp-based?""",

    'sync_breaks_on_delete':
        """I have observed a calendar server (sabre-based) that returned """
        """418 I'm a teapot """
        """when requesting updates on a calendar after some calendar resource """
        """object was deleted""",

    'propfind_allprop_failure':
        """The propfind test fails ... """
        """it asserts DAV:allprop response contains the text 'resourcetype', """
        """possibly this assert is wrong""",

    'no_todo':
        """Support for VTODO (tasks) apparently missing""",

    'no_todo_datesearch':
        """Date search on todo items fails""",

    'vtodo_datesearch_nodtstart_task_is_skipped':
        """date searches for todo-items will not find tasks without a dtstart""",

    'vtodo_datesearch_nodtstart_task_is_skipped_in_closed_date_range':
        """only open-ended date searches for todo-items will find tasks without a dtstart""",

    'vtodo_datesearch_notime_task_is_skipped':
        """date searches for todo-items will (only) find tasks that has either """
        """a dtstart or due set""",

    'vtodo_no_due_infinite_duration':
        """date search will find todo-items without due if dtstart is """
        """before the date search interval.  I didn't find anything explicit """
        """in The RFC on this (), but an event should be considered to have 0 """
        """duration if no dtend is set, and most server implementations seems to """
        """treat VTODOs the same""",

    'no_todo_on_standard_calendar':
        """Tasklists can be created, but a normal calendar does not support tasks""",

    'unique_calendar_ids':
        """For every test, generate a new and unique calendar id""",

    'sticky_events':
        """Events should be deleted before the calendar is deleted, """
        """and/or deleting a calendar may not have immediate effect""",

    'object_by_uid_is_broken':
        """calendar.object_by_uid(uid) does not work""",

    'no_mkcalendar':
        """mkcalendar is not supported""",

    'no_overwrite':
        """events cannot be edited""",

    'dav_not_supported':
        """when asked, the server may claim it doesn't support the DAV protocol.  Observed by one baikal server, should be investigated more (TODO) and robur""",

    'category_search_yields_nothing':
        """When querying for a text match report over fields like the category field, server returns nothing""",

    'text_search_is_case_insensitive':
        """Probably not supporting the collation used by the caldav library""",

    'text_search_is_exact_match_only':
        """Searching for 'CONF' i.e. in the class field will not yield CONFIDENTIAL.  Which generally makes sense, but the RFC specifies substring match""",

    'text_search_is_exact_match_sometimes':
        """Some servers are doing an exact match on summary field but substring match on category or vice versa""",

   'combined_search_not_working':
        """When querying for a text match and a date range in the same report, weird things happen""",

   'text_search_not_working':
        """Text search is generally broken""",

   'radicale_breaks_on_category_search':
        """See https://github.com/Kozea/Radicale/issues/1125""",

   'fastmail_buggy_noexpand_date_search':
        """The 'blissful anniversary' recurrent example event is returned when asked for a no-expand date search for some timestamps covering a completely different date""",

    'non_existing_raises_other':
        """Robur raises AuthorizationError when trying to access a non-existing resource (while 404 is expected).  Probably so one shouldn't probe a public name space?""",

    'no_supported_components_support':
        """The supported components prop query does not work""",

    'rrule_takes_no_count':
        """Fastmail consistently yields a "502 bad gateway" when presented with a rrule containing COUNT""",

    'no-current-user-principal':
        """when querying for the current user principal property, server doesn't report anything useful""",

    'read_only':
        """The calendar server does not support PUT, POST, DELETE, PROPSET, MKCALENDAR, etc""",

    'no_relships':
        """The calendar server does not support child/parent relationships between calendar components""",

    'isnotdefined_not_working':
        """The is-not-defined in a calendar-query not working as it should - see https://gitlab.com/davical-project/davical/-/issues/281""",

    'search_needs_comptype':
        """The server may not always come up with anything useful when searching for objects and ommitting to specify weather one wants to see tasks or events""",
}

xandikos = [
    ## https://github.com/jelmer/xandikos/issues/8
    "no_expand", "no_recurring",

    'text_search_is_exact_match_only',

    ## This one is fixed in master branch
    'category_search_yields_nothing', ## https://github.com/jelmer/xandikos/pull/194

    ## scheduling is not supported
    "no_scheduling",
]

radicale = [
    ## calendar listings and calendar creation works a bit
    ## "weird" on radicale
    "no_default_calendar",
    "non_existing_calendar_found",

    ## freebusy is not supported yet, but on the long-term road map
    "no_freebusy_rfc4791",

    ## TODO: raise an issue on this one
    "radicale_breaks_on_category_search",

    'no_scheduling',

    'text_search_is_case_insensitive',
    'text_search_is_exact_match_sometimes',
    'combined_search_not_working',

    ## extra features not specified in RFC5545
    "calendar_order",
    "calendar_color"
]

## ZIMBRA IS THE MOST SILLY, AND THERE ARE REGRESSIONS FOR EVERY RELEASE!
## AAARGH!
zimbra = [
    ## no idea why this breaks
    "non_existing_calendar_found",

    ## apparently, zimbra has no journal support
    'no_journal',

    ## setting display name in zimbra does not work (display name,
    ## calendar-ID and URL is the same, the display name cannot be
    ## changed, it can only be given if no calendar-ID is given.  In
    ## earlier versions of Zimbra display-name could be changed, but
    ## then the calendar would not be available on the old URL
    ## anymore)
    'no_displayname',
    'duplicate_in_other_calendar_with_same_uid_is_lost',
    'event_by_url_is_broken',
    'no_todo_on_standard_calendar',
    'no_sync_token',
    'vtodo_datesearch_notime_task_is_skipped',
    'category_search_yields_nothing',
    'text_search_is_exact_match_only',
    'no_relships',
    'isnotdefined_not_working',

    ## extra features not specified in RFC5545
    "calendar_order",
    "calendar_color"

    ## TODO: there is more, it should be organized and moved here.
    ## Search for 'zimbra' in the code repository!
]

bedework = [
    ## quite a lot of things were missing in Bedework last I checked -
    ## but that's quite a while ago!
    'no_journal',
    'no_todo',
    'propfind_allprop_failure',
    'no_recurring',

    ## taking an event, changing the uid, and saving in the same calendar gives a 403.
    ## editing the content slightly and it works.  Weird ...
    'duplicates_not_allowed',
    'duplicate_in_other_calendar_with_same_uid_is_lost'
]

baikal = [
    ## date search on todos does not seem to work
    ## (TODO: do some research on this)
    'sync_breaks_on_delete',
    'no_recurring_todo',
    'no_recurring_todo_expand',
    'non_existing_calendar_found',
    'combined_search_not_working',
    'text_search_is_exact_match_sometimes',

    ## extra features not specified in RFC5545
    "calendar_order",
    "calendar_color"
]

## See comments on https://github.com/python-caldav/caldav/issues/3
icloud = [
    'unique_calendar_ids',
    'duplicate_in_other_calendar_with_same_uid_breaks',
    'sticky_events',
    'no_journal', ## it threw a 500 internal server error!
    'no_todo',
    "no_freebusy_rfc4791",
    'no_recurring',
    'propfind_allprop_failure',
    'object_by_uid_is_broken'
]

davical = [
    #'no_journal', ## it threw a 500 internal server error! ## for old versions
    #'nofreebusy', ## for old versions
    'fragile_sync_tokens', ## no issue raised yet
    'vtodo_datesearch_nodtstart_task_is_skipped_in_closed_date_range', ## no issue raised yet
    'isnotdefined_not_working', ## https://gitlab.com/davical-project/davical/-/issues/281
    'fastmail_buggy_noexpand_date_search', ## https://gitlab.com/davical-project/davical/-/issues/280
    "isnotdefined_not_working",
]

google = [
    'no_mkcalendar',
    'no_overwrite',
    'no_todo',
    'no_recurring_expandation'
]

## https://www.sogo.nu/bugs/view.php?id=3065
## left a note about time-based sync tokens on https://www.sogo.nu/bugs/view.php?id=5163
## https://www.sogo.nu/bugs/view.php?id=5282
## https://bugs.sogo.nu/view.php?id=5693
## https://bugs.sogo.nu/view.php?id=5694
sogo = [ ## and in addition ... the requests are efficiently rate limited, as it spawns lots of postgresql connections all until it hits a limit, after that it's 501 errors ...
    "time_based_sync_tokens",
    "search_needs_comptype",
    "fastmail_buggy_noexpand_date_search",
    "text_search_not_working",
    "isnotdefined_not_working",
    'no_journal',
    'no_freebusy_rfc4791'
]

nextcloud = [
    'sync_breaks_on_delete',
    'no_recurring_todo',
    'no_recurring_todo_expand',
    'combined_search_not_working',
    'text_search_is_exact_match_sometimes',
]

fastmail = [
    'duplicates_not_allowed',
    'duplicate_in_other_calendar_with_same_uid_breaks',
    'no_todo',
    'sticky_events',
    'fastmail_buggy_noexpand_date_search',
    'combined_search_not_working',
    'text_search_is_exact_match_sometimes',
    'rrule_takes_no_count',
    'isnotdefined_not_working',
]

synology = [
    "fragile_sync_tokens",
    "vtodo_datesearch_notime_task_is_skipped",
    "no_recurring_todo",
]

robur = [
    'non_existing_raises_other', ## AuthorizationError instead of NotFoundError
    'no_scheduling',
    'no_sync_token',
    'no_supported_components_support',
    'no_journal',
    'no_freebusy_rfc4791',
    'no_todo_datesearch', ## returns nothing
    'text_search_not_working',
    'no_relships',
    'isnotdefined_not_working',
]


# fmt: on
