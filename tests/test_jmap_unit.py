"""
Unit tests for the caldav.jmap package.

Rule: zero network calls, zero Docker dependency, all tests are fast.
External HTTP is mocked via unittest.mock wherever needed.
"""

from unittest.mock import MagicMock, patch

import pytest

try:
    from niquests.auth import HTTPBasicAuth
except ImportError:
    from requests.auth import HTTPBasicAuth  # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# Shared test fixtures (module-level constants — not hardcoded inline)
# ---------------------------------------------------------------------------

_JMAP_URL = "http://localhost:8802/.well-known/jmap"
_API_URL = "http://localhost:8802/jmap/api"
_USERNAME = "user1"
_PASSWORD = "x"

# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------

from caldav.jmap.error import (
    JMAPAuthError,
    JMAPCapabilityError,
    JMAPError,
    JMAPMethodError,
)
from caldav.lib.error import AuthorizationError, DAVError


class TestJMAPErrorHierarchy:
    def test_jmap_error_is_dav_error(self):
        assert issubclass(JMAPError, DAVError)

    def test_jmap_capability_error_is_jmap_error(self):
        assert issubclass(JMAPCapabilityError, JMAPError)

    def test_jmap_auth_error_is_authorization_error(self):
        assert issubclass(JMAPAuthError, AuthorizationError)

    def test_jmap_auth_error_is_jmap_error(self):
        assert issubclass(JMAPAuthError, JMAPError)

    def test_jmap_method_error_is_jmap_error(self):
        assert issubclass(JMAPMethodError, JMAPError)

    def test_jmap_error_default_error_type(self):
        e = JMAPError()
        assert e.error_type == "serverError"

    def test_jmap_error_custom_error_type(self):
        e = JMAPError(error_type="unknownMethod")
        assert e.error_type == "unknownMethod"

    def test_jmap_error_str_contains_type(self):
        e = JMAPError(url="http://example.com", reason="boom", error_type="invalidArguments")
        s = str(e)
        assert "invalidArguments" in s
        assert "boom" in s
        assert "http://example.com" in s

    def test_jmap_capability_error_default_type(self):
        e = JMAPCapabilityError()
        assert e.error_type == "capabilityNotSupported"

    def test_jmap_auth_error_default_type(self):
        e = JMAPAuthError()
        assert e.error_type == "forbidden"

    def test_jmap_method_error_custom_type(self):
        e = JMAPMethodError(error_type="stateMismatch", reason="state changed")
        assert e.error_type == "stateMismatch"
        assert e.reason == "state changed"

    def test_jmap_error_catchable_as_dav_error(self):
        with pytest.raises(DAVError):
            raise JMAPMethodError(error_type="notFound")

    def test_jmap_auth_error_catchable_as_authorization_error(self):
        with pytest.raises(AuthorizationError):
            raise JMAPAuthError()


# ---------------------------------------------------------------------------
# Session establishment
# ---------------------------------------------------------------------------

from caldav.jmap.constants import CALENDAR_CAPABILITY
from caldav.jmap.session import Session, fetch_session

# Minimal valid Session JSON fixture
_SESSION_JSON = {
    "apiUrl": _API_URL,
    "state": "state-abc",
    "capabilities": {
        "urn:ietf:params:jmap:core": {"maxCallsInRequest": 32},
        CALENDAR_CAPABILITY: {},
    },
    "accounts": {
        _USERNAME: {
            "name": f"{_USERNAME}@example.com",
            "isPersonalAccount": True,
            "accountCapabilities": {
                CALENDAR_CAPABILITY: {},
            },
        }
    },
}


def _make_mock_response(json_data, status_code=200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestFetchSession:
    def test_parses_api_url(self):
        with patch("caldav.jmap.session.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(_SESSION_JSON)
            session = fetch_session(_JMAP_URL, auth=None)
        assert session.api_url == _API_URL

    def test_parses_account_id(self):
        with patch("caldav.jmap.session.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(_SESSION_JSON)
            session = fetch_session(_JMAP_URL, auth=None)
        assert session.account_id == _USERNAME

    def test_parses_state(self):
        with patch("caldav.jmap.session.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(_SESSION_JSON)
            session = fetch_session(_JMAP_URL, auth=None)
        assert session.state == "state-abc"

    def test_parses_account_capabilities(self):
        with patch("caldav.jmap.session.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(_SESSION_JSON)
            session = fetch_session(_JMAP_URL, auth=None)
        assert CALENDAR_CAPABILITY in session.account_capabilities

    def test_raw_is_full_response(self):
        with patch("caldav.jmap.session.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(_SESSION_JSON)
            session = fetch_session(_JMAP_URL, auth=None)
        assert session.raw == _SESSION_JSON

    def test_raises_auth_error_on_401(self):
        with patch("caldav.jmap.session.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response({}, status_code=401)
            with pytest.raises(JMAPAuthError):
                fetch_session(_JMAP_URL, auth=None)

    def test_raises_auth_error_on_403(self):
        with patch("caldav.jmap.session.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response({}, status_code=403)
            with pytest.raises(JMAPAuthError):
                fetch_session(_JMAP_URL, auth=None)

    def test_raises_capability_error_when_no_calendar_account(self):
        data = dict(_SESSION_JSON)
        data["accounts"] = {
            _USERNAME: {
                "name": f"{_USERNAME}@example.com",
                "isPersonalAccount": True,
                "accountCapabilities": {
                    "urn:ietf:params:jmap:mail": {},  # no calendars
                },
            }
        }
        with patch("caldav.jmap.session.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(data)
            with pytest.raises(JMAPCapabilityError):
                fetch_session(_JMAP_URL, auth=None)

    def test_raises_capability_error_when_no_accounts(self):
        data = dict(_SESSION_JSON)
        data["accounts"] = {}
        with patch("caldav.jmap.session.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(data)
            with pytest.raises(JMAPCapabilityError):
                fetch_session(_JMAP_URL, auth=None)

    def test_raises_capability_error_when_missing_api_url(self):
        data = dict(_SESSION_JSON)
        del data["apiUrl"]
        with patch("caldav.jmap.session.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(data)
            with pytest.raises(JMAPCapabilityError):
                fetch_session(_JMAP_URL, auth=None)

    def test_picks_first_calendar_capable_account(self):
        data = dict(_SESSION_JSON)
        data["accounts"] = {
            "user_mail_only": {
                "name": "mailonly@example.com",
                "isPersonalAccount": True,
                "accountCapabilities": {"urn:ietf:params:jmap:mail": {}},
            },
            "user_calendar": {
                "name": "calendar@example.com",
                "isPersonalAccount": True,
                "accountCapabilities": {CALENDAR_CAPABILITY: {}},
            },
        }
        with patch("caldav.jmap.session.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(data)
            session = fetch_session(_JMAP_URL, auth=None)
        assert session.account_id == "user_calendar"


# ---------------------------------------------------------------------------
# Calendar domain object
# ---------------------------------------------------------------------------

from caldav.jmap.objects.calendar import JMAPCalendar

_CALENDAR_JSON_FULL = {
    "id": "cal1",
    "name": "Personal",
    "description": "My personal calendar",
    "color": "#3a86ff",
    "isSubscribed": True,
    "myRights": {"mayReadItems": True, "mayAddItems": True},
    "sortOrder": 1,
    "isVisible": True,
}

_CALENDAR_JSON_MINIMAL = {
    "id": "cal2",
    "name": "Work",
}


class TestJMAPCalendar:
    def test_from_jmap_full(self):
        cal = JMAPCalendar.from_jmap(_CALENDAR_JSON_FULL)
        assert cal.id == "cal1"
        assert cal.name == "Personal"
        assert cal.description == "My personal calendar"
        assert cal.color == "#3a86ff"
        assert cal.is_subscribed is True
        assert cal.my_rights == {"mayReadItems": True, "mayAddItems": True}
        assert cal.sort_order == 1
        assert cal.is_visible is True

    def test_from_jmap_minimal_uses_defaults(self):
        cal = JMAPCalendar.from_jmap(_CALENDAR_JSON_MINIMAL)
        assert cal.id == "cal2"
        assert cal.name == "Work"
        assert cal.description is None
        assert cal.color is None
        assert cal.is_subscribed is True
        assert cal.my_rights == {}
        assert cal.sort_order == 0
        assert cal.is_visible is True

    def test_to_jmap_includes_required_fields(self):
        cal = JMAPCalendar.from_jmap(_CALENDAR_JSON_MINIMAL)
        d = cal.to_jmap()
        assert d["name"] == "Work"
        assert "isSubscribed" in d

    def test_to_jmap_excludes_server_set_fields(self):
        cal = JMAPCalendar.from_jmap(_CALENDAR_JSON_FULL)
        d = cal.to_jmap()
        assert "id" not in d
        assert "myRights" not in d

    def test_to_jmap_omits_none_optional_fields(self):
        cal = JMAPCalendar.from_jmap(_CALENDAR_JSON_MINIMAL)
        d = cal.to_jmap()
        assert "description" not in d
        assert "color" not in d

    def test_to_jmap_includes_optional_when_set(self):
        cal = JMAPCalendar.from_jmap(_CALENDAR_JSON_FULL)
        d = cal.to_jmap()
        assert d["description"] == "My personal calendar"
        assert d["color"] == "#3a86ff"

    def test_from_jmap_ignores_unknown_keys(self):
        data = dict(_CALENDAR_JSON_FULL)
        data["unknownFutureField"] = "something"
        cal = JMAPCalendar.from_jmap(data)
        assert cal.id == "cal1"

    def test_from_jmap_raises_when_name_missing(self):
        with pytest.raises(KeyError):
            JMAPCalendar.from_jmap({"id": "cal3"})


# ---------------------------------------------------------------------------
# Calendar method builders and parsers
# ---------------------------------------------------------------------------

from caldav.jmap.methods.calendar import (
    build_calendar_changes,
    build_calendar_get,
    parse_calendar_get,
)


class TestCalendarMethodBuilders:
    def test_build_calendar_get_structure(self):
        method, args, call_id = build_calendar_get("u1")
        assert method == "Calendar/get"
        assert args["accountId"] == "u1"
        assert args["ids"] is None
        assert isinstance(call_id, str)

    def test_build_calendar_get_with_ids(self):
        _, args, _ = build_calendar_get("u1", ids=["cal1", "cal2"])
        assert args["ids"] == ["cal1", "cal2"]

    def test_build_calendar_get_with_properties(self):
        _, args, _ = build_calendar_get("u1", properties=["id", "name"])
        assert args["properties"] == ["id", "name"]

    def test_build_calendar_get_no_properties_key_when_not_set(self):
        _, args, _ = build_calendar_get("u1")
        assert "properties" not in args

    def test_parse_calendar_get_returns_calendars(self):
        response_args = {"list": [_CALENDAR_JSON_FULL, _CALENDAR_JSON_MINIMAL]}
        cals = parse_calendar_get(response_args)
        assert len(cals) == 2
        assert isinstance(cals[0], JMAPCalendar)
        assert cals[0].id == "cal1"
        assert cals[1].id == "cal2"

    def test_parse_calendar_get_empty_list(self):
        cals = parse_calendar_get({"list": []})
        assert cals == []

    def test_parse_calendar_get_missing_list_key(self):
        cals = parse_calendar_get({})
        assert cals == []

    def test_build_calendar_changes_structure(self):
        method, args, call_id = build_calendar_changes("u1", "state-abc")
        assert method == "Calendar/changes"
        assert args["accountId"] == "u1"
        assert args["sinceState"] == "state-abc"
        assert isinstance(call_id, str)


# ---------------------------------------------------------------------------
# JMAPClient
# ---------------------------------------------------------------------------

from caldav.jmap.client import JMAPClient

_CALENDAR_GET_RESPONSE = {
    "methodResponses": [
        [
            "Calendar/get",
            {
                "accountId": _USERNAME,
                "state": "cal-state-1",
                "list": [_CALENDAR_JSON_FULL, _CALENDAR_JSON_MINIMAL],
                "notFound": [],
            },
            "cal-get-0",
        ]
    ]
}


def _make_client_with_mocked_session(monkeypatch, api_response_json):
    """Return a JMAPClient whose HTTP calls are fully mocked."""
    client = JMAPClient(url=_JMAP_URL, username=_USERNAME, password=_PASSWORD)
    client._session_cache = Session(
        api_url=_API_URL,
        account_id=_USERNAME,
        state="state-abc",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = api_response_json
    mock_resp.raise_for_status = MagicMock()
    monkeypatch.setattr("caldav.jmap.client.requests.post", lambda *a, **kw: mock_resp)
    return client


class TestJMAPClient:
    def test_context_manager(self):
        with JMAPClient(url="http://x", username="u", password="p") as client:
            assert isinstance(client, JMAPClient)

    def test_build_auth_basic_when_username_given(self):
        client = JMAPClient(url="http://x", username="u", password="p")
        assert isinstance(client._auth, HTTPBasicAuth)

    def test_build_auth_bearer_when_no_username(self):
        from caldav.requests import HTTPBearerAuth

        client = JMAPClient(url="http://x", password="token")
        assert isinstance(client._auth, HTTPBearerAuth)

    def test_build_auth_raises_when_no_credentials(self):
        with pytest.raises(JMAPAuthError):
            JMAPClient(url="http://x")

    def test_build_auth_explicit_bearer_type(self):
        from caldav.requests import HTTPBearerAuth

        client = JMAPClient(url="http://x", username="u", password="token", auth_type="bearer")
        assert isinstance(client._auth, HTTPBearerAuth)

    def test_build_auth_unsupported_type_raises(self):
        with pytest.raises(JMAPAuthError):
            JMAPClient(url="http://x", username="u", password="p", auth_type="digest")

    def test_build_auth_basic_without_username_raises(self):
        with pytest.raises(JMAPAuthError):
            JMAPClient(url="http://x", password="p", auth_type="basic")

    def test_build_auth_basic_without_password_raises(self):
        with pytest.raises(JMAPAuthError):
            JMAPClient(url="http://x", username="u", auth_type="basic")

    def test_build_auth_bearer_without_token_raises(self):
        with pytest.raises(JMAPAuthError):
            JMAPClient(url="http://x", username="u", auth_type="bearer")

    def test_get_calendars_returns_list(self, monkeypatch):
        client = _make_client_with_mocked_session(monkeypatch, _CALENDAR_GET_RESPONSE)
        cals = client.get_calendars()
        assert len(cals) == 2
        assert isinstance(cals[0], JMAPCalendar)
        assert cals[0].id == "cal1"
        assert cals[1].id == "cal2"

    def test_get_calendars_empty_response(self, monkeypatch):
        empty_response = {
            "methodResponses": [
                ["Calendar/get", {"accountId": _USERNAME, "state": "s1", "list": []}, "c0"]
            ]
        }
        client = _make_client_with_mocked_session(monkeypatch, empty_response)
        assert client.get_calendars() == []

    def test_request_raises_auth_error_on_401(self, monkeypatch):
        client = JMAPClient(url=_JMAP_URL, username=_USERNAME, password=_PASSWORD)
        client._session_cache = Session(api_url=_API_URL, account_id=_USERNAME, state="s")

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status = MagicMock()
        monkeypatch.setattr("caldav.jmap.client.requests.post", lambda *a, **kw: mock_resp)

        with pytest.raises(JMAPAuthError):
            client._request([("Calendar/get", {"accountId": _USERNAME, "ids": None}, "c0")])

    def test_request_raises_method_error_on_error_response(self, monkeypatch):
        error_response = {"methodResponses": [["error", {"type": "unknownMethod"}, "c0"]]}
        client = _make_client_with_mocked_session(monkeypatch, error_response)
        with pytest.raises(JMAPMethodError) as exc_info:
            client._request([("Calendar/get", {"accountId": _USERNAME}, "c0")])
        assert exc_info.value.error_type == "unknownMethod"


# ---------------------------------------------------------------------------
# get_jmap_client factory
# ---------------------------------------------------------------------------

from caldav.jmap import get_jmap_client


class TestGetJMAPClient:
    def test_returns_client_with_explicit_params(self):
        client = get_jmap_client(url=_JMAP_URL, username=_USERNAME, password=_PASSWORD)
        assert isinstance(client, JMAPClient)
        assert client.url == _JMAP_URL

    def test_returns_none_when_no_config(self, monkeypatch):
        monkeypatch.delenv("CALDAV_URL", raising=False)
        client = get_jmap_client(check_config_file=False, environment=False)
        assert client is None

    def test_strips_caldav_only_keys(self, monkeypatch):
        client = get_jmap_client(
            url=_JMAP_URL,
            username=_USERNAME,
            password=_PASSWORD,
            ssl_verify_cert=True,
        )
        assert isinstance(client, JMAPClient)
        assert not hasattr(client, "ssl_verify_cert")


# ---------------------------------------------------------------------------
# CalendarEvent domain object
# ---------------------------------------------------------------------------

from caldav.jmap.objects.event import JMAPEvent

_EVENT_JSON_FULL = {
    "id": "ev1",
    "uid": "abc123@example.com",
    "calendarIds": {"cal1": True},
    "title": "Team standup",
    "start": "2024-06-15T09:00:00",
    "timeZone": "Europe/Berlin",
    "duration": "PT30M",
    "showWithoutTime": False,
    "description": "Daily sync",
    "locations": {"loc1": {"name": "Room A"}},
    "virtualLocations": {"vl1": {"name": "Zoom", "uri": "https://zoom.us/j/123"}},
    "links": {"lnk1": {"href": "https://example.com/doc.pdf", "rel": "enclosure"}},
    "keywords": {"standup": True, "work": True},
    "participants": {
        "p1": {"name": "Alice", "email": "alice@example.com", "roles": {"owner": True}},
        "p2": {"name": "Bob", "email": "bob@example.com", "roles": {"attendee": True}},
    },
    "recurrenceRules": [{"frequency": "weekly", "byDay": [{"day": "mo"}]}],
    "excludedRecurrenceRules": [],
    "recurrenceOverrides": {"2024-06-22T09:00:00": None},
    "alerts": {"al1": {"trigger": "-PT15M", "action": "display"}},
    "useDefaultAlerts": False,
    "sequence": 3,
    "freeBusyStatus": "busy",
    "privacy": "private",
    "color": "#ff6b6b",
    "isDraft": False,
    "priority": 5,
}

_EVENT_JSON_MINIMAL = {
    "id": "ev2",
    "uid": "def456@example.com",
    "calendarIds": {"cal1": True},
    "title": "Dentist",
    "start": "2024-07-01T14:00:00",
}


class TestJMAPEvent:
    def test_from_jmap_full(self):
        ev = JMAPEvent.from_jmap(_EVENT_JSON_FULL)
        assert ev.id == "ev1"
        assert ev.uid == "abc123@example.com"
        assert ev.calendar_ids == {"cal1": True}
        assert ev.title == "Team standup"
        assert ev.start == "2024-06-15T09:00:00"
        assert ev.time_zone == "Europe/Berlin"
        assert ev.duration == "PT30M"
        assert ev.show_without_time is False
        assert ev.description == "Daily sync"
        assert ev.locations == {"loc1": {"name": "Room A"}}
        assert ev.virtual_locations == {"vl1": {"name": "Zoom", "uri": "https://zoom.us/j/123"}}
        assert ev.links == {"lnk1": {"href": "https://example.com/doc.pdf", "rel": "enclosure"}}
        assert ev.keywords == {"standup": True, "work": True}
        assert ev.participants["p1"]["roles"] == {"owner": True}
        assert ev.recurrence_rules == [{"frequency": "weekly", "byDay": [{"day": "mo"}]}]
        assert ev.recurrence_overrides == {"2024-06-22T09:00:00": None}
        assert ev.alerts == {"al1": {"trigger": "-PT15M", "action": "display"}}
        assert ev.use_default_alerts is False
        assert ev.sequence == 3
        assert ev.free_busy_status == "busy"
        assert ev.privacy == "private"
        assert ev.color == "#ff6b6b"
        assert ev.is_draft is False
        assert ev.priority == 5

    def test_from_jmap_minimal_uses_defaults(self):
        ev = JMAPEvent.from_jmap(_EVENT_JSON_MINIMAL)
        assert ev.id == "ev2"
        assert ev.uid == "def456@example.com"
        assert ev.calendar_ids == {"cal1": True}
        assert ev.title == "Dentist"
        assert ev.start == "2024-07-01T14:00:00"
        assert ev.time_zone is None
        assert ev.duration == "P0D"
        assert ev.show_without_time is False
        assert ev.description is None
        assert ev.locations == {}
        assert ev.virtual_locations == {}
        assert ev.links == {}
        assert ev.keywords == {}
        assert ev.participants == {}
        assert ev.recurrence_rules == []
        assert ev.excluded_recurrence_rules == []
        assert ev.recurrence_overrides == {}
        assert ev.alerts == {}
        assert ev.use_default_alerts is False
        assert ev.sequence == 0
        assert ev.free_busy_status == "busy"
        assert ev.privacy is None
        assert ev.color is None
        assert ev.is_draft is False
        assert ev.priority == 0

    def test_from_jmap_raises_when_required_field_missing(self):
        for missing_key in ("id", "uid", "calendarIds", "title", "start"):
            data = dict(_EVENT_JSON_MINIMAL)
            del data[missing_key]
            with pytest.raises(KeyError):
                JMAPEvent.from_jmap(data)

    def test_from_jmap_ignores_unknown_keys(self):
        data = dict(_EVENT_JSON_MINIMAL)
        data["unknownFutureField"] = "ignored"
        ev = JMAPEvent.from_jmap(data)
        assert ev.id == "ev2"

    def test_to_jmap_excludes_id(self):
        ev = JMAPEvent.from_jmap(_EVENT_JSON_MINIMAL)
        d = ev.to_jmap()
        assert "id" not in d

    def test_to_jmap_includes_required_fields(self):
        ev = JMAPEvent.from_jmap(_EVENT_JSON_MINIMAL)
        d = ev.to_jmap()
        assert d["uid"] == "def456@example.com"
        assert d["calendarIds"] == {"cal1": True}
        assert d["title"] == "Dentist"
        assert d["start"] == "2024-07-01T14:00:00"
        assert d["duration"] == "P0D"
        assert "showWithoutTime" in d
        assert "sequence" in d
        assert "freeBusyStatus" in d
        assert "useDefaultAlerts" in d

    def test_to_jmap_omits_none_optional_fields(self):
        ev = JMAPEvent.from_jmap(_EVENT_JSON_MINIMAL)
        d = ev.to_jmap()
        assert "timeZone" not in d
        assert "description" not in d
        assert "privacy" not in d
        assert "color" not in d
        assert "isDraft" not in d

    def test_to_jmap_omits_empty_collections(self):
        ev = JMAPEvent.from_jmap(_EVENT_JSON_MINIMAL)
        d = ev.to_jmap()
        assert "locations" not in d
        assert "virtualLocations" not in d
        assert "links" not in d
        assert "keywords" not in d
        assert "participants" not in d
        assert "recurrenceRules" not in d
        assert "excludedRecurrenceRules" not in d
        assert "recurrenceOverrides" not in d
        assert "alerts" not in d

    def test_to_jmap_includes_optional_when_set(self):
        ev = JMAPEvent.from_jmap(_EVENT_JSON_FULL)
        d = ev.to_jmap()
        assert d["timeZone"] == "Europe/Berlin"
        assert d["description"] == "Daily sync"
        assert d["locations"] == {"loc1": {"name": "Room A"}}
        assert d["participants"]["p1"]["roles"] == {"owner": True}
        assert d["recurrenceRules"] == [{"frequency": "weekly", "byDay": [{"day": "mo"}]}]
        assert d["alerts"] == {"al1": {"trigger": "-PT15M", "action": "display"}}
        assert d["privacy"] == "private"
        assert d["color"] == "#ff6b6b"

    def test_to_jmap_isDraft_included_when_true(self):
        data = dict(_EVENT_JSON_MINIMAL)
        data["isDraft"] = True
        ev = JMAPEvent.from_jmap(data)
        d = ev.to_jmap()
        assert d["isDraft"] is True

    def test_to_jmap_isDraft_omitted_when_false(self):
        ev = JMAPEvent.from_jmap(_EVENT_JSON_MINIMAL)
        d = ev.to_jmap()
        assert "isDraft" not in d

    def test_participant_roles_is_map_not_list(self):
        ev = JMAPEvent.from_jmap(_EVENT_JSON_FULL)
        roles = ev.participants["p1"]["roles"]
        assert isinstance(roles, dict)
        assert roles.get("owner") is True

    def test_recurrence_overrides_null_value_preserved(self):
        ev = JMAPEvent.from_jmap(_EVENT_JSON_FULL)
        assert ev.recurrence_overrides["2024-06-22T09:00:00"] is None

    def test_alert_trigger_is_string(self):
        ev = JMAPEvent.from_jmap(_EVENT_JSON_FULL)
        trigger = ev.alerts["al1"]["trigger"]
        assert isinstance(trigger, str)
        assert trigger == "-PT15M"

    def test_from_jmap_null_fields_coerced_to_defaults(self):
        # Cyrus returns null for optional collection fields instead of omitting them
        data = {
            "id": "ev1",
            "uid": "uid1",
            "calendarIds": {"Default": True},
            "title": "Test",
            "start": "2024-06-15T10:00:00",
            "keywords": None,
            "locations": None,
            "participants": None,
            "alerts": None,
            "recurrenceRules": None,
            "excludedRecurrenceRules": None,
            "recurrenceOverrides": None,
        }
        ev = JMAPEvent.from_jmap(data)
        assert ev.keywords == {}
        assert ev.locations == {}
        assert ev.participants == {}
        assert ev.alerts == {}
        assert ev.recurrence_rules == []
        assert ev.excluded_recurrence_rules == []
        assert ev.recurrence_overrides == {}

    def test_from_jmap_explicit_empty_collections_are_empty(self):
        # Server sending empty {} / [] is semantically identical to null for optional fields
        data = {
            "id": "ev1",
            "uid": "uid1",
            "calendarIds": {"Default": True},
            "title": "Test",
            "start": "2024-06-15T10:00:00",
            "keywords": {},
            "locations": {},
            "participants": {},
            "alerts": {},
            "recurrenceRules": [],
            "excludedRecurrenceRules": [],
            "recurrenceOverrides": {},
        }
        ev = JMAPEvent.from_jmap(data)
        assert ev.keywords == {}
        assert ev.locations == {}
        assert ev.participants == {}
        assert ev.alerts == {}
        assert ev.recurrence_rules == []
        assert ev.excluded_recurrence_rules == []
        assert ev.recurrence_overrides == {}


# ---------------------------------------------------------------------------
# CalendarEvent method builders and parsers
# ---------------------------------------------------------------------------

from caldav.jmap.methods.event import (
    build_event_changes,
    build_event_get,
    build_event_query,
    build_event_query_changes,
    build_event_set_create,
    build_event_set_destroy,
    build_event_set_update,
    parse_event_get,
    parse_event_query,
    parse_event_set,
)


class TestEventMethodBuilders:
    def test_build_event_get_structure(self):
        method, args, call_id = build_event_get("u1")
        assert method == "CalendarEvent/get"
        assert args["accountId"] == "u1"
        assert args["ids"] is None
        assert isinstance(call_id, str)

    def test_build_event_get_with_ids(self):
        _, args, _ = build_event_get("u1", ids=["ev1", "ev2"])
        assert args["ids"] == ["ev1", "ev2"]

    def test_build_event_get_with_properties(self):
        _, args, _ = build_event_get("u1", properties=["id", "title", "start"])
        assert args["properties"] == ["id", "title", "start"]

    def test_build_event_get_no_properties_key_when_not_set(self):
        _, args, _ = build_event_get("u1")
        assert "properties" not in args

    def test_parse_event_get_returns_events(self):
        response_args = {"list": [_EVENT_JSON_FULL, _EVENT_JSON_MINIMAL]}
        events = parse_event_get(response_args)
        assert len(events) == 2
        assert isinstance(events[0], JMAPEvent)
        assert events[0].id == "ev1"
        assert events[1].id == "ev2"

    def test_parse_event_get_empty_list(self):
        assert parse_event_get({"list": []}) == []

    def test_parse_event_get_missing_list_key(self):
        assert parse_event_get({}) == []

    def test_build_event_changes_structure(self):
        method, args, call_id = build_event_changes("u1", "state-abc")
        assert method == "CalendarEvent/changes"
        assert args["accountId"] == "u1"
        assert args["sinceState"] == "state-abc"
        assert isinstance(call_id, str)

    def test_build_event_changes_with_max_changes(self):
        _, args, _ = build_event_changes("u1", "state-abc", max_changes=50)
        assert args["maxChanges"] == 50

    def test_build_event_changes_no_max_changes_key_when_not_set(self):
        _, args, _ = build_event_changes("u1", "state-abc")
        assert "maxChanges" not in args

    def test_build_event_query_structure(self):
        method, args, call_id = build_event_query("u1")
        assert method == "CalendarEvent/query"
        assert args["accountId"] == "u1"
        assert args["position"] == 0
        assert isinstance(call_id, str)

    def test_build_event_query_with_filter(self):
        f = {"after": "2024-01-01T00:00:00Z", "before": "2024-12-31T23:59:59Z"}
        _, args, _ = build_event_query("u1", filter=f)
        assert args["filter"] == f

    def test_build_event_query_with_sort(self):
        s = [{"property": "start", "isAscending": True}]
        _, args, _ = build_event_query("u1", sort=s)
        assert args["sort"] == s

    def test_build_event_query_with_limit(self):
        _, args, _ = build_event_query("u1", limit=100)
        assert args["limit"] == 100

    def test_build_event_query_no_optional_keys_when_not_set(self):
        _, args, _ = build_event_query("u1")
        assert "filter" not in args
        assert "sort" not in args
        assert "limit" not in args

    def test_parse_event_query_returns_ids_state_total(self):
        response_args = {
            "ids": ["ev1", "ev2", "ev3"],
            "queryState": "qstate-1",
            "total": 10,
        }
        ids, query_state, total = parse_event_query(response_args)
        assert ids == ["ev1", "ev2", "ev3"]
        assert query_state == "qstate-1"
        assert total == 10

    def test_parse_event_query_total_defaults_to_ids_length(self):
        response_args = {"ids": ["ev1", "ev2"], "queryState": "q1"}
        ids, _, total = parse_event_query(response_args)
        assert total == 2

    def test_parse_event_query_empty_response(self):
        ids, query_state, total = parse_event_query({})
        assert ids == []
        assert query_state == ""
        assert total == 0

    def test_build_event_query_changes_structure(self):
        method, args, call_id = build_event_query_changes("u1", "qstate-1")
        assert method == "CalendarEvent/queryChanges"
        assert args["accountId"] == "u1"
        assert args["sinceQueryState"] == "qstate-1"
        assert isinstance(call_id, str)

    def test_build_event_query_changes_with_filter_and_sort(self):
        f = {"calendarIds": {"cal1": True}}
        s = [{"property": "start", "isAscending": True}]
        _, args, _ = build_event_query_changes("u1", "qstate-1", filter=f, sort=s)
        assert args["filter"] == f
        assert args["sort"] == s

    def test_build_event_set_create_structure(self):
        ev = JMAPEvent.from_jmap(_EVENT_JSON_MINIMAL)
        method, args, call_id = build_event_set_create("u1", {"new-1": ev})
        assert method == "CalendarEvent/set"
        assert "create" in args
        assert "new-1" in args["create"]
        assert "id" not in args["create"]["new-1"]

    def test_build_event_set_update_structure(self):
        method, args, call_id = build_event_set_update("u1", {"ev1": {"title": "Updated title"}})
        assert method == "CalendarEvent/set"
        assert args["update"] == {"ev1": {"title": "Updated title"}}

    def test_build_event_set_destroy_structure(self):
        method, args, call_id = build_event_set_destroy("u1", ["ev1", "ev2"])
        assert method == "CalendarEvent/set"
        assert args["destroy"] == ["ev1", "ev2"]

    def test_parse_event_set_created(self):
        response_args = {
            "created": {"new-1": {"id": "server-ev-99", "uid": "def456@example.com"}},
            "updated": None,
            "destroyed": None,
        }
        created, updated, destroyed, not_created, not_updated, not_destroyed = parse_event_set(
            response_args
        )
        assert created["new-1"]["id"] == "server-ev-99"
        assert updated == {}
        assert destroyed == []
        assert not_created == {}
        assert not_updated == {}
        assert not_destroyed == {}

    def test_parse_event_set_destroyed(self):
        response_args = {"created": None, "updated": None, "destroyed": ["ev1", "ev2"]}
        created, updated, destroyed, not_created, not_updated, not_destroyed = parse_event_set(
            response_args
        )
        assert created == {}
        assert updated == {}
        assert destroyed == ["ev1", "ev2"]
        assert not_created == {}

    def test_parse_event_set_empty_response(self):
        created, updated, destroyed, not_created, not_updated, not_destroyed = parse_event_set({})
        assert created == {}
        assert updated == {}
        assert destroyed == []
        assert not_created == {}
        assert not_updated == {}
        assert not_destroyed == {}

    def test_parse_event_set_partial_failure(self):
        # notCreated/notUpdated/notDestroyed carry SetError objects for failed operations
        response_args = {
            "created": {"new-1": {"id": "server-ev-99"}},
            "notCreated": {"new-2": {"type": "invalidArguments", "description": "bad uid"}},
            "notDestroyed": {"ev-old": {"type": "notFound"}},
        }
        created, updated, destroyed, not_created, not_updated, not_destroyed = parse_event_set(
            response_args
        )
        assert "new-1" in created
        assert not_created["new-2"]["type"] == "invalidArguments"
        assert not_destroyed["ev-old"]["type"] == "notFound"


# ===========================================================================
# iCalendar ↔ JSCalendar conversion layer
# ===========================================================================

from datetime import date, datetime, timedelta, timezone

import icalendar as _icalendar

from caldav.jmap.convert import ical_to_jscal, jscal_to_ical
from caldav.jmap.convert._utils import (
    _duration_to_timedelta,
    _format_local_dt,
    _timedelta_to_duration,
)

# ---------------------------------------------------------------------------
# Shared iCal fixtures
# ---------------------------------------------------------------------------


def _make_ical(extra_lines: str = "", uid: str = "test-uid@example.com") -> str:
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Test//Test//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        "DTSTAMP:20240101T000000Z\r\n" + extra_lines + "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


def _minimal_jscal(**kwargs) -> dict:
    base = {
        "uid": "test-uid@example.com",
        "title": "Test Event",
        "start": "2024-06-15T10:00:00",
        "timeZone": "Europe/Berlin",
        "duration": "PT1H",
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# TestUtils — shared utility functions
# ---------------------------------------------------------------------------


class TestUtils:
    def test_timedelta_to_duration_hours(self):
        assert _timedelta_to_duration(timedelta(hours=1, minutes=30)) == "PT1H30M"

    def test_timedelta_to_duration_days(self):
        assert _timedelta_to_duration(timedelta(days=1)) == "P1D"

    def test_timedelta_to_duration_mixed(self):
        assert _timedelta_to_duration(timedelta(days=1, hours=2)) == "P1DT2H"

    def test_timedelta_to_duration_zero(self):
        assert _timedelta_to_duration(timedelta(0)) == "P0D"

    def test_timedelta_to_duration_negative(self):
        assert _timedelta_to_duration(timedelta(seconds=-900)) == "-PT15M"

    def test_duration_to_timedelta_hours(self):
        assert _duration_to_timedelta("PT1H30M") == timedelta(hours=1, minutes=30)

    def test_duration_to_timedelta_days(self):
        assert _duration_to_timedelta("P1D") == timedelta(days=1)

    def test_duration_to_timedelta_zero(self):
        assert _duration_to_timedelta("P0D") == timedelta(0)

    def test_duration_to_timedelta_negative(self):
        assert _duration_to_timedelta("-PT15M") == timedelta(seconds=-900)

    def test_duration_round_trip(self):
        td = timedelta(days=2, hours=3, minutes=45, seconds=30)
        assert _duration_to_timedelta(_timedelta_to_duration(td)) == td

    def test_format_local_dt_utc(self):
        dt = datetime(2024, 6, 15, 9, 0, 0, tzinfo=timezone.utc)
        assert _format_local_dt(dt) == "2024-06-15T09:00:00Z"

    def test_format_local_dt_naive(self):
        dt = datetime(2024, 6, 15, 9, 0, 0)
        assert _format_local_dt(dt) == "2024-06-15T09:00:00"

    def test_format_local_dt_date(self):
        d = date(2024, 6, 15)
        assert _format_local_dt(d) == "2024-06-15T00:00:00"


# ---------------------------------------------------------------------------
# TestIcalToJscal
# ---------------------------------------------------------------------------


class TestIcalToJscal:
    def test_minimal_event(self):
        ical = _make_ical("DTSTART:20240615T100000Z\r\nDURATION:PT1H\r\nSUMMARY:Test Event\r\n")
        result = ical_to_jscal(ical)
        assert result["uid"] == "test-uid@example.com"
        assert result["title"] == "Test Event"
        assert result["start"] == "2024-06-15T10:00:00Z"
        assert result["duration"] == "PT1H"

    def test_all_day_event(self):
        ical = _make_ical(
            "DTSTART;VALUE=DATE:20240615\r\nDTEND;VALUE=DATE:20240616\r\nSUMMARY:All Day\r\n"
        )
        result = ical_to_jscal(ical)
        assert result["start"] == "2024-06-15T00:00:00"
        assert result["showWithoutTime"] is True
        assert "timeZone" not in result
        assert result["duration"] == "P1D"

    def test_timezone_aware_event(self):
        ical = _make_ical(
            "DTSTART;TZID=America/New_York:20240615T100000\r\nDURATION:PT1H\r\nSUMMARY:TZ Event\r\n"
        )
        result = ical_to_jscal(ical)
        assert result["start"] == "2024-06-15T10:00:00"
        assert result["timeZone"] == "America/New_York"
        assert "showWithoutTime" not in result

    def test_utc_event(self):
        ical = _make_ical("DTSTART:20240615T100000Z\r\nDURATION:PT30M\r\nSUMMARY:UTC Event\r\n")
        result = ical_to_jscal(ical)
        assert result["start"].endswith("Z")
        assert "timeZone" not in result

    def test_duration_from_dtend(self):
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\nDTEND:20240615T113000Z\r\nSUMMARY:DTEND Event\r\n"
        )
        result = ical_to_jscal(ical)
        assert result["duration"] == "PT1H30M"

    def test_duration_explicit(self):
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\nDURATION:P1DT2H\r\nSUMMARY:Duration Event\r\n"
        )
        result = ical_to_jscal(ical)
        assert result["duration"] == "P1DT2H"

    def test_duration_zero_when_missing(self):
        ical = _make_ical("DTSTART:20240615T100000Z\r\nSUMMARY:No Duration\r\n")
        result = ical_to_jscal(ical)
        assert result["duration"] == "P0D"

    def test_categories_to_keywords(self):
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\nSUMMARY:Cat Event\r\nCATEGORIES:work,standup\r\n"
        )
        result = ical_to_jscal(ical)
        assert "keywords" in result
        assert result["keywords"].get("work") is True
        assert result["keywords"].get("standup") is True

    def test_categories_multiple_lines(self):
        # Two separate CATEGORIES lines — icalendar returns a list of vCategory objects
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\nSUMMARY:Cat Event\r\n"
            "CATEGORIES:Work\r\nCATEGORIES:Standup\r\n"
        )
        result = ical_to_jscal(ical)
        assert "keywords" in result
        assert result["keywords"].get("Work") is True
        assert result["keywords"].get("Standup") is True

    def test_location_string(self):
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\nSUMMARY:Located Event\r\nLOCATION:Conference Room A\r\n"
        )
        result = ical_to_jscal(ical)
        assert "locations" in result
        locs = result["locations"]
        assert len(locs) == 1
        first_loc = next(iter(locs.values()))
        assert first_loc["name"] == "Conference Room A"

    def test_priority(self):
        ical = _make_ical("DTSTART:20240615T100000Z\r\nSUMMARY:Priority Event\r\nPRIORITY:5\r\n")
        result = ical_to_jscal(ical)
        assert result["priority"] == 5

    def test_class_private(self):
        ical = _make_ical("DTSTART:20240615T100000Z\r\nSUMMARY:Private Event\r\nCLASS:PRIVATE\r\n")
        result = ical_to_jscal(ical)
        assert result["privacy"] == "private"

    def test_class_confidential(self):
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\nSUMMARY:Confidential Event\r\nCLASS:CONFIDENTIAL\r\n"
        )
        result = ical_to_jscal(ical)
        assert result["privacy"] == "secret"

    def test_transp_transparent(self):
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\nSUMMARY:Free Event\r\nTRANSP:TRANSPARENT\r\n"
        )
        result = ical_to_jscal(ical)
        assert result["freeBusyStatus"] == "free"

    def test_rrule_weekly(self):
        ical = _make_ical(
            "DTSTART;TZID=Europe/Berlin:20240617T140000\r\n"
            "DURATION:PT1H\r\n"
            "SUMMARY:Team Meeting\r\n"
            "RRULE:FREQ=WEEKLY;BYDAY=MO,WE\r\n"
        )
        result = ical_to_jscal(ical)
        assert "recurrenceRules" in result
        rule = result["recurrenceRules"][0]
        assert rule["@type"] == "RecurrenceRule"
        assert rule["frequency"] == "weekly"
        assert rule["interval"] == 1
        assert rule["rscale"] == "gregorian"
        days = [d["day"] for d in rule["byDay"]]
        assert "mo" in days
        assert "we" in days

    def test_exdate(self):
        ical = _make_ical(
            "DTSTART;TZID=Europe/Berlin:20240617T140000\r\n"
            "DURATION:PT1H\r\n"
            "SUMMARY:Recurring\r\n"
            "RRULE:FREQ=WEEKLY\r\n"
            "EXDATE;TZID=Europe/Berlin:20240624T140000\r\n"
        )
        result = ical_to_jscal(ical)
        assert "recurrenceOverrides" in result
        overrides = result["recurrenceOverrides"]
        assert any(v == {"excluded": True} for v in overrides.values())

    def test_valarm_relative(self):
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\n"
            "SUMMARY:Alarm Event\r\n"
            "BEGIN:VALARM\r\n"
            "ACTION:DISPLAY\r\n"
            "TRIGGER:-PT15M\r\n"
            "DESCRIPTION:Reminder\r\n"
            "END:VALARM\r\n"
        )
        result = ical_to_jscal(ical)
        assert "alerts" in result
        alert = next(iter(result["alerts"].values()))
        assert alert["trigger"] == "-PT15M"
        assert alert["action"] == "display"

    def test_valarm_absolute(self):
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\n"
            "SUMMARY:Abs Alarm Event\r\n"
            "BEGIN:VALARM\r\n"
            "ACTION:DISPLAY\r\n"
            "TRIGGER;VALUE=DATE-TIME:20240615T093000Z\r\n"
            "DESCRIPTION:Reminder\r\n"
            "END:VALARM\r\n"
        )
        result = ical_to_jscal(ical)
        assert "alerts" in result
        alert = next(iter(result["alerts"].values()))
        assert alert["trigger"].endswith("Z")

    def test_organizer_attendee(self):
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\n"
            "SUMMARY:Meeting\r\n"
            "ORGANIZER;CN=Alice:mailto:alice@example.com\r\n"
            "ATTENDEE;CN=Bob;PARTSTAT=ACCEPTED:mailto:bob@example.com\r\n"
        )
        result = ical_to_jscal(ical)
        assert "participants" in result
        participants = result["participants"]
        # Find organizer
        organizer = next(
            (p for p in participants.values() if p.get("roles", {}).get("owner")), None
        )
        assert organizer is not None
        assert organizer["roles"].get("organizer") is True
        # Find attendee
        attendee = next(
            (p for p in participants.values() if p.get("roles", {}).get("attendee")), None
        )
        assert attendee is not None

    def test_attendee_partstat(self):
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\n"
            "SUMMARY:Meeting\r\n"
            "ATTENDEE;PARTSTAT=DECLINED:mailto:bob@example.com\r\n"
        )
        result = ical_to_jscal(ical)
        attendee = next(iter(result["participants"].values()))
        assert attendee["participationStatus"] == "declined"

    def test_calendar_id_set(self):
        ical = _make_ical("DTSTART:20240615T100000Z\r\nSUMMARY:Cal Event\r\n")
        result = ical_to_jscal(ical, calendar_id="Default")
        assert result["calendarIds"] == {"Default": True}

    def test_no_calendar_id_omits_key(self):
        ical = _make_ical("DTSTART:20240615T100000Z\r\nSUMMARY:No Cal\r\n")
        result = ical_to_jscal(ical)
        assert "calendarIds" not in result

    def test_floating_datetime(self):
        ical = _make_ical("DTSTART:20240615T100000\r\nDURATION:PT1H\r\nSUMMARY:Floating\r\n")
        result = ical_to_jscal(ical)
        assert result["start"] == "2024-06-15T10:00:00"
        assert "timeZone" not in result
        assert result.get("showWithoutTime") is not True

    def test_recurrence_id_child_vevent(self):
        ical = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//Test//Test//EN\r\n"
            "BEGIN:VEVENT\r\n"
            "UID:recur-uid@example.com\r\n"
            "DTSTAMP:20240101T000000Z\r\n"
            "DTSTART:20240617T140000Z\r\n"
            "DURATION:PT1H\r\n"
            "SUMMARY:Weekly Meeting\r\n"
            "RRULE:FREQ=WEEKLY\r\n"
            "END:VEVENT\r\n"
            "BEGIN:VEVENT\r\n"
            "UID:recur-uid@example.com\r\n"
            "DTSTAMP:20240101T000000Z\r\n"
            "RECURRENCE-ID:20240624T140000Z\r\n"
            "DTSTART:20240624T160000Z\r\n"
            "DURATION:PT2H\r\n"
            "SUMMARY:Rescheduled Meeting\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )
        result = ical_to_jscal(ical)
        assert "recurrenceOverrides" in result
        overrides = result["recurrenceOverrides"]
        assert len(overrides) == 1
        key = next(iter(overrides))
        patch = overrides[key]
        assert isinstance(patch, dict)
        assert patch.get("excluded") is not True
        assert patch.get("title") == "Rescheduled Meeting"

    def test_color_and_sequence(self):
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\nSUMMARY:Colored\r\nCOLOR:red\r\nSEQUENCE:3\r\n"
        )
        result = ical_to_jscal(ical)
        assert result.get("color") == "red"
        assert result.get("sequence") == 3

    def test_rrule_missing_freq_raises(self):
        ical = _make_ical("DTSTART:20240615T100000Z\r\nSUMMARY:Bad RRULE\r\nRRULE:INTERVAL=2\r\n")
        with pytest.raises((ValueError, Exception)):
            ical_to_jscal(ical)


# ---------------------------------------------------------------------------
# TestJscalToIcal
# ---------------------------------------------------------------------------


class TestJscalToIcal:
    def test_minimal_event(self):
        jscal = _minimal_jscal()
        result = jscal_to_ical(jscal)
        assert "BEGIN:VCALENDAR" in result
        assert "BEGIN:VEVENT" in result
        assert "SUMMARY:Test Event" in result
        assert "UID:test-uid@example.com" in result

    def test_all_day_event(self):
        jscal = _minimal_jscal(
            start="2024-06-15T00:00:00",
            showWithoutTime=True,
            duration="P1D",
        )
        del jscal["timeZone"]
        result = jscal_to_ical(jscal)
        assert "DTSTART;VALUE=DATE:20240615" in result

    def test_timezone_aware_event(self):
        jscal = _minimal_jscal(start="2024-06-15T10:00:00", timeZone="Europe/Berlin")
        result = jscal_to_ical(jscal)
        assert "DTSTART;TZID=Europe/Berlin:" in result

    def test_utc_event(self):
        jscal = _minimal_jscal(start="2024-06-15T10:00:00Z")
        del jscal["timeZone"]
        result = jscal_to_ical(jscal)
        assert "20240615T100000Z" in result

    def test_duration(self):
        jscal = _minimal_jscal(duration="PT2H30M")
        result = jscal_to_ical(jscal)
        assert "DURATION:PT2H30M" in result

    def test_keywords_to_categories(self):
        jscal = _minimal_jscal(keywords={"work": True, "standup": True})
        result = jscal_to_ical(jscal)
        assert "CATEGORIES" in result
        assert "work" in result or "standup" in result

    def test_location(self):
        jscal = _minimal_jscal(locations={"loc1": {"name": "Room A"}})
        result = jscal_to_ical(jscal)
        assert "LOCATION:Room A" in result

    def test_priority(self):
        jscal = _minimal_jscal(priority=5)
        result = jscal_to_ical(jscal)
        assert "PRIORITY:5" in result

    def test_privacy_private(self):
        jscal = _minimal_jscal(privacy="private")
        result = jscal_to_ical(jscal)
        assert "CLASS:PRIVATE" in result

    def test_privacy_secret(self):
        jscal = _minimal_jscal(privacy="secret")
        result = jscal_to_ical(jscal)
        assert "CLASS:CONFIDENTIAL" in result

    def test_free_busy_free(self):
        jscal = _minimal_jscal(freeBusyStatus="free")
        result = jscal_to_ical(jscal)
        assert "TRANSP:TRANSPARENT" in result

    def test_rrule(self):
        jscal = _minimal_jscal(
            recurrenceRules=[
                {
                    "@type": "RecurrenceRule",
                    "frequency": "weekly",
                    "interval": 1,
                    "byDay": [{"@type": "NDay", "day": "mo"}],
                    "rscale": "gregorian",
                    "skip": "omit",
                    "firstDayOfWeek": "mo",
                }
            ]
        )
        result = jscal_to_ical(jscal)
        assert "RRULE" in result
        assert "FREQ=WEEKLY" in result
        assert "BYDAY=MO" in result

    def test_exdate_from_overrides(self):
        jscal = _minimal_jscal(
            recurrenceRules=[{"frequency": "weekly", "@type": "RecurrenceRule"}],
            recurrenceOverrides={"2024-06-22T10:00:00": {"excluded": True}},
        )
        result = jscal_to_ical(jscal)
        assert "EXDATE" in result

    def test_alert_relative(self):
        jscal = _minimal_jscal(alerts={"al1": {"trigger": "-PT15M", "action": "display"}})
        result = jscal_to_ical(jscal)
        assert "BEGIN:VALARM" in result
        assert "TRIGGER:-PT15M" in result

    def test_participants_organizer(self):
        jscal = _minimal_jscal(
            participants={
                "p1": {
                    "roles": {"owner": True, "organizer": True},
                    "name": "Alice",
                    "email": "alice@example.com",
                    "sendTo": {"imip": "mailto:alice@example.com"},
                }
            }
        )
        result = jscal_to_ical(jscal)
        assert "ORGANIZER" in result
        assert "alice@example.com" in result

    def test_sequence_emitted(self):
        result = jscal_to_ical(_minimal_jscal(sequence=5))
        assert "SEQUENCE:5" in result

    def test_color_emitted(self):
        result = jscal_to_ical(_minimal_jscal(color="blue"))
        assert "COLOR:blue" in result

    def test_exrule_from_excluded_recurrence_rules(self):
        jscal = _minimal_jscal(
            recurrenceRules=[{"@type": "RecurrenceRule", "frequency": "weekly"}],
            excludedRecurrenceRules=[
                {"@type": "RecurrenceRule", "frequency": "weekly", "byDay": [{"day": "mo"}]}
            ],
        )
        assert "EXRULE" in jscal_to_ical(jscal)

    def test_recurrence_override_patch_becomes_child_vevent(self):
        jscal = _minimal_jscal(
            start="2024-06-17T14:00:00Z",
            recurrenceRules=[{"@type": "RecurrenceRule", "frequency": "weekly"}],
            recurrenceOverrides={
                "2024-06-24T14:00:00Z": {"title": "Rescheduled", "start": "2024-06-24T16:00:00Z"}
            },
        )
        del jscal["timeZone"]
        result = jscal_to_ical(jscal)
        assert result.count("BEGIN:VEVENT") == 2
        assert "RECURRENCE-ID" in result
        assert "Rescheduled" in result

    def test_floating_datetime_emitted(self):
        jscal = {
            "uid": "float-uid@example.com",
            "title": "Floating",
            "start": "2024-06-15T10:00:00",
            "duration": "PT1H",
        }
        result = jscal_to_ical(jscal)
        assert "DTSTART:20240615T100000" in result
        assert "TZID" not in result


# ---------------------------------------------------------------------------
# TestRoundTrip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def _key_fields_survive(self, original_ical: str) -> dict:
        """ical → jscal → ical → parse back and check."""
        jscal = ical_to_jscal(original_ical)
        round_tripped = jscal_to_ical(jscal)
        cal = _icalendar.Calendar.from_ical(round_tripped)
        event = next(c for c in cal.subcomponents if isinstance(c, _icalendar.Event))
        return {"jscal": jscal, "ical": round_tripped, "event": event}

    def test_basic_event_round_trip(self):
        ical = _make_ical("DTSTART:20240615T100000Z\r\nDURATION:PT1H\r\nSUMMARY:Basic Event\r\n")
        ctx = self._key_fields_survive(ical)
        assert str(ctx["event"]["SUMMARY"]) == "Basic Event"
        assert ctx["jscal"]["title"] == "Basic Event"
        assert ctx["jscal"]["duration"] == "PT1H"

    def test_all_day_round_trip(self):
        ical = _make_ical(
            "DTSTART;VALUE=DATE:20240615\r\nDTEND;VALUE=DATE:20240616\r\nSUMMARY:All Day Event\r\n"
        )
        ctx = self._key_fields_survive(ical)
        assert ctx["jscal"]["showWithoutTime"] is True
        assert ctx["jscal"]["duration"] == "P1D"

    def test_recurring_event_round_trip(self):
        ical = _make_ical(
            "DTSTART;TZID=Europe/Berlin:20240617T140000\r\n"
            "DURATION:PT1H\r\n"
            "SUMMARY:Weekly\r\n"
            "RRULE:FREQ=WEEKLY;COUNT=4\r\n"
        )
        ctx = self._key_fields_survive(ical)
        assert "recurrenceRules" in ctx["jscal"]
        assert ctx["jscal"]["recurrenceRules"][0]["frequency"] == "weekly"
        assert "RRULE" in ctx["ical"]

    def test_with_alert_round_trip(self):
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\n"
            "DURATION:PT1H\r\n"
            "SUMMARY:Alert Event\r\n"
            "BEGIN:VALARM\r\n"
            "ACTION:DISPLAY\r\n"
            "TRIGGER:-PT15M\r\n"
            "DESCRIPTION:Reminder\r\n"
            "END:VALARM\r\n"
        )
        ctx = self._key_fields_survive(ical)
        assert "alerts" in ctx["jscal"]
        alert = next(iter(ctx["jscal"]["alerts"].values()))
        assert alert["trigger"] == "-PT15M"
        assert "BEGIN:VALARM" in ctx["ical"]

    def test_with_attendees_round_trip(self):
        ical = _make_ical(
            "DTSTART:20240615T100000Z\r\n"
            "DURATION:PT1H\r\n"
            "SUMMARY:Meeting\r\n"
            "ORGANIZER;CN=Alice:mailto:alice@example.com\r\n"
            "ATTENDEE;CN=Bob;PARTSTAT=ACCEPTED:mailto:bob@example.com\r\n"
        )
        ctx = self._key_fields_survive(ical)
        assert "participants" in ctx["jscal"]
        assert len(ctx["jscal"]["participants"]) >= 1
        assert "alice@example.com" in ctx["ical"] or "ORGANIZER" in ctx["ical"]
