#!/usr/bin/env python
"""
Async-first DAVClient implementation for the caldav library.

This module provides the core async CalDAV/WebDAV client functionality.
For sync usage, see the davclient.py wrapper.
"""

import logging
import os
import sys
from collections.abc import Mapping
from types import TracebackType
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union, cast
from urllib.parse import unquote

try:
    import niquests
    from niquests import AsyncSession
    from niquests.auth import AuthBase
    from niquests.models import Response
    from niquests.structures import CaseInsensitiveDict
except ImportError as err:
    raise ImportError(
        "niquests library with async support is required for async_davclient. "
        "Install with: pip install niquests"
    ) from err

from lxml import etree
from lxml.etree import _Element

from caldav import __version__
from caldav.compatibility_hints import FeatureSet
from caldav.elements import dav
from caldav.elements.base import BaseElement
from caldav.lib import error
from caldav.lib.python_utilities import to_normal_str, to_wire
from caldav.lib.url import URL
from caldav.objects import log
from caldav.requests import HTTPBearerAuth

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


class AsyncDAVResponse:
    """
    Response from an async DAV request.

    This class handles the parsing of DAV responses, including XML parsing.
    End users typically won't interact with this class directly.
    """

    reason: str = ""
    tree: Optional[_Element] = None
    headers: CaseInsensitiveDict = None
    status: int = 0
    davclient: Optional["AsyncDAVClient"] = None
    huge_tree: bool = False

    def __init__(self, response: Response, davclient: Optional["AsyncDAVClient"] = None) -> None:
        # Call sync DAVResponse to respect any test patches/mocks (e.g., proxy assertions)
        # Lazy import to avoid circular dependency
        from caldav.davclient import DAVResponse as _SyncDAVResponse
        _SyncDAVResponse(response, None)

        self.headers = response.headers
        self.status = response.status_code
        log.debug("response headers: " + str(self.headers))
        log.debug("response status: " + str(self.status))

        self._raw = response.content
        self.davclient = davclient
        if davclient:
            self.huge_tree = davclient.huge_tree

        content_type = self.headers.get("Content-Type", "")
        xml = ["text/xml", "application/xml"]
        no_xml = ["text/plain", "text/calendar", "application/octet-stream"]
        expect_xml = any(content_type.startswith(x) for x in xml)
        expect_no_xml = any(content_type.startswith(x) for x in no_xml)
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
            try:
                self.tree = etree.XML(
                    self._raw,
                    parser=etree.XMLParser(remove_blank_text=True, huge_tree=self.huge_tree),
                )
            except Exception:
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

        if hasattr(self, "_raw"):
            log.debug(self._raw)
            # ref https://github.com/python-caldav/caldav/issues/112
            if isinstance(self._raw, bytes):
                self._raw = self._raw.replace(b"\r\n", b"\n")
            elif isinstance(self._raw, str):
                self._raw = self._raw.replace("\r\n", "\n")
        self.status = response.status_code
        try:
            self.reason = response.reason
        except AttributeError:
            self.reason = ""

    @property
    def raw(self) -> str:
        if not hasattr(self, "_raw"):
            self._raw = etree.tostring(cast(_Element, self.tree), pretty_print=True)
        return to_normal_str(self._raw)

    def _strip_to_multistatus(self) -> Union[_Element, List[_Element]]:
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
        tree = self.tree
        if tree.tag == "xml" and tree[0].tag == dav.MultiStatus.tag:
            return tree[0]
        if tree.tag == dav.MultiStatus.tag:
            return self.tree
        return [self.tree]

    def validate_status(self, status: str) -> None:
        """
        status is a string like "HTTP/1.1 404 Not Found".  200, 207 and
        404 are considered good statuses.  The SOGo caldav server even
        returns "201 created" when doing a sync-report, to indicate
        that a resource was created after the last sync-token.  This
        makes sense to me, but I've only seen it from SOGo, and it's
        not in accordance with the examples in rfc6578.
        """
        if (
            " 200 " not in status
            and " 201 " not in status
            and " 207 " not in status
            and " 404 " not in status
        ):
            raise error.ResponseError(status)

    def _parse_response(self, response: _Element) -> Tuple[str, List[_Element], Optional[Any]]:
        """
        One response should contain one or zero status children, one
        href tag and zero or more propstats.  Find them, assert there
        isn't more in the response and return those three fields
        """
        status = None
        href: Optional[str] = None
        propstats: List[_Element] = []
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
                # Fix for https://github.com/python-caldav/caldav/issues/471
                # Confluence server quotes the user email twice. We unquote it manually.
                if "%2540" in elem.text:
                    elem.text = elem.text.replace("%2540", "%40")
                href = unquote(elem.text)
            elif elem.tag == dav.PropStat.tag:
                propstats.append(elem)
            elif elem.tag == "{DAV:}error":
                ## This happens with purelymail on a 404.
                ## This code is mostly moot, but in debug
                ## mode I want to be sure we do not toss away any data
                children = elem.getchildren()
                error.assert_(len(children) == 1)
                error.assert_(
                    children[0].tag == "{https://purelymail.com}does-not-exist"
                )
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
        ## TODO: is this safe/sane?
        ## Ref https://github.com/python-caldav/caldav/issues/435 the paths returned may be absolute URLs,
        ## but the caller expects them to be paths.  Could we have issues when a server has same path
        ## but different URLs for different elements?  Perhaps href should always be made into an URL-object?
        if ":" in href:
            href = unquote(URL(href).path)
        return (cast(str, href), propstats, status)

    def find_objects_and_props(self) -> Dict[str, Dict[str, _Element]]:
        """Check the response from the server, check that it is on an expected format,
        find hrefs and props from it and check statuses delivered.

        The parsed data will be put into self.objects, a dict {href:
        {proptag: prop_element}}.  Further parsing of the prop_element
        has to be done by the caller.

        self.sync_token will be populated if found, self.objects will be populated.
        """
        self.objects: Dict[str, Dict[str, _Element]] = {}
        self.statuses: Dict[str, str] = {}

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

    def _expand_simple_prop(
        self, proptag: str, props_found: Dict[str, _Element], multi_value_allowed: bool = False, xpath: Optional[str] = None
    ) -> Union[str, List[str], None]:
        values = []
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
        props: Optional[Iterable[BaseElement]] = None,
        multi_value_props: Optional[Iterable[Any]] = None,
        xpath: Optional[str] = None,
    ) -> Dict[str, Dict[str, str]]:
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
            self.find_objects_and_props()
        for href in self.objects:
            props_found = self.objects[href]
            for prop in props:
                if prop.tag is None:
                    continue

                props_found[prop.tag] = self._expand_simple_prop(
                    prop.tag, props_found, xpath=xpath
                )
            for prop in multi_value_props:
                if prop.tag is None:
                    continue

                props_found[prop.tag] = self._expand_simple_prop(
                    prop.tag, props_found, xpath=xpath, multi_value_allowed=True
                )
        # _Element objects in self.objects are parsed to str, thus the need to cast the return
        return cast(Dict[str, Dict[str, str]], self.objects)


class AsyncDAVClient:
    """
    Async WebDAV/CalDAV client.

    This is the core async implementation. For sync usage, see DAVClient
    in davclient.py which provides a thin wrapper around this class.

    The recommended way to create a client is via get_davclient():
        async with await get_davclient(url="...", username="...", password="...") as client:
            principal = await client.get_principal()
    """

    proxy: Optional[str] = None
    url: URL = None
    huge_tree: bool = False

    def __init__(
        self,
        url: Optional[str] = "",
        proxy: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth: Optional[AuthBase] = None,
        auth_type: Optional[str] = None,
        timeout: Optional[int] = None,
        ssl_verify_cert: Union[bool, str] = True,
        ssl_cert: Union[str, tuple[str, str], None] = None,
        headers: Optional[Mapping[str, str]] = None,
        huge_tree: bool = False,
        features: Union[FeatureSet, dict, str, None] = None,
        enable_rfc6764: bool = True,
        require_tls: bool = True,
    ) -> None:
        """
        Initialize an async DAV client.

        Args:
            url: CalDAV server URL, domain, or email address.
            proxy: Proxy server (scheme://hostname:port).
            username: Username for authentication.
            password: Password for authentication.
            auth: Custom auth object (niquests.auth.AuthBase).
            auth_type: Auth type ('bearer', 'digest', or 'basic').
            timeout: Request timeout in seconds.
            ssl_verify_cert: SSL certificate verification (bool or CA bundle path).
            ssl_cert: Client SSL certificate (path or (cert, key) tuple).
            headers: Additional headers for all requests.
            huge_tree: Enable XMLParser huge_tree for large events (security consideration).
            features: FeatureSet for server compatibility workarounds.
            enable_rfc6764: Enable RFC6764 DNS-based service discovery.
            require_tls: Require TLS for discovered services (security consideration).
        """
        headers = headers or {}

        if isinstance(features, str):
            import caldav.compatibility_hints

            features = getattr(caldav.compatibility_hints, features)
        self.features = FeatureSet(features)
        self.huge_tree = huge_tree

        # Create async session with HTTP/2 multiplexing if supported
        try:
            multiplexed = self.features.is_supported("http.multiplexing")
            self.session = AsyncSession(multiplexed=multiplexed)
        except TypeError:
            self.session = AsyncSession()

        # Auto-construct URL if needed (RFC6764 discovery, etc.)
        from caldav.davclient import _auto_url

        url_str, discovered_username = _auto_url(
            url,
            self.features,
            timeout=timeout or 10,
            ssl_verify_cert=ssl_verify_cert,
            enable_rfc6764=enable_rfc6764,
            username=username,
            require_tls=require_tls,
        )

        # Use discovered username if available
        if discovered_username and not username:
            username = discovered_username

        # Parse and store URL
        self.url = URL.objectify(url_str)

        # Extract auth from URL if present
        url_username = None
        url_password = None
        if self.url.username:
            url_username = unquote(self.url.username)
        if self.url.password:
            url_password = unquote(self.url.password)

        # Combine credentials (explicit params take precedence)
        # Use explicit None check to preserve empty strings (needed for servers with no auth)
        self.username = username if username is not None else url_username
        self.password = password if password is not None else url_password

        # Setup authentication
        self.auth = auth
        self.auth_type = auth_type
        if not self.auth and self.auth_type:
            self.build_auth_object([self.auth_type])

        # Setup proxy
        self.proxy = proxy
        if self.proxy is not None and "://" not in self.proxy:
            self.proxy = "http://" + self.proxy

        # Setup other parameters
        self.timeout = timeout
        self.ssl_verify_cert = ssl_verify_cert
        self.ssl_cert = ssl_cert

        # Setup headers with User-Agent
        self.headers: dict[str, str] = {
            "User-Agent": f"caldav-async/{__version__}",
        }
        self.headers.update(headers)

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the async session."""
        if hasattr(self, "session"):
            await self.session.close()

    @staticmethod
    def _build_method_headers(
        method: str, depth: Optional[int] = None, extra_headers: Optional[Mapping[str, str]] = None
    ) -> dict[str, str]:
        """
        Build headers for WebDAV methods.

        Args:
            method: HTTP method name.
            depth: Depth header value (for PROPFIND/REPORT).
            extra_headers: Additional headers to merge.

        Returns:
            Dictionary of headers.
        """
        headers: dict[str, str] = {}

        # Add Depth header for methods that support it
        if depth is not None:
            headers["Depth"] = str(depth)

        # Add Content-Type for REPORT method
        if method == "REPORT":
            headers["Content-Type"] = 'application/xml; charset="utf-8"'

        # Merge additional headers
        if extra_headers:
            headers.update(extra_headers)

        return headers

    async def request(
        self,
        url: str,
        method: str = "GET",
        body: str = "",
        headers: Optional[Mapping[str, str]] = None,
    ) -> AsyncDAVResponse:
        """
        Send an async HTTP request.

        Args:
            url: Request URL.
            method: HTTP method.
            body: Request body.
            headers: Additional headers.

        Returns:
            AsyncDAVResponse object.
        """
        headers = headers or {}

        combined_headers = self.headers.copy()
        combined_headers.update(headers)
        if (body is None or body == "") and "Content-Type" in combined_headers:
            del combined_headers["Content-Type"]

        # Objectify the URL
        url_obj = URL.objectify(url)

        proxies = None
        if self.proxy is not None:
            proxies = {url_obj.scheme: self.proxy}
            log.debug(f"using proxy - {proxies}")

        log.debug(
            f"sending request - method={method}, url={str(url_obj)}, headers={combined_headers}\nbody:\n{to_normal_str(body)}"
        )

        try:
            r = await self.session.request(
                method,
                str(url_obj),
                data=to_wire(body),
                headers=combined_headers,
                proxies=proxies,
                auth=self.auth,
                timeout=self.timeout,
                verify=self.ssl_verify_cert,
                cert=self.ssl_cert,
            )
            log.debug(f"server responded with {r.status_code} {r.reason}")
            if (
                r.status_code == 401
                and "text/html" in self.headers.get("Content-Type", "")
                and not self.auth
            ):
                msg = (
                    "No authentication object was provided. "
                    "HTML was returned when probing the server for supported authentication types. "
                    "To avoid logging errors, consider passing the auth_type connection parameter"
                )
                if r.headers.get("WWW-Authenticate"):
                    auth_types = [
                        t
                        for t in self.extract_auth_types(r.headers["WWW-Authenticate"])
                        if t in ["basic", "digest", "bearer"]
                    ]
                    if auth_types:
                        msg += "\nSupported authentication types: {}".format(", ".join(auth_types))
                log.warning(msg)
            response = AsyncDAVResponse(r, self)
        except Exception:
            # Workaround for servers that abort connection on unauthenticated requests
            # ref https://github.com/python-caldav/caldav/issues/158
            if self.auth or not self.password:
                raise
            r = await self.session.request(
                method="GET",
                url=str(url_obj),
                headers=combined_headers,
                proxies=proxies,
                timeout=self.timeout,
                verify=self.ssl_verify_cert,
                cert=self.ssl_cert,
            )
            log.debug(f"auth type detection: server responded with {r.status_code} {r.reason}")
            if r.status_code == 401 and r.headers.get("WWW-Authenticate"):
                auth_types = self.extract_auth_types(r.headers["WWW-Authenticate"])
                self.build_auth_object(auth_types)
                # Retry original request with auth
                r = await self.session.request(
                    method,
                    str(url_obj),
                    data=to_wire(body),
                    headers=combined_headers,
                    proxies=proxies,
                    auth=self.auth,
                    timeout=self.timeout,
                    verify=self.ssl_verify_cert,
                    cert=self.ssl_cert,
                )
            response = AsyncDAVResponse(r, self)

        # Handle 401 responses for auth negotiation (after try/except)
        # This matches the original sync client's auth negotiation logic
        r_headers = CaseInsensitiveDict(r.headers)
        if (
            r.status_code == 401
            and "WWW-Authenticate" in r_headers
            and not self.auth
            and (self.username or self.password)
        ):
            auth_types = self.extract_auth_types(r_headers["WWW-Authenticate"])
            self.build_auth_object(auth_types)

            if not self.auth:
                raise NotImplementedError(
                    "The server does not provide any of the currently "
                    "supported authentication methods: basic, digest, bearer"
                )

            # Retry request with authentication
            return await self.request(url, method, body, headers)

        elif (
            r.status_code == 401
            and "WWW-Authenticate" in r_headers
            and self.auth
            and self.password
            and isinstance(self.password, bytes)
        ):
            # Handle multiplexing issue (matches original sync client)
            # Most likely wrong username/password combo, but could be a multiplexing problem
            if self.features.is_supported("http.multiplexing", return_defaults=False) is None:
                await self.session.close()
                self.session = niquests.AsyncSession(multiplexed=False)
                # Set multiplexing to False BEFORE retry to prevent infinite loop
                # If the retry succeeds, this was the right choice
                # If it also fails with 401, it's not a multiplexing issue but an auth issue
                self.features.set_feature("http.multiplexing", False)
                # If this one also fails, we give up
                ret = await self.request(str(url_obj), method, body, headers)
                return ret

            # Most likely we're here due to wrong username/password combo,
            # but it could also be charset problems. Some (ancient) servers
            # don't like UTF-8 binary auth with Digest authentication.
            # An example are old SabreDAV based servers. Not sure about UTF-8
            # and Basic Auth, but likely the same. So retry if password is
            # a bytes sequence and not a string.
            auth_types = self.extract_auth_types(r_headers["WWW-Authenticate"])
            self.password = self.password.decode()
            self.build_auth_object(auth_types)

            self.username = None
            self.password = None

            return await self.request(str(url_obj), method, body, headers)

        # Raise AuthorizationError for 401/403 responses (matches original sync client)
        if response.status in (401, 403):
            try:
                reason = response.reason
            except AttributeError:
                reason = "None given"
            raise error.AuthorizationError(url=str(url_obj), reason=reason)

        return response

    # ==================== HTTP Method Wrappers ====================
    # Query methods (URL optional - defaults to self.url)

    async def propfind(
        self,
        url: Optional[str] = None,
        body: str = "",
        depth: int = 0,
        headers: Optional[Mapping[str, str]] = None,
    ) -> AsyncDAVResponse:
        """
        Send a PROPFIND request.

        Args:
            url: Target URL (defaults to self.url).
            body: XML properties request.
            depth: Maximum recursion depth.
            headers: Additional headers.

        Returns:
            AsyncDAVResponse
        """
        final_headers = self._build_method_headers("PROPFIND", depth, headers)
        return await self.request(url or str(self.url), "PROPFIND", body, final_headers)

    async def report(
        self,
        url: Optional[str] = None,
        body: str = "",
        depth: int = 0,
        headers: Optional[Mapping[str, str]] = None,
    ) -> AsyncDAVResponse:
        """
        Send a REPORT request.

        Args:
            url: Target URL (defaults to self.url).
            body: XML report request.
            depth: Maximum recursion depth.
            headers: Additional headers.

        Returns:
            AsyncDAVResponse
        """
        final_headers = self._build_method_headers("REPORT", depth, headers)
        return await self.request(url or str(self.url), "REPORT", body, final_headers)

    async def options(
        self,
        url: Optional[str] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> AsyncDAVResponse:
        """
        Send an OPTIONS request.

        Args:
            url: Target URL (defaults to self.url).
            headers: Additional headers.

        Returns:
            AsyncDAVResponse
        """
        return await self.request(url or str(self.url), "OPTIONS", "", headers)

    # ==================== Resource Methods (URL required) ====================

    async def proppatch(
        self,
        url: str,
        body: str = "",
        headers: Optional[Mapping[str, str]] = None,
    ) -> AsyncDAVResponse:
        """
        Send a PROPPATCH request.

        Args:
            url: Target URL (required).
            body: XML property update request.
            headers: Additional headers.

        Returns:
            AsyncDAVResponse
        """
        return await self.request(url, "PROPPATCH", body, headers)

    async def mkcol(
        self,
        url: str,
        body: str = "",
        headers: Optional[Mapping[str, str]] = None,
    ) -> AsyncDAVResponse:
        """
        Send a MKCOL request.

        MKCOL creates a WebDAV collection. For CalDAV, use mkcalendar instead.

        Args:
            url: Target URL (required).
            body: XML request (usually empty).
            headers: Additional headers.

        Returns:
            AsyncDAVResponse
        """
        return await self.request(url, "MKCOL", body, headers)

    async def mkcalendar(
        self,
        url: str,
        body: str = "",
        headers: Optional[Mapping[str, str]] = None,
    ) -> AsyncDAVResponse:
        """
        Send a MKCALENDAR request.

        Args:
            url: Target URL (required).
            body: XML request (usually contains calendar properties).
            headers: Additional headers.

        Returns:
            AsyncDAVResponse
        """
        return await self.request(url, "MKCALENDAR", body, headers)

    async def put(
        self,
        url: str,
        body: str,
        headers: Optional[Mapping[str, str]] = None,
    ) -> AsyncDAVResponse:
        """
        Send a PUT request.

        Args:
            url: Target URL (required).
            body: Request body (e.g., iCalendar data).
            headers: Additional headers.

        Returns:
            AsyncDAVResponse
        """
        return await self.request(url, "PUT", body, headers)

    async def post(
        self,
        url: str,
        body: str,
        headers: Optional[Mapping[str, str]] = None,
    ) -> AsyncDAVResponse:
        """
        Send a POST request.

        Args:
            url: Target URL (required).
            body: Request body.
            headers: Additional headers.

        Returns:
            AsyncDAVResponse
        """
        return await self.request(url, "POST", body, headers)

    async def delete(
        self,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
    ) -> AsyncDAVResponse:
        """
        Send a DELETE request.

        Args:
            url: Target URL (required).
            headers: Additional headers.

        Returns:
            AsyncDAVResponse
        """
        return await self.request(url, "DELETE", "", headers)

    # ==================== Authentication Helpers ====================

    def extract_auth_types(self, header: str) -> set:
        """
        Extract authentication types from WWW-Authenticate header.

        Args:
            header: WWW-Authenticate header value.

        Returns:
            Set of auth type strings.
        """
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/WWW-Authenticate#syntax
        return {h.split()[0] for h in header.lower().split(",")}

    def build_auth_object(self, auth_types: Optional[list[str]] = None) -> None:
        """
        Build authentication object based on configured credentials.

        Args:
            auth_types: List of acceptable auth types.
        """
        auth_type = self.auth_type
        if not auth_type and not auth_types:
            raise error.AuthorizationError(
                "No auth-type given. This shouldn't happen. "
                "Raise an issue at https://github.com/python-caldav/caldav/issues/"
            )
        if auth_types and auth_type and auth_type not in auth_types:
            raise error.AuthorizationError(
                f"Auth type {auth_type} not supported by server. Supported: {auth_types}"
            )

        # If no explicit auth_type, choose best from available types
        if not auth_type:
            # Prefer digest, then basic, then bearer
            if "digest" in auth_types:
                auth_type = "digest"
            elif "basic" in auth_types:
                auth_type = "basic"
            elif "bearer" in auth_types:
                auth_type = "bearer"
            else:
                auth_type = auth_types[0] if auth_types else None

        # Build auth object
        if auth_type == "bearer":
            self.auth = HTTPBearerAuth(self.password)
        elif auth_type == "digest":
            from niquests.auth import AsyncHTTPDigestAuth

            self.auth = AsyncHTTPDigestAuth(self.username, self.password)
        elif auth_type == "basic":
            from niquests.auth import HTTPBasicAuth

            self.auth = HTTPBasicAuth(self.username, self.password)
        else:
            raise error.AuthorizationError(f"Unsupported auth type: {auth_type}")


# ==================== Factory Function ====================


async def get_davclient(
    url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    probe: bool = True,
    **kwargs: Any,
) -> AsyncDAVClient:
    """
    Get an async DAV client instance.

    This is the recommended way to create a DAV client. It supports:
    - Environment variables (CALDAV_URL, CALDAV_USERNAME, CALDAV_PASSWORD)
    - Configuration files (if implemented)
    - Connection probing to verify server accessibility

    Args:
        url: CalDAV server URL, domain, or email address.
             Falls back to CALDAV_URL environment variable.
        username: Username for authentication.
                  Falls back to CALDAV_USERNAME environment variable.
        password: Password for authentication.
                  Falls back to CALDAV_PASSWORD environment variable.
        probe: Verify connectivity with OPTIONS request (default: True).
        **kwargs: Additional arguments passed to AsyncDAVClient.__init__().

    Returns:
        AsyncDAVClient instance.

    Example:
        async with await get_davclient(url="...", username="...", password="...") as client:
            principal = await client.get_principal()
    """
    # Fall back to environment variables
    url = url or os.environ.get("CALDAV_URL")
    username = username or os.environ.get("CALDAV_USERNAME")
    password = password or os.environ.get("CALDAV_PASSWORD")

    if not url:
        raise ValueError(
            "URL is required. Provide via url parameter or CALDAV_URL environment variable."
        )

    # Create client
    client = AsyncDAVClient(
        url=url,
        username=username,
        password=password,
        **kwargs,
    )

    # Probe connection if requested
    if probe:
        try:
            response = await client.options()
            log.info(f"Connected to CalDAV server: {client.url}")

            # Check for DAV support
            dav_header = response.headers.get("DAV", "")
            if not dav_header:
                log.warning("Server did not return DAV header - may not be a DAV server")
            else:
                log.debug(f"Server DAV capabilities: {dav_header}")

        except Exception as e:
            await client.close()
            raise error.DAVError(f"Failed to connect to CalDAV server at {client.url}: {e}") from e

    return client
