#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import httplib
import urlparse
from lxml import etree


class DAVResponse:
    raw = ""
    tree = None
    headers = {}
    status = 0

    def __init__(self, response):
        self.raw = response.read()
        self.headers = response.getheaders()
        self.status = response.status

        try:
            self.tree = etree.XML (self.raw)
        except:
            self.tree = None
        

class DAVClient:
    def __init__(self, url):
        url = urlparse.urlparse(url)
        self.hostname = url.hostname
        self.port = url.port
        self.username = url.username
        self.password = url.password

        # Build global headers
        self.headers = { "User-Agent": "Mozilla/5.0" }
        if self.username is not None:
            hash = (("%s:%s" % (self.username, self.password))\
                    .encode('base64')[:-1])
            self.headers['authorization'] = "Basic %s" % hash

        # Connect
        if self.port == 443 or url.scheme == "https":
            self.handle = httplib.HTTPSConnection(self.hostname, self.port)
        else:
            self.handle = httplib.HTTPConnection(self.hostname, self.port)
        self.handle.connect()

    def propfind(self, url, props = "", depth = 0):
        return self.request(url, "PROPFIND", props, {'depth': depth})

    def report(self, url, query = "", depth = 0):
        return self.request(url, "REPORT", query, 
                            {'depth': depth, "Content-Type": 
                             "application/xml; charset=\"utf-8\""})

    def mkcol(self, url, body):
        return self.request(url, "MKCOL", body)

    def put(self, url, body):
        return self.request(url, "PUT", body)

    def delete(self, url):
        return self.request(url, "DELETE")

    def request(self, url, method = "GET", body = "", headers = {}):
        headers.update(self.headers)
        self.handle.request(method, url, body, headers)
        return DAVResponse(self.handle.getresponse())
