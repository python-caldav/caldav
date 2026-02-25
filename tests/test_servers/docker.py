"""
Docker-based test server implementations.

This module provides test server implementations for servers that run
in Docker containers: Baikal, Nextcloud, Cyrus, SOGo, Bedework, DAViCal, Davis, CCS, and Zimbra.
"""

import os
from typing import Any

try:
    import niquests as requests
except ImportError:
    import requests  # type: ignore

from caldav import compatibility_hints

from .base import DEFAULT_HTTP_TIMEOUT, DockerTestServer
from .registry import register_server_class


class BaikalTestServer(DockerTestServer):
    """
    Baikal CalDAV server in Docker.

    Baikal is a lightweight CalDAV/CardDAV server.
    """

    name = "Baikal"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", os.environ.get("BAIKAL_HOST", "localhost"))
        config.setdefault("port", int(os.environ.get("BAIKAL_PORT", "8800")))
        config.setdefault("username", os.environ.get("BAIKAL_USERNAME", "testuser"))
        config.setdefault("password", os.environ.get("BAIKAL_PASSWORD", "testpass"))
        # Set up Baikal-specific compatibility hints
        if "features" not in config:
            config["features"] = compatibility_hints.baikal.copy()
        super().__init__(config)

    def _default_port(self) -> int:
        return 8800

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/dav.php"


class NextcloudTestServer(DockerTestServer):
    """
    Nextcloud CalDAV server in Docker.

    Nextcloud is a self-hosted cloud platform with CalDAV support.
    """

    name = "Nextcloud"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", os.environ.get("NEXTCLOUD_HOST", "localhost"))
        config.setdefault("port", int(os.environ.get("NEXTCLOUD_PORT", "8801")))
        config.setdefault("username", os.environ.get("NEXTCLOUD_USERNAME", "testuser"))
        config.setdefault("password", os.environ.get("NEXTCLOUD_PASSWORD", "testpass"))
        # Set up Nextcloud-specific compatibility hints
        if "features" not in config:
            config["features"] = compatibility_hints.nextcloud.copy()
        super().__init__(config)

    def _default_port(self) -> int:
        return 8801

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/remote.php/dav"

    def is_accessible(self) -> bool:
        """Check if Nextcloud is accessible."""
        try:
            response = requests.get(f"{self.url}/", timeout=DEFAULT_HTTP_TIMEOUT)
            return response.status_code in (200, 207, 401, 403, 404)
        except Exception:
            return False


class CyrusTestServer(DockerTestServer):
    """
    Cyrus IMAP server with CalDAV support in Docker.

    Cyrus is a mail server that also supports CalDAV/CardDAV.
    """

    name = "Cyrus"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", os.environ.get("CYRUS_HOST", "localhost"))
        config.setdefault("port", int(os.environ.get("CYRUS_PORT", "8802")))
        config.setdefault("username", os.environ.get("CYRUS_USERNAME", "user1"))
        config.setdefault(
            "password", os.environ.get("CYRUS_PASSWORD", "any-password-seems-to-work")
        )
        # Set up Cyrus-specific compatibility hints
        if "features" not in config:
            config["features"] = compatibility_hints.cyrus.copy()
        super().__init__(config)

    def _default_port(self) -> int:
        return 8802

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/dav/calendars/user/{self.username}"

    def is_accessible(self) -> bool:
        """Check if Cyrus is accessible using PROPFIND."""
        try:
            response = requests.request(
                "PROPFIND",
                f"http://{self.host}:{self.port}/dav/",
                timeout=DEFAULT_HTTP_TIMEOUT,
            )
            return response.status_code in (200, 207, 401, 403, 404)
        except Exception:
            return False


class SOGoTestServer(DockerTestServer):
    """
    SOGo groupware server in Docker.

    SOGo is an open-source groupware server with CalDAV support.
    """

    name = "SOGo"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", os.environ.get("SOGO_HOST", "localhost"))
        config.setdefault("port", int(os.environ.get("SOGO_PORT", "8803")))
        config.setdefault("username", os.environ.get("SOGO_USERNAME", "testuser"))
        config.setdefault("password", os.environ.get("SOGO_PASSWORD", "testpass"))
        # Set up SOGo-specific compatibility hints
        if "features" not in config:
            config["features"] = compatibility_hints.sogo.copy()
        super().__init__(config)

    def _default_port(self) -> int:
        return 8803

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/SOGo/dav/{self.username}"

    def is_accessible(self) -> bool:
        """Check if SOGo is accessible using PROPFIND."""
        try:
            response = requests.request(
                "PROPFIND",
                f"http://{self.host}:{self.port}/SOGo/",
                timeout=DEFAULT_HTTP_TIMEOUT,
            )
            return response.status_code in (200, 207, 401, 403, 404)
        except Exception:
            return False


class BedeworkTestServer(DockerTestServer):
    """
    Bedework calendar server in Docker.

    Bedework is an enterprise-class open-source calendar system.
    """

    name = "Bedework"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", os.environ.get("BEDEWORK_HOST", "localhost"))
        config.setdefault("port", int(os.environ.get("BEDEWORK_PORT", "8804")))
        config.setdefault("username", os.environ.get("BEDEWORK_USERNAME", "vbede"))
        config.setdefault("password", os.environ.get("BEDEWORK_PASSWORD", "bedework"))
        # Set up Bedework-specific compatibility hints
        if "features" not in config:
            config["features"] = compatibility_hints.bedework.copy()
        super().__init__(config)

    def _default_port(self) -> int:
        return 8804

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/ucaldav/user/{self.username}"

    def is_accessible(self) -> bool:
        """Check if Bedework is accessible using PROPFIND."""
        try:
            response = requests.request(
                "PROPFIND",
                f"http://{self.host}:{self.port}/ucaldav/",
                timeout=DEFAULT_HTTP_TIMEOUT,
            )
            return response.status_code in (200, 207, 401, 403, 404)
        except Exception:
            return False


class DavicalTestServer(DockerTestServer):
    """
    DAViCal CalDAV server in Docker.

    DAViCal is a CalDAV server using PostgreSQL as its backend.
    It provides full CalDAV and CardDAV support.
    """

    name = "Davical"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", os.environ.get("DAVICAL_HOST", "localhost"))
        config.setdefault("port", int(os.environ.get("DAVICAL_PORT", "8805")))
        config.setdefault("username", os.environ.get("DAVICAL_USERNAME", "testuser"))
        config.setdefault("password", os.environ.get("DAVICAL_PASSWORD", "testpass"))
        if "features" not in config:
            config["features"] = compatibility_hints.davical.copy()
        super().__init__(config)

    def _default_port(self) -> int:
        return 8805

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/caldav.php/{self.username}/"

    def is_accessible(self) -> bool:
        """Check if DAViCal is accessible."""
        try:
            response = requests.request(
                "PROPFIND",
                f"http://{self.host}:{self.port}/caldav.php/",
                timeout=DEFAULT_HTTP_TIMEOUT,
            )
            return response.status_code in (200, 207, 401, 403, 404)
        except Exception:
            return False


class DavisTestServer(DockerTestServer):
    """
    Davis CalDAV server in Docker.

    Davis is a modern admin interface for sabre/dav, using Symfony 7.
    The standalone image bundles PHP-FPM + Caddy with SQLite.
    """

    name = "Davis"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", os.environ.get("DAVIS_HOST", "localhost"))
        config.setdefault("port", int(os.environ.get("DAVIS_PORT", "8806")))
        config.setdefault("username", os.environ.get("DAVIS_USERNAME", "testuser"))
        config.setdefault("password", os.environ.get("DAVIS_PASSWORD", "testpass"))
        if "features" not in config:
            config["features"] = compatibility_hints.davis.copy()
        super().__init__(config)

    def _default_port(self) -> int:
        return 8806

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/dav/"


class CCSTestServer(DockerTestServer):
    """
    Apple CalendarServer (CCS) in Docker.

    CCS is Apple's open-source CalDAV/CardDAV server (archived 2019).
    Uses UID-based principal URLs and XML-based directory service.
    """

    name = "CCS"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", os.environ.get("CCS_HOST", "localhost"))
        config.setdefault("port", int(os.environ.get("CCS_PORT", "8807")))
        config.setdefault("username", os.environ.get("CCS_USERNAME", "user01"))
        config.setdefault("password", os.environ.get("CCS_PASSWORD", "user01"))
        if "features" not in config:
            config["features"] = compatibility_hints.ccs.copy()
        super().__init__(config)

    def _default_port(self) -> int:
        return 8807

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/principals/"


class ZimbraTestServer(DockerTestServer):
    """
    Zimbra Collaboration Suite CalDAV server in Docker.

    Zimbra is a heavyweight server (~6GB RAM, ~10 min first startup).
    Uses HTTPS with a self-signed certificate.
    """

    name = "Zimbra"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        config.setdefault("host", os.environ.get("ZIMBRA_HOST", "zimbra-docker.zimbra.io"))
        config.setdefault("port", int(os.environ.get("ZIMBRA_PORT", "8808")))
        config.setdefault(
            "username",
            os.environ.get("ZIMBRA_USERNAME", "testuser@zimbra.io"),
        )
        config.setdefault("password", os.environ.get("ZIMBRA_PASSWORD", "testpass"))
        config.setdefault("ssl_verify_cert", False)
        if "features" not in config:
            config["features"] = compatibility_hints.zimbra.copy()
        super().__init__(config)

    def _default_port(self) -> int:
        return 8808

    @property
    def url(self) -> str:
        return f"https://{self.host}:{self.port}/dav/"

    def is_accessible(self) -> bool:
        """Check if Zimbra is accessible (HTTPS with self-signed cert)."""
        import warnings

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=Warning)
                response = requests.get(
                    f"https://{self.host}:{self.port}/",
                    timeout=DEFAULT_HTTP_TIMEOUT,
                    verify=False,
                )
            return response.status_code in (200, 301, 302, 401, 403, 404)
        except Exception:
            return False


# Register server classes
register_server_class("baikal", BaikalTestServer)
register_server_class("nextcloud", NextcloudTestServer)
register_server_class("cyrus", CyrusTestServer)
register_server_class("sogo", SOGoTestServer)
register_server_class("bedework", BedeworkTestServer)
register_server_class("davical", DavicalTestServer)
register_server_class("davis", DavisTestServer)
register_server_class("ccs", CCSTestServer)
register_server_class("zimbra", ZimbraTestServer)
