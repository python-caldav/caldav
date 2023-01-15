#!/usr/bin/env python
# -*- encoding: utf-8 -*-
import logging
import re

import requests
import six
from caldav.elements import cdav
from caldav.elements import dav
from caldav.elements import ical
from caldav.lib import error
from caldav.lib.python_utilities import to_normal_str
from caldav.lib.python_utilities import to_unicode
from caldav.lib.python_utilities import to_wire
from caldav.lib.url import URL
from caldav.objects import Calendar
from caldav.objects import errmsg
from caldav.objects import log
from caldav.objects import Principal
from caldav.objects import ScheduleInbox
from caldav.objects import ScheduleOutbox
from caldav.requests import HTTPBearerAuth
from lxml import etree

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

        self._raw = response.content

        ## TODO: this if/else/elif could possibly be refactored, or we should
        ## consider to do streaming into the xmltree library as originally
        ## intended.  It only makes sense for really huge payloads though.
        if self.headers.get("Content-Type", "").startswith(
            "text/xml"
        ) or self.headers.get("Content-Type", "").startswith("application/xml"):
            try:
                content_length = int(self.headers["Content-Length"])
            except:
                content_length = -1
            if content_length == 0 or not self._raw:
                self._raw = ""
                self.tree = None
                log.debug("No content delivered")
            else:
                ## With response.raw we could be streaming the content, but it does not work because
                ## the stream often is compressed.  We could add uncompression on the fly, but not
                ## considered worth the effort as for now.
                # self.tree = etree.parse(response.raw, parser=etree.XMLParser(remove_blank_text=True))
                try:
                    self.tree = etree.XML(
                        self._raw, parser=etree.XMLParser(remove_blank_text=True)
                    )
                except:
                    logging.critical(
                        "Expected some valid XML from the server, but got this: \n"
                        + self._raw,
                        exc_info=True,
                    )
                    raise
                if log.level <= logging.DEBUG:
                    log.debug(etree.tostring(self.tree, pretty_print=True))
        elif self.headers.get("Content-Type", "").startswith(
            "text/calendar"
        ) or self.headers.get("Content-Type", "").startswith("text/plain"):
            ## text/plain is typically for errors, we shouldn't see it on 200/207 responses.
            ## TODO: may want to log an error if it's text/plain and 200/207.
            ## Logic here was moved when refactoring
            pass
        else:
            ## Probably no content type given (iCloud).  Some servers
            ## give text/html as the default when no content is
            ## delivered or on errors (ref
            ## https://github.com/python-caldav/caldav/issues/142).
            ## TODO: maybe just remove all of the code above in this if/else and let all
            ## data be parsed through this code.
            try:
                self.tree = etree.XML(
                    self._raw, parser=etree.XMLParser(remove_blank_text=True)
                )
            except:
                pass

        ## this if will always be true as for now, see other comments on streaming.
        if hasattr(self, "_raw"):
            log.debug(self._raw)
            # ref https://github.com/python-caldav/caldav/issues/112 stray CRs may cause problems
            if type(self._raw) == bytes:
                self._raw = self._raw.replace(b"\r\n", b"\n")
            elif type(self._raw) == str:
                self._raw = self._raw.replace("\r\n", "\n")
        self.status = response.status_code
        ## ref https://github.com/python-caldav/caldav/issues/81,
        ## incidents with a response without a reason has been
        ## observed
        try:
            self.reason = response.reason
        except AttributeError:
            self.reason = ""

    @property
    def raw(self):
        ## TODO: this should not really be needed?
        if not hasattr(self, "_raw"):
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
        if tree.tag == "xml" and tree[0].tag == dav.MultiStatus.tag:
            return tree[0]
        if tree.tag == dav.MultiStatus.tag:
            return self.tree
        return [self.tree]

    def validate_status(self, status):
        """
        status is a string like "HTTP/1.1 404 Not Found".  200, 207 and
        404 are considered good statuses.  The SOGo caldav server even
        returns "201 created" when doing a sync-report, to indicate
        that a resource was created after the last sync-token.  This
        makes sense to me, but I've only seen it from SOGo, and it's
        not in accordance with the examples in rfc6578.
        """
        if (
            " 200 " not in status
            and " 201 " not in status
            and " 207 " not in status
            and " 404 " not in status
        ):
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

    def find_objects_and_props(self):
        """Check the response from the server, check that it is on an expected format,
        find hrefs and props from it and check statuses delivered.

        The parsed data will be put into self.objects, a dict {href:
        {proptag: prop_element}}.  Further parsing of the prop_element
        has to be done by the caller.

        self.sync_token will be populated if found, self.objects will be populated.
        """
        self.objects = {}

        if "Schedule-Tag" in self.headers:
            self.schedule_tag = self.headers["Schedule-Tag"]

        responses = self._strip_to_multistatus()
        for r in responses:
            if r.tag == dav.SyncToken.tag:
                self.sync_token = r.text
                continue
            error.assert_(r.tag == dav.Response.tag)

            (href, propstats, status) = self._parse_response(r)
            ## I would like to do this assert here ...
            # error.assert_(not href in self.objects)
            ## but then there was https://github.com/python-caldav/caldav/issues/136
            if not href in self.objects:
                self.objects[href] = {}

            ## The properties may be delivered either in one
            ## propstat with multiple props or in multiple
            ## propstat
            for propstat in propstats:
                cnt = 0
                status = propstat.find(dav.Status.tag)
                error.assert_(status is not None)
                if status is not None:
                    error.assert_(len(status) == 0)
                    cnt += 1
                    self.validate_status(status.text)
                    ## if a prop was not found, ignore it
                    if " 404 " in status.text:
                        continue
                for prop in propstat.iterfind(dav.Prop.tag):
                    cnt += 1
                    for theprop in prop:
                        self.objects[href][theprop.tag] = theprop

                ## there shouldn't be any more elements except for status and prop
                error.assert_(cnt == len(propstat))

        return self.objects

    def _expand_simple_prop(
        self, proptag, props_found, multi_value_allowed=False, xpath=None
    ):
        values = []
        if proptag in props_found:
            prop_xml = props_found[proptag]
            error.assert_(not prop_xml.items())
            if not xpath and len(prop_xml) == 0:
                if prop_xml.text:
                    values.append(prop_xml.text)
            else:
                _xpath = xpath if xpath else ".//*"
                leafs = prop_xml.findall(_xpath)
                values = []
                for leaf in leafs:
                    error.assert_(not leaf.items())
                    if leaf.text:
                        values.append(leaf.text)
                    else:
                        values.append(leaf.tag)
        if multi_value_allowed:
            return values
        else:
            if not values:
                return None
            error.assert_(len(values) == 1)
            return values[0]

    ## TODO: "expand" does not feel quite right.
    def expand_simple_props(self, props=[], multi_value_props=[], xpath=None):
        """
        The find_objects_and_props() will stop at the xml element
        below the prop tag.  This method will expand those props into
        text.

        Executes find_objects_and_props if not run already, then
        modifies and returns self.objects.
        """
        if not hasattr(self, "objects"):
            self.find_objects_and_props()
        for href in self.objects:
            props_found = self.objects[href]
            for prop in props:
                props_found[prop.tag] = self._expand_simple_prop(
                    prop.tag, props_found, xpath=xpath
                )
            for prop in multi_value_props:
                props_found[prop.tag] = self._expand_simple_prop(
                    prop.tag, props_found, xpath=xpath, multi_value_allowed=True
                )
        return self.objects


class DAVClient:
    """
    Basic client for webdav, uses the requests lib; gives access to
    low-level operations towards the caldav server.

    Unless you have special needs, you should probably care most about
    the constructor (__init__), the principal method and the calendar method.
    """

    proxy = None
    url = None

    def __init__(
        self,
        url,
        proxy=None,
        username=None,
        password=None,
        auth=None,
        timeout=None,
        ssl_verify_cert=True,
        ssl_cert=None,
    ):
        """
        Sets up a HTTPConnection object towards the server in the url.
        Parameters:
         * url: A fully qualified url: `scheme://user:pass@hostname:port`
         * proxy: A string defining a proxy server: `hostname:port`
         * username and password should be passed as arguments or in the URL
         * auth, timeout and ssl_verify_cert are passed to requests.request.
         ** ssl_verify_cert can be the path of a CA-bundle or False.

        The requests library will honor a .netrc-file, if such a file exists
        username and password may be omitted.  Known bug: .netrc is honored
        even if a username/password is given, ref https://github.com/python-caldav/caldav/issues/206
        """

        self.session = requests.Session()

        log.debug("url: " + str(url))
        self.url = URL.objectify(url)

        # Prepare proxy info
        if proxy is not None:
            self.proxy = proxy
            # requests library expects the proxy url to have a scheme
            if re.match("^.*://", proxy) is None:
                self.proxy = self.url.scheme + "://" + proxy

            # add a port is one is not specified
            # TODO: this will break if using basic auth and embedding
            # username:password in the proxy URL
            p = self.proxy.split(":")
            if len(p) == 2:
                self.proxy += ":8080"
            log.debug("init - proxy: %s" % (self.proxy))

        # Build global headers
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "text/xml",
            "Accept": "text/xml, text/calendar",
        }
        if self.url.username is not None:
            username = unquote(self.url.username)
            password = unquote(self.url.password)

        self.username = username
        self.password = password
        ## I had problems with passwords with non-ascii letters in it ...
        if hasattr(self.password, "encode"):
            self.password = self.password.encode("utf-8")
        self.auth = auth
        # TODO: it's possible to force through a specific auth method here,
        # but no test code for this.
        self.timeout = timeout
        self.ssl_verify_cert = ssl_verify_cert
        self.ssl_cert = ssl_cert
        self.url = self.url.unauth()
        log.debug("self.url: " + str(url))

        self._principal = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        """
        Closes the DAVClient's session object
        """
        self.session.close()

    def principal(self, *largs, **kwargs):
        """
        Convenience method, it gives a bit more object-oriented feel to
        write client.principal() than Principal(client).

        This method returns a :class:`caldav.Principal` object, with
        higher-level methods for dealing with the principals
        calendars.
        """
        if not self._principal:
            self._principal = Principal(client=self, *largs, **kwargs)
        return self._principal

    def calendar(self, **kwargs):
        """Returns a calendar object.

        Typically, an URL should be given as a named parameter (url)

        No network traffic will be initiated by this method.

        If you don't know the URL of the calendar, use
        client.principal().calendar(...) instead, or
        client.principal().calendars()
        """
        return Calendar(client=self, **kwargs)

    def check_dav_support(self):
        try:
            ## SOGo does not return the full capability list on the caldav
            ## root URL, and that's OK according to the RFC ... so apparently
            ## we need to do an extra step here to fetch the URL of some
            ## element that should come with caldav extras.
            ## Anyway, packing this into a try-except in case it fails.
            response = self.options(self.principal().url)
        except:
            response = self.options(self.url)
        return response.headers.get("DAV", None)

    def check_cdav_support(self):
        support_list = self.check_dav_support()
        return support_list and "calendar-access" in support_list

    def check_scheduling_support(self):
        support_list = self.check_dav_support()
        return support_list and "calendar-auto-schedule" in support_list

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
        return self.request(url or self.url, "PROPFIND", props, {"Depth": str(depth)})

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
        return self.request(
            url,
            "REPORT",
            query,
            {"Depth": str(depth), "Content-Type": 'application/xml; charset="utf-8"'},
        )

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

    def post(self, url, body, headers={}):
        """
        Send a POST request.
        """
        return self.request(url, "POST", body, headers)

    def delete(self, url):
        """
        Send a delete request.
        """
        return self.request(url, "DELETE")

    def options(self, url):
        return self.request(url, "OPTIONS")

    def extract_auth_types(self, header):
        auth_types = header.lower().split(",")
        auth_types = map(lambda auth_type: auth_type.strip(), auth_types)
        auth_types = map(lambda auth_type: auth_type[: auth_type.find(" ")], auth_types)
        return list(filter(lambda auth_type: auth_type, auth_types))

    def request(self, url, method="GET", body="", headers={}):
        """
        Actually sends the request
        """
        combined_headers = self.headers.copy()
        combined_headers.update(headers)
        if (body is None or body == "") and "Content-Type" in combined_headers:
            del combined_headers["Content-Type"]

        proxies = None
        if self.proxy is not None:
            proxies = {url.scheme: self.proxy}
            log.debug("using proxy - %s" % (proxies))

        # objectify the url
        url = URL.objectify(url)

        log.debug(
            "sending request - method={0}, url={1}, headers={2}\nbody:\n{3}".format(
                method, str(url), combined_headers, to_normal_str(body)
            )
        )

        try:
            r = self.session.request(
                method,
                str(url),
                data=to_wire(body),
                headers=combined_headers,
                proxies=proxies,
                auth=self.auth,
                timeout=self.timeout,
                verify=self.ssl_verify_cert,
                cert=self.ssl_cert,
            )
            log.debug("server responded with %i %s" % (r.status_code, r.reason))
            response = DAVResponse(r)
        except:
            ## this is a workaround needed due to some weird server
            ## that would just abort the connection rather than send a
            ## 401 when an unauthenticated request with a body was
            ## sent to the server - ref https://github.com/python-caldav/caldav/issues/158
            if self.auth or not self.password:
                raise
            r = self.session.request(
                method="GET",
                url=str(url),
                headers=combined_headers,
                proxies=proxies,
                timeout=self.timeout,
                verify=self.ssl_verify_cert,
                cert=self.ssl_cert,
            )
            if not r.status_code == 401:
                raise

        if r.status_code == 401 and "WWW-Authenticate" in r.headers and not self.auth:
            auth_types = self.extract_auth_types(r.headers["WWW-Authenticate"])

            if self.password and self.username and "digest" in auth_types:
                self.auth = requests.auth.HTTPDigestAuth(self.username, self.password)
            elif self.password and self.username and "basic" in auth_types:
                self.auth = requests.auth.HTTPBasicAuth(self.username, self.password)
            elif self.password and "bearer" in auth_types:
                self.auth = HTTPBearerAuth(self.password)
            else:
                raise NotImplementedError(
                    "The server does not provide any of the currently "
                    "supported authentication methods: basic, digest"
                )

            return self.request(url, method, body, headers)

        elif r.status_code == 401 and "WWW-Authenticate" in r.headers and self.auth:

            ## Some (ancient) servers don't like UTF-8 binary auth with Digest authentication.
            ## An example are old SabreDAV based servers.  Not sure about UTF-8 and Basic Auth,
            ## but likely the same.  so retry if password is a bytes sequence and not a string
            ## (see commit 13a4714, which introduced this regression)

            auth_types = self.extract_auth_types(r.headers["WWW-Authenticate"])

            if self.password and hasattr(self.password, "decode"):
                if self.username and "digest" in auth_types:
                    self.auth = requests.auth.HTTPDigestAuth(
                        self.username, self.password.decode()
                    )
                elif self.username and "basic" in auth_types:
                    self.auth = requests.auth.HTTPBasicAuth(
                        self.username, self.password.decode()
                    )
                elif "bearer" in auth_types:
                    self.auth = HTTPBearerAuth(self.password.decode())

            self.username = None
            self.password = None
            return self.request(url, method, body, headers)

        # this is an error condition that should be raised to the application
        if (
            response.status == requests.codes.forbidden
            or response.status == requests.codes.unauthorized
        ):
            try:
                reason = response.reason
            except AttributeError:
                reason = "None given"
            raise error.AuthorizationError(url=str(url), reason=reason)

        return response
