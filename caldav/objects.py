#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import copy
import urlparse
import vobject
import StringIO

from lxml import etree

import utils.vcal

class DavObject:
    url = None
    client = None

    def __init__(self, url = None):
        if url is not None:
            self.url = urlparse.urlparse(url)

    def geturl(self, path = None):
        u = ""
        if self.url is not None:
            if path is None:
                u = self.url.geturl()
            else:
                u = urlparse.urlunparse((self.url.scheme, self.url.netloc, 
                                         path, self.url.params, self.url.query,
                                         self.url.fragment))
        return u


class Principal(DavObject):
    def collections(self):
        return self.children("{DAV:}collection")

    def add_collection(self, coll):
        pass

class Collection(DavObject):
    def __str__(self):
        return "Collection: %s" % self.geturl()

    def events(self):
        return self.children(None)

    def add_event(self, event):
        pass

class Event(DavObject):
    instance = None

    def __init__(self, url, data):
        DavObject.__init__(self, url)
        self.instance = vobject.readOne(StringIO.StringIO(data))

    def load(self, client):
        r = client.request(self.url.path)
        r.raw = utils.vcal.fix(r.raw)
        self.instance = vobject.readOne(StringIO.StringIO(r.raw))

    def __str__(self):
        return "Event: %s" % self.geturl()

