import unittest

import manuel.codeblock
import manuel.doctest
import manuel.ignore
import manuel.testing
import pytest

from .test_servers import client_context, has_test_servers

# manuel.ignore must be the base to process ignore directives first
m = manuel.ignore.Manuel()
m += manuel.codeblock.Manuel()
m += manuel.doctest.Manuel()
manueltest = manuel.testing.TestFactory(m)


@pytest.mark.skipif(not has_test_servers(), reason="No test servers configured")
class DocTests(unittest.TestCase):
    def setUp(self):
        # Start a test server and configure environment for get_davclient()
        self._test_context = client_context()
        self._conn = self._test_context.__enter__()

    def tearDown(self):
        self._test_context.__exit__(None, None, None)

    test_tutorial = manueltest("../docs/source/tutorial.rst")
