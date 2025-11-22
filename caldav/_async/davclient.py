#!/usr/bin/env python
"""
Async DAVClient implementation using httpx.

This is the primary implementation - the sync API wraps this.
"""
import logging
import sys
from typing import Any
from typing import Dict
from typing import Mapping
from typing import Optional
from typing import Tuple
from typing import Union
from urllib.parse import unquote

import httpx
from lxml import etree
from lxml.etree import _Element

try:
    from caldav._version import __version__
except ImportError:
    __version__ = "0.0.0.dev"

from caldav.lib import error
from caldav.lib.python_utilities import to_normal_str
from caldav.lib.python_utilities import to_wire
from caldav.lib.url import URL

if sys.version_info < (3, 9):
    from typing import Iterable
else:
    from collections.abc import Iterable

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

log = logging.getLogger("caldav")


class HTTPBearerAuth(httpx.Auth):
    """Bearer token authentication for httpx."""

    def __init__(self, token: Union[str, bytes]):
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        self.token = token

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


class DAVResponse:
    """
    This class is a response from a DAV request. It is instantiated from
    the AsyncDAVClient class. End users of the library should not need to
    know anything about this class. Since we often get XML responses,
    it tries to parse it into `self.tree`
    """

    raw = ""
    reason: str = ""
    tree: Optional[_Element] = None
    headers: httpx.Headers = None
    status: int = 0
    davclient: Optional["AsyncDAVClient"] = None
    huge_tree: bool = False

    def __init__(
        self, response: httpx.Response, davclient: Optional["AsyncDAVClient"] = None
    ) -> None:
        from caldav.elements import cdav, dav

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
        expect_xml = any((content_type.startswith(x) for x in xml))
        expect_no_xml = any((content_type.startswith(x) for x in no_xml))
        if (
            content_type
            and not expect_xml
            and not expect_no_xml
            and response.status_code < 400
        ):
            error.weirdness(f"Unexpected content type: {content_type}")
        try:
            content_length = int(self.headers.get("Content-Length", -1))
        except:
            content_length = -1
        if content_length == 0 or not self._raw:
            self._raw = ""
            self.tree = None
            log.debug("No content delivered")
        else:
            try:
                self.tree = etree.XML(
                    self._raw,
                    parser=etree.XMLParser(
                        remove_blank_text=True, huge_tree=self.huge_tree
                    ),
                )
            except:
                if not expect_no_xml or log.level <= logging.DEBUG:
                    if not expect_no_xml:
                        _log = logging.critical
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
            if isinstance(self._raw, bytes):
                self._raw = self._raw.replace(b"\r\n", b"\n")
            elif isinstance(self._raw, str):
                self._raw = self._raw.replace("\r\n", "\n")
        self.status = response.status_code
        self.reason = response.reason_phrase or ""

    @property
    def raw(self) -> str:
        if not hasattr(self, "_raw"):
            from lxml.etree import _Element
            from typing import cast

            self._raw = etree.tostring(cast(_Element, self.tree), pretty_print=True)
        return to_normal_str(self._raw)

    def _strip_to_multistatus(self):
        """Strip down to the multistatus element or response list."""
        from caldav.elements import dav

        tree = self.tree
        if tree.tag == "xml" and tree[0].tag == dav.MultiStatus.tag:
            return tree[0]
        if tree.tag == dav.MultiStatus.tag:
            return self.tree
        return [self.tree]

    def validate_status(self, status: str) -> None:
        """Validate HTTP status string."""
        if (
            " 200 " not in status
            and " 201 " not in status
            and " 207 " not in status
            and " 404 " not in status
        ):
            raise error.ResponseError(status)

    def _parse_response(self, response) -> Tuple[str, list, Optional[Any]]:
        """Parse a single DAV response element."""
        from caldav.elements import dav
        from typing import cast

        status = None
        href: Optional[str] = None
        propstats: list = []
        check_404 = False

        error.assert_(response.tag == dav.Response.tag)
        for elem in response:
            if elem.tag == dav.Status.tag:
                error.assert_(not status)
                status = elem.text
                error.assert_(status)
                self.validate_status(status)
            elif elem.tag == dav.Href.tag:
                assert not href
                if "%2540" in elem.text:
                    elem.text = elem.text.replace("%2540", "%40")
                href = unquote(elem.text)
            elif elem.tag == dav.PropStat.tag:
                propstats.append(elem)
            elif elem.tag == "{DAV:}error":
                children = elem.getchildren()
                error.assert_(len(children) == 1)
                error.assert_(
                    children[0].tag == "{https://purelymail.com}does-not-exist"
                )
                check_404 = True
            else:
                error.weirdness("unexpected element found in response", elem)

        error.assert_(href)
        if check_404:
            error.assert_("404" in status)

        if ":" in href:
            href = unquote(URL(href).path)
        return (cast(str, href), propstats, status)

    def find_objects_and_props(self) -> Dict[str, Dict[str, _Element]]:
        """Parse response and extract hrefs and properties."""
        from caldav.elements import dav

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

            if href not in self.objects:
                self.objects[href] = {}
                self.statuses[href] = status

            for propstat in propstats:
                cnt = 0
                status_elem = propstat.find(dav.Status.tag)
                error.assert_(status_elem is not None)
                if status_elem is not None and status_elem.text is not None:
                    error.assert_(len(status_elem) == 0)
                    cnt += 1
                    self.validate_status(status_elem.text)
                    if " 404 " in status_elem.text:
                        continue
                for prop in propstat.iterfind(dav.Prop.tag):
                    cnt += 1
                    for theprop in prop:
                        self.objects[href][theprop.tag] = theprop

                error.assert_(cnt == len(propstat))

        return self.objects

    def _expand_simple_prop(
        self, proptag, props_found, multi_value_allowed=False, xpath=None
    ):
        """Expand a simple property to its text value(s)."""
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

    def expand_simple_props(
        self,
        props: Iterable = None,
        multi_value_props: Iterable[Any] = None,
        xpath: Optional[str] = None,
    ) -> Dict[str, Dict[str, str]]:
        """Expand properties to text values."""
        from typing import cast

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
        return cast(Dict[str, Dict[str, str]], self.objects)


class AsyncDAVClient:
    """
    Async CalDAV client using httpx.

    This is the primary implementation. The sync DAVClient wraps this class.
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
        auth: Optional[httpx.Auth] = None,
        auth_type: Optional[str] = None,
        timeout: Optional[float] = None,
        ssl_verify_cert: Union[bool, str] = True,
        ssl_cert: Union[str, Tuple[str, str], None] = None,
        headers: Mapping[str, str] = None,
        huge_tree: bool = False,
        features: Union["FeatureSet", dict, str] = None,
    ) -> None:
        """
        Initialize async DAV client.

        Args:
            url: CalDAV server URL
            proxy: Proxy server URL
            username: Username for authentication
            password: Password for authentication
            auth: httpx.Auth object for custom authentication
            auth_type: Auth type ('basic', 'digest', 'bearer')
            timeout: Request timeout in seconds
            ssl_verify_cert: SSL certificate verification (bool or CA bundle path)
            ssl_cert: Client SSL certificate
            headers: Additional headers
            huge_tree: Enable huge XML tree parsing
            features: Server compatibility features
        """
        import caldav.compatibility_hints
        from caldav.compatibility_hints import FeatureSet

        headers = headers or {}

        if isinstance(features, str):
            features = getattr(caldav.compatibility_hints, features)
        self.features = FeatureSet(features)
        self.huge_tree = huge_tree

        # Auto-configure URL based on features
        url = self._auto_url(url, self.features)

        log.debug("url: " + str(url))
        self.url = URL.objectify(url)

        # Configure proxy
        self._proxy = None
        if proxy is not None:
            _proxy = proxy
            if "://" not in proxy:
                _proxy = self.url.scheme + "://" + proxy
            p = _proxy.split(":")
            if len(p) == 2:
                _proxy += ":8080"
            log.debug("init - proxy: %s" % (_proxy))
            self._proxy = _proxy

        # Build headers
        self.headers = {
            "User-Agent": "python-caldav/" + __version__,
            "Content-Type": "text/xml",
            "Accept": "text/xml, text/calendar",
        }
        self.headers.update(headers or {})

        # Handle credentials from URL
        if self.url.username is not None:
            username = unquote(self.url.username)
            password = unquote(self.url.password)

        self.username = username
        self.password = password
        self.auth = auth
        self.auth_type = auth_type

        if isinstance(self.password, str):
            self.password = self.password.encode("utf-8")
        if auth and self.auth_type:
            logging.error(
                "both auth object and auth_type sent to AsyncDAVClient. The latter will be ignored."
            )
        elif self.auth_type:
            self._build_auth_object()

        self.timeout = timeout
        self.ssl_verify_cert = ssl_verify_cert
        self.ssl_cert = ssl_cert
        self.url = self.url.unauth()
        log.debug("self.url: " + str(url))

        self._principal = None
        self._client: Optional[httpx.AsyncClient] = None

    def _auto_url(self, url, features):
        """Auto-configure URL based on features."""
        from caldav.compatibility_hints import FeatureSet

        if isinstance(features, dict):
            features = FeatureSet(features)
        if "/" not in str(url):
            url_hints = features.is_supported("auto-connect.url", dict)
            if not url and "domain" in url_hints:
                url = url_hints["domain"]
            url = f"{url_hints.get('scheme', 'https')}://{url}{url_hints.get('basepath', '')}"
        return url

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx AsyncClient.

        When used from sync wrappers (via anyio.run()), we need to create
        a fresh client each time because the connection pool gets invalidated
        when the event loop closes.
        """
        # Always create a fresh client to avoid event loop issues
        # The overhead is minimal compared to connection establishment
        transport = None
        if self._proxy:
            transport = httpx.AsyncHTTPTransport(proxy=self._proxy)

        # Disable connection pooling to avoid stale connections
        # when used from sync context with multiple anyio.run() calls
        limits = httpx.Limits(max_keepalive_connections=0)

        client = httpx.AsyncClient(
            auth=self.auth,
            timeout=self.timeout,
            verify=self.ssl_verify_cert,
            cert=self.ssl_cert,
            transport=transport,
            limits=limits,
        )
        return client

    async def __aenter__(self) -> Self:
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def extract_auth_types(self, header: str):
        """Extract authentication types from WWW-Authenticate header."""
        return {h.split()[0] for h in header.lower().split(",")}

    def _build_auth_object(self, auth_types: Optional[list] = None):
        """Build authentication object based on auth_type or server response."""
        auth_type = self.auth_type
        if not auth_type and not auth_types:
            raise error.AuthorizationError("No auth-type given. This shouldn't happen.")
        if auth_types and auth_type and auth_type not in auth_types:
            raise error.AuthorizationError(
                reason=f"Configuration specifies to use {auth_type}, but server only accepts {auth_types}"
            )
        if not auth_type and auth_types:
            if self.username and "digest" in auth_types:
                auth_type = "digest"
            elif self.username and "basic" in auth_types:
                auth_type = "basic"
            elif self.password and "bearer" in auth_types:
                auth_type = "bearer"
            elif "bearer" in auth_types:
                raise error.AuthorizationError(
                    reason="Server provides bearer auth, but no password given."
                )

        if auth_type == "digest":
            self.auth = httpx.DigestAuth(self.username, self.password)
        elif auth_type == "basic":
            self.auth = httpx.BasicAuth(self.username, self.password)
        elif auth_type == "bearer":
            self.auth = HTTPBearerAuth(self.password)

    async def request(
        self,
        url: str,
        method: str = "GET",
        body: str = "",
        headers: Mapping[str, str] = None,
    ) -> DAVResponse:
        """
        Send an HTTP request to the CalDAV server.

        This is the core method that all other HTTP methods use.
        """
        headers = headers or {}

        combined_headers = dict(self.headers)
        combined_headers.update(headers or {})
        if (body is None or body == "") and "Content-Type" in combined_headers:
            del combined_headers["Content-Type"]

        url_obj = URL.objectify(url)

        log.debug(
            "sending request - method={0}, url={1}, headers={2}\nbody:\n{3}".format(
                method, str(url_obj), combined_headers, to_normal_str(body)
            )
        )

        # Create a fresh client for each request to avoid event loop issues
        # when used from sync context with multiple anyio.run() calls
        async with await self._get_client() as client:
            try:
                r = await client.request(
                    method,
                    str(url_obj),
                    content=to_wire(body) if body else None,
                    headers=combined_headers,
                )
                log.debug(
                    "server responded with %i %s" % (r.status_code, r.reason_phrase)
                )

                if (
                    r.status_code == 401
                    and "text/html" in self.headers.get("Content-Type", "")
                    and not self.auth
                ):
                    msg = (
                        "No authentication object was provided. "
                        "HTML was returned when probing the server for supported authentication types."
                    )
                    if r.headers.get("WWW-Authenticate"):
                        auth_types = [
                            t
                            for t in self.extract_auth_types(
                                r.headers["WWW-Authenticate"]
                            )
                            if t in ["basic", "digest", "bearer"]
                        ]
                        if auth_types:
                            msg += "\nSupported authentication types: %s" % (
                                ", ".join(auth_types)
                            )
                    log.warning(msg)
                response = DAVResponse(r, self)
            except httpx.RequestError:
                if self.auth or not self.password:
                    raise
                # Workaround for servers that abort connection instead of 401
                r = await client.request(
                    method="GET",
                    url=str(url_obj),
                    headers=combined_headers,
                )
                if r.status_code != 401:
                    raise
                response = DAVResponse(r, self)

        # Handle authentication (outside the client context - will create new client if needed)
        if (
            r.status_code == 401
            and "WWW-Authenticate" in r.headers
            and not self.auth
            and (self.username or self.password)
        ):
            auth_types = self.extract_auth_types(r.headers["WWW-Authenticate"])
            self._build_auth_object(list(auth_types))

            if not self.auth:
                raise NotImplementedError(
                    "The server does not provide any of the currently "
                    "supported authentication methods: basic, digest, bearer"
                )

            return await self.request(url, method, body, headers)

        elif (
            r.status_code == 401
            and "WWW-Authenticate" in r.headers
            and self.auth
            and self.password
            and isinstance(self.password, bytes)
        ):
            # Retry with decoded password for charset issues
            auth_types = self.extract_auth_types(r.headers["WWW-Authenticate"])
            self.password = self.password.decode()
            self._build_auth_object(list(auth_types))

            self.username = None
            self.password = None

            return await self.request(str(url_obj), method, body, headers)

        # Handle authorization errors
        if response.status in (403, 401):
            try:
                reason = response.reason
            except AttributeError:
                reason = "None given"
            raise error.AuthorizationError(url=str(url_obj), reason=reason)

        return response

    async def propfind(
        self, url: Optional[str] = None, props: str = "", depth: int = 0
    ) -> DAVResponse:
        """Send a PROPFIND request."""
        return await self.request(
            url or str(self.url), "PROPFIND", props, {"Depth": str(depth)}
        )

    async def proppatch(self, url: str, body: str, dummy: None = None) -> DAVResponse:
        """Send a PROPPATCH request."""
        return await self.request(url, "PROPPATCH", body)

    async def report(self, url: str, query: str = "", depth: int = 0) -> DAVResponse:
        """Send a REPORT request."""
        return await self.request(
            url,
            "REPORT",
            query,
            {"Depth": str(depth), "Content-Type": 'application/xml; charset="utf-8"'},
        )

    async def mkcol(self, url: str, body: str, dummy: None = None) -> DAVResponse:
        """Send a MKCOL request."""
        return await self.request(url, "MKCOL", body)

    async def mkcalendar(
        self, url: str, body: str = "", dummy: None = None
    ) -> DAVResponse:
        """Send a MKCALENDAR request."""
        return await self.request(url, "MKCALENDAR", body)

    async def put(
        self, url: str, body: str, headers: Mapping[str, str] = None
    ) -> DAVResponse:
        """Send a PUT request."""
        return await self.request(url, "PUT", body, headers or {})

    async def post(
        self, url: str, body: str, headers: Mapping[str, str] = None
    ) -> DAVResponse:
        """Send a POST request."""
        return await self.request(url, "POST", body, headers or {})

    async def delete(self, url: str) -> DAVResponse:
        """Send a DELETE request."""
        return await self.request(url, "DELETE")

    async def options(self, url: str) -> DAVResponse:
        """Send an OPTIONS request."""
        return await self.request(url, "OPTIONS")

    async def check_dav_support(self) -> Optional[str]:
        """Check if server supports DAV."""
        try:
            principal = await self.principal()
            response = await self.options(str(principal.url))
        except:
            response = await self.options(str(self.url))
        return response.headers.get("DAV", None)

    async def check_cdav_support(self) -> bool:
        """Check if server supports CalDAV."""
        support_list = await self.check_dav_support()
        return support_list is not None and "calendar-access" in support_list

    async def check_scheduling_support(self) -> bool:
        """Check if server supports CalDAV scheduling."""
        support_list = await self.check_dav_support()
        return support_list is not None and "calendar-auto-schedule" in support_list

    async def principal(self, *args, **kwargs):
        """Get the principal for this client."""
        # Lazy import to avoid circular imports
        from caldav._async.collection import AsyncPrincipal

        if not self._principal:
            self._principal = AsyncPrincipal(client=self, *args, **kwargs)
        return self._principal

    def calendar(self, **kwargs):
        """Get a calendar object by URL."""
        from caldav._async.collection import AsyncCalendar

        return AsyncCalendar(client=self, **kwargs)
