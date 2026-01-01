"""
Configuration loader for test servers.

This module provides functions for loading test server configuration
from YAML/JSON files, with fallback to the legacy conf_private.py.
"""

import os
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

from caldav.config import read_config, expand_env_vars

# Default config file locations (in priority order)
DEFAULT_CONFIG_LOCATIONS = [
    "tests/test_servers.yaml",
    "tests/test_servers.json",
    "~/.config/caldav/test_servers.yaml",
    "~/.config/caldav/test_servers.json",
]


def load_test_server_config(
    config_file: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Load test server configuration from file.

    Searches for config files in default locations and loads the first
    one found. Falls back to conf_private.py with a deprecation warning.

    Args:
        config_file: Optional explicit path to config file

    Returns:
        Dict mapping server names to their configuration dicts.
        Empty dict if no configuration found.

    Example config file (YAML):
        test-servers:
          radicale:
            type: embedded
            enabled: true
            port: 5232
          baikal:
            type: docker
            enabled: ${TEST_BAIKAL:-auto}
            url: http://localhost:8800/dav.php
    """
    # Try explicit config file first
    if config_file:
        cfg = read_config(config_file)
        if cfg:
            servers = cfg.get("test-servers", cfg)
            return expand_env_vars(servers)

    # Try default locations
    for loc in DEFAULT_CONFIG_LOCATIONS:
        path = Path(loc).expanduser()
        if path.exists():
            cfg = read_config(str(path))
            if cfg:
                servers = cfg.get("test-servers", cfg)
                return expand_env_vars(servers)

    # Fallback to conf_private.py with deprecation warning
    return _load_from_conf_private()


def _load_from_conf_private() -> Dict[str, Dict[str, Any]]:
    """
    Load configuration from legacy conf_private.py.

    This provides backwards compatibility during migration to
    the new YAML/JSON config format.

    Returns:
        Dict mapping server names to their configuration dicts.
        Empty dict if conf_private.py not found.
    """
    import sys

    original_path = sys.path.copy()
    try:
        sys.path.insert(0, "tests")
        sys.path.insert(1, ".")

        try:
            import conf_private

            warnings.warn(
                "conf_private.py is deprecated for test server configuration. "
                "Please migrate to tests/test_servers.yaml. "
                "See docs/testing.rst for the new format.",
                DeprecationWarning,
                stacklevel=3,
            )
            return _convert_conf_private_to_config(conf_private)
        except ImportError:
            return {}
    finally:
        sys.path = original_path


def _convert_conf_private_to_config(conf_private: Any) -> Dict[str, Dict[str, Any]]:
    """
    Convert conf_private.py format to new config format.

    Args:
        conf_private: The imported conf_private module

    Returns:
        Dict mapping server names to their configuration dicts
    """
    result: Dict[str, Dict[str, Any]] = {}

    # Convert caldav_servers list
    if hasattr(conf_private, "caldav_servers"):
        for i, server in enumerate(conf_private.caldav_servers):
            name = server.get("name", f"server_{i}")
            config: Dict[str, Any] = {
                "type": "external",
                "enabled": server.get("enable", True),
            }
            # Copy all other keys
            for key, value in server.items():
                if key not in ("enable", "name"):
                    config[key] = value
            result[name.lower().replace(" ", "_")] = config

    # Handle boolean enable/disable switches
    for attr in (
        "test_radicale",
        "test_xandikos",
        "test_baikal",
        "test_nextcloud",
        "test_cyrus",
        "test_sogo",
        "test_bedework",
    ):
        if hasattr(conf_private, attr):
            server_name = attr.replace("test_", "")
            if server_name not in result:
                result[server_name] = {"type": server_name}
            result[server_name]["enabled"] = getattr(conf_private, attr)

    # Handle host/port overrides
    for server_name in ("radicale", "xandikos", "baikal", "nextcloud", "cyrus", "sogo", "bedework"):
        host_attr = f"{server_name}_host"
        port_attr = f"{server_name}_port"

        if hasattr(conf_private, host_attr):
            if server_name not in result:
                result[server_name] = {"type": server_name}
            result[server_name]["host"] = getattr(conf_private, host_attr)

        if hasattr(conf_private, port_attr):
            if server_name not in result:
                result[server_name] = {"type": server_name}
            result[server_name]["port"] = getattr(conf_private, port_attr)

    return result


def create_example_config() -> str:
    """
    Generate an example config file content.

    Returns:
        YAML-formatted example configuration
    """
    return """# Test server configuration for caldav tests
# This file replaces the legacy conf_private.py

test-servers:
  # Embedded servers (run in-process)
  radicale:
    type: embedded
    enabled: true
    host: ${RADICALE_HOST:-localhost}
    port: ${RADICALE_PORT:-5232}
    username: user1
    password: ""

  xandikos:
    type: embedded
    enabled: true
    host: ${XANDIKOS_HOST:-localhost}
    port: ${XANDIKOS_PORT:-8993}
    username: sometestuser

  # Docker servers (require docker-compose)
  baikal:
    type: docker
    enabled: ${TEST_BAIKAL:-auto}  # "auto" means check if docker available
    host: ${BAIKAL_HOST:-localhost}
    port: ${BAIKAL_PORT:-8800}
    username: ${BAIKAL_USERNAME:-testuser}
    password: ${BAIKAL_PASSWORD:-testpass}

  nextcloud:
    type: docker
    enabled: ${TEST_NEXTCLOUD:-auto}
    host: ${NEXTCLOUD_HOST:-localhost}
    port: ${NEXTCLOUD_PORT:-8801}
    username: ${NEXTCLOUD_USERNAME:-testuser}
    password: ${NEXTCLOUD_PASSWORD:-TestPassword123!}

  cyrus:
    type: docker
    enabled: ${TEST_CYRUS:-auto}
    host: ${CYRUS_HOST:-localhost}
    port: ${CYRUS_PORT:-8802}
    username: ${CYRUS_USERNAME:-testuser@test.local}
    password: ${CYRUS_PASSWORD:-testpassword}

  sogo:
    type: docker
    enabled: ${TEST_SOGO:-auto}
    host: ${SOGO_HOST:-localhost}
    port: ${SOGO_PORT:-8803}
    username: ${SOGO_USERNAME:-testuser}
    password: ${SOGO_PASSWORD:-testpassword}

  bedework:
    type: docker
    enabled: ${TEST_BEDEWORK:-auto}
    host: ${BEDEWORK_HOST:-localhost}
    port: ${BEDEWORK_PORT:-8804}
    username: ${BEDEWORK_USERNAME:-admin}
    password: ${BEDEWORK_PASSWORD:-bedework}

  # External/private servers (user-configured)
  # Uncomment and configure for your own server:
  # my-server:
  #   type: external
  #   enabled: true
  #   url: ${CALDAV_URL}
  #   username: ${CALDAV_USERNAME}
  #   password: ${CALDAV_PASSWORD}
"""
