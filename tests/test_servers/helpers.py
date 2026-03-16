"""
Helper functions for test server management.

Provides convenient context managers for tests that need a running server
with get_davclient() support.
"""

import os
from contextlib import contextmanager

from caldav import DAVClient

from .registry import get_registry


@contextmanager
def client_context(server_index: int = 0, server_name: str | None = None):
    """
    Context manager that provides a running test server.

    Starts the highest-priority available server (or the one selected by
    ``server_index`` / ``server_name``), yields a connected DAVClient, and
    stops the server on exit.

    Sets ``PYTHON_CALDAV_USE_TEST_SERVER=1`` for the duration so that
    ``get_davclient()`` calls within the block also find the running server
    via the registry (without needing a temporary config file).

    Usage::

        from tests.test_servers import client_context

        with client_context() as client:
            principal = client.principal()
            # get_davclient() also works within this context

    Args:
        server_index: Index into the priority-ordered enabled-servers list
                      (default: 0 = highest-priority server).
        server_name: Optional server name to use instead of index.

    Yields:
        DAVClient: Connected client to the test server.

    Raises:
        RuntimeError: If no test servers are configured or the requested
                      server is not found.
    """
    registry = get_registry()
    servers = registry.enabled_servers()

    if not servers:
        raise RuntimeError("No test servers configured")

    if server_name:
        server = next((s for s in servers if s.name == server_name), None)
        if server is None:
            raise RuntimeError(f"Server '{server_name}' not found")
    else:
        server = servers[server_index]

    server.start()

    from caldav.davclient import CONNKEYS

    conn_kwargs = {
        k: v
        for k, v in {
            "url": server.url,
            "username": server.username,
            "password": server.password,
            "features": server.features,
        }.items()
        if v is not None and k in CONNKEYS
    }
    conn = DAVClient(**conn_kwargs)
    conn.server_name = server.name

    old_env = os.environ.get("PYTHON_CALDAV_USE_TEST_SERVER")
    os.environ["PYTHON_CALDAV_USE_TEST_SERVER"] = "1"

    try:
        yield conn
    finally:
        server.stop()

        if old_env is not None:
            os.environ["PYTHON_CALDAV_USE_TEST_SERVER"] = old_env
        else:
            os.environ.pop("PYTHON_CALDAV_USE_TEST_SERVER", None)


def has_test_servers() -> bool:
    """Check if any test servers are configured."""
    registry = get_registry()
    return len(registry.enabled_servers()) > 0
