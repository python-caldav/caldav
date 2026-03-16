"""
Embedded test server implementations for the test infrastructure.

The actual server logic lives in caldav/testing.py (part of the installed
package).  This module wraps those classes so they fit into the
EmbeddedTestServer hierarchy and are registered with the server registry.
"""

from typing import Any

from caldav.testing import RadicaleServer as _RadicaleCore
from caldav.testing import XandikosServer as _XandikosCore

from .base import EmbeddedTestServer
from .registry import register_server_class


class XandikosTestServer(EmbeddedTestServer):
    """Xandikos server wrapped for the test infrastructure."""

    name = "Xandikos"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", "localhost")
        config.setdefault("port", 8993)
        config.setdefault("username", "sometestuser")
        super().__init__(config)
        self._core = _XandikosCore(config)

    def _default_port(self) -> int:
        return 8993

    @property
    def url(self) -> str:
        return self._core.url

    def is_accessible(self) -> bool:
        return self._core.is_accessible()

    def start(self) -> None:
        self._core.start()
        self._started = self._core._started

    def stop(self) -> None:
        self._core.stop()
        self._started = self._core._started
        self._was_stopped = self._core._was_stopped


class RadicaleTestServer(EmbeddedTestServer):
    """Radicale server wrapped for the test infrastructure."""

    name = "Radicale"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", "localhost")
        config.setdefault("port", 5232)
        config.setdefault("username", "user1")
        config.setdefault("password", "")
        super().__init__(config)
        self._core = _RadicaleCore(config)

    def _default_port(self) -> int:
        return 5232

    @property
    def url(self) -> str:
        return self._core.url

    def is_accessible(self) -> bool:
        return self._core.is_accessible()

    def start(self) -> None:
        self._core.start()
        self._started = self._core._started

    def stop(self) -> None:
        self._core.stop()
        self._started = self._core._started
        self._was_stopped = self._core._was_stopped


# Register server classes
register_server_class("radicale", RadicaleTestServer)
register_server_class("xandikos", XandikosTestServer)
