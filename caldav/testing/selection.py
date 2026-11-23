"""
Which test server get_davclient() connects to with
PYTHON_CALDAV_USE_TEST_SERVER, and the ``test_*`` keys of a config file
that make a section a test server.
"""

import logging
import os
import warnings
from typing import Any

import calendaring_config

from caldav.config import (
    _DEPRECATED_TEST_KEYS,
    CONNKEYS,
    KINDS,
    _caldav_params,
    config_section,
)

log = logging.getLogger("caldav")


def get_test_setting(section_data: dict[str, Any], key: str, default: Any = None) -> Any:
    """Read the test-tooling setting ``key`` (e.g. ``test_priority``) from a
    config section, falling back to its deprecated name."""
    if key in section_data:
        return section_data[key]
    old_key = _DEPRECATED_TEST_KEYS.get(key)
    if old_key and old_key in section_data:
        warnings.warn(
            f"The config key '{old_key}' is deprecated, use '{key}' instead",
            ## Not DeprecationWarning: that would be hidden by default, and
            ## the one to act on it is whoever edits the config file
            FutureWarning,
            stacklevel=2,
        )
        return section_data[old_key]
    return default


def _get_test_server_config(
    name: str | None, environment: bool, config_file: str | None = None
) -> dict[str, Any] | None:
    """
    Get connection parameters for a test server.

    Uses the priority-ordered server list as the single source of truth.
    Embedded servers (xandikos priority 10, radicale priority 10) beat docker
    (20) and configured / test_allowed servers (30) by default.  Any server
    can override its priority via ``test_priority: <int>`` in its config.

    The servers are those of the ``caldav.testing`` registry (embedded,
    docker and external), plus the ``test_allowed`` sections of
    ``config_file``.

    Args:
        name: Optional server name or server_type to restrict selection.
        environment: Whether to read PYTHON_CALDAV_TEST_SERVER_NAME, and to
            find the config file through CALENDARING_CONFIG_FILE / CALDAV_CONFIG_FILE.
        config_file: Explicit config file path, for its test_allowed sections.

    Returns:
        Connection parameters dict, or None if no server could be started.
    """
    if environment and name is None:
        name = os.environ.get("PYTHON_CALDAV_TEST_SERVER_NAME")
    if environment and config_file is None:
        ## CALENDARING_CONFIG_FILE / CALDAV_CONFIG_FILE, else the default search
        try:
            found = calendaring_config.find_config_file(None)
        except calendaring_config.ConfigError:
            found = None
        config_file = str(found) if found else None

    for server in _collect_test_servers(name, config_file):
        was_already_started = server._started
        # A _ConfiguredServer has no session lock
        claim = getattr(server, "claim_server", None)
        claimed = False
        try:
            # Another process using this server: try the next one rather than wait
            claimed = bool(claim and claim(server.name, 0))
            server.start()
        except Exception as e:
            log.warning("Failed to start test server %s: %s", server.name, e)
            if claimed:
                server.release_server(server.name)
            continue
        log.info("Using test server: %s at %s", server.name, server.url)
        return _test_server_to_params(server, was_already_started)

    log.info(
        "PYTHON_CALDAV_USE_TEST_SERVER is set but no test server is available. "
        "Install xandikos or radicale, or add 'test_allowed: true' to a config section."
    )
    return None


def _collect_test_servers(name: str | None, config_file: str | None) -> list[Any]:
    """
    Return a priority-ordered list of available test servers.

    The registry reads the default config file, so ``config_file`` adds
    only what it holds beyond that: a file named explicitly or through
    CALENDARING_CONFIG_FILE / CALDAV_CONFIG_FILE.
    """
    from caldav.testing.registry import get_registry

    servers: list[Any] = list(get_registry().enabled_servers())
    if config_file:
        known = {s.name.lower() for s in servers}
        servers += [
            _ConfiguredServer(section_name, params)
            for section_name, params in get_all_test_servers(config_file).items()
            if section_name.lower() not in known
        ]
        servers.sort(key=lambda s: s.priority)

    if name is not None:
        servers = [s for s in servers if name.lower() in (s.name.lower(), s.server_type.lower())]
    return servers


class _ConfiguredServer:
    """
    Thin wrapper around a ``test_allowed`` section of a config file that
    the registry does not read (see ``_collect_test_servers``); the
    registry loads the default file's sections as ``ExternalTestServer``.
    """

    server_type = "external"

    def __init__(self, name: str, params: dict[str, Any]) -> None:
        self.name = name
        self._params = params
        self._started = False

    @property
    def priority(self) -> int:
        return int(self._params.get("test_priority", 30))

    @property
    def url(self) -> str:
        return self._params.get("url", "")

    @property
    def username(self) -> str | None:
        return self._params.get("username")

    @property
    def password(self) -> str | None:
        return self._params.get("password")

    @property
    def features(self) -> Any:
        return self._params.get("features")

    def start(self) -> None:
        self._started = True  # external — assumed already running

    def stop(self) -> None:
        self._started = False

    def is_accessible(self) -> bool:
        return bool(self.url)


def _test_server_to_params(server: Any, was_already_started: bool) -> dict[str, Any]:
    """Build a ``get_davclient``-compatible params dict from a server object."""
    params: dict[str, Any] = {
        "url": server.url,
        "_server_name": server.name,
    }
    if server.username:
        params["username"] = server.username
    if server.password:
        params["password"] = server.password
    if server.features:
        params["features"] = server.features
    # Only attach teardown if we started the server; if it was already running
    # (e.g. started by client_context) leave lifecycle management to the caller.
    if not was_already_started:
        params["_teardown"] = lambda _client=None, s=server: s.stop()
    return params


def get_all_test_servers(
    config_file: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Get all test servers from config file.

    Finds all sections with 'test_allowed: true' and returns their
    connection parameters.  Disabled sections and meta-sections are left
    out.

    Args:
        config_file: Optional explicit path to config file.
                    If None, searches default locations.

    Returns:
        Dict mapping section names to connection parameter dicts.
        Each dict contains: url, username, password, features, etc.
    """
    try:
        path = calendaring_config.find_config_file(config_file or None, environment=False)
    except calendaring_config.ConfigError:
        return {}
    cfg = calendaring_config.read_config(path) if path else {}

    result: dict[str, dict[str, Any]] = {}
    for section_name in cfg:
        try:
            section_data = config_section(cfg, section_name)
        except calendaring_config.ConfigError as e:
            ## A broken section that is not a test server must not hide the others
            log.warning(f"config section {section_name} skipped: {e}")
            continue
        if (
            not get_test_setting(section_data, "test_allowed")
            or "contains" in section_data
            or section_data.get("disable")
        ):
            continue
        ## A broken test server is an error, as is a password_command that fails
        conns = calendaring_config.load(path, section_name, environment=False, kinds=KINDS)
        for conn in conns:
            ## load() leaves out other kinds; a section of no kind is kept even
            ## without a URL, as features can give one
            params = _caldav_params(conn, warn=False)
            if not params:
                continue
            conn_params = {k: v for k, v in params.items() if k in CONNKEYS}
            priority = get_test_setting(section_data, "test_priority")
            if priority is not None:
                conn_params["test_priority"] = priority
            # Also copy the raw section data for keys not in CONNKEYS
            # (e.g., test_allowed itself, or custom keys)
            conn_params["_raw_config"] = section_data
            result[section_name] = conn_params

    return result
