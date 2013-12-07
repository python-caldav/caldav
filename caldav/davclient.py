#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import httplib
import logging
import urllib
from lxml import etree

from caldav.lib import error
from caldav.lib.url import URL


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
        logging.debug("response headers: " + str(self.headers))
        logging.debug("response status: " + str(self.status))
        logging.debug("raw response: " + str(self.raw))

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

    def __init__(self, url, proxy=None, username=None, password=None):
        """
        Sets up a HTTPConnection object towards the server in the url.
        Parameters:
         * url: A fully qualified url: `scheme://user:pass@hostname:port`
         * proxy: A string defining a proxy server: `hostname:port`
        """

        self.url = URL.objectify(url)

        # Prepare proxy info
        if proxy is not None:
            # TODO: this will break if using basic auth and embedding 
            # username:password in the proxy URL
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
            username = urllib.unquote(self.url.username)
            password = urllib.unquote(self.url.password)
        if username is not None:
            hash = (("%s:%s" % (username, password))
                    .encode('base64')[:-1])
            self.headers['authorization'] = "Basic %s" % hash

        # Connection proxy
        if self.proxy is not None:
            self.handle = httplib.HTTPConnection(*self.proxy)
        # direct, https
        # TODO: we shouldn't use SSL on http://weird.server.example.com:443/
        elif self.url.port == 443 or self.url.scheme == 'https':
            self.handle = httplib.HTTPSConnection(self.url.hostname,
                                                  self.url.port)
        # direct, http
        else:
            self.handle = httplib.HTTPConnection(self.url.hostname,
                                                 self.url.port)
        self.url = self.url.unauth()

    def propfind(self, url=None, props="", depth=0):
        """
        Send a propfind request.

        Parameters:
         * url: url for the root of the propfind.
         * props = (xml request), properties we want
         * depth: maximum recursion depth

        Returns
         * DAVResponse
        """
        return self.request(url or self.url, "PROPFIND", props, {'depth': str(depth)})

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
         * url: url for the root of the mkcol
         * body: XML request

        Returns
         * DAVResponse
        """
        return self.request(url, "MKCOL", body)

    def mkcalendar(self, url, body):
        """
        Send a mkcalendar request.

        Parameters:
         * url: url for the root of the mkcalendar
         * body: XML request

        Returns
         * DAVResponse
        """
        return self.request(url, "MKCALENDAR", body)

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
        url = URL.objectify(url)
        if self.proxy is not None:
            url = "%s://%s:%s%s" % (self.url.scheme, self.url.hostname,
                                    self.url.port, url.path)

        combined_headers = self.headers
        combined_headers.update(headers)
        if body is None or body == "" and "Content-Type" in combined_headers:
            del combined_headers["Content-Type"]

        try:
            logging.debug("sending request - method=%s, url=%s, headers=%s\nbody:\n%s" % (method, url, combined_headers, body))
            self.handle.request(method, url, body, combined_headers)
            response = DAVResponse(self.handle.getresponse())
        except httplib.BadStatusLine:
            # Try to reconnect
            self.handle.close()
            self.handle.connect()

            ## TODO: we're missing test code on this.  (will need to
            ## mock up a server to test this)
            self.handle.request(method, url, body, combined_headers)
            response = DAVResponse(self.handle.getresponse(n))

        # this is an error condition the application wants to know
        if response.status == httplib.FORBIDDEN or \
                response.status == httplib.UNAUTHORIZED:
            ex = error.AuthorizationError()
            ex.url = url
            ex.reason = response.reason
            raise ex

        return response
