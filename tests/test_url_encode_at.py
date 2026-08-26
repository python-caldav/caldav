"""Tests for the ``url.encode-at`` compatibility feature.

Three independently observable facts about a literal ``@`` in a resource path,
one subfeature each: whether the two spellings name one resource
(``.identity``), whether the literal ``@`` resolves (``.literal``), and whether
``%40`` resolves (``.encoded``).

``.literal`` and ``.encoded`` default to ``full``.  ``.identity`` deliberately
does not: its default is the *non*-conformant ``unsupported`` for the 3.x
series, because treating the two spellings as one URL is what this library has
always done and every server probed so far really does alias them.  A
conformant server has to say so out loud.

The rule the client follows is that it does not rewrite a spelling it was
handed.  There are exactly two places where it has no spelling to preserve and
must pick one - a UID and a cal_id it is minting a path from - and exactly one
where it overrides a spelling it *was* given: an ownCloud/Nextcloud
calendar-home-set, whose server hands out a literal ``@`` and then refuses to
serve it.  Most of what follows is about the places that must leave it alone.
"""

from unittest.mock import Mock

import pytest

from caldav.calendarobjectresource import _quote_uid
from caldav.collection import _quote_url_path, _sanitize_calendar_home_set_url
from caldav.compatibility_hints import (
    FeatureSet,
    at_spelling_to_mint,
    at_spellings_are_aliased,
)
from caldav.lib.url import URL, requote_path
from caldav.response import _normalize_href

HOME_SET = "/remote.php/dav/calendars/tobixen@e.email/"
ENCODED_HOME_SET = HOME_SET.replace("@", "%40")
ABS_URL = "http://dav.example.com/cal/tobixen@e.email/"

EVENT = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
    "BEGIN:VEVENT\r\nUID:foo@example.com\r\nDTSTAMP:20260101T120000Z\r\n"
    "DTSTART:20260101T120000Z\r\nSUMMARY:x\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
)


def features(**subfeatures) -> FeatureSet:
    """A FeatureSet with the named ``url.encode-at`` subfeatures declared.

    Keyword names use an underscore for the dot: ``literal="unsupported"``.
    """
    fs = FeatureSet()
    for name, support in subfeatures.items():
        fs.set_feature(f"url.encode-at.{name}", support)
    return fs


OWNCLOUD = features(literal="unsupported")
CONFORMANT = features(identity="full")


class TestTheFeatureShape:
    def test_the_three_subfeatures_exist(self) -> None:
        for name in ("identity", "literal", "encoded"):
            assert f"url.encode-at.{name}" in FeatureSet.FEATURES

    def test_both_spellings_are_assumed_to_resolve(self) -> None:
        fs = FeatureSet()
        assert fs.is_supported("url.encode-at.literal")
        assert fs.is_supported("url.encode-at.encoded")

    def test_identity_defaults_to_the_non_conformant_reading_in_3_x(self) -> None:
        """Deliberate: the conformant default would change URL identity for
        every user of an unprobed server, and no server probed so far is
        conformant anyway.  4.0 should flip it."""
        assert not FeatureSet().is_supported("url.encode-at.identity")

    def test_the_parent_is_a_grouping_node_with_no_default(self) -> None:
        """Otherwise the ancestor walk would let it decide for the children."""
        assert "default" not in FeatureSet.FEATURES["url.encode-at"]

    def test_a_declared_parent_reaches_the_children(self) -> None:
        """The ancestor walk is what it is; a profile declaring the parent is
        making a claim about all three, which is why profiles declare the
        subfeature they actually observed instead."""
        fs = FeatureSet()
        fs.set_feature("url.encode-at", {"support": "unsupported"})
        assert not fs.is_supported("url.encode-at.literal")


class TestWhichSpellingGetsMinted:
    """``at_spelling_to_mint`` - the only question the minting sites ask."""

    @pytest.mark.parametrize(
        "fs,expected",
        [
            (None, "@"),
            (FeatureSet(), "@"),
            (features(identity="unsupported"), "@"),
            (features(encoded="unsupported"), "@"),
            (OWNCLOUD, "%40"),
            (features(literal="unsupported", encoded="unsupported"), "%40"),
        ],
    )
    def test_matrix(self, fs, expected) -> None:
        assert at_spelling_to_mint(fs) == expected

    def test_the_literal_at_is_the_default_because_the_rfc_allows_it(self) -> None:
        """RFC3986 section 3.3: '@' is a legal pchar.  Encoding it is a rewrite
        nobody asked for, so it only happens where a server refuses it."""
        assert at_spelling_to_mint(FeatureSet()) == "@"


class TestWhetherTheSpellingsAreAliased:
    @pytest.mark.parametrize(
        "fs,expected",
        [
            (None, False),
            (FeatureSet(), True),
            (OWNCLOUD, True),
            (CONFORMANT, False),
        ],
    )
    def test_matrix(self, fs, expected) -> None:
        assert at_spellings_are_aliased(fs) is expected


class TestTheClientNeverRewritesASpellingItWasGiven:
    """The core contract.  Everything here takes a path the *server* named."""

    @pytest.mark.parametrize("spelling", ["@", "%40"])
    def test_requote_path_preserves_it(self, spelling) -> None:
        path = f"/cal/u{spelling}e.email/x.ics"
        assert requote_path(path) == path

    def test_requote_path_still_normalises_everything_else(self) -> None:
        """Preserving the @ must not cost us the Zimbra space quoting."""
        assert requote_path("/a b/u@e.email/c d/") == "/a%20b/u@e.email/c%20d/"

    @pytest.mark.parametrize("spelling", ["@", "%40"])
    def test_quote_url_path_preserves_it(self, spelling) -> None:
        url = ABS_URL.replace("@", spelling)
        assert _quote_url_path(url) == url

    def test_quote_url_path_leaves_the_netloc_alone(self) -> None:
        """Credentials embedded in the URL survive."""
        url = "http://user@example.com:pw@dav.example.com/cal/"
        assert _quote_url_path(url).startswith("http://user@example.com:pw@dav.example.com/")

    @pytest.mark.parametrize("spelling", ["@", "%40"])
    def test_an_href_keeps_the_spelling_the_server_used(self, spelling) -> None:
        href = f"/remote.php/dav/calendars/tobixen{spelling}e.email/x.ics"
        assert _normalize_href(href) == href

    def test_an_href_is_still_decoded_everywhere_else(self) -> None:
        assert _normalize_href("/cal/My%20Cal/u%40e.email/") == "/cal/My Cal/u%40e.email/"

    def test_an_absolute_href_is_still_reduced_to_its_path(self) -> None:
        """Ref https://github.com/python-caldav/caldav/issues/435"""
        assert _normalize_href("http://dav.example.com/cal/u%40e.email/") == "/cal/u%40e.email/"

    def test_the_confluence_double_encoding_fix_still_fires(self) -> None:
        """Ref https://github.com/python-caldav/caldav/issues/471"""
        assert _normalize_href("/cal/u%2540e.email/") == "/cal/u%40e.email/"

    def test_several_ats_in_one_path_each_keep_their_own_spelling(self) -> None:
        path = "/a@b/c%40d/e@f/"
        assert requote_path(path) == path


class TestUrlIdentity:
    """``canonical()`` decides ``__eq__`` and ``__hash__``.  It used to
    normalise ``@`` to ``%40`` unconditionally, which says two spellings are
    one resource - the lenient reading, and not the default any more."""

    LITERAL = "http://dav.example.com/cal/u@e.email/x.ics"
    ENCODED = "http://dav.example.com/cal/u%40e.email/x.ics"

    def test_two_spellings_are_one_url_by_default(self) -> None:
        """The 3.x default, and what this library has always done."""
        assert URL(self.LITERAL) == URL(self.ENCODED)
        assert hash(URL(self.LITERAL)) == hash(URL(self.ENCODED))
        assert len({URL(self.LITERAL), URL(self.ENCODED)}) == 1

    def test_a_server_declared_conformant_gets_two_urls(self) -> None:
        literal = URL(self.LITERAL, alias_at=False)
        encoded = URL(self.ENCODED, alias_at=False)
        assert literal != encoded
        assert hash(literal) != hash(encoded)
        assert len({literal, encoded}) == 2

    @pytest.mark.parametrize("alias_at", [False, True])
    def test_canonical_still_does_its_other_jobs(self, alias_at) -> None:
        """Credentials stripped, double slashes gone, port filled in."""
        url = URL("http://u:p@dav.example.com//cal//u@e.email/", alias_at=alias_at)
        assert "u:p@" not in str(url.canonical())
        assert "//cal" not in str(url.canonical()).replace("http://", "")

    def test_the_reading_is_inherited_by_every_derived_url(self) -> None:
        """Set once on the client's URL; everything is joined onto that."""
        root = URL("http://dav.example.com/cal/", alias_at=False)
        assert root.join("u%40e.email/").alias_at is False
        assert root.join("u%40e.email/").canonical().alias_at is False
        assert root.unauth().alias_at is False
        assert root.strip_trailing_slash().alias_at is False

    def test_a_plain_url_keeps_the_3_x_default(self) -> None:
        assert URL("http://x/a@b/").alias_at is True


class TestTheTwoPlacesThatMintASpelling:
    def test_a_uid_gets_a_literal_at_by_default(self) -> None:
        """It used to be encoded unconditionally."""
        assert _quote_uid("foo@example.com") == "foo@example.com"
        assert _quote_uid("foo@example.com", FeatureSet()) == "foo@example.com"

    def test_a_uid_is_encoded_only_where_the_literal_is_refused(self) -> None:
        assert _quote_uid("foo@example.com", OWNCLOUD) == "foo%40example.com"

    def test_a_uid_still_double_quotes_a_slash(self) -> None:
        """A slash becomes %2F and *then* gets quoted, hence %252F.

        Ref https://github.com/python-caldav/caldav/issues/143 - deliberate,
        and unrelated to the @ spelling, but it shares the one quote() call so
        it is worth pinning here.
        """
        assert _quote_uid("a/b") == "a%252Fb"
        assert _quote_uid("a/b", OWNCLOUD) == "a%252Fb"

    def _calendar_set(self, fs):
        from caldav.collection import CalendarSet

        client = Mock()
        client.features = fs
        client.url = URL("http://dav.example.com/")
        return CalendarSet(client, url="http://dav.example.com/cal/")

    def test_a_cal_id_gets_a_literal_at_by_default(self) -> None:
        cal = self._calendar_set(FeatureSet()).calendar(cal_id="u@e.email")
        assert str(cal.url).endswith("/u@e.email/")

    def test_a_cal_id_is_encoded_only_where_the_literal_is_refused(self) -> None:
        cal = self._calendar_set(OWNCLOUD).calendar(cal_id="u@e.email")
        assert str(cal.url).endswith("/u%40e.email/")

    def test_a_cal_id_is_never_double_encoded(self) -> None:
        """``quote()`` on an already-quoted id gave ``%2540``."""
        cal = self._calendar_set(OWNCLOUD).calendar(cal_id="u%40e.email")
        assert "%2540" not in str(cal.url)
        assert str(cal.url).endswith("/u%40e.email/")


class TestTheOwnCloudHomeSet:
    """The one place the client overrides a spelling the server gave it."""

    def test_an_undeclared_server_gets_its_own_bytes_back(self) -> None:
        """This used to rewrite unconditionally, for every server."""
        assert _sanitize_calendar_home_set_url(HOME_SET) == HOME_SET
        assert _sanitize_calendar_home_set_url(HOME_SET, FeatureSet()) == HOME_SET

    def test_a_server_refusing_the_literal_gets_it_encoded(self) -> None:
        assert _sanitize_calendar_home_set_url(HOME_SET, OWNCLOUD) == ENCODED_HOME_SET

    def test_an_absolute_home_set_too(self) -> None:
        """The historic heuristic bailed on ``"://" in url`` and always did."""
        assert _sanitize_calendar_home_set_url(ABS_URL, OWNCLOUD) == ABS_URL.replace("@", "%40")

    def test_an_already_encoded_home_set_is_left_as_it_is(self) -> None:
        assert _sanitize_calendar_home_set_url(ENCODED_HOME_SET, OWNCLOUD) == ENCODED_HOME_SET

    def test_the_rest_of_the_path_is_not_double_encoded(self) -> None:
        """``quote()`` on an already-quoted home-set turned ``%20`` into
        ``%2520``.  The old ``"%40" not in url`` guard only guarded ``%40``."""
        assert (
            _sanitize_calendar_home_set_url("/dav/calendars/t@e.email/My%20Cal/", OWNCLOUD)
            == "/dav/calendars/t%40e.email/My%20Cal/"
        )

    def test_none_stays_none(self) -> None:
        assert _sanitize_calendar_home_set_url(None, OWNCLOUD) is None


class TestObjectUrlsComeBackAsTheServerSpeltThem:
    """``_post_multiget`` and the REPORT result list did not agree with each
    other: the same object came back with a literal ``@`` from one and ``%40``
    from the other.  Both preserve now, so they cannot disagree."""

    HREF = "/cal/u@e.email/foo@example.com.ics"
    HREF_ENCODED = "/cal/u%40e.email/foo%40example.com.ics"

    def _calendar(self, fs):
        from caldav.collection import Calendar

        client = Mock()
        client.features = fs
        ## the real client stamps this onto its own URL, and every URL the
        ## library builds is joined onto that one
        client.url = URL("http://dav.example.com/", alias_at=at_spellings_are_aliased(fs))
        return Calendar(client, url="http://dav.example.com/cal/u@e.email/", parent=None)

    @pytest.mark.parametrize("href", [HREF, HREF_ENCODED])
    @pytest.mark.parametrize("fs", [FeatureSet(), OWNCLOUD, CONFORMANT])
    def test_multiget_preserves_whatever_it_was_handed(self, href, fs) -> None:
        obj = self._calendar(fs)._post_multiget([(href, EVENT)])[0]
        assert str(obj.url).endswith(href)

    def test_the_two_urls_stay_apart_on_a_conformant_server(self) -> None:
        cal = self._calendar(CONFORMANT)
        literal = cal._post_multiget([(self.HREF, EVENT)])[0]
        encoded = cal._post_multiget([(self.HREF_ENCODED, EVENT)])[0]
        assert str(literal.url) != str(encoded.url)
        assert literal.url != encoded.url
