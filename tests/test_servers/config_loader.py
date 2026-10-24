"""
Configuration loader for test servers.

This module loads test server configuration from all of:
1. Test-specific config files (tests/caldav_test_servers.yaml in the
   checkout, ~/.config/caldav/test_servers.yaml)
2. Main caldav config files with 'test_allowed: true' sections
"""

import json
import warnings
from pathlib import Path
from typing import Any

import yaml

from caldav.config import expand_env_vars, get_all_test_servers

# Test-specific config file locations (don't need test_allowed).  The
# checkout's file is found relative to this module, not to the current
# directory, so projects running from elsewhere see it too.
_TESTS_DIR = Path(__file__).resolve().parent.parent
TEST_CONFIG_LOCATIONS = [
    str(_TESTS_DIR / "caldav_test_servers.yaml"),
    str(_TESTS_DIR / "caldav_test_servers.json"),
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

    An explicit, existing config_file is used alone.  Otherwise the
    result is the union of the test-specific config files
    (tests/caldav_test_servers.yaml, etc.) and the main caldav config
    sections with 'test_allowed: true'; on a name clash the source
    listed first wins.

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

    result: dict[str, Any] = {}
    # The registry matches server names case-insensitively, so must the merge
    seen: set[str] = set()

    def merge(name: str, config: Any) -> None:
        if name.lower() not in seen:
            seen.add(name.lower())
            result[name] = config

    for loc in TEST_CONFIG_LOCATIONS:
        path = Path(loc).expanduser()
        if path.exists():
            for name, config in _load_config_file(str(path)).items():
                merge(name, config)

    # Main caldav config (sections with test_allowed).  A broken caldav
    # config must not take the test-server files down with it.
    try:
        servers = get_all_test_servers()
    except Exception as e:
        warnings.warn(
            f"test_allowed servers skipped, the caldav config could not be read: {e}",
            UserWarning,
            stacklevel=2,
        )
        servers = {}
    for name, config in servers.items():
        # Add type: external for registry to use ExternalTestServer
        config.setdefault("type", "external")
        config.setdefault("enabled", True)
        merge(name, config)

    return result


def _load_config_file(path: str) -> dict[str, dict[str, Any]]:
    """Load and parse a config file.

    Not the shared config format (it may hold top-level lists such as
    rfc6638_users), so it is parsed here: as JSON, else as YAML.
    """
    try:
        with open(path, "rb") as f:
            raw = f.read()
        try:
            cfg = json.loads(raw)
        except json.JSONDecodeError:
            cfg = yaml.safe_load(raw)
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
    # Preserve top-level non-server keys (e.g. rfc6638_users) by merging
    # them back into the servers dict after unwrapping.
    if "test-servers" in cfg:
        top_level_extras = {k: v for k, v in cfg.items() if k != "test-servers"}
        cfg = cfg["test-servers"]
        cfg.update(top_level_extras)

    return cfg
