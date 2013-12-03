#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import urlparse

class URL:
    """Addresses may be one out of three:

    1) a path relative to the DAV-root, i.e. "someuser/calendar" may
    refer to
    "http://my.davical-server.example.com/caldav.php/someuser/calendar".

    2) an absolute path, i.e. "/caldav.php/someuser/calendar"

    3) a fully qualified URL,
    i.e. "http://someuser:somepass@my.davical-server.example.com/caldav.php/someuser/calendar".
    Remark that hostname, port, user, pass is typically given when
    instantiating the DAVClient object and cannot be overridden later.

    As of 2013-11, some methods expects strings and some expects
    urlparse.ParseResult objects, some expects fully qualified URLs
    and most expects absolute paths.  The purpose of this class is to
    ensure consistency and at the same time maintaining backward
    compatibility.  Basically, all methods should accept any kind of
    URL.
    """
    def __init__(self, url):
        if isinstance(url, urlparse.ParseResult) or isinstance(url, urlparse.SplitResult):
            self.url_parsed = url
            self.url_raw = None
        else:
            self.url_raw = url
            self.url_parsed = None

    def __eq__(self, other):
        return str(self) == str(other)

    ## TODO: better naming?  Will return url if url is already an URL
    ## object, else will instantiate a new URL object
    @classmethod
    def objectify(self, url):
        if isinstance(url, URL):
            return url
        else:
            return URL(url)

    ## To deal with all kind of methods/properties in the ParseResult
    ## class
    def __getattr__(self, attr):
        if self.url_parsed is None:
            self.url_parsed = urlparse.urlparse(self.url_raw)
        return getattr(self.url_parsed, attr)

    ## returns the url in text format
    def __str__(self):
        if self.url_raw is None:
            self.url_raw = self.url_parsed.geturl()
        return self.url_raw

    def __repr__(self):
        return "URL(%s)" % str(self)

    def join(self, path):
        """
        assumes this object is the base URL or base path.  If the path
        is relative, it should be appended to the base.  If the path
        is absolute, it should be added to the connection details of
        self.  If the path already contains connection details and the
        connection details differ from self, raise an error.
        """
        path = URL.objectify(path)
        if (
            (path.scheme and self.scheme and path.scheme != self.scheme)
            or
            (path.netloc and self.netloc and path.netloc != self.netloc)
        ):
            raise ValueError("%s can't be joined with %s" % (self, path))
                
        if path.path[0] == '/':
            ret_path = path.path
        else:
            sep = "/"
            if self.path.endswith("/"):
                sep = ""
            ret_path = "%s%s%s" % (self.path, sep, path.path)
        return URL(urlparse.ParseResult(
            self.scheme or path.scheme, self.netloc or path.netloc, ret_path, path.params, path.query, path.fragment))

def join(url, part):
    sep = "/"
    if url.endswith("/"):
        sep = ""
    return "%s%s%s" % (url, sep, part)


def make(url, path=None):
    u = ""

    if path is not None:
        u = urlparse.urlunparse((url.scheme, url.netloc, path, url.params,
                                 url.query, url.fragment))
    else:
        u = url.geturl()

    return u


def canonicalize(url, parent=None):
    if url.scheme:
        netloc_unauth = ('%s:%s' % (url.hostname, url.port)
                         if url.port not in (80, None)
                         else url.hostname)
        return urlparse.urlunparse((url.scheme, netloc_unauth,
                                    url.path.replace('//', '/'),
                                    url.params, url.query, url.fragment))
    else:
        return urlparse.urljoin(parent.canonical_url,
                                url.path.replace('//', '/'))
