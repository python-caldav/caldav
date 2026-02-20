"""
Synchronous JMAP client.

Wraps session establishment, HTTP communication, and method dispatching
into a single object with a clean public API.

Auth note: JMAP has no 401-challenge-retry dance (unlike CalDAV).
Credentials are sent upfront on every request. A 401/403 is a hard failure.
"""

from __future__ import annotations

import logging

try:
    import niquests as requests
    from niquests.auth import HTTPBasicAuth
except ImportError:
    import requests  # type: ignore[no-redef]
    from requests.auth import HTTPBasicAuth  # type: ignore[no-redef]

from caldav.jmap.constants import CALENDAR_CAPABILITY, CORE_CAPABILITY
from caldav.jmap.error import JMAPAuthError, JMAPMethodError
from caldav.jmap.methods.calendar import build_calendar_get, parse_calendar_get
from caldav.jmap.objects.calendar import JMAPCalendar
from caldav.jmap.session import Session, fetch_session
from caldav.requests import HTTPBearerAuth

log = logging.getLogger("caldav.jmap")

# Default capabilities declared in every API request
_DEFAULT_USING = [CORE_CAPABILITY, CALENDAR_CAPABILITY]


class JMAPClient:
    """Synchronous JMAP client for calendar operations.

    Usage::

        from caldav.jmap import get_jmap_client
        client = get_jmap_client(url="https://jmap.example.com/.well-known/jmap",
                                  username="alice", password="secret")
        calendars = client.get_calendars()

    Args:
        url: URL of the JMAP session endpoint (``/.well-known/jmap``).
        username: Username for Basic auth.
        password: Password for Basic auth, or bearer token if no username.
        auth: A pre-built requests-compatible auth object. Takes precedence
              over username/password if provided.
        auth_type: Force a specific auth type: ``"basic"`` or ``"bearer"``.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        url: str,
        username: str | None = None,
        password: str | None = None,
        auth=None,
        auth_type: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.url = url
        self.username = username
        self.password = password
        self.timeout = timeout
        self._session_cache: Session | None = None

        if auth is not None:
            self._auth = auth
        else:
            self._auth = self._build_auth(auth_type)

    def __enter__(self) -> JMAPClient:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    def _build_auth(self, auth_type: str | None):
        """Select and construct the auth object.

        JMAP supports Basic and Bearer auth; Digest is not supported.
        When ``auth_type`` is ``None`` the type is inferred from the
        credentials supplied: a username triggers Basic, a password
        alone triggers Bearer, and neither raises :class:`JMAPAuthError`.
        """
        effective_type = auth_type
        if effective_type is None:
            if self.username:
                effective_type = "basic"
            elif self.password:
                effective_type = "bearer"
            else:
                raise JMAPAuthError(
                    url=self.url,
                    reason="No credentials provided. Supply username+password or a bearer token.",
                )

        if effective_type == "basic":
            if not self.username or not self.password:
                raise JMAPAuthError(
                    url=self.url,
                    reason="Basic auth requires both username and password.",
                )
            return HTTPBasicAuth(self.username, self.password)
        elif effective_type == "bearer":
            if not self.password:
                raise JMAPAuthError(
                    url=self.url,
                    reason="Bearer auth requires a token supplied as the password argument.",
                )
            return HTTPBearerAuth(self.password)
        else:
            raise JMAPAuthError(
                url=self.url,
                reason=f"Unsupported auth_type {effective_type!r}. Use 'basic' or 'bearer'.",
            )

    def _get_session(self) -> Session:
        """Return the cached Session, fetching it on first call."""
        if self._session_cache is None:
            self._session_cache = fetch_session(self.url, auth=self._auth)
        return self._session_cache

    def _request(self, method_calls: list[tuple]) -> list:
        """POST a batch of JMAP method calls and return the methodResponses.

        Args:
            method_calls: List of 3-tuples ``(method_name, args_dict, call_id)``.

        Returns:
            List of 3-tuples ``(method_name, response_args, call_id)`` from
            the server's ``methodResponses`` array.

        Raises:
            JMAPAuthError: On HTTP 401 or 403.
            JMAPMethodError: If any methodResponse is an ``error`` response.
            requests.HTTPError: On other non-2xx HTTP responses.
        """
        session = self._get_session()

        payload = {
            "using": _DEFAULT_USING,
            "methodCalls": list(method_calls),
        }

        log.debug("JMAP POST to %s: %d method call(s)", session.api_url, len(method_calls))

        response = requests.post(
            session.api_url,
            json=payload,
            auth=self._auth,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=self.timeout,
        )

        if response.status_code in (401, 403):
            raise JMAPAuthError(
                url=session.api_url,
                reason=f"HTTP {response.status_code} from API endpoint",
            )

        response.raise_for_status()

        data = response.json()
        method_responses = data.get("methodResponses", [])

        for resp in method_responses:
            method_name, resp_args, call_id = resp
            if method_name == "error":
                error_type = resp_args.get("type", "serverError")
                raise JMAPMethodError(
                    url=session.api_url,
                    reason=f"Method call failed: {resp_args}",
                    error_type=error_type,
                )

        return method_responses

    def get_calendars(self) -> list[JMAPCalendar]:
        """Fetch all calendars for the authenticated account.

        Returns:
            List of :class:`~caldav.jmap.objects.calendar.JMAPCalendar` objects.
        """
        session = self._get_session()
        call = build_calendar_get(session.account_id)
        responses = self._request([call])

        for method_name, resp_args, _ in responses:
            if method_name == "Calendar/get":
                return parse_calendar_get(resp_args)

        return []
