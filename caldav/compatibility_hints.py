# fmt: off
"""This text was updated 2025-05-17.  The plan is to reorganize this
file a lot over the next few months, see
https://github.com/python-caldav/caldav/issues/402

This file serves as a database of different compatibility issues we've
encountered while working on the caldav library, and descriptions on
how the well-known servers behave.

As for now, this is a list of binary "flags" that could be turned on
or off.  My experience is that there are often neuances, so the
compatibility matrix will be changed from being a list of flags to a
key=value store in the near future (at least, that's the plan).

The issues may be grouped together, maybe even organized
hierarchically.  I did consider organizing the compatibility issues in
some more advanced way, but I don't want to overcomplicate things - I
will try out the key-value-approach first.
"""
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
    'rate_limited':
        """It may be needed to pause a bit between each request when doing tests""",

    'search_delay':
        """Server populates indexes through some background job, so it takes some time from an event is added/edited until it's possible to search for it""",

    'cleanup_calendar':
        """Remove everything on the calendar for every test""",

    'no_delete_calendar':
        """Not allowed to delete calendars - or calendar ends up in a 'trashbin'""",

    'broken_expand':
        """Server-side expand seems to work, but delivers wrong data (typically missing RECURRENCE-ID)""",

    'no_expand':
        """Server-side expand does not seem to work""",

    'broken_expand_on_exceptions':
        """The testRecurringDateWithExceptionSearch test breaks as the icalendar_component is missing a RECURRENCE-ID field.  TODO: should be investigated more""",

    'inaccurate_datesearch':
        """A date search may yield results outside the search interval""",

    'no-principal-search':
        """Searching for principals gives a 403 error or similar""",

    'no-principal-search-self':
        """Searching for my own principal by name gives nothing, a 403 error or similar""",

    'no-principal-search-all':
        """Searching for all principals gives a 403 error or similar""",

    'no_current-user-principal':
        """Current user principal not supported by the server (flag is ignored by the tests as for now - pass the principal URL as the testing URL and it will work, albeit with one warning""",

    'no_recurring':
        """Server is having issues with recurring events and/or todos. """
        """date searches covering recurrances may yield no results, """
        """and events/todos may not be expanded with recurrances""",

    'no_alarmsearch':
        """Searching for alarms may yield too few or too many or even a 500 internal server error""",

    'no_recurring_todo':
        """Recurring events are supported, but not recurring todos""",

    'no_recurring_todo_expand':
        """Recurring todos aren't expanded (this is ignored by the tests now, as we're doing client-side expansion)""",

    'no_scheduling':
        """RFC6833 is not supported""",

    'no_scheduling_mailbox':
        """Parts of RFC6833 is supported, but not the existence of inbox/mailbox""",

    'no_scheduling_calendar_user_address_set':
        """Parts of RFC6833 is supported, but not getting the calendar users addresses""",

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

    'no_delete_event':
        """Zimbra does not support deleting an event, probably because event_by_url is broken""",

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

    'no_todo_on_standard_calendar':
        """Tasklists can be created, but a normal calendar does not support tasks""",

    'no_todo_datesearch':
        """Date search on todo items fails""",

    'vtodo_datesearch_nodtstart_task_is_skipped':
        """date searches for todo-items will not find tasks without a dtstart""",

    'vtodo_datesearch_nodtstart_task_is_skipped_in_closed_date_range':
        """only open-ended date searches for todo-items will find tasks without a dtstart""",

    'vtodo_datesearch_notime_task_is_skipped':
        """date searches for todo-items will (only) find tasks that has either """
        """a dtstart or due set""",

    'vtodo_datesearch_nostart_future_tasks_delivered':
        """Future tasks are yielded when doing a date search with some end timestamp and without start timestamp and the task contains both dtstart and due, but not duration (xandikos 0.2.12)""",

    'vtodo_no_due_infinite_duration':
        """date search will find todo-items without due if dtstart is """
        """before the date search interval.  This is in breach of rfc4791"""
        """section 9.9""",

    'vtodo_no_dtstart_infinite_duration':
        """date search will find todo-items without dtstart if due is """
        """after the date search interval.  This is in breach of rfc4791"""
        """section 9.9""",

    'vtodo_no_dtstart_search_weirdness':
       """Zimbra is weird""",

    'vtodo_no_duration_search_weirdness':
       """Zimbra is weird""",

    'vtodo_with_due_weirdness':
       """Zimbra is weird""",

    'vtodo-cannot-be-uncompleted':
        """If a VTODO object has been set with STATUS:COMPLETE, it's not possible to delete the COMPLTEDED attribute and change back to STATUS:IN-ACTION""",

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

    'date_search_ignores_duration':
        """Date search with search interval overlapping event interval works on events with dtstart and dtend, but not on events with dtstart and due""",

    'date_todo_search_ignores_duration':
        """Same as above, but specifically for tasks""",

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
        """The server may not always come up with anything useful when searching for objects and omitting to specify weather one wants to see tasks or events.  https://github.com/python-caldav/caldav/issues/401""",

    'search_always_needs_comptype':
        """calendar.mail.ru: the server throws 400 when searching for objects and omitting to specify weather one wants to see tasks or events.  `calendar.objects()` throws 404, even if there are events.  https://github.com/python-caldav/caldav/issues/401""",

    'robur_rrule_freq_yearly_expands_monthly':
        """Robur expands a yearly event into a monthly event.  I believe I've reported this one upstream at some point, but can't find back to it""",

    'no_search':
        """Apparently the calendar server does not support search at all (this often implies that 'object_by_uid_is_broken' has to be set as well)""",

    'no_search_openended':
        """An open-ended search will not work""",

    'no_events_and_tasks_on_same_calendar':
        """Zimbra has the concept of task lists ... a calendar must either be a calendar with only events, or it can be a task list, but those must never be mixed"""
}

xandikos = [
    ## https://github.com/jelmer/xandikos/issues/8
    "no_recurring",

    'date_todo_search_ignores_duration',
    'text_search_is_exact_match_only',
    "search_needs_comptype",
    'vtodo_datesearch_nostart_future_tasks_delivered',

    ## scheduling is not supported
    "no_scheduling",
    'no-principal-search',

    ## The test in the tests itself passes, but the test in the
    ## check_server_compatibility triggers a 500-error
    "no_freebusy_rfc4791",

    ## The test with an rrule and an overridden event passes as
    ## long as it's with timestamps.  With dates, xandikos gets
    ## into troubles.  I've chosen to edit the test to use timestamp
    ## rather than date, just to have the test exercised ... but we
    ## should report this upstream
    #'broken_expand_on_exceptions',

    ## No alarm search (500 internal server error)
    "no_alarmsearch",
]

## TODO - there has been quite some development in radicale recently, so this list
## should probably be gone through
radicale = [
    ## calendar listings and calendar creation works a bit
    ## "weird" on radicale
    "broken_expand",
    "no_default_calendar",
    "no_alarmsearch", ## This is fixed and will be released soon

    ## freebusy is not supported yet, but on the long-term road map
    #"no_freebusy_rfc4791",

    "no-principal-search-self", ## this may be because we haven't set up any users or authentication - so the display name of the current user principal is None

    'no_scheduling',
    "no_todo_datesearch",

    'text_search_is_case_insensitive',
    #'text_search_is_exact_match_sometimes',
    "search_needs_comptype",

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
    'no_delete_event',
    'no_sync_token',
    'vtodo_datesearch_notime_task_is_skipped',
    'category_search_yields_nothing',
    'text_search_is_exact_match_only',
    'no_relships',
    'isnotdefined_not_working',
    "no_alarmsearch",
    "no_events_and_tasks_on_same_calendar",
    "no-principal-search",

    ## TODO: I just discovered that when searching for a date some
    ## years after a recurring daily event was made, the event does
    ## not appear.

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
    'vtodo_datesearch_nodtstart_task_is_skipped', ## no issue raised yet
    'broken_expand_on_exceptions', ## no issue raised yet
    'date_todo_search_ignores_duration',
    'calendar_color',
    'calendar_order',
    'vtodo_datesearch_notime_task_is_skipped',
    "no_alarmsearch",
]

google = [
    'no_mkcalendar',
    'no_overwrite',
    'no_todo',
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
    'date_search_ignores_duration',
    'unique_calendar_ids',
    'broken_expand',
    'no_delete_calendar',
    'sync_breaks_on_delete',
    'no_recurring_todo',
    'combined_search_not_working',
    'text_search_is_exact_match_sometimes',
    'search_needs_comptype',
    'calendar_color',
    'calendar_order',
    'date_todo_search_ignores_duration',
    'broken_expand_on_exceptions'
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
    "no-principal-search",
    'no_relships',
    'isnotdefined_not_working',
    'no_alarmsearch',
    'broken_expand',
]

posteo = [
    'no_scheduling',
    'no_mkcalendar',
    'no_journal',
    'no_recurring_todo',
    'no_sync_token',
    'combined_search_not_working',
    'no_alarmsearch',
    'broken_expand',
    "no-principal-search-self",
]

calendar_mail_ru = [
    'no_mkcalendar', ## weird.  It was working in early June 2024, then it stopped working in mid-June 2024.
    'no_current-user-principal',
    'no_todo',
    'no_journal',
    'search_always_needs_comptype',
    'no_sync_token', ## don't know if sync tokens are supported or not - the sync-token-code needs some workarounds ref https://github.com/python-caldav/caldav/issues/401
    'text_search_not_working',
    'isnotdefined_not_working',
    'no_scheduling_mailbox',
    'no_freebusy_rfc4791',
    'no_relships', ## mail.ru recreates the icalendar content, and strips everything it doesn't know anyhting about, including relationship info
]

purelymail = [
    ## Known, work in progress
    'no_scheduling',

    ## Not a breach of standard
    'non_existing_calendar_found',

    ## Known, not a breach of standard
    'no_supported_components_support',

    ## Purelymail claims that the search indexes are "lazily" populated,
    ## so search works some minutes after the event was created/edited.
    'search_delay',

    "no-principal-search", ## more research may be needed.  "cant-operate-on-root", indicating that the URL may need adjusting?

    ## I haven't raised this one with them yet
    'no_alarmsearch',
]

gmx = [
    "no_scheduling_mailbox",
    "no_mkcalendar",
    "search_needs_comptype",
    #"text_search_is_case_insensitive",
    "no-principal-search-all",
    "no_freebusy_rfc4791",
    "no_expand",
    "no_search_openended",
    "no_sync_token",
    "no_scheduling_calendar_user_address_set",
    "no-principal-search-self",
    "vtodo-cannot-be-uncompleted",
    #"no-principal-search-all",
]

# fmt: on
