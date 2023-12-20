#!/usr/bin/env python
import logging

from ._version import __version__
from .davclient import DAVClient

# Silence notification of no default logging handler
log = logging.getLogger("caldav")


class NullHandler(logging.Handler):
    def emit(self, record) -> None:
        pass


log.addHandler(NullHandler())

__all__ = ["__version__", "DAVClient"]
