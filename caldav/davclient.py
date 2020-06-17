#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import logging
import re
import requests
import six
from caldav.lib.python_utilities import to_wire, to_unicode, to_normal_str
from lxml import etree

from caldav.lib import error
from caldav.lib.url import URL
from caldav.objects import Principal

if six.PY3:
    from urllib.parse import unquote
else:
    from urlparse import unquote

log = logging.getLogger('caldav')


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
        ## ref https://github.com/python-caldav/caldav/issues/81,
        ## incidents with a response without a reason has been
        ## observed
        try:
            self.reason = response.reason
        except AttributeError:
            self.reason = ''
        log.debug("response headers: " + str(self.headers))
        log.debug("response status: " + str(self.status))
        log.debug("raw response: " + str(self.raw))

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

    def __init__(self, url, proxy=None, username=None, password=None,
                 auth=None, ssl_verify_cert=True):
        """
        Sets up a HTTPConnection object towards the server in the url.
        Parameters:
         * url: A fully qualified url: `scheme://user:pass@hostname:port`
         * proxy: A string defining a proxy server: `hostname:port`
         * username and password should be passed as arguments or in the URL
         * auth and ssl_verify_cert is passed to requests.request.
         ** ssl_verify_cert can be the path of a CA-bundle or False.
        """

        self.session = requests.Session()

        log.debug("url: " + str(url))
        self.url = URL.objectify(url)

        # Prepare proxy info
        if proxy is not None:
            self.proxy = proxy
            # requests library expects the proxy url to have a scheme
            if re.match('^.*://', proxy) is None:
                self.proxy = self.url.scheme + '://' + proxy

            # add a port is one is not specified
            # TODO: this will break if using basic auth and embedding
            # username:password in the proxy URL
            p = self.proxy.split(":")
            if len(p) == 2:
                self.proxy += ':8080'
            log.debug("init - proxy: %s" % (self.proxy))

        # Build global headers
        self.headers = {"User-Agent": "Mozilla/5.0",
                        "Content-Type": "text/xml",
                        "Accept": "text/xml, text/calendar"}
        if self.url.username is not None:
            username = unquote(self.url.username)
            password = unquote(self.url.password)

        self.username = username
        self.password = password
        self.auth = auth
        # TODO: it's possible to force through a specific auth method here,
        # but no test code for this.
        self.ssl_verify_cert = ssl_verify_cert
        self.url = self.url.unauth()
        log.debug("self.url: " + str(url))

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
        return self.request(url or self.url, "PROPFIND", props,
                            {'Depth': str(depth)})

    def proppatch(self, url, body, dummy=None):
        """
        Send a proppatch request.

        Parameters:
         * url: url for the root of the propfind.
         * body: XML propertyupdate request
         * dummy: compatibility parameter

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

    def mkcol(self, url, body, dummy=None):
        """
        Send a MKCOL request.

        MKCOL is basically not used with caldav, one should use
        MKCALENDAR instead.  However, some calendar servers MAY allow
        "subcollections" to be made in a calendar, by using the MKCOL
        query.  As for 2020-05, this method is not exercised by test
        code or referenced anywhere else in the caldav library, it's
        included just for the sake of completeness.  And, perhaps this
        DAVClient class can be used for vCards and other WebDAV
        purposes.

        Parameters:
         * url: url for the root of the mkcol
         * body: XML request
         * dummy: compatibility parameter

        Returns
         * DAVResponse
        """
        return self.request(url, "MKCOL", body)

    def mkcalendar(self, url, body="", dummy=None):
        """
        Send a mkcalendar request.

        Parameters:
         * url: url for the root of the mkcalendar
         * body: XML request
         * dummy: compatibility parameter

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
            log.debug("using proxy - %s" % (proxies))

        # ensure that url is a normal string
        url = str(url)

        combined_headers = dict(self.headers)
        combined_headers.update(headers)
        if body is None or body == "" and "Content-Type" in combined_headers:
            del combined_headers["Content-Type"]

        log.debug(
            "sending request - method={0}, url={1}, headers={2}\nbody:\n{3}"
            .format(method, url, combined_headers, to_normal_str(body)))
        auth = None
        if self.auth is None and self.username is not None:
            auth = requests.auth.HTTPDigestAuth(self.username, self.password)
        else:
            auth = self.auth

        r = self.session.request(method, url, data=to_wire(body),
                             headers=combined_headers, proxies=proxies,
                             auth=auth, verify=self.ssl_verify_cert)
        response = DAVResponse(r)

        # If server supports BasicAuth and not DigestAuth, let's try again:
        if response.status == 401 and self.auth is None and auth is not None:
            auth = requests.auth.HTTPBasicAuth(self.username, self.password)
            r = self.session.request(method, url, data=to_wire(body),
                                 headers=combined_headers, proxies=proxies,
                                 auth=auth, verify=self.ssl_verify_cert)
            response = DAVResponse(r)

        self.auth = auth

        # this is an error condition the application wants to know
        if response.status == requests.codes.forbidden or \
                response.status == requests.codes.unauthorized:
            ex = error.AuthorizationError()
            ex.url = url
            ## ref https://github.com/python-caldav/caldav/issues/81,
            ## incidents with a response without a reason has been
            ## observed
            try:
                ex.reason = response.reason
            except AttributeError:
                ex.reason = "None given"
            raise ex

        # let's save the auth object and remove the user/pass information
        if not self.auth and auth:
            self.auth = auth
            del self.username
            del self.password

        return response
