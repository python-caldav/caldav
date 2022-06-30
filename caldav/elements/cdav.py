#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from datetime import datetime

try:
    from datetime import timezone

    utc_tz = timezone.utc
except:
    ## pytz is deprecated - but as of 2021-11, the icalendar library is only
    ## compatible with pytz (see https://github.com/collective/icalendar/issues/333 https://github.com/collective/icalendar/issues/335 https://github.com/collective/icalendar/issues/336)
    import pytz

    utc_tz = pytz.utc

from caldav.lib.namespace import ns
from .base import BaseElement, NamedBaseElement, ValuedBaseElement


def _to_utc_date_string(ts):
    # type (Union[date,datetime]]) -> str
    """coerce datetimes to UTC (assume localtime if nothing is given)"""
    if isinstance(ts, datetime):
        try:
            ## for any python version, this should work for a non-native
            ## timestamp.
            ## in python 3.6 and higher, ts.astimezone() will assume a
            ## naive timestamp is localtime (and so do we)
            ts = ts.astimezone(utc_tz)
        except:
            ## native time stamp and the current python version is
            ## not able to treat it as localtime.
            import tzlocal

            ts = ts.replace(tzinfo=tzlocal.get_localzone())
            ts = ts.astimezone(utc_tz)

    return ts.strftime("%Y%m%dT%H%M%SZ")


# Operations
class CalendarQuery(BaseElement):
    tag = ns("C", "calendar-query")


class FreeBusyQuery(BaseElement):
    tag = ns("C", "free-busy-query")


class Mkcalendar(BaseElement):
    tag = ns("C", "mkcalendar")


class CalendarMultiGet(BaseElement):
    tag = ns("C", "calendar-multiget")


class ScheduleInboxURL(BaseElement):
    tag = ns("C", "schedule-inbox-URL")


class ScheduleOutboxURL(BaseElement):
    tag = ns("C", "schedule-outbox-URL")


# Filters
class Filter(BaseElement):
    tag = ns("C", "filter")


class CompFilter(NamedBaseElement):
    tag = ns("C", "comp-filter")


class PropFilter(NamedBaseElement):
    tag = ns("C", "prop-filter")


class ParamFilter(NamedBaseElement):
    tag = ns("C", "param-filter")


# Conditions
class TextMatch(ValuedBaseElement):
    tag = ns("C", "text-match")

    def __init__(self, value, collation="i;octet", negate=False):
        super(TextMatch, self).__init__(value=value)
        self.attributes["collation"] = collation
        if negate:
            self.attributes["negate-condition"] = "yes"


class TimeRange(BaseElement):
    tag = ns("C", "time-range")

    def __init__(self, start=None, end=None):
        ## start and end should be an icalendar "date with UTC time",
        ## ref https://tools.ietf.org/html/rfc4791#section-9.9
        super(TimeRange, self).__init__()
        if start is not None:
            self.attributes["start"] = _to_utc_date_string(start)
        if end is not None:
            self.attributes["end"] = _to_utc_date_string(end)


class NotDefined(BaseElement):
    tag = ns("C", "is-not-defined")


# Components / Data
class CalendarData(BaseElement):
    tag = ns("C", "calendar-data")


class Expand(BaseElement):
    tag = ns("C", "expand")

    def __init__(self, start, end=None):
        super(Expand, self).__init__()
        if start is not None:
            self.attributes["start"] = _to_utc_date_string(start)
        if end is not None:
            self.attributes["end"] = _to_utc_date_string(end)


class Comp(NamedBaseElement):
    tag = ns("C", "comp")


# Uhhm ... can't find any references to calendar-collection in rfc4791.txt
# and newer versions of baikal gives 403 forbidden when this one is
# encountered
# class CalendarCollection(BaseElement):
#     tag = ns("C", "calendar-collection")


# Properties
class CalendarUserAddressSet(BaseElement):
    tag = ns("C", "calendar-user-address-set")


class CalendarUserType(BaseElement):
    tag = ns("C", "calendar-user-type")


class CalendarHomeSet(BaseElement):
    tag = ns("C", "calendar-home-set")


# calendar resource type, see rfc4791, sec. 4.2
class Calendar(BaseElement):
    tag = ns("C", "calendar")


class CalendarDescription(ValuedBaseElement):
    tag = ns("C", "calendar-description")


class CalendarTimeZone(ValuedBaseElement):
    tag = ns("C", "calendar-timezone")


class SupportedCalendarComponentSet(ValuedBaseElement):
    tag = ns("C", "supported-calendar-component-set")


class SupportedCalendarData(ValuedBaseElement):
    tag = ns("C", "supported-calendar-data")


class MaxResourceSize(ValuedBaseElement):
    tag = ns("C", "max-resource-size")


class MinDateTime(ValuedBaseElement):
    tag = ns("C", "min-date-time")


class MaxDateTime(ValuedBaseElement):
    tag = ns("C", "max-date-time")


class MaxInstances(ValuedBaseElement):
    tag = ns("C", "max-instances")


class MaxAttendeesPerInstance(ValuedBaseElement):
    tag = ns("C", "max-attendees-per-instance")


class Allprop(BaseElement):
    tag = ns("C", "allprop")


class ScheduleTag(BaseElement):
    tag = ns("C", "schedule-tag")
