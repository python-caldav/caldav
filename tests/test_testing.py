"""
Tests for the embedded servers in caldav.testing.

https://github.com/python-caldav/caldav/issues/797
"""

import pytest

from caldav.lib.http_sync import requests
from caldav.testing import RadicaleServer, XandikosServer

from .test_servers.helpers import free_port


def test_radicale_listens_on_configured_port() -> None:
    pytest.importorskip("radicale")
    port = free_port()
    server = RadicaleServer({"port": port})
    server.start()
    try:
        r = requests.get(f"http://localhost:{port}/{server.username}/", timeout=5)
        assert r.status_code in (200, 207, 401, 403, 404)
    finally:
        server.stop()


def test_radicale_stop_closes_both_socket_ends() -> None:
    pytest.importorskip("radicale")
    server = RadicaleServer({"port": free_port()})
    server.start()
    sockets = (server.shutdown_socket, server.shutdown_socket_out)
    server.stop()
    assert all(s.fileno() == -1 for s in sockets)


def test_xandikos_stop_closes_event_loop() -> None:
    pytest.importorskip("xandikos")
    server = XandikosServer({"port": free_port()})
    server.start()
    loop = server.xapp_loop
    server.stop()
    assert loop.is_closed()
