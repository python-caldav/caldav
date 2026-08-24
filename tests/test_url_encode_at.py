#!/usr/bin/env python
"""
Unit tests for the ``url.encode-at`` feature and the URL-quoting helpers that
consult it.

Rule: None of the tests in this file should initiate any internet
communication, and there should be no dependencies on a working caldav
server for the tests in this file.
"""

import pytest

from caldav.calendarobjectresource import _quote_uid
from caldav.collection import (
    Principal,
    _quote_url_path,
    _sanitize_calendar_home_set_url,
)
from caldav.compatibility_hints import FeatureSet
from caldav.lib.url import URL


def _fs(support: str | None = None, required: str | None = None) -> FeatureSet:
    """A FeatureSet with the url.encode-at facts explicitly configured.

    ``support`` is url.encode-at itself (does '%40' resolve), ``required`` is
    url.encode-at-required (does the literal '@' fail, so encoding is forced).
    Both left out means nothing is configured at all.
    """
    conf = {}
    if support is not None:
        conf["url.encode-at"] = {"support": support}
    if required is not None:
        conf["url.encode-at-required"] = {"support": required}
    return FeatureSet(conf) if conf else FeatureSet()


class TestRequiredSubfeature:
    """url.encode-at-required: the literal '@' fails, so the client must encode."""

    URL = "http://x.example/c/a@b/"

    def test_subfeature_exists(self) -> None:
        assert "url.encode-at-required" in FeatureSet.FEATURES

    def test_default_is_unknown(self) -> None:
        assert _fs().is_supported("url.encode-at-required", str) == "unknown"

    def test_independent_of_the_parent(self) -> None:
        """A dashed key keeps a declared 'full' parent from forcing encoding.

        Both spellings resolving is exactly the case where encoding is *not*
        required, so nesting this under url.encode-at - where the ancestor
        walk would inherit a declared parent - would invert the meaning.
        """
        assert _fs("full").is_supported("url.encode-at-required", str) == "unknown"
        assert _quote_url_path(self.URL, _fs("full")) == self.URL

    def test_declared_required_forces_encoding(self) -> None:
        assert _quote_url_path(self.URL, _fs(required="full")) == ("http://x.example/c/a%40b/")

    def test_declared_not_required_leaves_the_at_alone(self) -> None:
        assert _quote_url_path(self.URL, _fs(required="unsupported")) == self.URL


class TestFeatureRegistration:
    def test_feature_exists(self) -> None:
        """url.encode-at must be a known feature, or configuring it warns."""
        assert "url.encode-at" in FeatureSet.FEATURES

    def test_feature_is_documented(self) -> None:
        feat = FeatureSet.FEATURES["url.encode-at"]
        assert feat.get("description")
        assert feat.get("links")

    def test_default_is_unknown(self) -> None:
        """An unprobed server must not be assumed to accept %40."""
        assert _fs().is_supported("url.encode-at", str) == "unknown"

    def test_unconfigured_is_distinguishable_from_default(self) -> None:
        """return_defaults=False is how callers detect 'not explicitly configured'."""
        assert _fs().is_supported("url.encode-at", str, return_defaults=False) is None

    def test_configured_is_reported_back(self) -> None:
        for level in ("full", "quirk", "unsupported"):
            assert _fs(level).is_supported("url.encode-at", str, return_defaults=False) == level

    def test_quirk_counts_as_supported(self) -> None:
        """quirk means 'encode it' - the boolean view must be positive."""
        assert _fs("quirk").is_supported("url.encode-at") is True
        assert _fs("unsupported").is_supported("url.encode-at") is False


class TestQuoteUrlPath:
    URL = "http://dav.example.com/cal/user@example.com/csc_encode_at@example.com.ics"

    def test_unencoded_spaces_are_quoted(self) -> None:
        """The pre-existing job of this helper must keep working."""
        got = _quote_url_path("http://dav.example.com/cal/my calendar/")
        assert got == "http://dav.example.com/cal/my%20calendar/"

    def test_at_is_left_literal_without_features(self) -> None:
        """No FeatureSet at all - the historic heuristic is preserved verbatim."""
        assert _quote_url_path(self.URL) == self.URL

    def test_at_is_left_literal_when_not_configured(self) -> None:
        """A FeatureSet that says nothing about url.encode-at changes nothing."""
        assert _quote_url_path(self.URL, features=_fs()) == self.URL

    def test_at_is_left_literal_when_server_accepts_both(self) -> None:
        """'full' means both forms work, so there is no reason to rewrite."""
        assert _quote_url_path(self.URL, features=_fs("full")) == self.URL

    def test_at_is_left_literal_when_encoding_unsupported(self) -> None:
        assert _quote_url_path(self.URL, features=_fs("unsupported")) == self.URL

    def test_at_is_encoded_when_server_requires_it(self) -> None:
        """A declared url.encode-at-required means a literal @ 404s."""
        got = _quote_url_path(self.URL, features=_fs(required="full"))
        assert got == (
            "http://dav.example.com/cal/user%40example.com/csc_encode_at%40example.com.ics"
        )

    def test_netloc_is_never_touched(self) -> None:
        """Credentials in the netloc must survive a forced rewrite untouched."""
        url = "http://user@dav.example.com/cal/a@b/"
        got = _quote_url_path(url, features=_fs(required="full"))
        assert got.startswith("http://user@dav.example.com/")
        assert got.endswith("/cal/a%40b/")


class TestSanitizeCalendarHomeSetUrl:
    BARE = "/remote.php/dav/calendars/user@example.com/"

    def test_none_passes_through(self) -> None:
        assert _sanitize_calendar_home_set_url(None) is None

    def test_bare_path_is_quoted_without_features(self) -> None:
        """Historic owncloud heuristic, preserved when nothing is configured."""
        assert (
            _sanitize_calendar_home_set_url(self.BARE)
            == "/remote.php/dav/calendars/user%40example.com/"
        )

    def test_bare_path_is_quoted_when_not_configured(self) -> None:
        got = _sanitize_calendar_home_set_url(self.BARE, features=_fs())
        assert got == "/remote.php/dav/calendars/user%40example.com/"

    def test_bare_path_is_quoted_when_encoding_works(self) -> None:
        for level in ("full", "quirk"):
            got = _sanitize_calendar_home_set_url(self.BARE, features=_fs(level))
            assert got == "/remote.php/dav/calendars/user%40example.com/"

    def test_bare_path_is_left_alone_when_encoding_unsupported(self) -> None:
        """A server known to 404 on %40 must keep the literal @."""
        got = _sanitize_calendar_home_set_url(self.BARE, features=_fs("unsupported"))
        assert got == self.BARE

    def test_full_url_is_never_quoted(self) -> None:
        url = "http://dav.example.com/cal/user@example.com/"
        assert _sanitize_calendar_home_set_url(url) == url

    def test_already_encoded_is_left_alone(self) -> None:
        url = "/remote.php/dav/calendars/user%40example.com/"
        assert _sanitize_calendar_home_set_url(url) == url


class _FakeClient:
    """Minimal stand-in for DAVClient: just a root URL and a feature set."""

    def __init__(self, features: FeatureSet) -> None:
        self.url = URL.objectify("http://dav.example.com/")
        self.features = features


def _principal(features: FeatureSet, home_set: str) -> Principal:
    """A Principal whose calendar-home-set propfind returns ``home_set``."""
    principal = Principal(client=_FakeClient(features), url="http://dav.example.com/p/")
    principal.get_property = lambda *args, **kwargs: home_set  # type: ignore[method-assign]
    return principal


class TestQuoteUid:
    """``_quote_uid`` must honour url.encode-at, not encode @ unconditionally.

    The feature description names "an object whose UID is an email address"
    as one of the two cases it covers, so the object-URL path has to consult
    it too - otherwise a server declared ``unsupported`` still gets %40.
    """

    def test_at_is_encoded_by_default(self) -> None:
        """Historic behaviour: unconfigured servers keep getting %40."""
        assert _quote_uid("user@example.com") == "user%40example.com"

    def test_at_is_encoded_when_not_configured(self) -> None:
        assert _quote_uid("user@example.com", _fs()) == "user%40example.com"

    def test_at_is_encoded_when_encoding_works(self) -> None:
        for level in ("full", "quirk"):
            assert _quote_uid("user@example.com", _fs(level)) == "user%40example.com"

    def test_quirk_alone_does_not_force_encoding(self) -> None:
        """'quirk' is a severity, not a behaviour - it must not mean 'encode'.

        Another server's url.encode-at quirk could be something else entirely
        (e.g. depending on where in the path the '@' sits), so the forcing
        fact lives in url.encode-at-required, not in the severity level.
        """
        assert _quote_url_path("http://x.example/c/a@b/", _fs("quirk")) == (
            "http://x.example/c/a@b/"
        )

    def test_at_is_left_alone_when_encoding_unsupported(self) -> None:
        """A server known to 404 on %40 must get the literal @."""
        assert _quote_uid("user@example.com", _fs("unsupported")) == "user@example.com"

    def test_slashes_are_double_quoted_regardless(self) -> None:
        """https://github.com/python-caldav/caldav/issues/143 must keep working."""
        for features in (None, _fs(), _fs("quirk"), _fs("unsupported")):
            assert _quote_uid("a/b", features) == "a%252Fb"


class TestPrincipalCalendarHomeSet:
    """The sync property and the async helper must route through the helper.

    Both carried their own copy of the owncloud @-heuristic, so they ignored
    url.encode-at and disagreed with client.get_calendars() about the URL.
    """

    BARE = "/remote.php/dav/calendars/user@example.com/"

    def test_sync_property_quotes_by_default(self) -> None:
        principal = _principal(_fs(), self.BARE)
        assert "user%40example.com" in str(principal.calendar_home_set.url)

    def test_sync_property_honours_unsupported(self) -> None:
        principal = _principal(_fs("unsupported"), self.BARE)
        assert "user@example.com" in str(principal.calendar_home_set.url)

    def test_sync_property_does_not_double_encode(self) -> None:
        principal = _principal(_fs(), "/remote.php/dav/calendars/user%40example.com/")
        assert "%2540" not in str(principal.calendar_home_set.url)

    @pytest.mark.asyncio
    async def test_async_helper_honours_unsupported(self) -> None:
        async def _get_property(*args, **kwargs):
            return self.BARE

        principal = Principal(
            client=_FakeClient(_fs("unsupported")), url="http://dav.example.com/p/"
        )
        principal.get_property = _get_property  # type: ignore[method-assign]
        home_set = await principal._async_get_calendar_home_set()
        assert "user@example.com" in str(home_set.url)

    @pytest.mark.asyncio
    async def test_async_helper_quotes_by_default(self) -> None:
        async def _get_property(*args, **kwargs):
            return self.BARE

        principal = Principal(client=_FakeClient(_fs()), url="http://dav.example.com/p/")
        principal.get_property = _get_property  # type: ignore[method-assign]
        home_set = await principal._async_get_calendar_home_set()
        assert "user%40example.com" in str(home_set.url)
