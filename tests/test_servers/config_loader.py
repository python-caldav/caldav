"""
Configuration loader for test servers.

This module loads test server configuration from:
1. Test-specific config files (tests/caldav_test_servers.yaml)
2. Main caldav config files with 'testing_allowed: true' sections
"""

from pathlib import Path
from typing import Any

from caldav.config import expand_env_vars, get_all_test_servers, read_config

# Test-specific config file locations (don't need testing_allowed)
TEST_CONFIG_LOCATIONS = [
    "tests/caldav_test_servers.yaml",
    "tests/caldav_test_servers.json",
    "~/.config/caldav/test_servers.yaml",
    "~/.config/caldav/test_servers.json",
]


class ConfigParseError(Exception):
    """Raised when a config file exists but cannot be parsed."""

    pass


def load_test_server_config(
    config_file: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Load test server configuration.

    Priority:
    1. Explicit config_file argument
    2. Test-specific config files (tests/caldav_test_servers.yaml, etc.)
    3. Main caldav config sections with 'testing_allowed: true'

    Args:
        config_file: Optional explicit path to config file

    Returns:
        Dict mapping server names to their configuration dicts.
        Empty dict if no configuration found.

    Raises:
        ConfigParseError: If a config file exists but cannot be parsed.
    """
    # Try explicit config file first
    if config_file:
        try:
            return _load_config_file(config_file)
        except ConfigParseError:
            if Path(config_file).exists():
                raise
            # File doesn't exist - fall through to other locations

    # Try test-specific config files
    for loc in TEST_CONFIG_LOCATIONS:
        path = Path(loc).expanduser()
        if path.exists():
            return _load_config_file(str(path))

    # Try main caldav config (sections with testing_allowed)
    servers = get_all_test_servers()
    if servers:
        # Add type: external for registry to use ExternalTestServer
        for config in servers.values():
            config.setdefault("type", "external")
            config.setdefault("enabled", True)
        return servers

    return {}


def _load_config_file(path: str) -> dict[str, dict[str, Any]]:
    """Load and parse a config file."""
    try:
        cfg = read_config(path)
    except Exception as e:
        raise ConfigParseError(f"Config file '{path}' exists but could not be parsed: {e}") from e

    if not cfg:
        raise ConfigParseError(
            f"Config file '{path}' exists but could not be parsed. Check the YAML/JSON syntax."
        )

    cfg = expand_env_vars(cfg)

    # Unwrap the "test-servers" key if present (the example YAML
    # uses this as a top-level namespace).  Also support configs
    # where server dicts are at the top level directly.
    if "test-servers" in cfg:
        cfg = cfg["test-servers"]

    return cfg
