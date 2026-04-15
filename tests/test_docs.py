import os
import unittest

import manuel.codeblock
import manuel.doctest
import manuel.ignore
import manuel.testing
import pytest

from .test_servers import has_test_servers

# manuel.ignore must be the base to process ignore directives first
m = manuel.ignore.Manuel()
m += manuel.codeblock.Manuel()
m += manuel.doctest.Manuel()
manueltest = manuel.testing.TestFactory(m)


@pytest.mark.skipif(not has_test_servers(), reason="No test servers configured")
class DocTests(unittest.TestCase):
    def setUp(self):
        # Set the env var so each with-block in the tutorial starts its own
        # ephemeral test server (via get_davclient / get_calendar / get_calendars).
        # Do NOT pre-start a server here — that would cause all blocks to share
        # state, which is not what the tutorial intends.
        self._old_env = os.environ.get("PYTHON_CALDAV_USE_TEST_SERVER")
        os.environ["PYTHON_CALDAV_USE_TEST_SERVER"] = "1"

    def tearDown(self):
        if self._old_env is not None:
            os.environ["PYTHON_CALDAV_USE_TEST_SERVER"] = self._old_env
        else:
            os.environ.pop("PYTHON_CALDAV_USE_TEST_SERVER", None)

    test_tutorial = manueltest("../docs/source/tutorial.rst")
    test_async_tutorial = manueltest("../docs/source/async_tutorial.rst")
    test_async_ref = manueltest("../docs/source/async.rst")
