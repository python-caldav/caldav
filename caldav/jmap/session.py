"""
JMAP session establishment (RFC 8620 §2).

Fetches the Session object from /.well-known/jmap and extracts the
information needed to make subsequent API calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin

try:
    import niquests as requests
    from niquests import AsyncSession
except ImportError:
    import requests  # type: ignore[no-redef]

    AsyncSession = None  # type: ignore[assignment,misc]  # async_fetch_session requires niquests

from caldav.jmap.constants import CALENDAR_CAPABILITY
from caldav.jmap.error import JMAPAuthError, JMAPCapabilityError


@dataclass
class Session:
    """Parsed JMAP Session object (RFC 8620 §2).

    Attributes:
        api_url: URL to POST method calls to.
        account_id: The accountId to use for calendar method calls.
            Chosen from ``primaryAccounts`` if available, otherwise the first
            account advertising the calendars capability.
        state: Current session state string.
        account_capabilities: Capabilities dict for the chosen account.
        server_capabilities: Server-level capabilities dict.
        raw: The full parsed Session JSON for anything not captured above.
    """

    api_url: str
    account_id: str
    state: str
    account_capabilities: dict = field(default_factory=dict)
    server_capabilities: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


def _parse_session_data(url: str, data: dict) -> Session:
    api_url = data.get("apiUrl")
    if not api_url:
        raise JMAPCapabilityError(
            url=url,
            reason="Session response missing 'apiUrl'",
        )

    # RFC 8620 §2 says apiUrl SHOULD be absolute, but some servers (e.g. Cyrus)
    # return a relative path. Resolve it against the session endpoint URL.
    api_url = urljoin(url, api_url)

    state = data.get("state", "")
    server_capabilities = data.get("capabilities", {})
    accounts = data.get("accounts", {})

    account_id = None
    account_capabilities: dict = {}
    primary_acct_id = data.get("primaryAccounts", {}).get(CALENDAR_CAPABILITY)
    if primary_acct_id:
        acct_data = accounts.get(primary_acct_id, {})
        caps = acct_data.get("accountCapabilities", {})
        if CALENDAR_CAPABILITY in caps:
            account_id = primary_acct_id
            account_capabilities = caps
    if account_id is None:
        for acct_id, acct_data in accounts.items():
            caps = acct_data.get("accountCapabilities", {})
            if CALENDAR_CAPABILITY in caps:
                account_id = acct_id
                account_capabilities = caps
                break

    if account_id is None:
        raise JMAPCapabilityError(
            url=url,
            reason=(
                f"No account found with capability {CALENDAR_CAPABILITY!r}. "
                f"Available accounts: {list(accounts.keys())}"
            ),
        )

    return Session(
        api_url=api_url,
        account_id=account_id,
        state=state,
        account_capabilities=account_capabilities,
        server_capabilities=server_capabilities,
        raw=data,
    )


def fetch_session(url: str, auth, timeout: int = 30) -> Session:
    """Fetch and parse the JMAP Session object.

    Performs a GET request to ``url`` (expected to be ``/.well-known/jmap``
    or equivalent), authenticates with ``auth``, and returns a parsed
    :class:`Session`.

    Args:
        url: Full URL to the JMAP session endpoint.
        auth: A requests-compatible auth object (e.g. HTTPBasicAuth,
              HTTPBearerAuth).

    Returns:
        Parsed :class:`Session` with ``api_url`` and ``account_id`` set.

    Raises:
        JMAPAuthError: If the server returns HTTP 401 or 403.
        JMAPCapabilityError: If no account advertises the calendars capability.
        requests.HTTPError: For other non-2xx responses.
    """
    response = requests.get(url, auth=auth, headers={"Accept": "application/json"}, timeout=timeout)
    if response.status_code in (401, 403):
        raise JMAPAuthError(url=url, reason=f"HTTP {response.status_code} from session endpoint")
    response.raise_for_status()
    return _parse_session_data(url, response.json())


async def async_fetch_session(url: str, auth, timeout: int = 30) -> Session:
    """Async variant of :func:`fetch_session` using niquests.AsyncSession.

    Args:
        url: Full URL to the JMAP session endpoint.
        auth: A niquests-compatible auth object.

    Returns:
        Parsed :class:`Session` with ``api_url`` and ``account_id`` set.

    Raises:
        JMAPAuthError: If the server returns HTTP 401 or 403.
        JMAPCapabilityError: If no account advertises the calendars capability.
    """
    async with AsyncSession() as session:
        response = await session.get(
            url, auth=auth, headers={"Accept": "application/json"}, timeout=timeout
        )
    if response.status_code in (401, 403):
        raise JMAPAuthError(url=url, reason=f"HTTP {response.status_code} from session endpoint")
    response.raise_for_status()
    return _parse_session_data(url, response.json())
