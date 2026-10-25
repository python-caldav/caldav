"""
Base classes for test servers.

This module provides abstract base classes for different types of test servers:
- TestServer: Abstract base for all test servers
- EmbeddedTestServer: For servers that run in-process (Radicale, Xandikos)
- DockerTestServer: For servers that run in Docker containers
"""

import os
import threading
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any

from caldav.config import get_test_setting


def docker_servers_dir() -> Path:
    """Directory holding the per-server ``start.sh``/``docker-compose.yml`` files.

    These stay in the source repository, not in the installed package.  Point
    ``CALDAV_DOCKER_TEST_SERVERS_DIR`` at ``tests/docker-test-servers`` of a
    checkout to use them from an installed caldav; without it, the directory is
    looked up relative to the module (found when caldav is a source checkout).
    """
    env = os.environ.get("CALDAV_DOCKER_TEST_SERVERS_DIR")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent.parent.parent / "tests" / "docker-test-servers"


from caldav.lib.http_sync import requests

# Constants - extracted from magic numbers in conf.py
DEFAULT_HTTP_TIMEOUT = 5
MAX_STARTUP_WAIT_SECONDS = 60
STARTUP_POLL_INTERVAL = 0.05
SESSION_LOCK_TIMEOUT_SECONDS = 1800

# Per-server session locks held by this process, keyed by server name.
# flock conflicts between two opens even within one process, so each
# lock file is opened only once.
_session_locks: dict[str, IO[str]] = {}
# Servers whose lock timed out; later claims fail at once instead of
# waiting again for every remaining test.
_session_lock_failures: dict[str, RuntimeError] = {}
_session_locks_mutex = threading.Lock()


def _lock_path(name: str, suffix: str = "") -> Path:
    import tempfile

    return Path(tempfile.gettempdir()) / f"caldav-test-server-{name.lower()}{suffix}.lock"


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

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """
        Initialize a test server.

        Args:
            config: Configuration dict with server-specific options.
                    Common keys: host, port, username, password, features
        """
        self.config = config or {}
        self.name = self.config.get("name", self.__class__.__name__.replace("TestServer", ""))
        self._started = False
        self._started_by_us = False  # Track if we started the server or it was already running

    @property
    @abstractmethod
    def url(self) -> str:
        """Return the CalDAV endpoint URL."""
        pass

    @property
    def username(self) -> str | None:
        """Return the username for authentication."""
        # Support both test config format and main caldav config format
        return (
            self.config.get("username")
            or self.config.get("caldav_username")
            or self.config.get("caldav_user")
        )

    @property
    def password(self) -> str | None:
        """Return the password for authentication."""
        # Support both test config format and main caldav config format
        # Check explicitly for keys since empty string is valid
        for key in ("password", "caldav_password", "caldav_pass"):
            if key in self.config:
                return self.config[key]
        return None

    # Default priority per server type.  Lower number = higher priority.
    # Subclasses (embedded=10, docker=20, external=30) override this.
    _default_priority: int = 50

    @property
    def priority(self) -> int:
        """Return the sort priority for this server.

        Lower values are returned first by the registry.  Can be overridden
        per-server via ``test_priority: <int>`` in the server config.
        """
        return int(get_test_setting(self.config, "test_priority", self._default_priority))

    @property
    def features(self) -> Any:
        """
        Return compatibility features for this server.

        This can be a dict of feature flags or a reference to a
        compatibility hints object.  The "base" key (if present) is
        resolved here via config.resolve_features().
        """
        from caldav.config import resolve_features

        return resolve_features(self.config.get("features", []))

    @staticmethod
    def claim_server(name: str, timeout: float | None = None) -> bool:
        """Take an exclusive lock on server ``name`` for the rest of this process.

        Test runs sharing a server would clobber each other's calendars (and
        one run's teardown may stop a container another run still uses), so
        a second process waits here until the first one exits.  Runs against
        different servers proceed in parallel.  The OS drops the lock when
        the process dies, so a crashed run leaves nothing stale behind.

        Waits at most ``timeout`` seconds (default
        ``$PYTHON_CALDAV_TEST_SERVER_LOCK_TIMEOUT``, or 30 minutes) - two runs
        taking servers in different orders could otherwise deadlock.  A
        timeout is remembered, so the remaining tests for that server fail
        at once - except with ``timeout=0``, a mere probe.

        Returns True if the lock was taken just now, False if this process
        already held it.  Anything learned about the server before a fresh
        claim may be stale, since its previous user may have stopped it.

        Without ``fcntl`` (Windows) nothing is locked between processes.
        """
        import time

        try:
            import fcntl
        except ImportError:
            fcntl = None  # type: ignore[assignment]

        with _session_locks_mutex:
            if name in _session_locks:
                return False
            if name in _session_lock_failures:
                raise _session_lock_failures[name]
            if timeout is None:
                timeout = float(
                    os.environ.get(
                        "PYTHON_CALDAV_TEST_SERVER_LOCK_TIMEOUT", SESSION_LOCK_TIMEOUT_SECONDS
                    )
                )
            lock_file = open(_lock_path(name, ".session"), "a+")
            try:
                deadline = time.monotonic() + timeout
                announced = False
                while fcntl:
                    try:
                        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        lock_file.seek(0)
                        holder = lock_file.read().strip() or "unknown"
                        if time.monotonic() > deadline:
                            error = RuntimeError(
                                f"Test server {name} is in use by pid {holder}; "
                                f"gave up after {timeout:.0f}s"
                            )
                            if timeout:
                                _session_lock_failures[name] = error
                            raise error from None
                        if not announced:
                            print(f"[WAIT] {name} is in use by pid {holder} - waiting")
                            announced = True
                        time.sleep(1)
                lock_file.truncate(0)
                lock_file.write(str(os.getpid()))
                lock_file.flush()
            except BaseException:
                lock_file.close()
                raise
            _session_locks[name] = lock_file
            return True

    @staticmethod
    def release_server(name: str) -> None:
        """Give up a claim taken by ``claim_server()``, letting other runs have the server."""
        with _session_locks_mutex:
            lock_file = _session_locks.pop(name, None)
        if lock_file:
            lock_file.close()

    def claim(self) -> bool:
        """``claim_server()`` for this server."""
        return self.claim_server(self.name)

    @abstractmethod
    def start(self) -> None:
        """
        Start the server if not already running.

        Implementations must call ``self.claim()`` first.

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

        kwargs: dict[str, Any] = {
            "url": self.url,
            "username": self.username,
            "password": self.password,
            "features": self.features,
        }
        if "ssl_verify_cert" in self.config:
            kwargs["ssl_verify_cert"] = self.config["ssl_verify_cert"]
        client = DAVClient(**kwargs)
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

        kwargs: dict[str, Any] = {
            "url": self.url,
            "username": self.username,
            "password": self.password,
            "features": self.features,
            "probe": False,  # We already checked accessibility
        }
        if "ssl_verify_cert" in self.config:
            kwargs["ssl_verify_cert"] = self.config["ssl_verify_cert"]
        return await get_async_davclient(**kwargs)

    def get_server_params(self) -> dict[str, Any]:
        """
        Get parameters dict compatible with current caldav_servers format.

        This allows the new test server framework to work with the
        existing test infrastructure during migration.

        Returns:
            Dict with keys: name, url, username, password, features, setup, teardown
        """
        params: dict[str, Any] = {
            "name": self.name,
            "url": self.url,
            "username": self.username,
            "password": self.password,
            "features": self.features,
        }
        # Pass through SSL verification setting if configured
        if "ssl_verify_cert" in self.config:
            params["ssl_verify_cert"] = self.config["ssl_verify_cert"]
        # Pass through scheduling_users if configured (for TestScheduling generation)
        if "scheduling_users" in self.config:
            params["scheduling_users"] = self.config["scheduling_users"]
        # setup is always needed, since start() also takes the session lock
        params["setup"] = lambda _: self.start()
        # Check if server is already running (either started by us or externally)
        already_running = self._started or self.is_accessible()
        if already_running:
            # Server is already running - mark as started but don't add teardown
            # to avoid stopping a server that was running before tests started
            self._started = True
        else:
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
    _default_priority = 10

    def __init__(self, config: dict[str, Any] | None = None) -> None:
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

        raise RuntimeError(f"{self.name} failed to start after {MAX_STARTUP_WAIT_SECONDS} seconds")


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
    _default_priority = 20

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.host = self.config.get("host", "localhost")
        self.port = self.config.get("port", self._default_port())

        # Docker directory - default to tests/docker-test-servers/<name>
        from pathlib import Path

        default_docker_dir = docker_servers_dir() / self.name.lower()
        self.docker_dir = Path(self.config.get("docker_dir", default_docker_dir))
        # Set when start() fails, so later tests fail fast instead of
        # re-running start.sh and waiting for the full timeout every time.
        self._start_error: Exception | None = None

    def _default_port(self) -> int:
        """Return the default port for this server type."""
        return 8800  # Override in subclasses

    @staticmethod
    def verify_docker() -> bool:
        """
        Check if docker and docker-compose are available.

        Returns:
            True if docker compose is available and docker daemon is running
        """
        import subprocess

        def _run(*cmd: str) -> bool:
            try:
                subprocess.run(list(cmd), capture_output=True, check=True, timeout=5)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                return False

        # start.sh scripts use the standalone `docker-compose` binary, so we
        # only return True when that binary is actually present.  The `docker
        # compose` plugin form is NOT sufficient — start.sh will exit 127 if
        # only the plugin is available (e.g. on GitHub Actions runners).
        return _run("docker-compose", "--version") and _run("docker", "ps")

    def start(self) -> None:
        """
        Start the Docker container if not already running.

        If the server is already running (either from a previous test run or
        started externally), it will be reused without restarting.

        Raises:
            RuntimeError: If Docker is not available or container fails to start
        """
        if self.claim():
            # Whatever was seen before the lock (e.g. at collection) may be
            # stale: the previous holder may have stopped the container.
            self._started = False
        if self._started:
            return
        if self.is_accessible():
            self._started = True  # Mark as started even if already running
            # Don't set _started_by_us - we didn't start it this time
            print(f"[OK] {self.name} is already running")
            return

        if self._start_error is not None:
            raise RuntimeError(
                f"{self.name} previously failed to start: {self._start_error}"
            ) from self._start_error

        try:
            with self._lock():
                # Another process may have started it while we waited
                if self.is_accessible():
                    self._started = True
                    print(f"[OK] {self.name} was started by another process")
                    return
                self._start_container()
        except Exception as e:
            self._start_error = e
            raise

    @contextmanager
    def _lock(self) -> Iterator[None]:
        """Serialise start.sh/stop.sh for this server across processes.

        Keyed by server name rather than docker_dir, since clones of the
        repo share the same containers and ports.
        """
        import fcntl

        with open(_lock_path(self.name), "w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)

    def _start_container(self) -> None:
        import subprocess
        import time

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
                self._started_by_us = True  # We actually started this server
                return
            time.sleep(1)

        raise RuntimeError(f"{self.name} failed to start after {MAX_STARTUP_WAIT_SECONDS}s")

    def get_server_params(self) -> dict[str, Any]:
        params = super().get_server_params()
        # A run that waited for the lock may have restarted a container that
        # was up at collection; stop() leaves alone one we did not start.
        params["teardown"] = lambda _: self.stop()
        return params

    def stop(self) -> None:
        """Stop the Docker container and cleanup.

        Only stops the server if it was started by us (not externally).
        This allows running servers to be reused across test runs.
        """
        import subprocess

        if not self._started_by_us:
            # Server was already running before we started - don't stop it
            print(f"[OK] {self.name} was already running - leaving it running")
            return

        stop_script = self.docker_dir / "stop.sh"
        if stop_script.exists():
            print(f"Stopping {self.name}...")
            with self._lock():
                subprocess.run(
                    [str(stop_script)],
                    cwd=self.docker_dir,
                    check=True,
                    capture_output=True,
                )
        self._started = False
        self._started_by_us = False

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

    The URL can be provided directly via the 'url' config key, or constructed
    from the 'auto-connect.url' feature (with domain, scheme, basepath keys).
    """

    server_type = "external"
    _default_priority = 30

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._url = self._construct_url()

    def _construct_url(self) -> str:
        """Get explicit URL from config, if any.

        URL resolution from features (auto-connect.url) is handled by
        the DAVClient constructor via _auto_url() - not duplicated here.
        """
        return self.config.get("url") or self.config.get("caldav_url") or ""

    @property
    def url(self) -> str:
        return self._url

    def start(self) -> None:
        """External servers are already running - just mark as started."""
        # No accessibility check here - the caldav library handles URL
        # normalization, RFC6764 discovery, and will provide proper error
        # messages if the server is unreachable
        self.claim()
        self._started = True

    def stop(self) -> None:
        """External servers stay running - nothing to do."""
        self._started = False
        self._started_by_us = False

    def is_accessible(self) -> bool:
        """Check that the server's host accepts TCP connections on its port.

        A URL without a path is resolved from the features (auto-connect.url)
        without RFC6764 discovery.  Authentication, TLS and DAV support are
        left for the caldav library to report.
        """
        import socket
        from urllib.parse import urlsplit

        from caldav.base_client import _auto_url

        try:
            url, _ = _auto_url(self.url, self.features or {}, enable_rfc6764=False)
            parts = urlsplit(str(url))
            port = parts.port or (443 if parts.scheme == "https" else 80)
            if not parts.hostname:
                return False
            with socket.create_connection((parts.hostname, port), timeout=DEFAULT_HTTP_TIMEOUT):
                return True
        except (OSError, ValueError):
            return False
