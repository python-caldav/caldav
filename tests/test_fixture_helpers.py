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

from caldav import compatibility_hints
from caldav.compatibility_hints import FeatureSet
from caldav.lib import error

from .fixture_helpers import (
    _get_or_create_impl,
    adelete_calendar_if_present,
    adelete_test_calendar,
    afix_calendar,
    arelease_calendar,
    component_set_unobtainable,
    sweep_server,
    sweep_server_once,
    sweep_test_calendars,
    sweep_used_servers,
)
from .test_caldav import RepeatedFunctionalTestsBaseClass


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
        display_name: str = "",
    ) -> None:
        self.url = url
        self.display_name = display_name
        self.objects: list[FakeObject] = [FakeObject(self) for _ in range(n_objects)]
        self.deleted = False
        ## A Calendar object built from a cal_id is just a URL - the collection
        ## behind it may not exist at all, and then every request 404s.
        self.exists = exists

    async def get_display_name(self) -> str | None:
        return self.display_name

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
    is what a server that does not free the cal_id on delete (Synology, which
    refuses the DELETE; Nextcloud, which trashbins the calendar) replies with on
    the second run of a test - 405 "a collection already exists at that
    location".
    """

    def __init__(self, existing: dict[str, FakeCalendar] | None = None) -> None:
        self.calendars: dict[str, FakeCalendar] = dict(existing or {})
        self.make_calendar_calls: list[dict[str, Any]] = []
        self.calendar_calls: list[dict[str, Any]] = []

    async def make_calendar(self, **kwargs: Any) -> FakeCalendar:
        self.make_calendar_calls.append(kwargs)
        cal_id = kwargs.get("cal_id")
        if cal_id in self.calendars:
            raise error.MkcalendarError("405 Method Not Allowed - a collection already exists")
        calendar = FakeCalendar(url=f"http://dav.example.com/{cal_id}/")
        self.calendars[cal_id] = calendar
        return calendar

    async def calendar(
        self,
        name: str | None = None,
        cal_id: str | None = None,
        cal_url: str | None = None,
    ) -> FakeCalendar:
        ## Same signature as the real Principal.calendar() - cal_url included,
        ## which resolves against the *client* URL rather than the calendar
        ## home set and therefore must not be folded into cal_id.
        self.calendar_calls.append({"name": name, "cal_id": cal_id, "cal_url": cal_url})
        if cal_url is not None:
            return FakeCalendar(url=f"http://dav.example.com{cal_url}")
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


class FunctionalEvent:
    def __init__(self, calendar: "FunctionalCalendar", data: str) -> None:
        self.calendar = calendar
        self.data = data
        self.url = f"{calendar.url}event-{len(calendar.events)}.ics"


class FunctionalCalendar(FakeCalendar):
    """Small synchronous calendar adapter for the real functional test methods."""

    def __init__(self, owner: "FunctionalPrincipal", name: str | None, cal_id: str) -> None:
        super().__init__(url=f"http://dav.example.com/{cal_id}/")
        self.owner = owner
        self.cal_id = cal_id
        self.display_name = name
        self.events: list[FunctionalEvent] = []

    def add_event(self, data: str) -> FunctionalEvent:
        event = FunctionalEvent(self, data)
        self.events.append(event)
        return event

    def get_events(self) -> list[FunctionalEvent]:
        return list(self.events)

    def get_todos(self) -> list[Any]:
        return []

    def delete(self, wipe: bool | None = None) -> None:
        if wipe:
            self.events.clear()
            return
        self.owner.calendars.pop(self.cal_id, None)
        self.deleted = True


class FunctionalPrincipal(FakePrincipal):
    """Synchronous adapter over the fake calendar state used by fixture tests."""

    def make_calendar(self, **kwargs: Any) -> FunctionalCalendar:
        self.make_calendar_calls.append(kwargs)
        cal_id = kwargs.get("cal_id")
        if cal_id in self.calendars:
            raise error.MkcalendarError("405 Method Not Allowed - a collection already exists")
        if any(calendar.display_name == kwargs.get("name") for calendar in self.calendars.values()):
            raise error.MkcalendarError("409 Conflict - calendar name already exists")
        calendar = FunctionalCalendar(self, kwargs.get("name"), cal_id)
        self.calendars[cal_id] = calendar
        return calendar

    def calendar(
        self,
        name: str | None = None,
        cal_id: str | None = None,
        cal_url: str | None = None,
    ) -> FunctionalCalendar:
        self.calendar_calls.append({"name": name, "cal_id": cal_id, "cal_url": cal_url})
        if cal_url is not None:
            raise error.NotFoundError(f"no such calendar: {cal_url}")
        if cal_id is not None:
            calendar = self.calendars.get(cal_id)
            if calendar is None or (name is not None and calendar.display_name != name):
                raise error.NotFoundError(f"no such calendar: {name or cal_id}")
            return calendar
        for calendar in self.calendars.values():
            if calendar.display_name == name:
                return calendar
        raise error.NotFoundError(f"no such calendar: {name}")

    def get_calendars(self) -> list[FunctionalCalendar]:
        return list(self.calendars.values())


class FunctionalFixtureProbe(RepeatedFunctionalTestsBaseClass):
    """Adapter that keeps the production fixture methods under test synchronous."""

    def __init__(self, cleanup_regime: str = "wipe-calendar") -> None:
        self.principal = FunctionalPrincipal()
        self.caldav = FakeClient()
        self.cleanup_regime = cleanup_regime
        self.calendars_used: list[FunctionalCalendar] = []
        self._preconfigured_calendar_urls: set[str] = set()
        self.testcal_id = "pythoncaldav-test"
        self.testcal_id2 = "pythoncaldav-test2"
        self.teardown_calls: list[tuple[str | None, str | None]] = []
        self._default_calendar = None

    def is_supported(self, feature: str, return_type: type = bool, **_: Any) -> Any:
        if return_type is dict and feature == "test-calendar":
            return {}
        if return_type is str:
            return "unknown"
        return True

    def skip_unless_support(self, _: str) -> None:
        return None

    def _teardownCalendar(self, name: str | None = None, cal_id: str | None = None) -> None:
        self.teardown_calls.append((name, cal_id))
        try:
            self.principal.calendar(name=name, cal_id=cal_id).delete()
        except Exception:
            pass


def test_unicode_functional_fixtures_do_not_poison_shared_calendar_name() -> None:
    """The real event tests must leave the wipe-calendar fixture name usable."""
    fixture = FunctionalFixtureProbe()

    fixture.testUtf8Event()
    fixture.testUnicodeEvent()

    shared = fixture._fixCalendar()
    assert shared.display_name == "Yep"
    assert fixture.principal.calendar(name="Yep", cal_id=fixture.testcal_id) is shared

    utf8_calendar = fixture.principal.calendars[fixture.testcal_id + "-utf8"]
    unicode_calendar = fixture.principal.calendars[fixture.testcal_id + "-unicode"]
    assert utf8_calendar is not unicode_calendar
    assert {utf8_calendar.display_name, unicode_calendar.display_name} == {
        "Yølp UTF-8",
        "Yølp Unicode",
    }
    for calendar in (utf8_calendar, unicode_calendar):
        assert len(calendar.get_events()) == 1
        assert "Bringebærsyltetøyfestival" in calendar.get_events()[0].data


def test_unicode_fixture_ids_are_cleaned_by_known_calendar_cleanup() -> None:
    fixture = FunctionalFixtureProbe(cleanup_regime="light")

    fixture._cleanup()

    cleaned_ids = {cal_id for _, cal_id in fixture.teardown_calls}
    assert fixture.testcal_id + "-utf8" in cleaned_ids
    assert fixture.testcal_id + "-unicode" in cleaned_ids


class NoCreateCalendarProbe(FunctionalFixtureProbe):
    """A probe for a server that cannot create calendars (Posteo)."""

    def __init__(self) -> None:
        super().__init__()
        self.caldav = FakeClient({"create-calendar": False})

    def is_supported(self, feature: str, return_type: type = bool, **kw: Any) -> Any:
        if feature == "create-calendar" and return_type is bool:
            return False
        return super().is_supported(feature, return_type, **kw)


def test_sync_fixture_skips_rather_than_borrowing_a_users_calendar() -> None:
    """``_fixCalendar_`` must skip, not hand out None or the user's calendar."""
    fixture = NoCreateCalendarProbe()
    fixture.principal.calendars["personal"] = FunctionalCalendar(
        fixture.principal, "Personal", "personal"
    )

    with pytest.raises(pytest.skip.Exception, match="test-calendar"):
        fixture._fixCalendar()


def test_sync_fixture_borrows_the_calendar_at_its_cal_id() -> None:
    """Without create-calendar the sync fixture also finds a calendar by its cal_id."""
    fixture = NoCreateCalendarProbe()
    fixture.principal.calendars["personal"] = FunctionalCalendar(
        fixture.principal, "Personal", "personal"
    )
    at_cal_id = FunctionalCalendar(fixture.principal, None, fixture.testcal_id)
    fixture.principal.calendars[fixture.testcal_id] = at_cal_id

    assert fixture._fixCalendar() is at_cal_id


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

    This is the Synology/Nextcloud (and jeanes) case - ``delete-calendar
    .free-namespace`` false, whether because the DELETE is refused or because
    the calendar only moves to a trashbin: ``delete()`` degrades to a no-op
    wipe, so the leftover calendar survives and the MKCALENDAR that follows
    405s.  The helper must hand back that calendar, emptied, rather than letting
    the MkcalendarError escape.
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


@pytest.mark.asyncio
async def test_afix_calendar_keeps_calendar_when_it_cannot_be_recreated() -> None:
    """Without create-calendar there is no pre-delete: what is there gets reused.

    Posteo answers the DELETE of a calendar it does not have with 403, which
    used to error out every async test taking a calendar fixture.
    """
    from caldav.lib.error import AuthorizationError

    existing = FakeCalendar(url="http://dav.example.com/testcal/")
    client = FakeClient({"create-calendar": False})
    principal = FakePrincipal({"testcal": existing})

    async def delete(wipe: bool | None = None) -> None:
        raise AuthorizationError("Forbidden")

    existing.delete = delete  # type: ignore[method-assign]

    calendar, created = await afix_calendar(client, principal, cal_id="testcal")

    assert calendar is existing
    assert not created


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
async def test_a_calendar_of_the_user_is_never_borrowed() -> None:
    """Without create-calendar, only a calendar set aside for the tests may be used.

    The tests wipe the calendar they get.  Falling back to whatever calendar
    the server lists first would wipe the user's own data - on Posteo, which
    cannot create calendars, that is the account's default calendar.
    """
    users_own = FakeCalendar(url="http://dav.example.com/personal/", n_objects=5)
    client = FakeClient({"create-calendar": False})
    principal = FakePrincipal({"personal": users_own})

    calendar, created = await afix_calendar(client, principal, cal_id="testcal")

    assert calendar is None
    assert not created
    assert len(users_own.objects) == 5, "the user's calendar must not be wiped"


@pytest.mark.asyncio
async def test_a_calendar_failing_mkcalendar_does_not_borrow_another() -> None:
    """MKCALENDAR refused on a server claiming support: still no first-calendar fallback."""
    users_own = FakeCalendar(url="http://dav.example.com/personal/", n_objects=1)
    principal = FakePrincipal({"personal": users_own})

    async def make_calendar(**kwargs: Any) -> FakeCalendar:
        raise error.AuthorizationError("Forbidden")

    principal.make_calendar = make_calendar  # type: ignore[method-assign]

    calendar, created = await _get_or_create_impl(FakeClient(), principal)

    assert calendar is None
    assert not created


@pytest.mark.asyncio
async def test_a_calendar_named_for_the_tests_is_borrowed() -> None:
    """A display name containing ``pythoncaldav-test`` is the user's opt-in."""
    users_own = FakeCalendar(url="http://dav.example.com/personal/")
    set_aside = FakeCalendar(url="http://dav.example.com/other/", display_name="pythoncaldav-test")
    client = FakeClient({"create-calendar": False})
    principal = FakePrincipal({"personal": users_own, "other": set_aside})

    calendar, created = await _get_or_create_impl(client, principal)

    assert calendar is set_aside
    assert not created


@pytest.mark.parametrize(
    "url",
    ["http://dav.example.com/p%C3%B8-cal/", "http://dav.example.com/p%C3%B8-cal"],
    ids=["trailing-slash", "no-trailing-slash"],
)
@pytest.mark.asyncio
async def test_a_calendar_at_the_cal_id_is_borrowed(url: str) -> None:
    """The fixture's own cal_id is matched against the URL-quoted last path segment."""
    users_own = FakeCalendar(url="http://dav.example.com/personal/")
    at_cal_id = FakeCalendar(url=url)
    client = FakeClient({"create-calendar": False})
    principal = FakePrincipal({"personal": users_own, "pø-cal": at_cal_id})

    calendar, created = await _get_or_create_impl(client, principal, cal_id="pø-cal")

    assert calendar is at_cal_id
    assert not created


@pytest.mark.asyncio
async def test_configured_test_calendar_is_looked_up_and_awaited() -> None:
    """A ``test-calendar`` name/cal_id in the server config short-circuits creation.

    Only the keys ``principal.calendar()`` accepts may be forwarded; the same
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


@pytest.mark.asyncio
async def test_configured_cal_url_is_forwarded_as_cal_url() -> None:
    """A ``test-calendar`` config carrying ``cal_url`` must not be folded into ``cal_id``.

    ``Principal.calendar()`` accepts all three of ``name``/``cal_id``/``cal_url``,
    and they are not interchangeable: ``cal_url`` is joined against the *client*
    URL and used verbatim, whereas ``cal_id`` is URL-quoted and joined against
    the calendar home set - which on an async client also costs a PROPFIND that
    the ``cal_url`` path deliberately avoids.
    """
    client = FakeClient(
        {"test-calendar": {"cal_url": "/dav/user/calendars/mycal/", "cleanup-regime": "thorough"}}
    )
    principal = FakePrincipal()

    calendar, created = await _get_or_create_impl(client, principal, cal_id="testcal")

    assert not created
    assert principal.make_calendar_calls == []
    assert principal.calendar_calls == [
        {"name": None, "cal_id": None, "cal_url": "/dav/user/calendars/mycal/"}
    ]
    assert calendar.url == "http://dav.example.com/dav/user/calendars/mycal/"


@pytest.mark.asyncio
async def test_afix_calendar_keeps_a_name_the_caller_says_matters() -> None:
    """``keep_name`` mirrors ``_fixCalendar_``'s ``if "name" not in kwargs`` rule.

    The sync fixture only drops the display name when the *caller gave none*; a
    test that passes a name explicitly - ``testUtf8Event`` with ``name="Yølp"`` -
    always sends it, precisely because the name is what that test is about.
    Async callers always pass a name (the fixtures use the cal_id as filler), so
    the distinction has to be explicit rather than inferred from ``is None``.
    """
    client = FakeClient({"create-calendar.set-displayname": False})
    principal = FakePrincipal()

    await afix_calendar(client, principal, cal_id="testcal", calendar_name="Yølp", keep_name=True)

    assert principal.make_calendar_calls == [{"name": "Yølp", "cal_id": "testcal"}]


@pytest.mark.asyncio
async def test_afix_calendar_drops_name_for_component_restricted_calendar() -> None:
    """The ``restricted`` leg of ``_fixCalendar_``'s rule: VTODO-only stays nameless.

    A component-restricted fixture is only ever looked up by cal_id, and naming
    it can collide on servers enforcing per-principal unique calendar names
    (SOGo).  The server here is fully capable, so only ``restricted`` can be
    what drops the name.
    """
    client = FakeClient()
    principal = FakePrincipal()

    await afix_calendar(
        client,
        principal,
        cal_id="testcal-tasks",
        calendar_name="Tasks",
        supported_calendar_component_set=["VTODO"],
    )

    assert principal.make_calendar_calls == [
        {"cal_id": "testcal-tasks", "supported_calendar_component_set": ["VTODO"]}
    ]


IGNORED = {"create-calendar.with-supported-component-types": False}


@pytest.mark.parametrize(
    ("hints", "comp_set", "unobtainable"),
    [
        ({}, ["VTODO"], False),
        ({}, None, False),
        ## The restriction is ignored, but tasks go into an event calendar anyway.
        (IGNORED, ["VTODO"], False),
        ## Zimbra: no mixing, but a VTODO-only calendar is honoured.
        ({"save-load.todo.mixed-calendar": False}, ["VTODO"], False),
        ## Bedework 5: neither, so there is nowhere to put a task.
        (IGNORED | {"save-load.todo.mixed-calendar": False}, ["VTODO"], True),
        (IGNORED | {"save-load.todo.mixed-calendar": False}, ["VJOURNAL"], False),
        (IGNORED | {"save-load.journal.mixed-calendar": False}, ["VJOURNAL"], True),
        (IGNORED | {"save-load.todo.mixed-calendar": False}, ["VEVENT", "VTODO"], False),
    ],
)
def test_component_set_unobtainable(
    hints: dict, comp_set: list[str] | None, unobtainable: bool
) -> None:
    """A restricted calendar is out of reach only when the restriction is ignored
    *and* the component cannot share a calendar with events."""
    assert bool(component_set_unobtainable(FakeClient(hints), comp_set)) is unobtainable


def test_bedework_5_has_nowhere_to_put_a_task() -> None:
    client = FakeClient(compatibility_hints.bedework_5_0_0)
    assert component_set_unobtainable(client, ["VTODO"])


## Where a restricted calendar is out of reach, as it was before the
## component-set features were split into creation and obedience: the split
## must not move any profile in or out of this list.
UNOBTAINABLE = {
    ("bedework_5_0_0", "VTODO"),
    ("bedework_5_0_0", "VJOURNAL"),
    ("sogo", "VJOURNAL"),
    ("posteo", "VJOURNAL"),
    ("yahoo", "VTODO"),
    ("yahoo", "VJOURNAL"),
}


def _profile_names() -> list[str]:
    return [
        name
        for name, profile in vars(compatibility_hints).items()
        if isinstance(profile, dict) and not name.startswith("_") and name.islower()
    ]


@pytest.mark.parametrize("profile", _profile_names())
@pytest.mark.parametrize("component", ["VTODO", "VJOURNAL"])
def test_unobtainable_component_sets_per_profile(profile: str, component: str) -> None:
    """Obeying the set is not what the fixtures ask: they ask whether a calendar
    created for ``component`` takes it.  Bedework 3 lets a VEVENT into a
    VTODO-only calendar, and still a VJOURNAL-only calendar is there for the
    journals it cannot mix with events."""
    from caldav.config import resolve_features

    client = FakeClient(resolve_features(profile))
    unobtainable = bool(component_set_unobtainable(client, [component]))
    assert unobtainable is ((profile, component) in UNOBTAINABLE)


class SweepResponse:
    def __init__(self, status: int) -> None:
        self.status = status


class SweepClient(FakeClient):
    """Sync client that records the DELETEs a sweep sends."""

    def __init__(self, hints: dict[str, Any] | None = None, status: int = 204) -> None:
        super().__init__(hints)
        self.status = status
        self.deletes: list[tuple[str, dict[str, str] | None]] = []

    def delete(self, url: str, headers: dict[str, str] | None = None) -> SweepResponse:
        self.deletes.append((url, headers))
        if self.status in (401, 403):
            ## The real client raises on these rather than returning them.
            raise error.AuthorizationError(url=url, reason=str(self.status))
        return SweepResponse(self.status)


class SweepPrincipal:
    def __init__(self, *cal_ids: str, lingering: int = 0) -> None:
        self.cal_ids = list(cal_ids)
        ## Listings that still show a deleted calendar, as on a server
        ## deleting asynchronously.
        self.lingering = lingering
        self.listings = 0

    def get_calendars(self) -> list[FakeCalendar]:
        self.listings += 1
        if self.listings > 1 and self.lingering:
            self.lingering -= 1
        elif self.listings > 1:
            self.cal_ids = [c for c in self.cal_ids if not c.startswith("pythoncaldav-")]
        return [FakeCalendar(url=f"http://dav.example.com/cals/{c}/") for c in self.cal_ids]


def test_sweep_deletes_only_test_calendars_and_skips_the_trashbin() -> None:
    """Leftover pythoncaldav-* calendars go, for good; the user's calendars stay.

    On Nextcloud a plain DELETE moves the calendar to a trashbin that still
    counts towards the account's calendar limit, hence the header.
    """
    client = SweepClient()
    principal = SweepPrincipal(
        "personal", "pythoncaldav-test", "pythoncaldav-test-tasks", "9b0c663d-b3b0", "testcal"
    )

    deleted = sweep_test_calendars(client, principal)

    assert deleted == ["pythoncaldav-test", "pythoncaldav-test-tasks"]
    assert [url for url, _ in client.deletes] == [
        "http://dav.example.com/cals/pythoncaldav-test/",
        "http://dav.example.com/cals/pythoncaldav-test-tasks/",
    ]
    assert all(h == {"X-NC-CalDAV-No-Trashbin": "1"} for _, h in client.deletes)


@pytest.mark.parametrize(
    "hints",
    [
        ## Nothing can be recreated: whatever is there was set up by hand.
        {"create-calendar": {"support": "unsupported"}},
        {"delete-calendar": {"support": "unsupported"}},
        ## A calendar configured for the tests must survive the sweep.
        {"test-calendar": {"cal_id": "pythoncaldav-test"}},
        {"test-calendar": {"cleanup-regime": "none"}},
    ],
)
def test_sweep_leaves_calendars_it_cannot_recreate(hints: dict[str, Any]) -> None:
    client = SweepClient(hints)

    assert sweep_test_calendars(client, SweepPrincipal("pythoncaldav-test")) == []
    assert client.deletes == []


def test_sweep_does_not_count_a_refused_delete() -> None:
    client = SweepClient(status=403)

    assert sweep_test_calendars(client, SweepPrincipal("pythoncaldav-test")) == []


def test_sweep_goes_on_past_a_refused_delete() -> None:
    """A 403 on one calendar must not leave the others behind."""
    client = SweepClient(status=403)

    sweep_test_calendars(client, SweepPrincipal("pythoncaldav-test", "pythoncaldav-test2"))

    assert len(client.deletes) == 2


def test_sweep_matches_the_decoded_prefix_only() -> None:
    """Percent-encoded ids are decoded; a lookalike or a name is no match."""
    client = SweepClient()
    principal = SweepPrincipal("pythoncaldav%2Dtest", "xpythoncaldav-test", "my-pythoncaldav-test")

    assert sweep_test_calendars(client, principal) == ["pythoncaldav-test"]


def test_sweep_waits_for_an_asynchronous_deletion(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fixture re-creating the id must not meet the calendar on its way out."""
    import tests.fixture_helpers as fh

    monkeypatch.setattr(fh.time, "sleep", lambda s: None)
    client = SweepClient(
        {"synchronous-write.delete-calendar": {"support": "unsupported", "delay": 20}}
    )
    principal = SweepPrincipal("personal", "pythoncaldav-test", lingering=2)

    sweep_test_calendars(client, principal)

    ## the listing to sweep, two still showing it, one without it
    assert principal.listings == 4


class FakeRegistry:
    def __init__(self, servers: dict[str, Any]) -> None:
        self.servers = servers

    def get(self, name: str) -> Any:
        return self.servers.get(name)


@pytest.fixture
def swept(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record which servers get swept, with the registry and sweep faked."""
    import caldav.testing.registry
    import tests.fixture_helpers as fh
    from caldav.testing.base import ExternalTestServer

    class External(ExternalTestServer):
        def __init__(self, name: str) -> None:
            self.name = name

        def get_sync_client(self) -> Any:
            name = self.name

            class Client:
                def __enter__(self) -> Any:
                    return self

                def __exit__(self, *a: Any) -> None:
                    pass

                def principal(self) -> str:
                    return name

            return Client()

    class Docker:
        def get_sync_client(self) -> Any:
            raise AssertionError("a docker server must not be swept")

    registry = FakeRegistry(
        {"ecloud": External("ecloud"), "gmx": External("gmx"), "baikal": Docker()}
    )
    monkeypatch.setattr(caldav.testing.registry, "get_registry", lambda: registry)
    monkeypatch.setattr(fh, "_swept_servers", set())
    calls: list[str] = []
    monkeypatch.setattr(
        fh, "sweep_test_calendars", lambda client, principal: calls.append(principal) or []
    )
    return calls


def test_sweep_server_leaves_non_external_servers_alone(swept: list[str]) -> None:
    sweep_server("baikal")
    sweep_server("not-registered")

    assert swept == []


def test_sweep_once_per_server_then_again_at_session_end(swept: list[str]) -> None:
    for name in ("ecloud", "gmx", "ecloud", None):
        sweep_server_once(name)
    assert swept == ["ecloud", "gmx"]

    sweep_used_servers()
    assert swept == ["ecloud", "gmx", "ecloud", "gmx"]


@pytest.mark.asyncio
@pytest.mark.parametrize("frees", [True, False])
async def test_delete_test_calendar_skips_the_trashbin_where_it_would_keep_the_id(
    frees: bool,
) -> None:
    """Where a plain DELETE leaves the id taken (Nextcloud's trashbin), the
    calendar goes for good; elsewhere Calendar.delete() does it, with its
    retries and its wait for an asynchronous deletion."""
    client = SweepClient({"delete-calendar.free-namespace": frees})
    cal = FakeCalendar(url="http://dav.example.com/cals/pythoncaldav-test2/")

    await adelete_test_calendar(client, cal)

    assert cal.deleted is frees
    assert client.deletes == (
        []
        if frees
        else [("http://dav.example.com/cals/pythoncaldav-test2/", {"X-NC-CalDAV-No-Trashbin": "1"})]
    )


@pytest.mark.asyncio
async def test_delete_if_present_skips_the_trashbin_given_the_client() -> None:
    """A leftover cleared before re-creating its id must not land in the
    trashbin, or the MKCALENDAR that follows meets the id still taken."""
    url = "http://dav.example.com/cals/pythoncaldav-async-mkcalendar/"
    principal = FakePrincipal({"pythoncaldav-async-mkcalendar": FakeCalendar(url=url)})
    client = SweepClient({"delete-calendar.free-namespace": False})

    await adelete_calendar_if_present(principal, "pythoncaldav-async-mkcalendar", client=client)

    assert client.deletes == [(url, {"X-NC-CalDAV-No-Trashbin": "1"})]


@pytest.mark.asyncio
async def test_delete_test_calendar_wipes_where_deletion_is_unsupported() -> None:
    """Synology refuses the DELETE; Calendar.delete() wipes the objects there."""
    client = SweepClient(
        {"delete-calendar": {"support": "unsupported"}, "delete-calendar.free-namespace": False}
    )
    cal = FakeCalendar(url="http://dav.example.com/cals/pythoncaldav-test2/")

    await adelete_test_calendar(client, cal)

    assert cal.deleted
    assert client.deletes == []


def test_sweep_does_not_count_a_delete_answered_500() -> None:
    client = SweepClient(status=500)

    assert (
        sweep_test_calendars(client, SweepPrincipal("pythoncaldav-test", "pythoncaldav-test2"))
        == []
    )
    assert len(client.deletes) == 2


def test_sweep_server_survives_a_failing_sweep(
    swept: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Best effort: a server that breaks the sweep must not fail the session."""
    import tests.fixture_helpers as fh

    def boom(client: Any, principal: Any) -> list[str]:
        raise error.DAVError("server fell over")

    monkeypatch.setattr(fh, "sweep_test_calendars", boom)

    sweep_server("ecloud")
