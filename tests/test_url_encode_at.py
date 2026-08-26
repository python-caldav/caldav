"""Tests for the ``url.encode-at`` compatibility feature.

The feature models two orthogonal facts about a literal ``@`` in a resource
path: *which* spellings of it resolve (``at-spelling``), and - when both do -
whether they name one resource or two (``at-identity``).  The support level is
a severity only; nothing here may branch on it.  The tests are grouped so that
the "nothing declared changes nothing" contract is checked explicitly, since
that is what makes the feature safe to ship against unprobed servers.
"""

from unittest.mock import Mock

import pytest

from caldav.calendarobjectresource import _quote_uid
from caldav.collection import _quote_url_path, _sanitize_calendar_home_set_url
from caldav.compatibility_hints import (
    FeatureSet,
    _at_path_policy,
    _rejects_encoded_at,
    _requires_encoded_at,
)

HOME_SET = "/remote.php/dav/calendars/tobixen@e.email/"
ABS_URL = "http://dav.example.com/cal/tobixen@e.email/"


def features(**node) -> FeatureSet:
    """A FeatureSet with ``url.encode-at`` declared as given."""
    fs = FeatureSet()
    if node:
        fs.set_feature("url.encode-at", node)
    return fs


class TestPolicyDerivation:
    """``_at_path_policy`` is the single place the two axes are read."""

    @pytest.mark.parametrize(
        "node,expected",
        [
            ({}, None),
            ({"support": "quirk", "at-spelling": "encoded"}, "encode"),
            ({"support": "ungraceful", "at-spelling": "literal"}, "literal"),
            ({"support": "full", "at-spelling": "both", "at-identity": "aliased"}, None),
            (
                {"support": "unsupported", "at-spelling": "both", "at-identity": "distinct"},
                "preserve",
            ),
            ## "both" with the identity axis unobserved: not enough to act on.
            ({"support": "unknown", "at-spelling": "both"}, None),
        ],
    )
    def test_matrix(self, node, expected) -> None:
        assert _at_path_policy(features(**node)) == expected

    def test_no_features_object_at_all(self) -> None:
        assert _at_path_policy(None) is None

    def test_an_unrecognised_spelling_is_ignored_not_guessed_at(self) -> None:
        """A typo in a profile must not silently rewrite URLs."""
        assert _at_path_policy(features(support="quirk", at_spelling="encodedd")) is None
        assert _at_path_policy(features(**{"support": "quirk", "at-spelling": "ENCODED"})) is None

    def test_an_unrecognised_identity_does_not_reach_preserve(self) -> None:
        node = {"support": "unknown", "at-spelling": "both", "at-identity": "seperate"}
        assert _at_path_policy(features(**node)) is None

    def test_a_declared_parent_node_does_not_reach_the_child(self) -> None:
        """``url`` is a grouping node, and the ancestor walk in is_supported()
        hands back an explicitly declared parent.  It carries neither extra
        key, so it must not start deciding how the child spells its paths."""
        fs = FeatureSet()
        fs.set_feature("url", {"support": "quirk"})
        assert _at_path_policy(fs) is None

    def test_the_support_level_alone_decides_nothing(self) -> None:
        """A severity word must never be made to name a behaviour."""
        for level in ("full", "quirk", "unsupported", "ungraceful", "broken", "fragile"):
            assert _at_path_policy(features(support=level)) is None

    def test_is_supported_true_claims_the_encoded_form_reaches_the_resource(self) -> None:
        """The documented meaning of the boolean view, pinned."""
        both = features(support="full", **{"at-spelling": "both", "at-identity": "aliased"})
        encoded = features(support="quirk", **{"at-spelling": "encoded"})
        literal = features(support="ungraceful", **{"at-spelling": "literal"})
        distinct = features(
            support="unsupported", **{"at-spelling": "both", "at-identity": "distinct"}
        )
        assert both.is_supported("url.encode-at") is True
        assert encoded.is_supported("url.encode-at") is True
        assert literal.is_supported("url.encode-at") is False
        assert distinct.is_supported("url.encode-at") is False


class TestNothingDeclaredChangesNothing:
    """Every call site keeps the heuristic it had before the feature existed."""

    @pytest.mark.parametrize("fs", [None, FeatureSet()])
    def test_quote_url_path(self, fs) -> None:
        assert _quote_url_path(ABS_URL, fs) == ABS_URL
        ## the historic round-trip normalises an incoming %40 down to @ ...
        assert _quote_url_path(ABS_URL.replace("@", "%40"), fs) == ABS_URL
        ## ... and its actual purpose, quoting Zimbra's raw spaces, still works
        assert _quote_url_path("http://x/a b/", fs) == "http://x/a%20b/"

    @pytest.mark.parametrize("fs", [None, FeatureSet()])
    def test_home_set_is_quoted_the_owncloud_way(self, fs) -> None:
        assert _sanitize_calendar_home_set_url(HOME_SET, fs) == HOME_SET.replace("@", "%40")

    @pytest.mark.parametrize("fs", [None, FeatureSet()])
    def test_quote_uid_encodes_the_at(self, fs) -> None:
        assert _quote_uid("foo@example.com", fs) == "foo%40example.com"

    def test_a_declared_level_without_the_extra_keys_is_still_nothing(self) -> None:
        fs = features(support="quirk", behaviour="the @ is only honoured mid-path")
        assert _quote_url_path(ABS_URL, fs) == ABS_URL
        assert _sanitize_calendar_home_set_url(HOME_SET, fs) == HOME_SET.replace("@", "%40")
        assert _quote_uid("foo@example.com", fs) == "foo%40example.com"


class TestEncodedOnlyServer:
    """``at-spelling: encoded`` - only ``%40`` resolves, so the client encodes."""

    FS = features(support="quirk", **{"at-spelling": "encoded"})

    def test_helper(self) -> None:
        assert _requires_encoded_at(self.FS)
        assert not _rejects_encoded_at(self.FS)

    def test_quote_url_path_rewrites_the_at(self) -> None:
        assert _quote_url_path(ABS_URL, self.FS) == ABS_URL.replace("@", "%40")

    def test_home_set_still_quoted(self) -> None:
        assert _sanitize_calendar_home_set_url(HOME_SET, self.FS) == HOME_SET.replace("@", "%40")

    def test_quote_uid_still_encodes(self) -> None:
        assert _quote_uid("foo@example.com", self.FS) == "foo%40example.com"


class TestLiteralOnlyServer:
    """``at-spelling: literal`` - ``%40`` 404s, so the client must never send it."""

    FS = features(support="ungraceful", **{"at-spelling": "literal"})

    def test_helper(self) -> None:
        assert _rejects_encoded_at(self.FS)
        assert not _requires_encoded_at(self.FS)

    def test_quote_url_path_keeps_the_literal_at(self) -> None:
        assert _quote_url_path(ABS_URL, self.FS) == ABS_URL
        ## an incoming %40 is decoded back to the only spelling that resolves
        assert _quote_url_path(ABS_URL.replace("@", "%40"), self.FS) == ABS_URL

    def test_home_set_is_left_alone(self) -> None:
        assert _sanitize_calendar_home_set_url(HOME_SET, self.FS) == HOME_SET

    def test_quote_uid_keeps_the_at(self) -> None:
        assert _quote_uid("foo@example.com", self.FS) == "foo@example.com"


class TestDistinctSpellingsServer:
    """``at-spelling: both`` + ``at-identity: distinct``.

    RFC3986's conformant reading, and the case that turns the library's own
    rewriting into silent data loss: write one resource, read another.  So
    neither spelling may be rewritten into the other.
    """

    FS = features(support="unsupported", **{"at-spelling": "both", "at-identity": "distinct"})

    def test_neither_helper_fires(self) -> None:
        assert not _requires_encoded_at(self.FS)
        assert not _rejects_encoded_at(self.FS)

    def test_both_spellings_survive_the_round_trip(self) -> None:
        assert _quote_url_path(ABS_URL, self.FS) == ABS_URL
        encoded = ABS_URL.replace("@", "%40")
        assert _quote_url_path(encoded, self.FS) == encoded

    def test_the_rest_of_the_path_is_still_normalised(self) -> None:
        """Preserving the @ must not cost us the Zimbra space quoting."""
        assert (
            _quote_url_path("http://x/a b/u@e.email/c d/", self.FS)
            == "http://x/a%20b/u@e.email/c%20d/"
        )

    def test_several_ats_in_one_path(self) -> None:
        url = "http://x/a@b/c%40d/e@f/"
        assert _quote_url_path(url, self.FS) == url

    def test_home_set_is_left_alone(self) -> None:
        """Echo the server's own bytes back rather than minting a new spelling."""
        assert _sanitize_calendar_home_set_url(HOME_SET, self.FS) == HOME_SET


class TestAliasedSpellingsServer:
    """``at-spelling: both`` + ``at-identity: aliased`` - lenient, nothing to do."""

    FS = features(support="full", **{"at-spelling": "both", "at-identity": "aliased"})

    def test_behaves_exactly_as_an_undeclared_server(self) -> None:
        assert _quote_url_path(ABS_URL, self.FS) == _quote_url_path(ABS_URL, None)
        assert _sanitize_calendar_home_set_url(
            HOME_SET, self.FS
        ) == _sanitize_calendar_home_set_url(HOME_SET, None)
        assert _quote_uid("foo@example.com", self.FS) == _quote_uid("foo@example.com", None)


class TestNetlocIsNeverTouched:
    @pytest.mark.parametrize(
        "fs",
        [
            None,
            features(support="quirk", **{"at-spelling": "encoded"}),
            features(support="ungraceful", **{"at-spelling": "literal"}),
            features(support="unsupported", **{"at-spelling": "both", "at-identity": "distinct"}),
        ],
    )
    def test_credentials_in_the_url_survive(self, fs) -> None:
        url = "http://user@example.com:pw@dav.example.com/cal/"
        assert _quote_url_path(url, fs).startswith("http://user@example.com:pw@dav.example.com/")


class TestGeneratedObjectUrl:
    """``_generate_url`` reaches ``_quote_uid`` with the client's features."""

    def _event(self, fs):
        from caldav.calendarobjectresource import Event
        from caldav.lib.url import URL

        client = Mock()
        client.features = fs
        parent = Mock()
        parent.url = URL.objectify("http://dav.example.com/cal/")
        ## the UID lives in the calendar data, not in an attribute
        data = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
            "BEGIN:VEVENT\r\nUID:foo@example.com\r\nDTSTAMP:20260101T120000Z\r\n"
            "DTSTART:20260101T120000Z\r\nSUMMARY:x\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        return Event(client=client, parent=parent, data=data)

    def test_default_encodes(self) -> None:
        assert str(self._event(FeatureSet())._generate_url()).endswith("foo%40example.com.ics")

    def test_literal_only_server_keeps_the_at(self) -> None:
        fs = features(support="ungraceful", **{"at-spelling": "literal"})
        assert str(self._event(fs)._generate_url()).endswith("foo@example.com.ics")
