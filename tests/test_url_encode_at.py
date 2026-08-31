"""Tests for the ``url.encode-at`` compatibility feature.

Three independently observable facts about a literal ``@`` in a resource path,
one subfeature each: whether the two spellings name one resource
(``url.encode-at.identity``), whether the literal ``@`` resolves
(``.literal``), and whether ``%40`` resolves (``.encoded``).

``.identity`` is the switch everything turns on, and its 3.x default is the
*non*-conformant ``unsupported``: where the two spellings name one resource the
spelling carries no information, so the client normalises paths exactly as it
always has.  Only a server declared conformant makes the spelling part of the
name, and only there does the client start preserving it.

The first class below is the important one - it asserts, expression by
expression, that a server nobody has probed sees byte-for-byte what it saw
before this feature existed.  That is what makes the feature safe to ship
against the ~40 profiles nobody is going to re-probe.
"""

from unittest.mock import Mock
from urllib.parse import quote, unquote

import pytest

from caldav.calendarobjectresource import _quote_uid
from caldav.collection import _quote_url_path, _sanitize_calendar_home_set_url
from caldav.compatibility_hints import (
    FeatureSet,
    at_literal_is_refused,
    at_spelling_is_significant,
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


CONFORMANT = features(identity="full")
NO_LITERAL = features(literal="unsupported")
NO_ENCODED = features(encoded="unsupported")


class TestNothingDeclaredChangesNothing:
    """Every expression here is the one the call site used before the feature.

    Written out rather than referenced, so that changing the production code
    cannot quietly change what "unchanged" means.
    """

    @pytest.mark.parametrize("fs", [None, FeatureSet()])
    def test_a_uid_is_percent_encoded_as_it_always_was(self, fs) -> None:
        assert _quote_uid("foo@example.com", fs) == quote(
            "foo@example.com".replace("/", "%2F"), safe="/"
        )
        assert _quote_uid("foo@example.com", fs) == "foo%40example.com"

    @pytest.mark.parametrize("fs", [None, FeatureSet()])
    def test_a_path_is_quoted_as_it_always_was(self, fs) -> None:
        for path in ("/cal/u@e.email/x.ics", "/cal/u%40e.email/x.ics", "/cal/a b/u@e/"):
            url = "http://dav.example.com" + path
            assert _quote_url_path(url, fs) == "http://dav.example.com" + quote(
                unquote(path), safe="/@"
            )

    def test_an_href_is_decoded_as_it_always_was(self) -> None:
        for href in ("/cal/u%40e.email/x.ics", "/cal/My%20Cal/", "/cal/u@e.email/"):
            assert _normalize_href(href) == unquote(href)

    @pytest.mark.parametrize("fs", [None, FeatureSet()])
    def test_the_owncloud_home_set_hack_still_fires(self, fs) -> None:
        """It has quoted a relative home-set containing an '@' since 2021."""
        assert _sanitize_calendar_home_set_url(HOME_SET, fs) == ENCODED_HOME_SET

    @pytest.mark.parametrize("fs", [None, FeatureSet()])
    def test_the_home_set_hack_still_skips_what_it_always_skipped(self, fs) -> None:
        assert _sanitize_calendar_home_set_url(ABS_URL, fs) == ABS_URL
        assert _sanitize_calendar_home_set_url(ENCODED_HOME_SET, fs) == ENCODED_HOME_SET
        assert (
            _sanitize_calendar_home_set_url("/dav/calendars/plain/", fs) == "/dav/calendars/plain/"
        )
        assert _sanitize_calendar_home_set_url(None, fs) is None

    def test_two_spellings_are_still_one_url(self) -> None:
        literal = URL("http://dav.example.com/cal/u@e.email/x.ics")
        encoded = URL("http://dav.example.com/cal/u%40e.email/x.ics")
        assert literal == encoded
        assert hash(literal) == hash(encoded)
        assert len({literal, encoded}) == 1


class TestTheOneThingThatIsFixedRegardless:
    def test_the_home_set_hack_no_longer_double_encodes(self) -> None:
        """``quote()`` on an already-quoted home-set turned ``%20`` into
        ``%2520``.  The old ``"%40" not in url`` guard only guarded ``%40``,
        so a home-set with a literal ``@`` *and* another escape still broke.
        """
        assert (
            _sanitize_calendar_home_set_url("/dav/calendars/t@e.email/My%20Cal/")
            == "/dav/calendars/t%40e.email/My%20Cal/"
        )


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
    """``at_spelling_to_mint`` - what the two minting sites ask."""

    @pytest.mark.parametrize(
        "fs,expected",
        [
            (None, "%40"),
            (FeatureSet(), "%40"),
            (CONFORMANT, "%40"),
            (NO_LITERAL, "%40"),
            (NO_ENCODED, "@"),
        ],
    )
    def test_matrix(self, fs, expected) -> None:
        assert at_spelling_to_mint(fs) == expected

    def test_encoding_is_the_default_because_that_is_what_we_always_sent(self) -> None:
        """Not because it is prettier - RFC3986 section 3.3 says '@' needs no
        encoding at all.  Objects stored by older versions of this library are
        at the '%40' URL, and that is the only thing deciding it."""
        assert at_spelling_to_mint(FeatureSet()) == "%40"

    @pytest.mark.parametrize("level", ["unknown", "fragile"])
    def test_a_non_observation_does_not_move_the_minted_spelling(self, level) -> None:
        """ "We could not tell" is not "'%40' will not work".

        A probe that could not reach a verdict records the subfeature
        explicitly - 'unknown', or 'fragile' where two probes disagreed - and
        such a node overrides the 'full' default.  Read as a plain boolean that
        lands in the same bucket as 'unsupported', so a server nobody could
        measure would silently move every minted email-UID object off the '%40'
        URL this library has always used, onto '@'.  Only an actual observation
        that the encoded spelling does not resolve may do that.
        """
        assert at_spelling_to_mint(features(encoded=level)) == "%40"

    def test_an_observed_refusal_still_moves_it(self) -> None:
        """The counterpart: a real observation must keep working, or the
        ownCloud-shaped server this exists for gets a URL it cannot serve."""
        assert at_spelling_to_mint(features(encoded="unsupported")) == "@"


class TestANonObservationNeverRewritesAGivenSpelling:
    """The same rule on the other switch, where it bites the opposite way.

    ``at_literal_is_refused`` is only consulted for a server declared
    conformant, and there the two spellings are two resources - so rewriting
    the ``@`` the server handed out addresses something else.  Doing that
    because a probe recorded ``unknown`` would 404 a home-set that worked.
    """

    HOME = "/remote.php/dav/calendars/tobixen@e.email/"

    @pytest.mark.parametrize("level", ["unknown", "fragile"])
    def test_an_undecided_probe_leaves_a_conformant_home_set_alone(self, level) -> None:
        fs = features(identity="full", literal=level)
        assert at_literal_is_refused(fs) is False
        assert _sanitize_calendar_home_set_url(self.HOME, fs) == self.HOME

    def test_an_observed_refusal_still_encodes_it(self) -> None:
        """The ownCloud case itself must keep working."""
        fs = features(identity="full", literal="unsupported")
        assert at_literal_is_refused(fs) is True
        assert _sanitize_calendar_home_set_url(self.HOME, fs) == self.HOME.replace("@", "%40")

    def test_an_unprobed_conformant_server_keeps_its_bytes(self) -> None:
        assert _sanitize_calendar_home_set_url(self.HOME, features(identity="full")) == self.HOME


class TestWhetherTheSpellingMatters:
    @pytest.mark.parametrize(
        "fs,aliased",
        [(None, True), (FeatureSet(), True), (NO_LITERAL, True), (CONFORMANT, False)],
    )
    def test_matrix(self, fs, aliased) -> None:
        assert at_spellings_are_aliased(fs) is aliased
        assert at_spelling_is_significant(fs) is not aliased


class TestAConformantServerKeepsEverySpelling:
    """One switch, and it reaches every place a spelling could move."""

    @pytest.mark.parametrize("spelling", ["@", "%40"])
    def test_requote_path_preserves_it(self, spelling) -> None:
        path = f"/cal/u{spelling}e.email/x.ics"
        assert requote_path(path) == path

    def test_requote_path_still_normalises_everything_else(self) -> None:
        """Preserving the @ must not cost us the Zimbra space quoting."""
        assert requote_path("/a b/u@e.email/c d/") == "/a%20b/u@e.email/c%20d/"

    @pytest.mark.parametrize("spelling", ["@", "%40"])
    def test_a_path_from_the_server_keeps_its_spelling(self, spelling) -> None:
        url = ABS_URL.replace("@", spelling)
        assert _quote_url_path(url, CONFORMANT) == url

    def test_a_path_is_still_quoted_for_everything_else(self) -> None:
        assert _quote_url_path("http://x/a b/u@e/", CONFORMANT) == "http://x/a%20b/u@e/"

    def test_the_netloc_is_never_touched(self) -> None:
        """Credentials embedded in the URL survive."""
        url = "http://user@example.com:pw@dav.example.com/cal/"
        for fs in (None, CONFORMANT):
            assert _quote_url_path(url, fs).startswith(
                "http://user@example.com:pw@dav.example.com/"
            )

    @pytest.mark.parametrize("spelling", ["@", "%40"])
    def test_an_href_keeps_the_spelling_the_server_used(self, spelling) -> None:
        href = f"/remote.php/dav/calendars/tobixen{spelling}e.email/x.ics"
        assert _normalize_href(href, preserve_at=True) == href

    def test_an_href_is_still_decoded_everywhere_else(self) -> None:
        assert (
            _normalize_href("/cal/My%20Cal/u%40e.email/", preserve_at=True)
            == "/cal/My Cal/u%40e.email/"
        )

    def test_an_absolute_href_is_still_reduced_to_its_path(self) -> None:
        """Ref https://github.com/python-caldav/caldav/issues/435"""
        assert (
            _normalize_href("http://dav.example.com/cal/u%40e.email/", preserve_at=True)
            == "/cal/u%40e.email/"
        )

    def test_the_confluence_double_encoding_fix_still_fires(self) -> None:
        """Ref https://github.com/python-caldav/caldav/issues/471"""
        assert _normalize_href("/cal/u%2540e.email/", preserve_at=True) == "/cal/u%40e.email/"

    def test_the_home_set_hack_is_off(self) -> None:
        """Rewriting a home-set on a conformant server addresses another resource."""
        assert _sanitize_calendar_home_set_url(HOME_SET, CONFORMANT) == HOME_SET

    def test_unless_the_literal_spelling_is_the_one_that_does_not_serve(self) -> None:
        """The case the 2021 hack was actually written for."""
        fs = features(identity="full", literal="unsupported")
        assert _sanitize_calendar_home_set_url(HOME_SET, fs) == ENCODED_HOME_SET
        ## ...and then the absolute form too, which the hack never covered
        assert _sanitize_calendar_home_set_url(ABS_URL, fs) == ABS_URL.replace("@", "%40")

    def test_two_spellings_are_two_urls(self) -> None:
        literal = URL("http://dav.example.com/cal/u@e.email/x.ics", alias_at=False)
        encoded = URL("http://dav.example.com/cal/u%40e.email/x.ics", alias_at=False)
        assert literal != encoded
        assert hash(literal) != hash(encoded)
        assert len({literal, encoded}) == 2

    def test_the_reading_is_inherited_by_every_derived_url(self) -> None:
        """Set once on the client's URL; everything is joined onto that."""
        root = URL("http://dav.example.com/cal/", alias_at=False)
        assert root.join("u%40e.email/").alias_at is False
        assert root.join("u%40e.email/").canonical().alias_at is False
        assert root.unauth().alias_at is False
        assert root.strip_trailing_slash().alias_at is False

    def test_canonical_still_does_its_other_jobs(self) -> None:
        """Credentials stripped, double slashes gone."""
        url = URL("http://u:p@dav.example.com//cal//u@e.email/", alias_at=False)
        assert "u:p@" not in str(url.canonical())
        assert "//cal" not in str(url.canonical()).replace("http://", "")


class TestTheTwoPlacesThatMintASpelling:
    def test_a_uid_is_encoded_unless_that_will_not_work(self) -> None:
        assert _quote_uid("foo@example.com", NO_ENCODED) == "foo@example.com"
        assert _quote_uid("foo@example.com", NO_LITERAL) == "foo%40example.com"

    def test_a_uid_still_double_quotes_a_slash(self) -> None:
        """A slash becomes %2F and *then* gets quoted, hence %252F.

        Ref https://github.com/python-caldav/caldav/issues/143 - deliberate,
        and unrelated to the @ spelling, but it shares the one quote() call so
        it is worth pinning here.
        """
        assert _quote_uid("a/b") == "a%252Fb"
        assert _quote_uid("a/b", NO_ENCODED) == "a%252Fb"

    def _calendar_set(self, fs):
        from caldav.collection import CalendarSet

        client = Mock()
        client.features = fs
        client.url = URL("http://dav.example.com/")
        return CalendarSet(client, url="http://dav.example.com/cal/")

    def test_a_cal_id_is_encoded_as_it_always_was(self) -> None:
        cal = self._calendar_set(FeatureSet()).calendar(cal_id="u@e.email")
        assert str(cal.url).endswith("/u%40e.email/")

    def test_a_cal_id_uses_the_literal_where_encoding_will_not_work(self) -> None:
        cal = self._calendar_set(NO_ENCODED).calendar(cal_id="u@e.email")
        assert str(cal.url).endswith("/u@e.email/")


class TestObjectUrlsFromTheServer:
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
    def test_multiget_normalises_as_it_always_did(self, href) -> None:
        """``safe="/:@"`` since forever, so both spellings arrive as ``@``."""
        obj = self._calendar(FeatureSet())._post_multiget([(href, EVENT)])[0]
        assert str(obj.url).endswith(self.HREF)

    @pytest.mark.parametrize("href", [HREF, HREF_ENCODED])
    def test_multiget_preserves_on_a_conformant_server(self, href) -> None:
        obj = self._calendar(CONFORMANT)._post_multiget([(href, EVENT)])[0]
        assert str(obj.url).endswith(href)

    def test_the_two_urls_stay_apart_on_a_conformant_server(self) -> None:
        cal = self._calendar(CONFORMANT)
        literal = cal._post_multiget([(self.HREF, EVENT)])[0]
        encoded = cal._post_multiget([(self.HREF_ENCODED, EVENT)])[0]
        assert str(literal.url) != str(encoded.url)
        assert literal.url != encoded.url


class TestLiteralIsPerAxis:
    """``url.encode-at.literal`` has one child per thing a path can put an ``@`` in.

    The other two subfeatures stay shared.  This one had to be split because a
    real server was seen to differ between the axes: Stalwart re-encodes an
    ``@`` in an *object* name (a PUT to the literal path is accepted and the
    resource is then reachable only under ``%40``) while serving a *calendar*
    path under whichever spelling it was asked for.  Merged into one verdict
    that came out ``fragile``, which says "somewhere this does not work" and
    leaves the one consumer - the ownCloud home-set hack - no way to know
    whether it was talking about the segment it cares about.
    """

    def test_the_children_exist(self) -> None:
        for axis in ("object", "collection", "principal"):
            assert f"url.encode-at.literal.{axis}" in FeatureSet.FEATURES

    def test_an_unprobed_axis_still_resolves_the_way_it_always_did(self) -> None:
        fs = FeatureSet()
        for axis in ("object", "collection", "principal"):
            assert fs.is_supported(f"url.encode-at.literal.{axis}")

    def test_an_old_profile_declaring_the_parent_still_reaches_the_children(self) -> None:
        """~40 profiles predate the split and none of them will be re-probed."""
        fs = features(literal="unsupported")
        for axis in ("object", "collection", "principal"):
            assert not fs.is_supported(f"url.encode-at.literal.{axis}")

    def test_a_child_does_not_decide_for_its_siblings(self) -> None:
        fs = features(**{"literal.object": "unsupported"})
        assert not fs.is_supported("url.encode-at.literal.object")
        assert fs.is_supported("url.encode-at.literal.collection")
        assert fs.is_supported("url.encode-at.literal.principal")


class TestTheHomeSetHackReadsThePrincipalAxis:
    """``at_literal_is_refused`` gates one thing: rewriting an ``@`` the server
    handed out in a calendar-home-set.  That is a username inside a path the
    server minted - the principal axis - and nothing else may switch it on."""

    def test_an_old_flat_declaration_still_switches_it_on(self) -> None:
        assert at_literal_is_refused(features(literal="unsupported"))

    def test_the_principal_axis_switches_it_on(self) -> None:
        assert at_literal_is_refused(features(**{"literal.principal": "unsupported"}))

    def test_an_object_name_observation_does_not(self) -> None:
        """The Stalwart shape.  Its object paths refuse the literal spelling and
        its principal path does not; encoding the ``@`` in a home-set it serves
        fine would address a different resource on a server declared
        conformant, which is the only kind that reaches this function."""
        assert not at_literal_is_refused(features(**{"literal.object": "unsupported"}))

    def test_a_calendar_id_observation_does_not_either(self) -> None:
        assert not at_literal_is_refused(features(**{"literal.collection": "unsupported"}))

    def test_the_stalwart_profile_leaves_a_given_home_set_alone(self) -> None:
        """End to end, through the call site: conformant server, object paths
        that refuse a literal ``@``, and a home-set that must survive intact."""
        fs = features(identity="full", **{"literal.object": "unsupported"})
        assert _sanitize_calendar_home_set_url(HOME_SET, fs) == HOME_SET

    def test_a_real_owncloud_observation_still_encodes(self) -> None:
        fs = features(identity="full", **{"literal.principal": "unsupported"})
        assert _sanitize_calendar_home_set_url(HOME_SET, fs) == ENCODED_HOME_SET
