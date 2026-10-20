import copy
import json
import logging
import os
import warnings
from typing import Any

import calendaring_config
from calendaring_config import Connection
from calendaring_config import expand_env_vars as expand_env_vars

log = logging.getLogger("caldav")

"""
This configuration parsing code was just copied from my plann library (and will be removed from there at some point in the future).  Test coverage is poor as for now.
"""

## This is being moved from my plann library.  The code itself will be introduced into caldav 2.0, but proper test code and documentation will come in a later release (2.1?)


## TODO TODO TODO - write test code for all the corner cases
## TODO TODO TODO - write documentation of config format
def expand_config_section(config, section="default", blacklist=None):
    """
    The leaf sections that ``section`` expands to, as a list.

    We allow:

    * * includes all sections in config file that are not meta-sections
    * "Meta"-sections in the config file with the keyword "contains" followed by a list of section names
    * Recursive "meta"-sections
    * Glob patterns (work_* for all sections starting with work_)
    * Glob patterns in "meta"-sections

    The rules are calendaring-config's ``expand_section``; ``blacklist`` is
    no longer used.
    """
    if section == "default" and (section not in config or config[section].get("disable", False)):
        ## As for get_davclient(): when no section was named, a file
        ## without a usable "default" means no configuration
        return []
    return calendaring_config.expand_section(config, section)


def config_section(config, section="default"):
    if section in config and "inherits" in config[section]:
        ret = config_section(config, config[section]["inherits"])
    else:
        ret = {}
    if section in config:
        ret.update(config[section])
    return ret


def read_config(fn, interactive_error=False):
    """The sections of config file ``fn``, or of the first file found when it is not given.

    A missing file gives an empty dict; a file that cannot be parsed raises
    ``ValueError``.  Environment variables are not consulted.
    """
    try:
        path = calendaring_config.find_config_file(fn or None, environment=False)
    except calendaring_config.ConfigError as e:
        logging.debug(f"config file {fn} not usable: {e}")
        return {}
    if path is None:
        return {}
    return calendaring_config.read_config(path)


## Profiles that have been renamed.  The names are user-facing - they turn up
## as ``features:`` or ``base:`` in a caller's own config - so a rename has to
## explain itself rather than surface as an AttributeError from getattr.
RENAMED_FEATURE_PROFILES = {
    "bedework": (
        "bedework_3_10_3",
        "the profile was only ever measured against a quickstart-3.10.3 "
        "docker image from 2018; use bedework_5_0_0 for a current Bedework",
    ),
}


def _lookup_feature_profile(name):
    """Look up a named profile in compatibility_hints.

    Accepts the name either bare ("synology") or module-qualified
    ("compatibility_hints.synology").
    """
    import caldav.compatibility_hints

    if name.startswith("compatibility_hints."):
        name = name[len("compatibility_hints.") :]
    if name in RENAMED_FEATURE_PROFILES:
        new_name, reason = RENAMED_FEATURE_PROFILES[name]
        raise ValueError(
            f"The compatibility profile '{name}' has been renamed to "
            f"'{new_name}' - {reason}.  Update your configuration."
        )
    try:
        return copy.deepcopy(getattr(caldav.compatibility_hints, name))
    except AttributeError:
        raise ValueError(
            f"No compatibility profile named '{name}' in caldav.compatibility_hints"
        ) from None


def resolve_features(features):
    """Resolve a features specification into a dict suitable for FeatureSet.

    Supports:
    - None: returns None (backward compatibility mode)
    - str: looks up a named profile from compatibility_hints
      e.g. "synology" or "compatibility_hints.synology"
    - dict with "base" key: loads a named profile and merges overrides
      e.g. {"base": "synology", "search.is-not-defined": {"support": "fragile"}}
    - dict without "base": used as-is
    """
    if features is None:
        return None
    if isinstance(features, str):
        return _lookup_feature_profile(features)
    if isinstance(features, dict) and "base" in features:
        base_name = features["base"]
        if isinstance(base_name, str):
            base_features = _lookup_feature_profile(base_name)
            for key, value in features.items():
                if key != "base":
                    base_features[key] = value
            return base_features
    return features


# Valid connection parameter keys for DAVClient
CONNKEYS = frozenset(
    [
        "url",
        "proxy",
        "username",
        "password",
        "timeout",
        "headers",
        "huge_tree",
        "ssl_verify_cert",
        "ssl_cert",
        "auth",
        "auth_type",
        "features",
        "enable_rfc6764",
        "require_tls",
        "protocol",
    ]
)

# Keys starting with ``test_`` in a config section are reserved for test
# tooling; other users of the config file (like the calendaring library)
# drop them.  The old names are still read, with a deprecation warning.
_DEPRECATED_TEST_KEYS = {
    "test_allowed": "testing_allowed",
    "test_priority": "priority",
}


def get_test_setting(section_data: dict[str, Any], key: str, default: Any = None) -> Any:
    """Read the test-tooling setting ``key`` (e.g. ``test_priority``) from a
    config section, falling back to its deprecated name."""
    if key in section_data:
        return section_data[key]
    old_key = _DEPRECATED_TEST_KEYS.get(key)
    if old_key and old_key in section_data:
        warnings.warn(
            f"The config key '{old_key}' is deprecated, use '{key}' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return section_data[old_key]
    return default


def get_connection_params(
    check_config_file: bool = True,
    config_file: str | None = None,
    config_section: str | None = None,
    testconfig: bool = False,
    environment: bool = True,
    name: str | None = None,
    **explicit_params: Any,
) -> dict[str, Any] | None:
    """
    Get connection parameters from multiple sources.

    This is THE single source of truth for configuration discovery.
    Both sync and async get_davclient() functions should use this.

    Priority (first non-empty wins):
    1. Explicit parameters (url=, username=, password=, etc.)
    2. Test server config (if testconfig=True or PYTHON_CALDAV_USE_TEST_SERVER env var)
    3. Environment variables (CALDAV_URL, CALDAV_USERNAME, etc.)
    4. Config file (CALDAV_CONFIG_FILE env var or default locations)

    Test Server Mode:
        When testconfig=True or PYTHON_CALDAV_USE_TEST_SERVER env var is set,
        only config file sections with 'test_allowed: true' will be used.
        This prevents accidentally using personal/production servers for testing.

        If no test server is found, returns None (does NOT fall through to
        regular config file or environment variables).

        Environment variable PYTHON_CALDAV_TEST_SERVER_NAME can specify which
        config section to use for testing.

    Args:
        check_config_file: Whether to look for config files
        config_file: Explicit path to config file
        config_section: Section name in config file (default: "default")
        testconfig: Whether to use test server configuration
        environment: Whether to read from environment variables
        name: Name of test server/config section to use (for testconfig)
        **explicit_params: Explicit connection parameters

    Returns:
        Dict with connection parameters (url, username, password, etc.)
        or None if no configuration found.
    """
    # 1. Explicit parameters take highest priority.
    # A kwarg whose value is None counts as "not supplied" rather than
    # "unset it" - the common CLI wrapper get_davclient(url=args.url,
    # username=args.user, password=args.password) passes None for every
    # option the user left out, and overlaying those on the winning source
    # would wipe CALDAV_URL and friends.  An empty string is kept: it is
    # meaningful for servers with no authentication.
    explicit_conn = (
        {k: v for k, v in explicit_params.items() if k in CONNKEYS and v is not None}
        if explicit_params
        else {}
    )
    if explicit_conn.get("url") or explicit_conn.get("features"):
        # Return when URL is given, or when features are given (the
        # client constructor resolves URL from auto-connect.url hints
        # via _auto_url()).  Don't fall through to env vars/config
        # files when the caller explicitly provided connection info.
        return explicit_conn

    # 2. Test server configuration
    if testconfig or (environment and os.environ.get("PYTHON_CALDAV_USE_TEST_SERVER")):
        conn = _get_test_server_config(name, environment, config_file)
        if conn is not None:
            # Explicit kwargs outrank the discovered test server, same as for
            # the environment and config-file sources below.
            conn.update(explicit_conn)
            return conn
        # In test mode, don't fall through to regular config - return None
        # This prevents accidentally using personal/production servers for testing
        logging.info(
            "Test server mode enabled but no server with test_allowed=true found. "
            "Add 'test_allowed: true' to a config section to enable it for testing."
        )
        return None

    # 3./4. Environment variables (CALDAV_*), then the config file, through
    # calendaring-config: a CALDAV_URL replaces the file, other CALDAV_*
    # variables override the section's keys one by one.
    for conn_params in _caldav_connections(
        config_file, config_section, environment=environment, file=check_config_file
    ):
        conn_params = {k: v for k, v in conn_params.items() if k in CONNKEYS}
        conn_params.update(explicit_conn)
        return conn_params

    # No env/config source matched.  At this point explicit_conn has neither
    # 'url' nor 'features' (those return early above), so it cannot produce a
    # connectable client — treat it as "no configuration found".
    return None


# Section keys that are not client parameters.  calendar_name and
# calendar_url select calendars; test_*, x_* and extra_config belong to test
# tooling and applications (calendaring-config's docs/format.md).
CALENDAR_KEYS = ("calendar_name", "calendar_url")
# The kinds of section caldav connects to; a JMAP_URL must not hide them
KINDS = ("caldav",)
PASSED_KEYS = frozenset(["extra_config", *_DEPRECATED_TEST_KEYS.values()])
PASSED_PREFIXES = ("test_", "x_")
BOOLEAN_KEYS = frozenset(["ssl_verify_cert", "huge_tree", "enable_rfc6764", "require_tls"])
TRUE_WORDS = ("true", "yes", "on", "1")
FALSE_WORDS = ("false", "no", "off", "0")


def _is_caldav(conn: Connection) -> bool:
    """A section without a kind is caldav's when its URL is http(s)."""
    if conn.kind is not None:
        return conn.kind == "caldav"
    return str(conn.params.get("url", "")).startswith(("http://", "https://"))


def _convert(key: str, value: Any) -> Any:
    """Environment variables are strings; turn them into what the client takes."""
    if key == "features":
        return resolve_features(value)
    if not isinstance(value, str):
        return value
    if key in BOOLEAN_KEYS:
        # ssl_verify_cert may also be the path of a CA bundle
        if value.lower() in TRUE_WORDS:
            return True
        if value.lower() in FALSE_WORDS:
            return False
    elif key == "headers":
        try:
            headers = json.loads(value)
        except json.JSONDecodeError:
            headers = None
        if not isinstance(headers, dict):
            ## the value is left out: headers often carry a token
            raise ValueError("headers must be a JSON object")
        return headers
    return value


def _caldav_params(conn: Connection, warn: bool = True) -> dict[str, Any] | None:
    """The client parameters and calendar filters of a caldav connection.

    Keys caldav does not know are left out, and logged when ``warn``.
    ``None`` when there is neither a URL nor features to find one from.
    """
    params: dict[str, Any] = {}
    for key, value in conn.params.items():
        if key in CONNKEYS:
            params[key] = _convert(key, value)
        elif key in CALENDAR_KEYS:
            params[key] = value
        elif warn and key not in PASSED_KEYS and not key.startswith(PASSED_PREFIXES):
            log.warning(f"config section {conn.name}: unknown key '{key}'")
    return params if (params.get("url") or params.get("features")) else None


def _caldav_connections(
    config_file: str | None,
    section_name: str | None,
    environment: bool = True,
    file: bool = True,
) -> list[dict[str, Any]]:
    """The caldav connections ``section_name`` stands for, from the
    environment and the config file; other kinds of sections are skipped."""
    if file:
        conns = calendaring_config.load(
            config_file, section_name, environment=environment, kinds=KINDS
        )
    elif environment:
        conns = [
            Connection("environment", kind, params)
            for kind, params in calendaring_config.environment_connections(KINDS)
        ]
    else:
        return []
    found = (_caldav_params(conn) for conn in conns if _is_caldav(conn))
    return [params for params in found if params]


def _get_test_server_config(
    name: str | None, environment: bool, config_file: str | None = None
) -> dict[str, Any] | None:
    """
    Get connection parameters for a test server.

    Uses the priority-ordered server list as the single source of truth.
    Embedded servers (xandikos priority 10, radicale priority 10) beat docker
    (20) and configured / test_allowed servers (30) by default.  Any server
    can override its priority via ``test_priority: <int>`` in its config.

    When running from the source tree the full registry is used (embedded +
    docker + external).  When caldav is pip-installed without the test
    infrastructure, only embedded servers from ``caldav.testing`` plus any
    ``test_allowed`` config-file sections are available.

    Args:
        name: Optional server name or server_type to restrict selection.
        environment: Whether to read PYTHON_CALDAV_TEST_SERVER_NAME.
        config_file: Explicit config file path (for test_allowed fallback).

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
        # Servers from caldav.testing (pip-installed caldav) have no session lock
        claim = getattr(server, "claim_server", None)
        claimed = False
        try:
            # Another process using this server: try the next one rather than wait
            claimed = bool(claim and claim(server.name, 0))
            server.start()
        except Exception as e:
            logging.warning("Failed to start test server %s: %s", server.name, e)
            if claimed:
                server.release_server(server.name)
            continue
        logging.info("Using test server: %s at %s", server.name, server.url)
        return _test_server_to_params(server, was_already_started)

    logging.info(
        "PYTHON_CALDAV_USE_TEST_SERVER is set but no test server is available. "
        "Install xandikos or radicale, or add 'test_allowed: true' to a config section."
    )
    return None


def _collect_test_servers(name: str | None, config_file: str | None) -> list[Any]:
    """
    Return a priority-ordered list of available test servers.

    Tries the full registry first (source tree); falls back to embedded
    servers from ``caldav.testing`` plus ``test_allowed`` config sections
    (pip-installed users).
    """
    try:
        from tests.test_servers.registry import get_registry

        servers: list[Any] = list(get_registry().enabled_servers())
    except ImportError:
        servers = _get_pip_test_servers(config_file)

    if name is not None:
        servers = [s for s in servers if name.lower() in (s.name.lower(), s.server_type.lower())]
    return servers


def _get_pip_test_servers(config_file: str | None) -> list[Any]:
    """
    Build a server list for pip-installed users (no tests/ available).

    Includes embedded servers from caldav.testing and any test_allowed
    sections from config files, all sorted by priority.
    """
    from caldav.testing import RadicaleServer, XandikosServer

    servers: list[Any] = []

    try:
        import xandikos  # noqa: F401

        servers.append(XandikosServer())
    except ImportError:
        pass

    try:
        import radicale  # noqa: F401

        servers.append(RadicaleServer())
    except ImportError:
        pass

    for section_name, params in get_all_test_servers(config_file).items():
        servers.append(_ConfiguredServer(section_name, params))

    return sorted(servers, key=lambda s: s.priority)


class _ConfiguredServer:
    """
    Thin wrapper around a ``test_allowed`` config-file section.

    Used only in pip-installed mode; in the source tree these sections are
    loaded into the registry as ``ExternalTestServer`` instances instead.
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


def extract_conn_params_from_section(
    section_data: dict[str, Any],
    config_file: str | None = None,
    section_name: str = "section",
) -> dict[str, Any] | None:
    """Extract connection parameters from a config section dict.

    The section is read as calendaring-config reads it: a ``kind: caldav``
    section with plain keys, or ``caldav_``-prefixed keys (with
    ``caldav_user``/``caldav_pass`` accepted as aliases for
    username/password); environment variable references are expanded,
    ``password_command`` / ``password_keyring`` are resolved, and a
    ``features`` key is resolved through :func:`resolve_features`.  A
    ``password_command`` is only run when ``config_file`` names the file the
    section came from.  ``section_name`` is the name error messages use.
    Public so that downstream tools (e.g. plann) can
    reuse it on plann-style config sections, or on command line arguments:
    keys it does not know are ignored without a warning.

    Returns a dict containing only CONNKEYS entries.  Returns ``None`` for a
    section of another kind, or one with neither a server URL nor features
    (with features, the client constructor can resolve the URL from
    auto-connect.url hints).  Calendar filter keys (``calendar_name``,
    ``calendar_url``) are intentionally excluded — callers that need them
    read ``section_data`` directly.
    """
    conn = calendaring_config.section_connection(section_name, section_data, config_file)
    if conn.kind not in (None, *KINDS):
        return None
    params = _caldav_params(conn, warn=False)
    if not params:
        return None
    return {k: v for k, v in params.items() if k in CONNKEYS}


def get_all_file_connection_params(
    config_file: str | None,
    section_name: str | None = None,
    environment: bool = False,
) -> list[dict[str, Any]]:
    """Return connection-params dicts for every caldav leaf section that ``section_name`` expands to.

    ``section_name`` follows the same rules as everywhere else in the config
    system: a plain name returns ``[section_name]``; a meta-section with
    ``contains: [...]`` expands recursively; ``*`` means all non-disabled
    leaf sections; glob patterns (``work_*``) are also supported.  Sections
    of another kind (``kind: jmap``, a directory of ``.ics`` files) are
    skipped.

    Each dict contains CONNKEYS entries plus optional ``calendar_name`` /
    ``calendar_url`` calendar-filter keys read from the config section.
    With ``environment``, ``CALDAV_*`` variables apply as in
    :func:`get_connection_params`.

    Returns an empty list when the config file is absent or the section has
    neither a usable URL nor features to derive one from.
    """
    return _caldav_connections(config_file, section_name, environment=environment)


def get_all_test_servers(
    config_file: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Get all test servers from config file.

    Finds all sections with 'test_allowed: true' and returns their
    connection parameters.

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
    if not cfg:
        return {}

    result: dict[str, dict[str, Any]] = {}
    for section_name in cfg:
        section_data = config_section(cfg, section_name)
        if get_test_setting(section_data, "test_allowed"):
            conn_params = extract_conn_params_from_section(section_data, str(path), section_name)
            if conn_params:
                priority = get_test_setting(section_data, "test_priority")
                if priority is not None:
                    conn_params["test_priority"] = priority
                # Also copy the raw section data for keys not in CONNKEYS
                # (e.g., test_allowed itself, or custom keys)
                conn_params["_raw_config"] = section_data
                result[section_name] = conn_params

    return result
