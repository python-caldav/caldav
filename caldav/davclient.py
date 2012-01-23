#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import httplib
import urlparse
from lxml import etree

from caldav.lib import error


class DAVResponse:
    """
    This class is a response from a DAV request.
    Since we often get XML responses, it tries to parse it into `self.tree`
    """
    raw = ""
    reason = ""
    tree = None
    headers = {}
    status = 0

    def __init__(self, response):
        self.raw = response.read()
        self.headers = response.getheaders()
        self.status = response.status
        self.reason = response.reason

        try:
            self.tree = etree.XML(self.raw)
        except:
            self.tree = None


class DAVClient:
    """
    Basic client for webdav, heavily based on httplib
    """
    proxy = None
    url = None

    def __init__(self, url, proxy=None):
        """
        Connects to the server, as defined in the url.
        Parameters:
         * url: A fully qualified url: `scheme://user:pass@hostname:port`
         * proxy: A string defining a proxy server: `hostname:port`
        """

        self.url = urlparse.urlparse(url)

        # Prepare proxy info
        if proxy is not None:
            self.proxy = proxy.split(":")
            if len(self.proxy) == 1:
                self.proxy.append(8080)
            else:
                self.proxy[1] = int(self.proxy[1])

        # Build global headers
        self.headers = {"User-Agent": "Mozilla/5.0",
                        "Content-Type": "text/xml",
                        "Accept": "text/xml"}
        if self.url.username is not None:
            hash = (("%s:%s" % (self.url.username.replace('%40', '@'),
                                self.url.password))\
                    .encode('base64')[:-1])
            self.headers['authorization'] = "Basic %s" % hash

        # Connection proxy
        if self.proxy is not None:
            self.handle = httplib.HTTPConnection(*self.proxy)
        # direct, https
        elif self.url.port == 443 or self.url.scheme == 'https':
            self.handle = httplib.HTTPSConnection(self.url.hostname,
                                                  self.url.port)
        # direct, http
        else:
            self.handle = httplib.HTTPConnection(self.url.hostname,
                                                 self.url.port)

    def propfind(self, url, props="", depth=0):
        """
        Send a propfind request.

        Parameters:
         * url: url for the root of the propfind.
         * props = [dav.DisplayName(), ...], properties we want
         * depth: maximum recursion depth

        Returns
         * DAVResponse
        """
        return self.request(url, "PROPFIND", props, {'depth': str(depth)})

    def proppatch(self, url, body):
        """
        Send a proppatch request.

        Parameters:
         * url: url for the root of the propfind.
         * body: XML propertyupdate request

        Returns
         * DAVResponse
        """
        return self.request(url, "PROPPATCH", body)

    def report(self, url, query="", depth=0):
        """
        Send a report request.

        Parameters:
         * url: url for the root of the propfind.
         * query: XML request
         * depth: maximum recursion depth

        Returns
         * DAVResponse
        """
        return self.request(url, "REPORT", query,
                            {'depth': str(depth), "Content-Type":
                             "application/xml; charset=\"utf-8\""})

    def mkcol(self, url, body):
        """
        Send a mkcol request.

        Parameters:
         * url: url for the root of the propfind.
         * body: XML request

        Returns
         * DAVResponse
        """
        return self.request(url, "MKCOL", body)

    def put(self, url, body, headers={}):
        """
        Send a put request.
        """
        return self.request(url, "PUT", body, headers)

    def delete(self, url):
        """
        Send a delete request.
        """
        return self.request(url, "DELETE")

    def request(self, url, method="GET", body="", headers={}):
        """
        Actually sends the request
        """
        if self.proxy is not None:
            url = "%s://%s:%s%s" % (self.url.scheme, self.url.hostname,
                                    self.url.port, url)

        combined_headers = self.headers
        combined_headers.update(headers)
        if body is None or body == "" and "Content-Type" in combined_headers:
            del combined_headers["Content-Type"]
        self.handle.request(method, url, body, combined_headers)

        response = DAVResponse(self.handle.getresponse())

        # this is an error condition the application wants to know
        if response.status == httplib.FORBIDDEN or \
                response.status == httplib.UNAUTHORIZED:
            ex = error.AuthorizationError()
            ex.url = url
            ex.reason = response.reason
            raise ex

        return response
