"""The search-cache delay of the integration tests.

A server with ``search-cache: {"behaviour": "delay", "delay": N}`` answers
searches from an index that lags behind writes, so a search waits for what
is left of the delay since the client's last write.  With
``"filtered-only": True`` only a search that needs the index waits: on
Purelymail a time-range or text search finds a new object after ~25 s (the
profile allows 180 s), while a plain listing (``events()``, ``children()``)
finds it at once (probed 2026-10-14).  Bedework 3 lags in plain listings
too.

The caldav-server-tester does the same around ``CalDAVSearcher.search``
(its ``checker.py``); this one wraps ``Calendar.search``, which
``testCheckCompatibility`` unwraps while the tester runs.  It cannot see the
STATUS filters ``todos()`` adds in nested searches, so a search with
``include_completed=False`` counts as an index search.
"""

import asyncio
import inspect
import time
from functools import wraps

from caldav.collection import Calendar
from caldav.search import CalDAVSearcher

## HTTP methods that change server state
WRITE_HTTP_METHODS = frozenset(
    {"PUT", "DELETE", "MKCALENDAR", "MKCOL", "PROPPATCH", "MOVE", "COPY", "POST"}
)

_SEARCH_SIGNATURE = inspect.signature(Calendar.search)


class SearchCacheDelay:
    """The delay a search owes, counted from the client's last write.

    Before the first write it counts from now, as the server may have been
    written to just before.
    """

    def __init__(self, delay: float, filtered_only: bool = False) -> None:
        self.delay = delay
        self.filtered_only = filtered_only
        self.last_write = time.monotonic()

    @classmethod
    def from_features(cls, features) -> "SearchCacheDelay | None":
        config = features.is_supported("search-cache", dict)
        if config.get("behaviour") != "delay":
            return None
        return cls(config.get("delay", 1.5), bool(config.get("filtered-only")))

    def note_request(self, method: str) -> None:
        if str(method).upper() in WRITE_HTTP_METHODS:
            self.last_write = time.monotonic()

    def owed(self, calendar: Calendar, args: tuple, kwargs: dict) -> float:
        """How long this search must wait.  No bookkeeping is needed for a
        wait: once slept, the delay since the last write has passed."""
        remaining = self.delay - (time.monotonic() - self.last_write)
        if remaining <= 0:
            return 0
        if self.filtered_only and not _needs_search_index(calendar, args, kwargs):
            return 0
        return remaining

    def wrap_search(self, search):
        @wraps(search)
        def delayed(calendar, *args, **kwargs):
            wait = self.owed(calendar, args, kwargs)
            if wait:
                time.sleep(wait)
            return search(calendar, *args, **kwargs)

        return delayed

    def wrap_async_search(self, search):
        @wraps(search)
        async def delayed(calendar, *args, **kwargs):
            wait = self.owed(calendar, args, kwargs)
            if wait:
                await asyncio.sleep(wait)
            return await search(calendar, *args, **kwargs)

        return delayed

    def wrap_request(self, request):
        @wraps(request)
        def clocked(url, method="GET", *args, **kwargs):
            try:
                return request(url, method, *args, **kwargs)
            finally:
                self.note_request(method)

        return clocked

    def wrap_async_request(self, request):
        @wraps(request)
        async def clocked(url, method="GET", *args, **kwargs):
            try:
                return await request(url, method, *args, **kwargs)
            finally:
                self.note_request(method)

        return clocked


def _needs_search_index(calendar: Calendar, args: tuple, kwargs: dict) -> bool:
    """Whether ``calendar.search(*args, **kwargs)`` is answered from the index:
    a time or alarm range, a property filter (is-not-defined included), raw
    XML, or pending todos only."""
    bound = _SEARCH_SIGNATURE.bind(calendar, *args, **kwargs).arguments
    if bound.get("xml") or bound.get("filters"):
        return True
    searcher = CalDAVSearcher()
    calendar._populate_searcher(
        searcher, dict(bound.get("searchargs", {})), bound.get("sort_reverse", False)
    )
    return bool(
        searcher.start
        or searcher.end
        or searcher.alarm_start
        or searcher.alarm_end
        or searcher._property_filters
        or searcher._property_operator
        or searcher.include_completed is False
    )
