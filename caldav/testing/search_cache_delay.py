"""The search-cache delay of the integration tests, for downstream test suites too.

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

A downstream suite wraps the same way: ``Calendar.search`` with
``wrap_search()``, and its client's ``request`` with ``wrap_request()``.
Two things to know: wrapping ``Calendar.search`` changes the class, for
every client, so undo it when the test is done (``monkeypatch.setattr``
does); and only writes through the wrapped client move the clock, so a
search right after a write through another client may not wait long enough.
"""

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from caldav.collection import Calendar
from caldav.compatibility_hints import FeatureSet
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
        """``delay`` in seconds; ``filtered_only``: only a search that needs the index waits."""
        self.delay = delay
        self.filtered_only = filtered_only
        self.last_write = time.monotonic()

    @classmethod
    def from_features(cls, features: FeatureSet) -> "SearchCacheDelay | None":
        """The delay the server's ``search-cache`` hint gives (1.5 s if it names none);
        ``None`` unless its behaviour is ``delay``."""
        config = features.is_supported("search-cache", dict)
        if config.get("behaviour") != "delay":
            return None
        return cls(config.get("delay", 1.5), bool(config.get("filtered-only")))

    def note_request(self, method: str) -> None:
        """Start the clock again if ``method`` is a write."""
        if str(method).upper() in WRITE_HTTP_METHODS:
            self.last_write = time.monotonic()

    def remaining(self) -> float:
        """What is left of the delay since the last write, whatever is asked.  On a
        server that lags in plain listings too, a caller should sleep this long
        before a listing (a PROPFIND) of its own: nothing here makes it wait."""
        return max(0.0, self.delay - (time.monotonic() - self.last_write))

    def owed(self, calendar: Calendar, args: tuple[Any, ...], kwargs: dict[str, Any]) -> float:
        """How long this search must wait.  No bookkeeping is needed for a
        wait: once slept, the delay since the last write has passed."""
        remaining = self.remaining()
        if remaining <= 0:
            return 0.0
        if self.filtered_only and not _needs_search_index(calendar, args, kwargs):
            return 0.0
        return remaining

    def wrap_search(self, search: Callable[..., Any]) -> Callable[..., Any]:
        """``Calendar.search`` (unbound: the calendar comes first), sleeping what it owes first."""

        @wraps(search)
        def delayed(calendar: Calendar, *args: Any, **kwargs: Any) -> Any:
            wait = self.owed(calendar, args, kwargs)
            if wait:
                time.sleep(wait)
            return search(calendar, *args, **kwargs)

        return delayed

    def wrap_async_search(self, search: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
        """``wrap_search()`` for an async client: the wrapped search is awaited."""

        @wraps(search)
        async def delayed(calendar: Calendar, *args: Any, **kwargs: Any) -> Any:
            wait = self.owed(calendar, args, kwargs)
            if wait:
                await asyncio.sleep(wait)
            return await search(calendar, *args, **kwargs)

        return delayed

    def wrap_request(self, request: Callable[..., Any]) -> Callable[..., Any]:
        """A client's bound ``request(url, method, ...)``, noting each write."""

        @wraps(request)
        def clocked(url: Any, method: str = "GET", *args: Any, **kwargs: Any) -> Any:
            try:
                return request(url, method, *args, **kwargs)
            finally:
                self.note_request(method)

        return clocked

    def wrap_async_request(self, request: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
        """``wrap_request()`` for an async client."""

        @wraps(request)
        async def clocked(url: Any, method: str = "GET", *args: Any, **kwargs: Any) -> Any:
            try:
                return await request(url, method, *args, **kwargs)
            finally:
                self.note_request(method)

        return clocked


def _needs_search_index(calendar: Calendar, args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
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
