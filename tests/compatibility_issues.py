## The lists below are specifying what tests should be skipped or
## modified to accept non-conforming resultsets from the different
## calendar servers.  In addition there are some hacks in the library
## code itself to work around some known compatibility issues, like
## the caldav.lib.vcal.fix function.  We should probably keep a list
## in the documentation on everything.

xandikos = [
    ## Xandikos does not support recurring events as of 0.2.1/2020-05,
    ## ref https://github.com/jelmer/xandikos/issues/8
    "norecurring",

    ## As of 2020-05-17 it even returns a 500 internal server error
    ## when one attempts to use the expand-flag in a date search
    "noexpand",
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

    ## TODO: there is more, it should be organized and moved here.
    ## Search for 'zimbra' in the code repository!
]

bedework = [
    ## quite a lot of things were missing in Bedework last I checked -
    ## but that's quite a while ago!
    'nojournal',
    'notodo',
    'nopropfind',
    'norecurring'
]

baikal = [
    ## Quite a while since I tested towards baikal, but no issues were found
]

## The version of davical I'm testing towards is very old, so this list may be outdated
davical = [
    'nofreebusy',
    'vtodo_datesearch_nodtstart_task_is_skipped'
]

