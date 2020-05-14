xandikos = [
    ## Xandikos does not support recurring events as of 0.2.1/2020-05,
    ## ref https://github.com/jelmer/xandikos/issues/8
    "norecurring"
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
    "norecurringexpandation"
]

zimbra = [
    ## no idea why this breaks
    'nocalendarnotfound',

    ## apparently, zimbra has no journal support
    'nojournal'

    ## TODO: there is more.  Search for 'zimbra' in the code repository!
]

