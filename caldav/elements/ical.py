#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from caldav.lib.namespace import ns

from .base import BaseElement
from .base import ValuedBaseElement

# Properties
class CalendarColor(ValuedBaseElement):
    tag = ns("I", "calendar-color")


class CalendarOrder(ValuedBaseElement):
    tag = ns("I", "calendar-order")
