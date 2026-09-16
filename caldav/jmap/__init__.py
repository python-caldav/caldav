"""
JMAP calendar support for python-caldav.

.. deprecated::
   Thin re-export of the standalone `calendaring-jmap
   <https://pypi.org/project/calendaring-jmap/>`_ package. Import from
   ``calendaring_jmap`` directly instead.

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

import warnings

try:
    from calendaring_jmap import (
        AsyncJMAPClient,
        JMAPAuthError,
        JMAPCalendar,
        JMAPCalendarObject,
        JMAPCapabilityError,
        JMAPClient,
        JMAPError,
        JMAPMethodError,
    )
except ImportError as e:
    raise ImportError(
        "caldav.jmap requires the standalone calendaring-jmap package, which is "
        "not installed.  Install it with `pip install caldav[jmap]` or "
        "`pip install calendaring-jmap`."
    ) from e

warnings.warn(
    "caldav.jmap is deprecated; import from the standalone calendaring-jmap "
    "package instead (pip install calendaring-jmap). caldav.jmap now just "
    "re-exports it and will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
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
    "JMAPCalendar",
    "JMAPCalendarObject",
]
