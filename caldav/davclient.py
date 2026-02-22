#!/usr/bin/env python
"""
Sync CalDAV client using niquests or requests library.

This module provides the traditional synchronous API with protocol layer
for XML building and response parsing.

For async code, use: from caldav import aio
"""

import logging
import sys
import warnings
from types import TracebackType
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import unquote
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

# Try niquests first (preferred), fall back to requests
_USE_NIQUESTS = False
_USE_REQUESTS = False

try:
    import niquests as requests
    from niquests.auth import AuthBase
    from niquests.models import Response
    from niquests.structures import CaseInsensitiveDict

    _USE_NIQUESTS = True
except ImportError:
    import requests
    from requests.auth import AuthBase
    from requests.models import Response
    from requests.structures import CaseInsensitiveDict

    _USE_REQUESTS = True

from collections.abc import Mapping

from lxml import etree

import caldav.compatibility_hints
from caldav import __version__
from caldav.base_client import BaseDAVClient
from caldav.base_client import get_calendars as _base_get_calendars
from caldav.base_client import get_davclient as _base_get_davclient
from caldav.collection import Calendar, CalendarSet, Principal
from caldav.compatibility_hints import FeatureSet

# Re-export CONNKEYS for backward compatibility
from caldav.config import CONNKEYS  # noqa: F401
from caldav.elements import cdav, dav
from caldav.lib import error
from caldav.lib.python_utilities import to_normal_str, to_wire
from caldav.lib.url import URL
from caldav.objects import log
from caldav.requests import HTTPBearerAuth
from caldav.response import BaseDAVResponse

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

if TYPE_CHECKING:
    from caldav.calendarobjectresource import CalendarObjectResource, Event, Todo


"""
The ``DAVClient`` class handles the basic communication with a
CalDAV server.  In 1.x the recommended usage of the library is to
start constructing a DAVClient object.  In 2.0 the function
``get_davclient`` was added as the new recommended way to get a
DAVClient object.  In later versions there may be a ``get_calendar``,
eliminating the need to deal with DAVClient for most use cases.

The ``DAVResponse`` class handles the data returned from the server.
In most use-cases library users will not interface with this class
directly.

``get_davclient`` will return a DAVClient object, based either on
environmental variables, a configuration file or test configuration.
"""

## TODO: this is also declared in davclient.DAVClient.__init__(...)
# Import CONNKEYS from config to avoid duplication


def _auto_url(
    url,
    features,
    timeout=10,
    ssl_verify_cert=True,
    enable_rfc6764=True,
    username=None,
    require_tls=True,
):
    """
    Auto-construct URL from domain and features, with optional RFC6764 discovery.

    Args:
        url: User-provided URL, domain, or email address
        features: FeatureSet object or dict
        timeout: Timeout for RFC6764 well-known URI lookups
        ssl_verify_cert: SSL verification setting
        enable_rfc6764: Whether to attempt RFC6764 discovery
        username: Username to use for discovery if URL is not provided
        require_tls: Only accept TLS connections during discovery (default: True)

    Returns:
        A tuple of (url_string, discovered_username_or_None)
        The discovered_username will be extracted from email addresses like user@example.com
    """
    if isinstance(features, dict):
        features = FeatureSet(features)

    # If URL already has a path component, don't do discovery
    if url and "/" in str(url):
        return (url, None)

    # If no URL provided but username contains @, use username for discovery
    if not url and username and "@" in str(username) and enable_rfc6764:
        log.debug(f"No URL provided, using username for RFC6764 discovery: {username}")
        url = username

    # Try RFC6764 discovery first if enabled and we have a bare domain/email
    if enable_rfc6764 and url:
        from caldav.discovery import DiscoveryError, discover_caldav

        try:
            service_info = discover_caldav(
                identifier=url,
                timeout=timeout,
                ssl_verify_cert=ssl_verify_cert if isinstance(ssl_verify_cert, bool) else True,
                require_tls=require_tls,
            )
            if service_info:
                log.info(
                    f"RFC6764 discovered service: {service_info.url} (source: {service_info.source})"
                )
                if service_info.username:
                    log.debug(f"Username discovered from email: {service_info.username}")
                return (service_info.url, service_info.username)
        except DiscoveryError as e:
            log.debug(f"RFC6764 discovery failed: {e}")
        except Exception as e:
            log.debug(f"RFC6764 discovery error: {e}")

    # Fall back to feature-based URL construction
    url_hints = features.is_supported("auto-connect.url", dict)
    # If URL is still empty or looks like an email (from failed discovery attempt),
    # replace it with the domain from hints
    if (not url or (url and "@" in str(url))) and "domain" in url_hints:
        url = url_hints["domain"]
    url = f"{url_hints.get('scheme', 'https')}://{url}{url_hints.get('basepath', '')}"
    return (url, None)


class DAVResponse(BaseDAVResponse):
    """
    This class is a response from a DAV request.  It is instantiated from
    the DAVClient class.  End users of the library should not need to
    know anything about this class.  Since we often get XML responses,
    it tries to parse it into `self.tree`
    """

    # Protocol-layer parsed results (new interface, replaces find_objects_and_props())
    results: list | None = None
    sync_token: str | None = None

    def __init__(
        self,
        response: Response,
        davclient: Optional["DAVClient"] = None,
    ) -> None:
        self._init_from_response(response, davclient)

    # Response parsing methods are inherited from BaseDAVResponse


class DAVClient(BaseDAVClient):
    """
    Basic client for webdav, uses the niquests lib; gives access to
    low-level operations towards the caldav server.

    Unless you have special needs, you should probably care most about
    the constructor (__init__), the principal method and the calendar method.
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
        auth: AuthBase | None = None,
        auth_type: str | None = None,
        timeout: int | None = None,
        ssl_verify_cert: bool | str = True,
        ssl_cert: str | tuple[str, str] | None = None,
        headers: Mapping[str, str] = None,
        huge_tree: bool = False,
        features: FeatureSet | dict | str = None,
        enable_rfc6764: bool = True,
        require_tls: bool = True,
    ) -> None:
        """
        Sets up a HTTPConnection object towards the server in the url.

        Args:
          url: A fully qualified url, domain name, or email address. Can be omitted if username
               is an email address (RFC6764 discovery will use the username).
               Examples:
               - Full URL: `https://caldav.example.com/dav/`
               - Domain: `example.com` (will attempt RFC6764 discovery if enable_rfc6764=True)
               - Email: `user@example.com` (will attempt RFC6764 discovery if enable_rfc6764=True)
               - URL with auth: `scheme://user:pass@hostname:port`
               - Omit URL: Use `username='user@example.com'` for discovery
          username: Username for authentication. If url is omitted and username contains @,
                    RFC6764 discovery will be attempted using the username as email address.
          proxy: A string defining a proxy server: `scheme://hostname:port`. Scheme defaults to http, port defaults to 8080.
          auth: A niquests.auth.AuthBase or requests.auth.AuthBase object, may be passed instead of username/password.  username and password should be passed as arguments or in the URL
          timeout and ssl_verify_cert are passed to niquests.request.
          if auth_type is given, the auth-object will be auto-created. Auth_type can be ``bearer``, ``digest`` or ``basic``. Things are likely to work without ``auth_type`` set, but if nothing else the number of requests to the server will be reduced, and some servers may require this to squelch warnings of unexpected HTML delivered from the
           server etc.
          ssl_verify_cert can be the path of a CA-bundle or False.
          huge_tree: boolean, enable XMLParser huge_tree to handle big events, beware of security issues, see : https://lxml.de/api/lxml.etree.XMLParser-class.html
          features: The default, None, will in version 2.x enable all existing workarounds in the code for backward compability.  Otherwise it will expect a FeatureSet or a dict as defined in `caldav.compatibility_hints` and use that to figure out what workarounds are needed.
          enable_rfc6764: boolean, enable RFC6764 DNS-based service discovery for CalDAV/CardDAV.
                          Default: True. When enabled and a domain or email address is provided as url,
                          the library will attempt to discover the CalDAV service using:
                          1. DNS SRV records (_caldavs._tcp / _caldav._tcp)
                          2. DNS TXT records for path information
                          3. Well-Known URIs (/.well-known/caldav)
                          Set to False to disable automatic discovery and rely only on feature hints.
                          SECURITY: See require_tls parameter for security considerations.
          require_tls: boolean, require TLS (HTTPS) for discovered services. Default: True.
                       When True, RFC6764 discovery will ONLY accept HTTPS connections,
                       preventing DNS-based downgrade attacks where malicious DNS could
                       redirect to unencrypted HTTP. Set to False ONLY if you need to
                       support non-TLS servers and trust your DNS infrastructure.
                       This parameter has no effect if enable_rfc6764=False.

        The niquests library will honor a .netrc-file, if such a file exists
        username and password may be omitted.

        THe niquest library will honor standard proxy environmental variables like
        HTTP_PROXY, HTTPS_PROXY and ALL_PROXY.  See https://niquests.readthedocs.io/en/latest/user/advanced.html#proxies

        If the caldav server is behind a proxy or replies with html instead of xml
        when returning 401, warnings will be printed which might be unwanted.
        Check auth parameter for details.
        """
        headers = headers or {}

        ## Deprecation TODO: give a warning, user should use get_davclient or auto_calendar instead.  Probably.

        if isinstance(features, str):
            features = getattr(caldav.compatibility_hints, features)
        self.features = FeatureSet(features)
        self.huge_tree = huge_tree

        try:
            multiplexed = self.features.is_supported("http.multiplexing")
            self.session = requests.Session(multiplexed=multiplexed)
        except TypeError:
            self.session = requests.Session()

        url, discovered_username = _auto_url(
            url,
            self.features,
            timeout=timeout or 10,
            ssl_verify_cert=ssl_verify_cert,
            enable_rfc6764=enable_rfc6764,
            username=username,
            require_tls=require_tls,
        )

        log.debug("url: " + str(url))
        self.url = URL.objectify(url)
        # Prepare proxy info
        if proxy is not None:
            _proxy = proxy
            # niquests library expects the proxy url to have a scheme
            if "://" not in proxy:
                _proxy = self.url.scheme + "://" + proxy

            # add a port is one is not specified
            # TODO: this will break if using basic auth and embedding
            # username:password in the proxy URL
            p = _proxy.split(":")
            if len(p) == 2:
                _proxy += ":8080"
            log.debug("init - proxy: %s" % (_proxy))

            self.proxy = _proxy

        # Build global headers
        self.headers = CaseInsensitiveDict(
            {
                "User-Agent": "python-caldav/" + __version__,
                "Content-Type": "text/xml",
                "Accept": "text/xml, text/calendar",
            }
        )
        self.headers.update(headers or {})
        if self.url.username is not None:
            username = unquote(self.url.username)
            password = unquote(self.url.password)

        # Use discovered username if no explicit username was provided
        if username is None and discovered_username is not None:
            username = discovered_username
            log.debug(f"Using discovered username from RFC6764: {username}")

        self.username = username
        self.password = password
        self.auth = auth
        self.auth_type = auth_type

        ## I had problems with passwords with non-ascii letters in it ...
        if isinstance(self.password, str):
            self.password = self.password.encode("utf-8")
        if auth and self.auth_type:
            logging.error(
                "both auth object and auth_type sent to DAVClient.  The latter will be ignored."
            )
        elif self.auth_type:
            self.build_auth_object()

        # TODO: it's possible to force through a specific auth method here,
        # but no test code for this.
        self.timeout = timeout
        self.ssl_verify_cert = ssl_verify_cert
        self.ssl_cert = ssl_cert
        self.url = self.url.unauth()
        log.debug("self.url: " + str(url))

        self._principal = None

    def __enter__(self) -> Self:
        ## Used for tests, to set up a temporarily test server
        if hasattr(self, "setup"):
            try:
                self.setup()
            except TypeError:
                self.setup(self)
        return self

    def __exit__(
        self,
        exc_type: BaseException | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        self.close()
        ## Used for tests, to tear down a temporarily test server
        if hasattr(self, "teardown"):
            try:
                self.teardown()
            except:
                self.teardown(self)

    def close(self) -> None:
        """
        Closes the DAVClient's session object.
        """
        self.session.close()

    def search_principals(self, name=None):
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
        response = self.report(self.url, etree.tostring(query.xmlelement()))

        ## Possibly we should follow redirects (response status 3xx), but as
        ## for now we're just treating it in the same way as 4xx and 5xx -
        ## probably the server did not support the operation
        if response.status >= 300:
            raise error.ReportError(f"{response.status} {response.reason} - {response.raw}")

        principal_dict = response._find_objects_and_props()
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

    def principals(self, name=None):
        """
        Deprecated. Use :meth:`search_principals` instead.

        This method searches for principals on the server.
        """
        warnings.warn(
            "principals() is deprecated, use search_principals() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.search_principals(name=name)

    def principal(self, *largs, **kwargs):
        """
        Legacy method. Use :meth:`get_principal` for new code.

        Convenience method, it gives a bit more object-oriented feel to
        write client.principal() than Principal(client).

        This method returns a :class:`caldav.Principal` object, with
        higher-level methods for dealing with the principals
        calendars.
        """
        if not self._principal:
            self._principal = Principal(client=self, *largs, **kwargs)
        return self._principal

    def calendar(self, **kwargs):
        """Returns a calendar object.

        Typically, a URL should be given as a named parameter (url)

        No network traffic will be initiated by this method.

        If you don't know the URL of the calendar, use
        client.principal().calendar(...) instead, or
        client.principal().get_calendars()
        """
        return Calendar(client=self, **kwargs)

    # ==================== High-Level Methods ====================
    # These methods mirror the async API for consistency.

    def get_principal(self) -> Principal:
        """Get the principal (user) for this CalDAV connection.

        This is the recommended method for new code. It provides API
        consistency between sync and async clients.

        Returns:
            Principal object for the authenticated user.

        Example::

            principal = client.get_principal()
            calendars = principal.get_calendars()
        """
        return self.principal()

    def get_calendars(self, principal: Principal | None = None) -> list[Calendar]:
        """Get all calendars for the given principal.

        This method fetches calendars from the principal's calendar-home-set
        and returns a list of Calendar objects.

        Args:
            principal: Principal object (if None, fetches principal first)

        Returns:
            List of Calendar objects.

        Example:
            principal = client.get_principal()
            calendars = client.get_calendars(principal)
            for cal in calendars:
                print(f"Calendar: {cal.name}")
        """
        from caldav.operations.calendarset_ops import (
            _extract_calendars_from_propfind_results as extract_calendars,
        )

        if principal is None:
            principal = self.principal()

        # Get calendar-home-set from principal
        calendar_home_url = self._get_calendar_home_set(principal)
        if not calendar_home_url:
            return []

        # Make URL absolute if relative
        calendar_home_url = self._make_absolute_url(calendar_home_url)

        # Fetch calendars via PROPFIND
        response = self.propfind(
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

    def _get_calendar_home_set(self, principal: Principal) -> str | None:
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
        response = self.propfind(
            str(principal.url),
            props=self.CALENDAR_HOME_SET_PROPS,
            depth=0,
        )

        return extract_home_set(response.results)

    def get_events(
        self,
        calendar: Calendar,
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
            events = client.get_events(
                calendar,
                start=datetime(2024, 1, 1),
                end=datetime(2024, 12, 31)
            )
        """
        return self.search_calendar(calendar, event=True, start=start, end=end)

    def get_todos(
        self,
        calendar: Calendar,
        include_completed: bool = False,
    ) -> list["Todo"]:
        """Get todos from a calendar.

        Args:
            calendar: Calendar to search
            include_completed: Whether to include completed todos

        Returns:
            List of Todo objects.
        """
        return self.search_calendar(calendar, todo=True, include_completed=include_completed)

    def search_calendar(
        self,
        calendar: Calendar,
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

        This method provides a clean interface to calendar search.

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
            events = client.search_calendar(
                calendar,
                event=True,
                start=datetime(2024, 1, 1),
                end=datetime(2024, 1, 31),
            )
        """
        return calendar.search(
            event=event,
            todo=todo,
            journal=journal,
            start=start,
            end=end,
            include_completed=include_completed,
            expand=expand,
            **kwargs,
        )

    def check_dav_support(self) -> str | None:
        """
        Legacy method. Use :meth:`supports_dav` for new code.

        Does a probe towards the server and returns the DAV header if it
        says it supports RFC4918 / DAV, or None otherwise.
        """
        try:
            ## SOGo does not return the full capability list on the caldav
            ## root URL, and that's OK according to the RFC ... so apparently
            ## we need to do an extra step here to fetch the URL of some
            ## element that should come with caldav extras.
            ## Anyway, packing this into a try-except in case it fails.
            response = self.options(self.principal().url)
        except:
            response = self.options(str(self.url))
        return response.headers.get("DAV", None)

    def check_cdav_support(self) -> bool:
        """
        Legacy method. Use :meth:`supports_caldav` for new code.

        Does a probe towards the server and returns True if it says it
        supports RFC4791 / CalDAV.
        """
        support_list = self.check_dav_support()
        return support_list is not None and "calendar-access" in support_list

    def check_scheduling_support(self) -> bool:
        """
        Legacy method. Use :meth:`supports_scheduling` for new code.

        Does a probe towards the server and returns True if it says it
        supports RFC6638 / CalDAV Scheduling.
        """
        support_list = self.check_dav_support()
        return support_list is not None and "calendar-auto-schedule" in support_list

    # Recommended methods for capability checks (API consistency with AsyncDAVClient)

    def supports_dav(self) -> str | None:
        """Check if the server supports WebDAV (RFC4918).

        This is the recommended method for new code. It provides API
        consistency between sync and async clients.

        Returns:
            The DAV header value if supported, None otherwise.

        Example::

            if client.supports_dav():
                print("Server supports WebDAV")
        """
        return self.check_dav_support()

    def supports_caldav(self) -> bool:
        """Check if the server supports CalDAV (RFC4791).

        This is the recommended method for new code. It provides API
        consistency between sync and async clients.

        Returns:
            True if the server supports CalDAV, False otherwise.

        Example::

            if client.supports_caldav():
                calendars = client.get_calendars()
        """
        return self.check_cdav_support()

    def supports_scheduling(self) -> bool:
        """Check if the server supports CalDAV Scheduling (RFC6638).

        This is the recommended method for new code. It provides API
        consistency between sync and async clients.

        Returns:
            True if the server supports CalDAV Scheduling, False otherwise.

        Example::

            if client.supports_scheduling():
                # Server supports free-busy lookups and scheduling
                pass
        """
        return self.check_scheduling_support()

    def propfind(
        self,
        url: str | None = None,
        props=None,
        depth: int = 0,
    ) -> DAVResponse:
        """
        Send a propfind request.

        Parameters
        ----------
        url : URL
            url for the root of the propfind.
        props : str or List[str]
            XML body string (old interface) or list of property names (new interface).
        depth : int
            maximum recursion depth

        Returns
        -------
        DAVResponse
        """
        from caldav.protocol.xml_builders import _build_propfind_body

        # Handle both old interface (props=xml_string) and new interface (props=list)
        body = ""
        if props is not None:
            if isinstance(props, list):
                body = _build_propfind_body(props).decode("utf-8")
            else:
                body = props  # Old interface: props is XML string

        # Use sync path with protocol layer parsing
        headers = {"Depth": str(depth)}
        response = self.request(url or str(self.url), "PROPFIND", body, headers)

        # Parse response using protocol layer
        if response.status in (200, 207) and response._raw:
            from caldav.protocol.xml_parsers import _parse_propfind_response

            raw_bytes = (
                response._raw if isinstance(response._raw, bytes) else response._raw.encode("utf-8")
            )
            response.results = _parse_propfind_response(
                raw_bytes, response.status, response.huge_tree
            )
        return response

    def proppatch(self, url: str, body: str, dummy: None = None) -> DAVResponse:
        """
        Send a proppatch request.

        Args:
            url: url for the root of the propfind.
            body: XML propertyupdate request
            dummy: compatibility parameter

        Returns:
            DAVResponse
        """
        return self.request(url, "PROPPATCH", body)

    def report(self, url: str, query: str = "", depth: int | None = 0) -> DAVResponse:
        """
        Send a report request.

        Args:
            url: url for the root of the propfind.
            query: XML request
            depth: maximum recursion depth. None means don't send Depth header
                (required for calendar-multiget per RFC 4791 section 7.9).

        Returns
            DAVResponse
        """
        headers = {"Depth": str(depth)} if depth is not None else {}
        return self.request(url, "REPORT", query, headers)

    def mkcol(self, url: str, body: str, dummy: None = None) -> DAVResponse:
        """
        Send a MKCOL request.

        MKCOL is basically not used with caldav, one should use
        MKCALENDAR instead.  However, some calendar servers MAY allow
        "subcollections" to be made in a calendar, by using the MKCOL
        query.  As for 2020-05, this method is not exercised by test
        code or referenced anywhere else in the caldav library, it's
        included just for the sake of completeness.  And, perhaps this
        DAVClient class can be used for vCards and other WebDAV
        purposes.

        Args:
            url: url for the root of the mkcol
            body: XML request
            dummy: compatibility parameter

        Returns:
            DAVResponse
        """
        return self.request(url, "MKCOL", body)

    def mkcalendar(self, url: str, body: str = "", dummy: None = None) -> DAVResponse:
        """
        Send a mkcalendar request.

        Args:
            url: url for the root of the mkcalendar
            body: XML request
            dummy: compatibility parameter

        Returns:
            DAVResponse
        """
        return self.request(url, "MKCALENDAR", body)

    def put(self, url: str, body: str, headers: Mapping[str, str] = None) -> DAVResponse:
        """
        Send a put request.
        """
        return self.request(url, "PUT", body, headers)

    def post(self, url: str, body: str, headers: Mapping[str, str] = None) -> DAVResponse:
        """
        Send a POST request.
        """
        return self.request(url, "POST", body, headers)

    def delete(self, url: str) -> DAVResponse:
        """
        Send a delete request.
        """
        return self.request(url, "DELETE", "")

    def options(self, url: str) -> DAVResponse:
        """
        Send an options request.
        """
        return self.request(url, "OPTIONS", "")

    def build_auth_object(self, auth_types: list[str] | None = None) -> None:
        """Build authentication object for the requests/niquests library.

        Uses shared auth type selection logic from BaseDAVClient, then
        creates the appropriate auth object for this HTTP library.

        Args:
            auth_types: List of acceptable auth types from server.
        """
        # Use shared selection logic
        auth_type = self._select_auth_type(auth_types)

        # Decode password if it's bytes (HTTPDigestAuth needs string)
        password = self.password
        if isinstance(password, bytes):
            password = password.decode("utf-8")

        # Create auth object for requests/niquests
        if auth_type == "digest":
            self.auth = requests.auth.HTTPDigestAuth(self.username, password)
        elif auth_type == "basic":
            self.auth = requests.auth.HTTPBasicAuth(self.username, password)
        elif auth_type == "bearer":
            self.auth = HTTPBearerAuth(password)

    def request(
        self,
        url: str,
        method: str = "GET",
        body: str = "",
        headers: Mapping[str, str] = None,
    ) -> DAVResponse:
        """
        Send a generic HTTP request.

        Uses the sync session directly for all operations.

        Args:
            url: The URL to request
            method: HTTP method (GET, PUT, DELETE, etc.)
            body: Request body
            headers: Optional headers dict

        Returns:
            DAVResponse
        """
        return self._sync_request(url, method, body, headers)

    def _sync_request(
        self,
        url: str,
        method: str = "GET",
        body: str = "",
        headers: Mapping[str, str] = None,
    ) -> DAVResponse:
        """
        Sync HTTP request implementation with auth negotiation.
        """
        headers = headers or {}

        combined_headers = self.headers.copy()
        combined_headers.update(headers or {})
        if (body is None or body == "") and "Content-Type" in combined_headers:
            del combined_headers["Content-Type"]

        # objectify the url
        url_obj = URL.objectify(url)

        proxies = None
        if self.proxy is not None:
            proxies = {url_obj.scheme: self.proxy}
            log.debug("using proxy - %s" % (proxies))

        log.debug(
            f"sending request - method={method}, url={str(url_obj)}, headers={combined_headers}\nbody:\n{to_normal_str(body)}"
        )

        r = self.session.request(
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

        r_headers = CaseInsensitiveDict(r.headers)

        # Handle 429, 503 responses for retry negotiation
        if r.status_code in (429, 503) and "Retry-After" in r_headers:
            retry_after = r_headers["Retry-After"]
            if retry_after:
                try:
                    retry_seconds = int(retry_after)
                except ValueError:
                    try:
                        retry_date = parsedate_to_datetime(retry_after)
                        now = datetime.now(timezone.utc)
                        retry_seconds = max(0, (retry_date - now).total_seconds())
                    except:
                        retry_seconds = None

                raise error.RateLimitError(
                    f"Rate limited or service unavailable. Retry after: {retry_after}",
                    retry_after=retry_after,
                    retry_after_seconds=retry_seconds,
                )

        # Handle 401 responses for auth negotiation
        if (
            r.status_code == 401
            and "WWW-Authenticate" in r_headers
            and not self.auth
            and self.username is not None
            and self.password is not None  # Empty password OK, but None means not configured
        ):
            auth_types = self.extract_auth_types(r_headers["WWW-Authenticate"])
            self.build_auth_object(auth_types)

            if not self.auth:
                raise NotImplementedError(
                    "The server does not provide any of the currently "
                    "supported authentication methods: basic, digest, bearer"
                )

            # Retry request with authentication
            return self._sync_request(url, method, body, headers)

        # Raise AuthorizationError for 401/403 after auth attempt
        if r.status_code in (401, 403):
            try:
                reason = r.reason
            except AttributeError:
                reason = "None given"
            raise error.AuthorizationError(url=str(url_obj), reason=reason)

        response = DAVResponse(r, self)
        return response


def get_calendars(**kwargs) -> list["Calendar"]:
    """
    Get calendars from a CalDAV server with configuration from multiple sources.

    This is a convenience wrapper around :func:`caldav.base_client.get_calendars`
    that uses DAVClient.

    Args:
        calendar_url: URL(s) or ID(s) of specific calendars to fetch.
        calendar_name: Name(s) of specific calendars to fetch by display name.
        check_config_file: Whether to look for config files (default: True).
        config_file: Explicit path to config file.
        config_section: Section name in config file.
        testconfig: Whether to use test server configuration.
        environment: Whether to read from environment variables (default: True).
        name: Name of test server to use (for testconfig).
        raise_errors: If True, raise exceptions on errors; if False, log and skip.
        **config_data: Connection parameters (url, username, password, etc.)

    Returns:
        List of Calendar objects matching the criteria.

    Example::

        from caldav import get_calendars

        # Get all calendars
        calendars = get_calendars(url="https://...", username="...", password="...")

        # Get specific calendar by name
        calendars = get_calendars(calendar_name="Work", url="...", ...)
    """
    return _base_get_calendars(DAVClient, **kwargs)


def get_calendar(**kwargs) -> Optional["Calendar"]:
    """
    Get a single calendar from a CalDAV server.

    This is a convenience function for the common case where only one
    calendar is needed. It returns the first matching calendar or None.

    Args:
        Same as :func:`get_calendars`.

    Returns:
        A single Calendar object, or None if no calendars found.

    Example::

        from caldav import get_calendar

        calendar = get_calendar(calendar_name="Work", url="...", ...)
        if calendar:
            events = calendar.get_events()
    """
    calendars = _base_get_calendars(DAVClient, **kwargs)
    return calendars[0] if calendars else None


def get_davclient(**kwargs) -> Optional["DAVClient"]:
    """
    Get a DAVClient instance with configuration from multiple sources.

    See :func:`caldav.base_client.get_davclient` for full documentation.

    Returns:
        DAVClient instance, or None if no configuration is found.
    """
    return _base_get_davclient(DAVClient, **kwargs)
