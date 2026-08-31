"""The sync HTTP library, imported once for the whole package.

Everything that needs niquests-or-requests takes it from here rather than
repeating the fallback: ``from caldav.lib.http_sync import requests``.  Note
that ``requests`` is niquests when niquests is installed - the name is the one
the API is compatible with, not necessarily the package that provides it.

The async httpx-family selection is a different set of libraries in a
different order and lives in :mod:`caldav.async_davclient`.
"""

from typing import Any

from caldav.lib.http_libraries import (
    SYNC_CANDIDATES,
    no_http_library_error,
    required_library_error,
)

USE_NIQUESTS = False
USE_REQUESTS = False

## niquests' AsyncSession has no requests equivalent, so it is None on the
## fallback.  The JMAP async client is the only thing that needs it; it goes
## through require_async_session() to get a decent error rather than a
## TypeError on None.
AsyncSession: Any = None

try:
    import niquests as requests
    from niquests.auth import AuthBase, HTTPBasicAuth
    from niquests.models import Response
    from niquests.structures import CaseInsensitiveDict

    USE_NIQUESTS = True
except ImportError:
    try:
        import requests  # type: ignore[no-redef]
        from requests.auth import (  # type: ignore[assignment]
            AuthBase,
            HTTPBasicAuth,
        )
        from requests.models import Response  # type: ignore[assignment]
        from requests.structures import (  # type: ignore[assignment]
            CaseInsensitiveDict,
        )

        USE_REQUESTS = True
    except ImportError as e:
        raise ImportError(no_http_library_error(SYNC_CANDIDATES)) from e

if USE_NIQUESTS:
    ## Deliberately its own try: an ImportError here must not fall through to
    ## the requests branch and flip USE_NIQUESTS off on an install that does
    ## have niquests.  Only the async JMAP client needs it.
    try:
        from niquests import AsyncSession  # noqa: F811
    except ImportError:
        pass


def require_async_session() -> Any:
    """Return niquests' ``AsyncSession``, or explain why there isn't one.

    Used by the async JMAP client, which is built on it and has no httpx
    equivalent to fall back to.
    """
    if AsyncSession is None:
        raise ImportError(required_library_error("niquests", "The async JMAP client"))
    return AsyncSession


__all__ = [
    "AsyncSession",
    "AuthBase",
    "CaseInsensitiveDict",
    "HTTPBasicAuth",
    "Response",
    "USE_NIQUESTS",
    "USE_REQUESTS",
    "requests",
    "require_async_session",
]
