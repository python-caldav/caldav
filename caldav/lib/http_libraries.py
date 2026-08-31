"""Which HTTP libraries caldav can use, and what to say when none is there.

caldav does the HTTP itself, but which library it does it with is up to the
user: niquests is the recommended one, with fallbacks to requests (sync) and
to the httpx family (async).  See ``docs/source/http-libraries.rst``.

This module holds only the policy - the candidate lists and the error text - so
that it can be imported without any HTTP library being installed.  The actual
sync import lives in :mod:`caldav.lib.http_sync`, and the async one in
:mod:`caldav.async_davclient`.
"""

DOCS_URL = "https://caldav.readthedocs.io/en/latest/http-libraries.html"

## In the order they are tried.  Sync has no httpx support yet, see
## https://github.com/python-caldav/caldav/issues/696
SYNC_CANDIDATES = ("niquests", "requests")
ASYNC_HTTPX_CANDIDATES = ("httpx2", "httpxyz", "httpx")
ASYNC_CANDIDATES = ("niquests", *ASYNC_HTTPX_CANDIDATES)


def no_http_library_error(candidates: tuple[str, ...], mode: str = "sync") -> str:
    """Build the "you need an HTTP library" message.

    From v3.3.0 caldav may be installed with none of them present, so the
    failure has to explain what to install rather than surfacing as a bare
    ``ModuleNotFoundError`` from somewhere in an import chain.

    :param candidates: the libraries that were tried, in order of preference.
    :param mode: ``sync`` or ``async``, named in the message so the reader
        knows which of the two lists applies.
    """
    return (
        f"caldav needs an HTTP library for {mode} communication, and none of the "
        f"supported ones is installed (tried: {', '.join(candidates)}).  Install "
        "one - `pip install niquests` is the recommended choice - or, if you are "
        "declaring caldav as a dependency of your own project, depend on "
        "`caldav[niquests]` rather than plain `caldav`.  "
        f"See {DOCS_URL} for the supported libraries and the order they are tried in."
    )


def required_library_error(library: str, what: str) -> str:
    """Build the "this particular library is required" message.

    Distinct from :func:`no_http_library_error` because the condition is
    different, and so is the remedy: some parts of caldav are built on one
    library and have nothing to fall back to, so telling the user that "none
    of the supported ones is installed" would be false - the rest of caldav
    may be running happily on another one.

    :param library: the library that is required, e.g. ``niquests``.
    :param what: what needs it, e.g. ``the async JMAP client``.
    """
    return (
        f"{what} requires {library}, which is not installed.  Unlike the CalDAV "
        f"clients it has no fallback to another HTTP library.  Install it with "
        f"`pip install {library}` or, if you are declaring caldav as a dependency "
        f"of your own project, depend on `caldav[{library}]` rather than plain "
        f"`caldav`.  See {DOCS_URL} for which parts of caldav can use which "
        "library."
    )
