## The lists below are specifying what tests should be skipped or
## modified to accept non-conforming resultsets from the different
## calendar servers.  In addition there are some hacks in the library
## code itself to work around some known compatibility issues, like
## the caldav.lib.vcal.fix function.  We should probably keep a list
## in the documentation on everything.

xandikos = [
    ## TEMP TEMP TEMP - TODO - should be investigated
    ## (perhaps my xandikos version is too old?)
    "noexpand", "norecurring"
]

radicale = [
    ## The proxy test code needs to be rewritten
    ## ref https://github.com/python-caldav/caldav/issues/89    
    "noproxy",

    ## calendar listings and calendar creation works a bit
    ## "weird" on radicale
    "nodefaultcalendar",
    "nocalendarnotfound",

    ## freebusy is not supported yet, but on the long-term road map
    "nofreebusy",

    ## Expanding recurrent events is not yet supported
    ## ref https://github.com/Kozea/Radicale/issues/662
    "norecurringexpandation",

    ## extra features not specified in RFC5545
    "calendarorder",
    "calendarcolor"
]

zimbra = [
    ## no idea why this breaks
    'nocalendarnotfound',

    ## apparently, zimbra has no journal support
    'nojournal',

    ## setting display name in zimbra does not work (display name,
    ## calendar-ID and URL is the same, the display name cannot be
    ## changed, it can only be given if no calendar-ID is given.  In
    ## earlier versions of Zimbra display-name could be changed, but
    ## then the calendar would not be available on the old URL
    ## anymore)
    'nodisplayname'

    ## extra features not specified in RFC5545
    "calendarorder",
    "calendarcolor"

    ## TODO: there is more, it should be organized and moved here.
    ## Search for 'zimbra' in the code repository!
]

bedework = [
    ## quite a lot of things were missing in Bedework last I checked -
    ## but that's quite a while ago!
    'nojournal',
    'notodo',
    'nopropfind',
    'norecurring',

    ## taking an event, changing the uid, and saving in the same calendar gives a 403.
    ## editing the content slightly and it works.  Weird ...
    'duplicates_not_allowed',
    'duplicate_in_other_calendar_with_same_uid_is_lost'
]

baikal = [
    ## date search on todos does not seem to work
    ## (TODO: do some research on this)
    'notododatesearch',

    ## extra features not specified in RFC5545
    "calendarorder",
    "calendarcolor"

]

## See comments on https://github.com/python-caldav/caldav/issues/3
icloud = [
    'unique_calendar_ids',
    'cross_calendar_duplicate_not_allowed',
    'stickyevents',
    'nojournal', ## it threw a 500 internal server error!
    'notodo',
    'nofreebusy',
    'norecurring',
    'nopropfind',
    'object_by_uid_is_broken'
    ]

## The version of davical I'm testing towards is very old, so this list may be outdated
davical = [
    'nofreebusy',
    'vtodo_datesearch_nodtstart_task_is_skipped',
]

