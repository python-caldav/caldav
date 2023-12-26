#!/usr/bin/env python
import logging

try:
    from ._version import __version__
except ModuleNotFoundError:
    __version__ = "(unknown)"
    import warnings

    warnings.warn(
        "You need to install the `build` package and do a `python -m build` to get caldav.__version__ set correctly"
    )
from .davclient import DAVClient

# Silence notification of no default logging handler
log = logging.getLogger("caldav")


class NullHandler(logging.Handler):
    def emit(self, record) -> None:
        pass


log.addHandler(NullHandler())

__all__ = ["__version__", "DAVClient"]
