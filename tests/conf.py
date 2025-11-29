#!/usr/bin/env python
# -*- encoding: utf-8 -*-
## YOU SHOULD MOST LIKELY NOT EDIT THIS FILE!
## Make a conf_private.py for personal configuration.
## Check conf_private.py.EXAMPLE
import logging
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

try:
    import niquests as requests
except ImportError:
    import requests

from caldav import compatibility_hints
from caldav.compatibility_hints import FeatureSet
from caldav.davclient import CONNKEYS
from caldav.davclient import DAVClient

####################################
# Import personal test server config
####################################

## TODO: there are probably more elegant ways of doing this?

try:
    from .conf_private import only_private  ## legacy compatibility

    test_public_test_servers = not only_private
except ImportError:
    try:
        from .conf_private import test_public_test_servers
    except ImportError:
        test_public_test_servers = False

try:
    from .conf_private import caldav_servers
except ImportError:
    try:
        from conf_private import caldav_servers
    except ImportError:
        try:
            from tests.conf_private import caldav_servers
        except ImportError:
            caldav_servers = []
try:
    from .conf_private import test_private_test_servers

    if not test_private_test_servers:
        caldav_servers = []
except ImportError:
    pass

try:
    from .conf_private import xandikos_host, xandikos_port
except ImportError:
    xandikos_host = "localhost"
    xandikos_port = 8993  ## random port above 8000
try:
    from .conf_private import test_xandikos
except ImportError:
    try:
        import xandikos

        test_xandikos = True
    except:
        test_xandikos = False

try:
    from .conf_private import radicale_host, radicale_port
except ImportError:
    radicale_host = "localhost"
    radicale_port = 5232  ## default radicale host

try:
    from .conf_private import test_radicale
except ImportError:
    try:
        import radicale

        test_radicale = True
    except:
        test_radicale = False

try:
    from .conf_private import rfc6638_users
except ImportError:
    rfc6638_users = []

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
    has_docker = _run_command(["docker-compose", "--version"])
    if raise_err and not has_docker:
        raise RuntimeError(
            "docker-compose is not available. Baikal tests require Docker. "
            "Please install Docker or skip Baikal tests by setting "
            "test_baikal=False in tests/conf_private.py"
        )
    return has_docker


try:
    from .conf_private import baikal_host, baikal_port
except ImportError:
    baikal_host = "localhost"
    baikal_port = 8800

try:
    from .conf_private import test_baikal
except ImportError:
    ## Test Baikal if BAIKAL_URL is set OR if docker-compose is available
    if os.environ.get("BAIKAL_URL") is not None:
        test_baikal = True
    else:
        # Check if docker-compose is available
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

    def setup_baikal(self) -> None:
        """Start Baikal Docker container with pre-configured database."""
        import time
        from pathlib import Path

        _verify_docker(raise_err=True)
        # Check if docker-compose is available

        # Get the docker-compose directory
        baikal_dir = Path(__file__).parent / "docker-test-servers" / "baikal"

        # Check if docker-compose.yml exists
        if not (baikal_dir / "docker-compose.yml").exists():
            raise FileNotFoundError(f"docker-compose.yml not found in {baikal_dir}")

        # Start the container but don't wait for full startup
        print(f"Starting Baikal container from {baikal_dir}...")

        subprocess.run(
            ["docker-compose", "up", "--no-start"],
            cwd=baikal_dir,
            check=True,
            capture_output=True,
        )

        # Copy pre-configured files BEFORE starting the container
        # This way the entrypoint script will fix permissions properly
        print("Copying pre-configured files into container...")
        specific_dir = baikal_dir / "Specific"
        config_dir = baikal_dir / "config"

        subprocess.run(
            [
                "docker",
                "cp",
                f"{specific_dir}/.",
                "baikal-test:/var/www/baikal/Specific/",
            ],
            check=True,
            capture_output=True,
        )

        # Copy YAML config for newer Baikal versions
        if config_dir.exists():
            subprocess.run(
                [
                    "docker",
                    "cp",
                    f"{config_dir}/.",
                    "baikal-test:/var/www/baikal/config/",
                ],
                check=True,
                capture_output=True,
            )

        # Now start the container - the entrypoint will fix permissions
        print("Starting container...")
        subprocess.run(
            ["docker", "start", "baikal-test"],
            check=True,
            capture_output=True,
        )

        # Wait for Baikal to be ready
        print("Waiting for Baikal to be ready...")
        max_attempts = 30
        for i in range(max_attempts):
            try:
                response = requests.get(f"{baikal_url}/", timeout=2)
                if response.status_code in (200, 401, 403):
                    print(f"✓ Baikal is ready at {baikal_url}")
                    return
            except Exception:
                pass
            time.sleep(1)

        raise TimeoutError(f"Baikal did not become ready after {max_attempts} seconds")

    def teardown_baikal(self) -> None:
        """Stop Baikal Docker container."""

        baikal_dir = Path(__file__).parent / "docker-test-servers" / "baikal"

        print("Stopping Baikal container...")
        subprocess.run(
            ["docker-compose", "down"],
            cwd=baikal_dir,
            check=True,
            capture_output=True,
        )
        print("✓ Baikal container stopped")

    conn_params = {
        "name": "Baikal",
        "url": baikal_url,
        "username": baikal_username,
        "password": baikal_password,
        "features": "baikal",
    }

    # Only add Baikal to test servers if accessible OR if we can start it
    if is_baikal_accessible():
        caldav_servers.append(conn_params)
    else:
        # Not running, add with setup/teardown to auto-start
        caldav_servers.append(
            conn_params
            | {
                "setup": setup_baikal,
                "teardown": teardown_baikal,
            }
        )

## Nextcloud - Docker container with automated setup
try:
    from .conf_private import test_nextcloud
except ImportError:
    ## Test Nextcloud if NEXTCLOUD_URL is set OR if docker-compose is available
    if os.environ.get("NEXTCLOUD_URL") is not None:
        test_nextcloud = True
    else:
        # Check if docker-compose is available
        test_nextcloud = _verify_docker()

try:
    from .conf_private import nextcloud_host, nextcloud_port
except ImportError:
    nextcloud_host = "localhost"
    nextcloud_port = 8801

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

    def setup_nextcloud(self) -> None:
        """Start Nextcloud Docker container and configure it."""
        import time

        _verify_docker(raise_err=True)

        # Get the docker-compose directory
        nextcloud_dir = Path(__file__).parent / "docker-test-servers" / "nextcloud"

        # Check if docker-compose.yml exists
        if not (nextcloud_dir / "docker-compose.yml").exists():
            raise FileNotFoundError(f"docker-compose.yml not found in {nextcloud_dir}")

        # Start the container
        print(f"Starting Nextcloud container from {nextcloud_dir}...")
        subprocess.run(
            ["docker-compose", "up", "-d"],
            cwd=nextcloud_dir,
            check=True,
            capture_output=True,
        )

        # Run setup script to configure Nextcloud and create test user
        print("Configuring Nextcloud...")
        setup_script = nextcloud_dir / "setup_nextcloud.sh"
        result = subprocess.run(
            [str(setup_script)],
            cwd=nextcloud_dir,
            check=True,
            capture_output=False,
        )

        # Wait for Nextcloud to be ready
        print("Waiting for Nextcloud to be ready...")
        max_attempts = 30
        for i in range(max_attempts):
            try:
                response = requests.get(f"{nextcloud_url}/", timeout=2)
                if response.status_code in (200, 401, 403, 207):
                    print(f"✓ Nextcloud is ready at {nextcloud_url}")
                    return
            except Exception:
                pass
            time.sleep(1)

        raise TimeoutError(
            f"Nextcloud did not become ready after {max_attempts} seconds"
        )

    def teardown_nextcloud(self) -> None:
        """Stop Nextcloud Docker container."""

        nextcloud_dir = Path(__file__).parent / "docker-test-servers" / "nextcloud"

        print("Stopping Nextcloud container...")
        subprocess.run(
            ["docker-compose", "down"],
            cwd=nextcloud_dir,
            check=True,
            capture_output=True,
        )
        print("✓ Nextcloud container stopped")

    conn_params = {
        "name": "Nextcloud",
        "url": nextcloud_url,
        "username": nextcloud_username,
        "password": nextcloud_password,
        "features": "nextcloud",
    }
    # Only add Nextcloud to test servers if accessible OR if we can start it
    if is_nextcloud_accessible():
        # Already running, just use it
        caldav_servers.append(conn_params)
    else:
        # Not running, add with setup/teardown to auto-start
        caldav_servers.append(
            conn_params
            | {
                "setup": setup_nextcloud,
                "teardown": teardown_nextcloud,
            }
        )

## Cyrus IMAP - Docker container with CalDAV/CardDAV support
try:
    from .conf_private import test_cyrus
except ImportError:
    ## Test Cyrus if CYRUS_URL is set OR if docker-compose is available
    if os.environ.get("CYRUS_URL") is not None:
        test_cyrus = True
    else:
        # Check if docker-compose is available
        test_cyrus = _verify_docker()

try:
    from .conf_private import cyrus_host, cyrus_port
except ImportError:
    cyrus_host = "localhost"
    cyrus_port = 8802

if test_cyrus:
    cyrus_base_url = os.environ.get("CYRUS_URL", f"http://{cyrus_host}:{cyrus_port}")
    # Cyrus CalDAV path includes the username
    # Use user1 (pre-created user in Cyrus docker test server)
    cyrus_username = os.environ.get("CYRUS_USERNAME", "user1")
    cyrus_password = os.environ.get("CYRUS_PASSWORD", "x")
    cyrus_url = f"{cyrus_base_url}/dav/calendars/user/{cyrus_username}"

    def is_cyrus_accessible() -> bool:
        """Check if Cyrus server is accessible."""
        try:
            response = requests.get(f"{cyrus_base_url}/", timeout=5)
            return response.status_code in (200, 401, 403, 404, 207)
        except Exception:
            return False

    def setup_cyrus(self) -> None:
        """Start Cyrus Docker container and configure it."""
        import time

        # Check if Cyrus is already accessible (e.g., in GitHub Actions)
        if is_cyrus_accessible():
            print(f"✓ Cyrus is already running at {cyrus_base_url}")
            return

        # Check if docker-compose is available
        _verify_docker(raise_err=True)

        # Get the docker-compose directory
        cyrus_dir = Path(__file__).parent / "docker-test-servers" / "cyrus"

        # Check if start.sh exists
        start_script = cyrus_dir / "start.sh"
        if not start_script.exists():
            raise FileNotFoundError(f"start.sh not found in {cyrus_dir}")

        # Run start.sh script which handles docker-compose and setup
        print(f"Starting Cyrus container from {cyrus_dir}...")
        env = os.environ.copy()
        # Unset DOCKER_HOST to avoid conflicts with Podman
        env.pop("DOCKER_HOST", None)
        subprocess.run(
            [str(start_script)],
            cwd=cyrus_dir,
            check=True,
            capture_output=False,
            env=env,
        )

        # Wait a bit more to ensure Cyrus is fully ready
        print("Verifying Cyrus is ready for CalDAV...")
        time.sleep(2)

        # Verify CalDAV access
        try:
            response = requests.get(
                f"{cyrus_url}/", auth=(cyrus_username, cyrus_password), timeout=5
            )
            if response.status_code in (200, 207, 401, 403):
                print(f"✓ Cyrus CalDAV is accessible at {cyrus_url}")
            else:
                print(f"Warning: Cyrus returned status {response.status_code}")
        except Exception as e:
            print(f"Warning: Could not verify Cyrus access: {e}")

    def teardown_cyrus(self) -> None:
        """Stop Cyrus Docker container."""

        # If CYRUS_URL is set, the server is externally managed (e.g., GitHub Actions)
        # Don't try to stop it
        if os.environ.get("CYRUS_URL") is not None:
            return

        # Check if we started the container (by checking if it's running)
        output = _run_command(
            ["docker", "inspect", "-f", "{{.State.Running}}", "cyrus-test"],
            return_output=True,
        )

        # Container doesn't exist or not running or inspect failed
        # => nothing to tear down
        if not output or output != "true":
            # TODO: is this expected?  What if container is running,
            ## but the command fails for other reasons?
            return

        cyrus_dir = Path(__file__).parent / "docker-test-servers" / "cyrus"

        print("Stopping Cyrus container...")
        try:
            subprocess.run(
                ["docker-compose", "down"],
                cwd=cyrus_dir,
                timeout=30,
                capture_output=True,
            )
            print("✓ Cyrus container stopped")
        except subprocess.TimeoutExpired:
            print("Warning: Timeout stopping Cyrus container")

    # Add to servers list
    caldav_servers.append(
        {
            "name": "Cyrus",
            "url": cyrus_url,
            "username": cyrus_username,
            "password": cyrus_password,
            "features": "cyrus",
            "setup": setup_cyrus,
            "teardown": teardown_cyrus,
        }
    )


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
