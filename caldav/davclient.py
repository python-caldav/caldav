#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import logging
import re
import requests
import six
from caldav.lib.python_utilities import to_wire, to_unicode, to_normal_str
from lxml import etree

from caldav.elements import dav, cdav, ical

from caldav.lib import error
from caldav.lib.url import URL
from caldav.objects import Principal, errmsg, log

if six.PY3:
    from urllib.parse import unquote
else:
    from urlparse import unquote

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
        self.headers = response.headers
        log.debug("response headers: " + str(self.headers))
        log.debug("response status: " + str(self.status))
        if (self.headers.get('Content-Type', '').startswith('text/xml') or
            self.headers.get('Content-Type', '').startswith('application/xml')):
            try:
                content_length = int(self.headers['Content-Length'])
            except:
                content_length=-1
            if content_length == 0:
                self._raw = ''
                self.tree = None
                log.debug("No content delivered")
            else:
                #self.tree = etree.parse(response.raw, parser=etree.XMLParser(remove_blank_text=True))
                self.tree = etree.XML(response.content, parser=etree.XMLParser(remove_blank_text=True))
                if log.level <= logging.DEBUG:
                    log.debug(etree.tostring(self.tree, pretty_print=True))
        elif (self.headers.get('Content-Type', '').startswith('text/calendar') or
              self.headers.get('Content-Type', '').startswith('text/plain')):
              ## text/plain is typically for errors, we shouldn't see it on 200/207 responses.
              ## TODO: may want to log an error if it's text/plain and 200/207.
            self._raw = response.content
        else:
            ## probably content-type was not given, i.e. iCloud does not seem to include those
            if 'Content-Type' in self.headers:
                log.error("unexpected content type from server: %s. %s" % (self.headers['Content-Type'], error.ERR_FRAGMENT))
            self._raw = response.content
            try:
                self.tree = etree.XML(self._raw, parser=etree.XMLParser(remove_blank_text=True))
            except:
                pass

        if hasattr(self, '_raw'):
            log.debug(self._raw)
            # ref https://github.com/python-caldav/caldav/issues/112 stray CRs may cause problems
            if type(self._raw) == bytes:
                self._raw = self._raw.replace(b'\r\n', b'\n')
            elif type(self._raw) == str:
                self._raw = self._raw.replace('\r\n', '\n')
        self.status = response.status_code
        ## ref https://github.com/python-caldav/caldav/issues/81,
        ## incidents with a response without a reason has been
        ## observed
        try:
            self.reason = response.reason
        except AttributeError:
            self.reason = ''

    @property
    def raw(self):
        ## TODO: this should not really be needed?
        if not hasattr(self, '_raw'):
            self._raw = etree.tostring(self.tree, pretty_print=True)
        return self._raw

    def _strip_to_multistatus(self):
        """
        The general format of inbound data is something like this:

        <xml><multistatus>
            <response>(...)</response>
            <response>(...)</response>
            (...)
        </multistatus></xml>

        but sometimes the multistatus and/or xml element is missing in
        self.tree.  We don't want to bother with the multistatus and
        xml tags, we just want the response list.

        An "Element" in the lxml library is a list-like object, so we
        should typically return the element right above the responses.
        If there is nothing but a response, return it as a list with
        one element.

        (The equivalent of this method could probably be found with a
        simple XPath query, but I'm not much into XPath)
        """
        tree = self.tree
        if (tree.tag == 'xml' and tree[0].tag == dav.MultiStatus.tag):
            return tree[0]
        if (tree.tag == dav.MultiStatus.tag):
            return self.tree
        return [ self.tree ]

    def validate_status(self, status):
        """
        status is a string like "HTTP/1.1 404 Not Found".
        200, 207 and 404 are considered good statuses.
        """
        if (' 200 ' not in status and
            ' 207 ' not in status and
            ' 404 ' not in status):
            raise error.ResponseError(status)

    def _parse_response(self, response):
        """
        One response should contain one or zero status children, one
        href tag and zero or more propstats.  Find them, assert there
        isn't more in the response and return those three fields
        """
        status = None
        href = None
        propstats = []
        error.assert_(response.tag == dav.Response.tag)
        for elem in response:
            if elem.tag == dav.Status.tag:
                error.assert_(not status)
                status = elem.text
                error.assert_(status)
                self.validate_status(status)
            elif elem.tag == dav.Href.tag:
                assert not href
                href = unquote(elem.text)
            elif elem.tag == dav.PropStat.tag:
                propstats.append(elem)
            else:
                error.assert_(False)
        error.assert_(href)
        return (href, propstats, status)

    def find_objects_and_props(self, compatibility_mode=False):
        """Check the response from the server, check that it is on an expected format,
        find hrefs and props from it and check statuses delivered.

        The parsed data will be put into self.objects, a dict {href:
        {proptag: prop_element}}.  Further parsing of the prop_element
        has to be done by the caller.

        self.sync_token will be populated if found, self.objects will be populated.
        """
        self.objects = {}
        
        responses = self._strip_to_multistatus()
        for r in responses:
            if r.tag == dav.SyncToken.tag:
                self.sync_token = r.text
                continue
            error.assert_(r.tag == dav.Response.tag)

            (href, propstats, status) = self._parse_response(r)
            error.assert_(not href in self.objects)
            self.objects[href] = {}

            ## The properties may be delivered either in one
            ## propstat with multiple props or in multiple
            ## propstat
            for propstat in propstats:
                cnt = 0
                status = propstat.find(dav.Status.tag)
                error.assert_(status is not None)
                if (status is not None):
                    error.assert_(len(status) == 0)
                    cnt += 1
                    self.validate_status(status.text)
                    if not compatibility_mode:
                        ## if a prop was not found, ignore it
                        if ' 404 ' in status.text:
                            continue
                for prop in propstat.iterfind(dav.Prop.tag):
                    cnt += 1
                    for theprop in prop:
                        self.objects[href][theprop.tag] = theprop

                ## there shouldn't be any more elements except for status and prop
                error.assert_(cnt == len(propstat))

        return self.objects

    def _expand_prop(self, proptag, props_found, multi_value_allowed=False, xpath=None):
        values = []
        if proptag in props_found:
            prop_xml = props_found[proptag]
            if prop_xml.items():
                import pdb; pdb.set_trace()
            if not xpath and len(prop_xml)==0:
                if prop_xml.text:
                    values.append(prop_xml.text)
            else:
                _xpath = xpath if xpath else ".//*"
                leafs = prop_xml.findall(_xpath)
                values = []
                for leaf in leafs:
                    if leaf.items():
                        import pdb; pdb.set_trace()
                    if leaf.text:
                        values.append(leaf.text)
                    else:
                        values.append(leaf.tag)
        if multi_value_allowed:
            return values
        else:
            if not values:
                return None
            error.assert_(len(values)==1)
            return values[0]

    def expand_simple_props(self, props=[], multi_value_props=[], xpath=None):
        """
        The find_objects_and_props() will stop at the xml element
        below the prop tag.  This method will expand those props into
        text.

        Executes find_objects_and_props if not run already, then
        modifies and returns self.objects.
        """
        if not hasattr(self, 'objects'):
            self.find_objects_and_props()
        for href in self.objects:
            props_found = self.objects[href]
            for prop in props:
                props_found[prop.tag] = self._expand_prop(prop.tag, props_found, xpath=xpath)
            for prop in multi_value_props:
                props_found[prop.tag] = self._expand_prop(prop.tag, props_found, xpath=xpath, multi_value_allowed=True)
        return self.objects

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

        r = self.session.request(
            method, url, data=to_wire(body),
            headers=combined_headers, proxies=proxies, auth=auth,
            verify=self.ssl_verify_cert, stream=False) ## TODO: optimize with stream=True maybe
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
