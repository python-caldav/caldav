import json
import logging
import os
import re
import sys
from fnmatch import fnmatch
from typing import Any, Dict, Optional, Union

"""
This configuration parsing code was just copied from my plann library (and will be removed from there at some point in the future).  Test coverage is poor as for now.
"""

## This is being moved from my plann library.  The code itself will be introduced into caldav 2.0, but proper test code and documentation will come in a later release (2.1?)


## TODO TODO TODO - write test code for all the corner cases
## TODO TODO TODO - write documentation of config format
def expand_config_section(config, section="default", blacklist=None):
    """
    In the "normal" case, will return [ section ]

    We allow:

    * * includes all sections in config file
    * "Meta"-sections in the config file with the keyword "contains" followed by a list of section names
    * Recursive "meta"-sections
    * Glob patterns (work_* for all sections starting with work_)
    * Glob patterns in "meta"-sections
    """
    ## Optimizating for a special case.  The results should be the same without this optimization.
    if section == "*":
        return [x for x in config if not config[x].get("disable", False)]

    ## If it's not a glob-pattern ...
    if set(section).isdisjoint(set("[*?")):
        ## If it's referring to a "meta section" with the "contains" keyword
        if "contains" in config[section]:
            results = []
            if not blacklist:
                blacklist = set()
            blacklist.add(section)
            for subsection in config[section]["contains"]:
                if not subsection in results and not subsection in blacklist:
                    for recursivesubsection in expand_config_section(
                        config, subsection, blacklist
                    ):
                        if not recursivesubsection in results:
                            results.append(recursivesubsection)
            return results
        else:
            ## Disabled sections should be ignored
            if config.get("section", {}).get("disable", False):
                return []

            ## NORMAL CASE - return [ section ]
            return [section]
    ## section name is a glob pattern
    matching_sections = [x for x in config if fnmatch(x, section)]
    results = set()
    for s in matching_sections:
        if set(s).isdisjoint(set("[*?")):
            results.update(expand_config_section(config, s))
        else:
            ## Section names shouldn't contain []?* ... but in case they do ... don't recurse
            results.add(s)
    return results


def config_section(config, section="default"):
    if section in config and "inherits" in config[section]:
        ret = config_section(config, config[section]["inherits"])
    else:
        ret = {}
    if section in config:
        ret.update(config[section])
    return ret


def read_config(fn, interactive_error=False):
    if not fn:
        cfgdir = f"{os.environ.get('HOME', '/')}/.config/"
        for config_file in (
            f"{cfgdir}/caldav/calendar.conf",
            f"{cfgdir}/caldav/calendar.yaml",
            f"{cfgdir}/caldav/calendar.json",
            f"{cfgdir}/calendar.conf",
            "/etc/calendar.conf",
            "/etc/caldav/calendar.conf",
        ):
            cfg = read_config(config_file)
            if cfg:
                return cfg
        return None

    ## This can probably be refactored into fewer lines ...
    try:
        try:
            with open(fn, "rb") as config_file:
                return json.load(config_file)
        except json.decoder.JSONDecodeError:
            ## Late import, wrapped in try/except.  yaml is external module,
            ## and not included in the requirements as for now.
            try:
                import yaml

                try:
                    with open(fn, "rb") as config_file:
                        return yaml.load(config_file, yaml.Loader)
                except yaml.scanner.ScannerError:
                    logging.error(
                        f"config file {fn} exists but is neither valid json nor yaml.  Check the syntax."
                    )
            except ImportError:
                logging.error(
                    f"config file {fn} exists but is not valid json, and pyyaml is not installed."
                )

    except FileNotFoundError:
        ## File not found
        logging.info("no config file found")
    except ValueError:
        if interactive_error:
            logging.error(
                "error in config file.  Be aware that the interactive configuration will ignore and overwrite the current broken config file",
                exc_info=True,
            )
        else:
            logging.error("error in config file.  It will be ignored", exc_info=True)
    return {}


def expand_env_vars(value: Any) -> Any:
    """
    Expand environment variable references in configuration values.

    Supports two syntaxes:
    - ${VAR} - expands to the value of VAR, or empty string if not set
    - ${VAR:-default} - expands to the value of VAR, or 'default' if not set

    Works recursively on dicts and lists.

    Examples:
        >>> os.environ['TEST_VAR'] = 'hello'
        >>> expand_env_vars('${TEST_VAR}')
        'hello'
        >>> expand_env_vars('${MISSING:-default_value}')
        'default_value'
        >>> expand_env_vars({'key': '${TEST_VAR}'})
        {'key': 'hello'}
    """
    if isinstance(value, str):
        # Pattern matches ${VAR} or ${VAR:-default}
        pattern = r"\$\{([^}:]+)(?::-([^}]*))?\}"

        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            default = match.group(2) if match.group(2) is not None else ""
            return os.environ.get(var_name, default)

        return re.sub(pattern, replacer, value)
    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [expand_env_vars(v) for v in value]
    return value


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
    ]
)


def get_connection_params(
    check_config_file: bool = True,
    config_file: Optional[str] = None,
    config_section: Optional[str] = None,
    testconfig: bool = False,
    environment: bool = True,
    name: Optional[str] = None,
    **explicit_params: Any,
) -> Optional[Dict[str, Any]]:
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
        only config file sections with 'testing_allowed: true' will be used.
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
    # 1. Explicit parameters take highest priority
    if explicit_params:
        # Filter to valid connection keys
        conn_params = {k: v for k, v in explicit_params.items() if k in CONNKEYS}
        if conn_params.get("url"):
            return conn_params

    # 2. Test server configuration
    if testconfig or (environment and os.environ.get("PYTHON_CALDAV_USE_TEST_SERVER")):
        conn = _get_test_server_config(name, environment)
        if conn is not None:
            return conn
        # In test mode, don't fall through to regular config - return None
        # This prevents accidentally using personal/production servers for testing
        logging.info(
            "Test server mode enabled but no server with testing_allowed=true found. "
            "Add 'testing_allowed: true' to a config section to enable it for testing."
        )
        return None

    # 3. Environment variables (CALDAV_*)
    if environment:
        conn_params = _get_env_config()
        if conn_params:
            return conn_params

        # Also check for config file path from environment
        if not config_file:
            config_file = os.environ.get("CALDAV_CONFIG_FILE")
        if not config_section:
            config_section = os.environ.get("CALDAV_CONFIG_SECTION")

    # 4. Config file
    if check_config_file:
        conn_params = _get_file_config(config_file, config_section)
        if conn_params:
            return conn_params

    return None


def _get_env_config() -> Optional[Dict[str, Any]]:
    """Extract connection parameters from CALDAV_* environment variables."""
    conf: Dict[str, Any] = {}
    for env_key in os.environ:
        if env_key.startswith("CALDAV_") and not env_key.startswith("CALDAV_CONFIG"):
            key = env_key[7:].lower()
            # Map common aliases
            if key == "pass":
                key = "password"
            elif key == "user":
                key = "username"
            if key in CONNKEYS:
                conf[key] = os.environ[env_key]
    return conf if conf else None


def _get_file_config(
    file_path: Optional[str], section_name: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Extract connection parameters from config file."""
    if not section_name:
        section_name = "default"

    cfg = read_config(file_path)
    if not cfg:
        return None

    section_data = config_section(cfg, section_name)
    return _extract_conn_params_from_section(section_data)


def _get_test_server_config(
    name: Optional[str], environment: bool
) -> Optional[Dict[str, Any]]:
    """
    Get connection parameters for test server.

    Priority:
    1. Config file sections with 'testing_allowed: true'
    2. Built-in test servers from tests/conf.py (radicale, xandikos, docker)

    Args:
        name: Specific config section or test server name/index to use.
              Can be a config section name, test server name, or numeric index.
        environment: Whether to check environment variables for server selection.

    Returns:
        Connection parameters dict, or None if no test server configured.
    """
    # Check environment for server name
    if environment and name is None:
        name = os.environ.get("PYTHON_CALDAV_TEST_SERVER_NAME")

    # 1. Try config file with testing_allowed flag
    cfg = read_config(None)  # Use default config file locations
    if cfg:
        # If name is specified, check if it's a config section with testing_allowed
        if name is not None and not isinstance(name, int):
            section_data = config_section(cfg, str(name))
            if section_data.get("testing_allowed"):
                return _extract_conn_params_from_section(section_data)

        # Find first section with testing_allowed=true (if no name specified)
        if name is None:
            for section_name in cfg:
                section_data = config_section(cfg, section_name)
                if section_data.get("testing_allowed"):
                    logging.info(f"Using test server from config section: {section_name}")
                    return _extract_conn_params_from_section(section_data)

    # 2. Fall back to built-in test servers from tests/conf.py
    return _get_builtin_test_server(name, environment)


def _get_builtin_test_server(
    name: Optional[str], environment: bool
) -> Optional[Dict[str, Any]]:
    """
    Get connection parameters from built-in test servers (tests/conf.py).

    This supports radicale, xandikos, and docker-based test servers.
    """
    # Save current sys.path
    original_path = sys.path.copy()

    try:
        sys.path.insert(0, "tests")
        sys.path.insert(1, ".")

        try:
            from conf import client
        except (ImportError, ModuleNotFoundError) as e:
            logging.debug(f"Could not import tests/conf.py: {e}")
            return None
        except Exception as e:
            # Handle other import errors (e.g., syntax errors, missing dependencies)
            logging.warning(f"Error importing tests/conf.py: {e}")
            return None

        # Parse server selection
        idx: Optional[int] = None

        # If name is provided and can be parsed as int, use it as idx
        if name is not None:
            try:
                idx = int(name)
                name = None
            except (ValueError, TypeError):
                pass

        # Also check environment variables if environment=True
        if environment:
            if idx is None:
                idx_str = os.environ.get("PYTHON_CALDAV_TEST_SERVER_IDX")
                if idx_str:
                    try:
                        idx = int(idx_str)
                    except (ValueError, TypeError):
                        pass
            if name is None:
                name = os.environ.get("PYTHON_CALDAV_TEST_SERVER_NAME")

        conn = client(idx, name)
        if conn is None:
            return None

        # Extract connection parameters from DAVClient object
        conn_params: Dict[str, Any] = {}
        for key in CONNKEYS:
            if hasattr(conn, key):
                value = getattr(conn, key)
                if value is not None:
                    conn_params[key] = value

        # The client may have setup/teardown - store them too
        if hasattr(conn, "setup"):
            conn_params["_setup"] = conn.setup
        if hasattr(conn, "teardown"):
            conn_params["_teardown"] = conn.teardown
        if hasattr(conn, "server_name"):
            conn_params["_server_name"] = conn.server_name

        return conn_params

    finally:
        sys.path = original_path


def _extract_conn_params_from_section(section_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract connection parameters from a config section dict."""
    conn_params: Dict[str, Any] = {}
    for k in section_data:
        if k.startswith("caldav_") and section_data[k]:
            key = k[7:]
            # Map common aliases
            if key == "pass":
                key = "password"
            elif key == "user":
                key = "username"
            if key in CONNKEYS:
                conn_params[key] = expand_env_vars(section_data[k])
        elif k == "features" and section_data[k]:
            conn_params["features"] = section_data[k]

    return conn_params if conn_params.get("url") else None
