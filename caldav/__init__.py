#!/usr/bin/env python
"""
caldav — CalDAV client library for Python.

Heavy dependencies (niquests, icalendar, lxml) are loaded lazily on first
use via PEP 562 module-level ``__getattr__``.  This keeps ``import caldav``
fast even on constrained hardware.
"""

from __future__ import annotations

import importlib
import logging

try:
    from ._version import __version__
except ModuleNotFoundError:
    __version__ = "(unknown)"
    import warnings

    warnings.warn(
        "You need to install the `build` package and do a `python -m build` "
        "to get caldav.__version__ set correctly"
    )

# Silence notification of no default logging handler
log = logging.getLogger("caldav")


class NullHandler(logging.Handler):
    def emit(self, record) -> None:
        pass


log.addHandler(NullHandler())

# ---------------------------------------------------------------------------
# Lazy import machinery (PEP 562)
# ---------------------------------------------------------------------------
# Maps public attribute names to the *caldav* submodule that provides them.
_LAZY_IMPORTS: dict[str, str] = {
    # davclient
    "DAVClient": "caldav.davclient",
    "get_calendar": "caldav.davclient",
    "get_calendars": "caldav.davclient",
    "get_davclient": "caldav.davclient",
    # base_client
    "CalendarCollection": "caldav.base_client",
    "CalendarResult": "caldav.base_client",
    # collection
    "Calendar": "caldav.collection",
    "CalendarSet": "caldav.collection",
    "Principal": "caldav.collection",
    "ScheduleMailbox": "caldav.collection",
    "ScheduleInbox": "caldav.collection",
    "ScheduleOutbox": "caldav.collection",
    "SynchronizableCalendarObjectCollection": "caldav.collection",
    # davobject
    "DAVObject": "caldav.davobject",
    # calendarobjectresource
    "CalendarObjectResource": "caldav.calendarobjectresource",
    "Event": "caldav.calendarobjectresource",
    "Todo": "caldav.calendarobjectresource",
    "Journal": "caldav.calendarobjectresource",
    "FreeBusy": "caldav.calendarobjectresource",
    # search
    "CalDAVSearcher": "caldav.search",
}

# Submodules accessible as attributes (e.g. ``caldav.error``).
_LAZY_SUBMODULES: set[str] = {"error"}

__all__ = [
    "__version__",
    *_LAZY_IMPORTS,
]


def __getattr__(name: str) -> object:
    if name in _LAZY_IMPORTS:
        module = importlib.import_module(_LAZY_IMPORTS[name])
        attr = getattr(module, name)
        # Cache on the module so __getattr__ is not called again.
        globals()[name] = attr
        return attr

    if name in _LAZY_SUBMODULES:
        module = importlib.import_module(f"caldav.lib.{name}")
        globals()[name] = module
        return module

    raise AttributeError(f"module 'caldav' has no attribute {name!r}")


def __dir__() -> list[str]:
    # Expose lazy names alongside the eagerly-defined ones.
    eager = list(globals())
    return sorted(set(eager + list(_LAZY_IMPORTS) + list(_LAZY_SUBMODULES)))
