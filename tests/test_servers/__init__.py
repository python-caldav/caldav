"""
Test server framework for caldav tests.

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
from .base import DEFAULT_HTTP_TIMEOUT
from .base import DockerTestServer
from .base import EmbeddedTestServer
from .base import ExternalTestServer
from .base import MAX_STARTUP_WAIT_SECONDS
from .base import STARTUP_POLL_INTERVAL
from .base import TestServer
from .config_loader import create_example_config
from .config_loader import load_test_server_config
from .helpers import client_context
from .helpers import has_test_servers
from .registry import get_available_servers
from .registry import get_registry
from .registry import ServerRegistry

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
    "create_example_config",
    # Constants
    "DEFAULT_HTTP_TIMEOUT",
    "MAX_STARTUP_WAIT_SECONDS",
    "STARTUP_POLL_INTERVAL",
]
