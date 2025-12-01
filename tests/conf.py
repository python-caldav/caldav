#!/usr/bin/env python
# -*- encoding: utf-8 -*-
## YOU SHOULD MOST LIKELY NOT EDIT THIS FILE!
## Make a conf_private.py for personal configuration.
## Check conf_private.py.EXAMPLE
## TODO: Future refactoring suggestions (in priority order):
##
## 1. [DONE] Extract conf_private import logic into helper function
##
## 2. Create a DockerTestServer base class to eliminate duplication between
##    Baikal, Nextcloud, and Cyrus setup/teardown logic. All three follow
##    the same pattern: start.sh/stop.sh scripts, wait for HTTP response,
##    similar accessibility checks.
##
## 3. Create a TestServer base class that also covers Radicale and Xandikos
##    setup
##
## 4. Split into test_servers/ package structure:
##    - test_servers/base.py: Base classes and utilities
##    - test_servers/config_loader.py: Configuration import logic
##    - test_servers/docker_servers.py: Baikal, Nextcloud, Cyrus
##    - test_servers/embedded_servers.py: Radicale, Xandikos
##    This would reduce conf.py from 550+ lines to <100 lines.
##
## 5. Consider creating server registry pattern for dynamic server registration
##    instead of procedural if-blocks for each server type.
##
## 6. Extract magic numbers into named constants:
##    DEFAULT_HTTP_TIMEOUT, MAX_STARTUP_WAIT_SECONDS, etc.
## See also https://github.com/python-caldav/caldav/issues/577
import logging
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from typing import List
from typing import Optional

try:
    import niquests as requests
except ImportError:
    import requests

from caldav import compatibility_hints
from caldav.compatibility_hints import FeatureSet
from caldav.davclient import CONNKEYS
from caldav.davclient import DAVClient

####################################
# Configuration import utilities
####################################


def _import_from_private(
    name: str, default: Any = None, variants: Optional[List[str]] = None
) -> Any:
    """
    Import attribute from conf_private.py with fallback variants.

    Tries multiple import paths to handle different ways the test suite
    might be invoked (pytest, direct execution, from parent directory, etc.).

    Args:
        name: Attribute name to import from conf_private
        default: Default value if attribute not found in any variant
        variants: List of module paths to try. Defaults to common patterns.

    Returns:
        The imported value or the default if not found anywhere.

    Examples:
        >>> caldav_servers = _import_from_private('caldav_servers', default=[])
        >>> test_baikal = _import_from_private('test_baikal', default=True)
    """
    if variants is None:
        variants = ["conf_private", "tests.conf_private", ".conf_private"]

    for variant in variants:
        try:
            if variant.startswith("."):
                # Relative import - use importlib for better compatibility
                import importlib

                try:
                    module = importlib.import_module(variant, package=__package__)
                    return getattr(module, name)
                except (ImportError, AttributeError, TypeError):
                    # TypeError can occur if __package__ is None
                    continue
            else:
                # Absolute import
                module = __import__(variant, fromlist=[name])
                return getattr(module, name)
        except (ImportError, AttributeError):
            continue

    return default


####################################
# Import personal test server config
####################################

# Legacy compatibility: only_private → test_public_test_servers
only_private = _import_from_private("only_private")
if only_private is not None:
    test_public_test_servers = not only_private
else:
    test_public_test_servers = _import_from_private(
        "test_public_test_servers", default=False
    )

# User-configured caldav servers
caldav_servers = _import_from_private("caldav_servers", default=[])

# Check if private test servers should be tested
test_private_test_servers = _import_from_private(
    "test_private_test_servers", default=True
)
if not test_private_test_servers:
    caldav_servers = []

# Xandikos configuration
xandikos_host = _import_from_private("xandikos_host", default="localhost")
xandikos_port = _import_from_private("xandikos_port", default=8993)
test_xandikos = _import_from_private("test_xandikos")
if test_xandikos is None:
    # Auto-detect if xandikos is installed
    try:
        import xandikos

        test_xandikos = True
    except ImportError:
        test_xandikos = False

# Radicale configuration
radicale_host = _import_from_private("radicale_host", default="localhost")
radicale_port = _import_from_private("radicale_port", default=5232)
test_radicale = _import_from_private("test_radicale")
if test_radicale is None:
    # Auto-detect if radicale is installed
    try:
        import radicale

        test_radicale = True
    except ImportError:
        test_radicale = False

# RFC6638 users for scheduling tests
rfc6638_users = _import_from_private("rfc6638_users", default=[])

#############################
# Docker-based test servers #
#############################


## This pattern is repeated quite often when trying to run docker
def _run_command(cmd_list, return_output=False, timeout=5):
    try:
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            check=True,
            timeout=timeout,
        )
        if return_output:
            return result.stdout.strip()
        return True
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ) as e:
        return False


def _verify_docker(raise_err: bool = False):
    has_docker = _run_command(["docker-compose", "--version"]) and _run_command(
        ["docker", "ps"]
    )
    if raise_err and not has_docker:
        raise RuntimeError(
            "docker-compose is not available. Baikal tests require Docker. "
            "Please install Docker or skip Baikal tests by setting "
            "test_baikal=False in tests/conf_private.py"
        )
    return has_docker


## We may have different expectations to different servers on how they
## respond before they are ready to receive CalDAV requests and when
## they are still starting up, hence it's needed with different
## functions for each server.
_is_accessible_funcs = {}


def _start_or_stop_server(name, action, timeout=60):
    lcname = name.lower()

    # Check if server is already accessible (e.g., in GitHub Actions)
    if _is_accessible_funcs[lcname]():
        print(f"✓ {name} is already running")
        return

    ## TODO: generalize this, it doesn't need to be a docker
    ## server.  We simply run f"{action}.sh" and assume the server comes up/down.
    ## If it's not a docker-server, we do not need to verify docker
    _verify_docker(raise_err=True)

    # Get the docker-compose directory
    dir = Path(__file__).parent / "docker-test-servers" / lcname

    # Check if start.sh/stop.sh exists
    script = dir / f"{action}.sh"
    if not script.exists():
        raise FileNotFoundError(f"{script} not found in {dir}")

    # Start the server
    print(f"Let's {action} {name} from {dir}...")

    # Run start.sh/stop.sh script which handles docker-compose and setup
    subprocess.run(
        [str(script)],
        cwd=dir,
        check=True,
        capture_output=True,
        # env=env
    )

    if action == "stop":
        print(f"✓ {name} server stopped and volumes removed")
        ## Rest of the logic is irrelevant for stopping
        return

    ## This is probably moot, typically already taken care of in start.sh,
    ## but let's not rely on that
    for attempt in range(0, 60):
        if _is_accessible_funcs[lcname]():
            print(f"✓ {name} is ready")
            return
        else:
            print(f"... waiting for {name} to become ready")
            time.sleep(1)

    raise RuntimeError(
        f"{name} is still not accessible after {timeout}s, needs manual investigation.  Tried to run {start_script} in directory {dir}"
    )


## wrapper
def _conf_method(name, action):
    return lambda self: _start_or_stop_server(name, action)


def _add_conf(name, url, username, password, extra_params={}):
    lcname = name.lower()
    conn_params = {
        "name": name,
        "features": lcname,
        "url": url,
        "username": username,
        "password": password,
    }
    conn_params.update(extra_params)
    if _is_accessible_funcs[lcname]():
        caldav_servers.append(conn_params)
    else:
        # Not running, add with setup/teardown to auto-start
        caldav_servers.append(
            conn_params
            | {
                "setup": _conf_method(name, "start"),
                "teardown": _conf_method(name, "stop"),
            }
        )


# Baikal configuration
baikal_host = _import_from_private("baikal_host", default="localhost")
baikal_port = _import_from_private("baikal_port", default=8800)
test_baikal = _import_from_private("test_baikal")
if test_baikal is None:
    # Auto-enable if BAIKAL_URL is set OR if docker-compose is available
    if os.environ.get("BAIKAL_URL") is not None:
        test_baikal = True
    else:
        test_baikal = _verify_docker()

#####################
# Public test servers
#####################

## Currently I'm not aware of any publically available test servers, and my
## own attempts on maintaining any has been canned.

# if test_public_test_servers:
# caldav_servers.append( ... )

#######################
# Internal test servers
#######################

if test_radicale:
    import radicale.config
    import radicale
    import radicale.server
    import socket

    def setup_radicale(self):
        self.serverdir = tempfile.TemporaryDirectory()
        self.serverdir.__enter__()
        self.configuration = radicale.config.load("")
        self.configuration.update(
            {
                "storage": {"filesystem_folder": self.serverdir.name},
                "auth": {"type": "none"},
            }
        )
        self.server = radicale.server
        self.shutdown_socket, self.shutdown_socket_out = socket.socketpair()
        self.radicale_thread = threading.Thread(
            target=self.server.serve,
            args=(self.configuration, self.shutdown_socket_out),
        )
        self.radicale_thread.start()
        i = 0
        while True:
            try:
                requests.get(str(self.url))
                break
            except:
                time.sleep(0.05)
                i += 1
                assert i < 100

    def teardown_radicale(self):
        self.shutdown_socket.close()
        i = 0
        self.serverdir.__exit__(None, None, None)

    domain = f"{radicale_host}:{radicale_port}"
    features = compatibility_hints.radicale.copy()
    features["auto-connect.url"]["domain"] = domain
    compatibility_hints.radicale_tmp_test = features
    caldav_servers.append(
        {
            "name": "LocalRadicale",
            "username": "user1",
            "password": "",
            "features": "radicale_tmp_test",
            "backwards_compatibility_url": f"http://{domain}/user1",
            "setup": setup_radicale,
            "teardown": teardown_radicale,
        }
    )

## TODO: quite much duplicated code
if test_xandikos:
    import asyncio

    import aiohttp
    import aiohttp.web
    from xandikos.web import XandikosApp, XandikosBackend

    def setup_xandikos(self):
        ## TODO: https://github.com/jelmer/xandikos/issues/131#issuecomment-1054805270 suggests a simpler way to launch the xandikos server

        self.serverdir = tempfile.TemporaryDirectory()
        self.serverdir.__enter__()
        ## Most of the stuff below is cargo-cult-copied from xandikos.web.main
        ## Later jelmer created some API that could be used for this
        ## Threshold put high due to https://github.com/jelmer/xandikos/issues/235
        ## index_threshold not supported in latest release yet
        # self.backend = XandikosBackend(path=self.serverdir.name, index_threshold=0, paranoid=True)
        # self.backend = XandikosBackend(path=self.serverdir.name, index_threshold=9999, paranoid=True)
        self.backend = XandikosBackend(path=self.serverdir.name)
        self.backend._mark_as_principal("/sometestuser/")
        self.backend.create_principal("/sometestuser/", create_defaults=True)
        mainapp = XandikosApp(
            self.backend, current_user_principal="sometestuser", strict=True
        )

        async def xandikos_handler(request):
            return await mainapp.aiohttp_handler(request, "/")

        self.xapp = aiohttp.web.Application()
        self.xapp.router.add_route("*", "/{path_info:.*}", xandikos_handler)
        ## https://stackoverflow.com/questions/51610074/how-to-run-an-aiohttp-server-in-a-thread
        self.xapp_loop = asyncio.new_event_loop()
        self.xapp_runner = aiohttp.web.AppRunner(self.xapp)
        asyncio.set_event_loop(self.xapp_loop)
        self.xapp_loop.run_until_complete(self.xapp_runner.setup())
        self.xapp_site = aiohttp.web.TCPSite(
            self.xapp_runner, host=xandikos_host, port=xandikos_port
        )
        self.xapp_loop.run_until_complete(self.xapp_site.start())

        def aiohttp_server():
            self.xapp_loop.run_forever()

        self.xandikos_thread = threading.Thread(target=aiohttp_server)
        self.xandikos_thread.start()

    def teardown_xandikos(self):
        if not test_xandikos:
            return
        self.xapp_loop.stop()

        ## ... but the thread may be stuck waiting for a request ...
        def silly_request():
            try:
                requests.get(str(self.url))
            except:
                pass

        threading.Thread(target=silly_request).start()
        i = 0
        while self.xapp_loop.is_running():
            time.sleep(0.05)
            i += 1
            assert i < 100
        self.xapp_loop.run_until_complete(self.xapp_runner.cleanup())
        i = 0
        while self.xandikos_thread.is_alive():
            time.sleep(0.05)
            i += 1
            assert i < 100

        self.serverdir.__exit__(None, None, None)

    if xandikos.__version__ == (0, 2, 12):
        features = compatibility_hints.xandikos_v0_2_12.copy()
    else:
        features = compatibility_hints.xandikos_v0_3.copy()
    domain = f"{xandikos_host}:{xandikos_port}"
    features["auto-connect.url"]["domain"] = domain
    caldav_servers.append(
        {
            "name": "LocalXandikos",
            "backwards_compatibility_url": f"http://{domain}/sometestuser",
            "features": features,
            "setup": setup_xandikos,
            "teardown": teardown_xandikos,
        }
    )

## Baikal - Docker container with automated setup
if test_baikal:
    baikal_base_url = os.environ.get(
        "BAIKAL_URL", f"http://{baikal_host}:{baikal_port}"
    )
    # Ensure the URL includes /dav.php/ for CalDAV endpoint
    if not baikal_base_url.endswith("/dav.php") and not baikal_base_url.endswith(
        "/dav.php/"
    ):
        baikal_url = f"{baikal_base_url}/dav.php"
    else:
        baikal_url = baikal_base_url.rstrip("/")

    baikal_username = os.environ.get("BAIKAL_USERNAME", "testuser")
    baikal_password = os.environ.get("BAIKAL_PASSWORD", "testpass")

    def is_baikal_accessible() -> bool:
        """Check if Baikal server is accessible."""
        try:
            # Check the dav.php endpoint
            response = requests.get(f"{baikal_url}/", timeout=5)
            return response.status_code in (200, 401, 403, 404)
        except Exception:
            return False

    _is_accessible_funcs["baikal"] = is_baikal_accessible
    _add_conf("Baikal", baikal_url, baikal_username, baikal_password)

## Nextcloud - Docker container with automated setup
# Nextcloud configuration
nextcloud_host = _import_from_private("nextcloud_host", default="localhost")
nextcloud_port = _import_from_private("nextcloud_port", default=8801)
test_nextcloud = _import_from_private("test_nextcloud")
if test_nextcloud is None:
    # Auto-enable if NEXTCLOUD_URL is set OR if docker-compose is available
    if os.environ.get("NEXTCLOUD_URL") is not None:
        test_nextcloud = True
    else:
        test_nextcloud = _verify_docker()

if test_nextcloud:
    nextcloud_base_url = os.environ.get(
        "NEXTCLOUD_URL", f"http://{nextcloud_host}:{nextcloud_port}"
    )
    # Ensure the URL includes /remote.php/dav/ for CalDAV endpoint
    if not nextcloud_base_url.endswith(
        "/remote.php/dav"
    ) and not nextcloud_base_url.endswith("/remote.php/dav/"):
        nextcloud_url = f"{nextcloud_base_url}/remote.php/dav"
    else:
        nextcloud_url = nextcloud_base_url.rstrip("/")

    nextcloud_username = os.environ.get("NEXTCLOUD_USERNAME", "testuser")
    nextcloud_password = os.environ.get("NEXTCLOUD_PASSWORD", "TestPassword123!")

    def is_nextcloud_accessible() -> bool:
        """Check if Nextcloud server is accessible."""
        try:
            # Check the dav endpoint
            response = requests.get(f"{nextcloud_url}/", timeout=5)
            return response.status_code in (200, 401, 403, 404, 207)
        except Exception:
            return False

    _is_accessible_funcs["nextcloud"] = is_nextcloud_accessible
    _add_conf("Nextcloud", nextcloud_url, nextcloud_username, nextcloud_password)

## Cyrus IMAP - Docker container with CalDAV/CardDAV support
# Cyrus configuration
cyrus_host = _import_from_private("cyrus_host", default="localhost")
cyrus_port = _import_from_private("cyrus_port", default=8802)
test_cyrus = _import_from_private("test_cyrus")
if test_cyrus is None:
    # Auto-enable if CYRUS_URL is set OR if docker-compose is available
    if os.environ.get("CYRUS_URL") is not None:
        test_cyrus = True
    else:
        test_cyrus = _verify_docker()

if test_cyrus:
    cyrus_base_url = os.environ.get("CYRUS_URL", f"http://{cyrus_host}:{cyrus_port}")
    # Cyrus CalDAV path includes the username
    # Use user1 (pre-created user in Cyrus docker test server)
    cyrus_username = os.environ.get("CYRUS_USERNAME", "user1")
    cyrus_password = os.environ.get("CYRUS_PASSWORD", "any-password-seems-to-work")
    cyrus_url = f"{cyrus_base_url}/dav/calendars/user/{cyrus_username}"

    def is_cyrus_accessible() -> bool:
        """Check if Cyrus CalDAV server is accessible and working."""
        try:
            # Test actual CalDAV access, not just HTTP server
            response = requests.request(
                "PROPFIND",
                f"{cyrus_url}/",
                auth=(cyrus_username, cyrus_password),
                headers={"Depth": "0"},
                timeout=5,
            )
            # 207 Multi-Status means CalDAV is working
            # 404 with multistatus also means server is responding but user might not exist yet
            return response.status_code in (200, 207)
        except Exception:
            return False

    _is_accessible_funcs["cyrus"] = is_cyrus_accessible

    _add_conf("Cyrus", cyrus_url, cyrus_username, cyrus_password)


###################################################################
# Convenience - get a DAVClient object from the caldav_servers list
###################################################################
def client(
    idx=None, name=None, setup=lambda conn: None, teardown=lambda conn: None, **kwargs
):
    kwargs_ = kwargs.copy()
    no_args = not any(x for x in kwargs if kwargs[x] is not None)
    if idx is None and name is None and no_args and caldav_servers:
        ## No parameters given - find the first server in caldav_servers list
        return client(idx=0)
    elif idx is not None and no_args and caldav_servers:
        return client(**caldav_servers[idx])
    elif name is not None and no_args and caldav_servers:
        for s in caldav_servers:
            if s["name"] == name:
                return client(**s)
        return None
    elif no_args:
        return None
    for bad_param in (
        "incompatibilities",
        "backwards_compatibility_url",
        "principal_url",
        "enable",
    ):
        if bad_param in kwargs_:
            kwargs_.pop(bad_param)
    for kw in list(kwargs_.keys()):
        if not kw in CONNKEYS:
            logging.critical(
                "unknown keyword %s in connection parameters.  All compatibility flags should now be sent as a separate list, see conf_private.py.EXAMPLE.  Ignoring."
                % kw
            )
            kwargs_.pop(kw)
    conn = DAVClient(**kwargs_)
    conn.setup = setup
    conn.teardown = teardown
    conn.server_name = name
    return conn


caldav_servers = [x for x in caldav_servers if x.get("enable", True)]
