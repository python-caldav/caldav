#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from typing import ClassVar

from caldav.lib.namespace import ns

from .base import BaseElement
from .base import ValuedBaseElement

# Properties
class CalendarColor(ValuedBaseElement):
    tag: ClassVar[str] = ns("I", "calendar-color")


class CalendarOrder(ValuedBaseElement):
    tag: ClassVar[str] = ns("I", "calendar-order")
