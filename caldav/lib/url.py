#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from caldav.lib.python_utilities import to_normal_str
from caldav.lib.python_utilities import to_unicode
from six import PY3

if PY3:
    from urllib.parse import (
        ParseResult,
        SplitResult,
        urlparse,
        unquote,
        quote,
        urlunparse,
    )
else:
    from urlparse import ParseResult, SplitResult
    from urlparse import urlparse, urlunparse
    from urllib import unquote, quote


def uc2utf8(input):
    # argh!  this feels wrong, but seems to be needed.
    if not PY3 and type(input) == unicode:
        return input.encode("utf-8")
    else:
        return input


class URL:
    """
    This class is for wrapping URLs into objects.  It's used
    internally in the library, end users should not need to know
    anything about this class.  All methods that accept URLs can be
    fed either with an URL object, a string or an urlparse.ParsedURL
    object.

    Addresses may be one out of three:

    1) a path relative to the DAV-root, i.e. "someuser/calendar" may
    refer to
    "http://my.davical-server.example.com/caldav.php/someuser/calendar".

    2) an absolute path, i.e. "/caldav.php/someuser/calendar"

    3) a fully qualified URL, i.e.
    "http://someuser:somepass@my.davical-server.example.com/caldav.php/someuser/calendar".
    Remark that hostname, port, user, pass is typically given when
    instantiating the DAVClient object and cannot be overridden later.

    As of 2013-11, some methods in the caldav library expected strings
    and some expected urlParseResult objects, some expected
    fully qualified URLs and most expected absolute paths.  The purpose
    of this class is to ensure consistency and at the same time
    maintaining backward compatibility.  Basically, all methods should
    accept any kind of URL.

    """

    def __init__(self, url):
        if isinstance(url, ParseResult) or isinstance(url, SplitResult):
            self.url_parsed = url
            self.url_raw = None
        else:
            self.url_raw = url
            self.url_parsed = None

    def __bool__(self):
        if self.url_raw or self.url_parsed:
            return True
        else:
            return False

    def __ne__(self, other):
        return not self == other

    def __eq__(self, other):
        if str(self) == str(other):
            return True
        # The URLs could have insignificant differences
        me = self.canonical()
        if hasattr(other, "canonical"):
            other = other.canonical()
        return str(me) == str(other)

    def __hash__(self):
        return hash(str(self))

    # TODO: better naming?  Will return url if url is already an URL
    # object, else will instantiate a new URL object
    @classmethod
    def objectify(self, url):
        if url is None:
            return None
        if isinstance(url, URL):
            return url
        else:
            return URL(url)

    # To deal with all kind of methods/properties in the ParseResult
    # class
    def __getattr__(self, attr):
        if "url_parsed" not in vars(self):
            raise AttributeError
        if self.url_parsed is None:
            self.url_parsed = urlparse(self.url_raw)
        if hasattr(self.url_parsed, attr):
            return getattr(self.url_parsed, attr)
        else:
            return getattr(self.__unicode__(), attr)

    # returns the url in text format
    def __str__(self):
        return to_normal_str(self.__unicode__())

    # returns the url in text format
    def __unicode__(self):
        if self.url_raw is None:
            self.url_raw = self.url_parsed.geturl()
        return to_unicode(self.url_raw)

    def __repr__(self):
        return "URL(%s)" % str(self)

    def strip_trailing_slash(self):
        if str(self)[-1] == "/":
            return URL.objectify(str(self)[:-1])
        else:
            return self

    def is_auth(self):
        return self.username is not None

    def unauth(self):
        if not self.is_auth():
            return self
        return URL.objectify(
            ParseResult(
                self.scheme,
                "%s:%s"
                % (self.hostname, self.port or {"https": 443, "http": 80}[self.scheme]),
                self.path.replace("//", "/"),
                self.params,
                self.query,
                self.fragment,
            )
        )

    def canonical(self):
        """
        a canonical URL ... remove authentication details, make sure there
        are no double slashes, and to make sure the URL is always the same,
        run it through the urlparser, and make sure path is properly quoted
        """
        url = self.unauth()

        arr = list(self.url_parsed)
        ## quoting path and removing double slashes
        arr[2] = quote(unquote(url.path.replace("//", "/")))
        ## sensible defaults
        if not arr[0]:
            arr[0] = "https"
        if arr[1] and not ":" in arr[1]:
            if arr[0] == "https":
                portpart = ":443"
            elif arr[0] == "http":
                portpart = ":80"
            else:
                portpart = ""
            arr[1] += portpart

        # make sure to delete the string version
        url.url_raw = urlunparse(arr)
        url.url_parsed = None

        return url

    def join(self, path):
        """
        assumes this object is the base URL or base path.  If the path
        is relative, it should be appended to the base.  If the path
        is absolute, it should be added to the connection details of
        self.  If the path already contains connection details and the
        connection details differ from self, raise an error.
        """
        pathAsString = str(path)
        if not path or not pathAsString:
            return self
        path = URL.objectify(path)
        if (
            (path.scheme and self.scheme and path.scheme != self.scheme)
            or (path.hostname and self.hostname and path.hostname != self.hostname)
            or (path.port and self.port and path.port != self.port)
        ):
            raise ValueError("%s can't be joined with %s" % (self, path))

        if path.path[0] == "/":
            ret_path = uc2utf8(path.path)
        else:
            sep = "/"
            if self.path.endswith("/"):
                sep = ""
            ret_path = "%s%s%s" % (self.path, sep, uc2utf8(path.path))
        return URL(
            ParseResult(
                self.scheme or path.scheme,
                self.netloc or path.netloc,
                ret_path,
                path.params,
                path.query,
                path.fragment,
            )
        )


def make(url):
    """Backward compatibility"""
    return URL.objectify(url)
