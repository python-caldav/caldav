#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import requests
import logging
import urllib
import re
from lxml import etree

from caldav.lib import error
from caldav.lib.url import URL
from caldav.objects import Principal


class DAVResponse:
    """
    This class is a response from a DAV request.  It is instantiated from
    the DAVClient class.  End users of the library should not need to
    know anything about this class.  Since we often get XML responses,
    it tries to parse it into `self.tree`
    """
    raw = ""
    reason = ""
    tree = None
    headers = {}
    status = 0

    def __init__(self, response):
        self.raw = response.content
        self.headers = response.headers
        self.status = response.status_code
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
    Basic client for webdav, uses the requests lib; gives access to
    low-level operations towards the caldav server.

    Unless you have special needs, you should probably care most about
    the __init__ and principal methods.
    """
    proxy = None
    url = None

    def __init__(self, url, proxy=None, username=None, password=None, auth=None, ssl_verify_cert=None):
        """
        Sets up a HTTPConnection object towards the server in the url.
        Parameters:
         * url: A fully qualified url: `scheme://user:pass@hostname:port`
         * proxy: A string defining a proxy server: `hostname:port`
         * username and password should be passed as arguments or in the URL
        """

        logging.debug("url: " + str(url))
        self.url = URL.objectify(url)

        # Prepare proxy info
        if proxy is not None:
            self.proxy = proxy
            if re.match('^.*://', proxy) is None:  # requests library expects the proxy url to have a scheme
                self.proxy = self.url.scheme + '://' + proxy

            # add a port is one is not specified
            # TODO: this will break if using basic auth and embedding 
            # username:password in the proxy URL
            p = self.proxy.split(":")
            if len(p) == 2:
                self.proxy += ':8080'
            logging.debug("init - proxy: %s" % (self.proxy))

        # Build global headers
        self.headers = {"User-Agent": "Mozilla/5.0",
                        "Content-Type": "text/xml",
                        "Accept": "text/xml"}
        if self.url.username is not None:
            username = urllib.unquote(self.url.username)
            password = urllib.unquote(self.url.password)

        self.username = username
        self.password = password
        self.auth = auth
        self.ssl_verify_cert = ssl_verify_cert
        self.url = self.url.unauth()
        logging.debug("self.url: " + str(url))

    def principal(self):
        """
        Convenience method, it gives a bit more object-oriented feel to
        write client.principal() than Principal(client).

        This method returns a :class:`caldav.Principal` object, with
        higher-level methods for dealing with the principals
        calendars.
        """
        return Principal(self)

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
        return self.request(url or self.url, "PROPFIND", props, {'Depth': str(depth)})

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
                            {'Depth': str(depth), "Content-Type":
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

    def mkcalendar(self, url, body=""):
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

        # objectify the url
        url = URL.objectify(url)

        proxies = None
        if self.proxy is not None:
            proxies = {url.scheme: self.proxy}
            logging.debug("using proxy - %s" % (proxies))

        # ensure that url is a unicode string
        url = unicode(url)

        combined_headers = self.headers
        combined_headers.update(headers)
        if body is None or body == "" and "Content-Type" in combined_headers:
            del combined_headers["Content-Type"]

        if isinstance(body, unicode):
            body = body.encode('utf-8')

        logging.debug("sending request - method={0}, url={1}, headers={2}\nbody:\n{3}".format(method, url.encode('utf-8'), combined_headers, body))
        auth = None
        if self.auth is None and self.username is not None:
            auth = requests.auth.HTTPDigestAuth(self.username, self.password)
        else:
            auth = self.auth

        r = requests.request(method, url, data=body, headers=combined_headers, proxies=proxies, auth=auth)
        response = DAVResponse(r)

        ## If server supports BasicAuth and not DigestAuth, let's try again:
        if response.status == 401 and self.auth is None and auth is not None:
            auth = requests.auth.HTTPBasicAuth(self.username, self.password)
            r = requests.request(method, url, data=body, headers=combined_headers, proxies=proxies, auth=auth)
            response = DAVResponse(r)

        # this is an error condition the application wants to know
        if response.status == requests.codes.forbidden or \
                response.status == requests.codes.unauthorized:
            ex = error.AuthorizationError()
            ex.url = url
            ex.reason = response.reason
            raise ex

        ## let's save the auth object and remove the user/pass information
        if not self.auth and auth:
            self.auth = auth
            del self.username
            del self.password

        return response
