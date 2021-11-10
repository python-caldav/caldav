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
        """Server may throw errors when asked to do a expanded date search""",

    'no_recurring':
        """Server is having issues with recurring events and/or todos. """
        """date searches covering recurrances may yield no results, """
        """and events/todos may not be expanded with recurrances""",

    'no_recurring_expandation':
        """Server will not expand recurring events""",

    'no_recurring_todo':
        """Recurring events are supported, but not recurring todos""",

    'no_recurring_todo_expand':
        """Recurring todos aren't expanded""",

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

    'uid_required':
        """Server will not accept calendar object resources without an UID""",

    'no_sync_token':
        """RFC6578 is not supported, things will break if we try to do a sync-token report""",

    'time_based_sync_tokens':
        """The sync token is typically a time stamp, and we need to sleep a """
        """second in the test code to get things right""",

    'fragile_sync_tokens':
        """Every now and then (or perhaps always), more content than expected """
        """will be returned on a simple sync request.  Possibly a race condition """
        """if the token is timstamp-based?""",

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
}

xandikos = [
    ## TEMP TEMP TEMP - TODO - should be investigated
    ## (perhaps my xandikos version is too old?)
    "no_expand", "no_recurring",
    
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

    ## Expanding recurrent events is not yet supported
    ## ref https://github.com/Kozea/Radicale/issues/662
    "no_recurring_expandation",

    'no_scheduling',

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
    'uid_required',
    'no_todo_on_standard_calendar',
    'no_sync_token',
    'no_recurring_todo',

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
    'no_todo_datesearch',

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
    #'nofreebusy', ## for old versions 
    'vtodo_datesearch_nodtstart_task_is_skipped',
    'fragile_sync_tokens',
    'no_journal' ## it threw a 500 internal server error!
]

google = [
    'no_mkcalendar',
    'no_overwrite',
    'no_todo',
    'no_recurring_expandation'
]

sogo = [
    'no_journal',
    'no_freebusy_rfc4791', ## https://www.sogo.nu/bugs/view.php?id=5282
    "time_based_sync_tokens", ## Left a note on https://www.sogo.nu/bugs/view.php?id=5163
    "no_expand", ## https://www.sogo.nu/bugs/view.php?id=3065
    "vtodo_datesearch_nodtstart_task_is_skipped",
]

nextcloud = [
    'no_sync_token',
    'no_recurring_todo',
    'no_recurring_todo_expand',
]
