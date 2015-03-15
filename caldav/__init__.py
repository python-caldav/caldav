#!/usr/bin/env python

from .davclient import DAVClient
from .objects import *
import logging

# Silence notification of no default logging handler
log = logging.getLogger("caldav")


class NullHandler(logging.Handler):
    def emit(self, record):
        pass


log.addHandler(NullHandler())
