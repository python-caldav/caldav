from unittest import TestCase

from caldav.lib.python_utilities import to_wire


class TestUtils(TestCase):
    def test_to_wire(self):
        # fmt: off
        self.assertEqual(to_wire('blatti'), b'blatti')
        self.assertEqual(to_wire(b'blatti'), b'blatti')
        self.assertEqual(to_wire(u'blatti'), b'blatti')
        self.assertEqual(to_wire(''), b'')
        self.assertEqual(to_wire(u''), b'')
        self.assertEqual(to_wire(b''), b'')
        self.assertEqual(to_wire(None), None)
        # fmt: on
