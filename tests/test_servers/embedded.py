"""
Embedded test server implementations.

This module provides test server implementations for servers that run
in-process: Radicale and Xandikos.
"""

import socket
import tempfile
import threading
from typing import Any, Dict, Optional

try:
    import niquests as requests
except ImportError:
    import requests  # type: ignore

from .base import EmbeddedTestServer, STARTUP_POLL_INTERVAL, MAX_STARTUP_WAIT_SECONDS
from .registry import register_server_class


class RadicaleTestServer(EmbeddedTestServer):
    """
    Radicale CalDAV server running in a thread.

    Radicale is a lightweight CalDAV server that's easy to embed
    for testing purposes.
    """

    name = "LocalRadicale"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        config = config or {}
        config.setdefault("host", "localhost")
        config.setdefault("port", 5232)
        config.setdefault("username", "user1")
        config.setdefault("password", "")
        super().__init__(config)

        # Server state
        self.serverdir: Optional[tempfile.TemporaryDirectory] = None
        self.shutdown_socket: Optional[socket.socket] = None
        self.shutdown_socket_out: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None

    def _default_port(self) -> int:
        return 5232

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/{self.username}"

    def is_accessible(self) -> bool:
        try:
            response = requests.get(
                f"http://{self.host}:{self.port}",
                timeout=2,
            )
            return response.status_code in (200, 401, 403, 404)
        except Exception:
            return False

    def start(self) -> None:
        """Start the Radicale server in a background thread."""
        if self._started or self.is_accessible():
            return

        try:
            import radicale
            import radicale.config
            import radicale.server
        except ImportError:
            raise RuntimeError("Radicale is not installed")

        # Create temporary storage directory
        self.serverdir = tempfile.TemporaryDirectory()
        self.serverdir.__enter__()

        # Configure Radicale
        configuration = radicale.config.load("")
        configuration.update({
            "storage": {"filesystem_folder": self.serverdir.name},
            "auth": {"type": "none"},
        })

        # Create shutdown socket pair
        self.shutdown_socket, self.shutdown_socket_out = socket.socketpair()

        # Start server thread
        self.thread = threading.Thread(
            target=radicale.server.serve,
            args=(configuration, self.shutdown_socket_out),
        )
        self.thread.start()

        # Wait for server to be ready
        self._wait_for_startup()
        self._started = True

    def stop(self) -> None:
        """Stop the Radicale server and cleanup."""
        if self.shutdown_socket:
            self.shutdown_socket.close()
            self.shutdown_socket = None
            self.shutdown_socket_out = None

        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None

        if self.serverdir:
            self.serverdir.__exit__(None, None, None)
            self.serverdir = None

        self._started = False


class XandikosTestServer(EmbeddedTestServer):
    """
    Xandikos CalDAV server running with aiohttp.

    Xandikos is an async CalDAV server that uses aiohttp.
    We run it in a separate thread with its own event loop.
    """

    name = "LocalXandikos"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        config = config or {}
        config.setdefault("host", "localhost")
        config.setdefault("port", 8993)
        config.setdefault("username", "sometestuser")
        super().__init__(config)

        # Server state
        self.serverdir: Optional[tempfile.TemporaryDirectory] = None
        self.xapp_loop: Optional[Any] = None
        self.xapp_runner: Optional[Any] = None
        self.thread: Optional[threading.Thread] = None

    def _default_port(self) -> int:
        return 8993

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/{self.username}"

    def is_accessible(self) -> bool:
        try:
            response = requests.request(
                "PROPFIND",
                f"http://{self.host}:{self.port}",
                timeout=2,
            )
            return response.status_code in (200, 207, 401, 403, 404)
        except Exception:
            return False

    def start(self) -> None:
        """Start the Xandikos server."""
        if self._started or self.is_accessible():
            return

        try:
            import xandikos
            import xandikos.web
        except ImportError:
            raise RuntimeError("Xandikos is not installed")

        import asyncio
        from aiohttp import web

        # Create temporary storage directory
        self.serverdir = tempfile.TemporaryDirectory()
        self.serverdir.__enter__()

        # Create and configure the Xandikos app
        xapp = xandikos.web.XandikosApp(
            self.serverdir.name,
            current_user_principal=f"/{self.username}/",
            autocreate=True,
        )

        async def start_app() -> None:
            self.xapp_runner = web.AppRunner(xapp.app)
            await self.xapp_runner.setup()
            site = web.TCPSite(self.xapp_runner, self.host, self.port)
            await site.start()
            # Keep running until cancelled
            while True:
                await asyncio.sleep(3600)

        def run_in_thread() -> None:
            self.xapp_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.xapp_loop)
            try:
                self.xapp_loop.run_until_complete(start_app())
            except asyncio.CancelledError:
                pass
            finally:
                self.xapp_loop.close()

        # Start server in a background thread
        self.thread = threading.Thread(target=run_in_thread)
        self.thread.start()

        # Wait for server to be ready
        self._wait_for_startup()
        self._started = True

    def stop(self) -> None:
        """Stop the Xandikos server and cleanup."""
        import asyncio

        if self.xapp_loop and self.xapp_runner:
            # Schedule cleanup in the event loop
            async def cleanup() -> None:
                await self.xapp_runner.cleanup()

            future = asyncio.run_coroutine_threadsafe(cleanup(), self.xapp_loop)
            try:
                future.result(timeout=5)
            except Exception:
                pass

            # Stop the event loop
            self.xapp_loop.call_soon_threadsafe(self.xapp_loop.stop)

        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None

        if self.serverdir:
            self.serverdir.__exit__(None, None, None)
            self.serverdir = None

        self.xapp_loop = None
        self.xapp_runner = None
        self._started = False


# Register server classes
register_server_class("radicale", RadicaleTestServer)
register_server_class("xandikos", XandikosTestServer)
