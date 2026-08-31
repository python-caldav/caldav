"""The optional HTTP library dependencies, and what to say when none is there.

caldav does the HTTP itself, but which library it does it with is up to the
user: niquests is the recommended one, with fallbacks to requests (sync) and
to the httpx family (async).  See ``docs/source/http-libraries.rst``.

From v3.3.0 the library may be installed with none of them present, so the
failure has to explain what to install rather than surfacing as a bare
``ModuleNotFoundError: No module named 'requests'`` from somewhere deep in an
import chain.  The message lives here so that every fallback site raises the
same one.
"""

DOCS_URL = "https://caldav.readthedocs.io/en/latest/http-libraries.html"

## In the order they are tried.  The async list is the one implemented in
## async_davclient; the sync one has no httpx support yet, see
## https://github.com/python-caldav/caldav/issues/696
SYNC_CANDIDATES = ("niquests", "requests")
ASYNC_CANDIDATES = ("niquests", "httpx2", "httpxyz", "httpx")


def no_http_library_error(candidates: tuple[str, ...], mode: str = "sync") -> str:
    """Build the "you need an HTTP library" message.

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
