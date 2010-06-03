#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from nose.tools import assert_equal

from conf import principal_url

from caldav.caldav import CalDAV
from caldav.objects import Principal
from caldav.utils import namespace

class TestCalDAV:
    def setup(self):
        self.caldav = CalDAV(principal_url)

    def teardown(self):
        pass

    def testPrincipal(self):
        p = Principal(principal_url)
        assert_equal(p.geturl(), principal_url)

        collections = self.caldav.children(p, namespace.ns("D", "collection"))
        for c in collections:
            assert_equal(c.__class__.__name__, "Collection")

    def testYoupi(self):
        print "yay"
