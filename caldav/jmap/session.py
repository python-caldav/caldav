"""
JMAP session establishment (RFC 8620 §2).

Fetches the Session object from /.well-known/jmap and extracts the
information needed to make subsequent API calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

try:
    import niquests as requests
except ImportError:
    import requests  # type: ignore[no-redef]

from caldav.jmap.constants import CALENDAR_CAPABILITY
from caldav.jmap.error import JMAPAuthError, JMAPCapabilityError


@dataclass
class Session:
    """Parsed JMAP Session object (RFC 8620 §2).

    Attributes:
        api_url: URL to POST method calls to.
        account_id: The accountId to use for calendar method calls.
            Chosen as the first account advertising the calendars capability.
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


def fetch_session(url: str, auth) -> Session:
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
    response = requests.get(url, auth=auth, headers={"Accept": "application/json"})

    if response.status_code in (401, 403):
        raise JMAPAuthError(
            url=url,
            reason=f"HTTP {response.status_code} from session endpoint",
        )

    response.raise_for_status()

    data = response.json()

    api_url = data.get("apiUrl")
    if not api_url:
        raise JMAPCapabilityError(
            url=url,
            reason="Session response missing 'apiUrl'",
        )

    state = data.get("state", "")
    server_capabilities = data.get("capabilities", {})
    accounts = data.get("accounts", {})

    account_id = None
    account_capabilities: dict = {}
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
