"""Unit tests for the test-suite's own calendar fixture helpers.

``tests/fixture_helpers.py`` is what every functional test uses to get hold of
a test calendar, and it is full of server-capability branches that only trigger
against particular real servers.  These tests drive those branches with fakes so
a regression shows up in a two-second unit run rather than in an integration run
against one specific external server.

Fakes are fine here: this is a unit test *of the test infrastructure*, not an
integration test.
"""

from typing import Any

import pytest

from caldav.compatibility_hints import FeatureSet
from caldav.lib import error

from .fixture_helpers import (
    _get_or_create_impl,
    afix_calendar,
    arelease_calendar,
)


class FakeObject:
    def __init__(self, calendar: "FakeCalendar") -> None:
        self.calendar = calendar

    async def delete(self) -> None:
        self.calendar.objects.remove(self)


class FakeCalendar:
    def __init__(
        self,
        url: str = "http://dav.example.com/cal/",
        n_objects: int = 0,
        exists: bool = True,
    ) -> None:
        self.url = url
        self.objects: list[FakeObject] = [FakeObject(self) for _ in range(n_objects)]
        self.deleted = False
        ## A Calendar object built from a cal_id is just a URL - the collection
        ## behind it may not exist at all, and then every request 404s.
        self.exists = exists

    async def search(self) -> list[FakeObject]:
        if not self.exists:
            raise error.NotFoundError(f"no collection at {self.url}")
        return list(self.objects)

    async def delete(self, wipe: bool | None = None) -> None:
        if not self.exists:
            raise error.NotFoundError(f"no collection at {self.url}")
        self.deleted = True


class FakePrincipal:
    """Principal that only lets a calendar be created once, like a real server.

    A second MKCALENDAR at the same cal_id fails with ``MkcalendarError``, which
    is what a server whose calendars cannot be deleted (Synology, Nextcloud)
    replies with on the second run of a test - 405 "a collection already exists
    at that location".
    """

    def __init__(self, existing: dict[str, FakeCalendar] | None = None) -> None:
        self.calendars: dict[str, FakeCalendar] = dict(existing or {})
        self.make_calendar_calls: list[dict[str, Any]] = []

    async def make_calendar(self, **kwargs: Any) -> FakeCalendar:
        self.make_calendar_calls.append(kwargs)
        cal_id = kwargs.get("cal_id")
        if cal_id in self.calendars:
            raise error.MkcalendarError("405 Method Not Allowed - a collection already exists")
        calendar = FakeCalendar(url=f"http://dav.example.com/{cal_id}/")
        self.calendars[cal_id] = calendar
        return calendar

    async def calendar(self, name: str | None = None, cal_id: str | None = None) -> FakeCalendar:
        if cal_id is not None:
            ## Like the real thing: a cal_id lookup does no I/O, it just builds a
            ## URL.  Whether anything lives there is discovered on first use.
            if cal_id in self.calendars:
                return self.calendars[cal_id]
            return FakeCalendar(url=f"http://dav.example.com/{cal_id}/", exists=False)
        raise error.NotFoundError(f"no such calendar: {name}")

    async def get_calendars(self) -> list[FakeCalendar]:
        return list(self.calendars.values())


class FakeClient:
    def __init__(self, hints: dict[str, Any] | None = None) -> None:
        self.features = FeatureSet(hints or {})


@pytest.mark.asyncio
async def test_afix_calendar_creates_and_names() -> None:
    """Happy path: fresh calendar, display name set, deleted again on release."""
    client = FakeClient()
    principal = FakePrincipal()

    calendar, created = await afix_calendar(
        client, principal, cal_id="testcal", calendar_name="Yep"
    )

    assert created
    assert principal.make_calendar_calls == [{"name": "Yep", "cal_id": "testcal"}]

    await arelease_calendar(client, calendar, created)
    assert calendar.deleted


@pytest.mark.asyncio
async def test_afix_calendar_reuses_and_wipes_when_calendar_cannot_be_deleted() -> None:
    """A leftover calendar on a no-delete server is reused and emptied.

    This is the Synology/Nextcloud (and jeanes) case: ``delete()`` degrades to a
    no-op wipe, so the leftover calendar survives and the MKCALENDAR that
    follows 405s.  The helper must hand back that calendar, emptied, rather than
    letting the MkcalendarError escape.
    """
    leftover = FakeCalendar(url="http://dav.example.com/testcal/", n_objects=3)
    client = FakeClient({"delete-calendar": False})
    principal = FakePrincipal({"testcal": leftover})

    calendar, created = await afix_calendar(
        client, principal, cal_id="testcal", calendar_name="Yølp"
    )

    assert calendar is leftover
    assert not created
    assert calendar.objects == [], "the reused calendar should have been wiped"
    assert not calendar.deleted, "a calendar we did not create must not be deleted"

    await arelease_calendar(client, calendar, created)
    assert not calendar.deleted


@pytest.mark.asyncio
async def test_afix_calendar_deletes_leftover_when_deletion_frees_the_url() -> None:
    """On a well-behaved server the leftover is deleted and a fresh one created."""
    leftover = FakeCalendar(url="http://dav.example.com/testcal/", n_objects=2)
    client = FakeClient()
    principal = FakePrincipal({"testcal": leftover})

    ## adelete_calendar_if_present() is expected to remove it from the server,
    ## which our fake models by dropping it from the dict.
    async def delete(wipe: bool | None = None) -> None:
        leftover.deleted = True
        del principal.calendars["testcal"]

    leftover.delete = delete  # type: ignore[method-assign]

    calendar, created = await afix_calendar(client, principal, cal_id="testcal")

    assert leftover.deleted
    assert created
    assert calendar is not leftover


@pytest.mark.parametrize(
    "hints",
    [
        {"create-calendar.set-displayname": False},
        {"create-calendar.stable-url": False},
    ],
    ids=["no-set-displayname", "no-stable-url"],
)
@pytest.mark.asyncio
async def test_afix_calendar_drops_name_when_server_cannot_keep_it(hints: dict) -> None:
    """Mirrors _fixCalendar_: nameless fixture unless the name sticks at the cal_id."""
    client = FakeClient(hints)
    principal = FakePrincipal()

    await afix_calendar(client, principal, cal_id="testcal", calendar_name="Yep")

    assert principal.make_calendar_calls == [{"cal_id": "testcal"}]


@pytest.mark.asyncio
async def test_afix_calendar_returns_none_when_nothing_can_be_had() -> None:
    """No creation support and no calendars on the server: the caller must skip."""
    client = FakeClient({"create-calendar": False})
    principal = FakePrincipal()

    calendar, created = await afix_calendar(client, principal, cal_id="testcal")

    assert calendar is None
    assert not created
    ## arelease_calendar must tolerate that None rather than blowing up in teardown
    await arelease_calendar(client, calendar, created)


@pytest.mark.asyncio
async def test_configured_test_calendar_is_looked_up_and_awaited() -> None:
    """A ``test-calendar`` name/cal_id in the server config short-circuits creation.

    Only the keys ``principal.calendar()` accepts may be forwarded; the same
    config dict also carries ``cleanup-regime`` (and FeatureSet may add
    ``support``), and the async lookup returns a coroutine that must be awaited.
    """
    configured = FakeCalendar(url="http://dav.example.com/configured/")
    client = FakeClient(
        {"test-calendar": {"cal_id": "configured", "cleanup-regime": "wipe-calendar"}}
    )
    principal = FakePrincipal({"configured": configured})

    calendar, created = await _get_or_create_impl(client, principal, cal_id="testcal")

    assert calendar is configured
    assert not created
    assert principal.make_calendar_calls == []
