#!/usr/bin/env python
# -*- encoding: utf-8 -*-
## YOU SHOULD MOST LIKELY NOT EDIT THIS FILE!
## Make a conf_private.py for personal configuration.
## Check conf_private.py.EXAMPLE
import logging
import tempfile
import threading
import time

import requests

from caldav import compatibility_hints
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

proxy = "127.0.0.1:8080"
proxy_noport = "127.0.0.1"

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

    url = "http://%s:%i/" % (radicale_host, radicale_port)
    caldav_servers.append(
        {
            "url": url,
            "name": "LocalRadicale",
            "username": "user1",
            "password": "",
            "backwards_compatibility_url": url + "user1",
            "incompatibilities": compatibility_hints.radicale,
            "setup": setup_radicale,
            "teardown": teardown_radicale,
        }
    )

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

    url = "http://%s:%i/" % (xandikos_host, xandikos_port)
    caldav_servers.append(
        {
            "name": "LocalXandikos",
            "url": url,
            "backwards_compatibility_url": url + "sometestuser",
            "incompatibilities": compatibility_hints.xandikos,
            "setup": setup_xandikos,
            "teardown": teardown_xandikos,
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
    setup(conn)
    conn.teardown = teardown
    conn.incompatibilities = kwargs.get("incompatibilities")
    conn.server_name = name
    return conn


caldav_servers = [x for x in caldav_servers if x.get("enable", True)]
