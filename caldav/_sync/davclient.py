#!/usr/bin/env python
"""
Sync DAVClient - thin wrapper around AsyncDAVClient using anyio.

This provides backward-compatible synchronous API by wrapping the
async implementation.
"""
import sys
from functools import wraps
from typing import Mapping
from typing import Optional
from typing import Tuple
from typing import Union

import anyio
from anyio.from_thread import BlockingPortal
from anyio.from_thread import start_blocking_portal

from caldav._async.davclient import AsyncDAVClient
from caldav._async.davclient import DAVResponse
from caldav._async.davclient import HTTPBearerAuth
from caldav.lib.url import URL

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

# Re-export for backward compatibility
__all__ = ["DAVClient", "DAVResponse", "HTTPBearerAuth"]


def _run_sync(async_fn, *args, **kwargs):
    """
    Execute an async function synchronously.

    Uses anyio.run() to execute the coroutine in a new event loop.
    This is the simplest approach for running async code from sync.
    """

    async def _wrapper():
        return await async_fn(*args, **kwargs)

    return anyio.from_thread.run_sync(_wrapper) if False else anyio.run(_wrapper)


class DAVClient:
    """
    Synchronous CalDAV client - thin wrapper around AsyncDAVClient.

    This class provides the same interface as the original DAVClient
    but delegates all operations to the async implementation.
    """

    def __init__(
        self,
        url: Optional[str] = "",
        proxy: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth=None,
        auth_type: Optional[str] = None,
        timeout: Optional[float] = None,
        ssl_verify_cert: Union[bool, str] = True,
        ssl_cert: Union[str, Tuple[str, str], None] = None,
        headers: Mapping[str, str] = None,
        huge_tree: bool = False,
        features=None,
    ) -> None:
        """
        Initialize sync DAV client.

        All parameters are passed to AsyncDAVClient.
        """
        self._async = AsyncDAVClient(
            url=url,
            proxy=proxy,
            username=username,
            password=password,
            auth=auth,
            auth_type=auth_type,
            timeout=timeout,
            ssl_verify_cert=ssl_verify_cert,
            ssl_cert=ssl_cert,
            headers=headers,
            huge_tree=huge_tree,
            features=features,
        )

    # Expose commonly accessed attributes
    @property
    def url(self) -> URL:
        return self._async.url

    @url.setter
    def url(self, value):
        self._async.url = value

    @property
    def headers(self):
        return self._async.headers

    @property
    def huge_tree(self) -> bool:
        return self._async.huge_tree

    @property
    def features(self):
        return self._async.features

    @property
    def username(self):
        return self._async.username

    @property
    def password(self):
        return self._async.password

    @property
    def auth(self):
        return self._async.auth

    @property
    def timeout(self):
        return self._async.timeout

    @property
    def ssl_verify_cert(self):
        return self._async.ssl_verify_cert

    @property
    def ssl_cert(self):
        return self._async.ssl_cert

    @property
    def proxy(self):
        return self._async._proxy

    def __enter__(self) -> Self:
        """Context manager entry."""
        _run_sync(self._async.__aenter__)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Context manager exit."""
        _run_sync(self._async.__aexit__, exc_type, exc_value, traceback)

    def close(self) -> None:
        """Close the client connection."""
        _run_sync(self._async.close)

    def request(
        self,
        url: str,
        method: str = "GET",
        body: str = "",
        headers: Mapping[str, str] = None,
    ) -> DAVResponse:
        """Send an HTTP request."""
        return _run_sync(self._async.request, url, method, body, headers)

    def propfind(
        self, url: Optional[str] = None, props: str = "", depth: int = 0
    ) -> DAVResponse:
        """Send a PROPFIND request."""
        return _run_sync(self._async.propfind, url, props, depth)

    def proppatch(self, url: str, body: str, dummy: None = None) -> DAVResponse:
        """Send a PROPPATCH request."""
        return _run_sync(self._async.proppatch, url, body, dummy)

    def report(self, url: str, query: str = "", depth: int = 0) -> DAVResponse:
        """Send a REPORT request."""
        return _run_sync(self._async.report, url, query, depth)

    def mkcol(self, url: str, body: str, dummy: None = None) -> DAVResponse:
        """Send a MKCOL request."""
        return _run_sync(self._async.mkcol, url, body, dummy)

    def mkcalendar(self, url: str, body: str = "", dummy: None = None) -> DAVResponse:
        """Send a MKCALENDAR request."""
        return _run_sync(self._async.mkcalendar, url, body, dummy)

    def put(
        self, url: str, body: str, headers: Mapping[str, str] = None
    ) -> DAVResponse:
        """Send a PUT request."""
        return _run_sync(self._async.put, url, body, headers)

    def post(
        self, url: str, body: str, headers: Mapping[str, str] = None
    ) -> DAVResponse:
        """Send a POST request."""
        return _run_sync(self._async.post, url, body, headers)

    def delete(self, url: str) -> DAVResponse:
        """Send a DELETE request."""
        return _run_sync(self._async.delete, url)

    def options(self, url: str) -> DAVResponse:
        """Send an OPTIONS request."""
        return _run_sync(self._async.options, url)

    def check_dav_support(self) -> Optional[str]:
        """Check if server supports DAV."""
        return _run_sync(self._async.check_dav_support)

    def check_cdav_support(self) -> bool:
        """Check if server supports CalDAV."""
        return _run_sync(self._async.check_cdav_support)

    def check_scheduling_support(self) -> bool:
        """Check if server supports CalDAV scheduling."""
        return _run_sync(self._async.check_scheduling_support)

    def principal(self, *args, **kwargs):
        """Get the principal for this client."""
        from caldav._sync.collection import Principal

        # Note: principal() in async returns an async principal
        # We need to wrap it in a sync principal
        if not hasattr(self, "_principal") or self._principal is None:
            self._principal = Principal(client=self, *args, **kwargs)
        return self._principal

    def calendar(self, **kwargs):
        """Get a calendar object by URL."""
        from caldav._sync.collection import Calendar

        return Calendar(client=self, **kwargs)

    # For backward compatibility with tests that check for session
    @property
    def session(self):
        """Backward compatibility - return the httpx client."""
        return self._async._client
