"""The sync HTTP library, imported once for the whole package.

Everything that needs niquests-or-requests takes it from here rather than
repeating the fallback: ``from caldav.lib.http_sync import requests``.  Note
that ``requests`` is niquests when niquests is installed - the name is the one
the API is compatible with, not necessarily the package that provides it.

The async httpx-family selection is a different set of libraries in a
different order and lives in :mod:`caldav.async_davclient`.
"""

from caldav.lib.http_libraries import (
    SYNC_CANDIDATES,
    no_http_library_error,
)

USE_NIQUESTS = False
USE_REQUESTS = False

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

__all__ = [
    "AuthBase",
    "CaseInsensitiveDict",
    "HTTPBasicAuth",
    "Response",
    "USE_NIQUESTS",
    "USE_REQUESTS",
    "requests",
]
