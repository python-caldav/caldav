"""
Embedded test server implementations.

This module provides test server implementations for servers that run
in-process: Radicale and Xandikos.
"""

import socket
import tempfile
import threading
from typing import Any

try:
    import niquests as requests
except ImportError:
    import requests  # type: ignore

from caldav import compatibility_hints

from .base import EmbeddedTestServer
from .registry import register_server_class


class RadicaleTestServer(EmbeddedTestServer):
    """
    Radicale CalDAV server running in a thread.

    Radicale is a lightweight CalDAV server that's easy to embed
    for testing purposes.
    """

    name = "LocalRadicale"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", "localhost")
        config.setdefault("port", 5232)
        config.setdefault("username", "user1")
        config.setdefault("password", "")
        # Set up Radicale-specific compatibility hints
        if "features" not in config:
            features = compatibility_hints.radicale.copy()
            host = config.get("host", "localhost")
            port = config.get("port", 5232)
            features["auto-connect.url"]["domain"] = f"{host}:{port}"
            config["features"] = features
        super().__init__(config)

        # Server state
        self.serverdir: tempfile.TemporaryDirectory | None = None
        self.shutdown_socket: socket.socket | None = None
        self.shutdown_socket_out: socket.socket | None = None
        self.thread: threading.Thread | None = None

    def _default_port(self) -> int:
        return 5232

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/{self.username}"

    def is_accessible(self) -> bool:
        try:
            # Check the user URL to ensure the server is ready
            # and to auto-create the user collection (Radicale does this on first access)
            response = requests.get(
                f"http://{self.host}:{self.port}/{self.username}",
                timeout=2,
            )
            return response.status_code in (200, 401, 403, 404)
        except Exception:
            return False

    def start(self) -> None:
        """Start the Radicale server in a background thread."""
        # Only check is_accessible() if we haven't been started before.
        # After stop() is called, the port might still respond briefly,
        # so we can't trust is_accessible() in that case.
        if self._started:
            return
        if not hasattr(self, "_was_stopped") and self.is_accessible():
            return

        try:
            import radicale
            import radicale.config
            import radicale.server
        except ImportError as e:
            raise RuntimeError("Radicale is not installed") from e

        # Create temporary storage directory
        self.serverdir = tempfile.TemporaryDirectory()
        self.serverdir.__enter__()

        # Configure Radicale
        configuration = radicale.config.load("")
        configuration.update(
            {
                "storage": {"filesystem_folder": self.serverdir.name},
                "auth": {"type": "none"},
            }
        )

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

        # Create the user collection with MKCOL
        # Radicale requires the parent collection to exist before MKCALENDAR
        user_url = f"http://{self.host}:{self.port}/{self.username}/"
        try:
            response = requests.request(
                "MKCOL",
                user_url,
                timeout=5,
            )
            # 201 = created, 405 = already exists (or method not allowed)
            if response.status_code not in (200, 201, 204, 405):
                # Some servers need a trailing slash, try without
                response = requests.request(
                    "MKCOL",
                    user_url.rstrip("/"),
                    timeout=5,
                )
        except Exception:
            pass  # Ignore errors, the collection might already exist

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
        self._was_stopped = True  # Mark that we've been stopped at least once


class XandikosTestServer(EmbeddedTestServer):
    """
    Xandikos CalDAV server running with aiohttp.

    Xandikos is an async CalDAV server that uses aiohttp.
    We run it in a separate thread with its own event loop.
    """

    name = "LocalXandikos"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", "localhost")
        config.setdefault("port", 8993)
        config.setdefault("username", "sometestuser")
        # Set up Xandikos-specific compatibility hints
        if "features" not in config:
            features = compatibility_hints.xandikos.copy()
            host = config.get("host", "localhost")
            port = config.get("port", 8993)
            features["auto-connect.url"]["domain"] = f"{host}:{port}"
            config["features"] = features
        super().__init__(config)

        # Server state
        self.serverdir: tempfile.TemporaryDirectory | None = None
        self.xapp_loop: Any | None = None
        self.xapp_runner: Any | None = None
        self.xapp: Any | None = None
        self.thread: threading.Thread | None = None

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
        # Only check is_accessible() if we haven't been started before.
        # After stop() is called, the port might still respond briefly,
        # so we can't trust is_accessible() in that case.
        if self._started:
            return
        if not hasattr(self, "_was_stopped") and self.is_accessible():
            return

        try:
            from xandikos.web import SingleUserFilesystemBackend, XandikosApp
        except ImportError as e:
            raise RuntimeError("Xandikos is not installed") from e

        import asyncio

        from aiohttp import web

        # Create temporary storage directory
        self.serverdir = tempfile.TemporaryDirectory()
        self.serverdir.__enter__()

        # Create backend and configure principal (following conf.py pattern)
        backend = SingleUserFilesystemBackend(self.serverdir.name)
        backend._mark_as_principal(f"/{self.username}/")
        backend.create_principal(f"/{self.username}/", create_defaults=True)

        # Create the Xandikos app with the backend
        mainapp = XandikosApp(backend, current_user_principal=self.username, strict=True)

        # Create aiohttp handler
        async def xandikos_handler(request: web.Request) -> web.Response:
            return await mainapp.aiohttp_handler(request, "/")

        self.xapp = web.Application()
        self.xapp.router.add_route("*", "/{path_info:.*}", xandikos_handler)

        def run_in_thread() -> None:
            self.xapp_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.xapp_loop)

            async def start_app() -> None:
                self.xapp_runner = web.AppRunner(self.xapp)
                await self.xapp_runner.setup()
                site = web.TCPSite(self.xapp_runner, self.host, self.port)
                await site.start()

            self.xapp_loop.run_until_complete(start_app())
            self.xapp_loop.run_forever()

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
            # Clean shutdown: first cleanup the aiohttp runner (stops accepting
            # connections and waits for in-flight requests), then stop the loop.
            # This must be done from within the event loop thread.
            async def cleanup_and_stop() -> None:
                await self.xapp_runner.cleanup()
                self.xapp_loop.stop()

            try:
                asyncio.run_coroutine_threadsafe(cleanup_and_stop(), self.xapp_loop).result(
                    timeout=10
                )
            except Exception:
                # Fallback: force stop if cleanup fails
                if self.xapp_loop:
                    self.xapp_loop.call_soon_threadsafe(self.xapp_loop.stop)
        elif self.xapp_loop:
            self.xapp_loop.call_soon_threadsafe(self.xapp_loop.stop)

        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None

        if self.serverdir:
            self.serverdir.__exit__(None, None, None)
            self.serverdir = None

        self.xapp_loop = None
        self.xapp_runner = None
        self.xapp = None
        self._started = False
        self._was_stopped = True  # Mark that we've been stopped at least once


# Register server classes
register_server_class("radicale", RadicaleTestServer)
register_server_class("xandikos", XandikosTestServer)
