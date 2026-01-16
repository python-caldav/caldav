"""
Base class for DAV clients.

This module contains the BaseDAVClient class which provides shared
functionality for both sync (DAVClient) and async (AsyncDAVClient) clients.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Mapping, Optional

from caldav.lib import error
from caldav.lib.auth import extract_auth_types, select_auth_type

if TYPE_CHECKING:
    from caldav.compatibility_hints import FeatureSet


class BaseDAVClient(ABC):
    """
    Base class for DAV clients providing shared authentication and configuration logic.

    This abstract base class contains common functionality used by both
    DAVClient (sync) and AsyncDAVClient (async). Subclasses must implement
    the abstract methods for their specific HTTP library.

    Shared functionality:
    - Authentication type extraction and selection
    - Feature set management
    - Common properties (username, password, auth_type, etc.)
    """

    # Common attributes that subclasses will set
    username: Optional[str] = None
    password: Optional[str] = None
    auth: Optional[Any] = None
    auth_type: Optional[str] = None
    features: Optional["FeatureSet"] = None

    def extract_auth_types(self, header: str) -> set[str]:
        """Extract authentication types from WWW-Authenticate header.

        Parses the WWW-Authenticate header value and extracts the
        authentication scheme names (e.g., "basic", "digest", "bearer").

        Args:
            header: WWW-Authenticate header value from server response.

        Returns:
            Set of lowercase auth type strings.

        Example:
            >>> client.extract_auth_types('Basic realm="test", Digest realm="test"')
            {'basic', 'digest'}
        """
        return extract_auth_types(header)

    def _select_auth_type(
        self, auth_types: Optional[list[str]] = None
    ) -> Optional[str]:
        """
        Select the best authentication type from available options.

        This method implements the shared logic for choosing an auth type
        based on configured credentials and server-supported types.

        Args:
            auth_types: List of acceptable auth types from server.

        Returns:
            Selected auth type string, or None if no suitable type found.

        Raises:
            AuthorizationError: If configuration conflicts with server capabilities.
        """
        auth_type = self.auth_type

        if not auth_type and not auth_types:
            raise error.AuthorizationError(
                "No auth-type given. This shouldn't happen. "
                "Raise an issue at https://github.com/python-caldav/caldav/issues/"
            )

        if auth_types and auth_type and auth_type not in auth_types:
            raise error.AuthorizationError(
                reason=f"Configuration specifies to use {auth_type}, "
                f"but server only accepts {auth_types}"
            )

        if not auth_type and auth_types:
            # Use shared selection logic from lib/auth
            auth_type = select_auth_type(
                auth_types,
                has_username=bool(self.username),
                has_password=bool(self.password),
            )

            # Handle bearer token without password
            if not auth_type and "bearer" in auth_types and not self.password:
                raise error.AuthorizationError(
                    reason="Server provides bearer auth, but no password given. "
                    "The bearer token should be configured as password"
                )

        return auth_type

    @abstractmethod
    def build_auth_object(self, auth_types: Optional[list[str]] = None) -> None:
        """
        Build authentication object based on configured credentials.

        This method must be implemented by subclasses to create the
        appropriate auth object for their HTTP library (requests, httpx, etc.).

        Args:
            auth_types: List of acceptable auth types from server.
        """
        pass


def create_client_from_config(
    client_class: type,
    check_config_file: bool = True,
    config_file: Optional[str] = None,
    config_section: Optional[str] = None,
    testconfig: bool = False,
    environment: bool = True,
    name: Optional[str] = None,
    **config_data,
) -> Optional[Any]:
    """
    Create a DAV client using configuration from multiple sources.

    This is a shared helper for both sync and async get_davclient functions.
    It reads configuration from various sources in priority order:

    1. Explicit parameters (url=, username=, password=, etc.)
    2. Test server config (if testconfig=True or PYTHON_CALDAV_USE_TEST_SERVER env var)
    3. Environment variables (CALDAV_URL, CALDAV_USERNAME, etc.)
    4. Config file (CALDAV_CONFIG_FILE env var or default locations)

    Args:
        client_class: The client class to instantiate (DAVClient or AsyncDAVClient).
        check_config_file: Whether to look for config files.
        config_file: Explicit path to config file.
        config_section: Section name in config file.
        testconfig: Whether to use test server configuration.
        environment: Whether to read from environment variables.
        name: Name of test server to use.
        **config_data: Explicit connection parameters.

    Returns:
        Client instance, or None if no configuration is found.
    """
    from caldav import config

    # Use unified config discovery
    conn_params = config.get_connection_params(
        check_config_file=check_config_file,
        config_file=config_file,
        config_section=config_section,
        testconfig=testconfig,
        environment=environment,
        name=name,
        **config_data,
    )

    if conn_params is None:
        return None

    # Extract special keys that aren't connection params
    setup_func = conn_params.pop("_setup", None)
    teardown_func = conn_params.pop("_teardown", None)
    server_name = conn_params.pop("_server_name", None)

    # Create client
    client = client_class(**conn_params)

    # Attach test server metadata if present
    if setup_func is not None:
        client.setup = setup_func
    if teardown_func is not None:
        client.teardown = teardown_func
    if server_name is not None:
        client.server_name = server_name

    return client
