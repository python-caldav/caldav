"""
Base class for DAV clients.

This module contains the BaseDAVClient class which provides shared
functionality for both sync (DAVClient) and async (AsyncDAVClient) clients.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, NoReturn

from caldav.lib import error
from caldav.lib.auth import extract_auth_types, select_auth_type
from caldav.lib.python_utilities import to_normal_str
from caldav.lib.url import URL

if TYPE_CHECKING:
    from caldav.compatibility_hints import FeatureSet

log = logging.getLogger("caldav")


class BaseDAVClient(ABC):
    """
    Base class for DAV clients providing shared authentication and configuration logic.

    This abstract base class contains common functionality used by both
    DAVClient (sync) and AsyncDAVClient (async). Subclasses must implement
    the abstract methods for their specific HTTP library.

    Shared functionality:
    - Authentication type extraction and selection
    - Feature set management
    - Common properties (username, password, auth_type, etc.)
    """

    # Property lists for PROPFIND requests - shared between sync and async
    CALENDAR_HOME_SET_PROPS = ["{urn:ietf:params:xml:ns:caldav}calendar-home-set"]
    CALENDAR_LIST_PROPS = [
        "{DAV:}resourcetype",
        "{DAV:}displayname",
        "{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set",
        "{http://apple.com/ns/ical/}calendar-color",
        "{http://calendarserver.org/ns/}getctag",
    ]

    # Common attributes that subclasses will set
    username: str | None = None
    password: str | None = None
    auth: Any | None = None
    auth_type: str | None = None
    features: FeatureSet | None = None
    url: Any = None  # URL object, set by subclasses

    def _make_absolute_url(self, url: str) -> str:
        """Make a URL absolute by joining with the client's base URL if needed.

        Args:
            url: URL string, possibly relative (e.g., "/calendars/user/")

        Returns:
            Absolute URL string.
        """
        if url and not url.startswith("http"):
            return str(self.url.join(url))
        return url

    def extract_auth_types(self, header: str) -> set[str]:
        """Extract authentication types from WWW-Authenticate header.

        Parses the WWW-Authenticate header value and extracts the
        authentication scheme names (e.g., "basic", "digest", "bearer").

        Args:
            header: WWW-Authenticate header value from server response.

        Returns:
            Set of lowercase auth type strings.

        Example:
            >>> client.extract_auth_types('Basic realm="test", Digest realm="test"')
            {'basic', 'digest'}
        """
        return extract_auth_types(header)

    def _select_auth_type(self, auth_types: list[str] | None = None) -> str | None:
        """
        Select the best authentication type from available options.

        This method implements the shared logic for choosing an auth type
        based on configured credentials and server-supported types.

        Args:
            auth_types: List of acceptable auth types from server.

        Returns:
            Selected auth type string, or None if no suitable type found.

        Raises:
            AuthorizationError: If configuration conflicts with server capabilities.
        """
        auth_type = self.auth_type

        if not auth_type and not auth_types:
            raise error.AuthorizationError(
                "No auth-type given. This shouldn't happen. "
                "Raise an issue at https://github.com/python-caldav/caldav/issues/"
            )

        if auth_types and auth_type and auth_type not in auth_types:
            raise error.AuthorizationError(
                reason=f"Configuration specifies to use {auth_type}, "
                f"but server only accepts {auth_types}"
            )

        if not auth_type and auth_types:
            # Use shared selection logic from lib/auth
            auth_type = select_auth_type(
                auth_types,
                has_username=bool(self.username),
                has_password=bool(self.password),
            )

            # Handle bearer token without password
            if not auth_type and "bearer" in auth_types and not self.password:
                raise error.AuthorizationError(
                    reason="Server provides bearer auth, but no password given. "
                    "The bearer token should be configured as password"
                )

        return auth_type

    def _prepare_request(
        self,
        url: str,
        method: str,
        body: str,
        headers: Mapping[str, str] | None,
    ) -> tuple[URL, dict]:
        """Combine headers, strip Content-Type for empty bodies, objectify URL, and log.

        Returns:
            (url_obj, combined_headers) ready to pass to the HTTP library.
        """
        headers = headers or {}
        combined_headers = self.headers.copy()
        combined_headers.update(headers)
        if (body is None or body == "") and "Content-Type" in combined_headers:
            del combined_headers["Content-Type"]
        url_obj = URL.objectify(url)
        log.debug(
            f"sending request - method={method}, url={str(url_obj)}, "
            f"headers={combined_headers}\nbody:\n{to_normal_str(body)}"
        )
        return url_obj, combined_headers

    def _should_negotiate_auth(self, status_code: int, headers: Any) -> bool:
        """Return True when a 401 response warrants auth negotiation.

        True when: status is 401, WWW-Authenticate header present, no auth
        object yet, and credentials are configured.
        """
        return (
            status_code == 401
            and "WWW-Authenticate" in headers
            and not self.auth
            and self.username is not None
            and self.password is not None
        )

    def _build_auth_from_401(self, www_authenticate: str) -> None:
        """Build auth object from a WWW-Authenticate header value.

        Raises:
            NotImplementedError: If the server offers no supported auth method.
        """
        auth_types = self.extract_auth_types(www_authenticate)
        self.build_auth_object(auth_types)
        if not self.auth:
            raise NotImplementedError(
                "The server does not provide any of the currently "
                "supported authentication methods: basic, digest, bearer"
            )

    def _raise_authorization_error(self, url_str: str, reason_source: Any) -> NoReturn:
        """Raise AuthorizationError, extracting reason from reason_source.reason."""
        try:
            reason = reason_source.reason
        except AttributeError:
            reason = "None given"
        raise error.AuthorizationError(url=url_str, reason=reason)

    def _build_principal_search_query(self, name: str | None) -> bytes:
        """Build the XML body for a principal-property-search REPORT."""
        from lxml import etree

        from caldav.elements import cdav, dav

        name_filter = (
            [dav.PropertySearch() + [dav.Prop() + [dav.DisplayName()]] + dav.Match(value=name)]
            if name
            else []
        )
        query = (
            dav.PrincipalPropertySearch()
            + name_filter
            + [dav.Prop(), cdav.CalendarHomeSet(), dav.DisplayName()]
        )
        return etree.tostring(query.xmlelement())

    def _parse_principal_search_response(self, principal_dict: dict) -> list:
        """Parse principal-property-search REPORT results into Principal objects."""
        from caldav.collection import CalendarSet, Principal
        from caldav.elements import cdav, dav

        ret = []
        for x in principal_dict:
            p = principal_dict[x]
            if dav.DisplayName.tag not in p:
                continue
            name = p[dav.DisplayName.tag].text
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
                Principal(client=self, url=x, name=name, calendar_home_set=calendar_home_set)
            )
        return ret

    def get_events(self, calendar: Any, start: Any = None, end: Any = None) -> Any:
        """Get events from a calendar, optionally filtered by date range.

        For sync clients returns a list directly.
        For async clients returns a coroutine that must be awaited.
        """
        return self.search_calendar(calendar, event=True, start=start, end=end)

    def get_todos(self, calendar: Any, include_completed: bool = False) -> Any:
        """Get todos from a calendar.

        For sync clients returns a list directly.
        For async clients returns a coroutine that must be awaited.
        """
        return self.search_calendar(calendar, todo=True, include_completed=include_completed)

    @abstractmethod
    def build_auth_object(self, auth_types: list[str] | None = None) -> None:
        """
        Build authentication object based on configured credentials.

        This method must be implemented by subclasses to create the
        appropriate auth object for their HTTP library (requests, httpx, etc.).

        Args:
            auth_types: List of acceptable auth types from server.
        """
        pass


class CalendarCollection(list):
    """
    A list of calendars that can be used as a context manager.

    This class extends list to provide automatic cleanup of the underlying
    DAV client connection when used with a `with` statement.

    Example::

        from caldav import get_calendars

        # As context manager (recommended) - auto-closes connection
        with get_calendars(url="...", username="...", password="...") as calendars:
            for cal in calendars:
                print(cal.get_display_name())

        # Without context manager - must close manually
        calendars = get_calendars(url="...", username="...", password="...")
        # ... use calendars ...
        if calendars:
            calendars[0].client.close()
    """

    def __init__(self, calendars: list | None = None, client: Any = None):
        super().__init__(calendars or [])
        self._client = client

    @property
    def client(self):
        """The underlying DAV client, if available."""
        if self._client:
            return self._client
        # Fall back to getting client from first calendar
        if self:
            return self[0].client
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        """Close the underlying DAV client connection."""
        if self._client:
            self._client.close()
        elif self:
            self[0].client.close()


class CalendarResult:
    """
    A single calendar result that can be used as a context manager.

    This wrapper holds a single Calendar (or None) and provides automatic
    cleanup of the underlying DAV client connection when used with a
    `with` statement.

    Example::

        from caldav import get_calendar

        # As context manager (recommended) - auto-closes connection
        with get_calendar(calendar_name="Work", url="...") as calendar:
            if calendar:
                events = calendar.date_search(start=..., end=...)

        # Without context manager
        result = get_calendar(calendar_name="Work", url="...")
        calendar = result.calendar  # or just use result directly
        # ... use calendar ...
        result.close()
    """

    def __init__(self, calendar: Any = None, client: Any = None):
        self._calendar = calendar
        self._client = client

    @property
    def calendar(self):
        """The calendar, or None if not found."""
        return self._calendar

    @property
    def client(self):
        """The underlying DAV client."""
        if self._client:
            return self._client
        if self._calendar:
            return self._calendar.client
        return None

    def __enter__(self):
        return self._calendar

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        """Close the underlying DAV client connection."""
        client = self.client
        if client:
            client.close()

    # Allow using the result directly as if it were the calendar
    def __bool__(self):
        return self._calendar is not None

    def __getattr__(self, name):
        if self._calendar is None:
            raise AttributeError(f"No calendar found, cannot access '{name}'")
        return getattr(self._calendar, name)


def _normalize_to_list(obj: Any) -> list:
    """Convert a string or None to a list for uniform handling."""
    if not obj:
        return []
    if isinstance(obj, (str, bytes)):
        return [obj]
    return list(obj)


def get_calendars(
    client_class: type,
    calendar_url: Any | None = None,
    calendar_name: Any | None = None,
    check_config_file: bool = True,
    config_file: str | None = None,
    config_section: str | None = None,
    testconfig: bool = False,
    environment: bool = True,
    name: str | None = None,
    raise_errors: bool = False,
    **config_data,
) -> CalendarCollection:
    """
    Get calendars from a CalDAV server with configuration from multiple sources.

    This function creates a client, connects to the server, and returns
    calendar objects based on the specified criteria. Configuration is read
    from various sources (explicit parameters, environment variables, config files).

    The returned CalendarCollection can be used as a context manager to ensure
    the underlying connection is properly closed.

    Args:
        client_class: The client class to use (DAVClient or AsyncDAVClient).
        calendar_url: URL(s) or ID(s) of specific calendars to fetch.
            Can be a string or list of strings. If the value contains '/',
            it's treated as a URL; otherwise as a calendar ID.
        calendar_name: Name(s) of specific calendars to fetch by display name.
            Can be a string or list of strings.
        check_config_file: Whether to look for config files (default: True).
        config_file: Explicit path to config file.
        config_section: Section name in config file (default: "default").
        testconfig: Whether to use test server configuration.
        environment: Whether to read from environment variables (default: True).
        name: Name of test server to use (for testconfig).
        raise_errors: If True, raise exceptions on errors; if False, log and skip.
        **config_data: Connection parameters (url, username, password, etc.)

    Returns:
        CalendarCollection of Calendar objects matching the criteria.
        If no calendar_url or calendar_name specified, returns all calendars.

    Example::

        from caldav import get_calendars

        # As context manager (recommended)
        with get_calendars(url="https://...", username="...", password="...") as calendars:
            for cal in calendars:
                print(cal.get_display_name())

        # Without context manager - connection closed on garbage collection
        calendars = get_calendars(url="https://...", username="...", password="...")
    """
    import logging

    log = logging.getLogger("caldav")

    def _try(meth, kwargs, errmsg):
        """Try a method call, handling errors based on raise_errors flag."""
        try:
            ret = meth(**kwargs)
            if ret is None:
                raise ValueError(f"Method returned None: {errmsg}")
            return ret
        except Exception as e:
            log.error(f"Problems fetching calendar information: {errmsg} - {e}")
            if raise_errors:
                raise
            return None

    # Get client using existing config infrastructure
    client = get_davclient(
        client_class=client_class,
        check_config_file=check_config_file,
        config_file=config_file,
        config_section=config_section,
        testconfig=testconfig,
        environment=environment,
        name=name,
        **config_data,
    )

    if client is None:
        if raise_errors:
            raise ValueError("Could not create DAV client - no configuration found")
        return CalendarCollection()

    # Get principal
    principal = _try(client.principal, {}, "getting principal")
    if not principal:
        return CalendarCollection(client=client)

    calendars = []
    calendar_urls = _normalize_to_list(calendar_url)
    calendar_names = _normalize_to_list(calendar_name)

    # Fetch specific calendars by URL/ID
    for cal_url in calendar_urls:
        if "/" in str(cal_url):
            calendar = principal.calendar(cal_url=cal_url)
        else:
            calendar = principal.calendar(cal_id=cal_url)

        # Verify the calendar exists by trying to get its display name
        if _try(calendar.get_display_name, {}, f"calendar {cal_url}"):
            calendars.append(calendar)

    # Fetch specific calendars by name
    for cal_name in calendar_names:
        calendar = _try(
            principal.calendar,
            {"name": cal_name},
            f"calendar by name '{cal_name}'",
        )
        if calendar:
            calendars.append(calendar)

    # If no specific calendars requested, get all calendars
    if not calendars and not calendar_urls and not calendar_names:
        all_cals = _try(principal.get_calendars, {}, "getting all calendars")
        if all_cals:
            calendars = all_cals

    return CalendarCollection(calendars, client=client)


def get_davclient(
    client_class: type,
    check_config_file: bool = True,
    config_file: str | None = None,
    config_section: str | None = None,
    testconfig: bool = False,
    environment: bool = True,
    name: str | None = None,
    **config_data,
) -> Any | None:
    """
    Get a DAV client instance with configuration from multiple sources.

    This is the canonical implementation used by both sync and async clients.
    Configuration is read from various sources in priority order:

    1. Explicit parameters (url=, username=, password=, etc.)
    2. Test server config (if testconfig=True or PYTHON_CALDAV_USE_TEST_SERVER env var)
    3. Environment variables (CALDAV_URL, CALDAV_USERNAME, CALDAV_PASSWORD)
    4. Config file (CALDAV_CONFIG_FILE env var or ~/.config/caldav/)

    Args:
        client_class: The client class to instantiate (DAVClient or AsyncDAVClient).
        check_config_file: Whether to look for config files (default: True).
        config_file: Explicit path to config file.
        config_section: Section name in config file (default: "default").
        testconfig: Whether to use test server configuration.
        environment: Whether to read from environment variables (default: True).
        name: Name of test server to use (for testconfig).
        **config_data: Explicit connection parameters passed to client constructor.
            Common parameters include:
            - url: CalDAV server URL, domain, or email address
            - username: Username for authentication
            - password: Password for authentication
            - ssl_verify_cert: Whether to verify SSL certificates
            - auth_type: Authentication type ("basic", "digest", "bearer")

    Returns:
        Client instance, or None if no configuration is found.

    Example (sync)::

        from caldav import get_davclient
        client = get_davclient(url="https://caldav.example.com", username="user", password="pass")

    Example (async)::

        from caldav.async_davclient import get_davclient
        client = await get_davclient(url="https://caldav.example.com", username="user", password="pass")
    """
    from caldav import config

    # Use unified config discovery
    conn_params = config.get_connection_params(
        check_config_file=check_config_file,
        config_file=config_file,
        config_section=config_section,
        testconfig=testconfig,
        environment=environment,
        name=name,
        **config_data,
    )

    if conn_params is None:
        return None

    # Extract special keys that aren't connection params
    setup_func = conn_params.pop("_setup", None)
    teardown_func = conn_params.pop("_teardown", None)
    server_name = conn_params.pop("_server_name", None)
    # Remove protocol field — present when config file has both CalDAV and JMAP sections,
    # or when the caller passes protocol="jmap"/"caldav". DAVClient doesn't accept it.
    conn_params.pop("protocol", None)

    # Create client
    client = client_class(**conn_params)

    # Attach test server metadata if present
    if setup_func is not None:
        client.setup = setup_func
    if teardown_func is not None:
        client.teardown = teardown_func
    if server_name is not None:
        client.server_name = server_name

    return client
