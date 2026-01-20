import json
import os
import tempfile
import unittest

import manuel.codeblock
import manuel.doctest
import manuel.testing
import pytest

from .test_caldav import caldav_servers
from .test_caldav import client

m = manuel.codeblock.Manuel()
m += manuel.doctest.Manuel()
manueltest = manuel.testing.TestFactory(m)


@pytest.mark.skipif(not caldav_servers, reason="No test servers configured")
class DocTests(unittest.TestCase):
    def setUp(self):
        # Use the first server (typically Radicale/Xandikos embedded servers)
        # The client() helper will start the server if needed via setup callback
        server_params = caldav_servers[0]

        # Start the server and keep it running throughout the test
        self._client = client(**server_params)
        self._conn = self._client.__enter__()

        # Create a temporary config file with testing_allowed: true
        config = {"testing_allowed": True}
        for key in ("username", "password", "proxy"):
            if key in server_params:
                config[f"caldav_{key}"] = server_params[key]
        config["caldav_url"] = server_params["url"]

        self._config_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump({"default": config}, self._config_file)
        self._config_file.close()

        os.environ["CALDAV_CONFIG_FILE"] = self._config_file.name
        os.environ["PYTHON_CALDAV_USE_TEST_SERVER"] = "1"

    def tearDown(self):
        self._client.__exit__(None, None, None)
        os.unlink(self._config_file.name)
        del os.environ["CALDAV_CONFIG_FILE"]
        del os.environ["PYTHON_CALDAV_USE_TEST_SERVER"]

    test_tutorial = manueltest("../docs/source/tutorial.rst")
