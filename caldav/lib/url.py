#!/usr/bin/env python
import re
import sys
import urllib.parse
from typing import Any, cast
from urllib.parse import ParseResult, SplitResult, quote, unquote, urlparse, urlunparse

from caldav.lib.python_utilities import to_normal_str, to_unicode

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


def requote_path(path: str, safe: str = "/") -> str:
    """Normalise ``path`` without ever rewriting the spelling of an ``@``.

    Everything else is decoded and re-encoded, which is what fixes servers
    handing out unencoded spaces.  ``@`` and ``%40`` are lifted out of that
    round-trip and put back verbatim: RFC3986 section 2.2 makes ``@`` reserved,
    so the two spellings are different paths, and a client that "normalises"
    one into the other is renaming the resource it was asked about.  Which
    spelling to *mint* when there is no existing one to preserve is a separate
    question - see ``compatibility_hints.at_spelling_to_mint``.
    """
    safe = safe.replace("@", "")
    parts = re.split("(%40|@)", path)
    return "".join(
        part if part in ("%40", "@") else quote(unquote(part), safe=safe) for part in parts
    )


def alias_at_path(path: str, safe: str = "/") -> str:
    """``requote_path`` for a server that serves both spellings as one resource.

    Only for ``url.encode-at.identity: unsupported``.  The two spellings are
    then interchangeable, so collapsing them onto one gives a stable key to
    compare and hash by - which is what this library did unconditionally
    before it knew the difference.
    """
    return quote(unquote(path), safe=safe.replace("@", ""))


def normalise_path(path: str, safe: str = "/", preserve_at: bool = False) -> str:
    """Re-quote ``path``; ``preserve_at`` decides whether an ``@`` may be moved.

    Without it this is the plain ``quote(unquote(path), safe=safe)`` every
    caller did before ``url.encode-at`` existed, ``@`` and all - which is what
    keeps an unprobed server behaving exactly as it did.  With it, the two
    spellings are left exactly as they came; see :func:`requote_path`.
    """
    if preserve_at:
        return requote_path(path, safe=safe)
    return quote(unquote(path), safe=safe)


def unquote_preserving_at(text: str) -> str:
    """``unquote(text)``, except that ``%40`` is left as it stands.

    An href is the server telling us the name of a resource.  Decoding a
    ``%40`` in it renames that resource - to one that may not exist, and on a
    server that refuses the literal spelling, to one that cannot be fetched.
    """
    parts = re.split("(%40)", text)
    return "".join(part if part == "%40" else unquote(part) for part in parts)


class URL:
    """
    This class is for wrapping URLs into objects.  It's used
    internally in the library, end users should not need to know
    anything about this class.  All methods that accept URLs can be
    fed either with a URL object, a string or a urlparse.ParsedURL
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

    def __init__(self, url: str | ParseResult | SplitResult, alias_at: bool = True) -> None:
        if isinstance(url, ParseResult) or isinstance(url, SplitResult):
            self.url_parsed: ParseResult | SplitResult | None = url
            self.url_raw = None
        else:
            self.url_raw = url
            self.url_parsed = None
        ## Whether this URL's server serves "@" and "%40" as one resource
        ## (url.encode-at.identity: unsupported).  True is the default in the
        ## 3.x series - see the feature description: it is what this library
        ## has always done, and what every server probed so far does.  False is
        ## the RFC3986-conformant reading, in which two spellings of an "@" are
        ## two URLs.  It travels with the URL because
        ## canonical(), __eq__ and __hash__ need it and take no arguments;
        ## every URL derived from this one inherits it, so setting it once on
        ## the client's root URL reaches everything joined onto it.
        self.alias_at = alias_at

    def _derive(self, url: "str | ParseResult | SplitResult") -> "URL":
        """A new URL from ``url``, carrying this one's ``alias_at`` along."""
        return URL(url, alias_at=self.alias_at)

    def with_alias_at(self, alias_at: bool) -> "URL":
        """This URL, told whether its server aliases the two ``@`` spellings."""
        if alias_at == self.alias_at:
            return self
        return URL(self.url_parsed if self.url_raw is None else self.url_raw, alias_at=alias_at)

    def __bool__(self) -> bool:
        if self.url_raw or self.url_parsed:
            return True
        else:
            return False

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __eq__(self, other: object) -> bool:
        if str(self) == str(other):
            return True
        # The URLs could have insignificant differences
        me = self.canonical()
        if hasattr(other, "canonical"):
            other = other.canonical()
        return str(me) == str(other)

    def __hash__(self) -> int:
        # Must use canonical form to match __eq__ behavior
        return hash(str(self.canonical()))

    # TODO: better naming?  Will return url if url is already a URL
    # object, else will instantiate a new URL object
    @classmethod
    def objectify(
        cls, url: Self | str | ParseResult | SplitResult, alias_at: bool | None = None
    ) -> "URL":
        if url is None:
            return url
        if isinstance(url, URL):
            return url if alias_at is None else url.with_alias_at(alias_at)
        return URL(url) if alias_at is None else URL(url, alias_at=alias_at)

    # To deal with all kind of methods/properties in the ParseResult
    # class
    def __getattr__(self, attr: str):
        if "url_parsed" not in vars(self):
            raise AttributeError
        if self.url_parsed is None:
            self.url_parsed = cast(urllib.parse.ParseResult, urlparse(self.url_raw))
        if hasattr(self.url_parsed, attr):
            return getattr(self.url_parsed, attr)
        else:
            return getattr(self.__unicode__(), attr)

    # returns the url in text format
    def __str__(self) -> str:
        return to_normal_str(self.__unicode__())

    # returns the url in text format
    def __unicode__(self) -> str:
        if self.url_raw is None:
            if self.url_parsed is None:
                raise ValueError("Unexpected value None for self.url_parsed")

            self.url_raw = self.url_parsed.geturl()
        return to_unicode(self.url_raw)

    def __repr__(self) -> str:
        return "URL(%s)" % str(self)

    def strip_trailing_slash(self) -> "URL":
        if str(self)[-1] == "/":
            return self._derive(str(self)[:-1])
        else:
            return self

    def is_auth(self) -> bool:
        return self.username is not None

    def unauth(self) -> "URL":
        if not self.is_auth():
            return self
        return self._derive(
            ParseResult(
                self.scheme,
                "%s:%s" % (self.hostname, self.port or {"https": 443, "http": 80}[self.scheme]),
                self.path.replace("//", "/"),
                self.params,
                self.query,
                self.fragment,
            )
        )

    def canonical(self) -> "URL":
        """
        a canonical URL ... remove authentication details, make sure there
        are no double slashes, and to make sure the URL is always the same,
        run it through the urlparser, and make sure path is properly quoted
        """
        url = self.unauth()

        # Use url's parsed form (credentials already stripped), not self's.
        # Also always build a fresh URL so self is never mutated — unauth()
        # returns self when there are no credentials, and the old code then
        # overwrote url.url_raw/url_parsed which are the same object as self.
        if url.url_parsed is None:
            url.url_parsed = cast(urllib.parse.ParseResult, urlparse(str(url)))
        arr = list(url.url_parsed)
        ## quoting path and removing double slashes.  The "@" spelling is
        ## preserved rather than normalised, unless the server is declared to
        ## alias the two spellings - then collapsing them is what makes two
        ## spellings of one resource compare and hash alike.
        collapse = alias_at_path if self.alias_at else requote_path
        arr[2] = collapse(url.path.replace("//", "/"))
        ## sensible defaults
        if not arr[0]:
            arr[0] = "https"
        if arr[1] and ":" not in arr[1]:
            if arr[0] == "https":
                portpart = ":443"
            elif arr[0] == "http":
                portpart = ":80"
            else:
                portpart = ""
            arr[1] += portpart

        return self._derive(urlunparse(arr))

    def join(self, path: Any) -> "URL":
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

        if path.path and path.path[0] == "/":
            ret_path = path.path
        else:
            sep = "/"
            if self.path.endswith("/"):
                sep = ""
            ret_path = "%s%s%s" % (self.path, sep, path.path)
        return self._derive(
            ParseResult(
                self.scheme or path.scheme,
                self.netloc or path.netloc,
                ret_path,
                path.params,
                path.query,
                path.fragment,
            )
        )


def make(url: URL | str | ParseResult | SplitResult) -> URL:
    """Backward compatibility"""
    return URL.objectify(url)
