#!/usr/bin/env python
"""
Async CalDAV client implementation using httpx.AsyncClient.

This module provides AsyncDAVClient and AsyncDAVResponse classes that mirror
the synchronous DAVClient and DAVResponse but with async/await support.
"""
import logging
import os
import sys
from types import TracebackType
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, Union, cast
from urllib.parse import unquote

import httpx
from httpx import BasicAuth, DigestAuth
from lxml import etree
from lxml.etree import _Element

from .elements.base import BaseElement
from caldav import __version__
from caldav.davclient import DAVResponse, CONNKEYS  # Reuse DAVResponse and CONNKEYS
from caldav.compatibility_hints import FeatureSet
from caldav.elements import cdav, dav
from caldav.lib import error
from caldav.lib.python_utilities import to_normal_str, to_wire
from caldav.lib.url import URL
from caldav.objects import log
from caldav.requests import HTTPBearerAuth

if TYPE_CHECKING:
    from caldav.collection import Calendar

if sys.version_info < (3, 9):
    from typing import Iterable, Mapping
else:
    from collections.abc import Iterable, Mapping

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


# AsyncDAVResponse can reuse the synchronous DAVResponse since it only processes
# the response data without making additional async calls
AsyncDAVResponse = DAVResponse


class AsyncDAVClient:
    """
    Async CalDAV client using httpx.AsyncClient.

    This class mirrors DAVClient but provides async methods for all HTTP operations.
    Use this with async/await syntax:

        async with AsyncDAVClient(url="...", username="...", password="...") as client:
            principal = await client.principal()
            calendars = await principal.calendars()
    """

    proxy: Optional[str] = None
    url: URL = None
    huge_tree: bool = False

    def __init__(
        self,
        url: str,
        proxy: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth: Optional[httpx.Auth] = None,
        auth_type: Optional[str] = None,
        timeout: Optional[int] = None,
        ssl_verify_cert: Union[bool, str] = True,
        ssl_cert: Union[str, Tuple[str, str], None] = None,
        headers: Mapping[str, str] = None,
        huge_tree: bool = False,
        features: Union[FeatureSet, dict] = None,
    ) -> None:
        """
        Sets up an async HTTP connection towards the server.

        Args:
          url: A fully qualified url: `scheme://user:pass@hostname:port`
          proxy: A string defining a proxy server: `scheme://hostname:port`
          auth: A httpx.Auth object, may be passed instead of username/password
          timeout and ssl_verify_cert are passed to httpx.AsyncClient
          auth_type can be ``bearer``, ``digest`` or ``basic``
          ssl_verify_cert can be the path of a CA-bundle or False
          huge_tree: boolean, enable XMLParser huge_tree to handle big events
          features: FeatureSet or dict for compatibility hints

        The httpx library will honor proxy environmental variables like
        HTTP_PROXY, HTTPS_PROXY, ALL_PROXY, and NO_PROXY.
        """
        headers = headers or {}

        log.debug("url: " + str(url))
        self.url = URL.objectify(url)
        self.huge_tree = huge_tree
        self.features = FeatureSet(features)

        # Extract username/password from URL early (before creating AsyncClient)
        # This needs to happen before we compute the base_url
        if self.url.username is not None:
            username = unquote(self.url.username)
            password = unquote(self.url.password)

        self.username = username
        self.password = password
        self.auth = auth
        self.auth_type = auth_type

        # Handle non-ASCII passwords
        if isinstance(self.password, str):
            self.password = self.password.encode("utf-8")
        if auth and self.auth_type:
            logging.error(
                "both auth object and auth_type sent to AsyncDAVClient. The latter will be ignored."
            )
        elif self.auth_type:
            self.build_auth_object()

        # Compute base URL without authentication for httpx.AsyncClient
        # This MUST be done before creating the AsyncClient to avoid relative URL issues
        self.url = self.url.unauth()
        base_url_str = str(self.url)
        log.debug("self.url: " + base_url_str)

        # Store SSL and timeout settings early, needed for AsyncClient creation
        self.timeout = timeout
        self.ssl_verify_cert = ssl_verify_cert
        self.ssl_cert = ssl_cert

        # Prepare proxy info
        self.proxy = None
        if proxy is not None:
            _proxy = proxy
            # httpx library expects the proxy url to have a scheme
            if "://" not in proxy:
                _proxy = self.url.scheme + "://" + proxy

            # add a port if one is not specified
            p = _proxy.split(":")
            if len(p) == 2:
                _proxy += ":8080"
            log.debug("init - proxy: %s" % (_proxy))

            self.proxy = _proxy

        # Build global headers
        # Combine default headers with user-provided headers (user headers override defaults)
        default_headers = {
            "User-Agent": "python-caldav/" + __version__,
            "Content-Type": "text/xml",
            "Accept": "text/xml, text/calendar",
        }
        if headers:
            combined_headers = dict(default_headers)
            combined_headers.update(headers)
        else:
            combined_headers = default_headers

        # Create httpx AsyncClient with HTTP/2 support
        # CRITICAL: base_url is required to handle relative URLs properly with cookies
        # Without base_url, httpx's cookie jar will receive relative URLs which causes
        # urllib.request.Request to fail with "unknown url type" error
        self.session = httpx.AsyncClient(
            base_url=base_url_str,
            http2=True,
            proxy=self.proxy,
            verify=self.ssl_verify_cert,
            cert=self.ssl_cert,
            timeout=self.timeout,
            headers=combined_headers,
        )

        # Store headers for reference
        self.headers = self.session.headers

        self._principal = None

    async def __aenter__(self) -> Self:
        """Async context manager entry"""
        # Used for tests, to set up a temporarily test server
        if hasattr(self, "setup"):
            try:
                self.setup()
            except:
                self.setup(self)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[BaseException] = None,
        exc_value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None,
    ) -> None:
        """Async context manager exit"""
        await self.close()
        # Used for tests, to tear down a temporarily test server
        if hasattr(self, "teardown"):
            try:
                self.teardown()
            except:
                self.teardown(self)

    async def close(self) -> None:
        """Closes the AsyncDAVClient's session object"""
        await self.session.aclose()

    def extract_auth_types(self, header: str):
        """Extract supported authentication types from WWW-Authenticate header"""
        return {h.split()[0] for h in header.lower().split(",")}

    def build_auth_object(self, auth_types: Optional[List[str]] = None):
        """
        Build authentication object based on auth_type or server capabilities.

        Args:
            auth_types: A list/tuple of acceptable auth_types from server
        """
        auth_type = self.auth_type
        if not auth_type and not auth_types:
            raise error.AuthorizationError(
                "No auth-type given. This shouldn't happen."
            )
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
                self.auth = DigestAuth(self.username, self.password)
            elif auth_type == "basic":
                self.auth = BasicAuth(self.username, self.password)
            elif auth_type == "bearer":
                self.auth = HTTPBearerAuth(self.password)

    async def request(
        self,
        url: str,
        method: str = "GET",
        body: str = "",
        headers: Mapping[str, str] = None,
    ) -> AsyncDAVResponse:
        """
        Send an async HTTP request and return response.

        Args:
            url: Target URL
            method: HTTP method (GET, POST, PROPFIND, etc.)
            body: Request body
            headers: Additional headers for this request

        Returns:
            AsyncDAVResponse object
        """
        headers = headers or {}

        # Combine instance headers with request-specific headers
        combined_headers = dict(self.headers)
        combined_headers.update(headers or {})
        if (body is None or body == "") and "Content-Type" in combined_headers:
            del combined_headers["Content-Type"]

        # Objectify the URL
        url_obj = URL.objectify(url)

        if self.proxy is not None:
            log.debug("using proxy - %s" % (self.proxy))

        log.debug(
            "sending request - method={0}, url={1}, headers={2}\nbody:\n{3}".format(
                method, str(url_obj), combined_headers, to_normal_str(body)
            )
        )

        try:
            r = await self.session.request(
                method,
                str(url_obj),
                content=to_wire(body),
                headers=combined_headers,
                auth=self.auth,
                follow_redirects=True,
            )
            reason_phrase = r.reason_phrase if hasattr(r, 'reason_phrase') else ''
            log.debug("server responded with %i %s" % (r.status_code, reason_phrase))
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
                        msg += "\nSupported authentication types: %s" % (
                            ", ".join(auth_types)
                        )
                log.warning(msg)
            response = AsyncDAVResponse(r, self)
        except:
            # Workaround for servers that abort connection on unauthenticated requests with body
            # ref https://github.com/python-caldav/caldav/issues/158
            if self.auth or not self.password:
                raise
            r = await self.session.request(
                method="GET",
                url=str(url_obj),
                headers=combined_headers,
                follow_redirects=True,
            )
            if not r.status_code == 401:
                raise

        # Handle authentication challenges
        r_headers = r.headers
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

            return await self.request(url, method, body, headers)

        elif (
            r.status_code == 401
            and "WWW-Authenticate" in r_headers
            and self.auth
            and self.password
            and isinstance(self.password, bytes)
        ):
            # Retry with decoded password for compatibility with old servers
            auth_types = self.extract_auth_types(r_headers["WWW-Authenticate"])
            self.password = self.password.decode()
            self.build_auth_object(auth_types)

            self.username = None
            self.password = None
            return await self.request(str(url_obj), method, body, headers)

        # Raise authorization errors
        if response.status == httpx.codes.FORBIDDEN or response.status == httpx.codes.UNAUTHORIZED:
            try:
                reason = response.reason
            except AttributeError:
                reason = "None given"
            raise error.AuthorizationError(url=str(url_obj), reason=reason)

        if error.debug_dump_communication:
            import datetime
            from tempfile import NamedTemporaryFile

            with NamedTemporaryFile(prefix="caldavcomm", delete=False) as commlog:
                commlog.write(b"=" * 80 + b"\n")
                commlog.write(f"{datetime.datetime.now():%FT%H:%M:%S}".encode("utf-8"))
                commlog.write(b"\n====>\n")
                commlog.write(f"{method} {url}\n".encode("utf-8"))
                commlog.write(
                    b"\n".join(to_wire(f"{x}: {headers[x]}") for x in headers)
                )
                commlog.write(b"\n\n")
                commlog.write(to_wire(body))
                commlog.write(b"<====\n")
                commlog.write(f"{response.status} {response.reason}".encode("utf-8"))
                commlog.write(
                    b"\n".join(
                        to_wire(f"{x}: {response.headers[x]}") for x in response.headers
                    )
                )
                commlog.write(b"\n\n")
                if response.tree is not None:
                    commlog.write(
                        to_wire(etree.tostring(response.tree, pretty_print=True))
                    )
                else:
                    commlog.write(to_wire(response._raw))
                commlog.write(b"\n")

        return response

    async def propfind(
        self, url: Optional[str] = None, props: str = "", depth: int = 0
    ) -> AsyncDAVResponse:
        """Send a PROPFIND request"""
        return await self.request(
            url or str(self.url), "PROPFIND", props, {"Depth": str(depth)}
        )

    async def proppatch(self, url: str, body: str, dummy: None = None) -> AsyncDAVResponse:
        """Send a PROPPATCH request"""
        return await self.request(url, "PROPPATCH", body)

    async def report(self, url: str, query: str = "", depth: int = 0) -> AsyncDAVResponse:
        """Send a REPORT request"""
        return await self.request(
            url,
            "REPORT",
            query,
            {"Depth": str(depth), "Content-Type": 'application/xml; charset="utf-8"'},
        )

    async def mkcol(self, url: str, body: str, dummy: None = None) -> AsyncDAVResponse:
        """Send a MKCOL request"""
        return await self.request(url, "MKCOL", body)

    async def mkcalendar(self, url: str, body: str = "", dummy: None = None) -> AsyncDAVResponse:
        """Send a MKCALENDAR request"""
        return await self.request(url, "MKCALENDAR", body)

    async def put(
        self, url: str, body: str, headers: Mapping[str, str] = None
    ) -> AsyncDAVResponse:
        """Send a PUT request"""
        return await self.request(url, "PUT", body, headers or {})

    async def post(
        self, url: str, body: str, headers: Mapping[str, str] = None
    ) -> AsyncDAVResponse:
        """Send a POST request"""
        return await self.request(url, "POST", body, headers or {})

    async def delete(self, url: str) -> AsyncDAVResponse:
        """Send a DELETE request"""
        return await self.request(url, "DELETE")

    async def options(self, url: str) -> AsyncDAVResponse:
        """Send an OPTIONS request"""
        return await self.request(url, "OPTIONS")

    async def check_dav_support(self) -> Optional[str]:
        """Check if server supports DAV (RFC4918)"""
        try:
            # Try to get principal URL for better capability detection
            principal = await self.principal()
            response = await self.options(principal.url)
        except:
            response = await self.options(str(self.url))
        return response.headers.get("DAV", None)

    async def check_cdav_support(self) -> bool:
        """Check if server supports CalDAV (RFC4791)"""
        support_list = await self.check_dav_support()
        return support_list is not None and "calendar-access" in support_list

    async def check_scheduling_support(self) -> bool:
        """Check if server supports CalDAV Scheduling (RFC6833)"""
        support_list = await self.check_dav_support()
        return support_list is not None and "calendar-auto-schedule" in support_list

    async def principal(self, *largs, **kwargs):
        """
        Returns an AsyncPrincipal object for the current user.

        This is the main entry point for interacting with calendars.

        Returns:
            AsyncPrincipal object
        """
        from .async_collection import AsyncPrincipal

        if not self._principal:
            self._principal = AsyncPrincipal(client=self, *largs, **kwargs)
            await self._principal._ensure_principal_url()
        return self._principal

    def calendar(self, **kwargs):
        """
        Returns an AsyncCalendar object.

        Note: This doesn't verify the calendar exists on the server.
        Typically, a URL should be given as a named parameter.

        If you don't know the URL, use:
            principal = await client.principal()
            calendars = await principal.calendars()
        """
        from .async_collection import AsyncCalendar
        return AsyncCalendar(client=self, **kwargs)
