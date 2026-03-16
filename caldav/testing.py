"""
Lightweight embedded CalDAV test servers.

Provides XandikosServer and RadicaleServer that are part of the installed
package so that pip-installed users can use get_davclient() with
PYTHON_CALDAV_USE_TEST_SERVER=1 without needing the full test infrastructure
from the source tree.

Docker and external server support lives in tests/test_servers/ (source only).
"""

import socket
import tempfile
import threading
import time
from typing import Any

try:
    import niquests as requests
except ImportError:
    import requests  # type: ignore[no-redef]

# ── Constants ────────────────────────────────────────────────────────────────

MAX_STARTUP_WAIT_SECONDS = 60
STARTUP_POLL_INTERVAL = 0.05


# ── Base class ───────────────────────────────────────────────────────────────


class EmbeddedServer:
    """
    Base class for lightweight embedded CalDAV test servers.

    Subclasses must implement ``start()``, ``stop()``, and ``is_accessible()``.

    Priority
    --------
    Both embedded servers default to priority **10**, which beats docker (20)
    and external / configured servers (30).  Override via ``priority: <int>``
    in the config dict or by setting ``_default_priority`` on the subclass.
    """

    name: str = "EmbeddedServer"
    server_type: str = "embedded"
    _default_priority: int = 10

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config: dict[str, Any] = config or {}
        self.host: str = self.config.get("host", "localhost")
        self.port: int = self.config.get("port", self._default_port())
        self._started: bool = False
        self._was_stopped: bool = False

    def _default_port(self) -> int:
        return 5232

    # ── Properties read by caldav/config.py ──────────────────────────────────

    @property
    def priority(self) -> int:
        return int(self.config.get("priority", self._default_priority))

    @property
    def username(self) -> str | None:
        return (
            self.config.get("username")
            or self.config.get("caldav_username")
            or self.config.get("caldav_user")
        )

    @property
    def password(self) -> str | None:
        for key in ("password", "caldav_password", "caldav_pass"):
            if key in self.config:
                return self.config[key]
        return None

    @property
    def features(self) -> Any:
        from caldav.config import resolve_features

        return resolve_features(self.config.get("features", []))

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/{self.username or ''}"

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def is_accessible(self) -> bool:
        raise NotImplementedError

    def _wait_for_startup(self) -> None:
        attempts = int(MAX_STARTUP_WAIT_SECONDS / STARTUP_POLL_INTERVAL)
        for _ in range(attempts):
            if self.is_accessible():
                return
            time.sleep(STARTUP_POLL_INTERVAL)
        raise RuntimeError(f"{self.name} failed to start after {MAX_STARTUP_WAIT_SECONDS} seconds")


# ── XandikosServer ────────────────────────────────────────────────────────────


class XandikosServer(EmbeddedServer):
    """Xandikos CalDAV server running in a background aiohttp thread."""

    name = "Xandikos"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", "localhost")
        config.setdefault("port", 8993)
        config.setdefault("username", "sometestuser")
        if "features" not in config:
            from caldav import compatibility_hints

            features = compatibility_hints.xandikos.copy()
            features["auto-connect.url"]["domain"] = f"{config['host']}:{config['port']}"
            config["features"] = features
        super().__init__(config)

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
        if self._started:
            return
        if not self._was_stopped and self.is_accessible():
            self._started = True
            return

        try:
            from xandikos.web import XandikosApp

            try:
                from xandikos.web import SingleUserFilesystemBackend as XandikosBackend
            except ImportError:
                from xandikos.web import XandikosBackend  # type: ignore[no-redef]
        except ImportError as e:
            raise RuntimeError("Xandikos is not installed") from e

        import asyncio

        from aiohttp import web

        self.serverdir = tempfile.TemporaryDirectory()
        self.serverdir.__enter__()

        backend = XandikosBackend(self.serverdir.name)
        backend._mark_as_principal(f"/{self.username}/")
        backend.create_principal(f"/{self.username}/", create_defaults=True)

        mainapp = XandikosApp(backend, current_user_principal=self.username, strict=True)

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

        self.thread = threading.Thread(target=run_in_thread, daemon=True)
        self.thread.start()
        self._wait_for_startup()
        self._started = True

    def stop(self) -> None:
        import asyncio

        if self.xapp_loop and self.xapp_runner:

            async def cleanup_and_stop() -> None:
                await self.xapp_runner.cleanup()
                self.xapp_loop.stop()

            try:
                asyncio.run_coroutine_threadsafe(cleanup_and_stop(), self.xapp_loop).result(
                    timeout=10
                )
            except Exception:
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
        self._was_stopped = True


# ── RadicaleServer ────────────────────────────────────────────────────────────


class RadicaleServer(EmbeddedServer):
    """Radicale CalDAV server running in a background thread."""

    name = "Radicale"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", "localhost")
        config.setdefault("port", 5232)
        config.setdefault("username", "user1")
        config.setdefault("password", "")
        if "features" not in config:
            from caldav import compatibility_hints

            features = compatibility_hints.radicale.copy()
            features["auto-connect.url"]["domain"] = f"{config['host']}:{config['port']}"
            config["features"] = features
        super().__init__(config)

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
            response = requests.get(
                f"http://{self.host}:{self.port}/{self.username}",
                timeout=2,
            )
            return response.status_code in (200, 401, 403, 404)
        except Exception:
            return False

    def start(self) -> None:
        if self._started:
            return
        if not self._was_stopped and self.is_accessible():
            self._started = True
            return

        try:
            import radicale
            import radicale.config
            import radicale.server
        except ImportError as e:
            raise RuntimeError("Radicale is not installed") from e

        self.serverdir = tempfile.TemporaryDirectory()
        self.serverdir.__enter__()

        configuration = radicale.config.load("")
        configuration.update(
            {
                "storage": {"filesystem_folder": self.serverdir.name},
                "auth": {"type": "none"},
            }
        )

        self.shutdown_socket, self.shutdown_socket_out = socket.socketpair()
        self.thread = threading.Thread(
            target=radicale.server.serve,
            args=(configuration, self.shutdown_socket_out),
            daemon=True,
        )
        self.thread.start()
        self._wait_for_startup()

        # Create the user principal collection (Radicale needs it before MKCALENDAR)
        user_url = f"http://{self.host}:{self.port}/{self.username}/"
        try:
            r = requests.request("MKCOL", user_url, timeout=5)
            if r.status_code not in (200, 201, 204, 405):
                requests.request("MKCOL", user_url.rstrip("/"), timeout=5)
        except Exception:
            pass

        self._started = True

    def stop(self) -> None:
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
        self._was_stopped = True
