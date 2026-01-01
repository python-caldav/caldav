"""
Base classes for test servers.

This module provides abstract base classes for different types of test servers:
- TestServer: Abstract base for all test servers
- EmbeddedTestServer: For servers that run in-process (Radicale, Xandikos)
- DockerTestServer: For servers that run in Docker containers
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

try:
    import niquests as requests
except ImportError:
    import requests  # type: ignore

# Constants - extracted from magic numbers in conf.py
DEFAULT_HTTP_TIMEOUT = 5
MAX_STARTUP_WAIT_SECONDS = 60
STARTUP_POLL_INTERVAL = 0.05


class TestServer(ABC):
    """
    Abstract base class for all test servers.

    A test server provides a CalDAV endpoint for running tests. It can be:
    - An embedded server running in-process (Radicale, Xandikos)
    - A Docker container (Baikal, Nextcloud, etc.)
    - An external server (user-configured private servers)

    Attributes:
        name: Human-readable name for the server (used in test class names)
        server_type: Type of server ("embedded", "docker", "external")
        config: Configuration dict for the server
    """

    name: str = "TestServer"
    server_type: str = "abstract"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize a test server.

        Args:
            config: Configuration dict with server-specific options.
                    Common keys: host, port, username, password, features
        """
        self.config = config or {}
        self.name = self.config.get("name", self.__class__.__name__.replace("TestServer", ""))
        self._started = False

    @property
    @abstractmethod
    def url(self) -> str:
        """Return the CalDAV endpoint URL."""
        pass

    @property
    def username(self) -> Optional[str]:
        """Return the username for authentication."""
        return self.config.get("username")

    @property
    def password(self) -> Optional[str]:
        """Return the password for authentication."""
        return self.config.get("password")

    @property
    def features(self) -> Any:
        """
        Return compatibility features for this server.

        This can be a dict of feature flags or a reference to a
        compatibility hints object.
        """
        return self.config.get("features", [])

    @abstractmethod
    def start(self) -> None:
        """
        Start the server if not already running.

        This method should be idempotent - calling it multiple times
        should not cause issues.

        Raises:
            RuntimeError: If the server fails to start
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """
        Stop the server and cleanup resources.

        This method should be idempotent - calling it multiple times
        should not cause issues.
        """
        pass

    @abstractmethod
    def is_accessible(self) -> bool:
        """
        Check if the server is accessible and ready for requests.

        Returns:
            True if the server is responding to HTTP requests
        """
        pass

    def get_sync_client(self) -> "DAVClient":
        """
        Get a synchronous DAVClient for this server.

        Returns:
            DAVClient configured for this server
        """
        from caldav.davclient import DAVClient

        client = DAVClient(
            url=self.url,
            username=self.username,
            password=self.password,
        )
        client.server_name = self.name
        # Attach no-op setup/teardown by default
        client.setup = lambda self_: None
        client.teardown = lambda self_: None
        return client

    async def get_async_client(self) -> "AsyncDAVClient":
        """
        Get an async DAVClient for this server.

        Returns:
            AsyncDAVClient configured for this server
        """
        from caldav.aio import get_async_davclient

        return await get_async_davclient(
            url=self.url,
            username=self.username,
            password=self.password,
            probe=False,  # We already checked accessibility
        )

    def get_server_params(self) -> Dict[str, Any]:
        """
        Get parameters dict compatible with current caldav_servers format.

        This allows the new test server framework to work with the
        existing test infrastructure during migration.

        Returns:
            Dict with keys: name, url, username, password, features, setup, teardown
        """
        params: Dict[str, Any] = {
            "name": self.name,
            "url": self.url,
            "username": self.username,
            "password": self.password,
            "features": self.features,
        }
        if not self._started:
            params["setup"] = lambda _: self.start()
            params["teardown"] = lambda _: self.stop()
        return params

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, url={self.url!r})"


class EmbeddedTestServer(TestServer):
    """
    Base class for servers that run in-process.

    Embedded servers (like Radicale and Xandikos) run in a separate thread
    within the test process. They use temporary directories for storage
    and are automatically cleaned up when stopped.

    Attributes:
        host: Host to bind to (default: "localhost")
        port: Port to bind to (server-specific default)
    """

    server_type = "embedded"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self.host = self.config.get("host", "localhost")
        self.port = self.config.get("port", self._default_port())

    def _default_port(self) -> int:
        """Return the default port for this server type."""
        return 5232  # Override in subclasses

    @property
    def url(self) -> str:
        """Return the CalDAV endpoint URL."""
        username = self.username or ""
        return f"http://{self.host}:{self.port}/{username}"

    def _wait_for_startup(self) -> None:
        """
        Wait for the server to become accessible.

        Raises:
            RuntimeError: If server doesn't start within MAX_STARTUP_WAIT_SECONDS
        """
        import time

        attempts = int(MAX_STARTUP_WAIT_SECONDS / STARTUP_POLL_INTERVAL)
        for _ in range(attempts):
            if self.is_accessible():
                return
            time.sleep(STARTUP_POLL_INTERVAL)

        raise RuntimeError(
            f"{self.name} failed to start after {MAX_STARTUP_WAIT_SECONDS} seconds"
        )


class DockerTestServer(TestServer):
    """
    Base class for Docker-based test servers.

    Docker servers run in containers managed by docker-compose.
    They expect a docker_dir with start.sh and stop.sh scripts.

    Attributes:
        docker_dir: Path to the directory containing docker-compose.yml
        host: Host where the container is accessible (default: "localhost")
        port: Port where the container is accessible
    """

    server_type = "docker"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self.host = self.config.get("host", "localhost")
        self.port = self.config.get("port", self._default_port())

        # Docker directory - default to tests/docker-test-servers/<name>
        from pathlib import Path

        default_docker_dir = (
            Path(__file__).parent.parent / "docker-test-servers" / self.name.lower()
        )
        self.docker_dir = Path(self.config.get("docker_dir", default_docker_dir))

    def _default_port(self) -> int:
        """Return the default port for this server type."""
        return 8800  # Override in subclasses

    @staticmethod
    def verify_docker() -> bool:
        """
        Check if docker and docker-compose are available.

        Returns:
            True if docker-compose is available and docker daemon is running
        """
        import subprocess

        try:
            subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def start(self) -> None:
        """
        Start the Docker container if not already running.

        Raises:
            RuntimeError: If Docker is not available or container fails to start
        """
        import subprocess
        import time

        if self._started or self.is_accessible():
            print(f"[OK] {self.name} is already running")
            return

        if not self.verify_docker():
            raise RuntimeError(f"Docker not available for {self.name}")

        start_script = self.docker_dir / "start.sh"
        if not start_script.exists():
            raise FileNotFoundError(f"{start_script} not found")

        print(f"Starting {self.name} from {self.docker_dir}...")
        subprocess.run(
            [str(start_script)],
            cwd=self.docker_dir,
            check=True,
            capture_output=True,
        )

        # Wait for server to become accessible
        for _ in range(MAX_STARTUP_WAIT_SECONDS):
            if self.is_accessible():
                print(f"[OK] {self.name} is ready")
                self._started = True
                return
            time.sleep(1)

        raise RuntimeError(
            f"{self.name} failed to start after {MAX_STARTUP_WAIT_SECONDS}s"
        )

    def stop(self) -> None:
        """Stop the Docker container and cleanup."""
        import subprocess

        stop_script = self.docker_dir / "stop.sh"
        if stop_script.exists():
            subprocess.run(
                [str(stop_script)],
                cwd=self.docker_dir,
                check=True,
                capture_output=True,
            )
        self._started = False

    def is_accessible(self) -> bool:
        """Check if the Docker container is accessible."""
        try:
            response = requests.get(f"{self.url}/", timeout=DEFAULT_HTTP_TIMEOUT)
            return response.status_code in (200, 401, 403, 404)
        except Exception:
            return False


class ExternalTestServer(TestServer):
    """
    Test server for external/user-configured servers.

    External servers are already running somewhere - we don't start or stop them.
    This is used for testing against real CalDAV servers configured by the user.
    """

    server_type = "external"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self._url = self.config.get("url", "")

    @property
    def url(self) -> str:
        return self._url

    def start(self) -> None:
        """External servers are already running - nothing to do."""
        if not self.is_accessible():
            raise RuntimeError(f"External server {self.name} at {self.url} is not accessible")
        self._started = True

    def stop(self) -> None:
        """External servers stay running - nothing to do."""
        self._started = False

    def is_accessible(self) -> bool:
        """Check if the external server is accessible."""
        try:
            response = requests.get(self.url, timeout=DEFAULT_HTTP_TIMEOUT)
            return response.status_code in (200, 401, 403, 404)
        except Exception:
            return False
