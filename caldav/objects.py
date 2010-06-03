#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import copy
import urlparse
import vobject
import StringIO

from caldav.utils import vcal
from caldav.utils.namespace import ns
from caldav.utils import url

class DAVObject:
    id = None
    url = None
    client = None
    parent = None
    name = None

    def __init__(self, client, url = None, parent = None, name = None, id = None):
        self.client = client
        self.parent = parent
        self.name = name
        self.id = id
        if url is not None:
            self.url = urlparse.urlparse(url)
 
    def properties(self, props):
        return commands.properties(self.client, self, props)
    
    def save(self):
        raise Exception("Must be defined in subclasses")

    def delete(self):
        if self.url is not None:
            commands.delete(self.client, self)



class Principal(DAVObject):
    def __init__(self, client, url):
        self.client = client
        self.url = urlparse.urlparse(url)

    def calendars(self):
        return commands.children(self.client, self, ns("D", "collection"))


class Calendar(DAVObject):
    def save(self):
        if self.url is None:
            (id, path) = commands.create_calendar(self.client, self.parent, 
                                                  self.name, self.id)
            self.id = id
            if path is not None:
                self.url = urlparse.urlparse(path)
        return self

    def date_search(self, start, end = None):
        return commands.date_search(self.client, self, start, end)

    def events(self):
        return commands.children(self.client, self)

    def __str__(self):
        return "Collection: %s" % url.make(self.url)

class Event(DAVObject):
    instance = None

    def __init__(self, client, url = None, data = None, parent = None, id = None):
        DAVObject.__init__(self, client, url, parent, id)
        if data is not None:
            self.instance = vobject.readOne(StringIO.StringIO(data))

    def load(self):
        r = self.client.request(self.url.path)
        r.raw = vcal.fix(r.raw)
        self.instance = vobject.readOne(StringIO.StringIO(r.raw))

    def update(self, data):
        self.data = vcal.fix(data)
        self.instance = vobject.readOne(StringIO.StringIO(self.data))

    def save(self):
        if self.instance is not None:
            (id, path) = commands.create_event(self.client, self.parent, 
                                               self.instance.serialize(), 
                                               self.id)
            self.id = id
            if path is not None:
                self.url = urlparse.urlparse(path)
        return self

    def __str__(self):
        return "Event: %s" % url.make(self.url)




from utils import commands
