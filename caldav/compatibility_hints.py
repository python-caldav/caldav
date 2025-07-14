# fmt: off
"""
This file serves as a database of different compatibility issues we've
encountered while working on the caldav library, and descriptions on
how the well-known servers behave.
"""

import copy

## NEW STYLE
## (we're gradually moving stuff from the good old
## "incompatibility_description" below over to
## "compatibility_features")

class FeatureSet:
    """Work in progress ... TODO: write a better class description.

    This class holds the description of different behaviour observed in
    a class constant.

    An object of this class describes the feature set of a server.

    TODO: use enums?
      type -> "client-feature", "server-peculiarity", "tests-behaviour", "server-observation", "server-feature" (last is default)
      support -> "supported" (default), "unsupported", "fragile", "broken", "ungraceful"

    types:
     * client-feature means the client is supposed to do special things (like, rate-limiting).  While the need for rate-limiting may be set by the server, it may not be possible to reliably establish it by probling the server, and the value may differ for different clients.
    * server-peculiarity - weird behaviour detected at the server side, behaviour that is too odd to be described as "missing support for a feature".  Example: there is some cache working, causing a delay from some object is sent to the server and until it can be retrieved.  The difference between an "unsupported server-feature" and a "server-peculiarity" may be a bit floating - like, arguably "instant updates" may be considered a feature.
    """
    FEATURES = {
        "get-current-user-principal": {
            "description": "Support for RFC5397, current principal extension.  Most CalDAV servers have this, but it is an extension to the standard",
            "features": {
                "has-calendar": {
                    "type": "server-observation",
                    "description": "Principal has one or more calendars.  Some servers and providers comes with a pre-defined calendar for each user, for other servers a calendar has to be explicitly created (supported means there exists a calendar - it may be because the calendar was already provisioned together with the principal, or it may be because a calendar was created manually, the checks can't see the difference)"}
            }
        },
        "rate-limit": {
            "type": "client-feature",
            "description": "client (or test code) must not send requests too fast",
            "extra_keys": {
                "interval": "Rate limiting window, in seconds",
                "count": "Max number of requests to send within the interval",
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
            "description": "RFC4791 says that \"support for MKCALENDAR on the server is only RECOMMENDED and not REQUIRED because some calendar stores only support one calendar per user (or principal), and those are typically pre-created for each account\".  Hence a conformant server may opt to not support creating calendars, this is often seen for cloud services (some services allows extra calendars to be made, but not through the CalDAV protocol).  (RFC4791 also says that the server MAY support MKCOL in section 8.5.2.  I do read it as MKCOL may be used for creating calendars - which is weird, since section 8.5.2 is titled \"external attachments\".  We should consider testing this as well)",
            "features": {
                "auto": {
                    "default": { "support": "unsupported" },
                    "description": "Accessing a calendar which does not exist automatically creates it",
                },
                "set-displayname": {
                    "description": "It's possible to set the displayname on a calendar upon creation"
                }
            }
        },
        "delete-calendar": {
            "description": "RFC4791 says nothing about deletion of calendars, so the server implementation is free to choose weather this should be supported or not.  Section 3.2.3.2 in RFC 6638 says that if a calendar is deleted, all the calendarobjectresources on the calendar should also be deleted - but it's a bit unclear if this only applies to scheduling objects or not.  Some calendar servers moves the object to a trashcan rather than deleting it",
            "features": {
                "free-namespace": {
                    "description": "The delete operations clears the namespace, so that another calendar with the same ID/name can be created"
                }
            }
        },
        "search": {
            "description": "calendar MUST support searching for objects using the REPORT method, as specified in RFC4791, section 7",
            "features": {
                ## TODO - there is still quite a lot of search-related
                ## stuff that hasn't been moved from the old "quirk list"
                "time-range": {
                    "description": "Search for time or date ranges should work.  This is specified in RFC4791, section 7.4 and section 9.9",
                    "features": {
                        "todo": {"description": "basic time range searches for tasks works"},
                        "event": {"description": "basic time range searches for events works"},
                        "journal": {"description": "basic time range searches for journals works"},
                    }
                }
            }
        },
        "recurrences": {
            "description": "Support for recurring events and tasks",
            "features": {
                "save-load": {
                    "description": "Calendar server should accept ojects with RRULE given, as well as objects with recurrence sets, and should be able to deliver back the same data",
                    "features": {
                        "event": {"description": "works with events"},
                        "todo": {"description": "works with tasks"},
                    }
                },
                "search-includes-implicit-recurrences": {
                    "description": "RFC 4791, section 7.4 says that the server MUST expand recurring components to determine whether any recurrence instances overlap the specified time range.  Considered supported i.e. if a search for 2005 yields a yearly event happening first time in 2004.",
                    "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-7.4"],
                    "features": {
                        "infinite-scope": {
                            "description": "Needless to say, search on any future date range, no matter how far out in the future, should yield the recurring object"
                        },
                        "event": {"description": "works with events"},
                        "todo": {"description": "works with tasks"},
                    }
                },
                "expanded-search": {
                    "description": "According to RFC 4791, the server MUST expand recurrence objects if asked for it - but many server doesn't do that.  It doesn't matter much by now, as the client library can do the expandation.  Some servers don't do expand at all, others deliver broken data, typically missing RECURRENCE-ID",
                    "links": ["https://datatracker.ietf.org/doc/html/rfc4791#section-9.6.5"],
                    "features": {
                        "exception": {
                            "description": "Server expand should work correctly also if a recurrence set with exceptions is given" },
                        "event": {"description": "works with events"},
                        "todo": {"description": "works with tasks"},
                    },
                },
            },
        },
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
        
        ## TODO: copy the FEATURES dict, or just the feature_set dict?
        ## (anyways, that is an internal design decision that may be
        ## changed ... but we need test code in place)
        self._server_features = {}
        if feature_set_dict:
            self.copyFeatureSet(feature_set_dict)

    def _copyFeature(self, def_node, server_node, value):
        if isinstance(value, str) and not 'support' in server_node:
            server_node['support'] = value
        elif isinstance(value, dict):
            if value.get('features'):
                raise NotImplementedError("todo ... work in progress ... need to recursively process the feature set")
            server_node.update(value)

    def copyFeatureSet(self, feature_set):
        for feature in feature_set:
            ## TODO: temp - should be removed
            if feature == 'old_flags':
                continue
            fpath = feature.split('.')
            def_tree = self.FEATURES
            server_tree = self._server_features
            for step in fpath:
                assert def_tree
                assert step in def_tree
                def_node = def_tree[step]
                if not step in server_tree:
                    server_tree[step] = {}
                server_node = server_tree[step]
                if not 'features' in def_node:
                    server_tree = None
                    def_tree = None
                else:
                    if not 'features' in server_node:
                        server_node['features'] = {}
                    server_tree = server_node['features']
                    def_tree = def_node['features']
            self._copyFeature(def_node, server_node, feature_set[feature])

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
        else:
            breakpoint()

    def check_support(self, feature, return_type=bool):
        """
        Work in progress

        TODO: write a better docstring
        """
        feature_info = self.find_feature(feature)
        node = self._server_features
        feature_path = feature.split('.')
        support = None
        for x in feature_path:
            if x in node:
                support = node[x]
                node = support.get('features', {})
            else:
                if support is None:
                    support = self._default(feature_info)
                break
        if return_type == str:
            ## TODO: consider type, be smarter about it
            return support.get('support', support.get('enable', support.get('behaviour')))
        elif return_type == dict:
            return support
        elif return_type == bool:
            ## TODO: consider feature_info['type'], be smarter about this
            return support.get('support', 'full') == 'full' and not support.get('enable') and not support.get('behaviour') and not support.get('observed')

    ## TODO: could be a class method?
    def find_feature(self, feature: str) -> dict:
        """
        Feature should be a string like feature.subfeature.subsubfeature.

        Looks through the FEATURES list and returns the relevant section.

        Will raise an AssertionError if feature is not found
        """
        hierarchy = feature.split('.')
        node = self.FEATURES
        for x in hierarchy:
            assert x in node
            feature = node[x]
            node = feature.get('features', {})
        return feature

    def dotted_feature_set_list(self, compact=False):
        return self._dotted_feature_set_list('', self._server_features, compact=compact, feature_info=None)

    def _dotted_feature_set_list(self, feature_path, feature_node, compact, feature_info):
        ret = {}
        if feature_info:
            num_expected_subfeatures = len(feature_info.get('features', {}))
        else:
            num_expected_subfeatures = 0
        orig_feature_path = feature_path
        if feature_path:
            feature_path = f"{feature_path}."
        sub_features = {}
        all_sub_features_equal = True
        last_sub_feature = None
        cnt = 0
        for x in feature_node:
            feature = feature_node[x].copy()
            full = f"{feature_path}{x}"
            feature_info = self.find_feature(full)
            if compact and feature_info.get('type', 'server-feature') in ('client-feature', 'server-observation'):
                continue
            if 'features' in feature:
                subnode = feature.pop('features')
                ret.update(self._dotted_feature_set_list(full, subnode, compact, feature_info))
            if compact and feature == self._default(feature_info):
                all_sub_features_equal = False
                continue
            if feature:
                sub_features[full] = feature
                if last_sub_feature and last_sub_feature != feature:
                    all_sub_features_equal = False
                last_sub_feature = feature
                cnt += 1
        if compact and all_sub_features_equal and last_sub_feature and cnt>1 and len(feature_node.keys()) == num_expected_subfeatures:
            ret[orig_feature_path] = last_sub_feature
        else:
            ret.update(sub_features)
        return ret

#### OLD STYLE

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

    'no_alarmsearch':
        """Searching for alarms may yield too few or too many or even a 500 internal server error""",

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

xandikos = {
    "recurrences.expanded-search": {'support': 'unsupported'},
    "recurrences.search-includes-implicit-recurrences": {'support': 'unsupported'},
    "old_flags":  [
    ## https://github.com/jelmer/xandikos/issues/8
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
}

## TODO - there has been quite some development in radicale recently, so this list
## should probably be gone through
radicale = {
    "search.time-range.todo": {"support": "unsupported"},
    'old_flags': [
    ## calendar listings and calendar creation works a bit
    ## "weird" on radicale
    "no_default_calendar",
    "no_alarmsearch", ## This is fixed and will be released soon

    ## freebusy is not supported yet, but on the long-term road map
    #"no_freebusy_rfc4791",

    "no-principal-search-self", ## this may be because we haven't set up any users or authentication - so the display name of the current user principal is None

    'no_scheduling',

    'text_search_is_case_insensitive',
    #'text_search_is_exact_match_sometimes',
    "search_needs_comptype",

    ## extra features not specified in RFC5545
    "calendar_order",
    "calendar_color"
    ]
}

## ZIMBRA IS THE MOST SILLY, AND THERE ARE REGRESSIONS FOR EVERY RELEASE!
## AAARGH!
zimbra = [
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
