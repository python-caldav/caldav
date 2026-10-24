"""
Test server framework for caldav tests.

The implementation lives in caldav.testing (shipped with the package, so that
other projects can use it); this package re-exports it, and each submodule is
an alias of its caldav.testing counterpart, so existing imports and
monkeypatching keep working.

This package provides a unified framework for starting and managing
test servers (Radicale, Xandikos, Docker containers) for both sync
and async tests.

Usage:
    from tests.test_servers import client_context

    # Simple: get a running server with get_davclient() support
    with client_context() as client:
        principal = client.principal()
        # get_davclient() also works within this context

    # Or use the lower-level APIs:
    from tests.test_servers import get_available_servers, ServerRegistry

    for server in get_available_servers():
        server.start()
        client = server.get_sync_client()
        # ... run tests ...
        server.stop()
"""

import importlib
import sys

from caldav.testing.base import (
    DEFAULT_HTTP_TIMEOUT,
    MAX_STARTUP_WAIT_SECONDS,
    STARTUP_POLL_INTERVAL,
    DockerTestServer,
    EmbeddedTestServer,
    ExternalTestServer,
    TestServer,
)
from caldav.testing.config_loader import ConfigParseError, load_test_server_config
from caldav.testing.helpers import client_context, has_test_servers
from caldav.testing.registry import ServerRegistry, get_available_servers, get_registry

for _name in ("base", "config_loader", "docker", "embedded", "helpers", "registry"):
    sys.modules[f"{__name__}.{_name}"] = globals()[_name] = importlib.import_module(
        f"caldav.testing.{_name}"
    )

__all__ = [
    # High-level helpers
    "client_context",
    "has_test_servers",
    # Base classes
    "TestServer",
    "EmbeddedTestServer",
    "DockerTestServer",
    "ExternalTestServer",
    # Registry
    "ServerRegistry",
    "get_available_servers",
    "get_registry",
    # Config loading
    "load_test_server_config",
    "ConfigParseError",
    # Constants
    "DEFAULT_HTTP_TIMEOUT",
    "MAX_STARTUP_WAIT_SECONDS",
    "STARTUP_POLL_INTERVAL",
]
