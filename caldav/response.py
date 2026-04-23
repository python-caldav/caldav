"""
DAV response parsing: base class, result types and XML parse functions.
"""

import logging
import warnings
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import unquote

from lxml import etree
from lxml.etree import _Element

from caldav.calendarobjectresource import FreeBusy
from caldav.elements import cdav, dav
from caldav.elements.base import BaseElement
from caldav.lib import error
from caldav.lib.python_utilities import to_normal_str
from caldav.lib.url import URL

if TYPE_CHECKING:
    Response = Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses (previously in protocol/types.py)
# ---------------------------------------------------------------------------


@dataclass
class PropfindResult:
    """Parsed result of a PROPFIND request for a single resource."""

    href: str
    properties: dict[str, Any] = field(default_factory=dict)
    status: int = 200


@dataclass
class CalendarQueryResult:
    """Parsed result of a calendar-query or calendar-multiget REPORT for a single object."""

    href: str
    etag: str | None = None
    calendar_data: str | None = None
    status: int = 200


@dataclass
class SyncCollectionResult:
    """Parsed result of a sync-collection REPORT."""

    changed: list[CalendarQueryResult] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    sync_token: str | None = None


@dataclass
class MultistatusResponse:
    """Parsed multi-status (207) response containing multiple PropfindResults."""

    responses: list[PropfindResult] = field(default_factory=list)
    sync_token: str | None = None


# ---------------------------------------------------------------------------
# XML parse helpers (previously in protocol/xml_parsers.py)
# ---------------------------------------------------------------------------


def _normalize_href(text: str) -> str:
    """Normalize an href string from a DAV response element.

    Handles the Confluence double-encoding bug (%2540 → %40) and converts
    absolute URLs to path-only strings so callers always work with paths.
    """
    # Fix for https://github.com/python-caldav/caldav/issues/471
    if "%2540" in text:
        text = text.replace("%2540", "%40")
    href = unquote(text)
    # Ref https://github.com/python-caldav/caldav/issues/435
    if ":" in href:
        href = unquote(URL(href).path)
    return href


def _validate_status(status: str | None) -> None:
    """Validate a status string like "HTTP/1.1 404 Not Found".

    200, 201, 207 and 404 are considered acceptable statuses.
    """
    if status is None:
        return
    if not any(code in status for code in (" 200 ", " 201 ", " 207 ", " 404 ")):
        raise error.ResponseError(status)


def _status_to_code(status: str | None) -> int:
    """Extract integer status code from a status string like "HTTP/1.1 200 OK"."""
    if not status:
        return 200
    parts = status.split()
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            pass
    return 200


def _strip_to_multistatus(tree: _Element) -> "_Element | list[_Element]":
    """Strip outer elements to reach the multistatus response children.

    The general format is <xml><multistatus><response>…</response>…</multistatus></xml>
    but sometimes the multistatus and/or xml wrapper is absent.
    """
    if tree.tag == "xml" and len(tree) > 0 and tree[0].tag == dav.MultiStatus.tag:
        return tree[0]
    if tree.tag == dav.MultiStatus.tag:
        return tree
    return [tree]


## TODO: _parse_response_element is a simplified version of DAVResponse._parse_response
## (which adds assertions and handles Stalwart/purelymail quirks).  The module-level parse
## functions (_parse_multistatus etc.) use this simpler version because they are pure
## functions with no access to a response instance.  If the parse pipeline were refactored
## to work through the tree already stored on self (avoiding the re-parse in _raw_bytes),
## both of these could be unified into a single method.
def _parse_response_element(
    response: _Element,
) -> "tuple[str, list[_Element], str | None]":
    """Parse a single DAV:response element into (href, propstats, status)."""
    status: str | None = None
    href: str | None = None
    propstats: list[_Element] = []
    for elem in response:
        if elem.tag == dav.Status.tag:
            status = elem.text
            _validate_status(status)
        elif elem.tag == dav.Href.tag:
            href = _normalize_href(elem.text or "")
        elif elem.tag == dav.PropStat.tag:
            propstats.append(elem)
    return (href or "", propstats, status)


def _extract_properties(propstats: "list[_Element]") -> "dict[str, Any]":
    """Extract properties from propstat elements into a flat dict."""
    properties: dict[str, Any] = {}
    for propstat in propstats:
        status_elem = propstat.find(dav.Status.tag)
        if status_elem is not None and status_elem.text and " 404 " in status_elem.text:
            continue
        prop = propstat.find(dav.Prop.tag)
        if prop is None:
            continue
        for child in prop:
            if len(child) == 0:
                properties[child.tag] = child.text
            else:
                properties[child.tag] = _element_to_value(child)
    return properties


def _element_to_value(elem: _Element) -> Any:
    """Convert a complex XML element to a Python value."""
    if len(elem) == 0:
        return elem.text

    tag = elem.tag

    if tag == cdav.SupportedCalendarComponentSet.tag:
        return [child.get("name") for child in elem if child.get("name")]

    if tag == cdav.CalendarUserAddressSet.tag:
        return [child.text for child in elem if child.tag == dav.Href.tag and child.text]

    if tag == cdav.CalendarHomeSet.tag:
        hrefs = [child.text for child in elem if child.tag == dav.Href.tag and child.text]
        return hrefs[0] if len(hrefs) == 1 else hrefs

    if tag == dav.ResourceType.tag:
        return [child.tag for child in elem]

    if tag == dav.CurrentUserPrincipal.tag:
        for child in elem:
            if child.tag == dav.Href.tag and child.text:
                return child.text
        return None

    children_texts = []
    for child in elem:
        if child.text:
            children_texts.append(child.text)
        elif child.get("name"):
            children_texts.append(child.get("name"))
        elif len(child) == 0:
            children_texts.append(child.tag)

    if len(children_texts) == 1:
        return children_texts[0]
    elif children_texts:
        return children_texts

    return elem


def _parse_multistatus(body: bytes, huge_tree: bool = False) -> MultistatusResponse:
    """Parse a 207 Multi-Status response body into a MultistatusResponse."""
    parser = etree.XMLParser(huge_tree=huge_tree)
    tree = etree.fromstring(body, parser)

    responses: list[PropfindResult] = []
    sync_token: str | None = None

    for elem in _strip_to_multistatus(tree):
        if elem.tag == dav.SyncToken.tag:
            sync_token = elem.text
            continue
        if elem.tag != dav.Response.tag:
            continue
        href, propstats, status = _parse_response_element(elem)
        properties = _extract_properties(propstats)
        responses.append(
            PropfindResult(
                href=href,
                properties=properties,
                status=_status_to_code(status) if status else 200,
            )
        )

    return MultistatusResponse(responses=responses, sync_token=sync_token)


def _parse_propfind_response(
    body: bytes, status_code: int = 207, huge_tree: bool = False
) -> list[PropfindResult]:
    """Parse a PROPFIND response body into a list of PropfindResult objects."""
    if status_code == 404:
        return []
    if status_code not in (200, 207):
        raise error.ResponseError(f"PROPFIND failed with status {status_code}")
    if not body:
        return []
    return _parse_multistatus(body, huge_tree=huge_tree).responses


def _parse_calendar_query_response(
    body: bytes, status_code: int = 207, huge_tree: bool = False
) -> list[CalendarQueryResult]:
    """Parse a calendar-query or calendar-multiget REPORT response."""
    if status_code not in (200, 207):
        raise error.ResponseError(f"REPORT failed with status {status_code}")
    if not body:
        return []

    parser = etree.XMLParser(huge_tree=huge_tree)
    tree = etree.fromstring(body, parser)
    results: list[CalendarQueryResult] = []

    for elem in _strip_to_multistatus(tree):
        if elem.tag != dav.Response.tag:
            continue
        href, propstats, status = _parse_response_element(elem)
        calendar_data: str | None = None
        etag: str | None = None
        for propstat in propstats:
            prop = propstat.find(dav.Prop.tag)
            if prop is None:
                continue
            for child in prop:
                if child.tag == cdav.CalendarData.tag:
                    calendar_data = child.text
                elif child.tag == dav.GetEtag.tag:
                    etag = child.text
        results.append(
            CalendarQueryResult(
                href=href,
                etag=etag,
                calendar_data=calendar_data,
                status=_status_to_code(status) if status else 200,
            )
        )

    return results


def _parse_sync_collection_response(
    body: bytes, status_code: int = 207, huge_tree: bool = False
) -> SyncCollectionResult:
    """Parse a sync-collection REPORT response."""
    if status_code not in (200, 207):
        raise error.ResponseError(f"sync-collection failed with status {status_code}")
    if not body:
        return SyncCollectionResult()

    parser = etree.XMLParser(huge_tree=huge_tree)
    tree = etree.fromstring(body, parser)
    changed: list[CalendarQueryResult] = []
    deleted: list[str] = []
    sync_token: str | None = None

    for elem in _strip_to_multistatus(tree):
        if elem.tag == dav.SyncToken.tag:
            sync_token = elem.text
            continue
        if elem.tag != dav.Response.tag:
            continue
        href, propstats, status = _parse_response_element(elem)
        status_code_elem = _status_to_code(status) if status else 200
        if status_code_elem == 404:
            deleted.append(href)
            continue
        calendar_data = None
        etag = None
        for propstat in propstats:
            prop = propstat.find(dav.Prop.tag)
            if prop is None:
                continue
            for child in prop:
                if child.tag == cdav.CalendarData.tag:
                    calendar_data = child.text
                elif child.tag == dav.GetEtag.tag:
                    etag = child.text
        changed.append(
            CalendarQueryResult(
                href=href,
                etag=etag,
                calendar_data=calendar_data,
                status=status_code_elem,
            )
        )

    return SyncCollectionResult(changed=changed, deleted=deleted, sync_token=sync_token)


class DAVResponse:
    """
    Base class containing shared response parsing logic.

    This class provides the XML parsing and response extraction methods
    that are common to both sync and async DAV responses.
    """

    tree: _Element | None = None
    headers: Any = None
    status: int = 0
    _raw: Any = ""
    huge_tree: bool = False
    reason: str = ""
    davclient: Any = None
    results: list[PropfindResult | CalendarQueryResult] | None = None
    _sync_token: str | None = None

    def __init__(self, response: "Response", davclient: Any = None) -> None:
        self._init_from_response(response, davclient)

    def _init_from_response(self, response: "Response", davclient: Any = None) -> None:
        """
        Initialize response from an HTTP response object.

        This shared method extracts headers, status, and parses XML content.
        Both DAVResponse and AsyncDAVResponse should call this from their __init__.

        Args:
            response: The HTTP response object from niquests
            davclient: Optional reference to the DAVClient for huge_tree setting
        """
        self.headers = response.headers
        self.status = response.status_code
        log.debug("response headers: " + str(self.headers))
        log.debug("response status: " + str(self.status))

        self._raw = response.content
        self.davclient = davclient
        if davclient:
            self.huge_tree = davclient.huge_tree

        content_type = self.headers.get("Content-Type", "")
        xml_types = ["text/xml", "application/xml"]
        no_xml_types = ["text/plain", "text/calendar", "application/octet-stream"]
        expect_xml = any(content_type.startswith(x) for x in xml_types)
        expect_no_xml = any(content_type.startswith(x) for x in no_xml_types)
        if (
            content_type
            and not expect_xml
            and not expect_no_xml
            and response.status_code < 400
            and response.text
        ):
            error.weirdness(f"Unexpected content type: {content_type}")
        try:
            content_length = int(self.headers["Content-Length"])
        except (KeyError, ValueError, TypeError):
            content_length = -1
        if content_length == 0 or not self._raw:
            self._raw = ""
            self.tree = None
            log.debug("No content delivered")
        else:
            # For really huge objects we should pass the object as a stream to the
            # XML parser, but we would also need to decompress on the fly.
            try:
                # https://github.com/python-caldav/caldav/issues/142
                # We cannot trust the content-type (iCloud, OX and others).
                # We'll try to parse the content as XML no matter the content type.
                self.tree = etree.XML(
                    self._raw,
                    parser=etree.XMLParser(remove_blank_text=True, huge_tree=self.huge_tree),
                )
            except Exception:
                # Content wasn't XML.  What does the content-type say?
                # expect_no_xml means text/plain or text/calendar -> ok, pass on
                # expect_xml means text/xml or application/xml -> raise an error
                # anything else -> log an info message and continue
                if not expect_no_xml or log.level <= logging.DEBUG:
                    if not expect_no_xml:
                        _log = logging.info
                    else:
                        _log = logging.debug
                    _log(
                        "Expected some valid XML from the server, but got this: \n"
                        + str(self._raw),
                        exc_info=True,
                    )
                if expect_xml:
                    raise
            else:
                if log.level <= logging.DEBUG:
                    log.debug(etree.tostring(self.tree, pretty_print=True))

        # this if will always be true as for now, see other comments on streaming.
        if hasattr(self, "_raw"):
            log.debug(self._raw)
            # ref https://github.com/python-caldav/caldav/issues/112 stray CRs may cause problems
            if isinstance(self._raw, bytes):
                self._raw = self._raw.replace(b"\r\n", b"\n")
            elif isinstance(self._raw, str):
                self._raw = self._raw.replace("\r\n", "\n")
        self.status = response.status_code
        # ref https://github.com/python-caldav/caldav/issues/81,
        # incidents with a response without a reason has been observed
        # httpx uses reason_phrase, niquests/requests use reason
        try:
            self.reason = getattr(response, "reason_phrase", None) or response.reason
        except AttributeError:
            self.reason = ""

    @property
    def raw(self) -> str:
        """Return the raw response content as a string."""
        if not hasattr(self, "_raw"):
            self._raw = etree.tostring(cast(_Element, self.tree), pretty_print=True)
        return to_normal_str(self._raw)

    def _strip_to_multistatus(self) -> _Element | list[_Element]:
        """
        The general format of inbound data is something like this:

        <xml><multistatus>
            <response>(...)</response>
            <response>(...)</response>
            (...)
        </multistatus></xml>

        but sometimes the multistatus and/or xml element is missing in
        self.tree.  We don't want to bother with the multistatus and
        xml tags, we just want the response list.

        An "Element" in the lxml library is a list-like object, so we
        should typically return the element right above the responses.
        If there is nothing but a response, return it as a list with
        one element.

        (The equivalent of this method could probably be found with a
        simple XPath query, but I'm not much into XPath)
        """
        return _strip_to_multistatus(self.tree)

    def validate_status(self, status: str) -> None:
        """
        status is a string like "HTTP/1.1 404 Not Found".  200, 207 and
        404 are considered good statuses.  The SOGo caldav server even
        returns "201 created" when doing a sync-report, to indicate
        that a resource was created after the last sync-token.  This
        makes sense to me, but I've only seen it from SOGo, and it's
        not in accordance with the examples in rfc6578.
        """
        _validate_status(status)

    def _raw_bytes(self) -> bytes:
        """Return raw response content as bytes."""
        raw = self._raw
        if isinstance(raw, bytes):
            return raw
        return raw.encode("utf-8") if raw else b""

    ## TODO: parse_propfind / parse_calendar_query / parse_sync_collection currently
    ## re-parse the XML from raw bytes (via _raw_bytes) even though _init_from_response
    ## already parsed it into self.tree.  A cleaner implementation would walk self.tree
    ## directly and use self._parse_response() (the assertion-rich class method) instead
    ## of re-parsing and using the simplified module-level _parse_response_element.
    ## That would also let us drop _raw_bytes, _parse_response_element, and _parse_multistatus.

    def parse_propfind(self) -> list["PropfindResult"]:
        """Parse the response body as a PROPFIND multi-status reply."""
        return _parse_propfind_response(self._raw_bytes(), self.status, self.huge_tree)

    def parse_calendar_query(self) -> list["CalendarQueryResult"]:
        """Parse the response body as a calendar-query or calendar-multiget REPORT reply."""
        return _parse_calendar_query_response(self._raw_bytes(), self.status, self.huge_tree)

    def parse_sync_collection(self) -> "SyncCollectionResult":
        """Parse the response body as a sync-collection REPORT reply."""
        return _parse_sync_collection_response(self._raw_bytes(), self.status, self.huge_tree)

    def _parse_response(self, response: _Element) -> tuple[str, list[_Element], Any | None]:
        """
        One response should contain one or zero status children, one
        href tag and zero or more propstats.  Find them, assert there
        isn't more in the response and return those three fields
        """
        status = None
        href: str | None = None
        propstats: list[_Element] = []
        check_404 = False  ## special for purelymail and stalwart
        error.assert_(response.tag == dav.Response.tag)
        for elem in response:
            if elem.tag == dav.Status.tag:
                error.assert_(not status)
                status = elem.text
                error.assert_(status)
                self.validate_status(status)
            elif elem.tag == dav.Href.tag:
                assert not href
                href = _normalize_href(elem.text or "")
            elif elem.tag == dav.PropStat.tag:
                propstats.append(elem)
            elif elem.tag == "{DAV:}responsedescription":
                ## This happens with Stalwart on a 404.
                ## This code is mostly moot, but in debug
                ## mode I want to be sure we do not toss away any data
                error.assert_(elem.text == "No resources found")
                check_404 = True
            elif elem.tag == "{DAV:}error":
                ## This happens with purelymail on a 404.
                ## This code is mostly moot, but in debug
                ## mode I want to be sure we do not toss away any data
                children = elem.getchildren()
                error.assert_(len(children) == 1)
                error.assert_(children[0].tag == "{https://purelymail.com}does-not-exist")
                check_404 = True
            else:
                ## i.e. purelymail may contain one more tag, <error>...</error>
                ## This is probably not a breach of the standard.  It may
                ## probably be ignored.  But it's something we may want to
                ## know.
                error.weirdness("unexpected element found in response", elem)
        error.assert_(href)
        if check_404:
            error.assert_("404" in status)
        return (cast(str, href), propstats, status)

    def _parse_scheduling_response_objects(self, parent) -> dict:
        """Parses an RFC6638 freebusy scheduling request response

        The response from the server is asserted to be a
        scheduling-response, with freebusy status for one or more wanted
        attendee - potentially with error status for all or some
        of the wanted attendees.

        TODO: some asserts here - should make better error handling

        Returns:
            Dict with:
              * email addresses -> FreeBusy status (raw data)
              * errors - dict with email addresses -> error messages

        """
        self.objects = {}
        self.objects["errors"] = {}
        assert self.tree.tag == cdav.ScheduleResponse.tag
        for response in self.tree:
            assert response.tag == cdav.Response.tag
            parsed_response = self._parse_scheduling_response(response)
            for x in parsed_response:
                if x.endswith(":err"):
                    self.objects["errors"][x[:-4]] = parsed_response[x]
                else:
                    self.objects[x] = FreeBusy(parent=parent, data=parsed_response[x])

        return self.objects

    def _parse_scheduling_response(self, response) -> dict[str, str]:
        """
        TODO: lots of asserts here - should make better error handling

        Parses one attendee response from a RFC6638 freebusy scheduling request

        Returns:
          * ``{ recipient => calendar_data }`` if everything is OK,
          * ``{f"{recipient}:err": status}`` if things are not OK,
          * a dict with both elements if things are partially OK
        """
        ret = {}
        recipient = None
        status = None
        calendar_data = None
        for x in response:
            if x.tag == cdav.Recipient.tag:
                if len(x) == 1:
                    assert x[0].tag == dav.Href.tag
                    recipient = x[0].text
                else:
                    recipient = x.text
            elif x.tag == cdav.RequestStatus.tag:
                status = x.text
            elif x.tag == cdav.CalendarData.tag:
                calendar_data = x.text
            else:
                raise error.DAVError(f"unexpected attribute {x.tag}")
        assert recipient
        assert status
        if not status.startswith("2.0"):
            ret[f"{recipient}:err"] = status
        if calendar_data:
            ret[recipient] = calendar_data
        return ret

    @property
    def sync_token(self):
        try:
            sync_token = self._sync_token
        except AttributeError:
            sync_token = None
        if sync_token is None:
            ## TODO: this should not be needed?
            ## investigate!
            tokens = self.tree.findall(".//" + dav.SyncToken.tag) if self.tree is not None else []
            sync_token = tokens[0].text if tokens else None
        return sync_token

    ## TODO: there is currently quite some overlapping with the
    ## protocol.xml_parsers we should refactor.  I'm not 100% sure the
    ## protocol.xml_parsers layer is a better approach.  Look for more
    ## cases of old code that was is still remaining after the
    ## protocol layer refactoring
    def _find_objects_and_props(self) -> dict[str, dict[str, _Element]]:
        """Internal implementation of find_objects_and_props without deprecation warning."""
        self.objects: dict[str, dict[str, _Element]] = {}
        self.statuses: dict[str, str] = {}

        ## TODO: the schedule_tag is not used anywhere as for now
        ## TODO: should it be set somewhere else? (now it's not
        ## covered by the scheduling freebusy requests)
        if "Schedule-Tag" in self.headers:
            self.schedule_tag = self.headers["Schedule-Tag"]

        responses = self._strip_to_multistatus()

        for r in responses:
            if r.tag == dav.SyncToken.tag:
                self._sync_token = r.text
                continue
            error.assert_(r.tag == dav.Response.tag)

            (href, propstats, status) = self._parse_response(r)
            ## I would like to do this assert here ...
            # error.assert_(not href in self.objects)
            ## but then there was https://github.com/python-caldav/caldav/issues/136
            if href not in self.objects:
                self.objects[href] = {}
                self.statuses[href] = status

            ## The properties may be delivered either in one
            ## propstat with multiple props or in multiple
            ## propstat
            for propstat in propstats:
                cnt = 0
                status = propstat.find(dav.Status.tag)
                error.assert_(status is not None)
                if status is not None and status.text is not None:
                    error.assert_(len(status) == 0)
                    cnt += 1
                    self.validate_status(status.text)
                    ## if a prop was not found, ignore it
                    if " 404 " in status.text:
                        continue
                for prop in propstat.iterfind(dav.Prop.tag):
                    cnt += 1
                    for theprop in prop:
                        self.objects[href][theprop.tag] = theprop

                ## there shouldn't be any more elements except for status and prop
                error.assert_(cnt == len(propstat))

        return self.objects

    def find_objects_and_props(self) -> dict[str, dict[str, _Element]]:
        """Check the response from the server, check that it is on an expected format,
        find hrefs and props from it and check statuses delivered.

        The parsed data will be put into self.objects, a dict {href:
        {proptag: prop_element}}.  Further parsing of the prop_element
        has to be done by the caller.

        self.sync_token will be populated if found, self.objects will be populated.

        .. deprecated::
            Use ``response.results`` instead, which provides pre-parsed property values.
            This method will be removed in a future version.
        """
        warnings.warn(
            "find_objects_and_props() is deprecated. Use response.results instead, "
            "which provides pre-parsed property values from the protocol layer.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._find_objects_and_props()

    def _expand_simple_prop(
        self,
        proptag: str,
        props_found: dict[str, _Element],
        multi_value_allowed: bool = False,
        xpath: str | None = None,
    ) -> str | list[str] | None:
        values: list[str] = []
        if proptag in props_found:
            prop_xml = props_found[proptag]
            for item in prop_xml.items():
                if proptag == cdav.CalendarData.tag:
                    if (
                        item[0].lower().endswith("content-type")
                        and item[1].lower() == "text/calendar"
                    ):
                        continue
                    if item[0].lower().endswith("version") and item[1] in ("2", "2.0"):
                        continue
                log.error(
                    f"If you see this, please add a report at https://github.com/python-caldav/caldav/issues/209 - in _expand_simple_prop, dealing with {proptag}, extra item found: {'='.join(item)}."
                )
            if not xpath and len(prop_xml) == 0:
                if prop_xml.text:
                    values.append(prop_xml.text)
            else:
                _xpath = xpath if xpath else ".//*"
                leafs = prop_xml.findall(_xpath)
                values = []
                for leaf in leafs:
                    error.assert_(not leaf.items())
                    if leaf.text:
                        values.append(leaf.text)
                    else:
                        values.append(leaf.tag)
        if multi_value_allowed:
            return values
        else:
            if not values:
                return None
            error.assert_(len(values) == 1)
            return values[0]

    ## TODO: word "expand" does not feel quite right.
    ## TODO: I'm considering to deprecate this in v4
    def expand_simple_props(self, *largs, **kwargs) -> dict[str, dict[str, str]]:
        return self._expand_simple_props(*largs, **kwargs)

    def _expand_simple_props(
        self,
        props: Iterable[BaseElement] | None = None,
        multi_value_props: Iterable[Any] | None = None,
        xpath: str | None = None,
    ) -> dict[str, dict[str, str]]:
        """
        The find_objects_and_props() will stop at the xml element
        below the prop tag.  This method will expand those props into
        text.

        Executes find_objects_and_props if not run already, then
        modifies and returns self.objects.
        """
        props = props or []
        multi_value_props = multi_value_props or []

        if not hasattr(self, "objects"):
            self._find_objects_and_props()
        for href in self.objects:
            props_found = self.objects[href]
            for prop in props:
                if prop.tag is None:
                    continue

                props_found[prop.tag] = self._expand_simple_prop(prop.tag, props_found, xpath=xpath)
            for prop in multi_value_props:
                if prop.tag is None:
                    continue

                props_found[prop.tag] = self._expand_simple_prop(
                    prop.tag, props_found, xpath=xpath, multi_value_allowed=True
                )
        # _Element objects in self.objects are parsed to str, thus the need to cast the return
        return cast(dict[str, dict[str, str]], self.objects)
