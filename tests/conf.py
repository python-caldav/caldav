#!/usr/bin/env python
# -*- encoding: utf-8 -*-
## YOU SHOULD MOST LIKELY NOT EDIT THIS FILE!
## Make a conf_private.py for personal configuration.
## Check conf_private.py.EXAMPLE
import logging
import tempfile
import threading
import time

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

try:
    from .conf_private import baikal_host, baikal_port
except ImportError:
    baikal_host = "localhost"
    baikal_port = 8800

try:
    from .conf_private import test_baikal
except ImportError:
    import os
    import subprocess

    ## Test Baikal if BAIKAL_URL is set OR if docker-compose is available
    if os.environ.get("BAIKAL_URL") is not None:
        test_baikal = True
    else:
        # Check if docker-compose is available
        try:
            subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            test_baikal = True
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            test_baikal = False

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
    import os
    import subprocess
    from pathlib import Path

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
        import subprocess
        import time
        from pathlib import Path

        # Check if docker-compose is available
        try:
            subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ) as e:
            raise RuntimeError(
                "docker-compose is not available. Baikal tests require Docker. "
                "Please install Docker or skip Baikal tests by setting "
                "test_baikal=False in tests/conf_private.py"
            ) from e

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
        import subprocess
        from pathlib import Path

        baikal_dir = Path(__file__).parent / "docker-test-servers" / "baikal"

        print("Stopping Baikal container...")
        subprocess.run(
            ["docker-compose", "down"],
            cwd=baikal_dir,
            check=True,
            capture_output=True,
        )
        print("✓ Baikal container stopped")

    # Only add Baikal to test servers if accessible OR if we can start it
    if is_baikal_accessible():
        # Already running, just use it
        features = compatibility_hints.baikal.copy()
        caldav_servers.append(
            {
                "name": "Baikal",
                "url": baikal_url,
                "username": baikal_username,
                "password": baikal_password,
                "features": features,
            }
        )
    else:
        # Not running, add with setup/teardown to auto-start
        features = compatibility_hints.baikal.copy()
        caldav_servers.append(
            {
                "name": "Baikal",
                "url": baikal_url,
                "username": baikal_username,
                "password": baikal_password,
                "features": features,
                "setup": setup_baikal,
                "teardown": teardown_baikal,
            }
        )

## Nextcloud - Docker container with automated setup
try:
    from .conf_private import test_nextcloud
except ImportError:
    import os
    import subprocess

    ## Test Nextcloud if NEXTCLOUD_URL is set OR if docker-compose is available
    if os.environ.get("NEXTCLOUD_URL") is not None:
        test_nextcloud = True
    else:
        # Check if docker-compose is available
        try:
            subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            test_nextcloud = True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            test_nextcloud = False

try:
    from .conf_private import nextcloud_host, nextcloud_port
except ImportError:
    nextcloud_host = "localhost"
    nextcloud_port = 8801

if test_nextcloud:
    import os
    import subprocess
    from pathlib import Path

    nextcloud_base_url = os.environ.get(
        "NEXTCLOUD_URL", f"http://{nextcloud_host}:{nextcloud_port}"
    )
    # Ensure the URL includes /remote.php/dav/ for CalDAV endpoint
    if not nextcloud_base_url.endswith("/remote.php/dav") and not nextcloud_base_url.endswith(
        "/remote.php/dav/"
    ):
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
        import subprocess
        import time
        from pathlib import Path

        # Check if docker-compose is available
        try:
            subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ) as e:
            raise RuntimeError(
                "docker-compose is not available. Nextcloud tests require Docker. "
                "Please install Docker or skip Nextcloud tests by setting "
                "test_nextcloud=False in tests/conf_private.py"
            ) from e

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

        raise TimeoutError(f"Nextcloud did not become ready after {max_attempts} seconds")

    def teardown_nextcloud(self) -> None:
        """Stop Nextcloud Docker container."""
        import subprocess
        from pathlib import Path

        nextcloud_dir = Path(__file__).parent / "docker-test-servers" / "nextcloud"

        print("Stopping Nextcloud container...")
        subprocess.run(
            ["docker-compose", "down"],
            cwd=nextcloud_dir,
            check=True,
            capture_output=True,
        )
        print("✓ Nextcloud container stopped")

    # Only add Nextcloud to test servers if accessible OR if we can start it
    if is_nextcloud_accessible():
        # Already running, just use it
        features = compatibility_hints.nextcloud.copy()
        caldav_servers.append(
            {
                "name": "Nextcloud",
                "url": nextcloud_url,
                "username": nextcloud_username,
                "password": nextcloud_password,
                "features": features,
            }
        )
    else:
        # Not running, add with setup/teardown to auto-start
        features = compatibility_hints.nextcloud.copy()
        caldav_servers.append(
            {
                "name": "Nextcloud",
                "url": nextcloud_url,
                "username": nextcloud_username,
                "password": nextcloud_password,
                "features": features,
                "setup": setup_nextcloud,
                "teardown": teardown_nextcloud,
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
