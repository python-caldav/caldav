#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import httplib
import urlparse
from lxml import etree


class DAVResponse:
    """
    This class is a response from a DAV request.
    Since we often get XML responses, it tries to parse it into `self.tree`
    """
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
    """
    Basic client for webdav, heavily based on httplib
    """
    def __init__(self, url):
        """
        Connects to the server, as defined in the url.
        """
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
        """
        Send a propfind request.

        Parameters:
         * url: url for the root of the propfind.
         * props = [ns("C", "bla"), ...], properties we want
         * depth: maximum recursion depth

        Returns
           DAVResponse
        """
        return self.request(url, "PROPFIND", props, {'depth': depth})

    def proppatch(self, url, body):
        """
        Send a proppatch request.

        Parameters:
         * url: url for the root of the propfind.
         * body: XML propertyupdate request

        Returns
           DAVResponse
        """
        return self.request(url, "PROPPATCH", body)

    def report(self, url, query = "", depth = 0):
        """
        Send a report request.

        Parameters:
         * url: url for the root of the propfind.
         * query: XML request
         * depth: maximum recursion depth

        Returns
           DAVResponse
        """
        return self.request(url, "REPORT", query, 
                            {'depth': depth, "Content-Type": 
                             "application/xml; charset=\"utf-8\""})

    def mkcol(self, url, body):
        """
        Send a mkcol request.

        Parameters:
         * url: url for the root of the propfind.
         * body: XML request

        Returns
           DAVResponse
        """
        return self.request(url, "MKCOL", body)

    def put(self, url, body):
        """
        Send a put request.
        """
        return self.request(url, "PUT", body)

    def delete(self, url):
        """
        Send a delete request.
        """
        return self.request(url, "DELETE")

    def request(self, url, method = "GET", body = "", headers = {}):
        """
        Actually sends the request
        """
        headers.update(self.headers)
        self.handle.request(method, url, body, headers)
        return DAVResponse(self.handle.getresponse())
