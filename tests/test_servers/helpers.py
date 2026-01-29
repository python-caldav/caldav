"""
Helper functions for test server management.

Provides convenient context managers for tests that need a running server
with get_davclient() support.
"""

import json
import os
import tempfile
from contextlib import contextmanager

from caldav import DAVClient

from .registry import get_registry


@contextmanager
def client_context(server_index: int = 0, server_name: str | None = None):
    """
    Context manager that provides a running test server and configured environment.

    This is the recommended way to get a test client when you need:
    - A running server
    - Environment configured so get_davclient() works
    - Automatic cleanup

    Usage:
        from tests.test_servers import client_context

        with client_context() as client:
            principal = client.principal()
            # get_davclient() will also work within this context

    Args:
        server_index: Index into the caldav_servers list (default: 0, first server)
        server_name: Optional server name to use instead of index

    Yields:
        DAVClient: Connected client to the test server

    Raises:
        RuntimeError: If no test servers are configured
    """
    registry = get_registry()
    servers = registry.get_caldav_servers_list()

    if not servers:
        raise RuntimeError("No test servers configured")

    # Find the server to use
    if server_name:
        server_params = None
        for s in servers:
            if s.get("name") == server_name:
                server_params = s
                break
        if not server_params:
            raise RuntimeError(f"Server '{server_name}' not found")
    else:
        server_params = servers[server_index]

    # Import here to avoid circular imports
    from caldav.davclient import CONNKEYS

    # Create client and start server via setup callback
    kwargs = {k: v for k, v in server_params.items() if k in CONNKEYS}
    conn = DAVClient(**kwargs)
    conn.setup = server_params.get("setup", lambda _: None)
    conn.teardown = server_params.get("teardown", lambda _: None)

    # Create temporary config file for get_davclient()
    config = {"testing_allowed": True}
    for key in ("username", "password", "proxy"):
        if key in server_params:
            config[f"caldav_{key}"] = server_params[key]
    config["caldav_url"] = server_params["url"]

    config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump({"default": config}, config_file)
    config_file.close()

    # Set environment variables
    old_config_file = os.environ.get("CALDAV_CONFIG_FILE")
    old_test_server = os.environ.get("PYTHON_CALDAV_USE_TEST_SERVER")

    os.environ["CALDAV_CONFIG_FILE"] = config_file.name
    os.environ["PYTHON_CALDAV_USE_TEST_SERVER"] = "1"

    try:
        # Enter client context (starts server)
        conn.__enter__()
        yield conn
    finally:
        # Exit client context (stops server)
        conn.__exit__(None, None, None)

        # Clean up config file
        os.unlink(config_file.name)

        # Restore environment
        if old_config_file is not None:
            os.environ["CALDAV_CONFIG_FILE"] = old_config_file
        else:
            os.environ.pop("CALDAV_CONFIG_FILE", None)

        if old_test_server is not None:
            os.environ["PYTHON_CALDAV_USE_TEST_SERVER"] = old_test_server
        else:
            os.environ.pop("PYTHON_CALDAV_USE_TEST_SERVER", None)


def has_test_servers() -> bool:
    """Check if any test servers are configured."""
    registry = get_registry()
    return len(registry.get_caldav_servers_list()) > 0
