import manuel.codeblock
import manuel.doctest
import manuel.testing
import unittest
import os

m = manuel.codeblock.Manuel()
m += manuel.doctest.Manuel()
manueltest = manuel.testing.TestFactory(m)

class DocTests(unittest.TestCase):
    def setUp(self):
        os.environ['PYTHON_CALDAV_USE_TEST_SERVER'] = '1'

    test_tutorial = manueltest('../docs/source/tutorial.rst')


