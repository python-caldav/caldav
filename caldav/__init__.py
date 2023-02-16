#!/usr/bin/env python
import logging

import vobject.icalendar

__version__ = "1.1.1"

from .davclient import DAVClient
from .objects import *


## Notes:
##
## * The vobject.icalendar has (or had?) to be explicitly imported due to some bug in the tBaxter fork of vobject.
## * The "import *" looks quite ugly, should be revisited prior to launching 1.0.

# Silence notification of no default logging handler
log = logging.getLogger("caldav")


class NullHandler(logging.Handler):
    def emit(self, record):
        pass


log.addHandler(NullHandler())
