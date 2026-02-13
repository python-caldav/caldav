#!/usr/bin/env python
"""
Async-first DAVClient implementation for the caldav library.

This module provides the core async CalDAV/WebDAV client functionality.
For sync usage, see the davclient.py wrapper.
"""

import logging
import sys
from collections.abc import Mapping
from types import TracebackType
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import unquote

if TYPE_CHECKING:
    from caldav.calendarobjectresource import CalendarObjectResource, Event, Todo
    from caldav.collection import Calendar, Principal

# Try httpx first (preferred), fall back to niquests
_USE_HTTPX = False
_USE_NIQUESTS = False
_H2_AVAILABLE = False

try:
    import httpx

    _USE_HTTPX = True
    # Check if h2 is available for HTTP/2 support
    try:
        import h2  # noqa: F401

        _H2_AVAILABLE = True
    except ImportError:
        pass
except ImportError:
    pass

if not _USE_HTTPX:
    try:
        import niquests
        from niquests import AsyncSession
        from niquests.structures import CaseInsensitiveDict

        _USE_NIQUESTS = True
    except ImportError:
        pass

if not _USE_HTTPX and not _USE_NIQUESTS:
    raise ImportError(
        "Either httpx or niquests library is required for async_davclient. "
        "Install with: pip install httpx  (or: pip install niquests)"
    )


from caldav import __version__
from caldav.base_client import BaseDAVClient
from caldav.base_client import get_davclient as _base_get_davclient
from caldav.compatibility_hints import FeatureSet
from caldav.lib import error
from caldav.lib.python_utilities import to_normal_str, to_wire
from caldav.lib.url import URL
from caldav.protocol.types import (
    CalendarQueryResult,
    PropfindResult,
)
from caldav.protocol.xml_builders import (
    _build_calendar_multiget_body,
    _build_calendar_query_body,
    _build_propfind_body,
    _build_sync_collection_body,
)
from caldav.protocol.xml_parsers import (
    _parse_calendar_query_response,
    _parse_propfind_response,
    _parse_sync_collection_response,
)
from caldav.requests import HTTPBearerAuth
from caldav.response import BaseDAVResponse

log = logging.getLogger("caldav")

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


class AsyncDAVResponse(BaseDAVResponse):
    """
    Response from an async DAV request.

    This class handles the parsing of DAV responses, including XML parsing.
    End users typically won't interact with this class directly.

    Response parsing methods are inherited from BaseDAVResponse.

    New protocol-based attributes:
        results: Parsed results from protocol layer (List[PropfindResult], etc.)
        sync_token: Sync token from sync-collection response
    """

    # Protocol-based parsed results (new interface)
    results: list[PropfindResult | CalendarQueryResult] | None = None
    sync_token: str | None = None

    def __init__(self, response: Any, davclient: Optional["AsyncDAVClient"] = None) -> None:
        """Initialize from httpx.Response or niquests.Response."""
        self._init_from_response(response, davclient)

    # Response parsing methods are inherited from BaseDAVResponse


class AsyncDAVClient(BaseDAVClient):
    """
    Async WebDAV/CalDAV client.

    This is the core async implementation. For sync usage, see DAVClient
    in davclient.py which provides a thin wrapper around this class.

    The recommended way to create a client is via get_davclient():
        async with await get_davclient(url="...", username="...", password="...") as client:
            principal = await client.get_principal()
    """

    proxy: str | None = None
    url: URL = None
    huge_tree: bool = False

    def __init__(
        self,
        url: str | None = "",
        proxy: str | None = None,
        username: str | None = None,
        password: str | None = None,
        auth: Any | None = None,  # httpx.Auth or niquests.auth.AuthBase
        auth_type: str | None = None,
        timeout: int | None = None,
        ssl_verify_cert: bool | str = True,
        ssl_cert: str | tuple[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        huge_tree: bool = False,
        features: FeatureSet | dict | str | None = None,
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
            auth: Custom auth object (httpx.Auth or niquests AuthBase).
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

        from caldav.config import resolve_features

        features = resolve_features(features)
        if isinstance(features, FeatureSet):
            self.features = features
        else:
            self.features = FeatureSet(features)
        self.huge_tree = huge_tree

        # Store SSL and proxy settings for client creation
        self._http2 = None
        self._proxy = proxy
        if self._proxy is not None and "://" not in self._proxy:
            self._proxy = "http://" + self._proxy
        self._ssl_verify_cert = ssl_verify_cert
        self._ssl_cert = ssl_cert
        self._timeout = timeout

        # Create async client with HTTP/2 if supported and h2 package is available
        # Note: Client is created lazily or recreated when settings change
        try:
            # Only enable HTTP/2 if the server supports it AND h2 is installed
            self._http2 = self.features.is_supported("http.multiplexing") and (
                _H2_AVAILABLE or _USE_NIQUESTS
            )
        except (TypeError, AttributeError):
            self._http2 = False
        self._create_session()

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

        # Setup proxy (stored in self._proxy above)
        self.proxy = self._proxy

        # Setup other parameters (stored above for client creation)
        self.timeout = self._timeout
        self.ssl_verify_cert = self._ssl_verify_cert
        self.ssl_cert = self._ssl_cert

        # Setup headers with User-Agent
        self.headers: dict[str, str] = {
            "User-Agent": f"caldav-async/{__version__}",
        }
        self.headers.update(headers)

    def _create_session(self) -> None:
        """Create or recreate the async HTTP client with current settings."""
        if _USE_HTTPX:
            self.session = httpx.AsyncClient(
                http2=self._http2 or False,
                proxy=self._proxy,
                verify=self._ssl_verify_cert if self._ssl_verify_cert is not None else True,
                cert=self._ssl_cert,
                timeout=self._timeout,
            )
        else:
            # niquests - proxy/ssl/timeout are passed per-request
            try:
                self.session = AsyncSession(multiplexed=self._http2 or False)
            except TypeError:
                self.session = AsyncSession()

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the async client."""
        if hasattr(self, "session"):
            if _USE_HTTPX:
                await self.session.aclose()
            else:
                await self.session.close()

    @staticmethod
    def _build_method_headers(
        method: str,
        depth: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
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

        # Add Content-Type for methods that typically send XML bodies
        if method in ("REPORT", "PROPFIND", "PROPPATCH", "MKCALENDAR", "MKCOL"):
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
        headers: Mapping[str, str] | None = None,
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

        log.debug(
            f"sending request - method={method}, url={str(url_obj)}, headers={combined_headers}\nbody:\n{to_normal_str(body)}"
        )

        # Build request kwargs - different for httpx vs niquests
        if _USE_HTTPX:
            request_kwargs: dict[str, Any] = {
                "method": method,
                "url": str(url_obj),
                "content": to_wire(body) if body else None,
                "headers": combined_headers,
                "auth": self.auth,
                "timeout": self.timeout,
            }
        else:
            # niquests uses different parameter names
            proxies = None
            if self.proxy is not None:
                proxies = {url_obj.scheme: self.proxy}
            request_kwargs: dict[str, Any] = {
                "method": method,
                "url": str(url_obj),
                "data": to_wire(body) if body else None,
                "headers": combined_headers,
                "auth": self.auth,
                "timeout": self.timeout,
                "proxies": proxies,
                "verify": self.ssl_verify_cert,
                "cert": self.ssl_cert,
            }

        try:
            r = await self.session.request(**request_kwargs)
            reason = r.reason_phrase if _USE_HTTPX else r.reason
            log.debug(f"server responded with {r.status_code} {reason}")
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
            # Build minimal request for auth detection
            if _USE_HTTPX:
                r = await self.session.request(
                    method="GET",
                    url=str(url_obj),
                    headers=combined_headers,
                    timeout=self.timeout,
                )
            else:
                proxies = None
                if self.proxy is not None:
                    proxies = {url_obj.scheme: self.proxy}
                r = await self.session.request(
                    method="GET",
                    url=str(url_obj),
                    headers=combined_headers,
                    timeout=self.timeout,
                    proxies=proxies,
                    verify=self.ssl_verify_cert,
                    cert=self.ssl_cert,
                )
            reason = r.reason_phrase if _USE_HTTPX else r.reason
            log.debug(f"auth type detection: server responded with {r.status_code} {reason}")
            if r.status_code == 401 and r.headers.get("WWW-Authenticate"):
                auth_types = self.extract_auth_types(r.headers["WWW-Authenticate"])
                self.build_auth_object(auth_types)
                # Retry original request with auth
                request_kwargs["auth"] = self.auth
                r = await self.session.request(**request_kwargs)
            response = AsyncDAVResponse(r, self)

        # Handle 401 responses for auth negotiation (after try/except)
        # This matches the original sync client's auth negotiation logic
        # httpx headers are already case-insensitive
        if (
            r.status_code == 401
            and "WWW-Authenticate" in r.headers
            and not self.auth
            and self.username is not None
            and self.password is not None  # Empty password OK, but None means not configured
        ):
            auth_types = self.extract_auth_types(r.headers["WWW-Authenticate"])
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
            and "WWW-Authenticate" in r.headers
            and self.auth
            and self.password
            and isinstance(self.password, bytes)
        ):
            # Handle HTTP/2 issue (matches original sync client)
            # Most likely wrong username/password combo, but could be an HTTP/2 problem
            if self.features.is_supported("http.multiplexing", return_defaults=False) is None:
                await self.close()  # Uses correct close method for httpx/niquests
                self._http2 = False
                self._create_session()
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
            auth_types = self.extract_auth_types(r.headers["WWW-Authenticate"])
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
        url: str | None = None,
        body: str = "",
        depth: int = 0,
        headers: Mapping[str, str] | None = None,
        props: list[str] | None = None,
    ) -> AsyncDAVResponse:
        """
        Send a PROPFIND request.

        Args:
            url: Target URL (defaults to self.url).
            body: XML properties request (legacy, use props instead).
            depth: Maximum recursion depth.
            headers: Additional headers.
            props: List of property names to request (uses protocol layer).

        Returns:
            AsyncDAVResponse with results attribute containing parsed PropfindResult list.
        """
        # Use protocol layer to build XML if props provided
        if props is not None and not body:
            body = _build_propfind_body(props).decode("utf-8")

        final_headers = self._build_method_headers("PROPFIND", depth, headers)
        response = await self.request(url or str(self.url), "PROPFIND", body, final_headers)

        # Parse response using protocol layer
        if response.status in (200, 207) and response._raw:
            raw_bytes = (
                response._raw if isinstance(response._raw, bytes) else response._raw.encode("utf-8")
            )
            response.results = _parse_propfind_response(
                raw_bytes, response.status, response.huge_tree
            )

        return response

    async def report(
        self,
        url: str | None = None,
        body: str = "",
        depth: int | None = 0,
        headers: Mapping[str, str] | None = None,
    ) -> AsyncDAVResponse:
        """
        Send a REPORT request.

        Args:
            url: Target URL (defaults to self.url).
            body: XML report request.
            depth: Maximum recursion depth. None means don't send Depth header
                (required for calendar-multiget per RFC 4791 section 7.9).
            headers: Additional headers.

        Returns:
            AsyncDAVResponse
        """
        final_headers = self._build_method_headers("REPORT", depth, headers)
        return await self.request(url or str(self.url), "REPORT", body, final_headers)

    async def options(
        self,
        url: str | None = None,
        headers: Mapping[str, str] | None = None,
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
        headers: Mapping[str, str] | None = None,
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
        final_headers = self._build_method_headers("PROPPATCH", extra_headers=headers)
        return await self.request(url, "PROPPATCH", body, final_headers)

    async def mkcol(
        self,
        url: str,
        body: str = "",
        headers: Mapping[str, str] | None = None,
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
        final_headers = self._build_method_headers("MKCOL", extra_headers=headers)
        return await self.request(url, "MKCOL", body, final_headers)

    async def mkcalendar(
        self,
        url: str,
        body: str = "",
        headers: Mapping[str, str] | None = None,
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
        final_headers = self._build_method_headers("MKCALENDAR", extra_headers=headers)
        return await self.request(url, "MKCALENDAR", body, final_headers)

    async def put(
        self,
        url: str,
        body: str,
        headers: Mapping[str, str] | None = None,
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
        headers: Mapping[str, str] | None = None,
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
        headers: Mapping[str, str] | None = None,
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

    # ==================== High-Level CalDAV Methods ====================
    # These methods use the protocol layer for building XML and parsing responses

    async def calendar_query(
        self,
        url: str | None = None,
        start: Any | None = None,
        end: Any | None = None,
        event: bool = False,
        todo: bool = False,
        journal: bool = False,
        expand: bool = False,
        depth: int = 1,
        headers: Mapping[str, str] | None = None,
    ) -> AsyncDAVResponse:
        """
        Execute a calendar-query REPORT to search for calendar objects.

        Args:
            url: Target calendar URL (defaults to self.url).
            start: Start of time range filter.
            end: End of time range filter.
            event: Include events (VEVENT).
            todo: Include todos (VTODO).
            journal: Include journals (VJOURNAL).
            expand: Expand recurring events.
            depth: Search depth.
            headers: Additional headers.

        Returns:
            AsyncDAVResponse with results containing List[CalendarQueryResult].
        """

        body, _ = _build_calendar_query_body(
            start=start,
            end=end,
            event=event,
            todo=todo,
            journal=journal,
            expand=expand,
        )

        final_headers = self._build_method_headers("REPORT", depth, headers)
        response = await self.request(
            url or str(self.url), "REPORT", body.decode("utf-8"), final_headers
        )

        # Parse response using protocol layer
        if response.status in (200, 207) and response._raw:
            raw_bytes = (
                response._raw if isinstance(response._raw, bytes) else response._raw.encode("utf-8")
            )
            response.results = _parse_calendar_query_response(
                raw_bytes, response.status, response.huge_tree
            )

        return response

    async def calendar_multiget(
        self,
        url: str | None = None,
        hrefs: list[str] | None = None,
        depth: int = 1,
        headers: Mapping[str, str] | None = None,
    ) -> AsyncDAVResponse:
        """
        Execute a calendar-multiget REPORT to fetch specific calendar objects.

        Args:
            url: Target calendar URL (defaults to self.url).
            hrefs: List of object URLs to retrieve.
            depth: Search depth.
            headers: Additional headers.

        Returns:
            AsyncDAVResponse with results containing List[CalendarQueryResult].
        """
        body = _build_calendar_multiget_body(hrefs or [])

        final_headers = self._build_method_headers("REPORT", depth, headers)
        response = await self.request(
            url or str(self.url), "REPORT", body.decode("utf-8"), final_headers
        )

        # Parse response using protocol layer
        if response.status in (200, 207) and response._raw:
            raw_bytes = (
                response._raw if isinstance(response._raw, bytes) else response._raw.encode("utf-8")
            )
            response.results = _parse_calendar_query_response(
                raw_bytes, response.status, response.huge_tree
            )

        return response

    async def sync_collection(
        self,
        url: str | None = None,
        sync_token: str | None = None,
        props: list[str] | None = None,
        depth: int = 1,
        headers: Mapping[str, str] | None = None,
    ) -> AsyncDAVResponse:
        """
        Execute a sync-collection REPORT for efficient synchronization.

        Args:
            url: Target calendar URL (defaults to self.url).
            sync_token: Previous sync token (None for initial sync).
            props: Properties to include in response.
            depth: Search depth.
            headers: Additional headers.

        Returns:
            AsyncDAVResponse with results containing SyncCollectionResult.
        """
        body = _build_sync_collection_body(sync_token=sync_token, props=props)

        final_headers = self._build_method_headers("REPORT", depth, headers)
        response = await self.request(
            url or str(self.url), "REPORT", body.decode("utf-8"), final_headers
        )

        # Parse response using protocol layer
        if response.status in (200, 207) and response._raw:
            raw_bytes = (
                response._raw if isinstance(response._raw, bytes) else response._raw.encode("utf-8")
            )
            sync_result = _parse_sync_collection_response(
                raw_bytes, response.status, response.huge_tree
            )
            response.results = sync_result.changed
            response.sync_token = sync_result.sync_token

        return response

    # ==================== Authentication Helpers ====================

    def build_auth_object(self, auth_types: list[str] | None = None) -> None:
        """Build authentication object for the httpx/niquests library.

        Uses shared auth type selection logic from BaseDAVClient, then
        creates the appropriate auth object for this HTTP library.

        Args:
            auth_types: List of acceptable auth types from server.
        """
        # Use shared selection logic
        auth_type = self._select_auth_type(auth_types)

        # Build auth object - use appropriate classes for httpx or niquests
        if auth_type == "bearer":
            self.auth = HTTPBearerAuth(self.password)
        elif auth_type == "digest":
            if _USE_HTTPX:
                self.auth = httpx.DigestAuth(self.username, self.password)
            else:
                from niquests.auth import HTTPDigestAuth

                self.auth = HTTPDigestAuth(self.username, self.password)
        elif auth_type == "basic":
            if _USE_HTTPX:
                self.auth = httpx.BasicAuth(self.username, self.password)
            else:
                from niquests.auth import HTTPBasicAuth

                self.auth = HTTPBasicAuth(self.username, self.password)
        elif auth_type:
            raise error.AuthorizationError(f"Unsupported auth type: {auth_type}")

    # ==================== High-Level Methods ====================
    # These methods provide a clean, client-centric async API using the operations layer.

    async def get_principal(self) -> "Principal":
        """Get the principal (user) for this CalDAV connection.

        This method fetches the current-user-principal from the server and returns
        a Principal object that can be used to access calendars and other resources.

        Returns:
            Principal object for the authenticated user.

        Example:
            async with await get_davclient(url="...", username="...", password="...") as client:
                principal = await client.get_principal()
                calendars = await client.get_calendars(principal)
        """
        from caldav.collection import Principal

        # Use operations layer for discovery logic

        # Fetch current-user-principal
        response = await self.propfind(
            str(self.url),
            props=["{DAV:}current-user-principal"],
            depth=0,
        )

        principal_url = None
        if response.results:
            for result in response.results:
                cup = result.properties.get("{DAV:}current-user-principal")
                if cup:
                    principal_url = cup
                    break

        if not principal_url:
            # Fallback: use the base URL as principal URL
            principal_url = str(self.url)

        # Create and return Principal object
        principal = Principal(client=self, url=principal_url)
        return principal

    async def get_calendars(self, principal: Optional["Principal"] = None) -> list["Calendar"]:
        """Get all calendars for the given principal.

        This method fetches calendars from the principal's calendar-home-set
        and returns a list of Calendar objects.

        Args:
            principal: Principal object (if None, fetches principal first)

        Returns:
            List of Calendar objects.

        Example:
            principal = await client.get_principal()
            calendars = await client.get_calendars(principal)
            for cal in calendars:
                print(f"Calendar: {cal.get_display_name()}")
        """
        from caldav.collection import Calendar
        from caldav.operations.calendarset_ops import (
            _extract_calendars_from_propfind_results as extract_calendars,
        )

        if principal is None:
            principal = await self.get_principal()

        # Get calendar-home-set from principal
        calendar_home_url = await self._get_calendar_home_set(principal)
        if not calendar_home_url:
            return []

        # Make URL absolute if relative
        calendar_home_url = self._make_absolute_url(calendar_home_url)

        # Fetch calendars via PROPFIND
        response = await self.propfind(
            calendar_home_url,
            props=self.CALENDAR_LIST_PROPS,
            depth=1,
        )

        # Process results using shared helper
        calendar_infos = extract_calendars(response.results)

        # Convert CalendarInfo objects to Calendar objects
        return [
            Calendar(client=self, url=info.url, name=info.name, id=info.cal_id)
            for info in calendar_infos
        ]

    async def _get_calendar_home_set(self, principal: "Principal") -> str | None:
        """Get the calendar-home-set URL for a principal.

        Args:
            principal: Principal object

        Returns:
            Calendar home set URL or None
        """
        from caldav.operations.principal_ops import (
            _extract_calendar_home_set_from_results as extract_home_set,
        )

        # Try to get from principal properties
        response = await self.propfind(
            str(principal.url),
            props=self.CALENDAR_HOME_SET_PROPS,
            depth=0,
        )

        return extract_home_set(response.results)

    async def get_events(
        self,
        calendar: "Calendar",
        start: Any | None = None,
        end: Any | None = None,
    ) -> list["Event"]:
        """Get events from a calendar.

        This is a convenience method that searches for VEVENT objects in the
        calendar, optionally filtered by date range.

        Args:
            calendar: Calendar to search
            start: Start of date range (optional)
            end: End of date range (optional)

        Returns:
            List of Event objects.

        Example:
            from datetime import datetime
            events = await client.get_events(
                calendar,
                start=datetime(2024, 1, 1),
                end=datetime(2024, 12, 31)
            )
        """
        return await self.search_calendar(calendar, event=True, start=start, end=end)

    async def get_todos(
        self,
        calendar: "Calendar",
        include_completed: bool = False,
    ) -> list["Todo"]:
        """Get todos from a calendar.

        Args:
            calendar: Calendar to search
            include_completed: Whether to include completed todos

        Returns:
            List of Todo objects.
        """
        return await self.search_calendar(calendar, todo=True, include_completed=include_completed)

    async def search_calendar(
        self,
        calendar: "Calendar",
        event: bool = False,
        todo: bool = False,
        journal: bool = False,
        start: Any | None = None,
        end: Any | None = None,
        include_completed: bool | None = None,
        expand: bool = False,
        **kwargs: Any,
    ) -> list["CalendarObjectResource"]:
        """Search a calendar for events, todos, or journals.

        This method provides a clean interface to calendar search using the
        operations layer for building queries and processing results.

        Args:
            calendar: Calendar to search
            event: Search for events (VEVENT)
            todo: Search for todos (VTODO)
            journal: Search for journals (VJOURNAL)
            start: Start of date range
            end: End of date range
            include_completed: Include completed todos (default: False for todos)
            expand: Expand recurring events
            **kwargs: Additional search parameters

        Returns:
            List of Event/Todo/Journal objects.

        Example:
            # Get all events in January 2024
            events = await client.search_calendar(
                calendar,
                event=True,
                start=datetime(2024, 1, 1),
                end=datetime(2024, 1, 31),
            )

            # Get pending todos
            todos = await client.search_calendar(
                calendar,
                todo=True,
                include_completed=False,
            )
        """
        from caldav.search import CalDAVSearcher

        # Build searcher with parameters
        searcher = CalDAVSearcher(
            event=event,
            todo=todo,
            journal=journal,
            start=start,
            end=end,
            expand=expand,
        )

        if include_completed is not None:
            searcher.include_completed = include_completed

        # Execute async search
        results = await searcher.async_search(calendar, **kwargs)
        return results

    async def search_principals(self, name: str | None = None) -> list["Principal"]:
        """
        Search for principals on the server.

        Instead of returning the current logged-in principal, this method
        attempts to query for all principals (or principals matching a name).
        This may or may not work depending on the permissions and
        implementation of the calendar server.

        Args:
            name: Optional name filter to search for specific principals

        Returns:
            List of Principal objects found on the server

        Raises:
            ReportError: If the server doesn't support principal search
        """
        from lxml import etree

        from caldav.collection import CalendarSet, Principal
        from caldav.elements import cdav, dav

        if name:
            name_filter = [
                dav.PropertySearch() + [dav.Prop() + [dav.DisplayName()]] + dav.Match(value=name)
            ]
        else:
            name_filter = []

        query = (
            dav.PrincipalPropertySearch()
            + name_filter
            + [dav.Prop(), cdav.CalendarHomeSet(), dav.DisplayName()]
        )
        response = await self.report(str(self.url), etree.tostring(query.xmlelement()))

        if response.status >= 300:
            raise error.ReportError(f"{response.status} {response.reason} - {response.raw}")

        principal_dict = response._find_objects_and_props()
        ret = []
        for x in principal_dict:
            p = principal_dict[x]
            if dav.DisplayName.tag not in p:
                continue
            pname = p[dav.DisplayName.tag].text
            error.assert_(not p[dav.DisplayName.tag].getchildren())
            error.assert_(not p[dav.DisplayName.tag].items())
            chs = p[cdav.CalendarHomeSet.tag]
            error.assert_(not chs.items())
            error.assert_(not chs.text)
            chs_href = chs.getchildren()
            error.assert_(len(chs_href) == 1)
            error.assert_(not chs_href[0].items())
            error.assert_(not chs_href[0].getchildren())
            chs_url = chs_href[0].text
            calendar_home_set = CalendarSet(client=self, url=chs_url)
            ret.append(
                Principal(client=self, url=x, name=pname, calendar_home_set=calendar_home_set)
            )
        return ret

    async def principals(self, name: str | None = None) -> list["Principal"]:
        """
        Deprecated. Use :meth:`search_principals` instead.

        This method searches for principals on the server.
        """
        import warnings

        warnings.warn(
            "principals() is deprecated, use search_principals() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.search_principals(name=name)

    async def principal(self) -> "Principal":
        """
        Legacy method. Use :meth:`get_principal` for new code.

        Returns the Principal object for the authenticated user.
        """
        return await self.get_principal()

    def calendar(self, **kwargs: Any) -> "Calendar":
        """Returns a calendar object.

        Typically, a URL should be given as a named parameter (url)

        No network traffic will be initiated by this method.

        If you don't know the URL of the calendar, use
        ``await client.get_principal().get_calendars()`` instead, or
        ``await client.get_calendars()``
        """
        from caldav.collection import Calendar

        return Calendar(client=self, **kwargs)

    async def check_dav_support(self) -> str | None:
        """
        Check if the server supports DAV.

        Returns the DAV header from an OPTIONS request, or None if not supported.
        """
        response = await self.options(str(self.url))
        return response.headers.get("DAV")

    async def check_cdav_support(self) -> bool:
        """
        Check if the server supports CalDAV.

        Returns True if the server indicates CalDAV support in DAV header.
        """
        dav_header = await self.check_dav_support()
        return dav_header is not None and "calendar-access" in dav_header

    async def check_scheduling_support(self) -> bool:
        """
        Check if the server supports RFC6638 scheduling.

        Returns True if the server indicates scheduling support in DAV header.
        """
        dav_header = await self.check_dav_support()
        return dav_header is not None and "calendar-auto-schedule" in dav_header

    async def supports_dav(self) -> str | None:
        """
        Check if the server supports DAV.

        This is an alias for :meth:`check_dav_support`.
        """
        return await self.check_dav_support()

    async def supports_caldav(self) -> bool:
        """
        Check if the server supports CalDAV.

        This is an alias for :meth:`check_cdav_support`.
        """
        return await self.check_cdav_support()

    async def supports_scheduling(self) -> bool:
        """
        Check if the server supports RFC6638 scheduling.

        This is an alias for :meth:`check_scheduling_support`.
        """
        return await self.check_scheduling_support()


# ==================== Factory Function ====================


async def get_davclient(probe: bool = True, **kwargs: Any) -> AsyncDAVClient:
    """
    Get an async DAV client instance with configuration from multiple sources.

    See :func:`caldav.base_client.get_davclient` for full documentation.

    Args:
        probe: Verify connectivity with OPTIONS request (default: True).
        **kwargs: All other arguments passed to base get_davclient.

    Returns:
        AsyncDAVClient instance.

    Raises:
        ValueError: If no configuration is found.

    Example::

        async with await get_davclient(url="...", username="...", password="...") as client:
            principal = await client.principal()
    """
    client = _base_get_davclient(AsyncDAVClient, **kwargs)

    if client is None:
        raise ValueError(
            "No configuration found. Provide connection parameters, "
            "set CALDAV_URL environment variable, or create a config file."
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


async def get_calendars(
    calendar_url: Any | None = None,
    calendar_name: Any | None = None,
    raise_errors: bool = False,
    **kwargs: Any,
) -> list["Calendar"]:
    """
    Get calendars from a CalDAV server asynchronously.

    This is the async version of :func:`caldav.get_calendars`.

    Args:
        calendar_url: URL(s) or ID(s) of specific calendars to fetch.
        calendar_name: Name(s) of specific calendars to fetch by display name.
        raise_errors: If True, raise exceptions on errors; if False, log and skip.
        **kwargs: Connection parameters (url, username, password, etc.)

    Returns:
        List of Calendar objects matching the criteria.

    Example::

        from caldav.async_davclient import get_calendars

        calendars = await get_calendars(url="...", username="...", password="...")
    """
    from caldav.base_client import _normalize_to_list

    def _try(coro_result, errmsg):
        """Handle errors based on raise_errors flag."""
        if coro_result is None:
            log.error(f"Problems fetching calendar information: {errmsg}")
            if raise_errors:
                raise ValueError(errmsg)
        return coro_result

    try:
        client = await get_davclient(probe=True, **kwargs)
    except Exception as e:
        if raise_errors:
            raise
        log.error(f"Failed to create async client: {e}")
        return []

    try:
        principal = await client.get_principal()
        if not principal:
            _try(None, "getting principal")
            return []

        calendars = []
        calendar_urls = _normalize_to_list(calendar_url)
        calendar_names = _normalize_to_list(calendar_name)

        # Fetch specific calendars by URL/ID
        for cal_url in calendar_urls:
            if "/" in str(cal_url):
                calendar = principal.calendar(cal_url=cal_url)
            else:
                calendar = principal.calendar(cal_id=cal_url)

            try:
                display_name = await calendar.get_display_name()
                if display_name is not None:
                    calendars.append(calendar)
            except Exception as e:
                log.error(f"Problems fetching calendar {cal_url}: {e}")
                if raise_errors:
                    raise

        # Fetch specific calendars by name
        for cal_name in calendar_names:
            try:
                calendar = await principal.calendar(name=cal_name)
                if calendar:
                    calendars.append(calendar)
            except Exception as e:
                log.error(f"Problems fetching calendar by name '{cal_name}': {e}")
                if raise_errors:
                    raise

        # If no specific calendars requested, get all calendars
        if not calendars and not calendar_urls and not calendar_names:
            try:
                all_cals = await principal.get_calendars()
                if all_cals:
                    calendars = all_cals
            except Exception as e:
                log.error(f"Problems fetching all calendars: {e}")
                if raise_errors:
                    raise

        return calendars

    finally:
        # Don't close the client - let the caller manage its lifecycle
        pass


async def get_calendar(**kwargs: Any) -> Optional["Calendar"]:
    """
    Get a single calendar from a CalDAV server asynchronously.

    This is a convenience function for the common case where only one
    calendar is needed. It returns the first matching calendar or None.

    Args:
        Same as :func:`get_calendars`.

    Returns:
        A single Calendar object, or None if no calendars found.

    Example::

        from caldav.async_davclient import get_calendar

        calendar = await get_calendar(calendar_name="Work", url="...", ...)
    """
    calendars = await get_calendars(**kwargs)
    return calendars[0] if calendars else None
