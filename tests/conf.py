"""
Compatibility shim for tests that still import from tests.conf.

This module provides the same interface as the old conf.py but uses
the test_servers framework under the hood.

NOTE: New tests should use test_servers directly:
    from tests.test_servers import get_available_servers, ServerRegistry
"""
import logging
import os
import socket
import tempfile
import threading
import time
from typing import Any, List, Optional

try:
    import niquests as requests
except ImportError:
    import requests

from caldav import compatibility_hints
from caldav.davclient import DAVClient

# Configuration from environment or defaults
test_public_test_servers = False

# Radicale configuration
radicale_host = os.environ.get("RADICALE_HOST", "localhost")
radicale_port = int(os.environ.get("RADICALE_PORT", "5232"))
test_radicale = False
try:
    import radicale
    test_radicale = True
except ImportError:
    pass

# Xandikos configuration
xandikos_host = os.environ.get("XANDIKOS_HOST", "localhost")
xandikos_port = int(os.environ.get("XANDIKOS_PORT", "8993"))
test_xandikos = False
try:
    import xandikos
    test_xandikos = True
except ImportError:
    pass

# RFC6638 users (scheduling tests)
rfc6638_users: List[Any] = []

# Server list - populated dynamically
caldav_servers: List[dict] = []

# Radicale embedded server setup
if test_radicale:
    import radicale.config
    import radicale.server

    def setup_radicale(self):
        self.serverdir = tempfile.TemporaryDirectory()
        self.serverdir.__enter__()
        self.configuration = radicale.config.load("")
        self.configuration.update(
            {
                "storage": {"filesystem_folder": self.serverdir.name},
                "auth": {"type": "none"},
            }
        )
        self.server = radicale.server
        self.shutdown_socket, self.shutdown_socket_out = socket.socketpair()
        self.radicale_thread = threading.Thread(
            target=self.server.serve,
            args=(self.configuration, self.shutdown_socket_out),
        )
        self.radicale_thread.start()
        i = 0
        while True:
            try:
                requests.get(str(self.url))
                break
            except:
                time.sleep(0.05)
                i += 1
                assert i < 100

    def teardown_radicale(self):
        self.shutdown_socket.close()
        self.serverdir.__exit__(None, None, None)

    domain = f"{radicale_host}:{radicale_port}"
    features = compatibility_hints.radicale.copy()
    features["auto-connect.url"]["domain"] = domain
    compatibility_hints.radicale_tmp_test = features
    caldav_servers.append(
        {
            "name": "LocalRadicale",
            "username": "user1",
            "password": "",
            "features": "radicale_tmp_test",
            "backwards_compatibility_url": f"http://{domain}/user1",
            "setup": setup_radicale,
            "teardown": teardown_radicale,
        }
    )

# Xandikos embedded server setup
if test_xandikos:
    import asyncio
    import aiohttp
    import aiohttp.web
    from xandikos.web import XandikosApp, XandikosBackend

    def setup_xandikos(self):
        self.serverdir = tempfile.TemporaryDirectory()
        self.serverdir.__enter__()
        self.backend = XandikosBackend(path=self.serverdir.name)
        self.backend._mark_as_principal("/sometestuser/")
        self.backend.create_principal("/sometestuser/", create_defaults=True)
        mainapp = XandikosApp(
            self.backend, current_user_principal="sometestuser", strict=True
        )

        async def xandikos_handler(request):
            return await mainapp.aiohttp_handler(request, "/")

        self.xapp = aiohttp.web.Application()
        self.xapp.router.add_route("*", "/{path_info:.*}", xandikos_handler)
        self.xapp_loop = asyncio.new_event_loop()
        self.xapp_runner = aiohttp.web.AppRunner(self.xapp)
        asyncio.set_event_loop(self.xapp_loop)
        self.xapp_loop.run_until_complete(self.xapp_runner.setup())
        self.xapp_site = aiohttp.web.TCPSite(
            self.xapp_runner, host=xandikos_host, port=xandikos_port
        )
        self.xapp_loop.run_until_complete(self.xapp_site.start())

        def aiohttp_server():
            self.xapp_loop.run_forever()

        self.xandikos_thread = threading.Thread(target=aiohttp_server)
        self.xandikos_thread.start()

    def teardown_xandikos(self):
        self.xapp_loop.stop()

        def silly_request():
            try:
                requests.get(str(self.url))
            except:
                pass

        threading.Thread(target=silly_request).start()
        i = 0
        while self.xapp_loop.is_running():
            time.sleep(0.05)
            i += 1
            assert i < 100
        self.xapp_loop.run_until_complete(self.xapp_runner.cleanup())
        i = 0
        while self.xandikos_thread.is_alive():
            time.sleep(0.05)
            i += 1
            assert i < 100
        self.serverdir.__exit__(None, None, None)

    if xandikos.__version__ == (0, 2, 12):
        features = compatibility_hints.xandikos_v0_2_12.copy()
    else:
        features = compatibility_hints.xandikos_v0_3.copy()
    domain = f"{xandikos_host}:{xandikos_port}"
    features["auto-connect.url"]["domain"] = domain
    caldav_servers.append(
        {
            "name": "LocalXandikos",
            "backwards_compatibility_url": f"http://{domain}/sometestuser",
            "features": features,
            "setup": setup_xandikos,
            "teardown": teardown_xandikos,
        }
    )


def client(
    idx: Optional[int] = None,
    name: Optional[str] = None,
    setup=lambda conn: None,
    teardown=lambda conn: None,
    **kwargs,
) -> Optional[DAVClient]:
    """Get a DAVClient for testing."""
    from caldav.davclient import CONNKEYS

    kwargs_ = kwargs.copy()
    no_args = not any(x for x in kwargs if kwargs[x] is not None)

    if idx is None and name is None and no_args and caldav_servers:
        return client(idx=0)
    elif idx is not None and no_args and caldav_servers:
        return client(**caldav_servers[idx])
    elif name is not None and no_args and caldav_servers:
        for s in caldav_servers:
            if s["name"] == name:
                return client(**s)
        return None
    elif no_args:
        return None

    # Clean up non-connection parameters
    for bad_param in ("incompatibilities", "backwards_compatibility_url", "principal_url", "enable"):
        kwargs_.pop(bad_param, None)

    for kw in list(kwargs_.keys()):
        if kw not in CONNKEYS:
            logging.debug(f"Ignoring unknown parameter: {kw}")
            kwargs_.pop(kw)

    conn = DAVClient(**kwargs_)
    conn.setup = setup
    conn.teardown = teardown
    conn.server_name = name
    return conn


# Filter enabled servers
caldav_servers = [x for x in caldav_servers if x.get("enable", True)]
