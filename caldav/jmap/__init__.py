"""
JMAP calendar support for python-caldav.

Provides a synchronous JMAP client with the same public API as the
CalDAV client, so user code works regardless of server protocol.

Basic usage::

    from caldav.jmap import get_jmap_client

    client = get_jmap_client(
        url="https://jmap.example.com/.well-known/jmap",
        username="alice",
        password="secret",
    )
    calendars = client.get_calendars()
"""

from caldav.jmap.client import JMAPClient
from caldav.jmap.error import (
    JMAPAuthError,
    JMAPCapabilityError,
    JMAPError,
    JMAPMethodError,
)


def get_jmap_client(**kwargs) -> JMAPClient | None:
    """Create a :class:`JMAPClient` from configuration.

    Configuration is read from the same sources as :func:`caldav.get_davclient`:

    1. Explicit keyword arguments (``url``, ``username``, ``password``, …)
    2. Environment variables (``CALDAV_URL``, ``CALDAV_USERNAME``, …)
    3. Config file (``~/.config/caldav/calendar.conf`` or equivalent)

    Returns ``None`` if no configuration is found, matching the behaviour
    of :func:`caldav.get_davclient`.

    Example::

        client = get_jmap_client(url="https://jmap.example.com/.well-known/jmap",
                                  username="alice", password="secret")
    """
    from caldav.config import get_connection_params

    conn_params = get_connection_params(**kwargs)
    if conn_params is None:
        return None

    # Strip CalDAV-only keys that JMAPClient does not accept.
    _JMAP_KEYS = {"url", "username", "password", "auth", "auth_type", "timeout"}
    jmap_params = {k: v for k, v in conn_params.items() if k in _JMAP_KEYS}

    return JMAPClient(**jmap_params)


__all__ = [
    "JMAPClient",
    "get_jmap_client",
    "JMAPError",
    "JMAPCapabilityError",
    "JMAPAuthError",
    "JMAPMethodError",
]
