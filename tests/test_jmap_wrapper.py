"""
Tests for caldav.jmap, the thin wrapper around the standalone
calendaring-jmap package.

The JMAP client/conversion/protocol logic itself is calendaring-jmap's own
concern and is covered by that package's test suite; these tests only cover
the wrapper: does the public surface still resolve, does get_jmap_client()
still read caldav's config sources, and are JMAP errors still catchable as
DAVError.
"""

import subprocess
import sys
import textwrap

import calendaring_jmap
import pytest

import caldav.jmap as jmap
from caldav.lib.error import AuthorizationError, DAVError


class TestDeprecationWarning:
    """caldav.jmap must warn on import - issue #10's explicit requirement,
    so old imports keep working but say they're deprecated."""

    def test_import_warns(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                textwrap.dedent(
                    """
                    import warnings
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter("always")
                        import caldav.jmap
                    assert len(caught) == 1, caught
                    assert issubclass(caught[0].category, DeprecationWarning)
                    assert "caldav.jmap is deprecated" in str(caught[0].message)
                    print("ok")
                    """
                ),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout


class TestMissingDependency:
    """caldav.jmap must explain itself when calendaring-jmap isn't installed,
    not surface a bare ModuleNotFoundError."""

    def test_import_without_calendaring_jmap_raises_helpful_error(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                textwrap.dedent(
                    """
                    import sys

                    class Blocker:
                        def find_spec(self, fullname, path=None, target=None):
                            if fullname.split(".")[0] == "calendaring_jmap":
                                raise ImportError("blocked by test")
                            return None

                    sys.meta_path.insert(0, Blocker())

                    try:
                        import caldav.jmap
                    except ImportError as e:
                        assert "caldav[jmap]" in str(e)
                        assert "calendaring-jmap" in str(e)
                        print("ok")
                    else:
                        print("no ImportError raised")
                    """
                ),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout


class TestPublicSurface:
    """The wrapper must keep exactly the same __all__ as before extraction."""

    def test_all_matches_expected_names(self):
        assert sorted(jmap.__all__) == sorted(
            [
                "JMAPClient",
                "AsyncJMAPClient",
                "get_jmap_client",
                "get_async_jmap_client",
                "JMAPError",
                "JMAPCapabilityError",
                "JMAPAuthError",
                "JMAPMethodError",
                "JMAPCalendar",
                "JMAPCalendarObject",
            ]
        )

    def test_client_classes_are_calendaring_jmap_s(self):
        assert jmap.JMAPClient is calendaring_jmap.JMAPClient
        assert jmap.AsyncJMAPClient is calendaring_jmap.AsyncJMAPClient

    def test_object_classes_are_calendaring_jmap_s(self):
        assert jmap.JMAPCalendar is calendaring_jmap.JMAPCalendar
        assert jmap.JMAPCalendarObject is calendaring_jmap.JMAPCalendarObject


class TestGetJmapClient:
    """get_jmap_client()/get_async_jmap_client() still resolve config the
    way get_davclient() does, via caldav.config.get_connection_params()."""

    def test_explicit_kwargs_build_a_client(self):
        client = jmap.get_jmap_client(
            url="https://jmap.example.com/.well-known/jmap",
            username="alice",
            password="secret",
        )
        assert isinstance(client, calendaring_jmap.JMAPClient)
        assert client.url == "https://jmap.example.com/.well-known/jmap"
        assert client.username == "alice"

    def test_async_explicit_kwargs_build_a_client(self):
        client = jmap.get_async_jmap_client(
            url="https://jmap.example.com/.well-known/jmap",
            username="alice",
            password="secret",
        )
        assert isinstance(client, calendaring_jmap.AsyncJMAPClient)

    def test_no_config_returns_none(self, monkeypatch):
        monkeypatch.delenv("CALDAV_URL", raising=False)
        monkeypatch.setattr(
            "caldav.config.get_connection_params",
            lambda **kwargs: None,
        )
        assert jmap.get_jmap_client(check_config_file=False, environment=False) is None
        assert jmap.get_async_jmap_client(check_config_file=False, environment=False) is None

    def test_non_jmap_keys_are_filtered_out(self, monkeypatch):
        """get_connection_params() can return CalDAV-only keys (proxy, headers,
        ...); JMAPClient's constructor does not accept those and must not see
        them."""
        monkeypatch.setattr(
            "caldav.config.get_connection_params",
            lambda **kwargs: {
                "url": "https://jmap.example.com/.well-known/jmap",
                "username": "alice",
                "password": "secret",
                "proxy": "http://localhost:8080",
                "headers": {"X-Test": "1"},
            },
        )
        client = jmap.get_jmap_client()
        assert isinstance(client, calendaring_jmap.JMAPClient)


class TestErrorHierarchy:
    """caldav.jmap's error classes ARE calendaring_jmap's (plain re-exports,
    no wrapper subclassing). calendaring_jmap/error.py is what conditionally
    adds the DAVError/AuthorizationError parentage when caldav is importable."""

    def test_error_classes_are_calendaring_jmap_s(self):
        assert jmap.JMAPError is calendaring_jmap.JMAPError
        assert jmap.JMAPCapabilityError is calendaring_jmap.JMAPCapabilityError
        assert jmap.JMAPAuthError is calendaring_jmap.JMAPAuthError
        assert jmap.JMAPMethodError is calendaring_jmap.JMAPMethodError

    @pytest.mark.parametrize(
        "error_cls",
        [jmap.JMAPError, jmap.JMAPCapabilityError, jmap.JMAPAuthError, jmap.JMAPMethodError],
    )
    def test_is_a_daverror(self, error_cls):
        assert issubclass(error_cls, DAVError)

    def test_jmap_auth_error_is_also_an_authorizationerror(self):
        assert issubclass(jmap.JMAPAuthError, AuthorizationError)

    def test_except_daverror_catches_jmap_auth_error(self):
        with pytest.raises(DAVError):
            raise jmap.JMAPAuthError(url="https://x", reason="nope")

    def test_error_type_and_reason_survive_construction(self):
        err = jmap.JMAPMethodError(
            url="https://jmap.example.com",
            reason="bad request",
            error_type="invalidArguments",
        )
        assert err.error_type == "invalidArguments"
        assert err.reason == "bad request"
        assert err.url == "https://jmap.example.com"

    def test_calendaring_jmap_falls_back_without_caldav(self):
        """calendaring_jmap must not hard-depend on caldav."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                textwrap.dedent(
                    """
                    import sys

                    class Blocker:
                        def find_spec(self, fullname, path=None, target=None):
                            if fullname.split(".")[0] == "caldav":
                                raise ImportError("blocked by test")
                            return None

                    sys.meta_path.insert(0, Blocker())

                    from calendaring_jmap.error import JMAPError, JMAPAuthError

                    assert "caldav" not in sys.modules
                    err = JMAPAuthError(url="https://x", reason="nope")
                    assert isinstance(err, Exception)
                    print("ok")
                    """
                ),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout
