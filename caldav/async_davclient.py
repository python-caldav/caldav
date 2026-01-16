#!/usr/bin/env python
"""
Async-first DAVClient implementation for the caldav library.

This module provides the core async CalDAV/WebDAV client functionality.
For sync usage, see the davclient.py wrapper.
"""
import logging
import sys
import warnings
from collections.abc import Mapping
from types import TracebackType
from typing import Any
from typing import List
from typing import Optional
from typing import Union
from urllib.parse import unquote

try:
    import httpx
except ImportError as err:
    raise ImportError(
        "httpx library is required for async_davclient. "
        "Install with: pip install httpx"
    ) from err


from caldav import __version__
from caldav.compatibility_hints import FeatureSet
from caldav.lib import error
from caldav.lib.auth import extract_auth_types
from caldav.lib.python_utilities import to_normal_str, to_wire
from caldav.lib.url import URL
from caldav.objects import log
from caldav.protocol.types import (
    PropfindResult,
    CalendarQueryResult,
    SyncCollectionResult,
)
from caldav.protocol.xml_builders import (
    build_propfind_body,
    build_calendar_query_body,
    build_calendar_multiget_body,
    build_sync_collection_body,
    build_mkcalendar_body,
    build_proppatch_body,
)
from caldav.protocol.xml_parsers import (
    parse_propfind_response,
    parse_calendar_query_response,
    parse_sync_collection_response,
)
from caldav.requests import HTTPBearerAuth
from caldav.response import BaseDAVResponse

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
    results: Optional[List[Union[PropfindResult, CalendarQueryResult]]] = None
    sync_token: Optional[str] = None

    def __init__(
        self, response: httpx.Response, davclient: Optional["AsyncDAVClient"] = None
    ) -> None:
        self._init_from_response(response, davclient)

    # Response parsing methods are inherited from BaseDAVResponse


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
        auth: Optional[httpx.Auth] = None,
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
            auth: Custom auth object (httpx.Auth).
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

        # Create async client with HTTP/2 if supported
        # Note: Client is created lazily or recreated when settings change
        try:
            self._http2 = self.features.is_supported("http.multiplexing")
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
        """Create or recreate the httpx.AsyncClient with current settings."""
        self.session = httpx.AsyncClient(
            http2=self._http2 or False,
            proxy=self._proxy,
            verify=self._ssl_verify_cert if self._ssl_verify_cert is not None else True,
            cert=self._ssl_cert,
            timeout=self._timeout,
        )

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
        """Close the async client."""
        if hasattr(self, "session"):
            await self.session.aclose()

    @staticmethod
    def _build_method_headers(
        method: str,
        depth: Optional[int] = None,
        extra_headers: Optional[Mapping[str, str]] = None,
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

        log.debug(
            f"sending request - method={method}, url={str(url_obj)}, headers={combined_headers}\nbody:\n{to_normal_str(body)}"
        )

        # Build request kwargs for httpx
        request_kwargs: dict[str, Any] = {
            "method": method,
            "url": str(url_obj),
            "content": to_wire(body) if body else None,
            "headers": combined_headers,
            "auth": self.auth,
            "timeout": self.timeout,
        }

        try:
            r = await self.session.request(**request_kwargs)
            log.debug(f"server responded with {r.status_code} {r.reason_phrase}")
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
                        msg += "\nSupported authentication types: {}".format(
                            ", ".join(auth_types)
                        )
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
                timeout=self.timeout,
            )
            log.debug(
                f"auth type detection: server responded with {r.status_code} {r.reason_phrase}"
            )
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
            and self.password
            is not None  # Empty password OK, but None means not configured
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
            if (
                self.features.is_supported("http.multiplexing", return_defaults=False)
                is None
            ):
                await self.session.aclose()
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
        url: Optional[str] = None,
        body: str = "",
        depth: int = 0,
        headers: Optional[Mapping[str, str]] = None,
        props: Optional[List[str]] = None,
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
            body = build_propfind_body(props).decode("utf-8")

        final_headers = self._build_method_headers("PROPFIND", depth, headers)
        response = await self.request(
            url or str(self.url), "PROPFIND", body, final_headers
        )

        # Parse response using protocol layer
        if response.status in (200, 207) and response._raw:
            raw_bytes = (
                response._raw
                if isinstance(response._raw, bytes)
                else response._raw.encode("utf-8")
            )
            response.results = parse_propfind_response(
                raw_bytes, response.status, response.huge_tree
            )

        return response

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
        final_headers = self._build_method_headers("PROPPATCH", extra_headers=headers)
        return await self.request(url, "PROPPATCH", body, final_headers)

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
        final_headers = self._build_method_headers("MKCOL", extra_headers=headers)
        return await self.request(url, "MKCOL", body, final_headers)

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
        final_headers = self._build_method_headers("MKCALENDAR", extra_headers=headers)
        return await self.request(url, "MKCALENDAR", body, final_headers)

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

    # ==================== High-Level CalDAV Methods ====================
    # These methods use the protocol layer for building XML and parsing responses

    async def calendar_query(
        self,
        url: Optional[str] = None,
        start: Optional[Any] = None,
        end: Optional[Any] = None,
        event: bool = False,
        todo: bool = False,
        journal: bool = False,
        expand: bool = False,
        depth: int = 1,
        headers: Optional[Mapping[str, str]] = None,
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
        from datetime import datetime

        body, _ = build_calendar_query_body(
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
                response._raw
                if isinstance(response._raw, bytes)
                else response._raw.encode("utf-8")
            )
            response.results = parse_calendar_query_response(
                raw_bytes, response.status, response.huge_tree
            )

        return response

    async def calendar_multiget(
        self,
        url: Optional[str] = None,
        hrefs: Optional[List[str]] = None,
        depth: int = 1,
        headers: Optional[Mapping[str, str]] = None,
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
        body = build_calendar_multiget_body(hrefs or [])

        final_headers = self._build_method_headers("REPORT", depth, headers)
        response = await self.request(
            url or str(self.url), "REPORT", body.decode("utf-8"), final_headers
        )

        # Parse response using protocol layer
        if response.status in (200, 207) and response._raw:
            raw_bytes = (
                response._raw
                if isinstance(response._raw, bytes)
                else response._raw.encode("utf-8")
            )
            response.results = parse_calendar_query_response(
                raw_bytes, response.status, response.huge_tree
            )

        return response

    async def sync_collection(
        self,
        url: Optional[str] = None,
        sync_token: Optional[str] = None,
        props: Optional[List[str]] = None,
        depth: int = 1,
        headers: Optional[Mapping[str, str]] = None,
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
        body = build_sync_collection_body(sync_token=sync_token, props=props)

        final_headers = self._build_method_headers("REPORT", depth, headers)
        response = await self.request(
            url or str(self.url), "REPORT", body.decode("utf-8"), final_headers
        )

        # Parse response using protocol layer
        if response.status in (200, 207) and response._raw:
            raw_bytes = (
                response._raw
                if isinstance(response._raw, bytes)
                else response._raw.encode("utf-8")
            )
            sync_result = parse_sync_collection_response(
                raw_bytes, response.status, response.huge_tree
            )
            response.results = sync_result.changed
            response.sync_token = sync_result.sync_token

        return response

    # ==================== Authentication Helpers ====================

    def extract_auth_types(self, header: str) -> set[str]:
        """Extract authentication types from WWW-Authenticate header.

        Delegates to caldav.lib.auth.extract_auth_types().
        """
        return extract_auth_types(header)

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
            self.auth = httpx.DigestAuth(self.username, self.password)
        elif auth_type == "basic":
            self.auth = httpx.BasicAuth(self.username, self.password)
        else:
            raise error.AuthorizationError(f"Unsupported auth type: {auth_type}")


# ==================== Factory Function ====================


async def get_davclient(
    url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    probe: bool = True,
    check_config_file: bool = True,
    config_file: Optional[str] = None,
    config_section: Optional[str] = None,
    testconfig: bool = False,
    environment: bool = True,
    name: Optional[str] = None,
    **kwargs: Any,
) -> AsyncDAVClient:
    """
    Get an async DAV client instance.

    This is the recommended way to create an async DAV client. It supports:
    - Explicit parameters (url=, username=, password=, etc.)
    - Test server config (if testconfig=True or PYTHON_CALDAV_USE_TEST_SERVER env var)
    - Environment variables (CALDAV_URL, CALDAV_USERNAME, CALDAV_PASSWORD)
    - Configuration files (JSON/YAML in ~/.config/caldav/)
    - Connection probing to verify server accessibility

    Args:
        url: CalDAV server URL, domain, or email address.
        username: Username for authentication.
        password: Password for authentication.
        probe: Verify connectivity with OPTIONS request (default: True).
        check_config_file: Whether to look for config files (default: True).
        config_file: Explicit path to config file.
        config_section: Section name in config file (default: "default").
        testconfig: Whether to use test server configuration.
        environment: Whether to read from environment variables (default: True).
        name: Name of test server to use (for testconfig).
        **kwargs: Additional arguments passed to AsyncDAVClient.__init__().

    Returns:
        AsyncDAVClient instance.

    Raises:
        ValueError: If no configuration is found.

    Example:
        async with await get_davclient(url="...", username="...", password="...") as client:
            principal = await AsyncPrincipal.create(client)
    """
    from . import config as config_module

    # Merge explicit url/username/password into kwargs for config lookup
    # Note: Use `is not None` rather than truthiness to allow empty strings
    explicit_params = dict(kwargs)
    if url is not None:
        explicit_params["url"] = url
    if username is not None:
        explicit_params["username"] = username
    if password is not None:
        explicit_params["password"] = password

    # Use unified config discovery
    conn_params = config_module.get_connection_params(
        check_config_file=check_config_file,
        config_file=config_file,
        config_section=config_section,
        testconfig=testconfig,
        environment=environment,
        name=name,
        **explicit_params,
    )

    if conn_params is None:
        raise ValueError(
            "No configuration found. Provide connection parameters, "
            "set CALDAV_URL environment variable, or create a config file."
        )

    # Extract special keys that aren't connection params
    setup_func = conn_params.pop("_setup", None)
    teardown_func = conn_params.pop("_teardown", None)
    server_name = conn_params.pop("_server_name", None)

    # Create client
    client = AsyncDAVClient(**conn_params)

    # Attach test server metadata if present
    if setup_func is not None:
        client.setup = setup_func
    if teardown_func is not None:
        client.teardown = teardown_func
    if server_name is not None:
        client.server_name = server_name

    # Probe connection if requested
    if probe:
        try:
            response = await client.options()
            log.info(f"Connected to CalDAV server: {client.url}")

            # Check for DAV support
            dav_header = response.headers.get("DAV", "")
            if not dav_header:
                log.warning(
                    "Server did not return DAV header - may not be a DAV server"
                )
            else:
                log.debug(f"Server DAV capabilities: {dav_header}")

        except Exception as e:
            await client.close()
            raise error.DAVError(
                f"Failed to connect to CalDAV server at {client.url}: {e}"
            ) from e

    return client
