"""
Base class for DAV response parsing.

This module contains the shared logic between DAVResponse (sync) and
AsyncDAVResponse (async) to eliminate code duplication.
"""

import logging
import warnings
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

from lxml import etree
from lxml.etree import _Element

from caldav.elements import dav
from caldav.elements.base import BaseElement
from caldav.lib import error
from caldav.lib.python_utilities import to_normal_str
from caldav.protocol.xml_parsers import (
    _normalize_href,
    _validate_status,
)
from caldav.protocol.xml_parsers import (
    _strip_to_multistatus as _proto_strip,
)

if TYPE_CHECKING:
    # Protocol for HTTP response objects (works with httpx, niquests, requests)
    # Using Any as the type hint to avoid strict protocol matching
    Response = Any

log = logging.getLogger(__name__)


class BaseDAVResponse:
    """
    Base class containing shared response parsing logic.

    This class provides the XML parsing and response extraction methods
    that are common to both sync and async DAV responses.
    """

    # These attributes should be set by subclass __init__
    tree: _Element | None = None
    headers: Any = None
    status: int = 0
    _raw: Any = ""
    huge_tree: bool = False
    reason: str = ""
    davclient: Any = None

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
        return _proto_strip(self.tree)

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

    def _parse_response(self, response: _Element) -> tuple[str, list[_Element], Any | None]:
        """
        One response should contain one or zero status children, one
        href tag and zero or more propstats.  Find them, assert there
        isn't more in the response and return those three fields
        """
        status = None
        href: str | None = None
        propstats: list[_Element] = []
        check_404 = False  ## special for purelymail
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

    def _find_objects_and_props(self) -> dict[str, dict[str, _Element]]:
        """Internal implementation of find_objects_and_props without deprecation warning."""
        self.objects: dict[str, dict[str, _Element]] = {}
        self.statuses: dict[str, str] = {}

        if "Schedule-Tag" in self.headers:
            self.schedule_tag = self.headers["Schedule-Tag"]

        responses = self._strip_to_multistatus()
        for r in responses:
            if r.tag == dav.SyncToken.tag:
                self.sync_token = r.text
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
                if proptag == "{urn:ietf:params:xml:ns:caldav}calendar-data":
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
    def expand_simple_props(
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
