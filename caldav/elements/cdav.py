#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from caldav.lib.namespace import ns
from base import BaseElement, NamedBaseElement, ValuedBaseElement


## Operations
class CalendarQuery(BaseElement):
    tag = ns("C", "calendar-query")


## Filters
class Filter(BaseElement):
    tag = ns("C", "filter")


class CompFilter(NamedBaseElement):
    tag = ns("C", "comp-filter")


class PropFilter(NamedBaseElement):
    tag = ns("C", "prop-filter")


class ParamFilter(NamedBaseElement):
    tag = ns("C", "param-filter")


## Conditions
class TextMatch(ValuedBaseElement):
    tag = ns("C", "text-match")

    def __init__(self, value, collation="i; octet", negate=False):
        super(TextMatch, self).__init__(value=value)
        self.attributes['collation'] = collation
        self.attributes['negate'] = "no"
        if negate:
            self.attributes['negate'] = "yes"


class TimeRange(BaseElement):
    tag = ns("C", "time-range")

    def __init__(self, start=None, end=None):
        super(TimeRange, self).__init__()
        if start is not None:
            self.attributes['start'] = \
                    start.strftime("%Y%m%dT%H%M%SZ")
        if end is not None:
            self.attributes['end'] = end.strftime("%Y%m%dT%H%M%SZ")


class NotDefined(BaseElement):
    tag = ns("C", "is-not-defined")


## Components / Data
class CalendarData(BaseElement):
    tag = ns("C", "calendar-data")


class Expand(BaseElement):
    tag = ns("C", "expand")

    def __init__(self, start, end=None):
        super(Expand, self).__init__()
        self.attributes['start'] = start.strftime("%Y%m%dT%H%M%SZ")
        if end is not None:
            self.attributes['end'] = end.strftime("%Y%m%dT%H%M%SZ")


class Comp(NamedBaseElement):
    tag = ns("C", "comp")


class CalendarCollection(BaseElement):
    tag = ns("C", "calendar-collection")


## Properties

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
