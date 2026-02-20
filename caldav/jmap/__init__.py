"""
JMAP calendar support for python-caldav.

Provides synchronous and asynchronous JMAP clients with the same public API as
the CalDAV client, so user code works regardless of server protocol.

Basic usage::

    from caldav.jmap import get_jmap_client

    client = get_jmap_client(
        url="https://jmap.example.com/.well-known/jmap",
        username="alice",
        password="secret",
    )
    calendars = client.get_calendars()

Async usage::

    from caldav.jmap import get_async_jmap_client

    async with get_async_jmap_client(
        url="https://jmap.example.com/.well-known/jmap",
        username="alice",
        password="secret",
    ) as client:
        calendars = await client.get_calendars()
"""

from caldav.jmap.async_client import AsyncJMAPClient
from caldav.jmap.client import JMAPClient
from caldav.jmap.error import (
    JMAPAuthError,
    JMAPCapabilityError,
    JMAPError,
    JMAPMethodError,
)

_JMAP_KEYS = {"url", "username", "password", "auth", "auth_type", "timeout"}


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
    return JMAPClient(**{k: v for k, v in conn_params.items() if k in _JMAP_KEYS})


def get_async_jmap_client(**kwargs) -> AsyncJMAPClient | None:
    """Create an :class:`AsyncJMAPClient` from configuration.

    Accepts the same arguments and reads configuration from the same sources
    as :func:`get_jmap_client`. Returns ``None`` if no configuration is found.

    Example::

        async with get_async_jmap_client(
            url="https://jmap.example.com/.well-known/jmap",
            username="alice", password="secret"
        ) as client:
            calendars = await client.get_calendars()
    """
    from caldav.config import get_connection_params

    conn_params = get_connection_params(**kwargs)
    if conn_params is None:
        return None
    return AsyncJMAPClient(**{k: v for k, v in conn_params.items() if k in _JMAP_KEYS})


__all__ = [
    "JMAPClient",
    "AsyncJMAPClient",
    "get_jmap_client",
    "get_async_jmap_client",
    "JMAPError",
    "JMAPCapabilityError",
    "JMAPAuthError",
    "JMAPMethodError",
]
