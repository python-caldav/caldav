"""
Server registry for test server discovery and management.

This module provides a registry for discovering and managing test servers.
It supports automatic detection of available servers and lazy initialization.
"""

from .base import TestServer

# Server class registry - maps type names to server classes
_SERVER_CLASSES: dict[str, type[TestServer]] = {}


def register_server_class(type_name: str, server_class: type[TestServer]) -> None:
    """
    Register a server class for a given type name.

    Args:
        type_name: The type identifier (e.g., "radicale", "baikal")
        server_class: The TestServer subclass
    """
    _SERVER_CLASSES[type_name] = server_class


def get_server_class(type_name: str) -> type[TestServer] | None:
    """
    Get the server class for a given type name.

    Args:
        type_name: The type identifier

    Returns:
        The TestServer subclass, or None if not found
    """
    return _SERVER_CLASSES.get(type_name)


class ServerRegistry:
    """
    Registry for test server discovery and management.

    The registry maintains a collection of test servers and provides
    methods for discovering, starting, and stopping them.

    Usage:
        registry = ServerRegistry()
        registry.auto_discover()  # Detect available servers

        for server in registry.all_servers():
            server.start()
            # ... run tests ...
            server.stop()
    """

    def __init__(self) -> None:
        self._servers: dict[str, TestServer] = {}

    def register(self, server: TestServer) -> None:
        """
        Register a test server.

        Args:
            server: The test server instance to register
        """
        self._servers[server.name] = server

    def unregister(self, name: str) -> TestServer | None:
        """
        Unregister a test server by name.

        Args:
            name: The server name

        Returns:
            The removed server, or None if not found
        """
        return self._servers.pop(name, None)

    def get(self, name: str) -> TestServer | None:
        """
        Get a test server by name.

        Args:
            name: The server name

        Returns:
            The server instance, or None if not found
        """
        return self._servers.get(name)

    def all_servers(self) -> list[TestServer]:
        """
        Get all registered test servers.

        Returns:
            List of all registered servers
        """
        return list(self._servers.values())

    def enabled_servers(self) -> list[TestServer]:
        """
        Get all enabled test servers.

        Returns:
            List of servers where config.get("enabled", True) is True
        """
        return [s for s in self._servers.values() if s.config.get("enabled", True)]

    def load_from_config(self, config: dict) -> None:
        """
        Load servers from a configuration dict.

        The config should be a dict mapping server names to their configs:
        {
            "radicale": {"type": "embedded", "port": 5232, ...},
            "baikal": {"type": "docker", "port": 8800, ...},
        }

        Args:
            config: Configuration dict

        Raises:
            ValueError: If a server configuration is invalid
        """
        import warnings

        for name, server_config in config.items():
            if not isinstance(server_config, dict):
                raise ValueError(
                    f"Server '{name}': configuration must be a dict, "
                    f"got {type(server_config).__name__}"
                )

            if not server_config.get("enabled", True):
                continue

            server_type = server_config.get("type", name)
            server_class = get_server_class(server_type)

            if server_class is None:
                # Try to find by name if type not found
                server_class = get_server_class(name)

            if server_class is None:
                warnings.warn(
                    f"Server '{name}': unknown type '{server_type}'. "
                    f"Valid types: embedded, docker, external, radicale, xandikos, "
                    f"baikal, nextcloud, cyrus, sogo, bedework. "
                    f"Server will be skipped.",
                    UserWarning,
                    stacklevel=2,
                )
                continue

            try:
                server_config["name"] = name
                server = server_class(server_config)
                self.register(server)
            except Exception as e:
                raise ValueError(f"Server '{name}': failed to create server instance: {e}") from e

    def auto_discover(self) -> None:
        """
        Automatically discover and register available test servers.

        This checks for:
        - Radicale (if radicale package is installed)
        - Xandikos (if xandikos package is installed)
        - Docker servers (if docker-compose is available)
        """
        # Import server implementations to trigger registration
        try:
            from . import embedded
        except ImportError:
            pass

        try:
            from . import docker
        except ImportError:
            pass

        # Discover embedded servers
        self._discover_embedded_servers()

        # Discover Docker servers
        self._discover_docker_servers()

    def _discover_embedded_servers(self) -> None:
        """Discover available embedded servers."""
        # Check for Radicale
        try:
            import radicale  # noqa: F401

            radicale_class = get_server_class("radicale")
            if radicale_class is not None:
                self.register(radicale_class())
        except ImportError:
            pass

        # Check for Xandikos
        try:
            import xandikos  # noqa: F401

            xandikos_class = get_server_class("xandikos")
            if xandikos_class is not None:
                self.register(xandikos_class())
        except ImportError:
            pass

    def _discover_docker_servers(self) -> None:
        """Discover available Docker servers."""
        from pathlib import Path

        from .base import DockerTestServer

        if not DockerTestServer.verify_docker():
            return

        # Look for docker-test-servers directories
        docker_servers_dir = Path(__file__).parent.parent / "docker-test-servers"
        if not docker_servers_dir.exists():
            return

        # Check each subdirectory for a start.sh script
        for server_dir in docker_servers_dir.iterdir():
            if server_dir.is_dir() and (server_dir / "start.sh").exists():
                server_name = server_dir.name
                server_class = get_server_class(server_name)

                if server_class is not None and server_name not in self._servers:
                    self.register(server_class({"docker_dir": str(server_dir)}))

    def get_caldav_servers_list(self) -> list[dict]:
        """
        Return list compatible with current caldav_servers format.

        This is for backwards compatibility with the existing test infrastructure.

        Returns:
            List of server parameter dicts
        """
        return [s.get_server_params() for s in self.enabled_servers()]


# Global registry instance
_global_registry: ServerRegistry | None = None


def get_registry() -> ServerRegistry:
    """
    Get the global server registry instance.

    Creates the registry on first call, runs auto-discovery, and loads
    configuration from the config file (if present).

    Returns:
        The global ServerRegistry instance

    Raises:
        ConfigParseError: If the config file exists but cannot be parsed
        ValueError: If the config has invalid server definitions
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ServerRegistry()
        _global_registry.auto_discover()

        # Load configuration from config file
        # Let ConfigParseError and ValueError propagate - these are real errors
        from .config_loader import ConfigParseError, load_test_server_config

        try:
            config = load_test_server_config()
            if config:
                _global_registry.load_from_config(config)
        except ConfigParseError:
            # Re-raise config parse errors - these should fail loudly
            raise
        except Exception as e:
            # Log unexpected errors but don't silently ignore them
            import warnings

            warnings.warn(
                f"Failed to load test server configuration: {e}. "
                "Check tests/caldav_test_servers.yaml for errors.",
                UserWarning,
                stacklevel=2,
            )

    return _global_registry


def get_available_servers() -> list[TestServer]:
    """
    Get all available test servers.

    Convenience function that returns enabled servers from the global registry.

    Returns:
        List of available test servers
    """
    return get_registry().enabled_servers()
