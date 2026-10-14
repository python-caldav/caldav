"""Unit tests for the search-cache delay the integration tests apply.

A search waits only for what is left of the delay since the last write.
Purelymail's search index lags a write by ~25 s for time-range and text
searches, while a plain listing (events(), children) sees a new object at
once (probed 2026-10-14), so its profile sets ``filtered-only`` and plain
listings do not wait at all.  Bedework 3 lags in plain listings too, so
without the key every search waits.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from caldav.collection import Calendar

from .search_cache_delay import SearchCacheDelay

START = datetime(2027, 3, 1, tzinfo=timezone.utc)


@pytest.fixture
def clock():
    """A frozen clock: no time passes unless a test moves it."""
    with patch("tests.search_cache_delay.time.monotonic", return_value=1000.0) as monotonic:
        yield monotonic


def owed(state, **searchargs):
    return state.owed(Calendar(url="https://caldav.example.com/cal/"), (), searchargs)


@pytest.mark.parametrize(
    "searchargs",
    [{"event": True}, {"comp_class": None, "event": True}, {"journal": True}, {"todo": True}],
)
def test_plain_listing_owes_nothing_if_filtered_only(clock, searchargs) -> None:
    assert owed(SearchCacheDelay(180, filtered_only=True), **searchargs) == 0


def test_plain_listing_owes_the_delay_by_default(clock) -> None:
    """Bedework 3 returns stale plain listings right after a write."""
    assert owed(SearchCacheDelay(180), event=True) == 180


@pytest.mark.parametrize(
    "searchargs",
    [
        {"event": True, "start": START},
        {"event": True, "end": START},
        {"event": True, "alarm_start": START},
        {"event": True, "summary": "meeting"},
        {"event": True, "uid": "abc"},
        {"event": True, "no_category": True},
        {"todo": True, "include_completed": False},
        {"xml": "<C:calendar-query/>"},
    ],
)
def test_index_search_owes_the_delay(clock, searchargs) -> None:
    assert owed(SearchCacheDelay(180, filtered_only=True), **searchargs) == 180


def test_owes_only_the_rest_since_the_last_write(clock) -> None:
    state = SearchCacheDelay(180)
    state.note_request("PUT")
    clock.return_value = 1100.0
    assert owed(state, event=True, start=START) == 80
    ## that sleep paid the delay: the next search right after owes nothing
    clock.return_value = 1180.0
    assert owed(state, event=True, start=START) == 0


def test_a_read_does_not_restart_the_clock(clock) -> None:
    state = SearchCacheDelay(180)
    clock.return_value = 1500.0
    state.note_request("GET")
    state.note_request("REPORT")
    assert owed(state, event=True, start=START) == 0
    state.note_request("put")
    assert owed(state, event=True, start=START) == 180


@patch("tests.search_cache_delay.time.sleep")
def test_wrapped_search_sleeps_for_index_search_only(mock_sleep, clock) -> None:
    state = SearchCacheDelay(180, filtered_only=True)
    original = Mock(return_value=["found"])
    search = state.wrap_search(original)
    cal = Calendar(url="https://caldav.example.com/cal/")
    assert search(cal, event=True) == ["found"]
    mock_sleep.assert_not_called()
    search(cal, event=True, summary="meeting")
    mock_sleep.assert_called_once_with(180)
    original.assert_called_with(cal, event=True, summary="meeting")


@patch("tests.search_cache_delay.time.sleep")
def test_wrapped_request_moves_the_clock(mock_sleep, clock) -> None:
    state = SearchCacheDelay(180)
    request = state.wrap_request(Mock(return_value="response"))
    clock.return_value = 2000.0
    assert request("https://caldav.example.com/cal/x.ics", "PUT") == "response"
    clock.return_value = 2100.0
    assert owed(state, event=True, start=START) == 80


@patch("tests.search_cache_delay.asyncio.sleep")
def test_async_wrappers(mock_sleep, clock) -> None:
    state = SearchCacheDelay(180, filtered_only=True)

    async def original_search(self, *args, **kwargs):
        return ["found"]

    async def original_request(url, method="GET", *args, **kwargs):
        return "response"

    search = state.wrap_async_search(original_search)
    request = state.wrap_async_request(original_request)
    cal = Calendar(url="https://caldav.example.com/cal/")

    async def run():
        assert await request("https://caldav.example.com/cal/x.ics", "PUT") == "response"
        assert await search(cal, event=True) == ["found"]
        assert await search(cal, event=True, start=START) == ["found"]

    asyncio.run(run())
    mock_sleep.assert_called_once_with(180)


def test_from_features() -> None:
    from caldav.compatibility_hints import FeatureSet

    features = FeatureSet()
    assert SearchCacheDelay.from_features(features) is None
    features.copyFeatureSet({"search-cache": {"behaviour": "delay", "delay": 3}}, collapse=False)
    state = SearchCacheDelay.from_features(features)
    assert (state.delay, state.filtered_only) == (3, False)
    features.copyFeatureSet(
        {"search-cache": {"behaviour": "delay", "delay": 180, "filtered-only": True}},
        collapse=False,
    )
    state = SearchCacheDelay.from_features(features)
    assert (state.delay, state.filtered_only) == (180, True)
