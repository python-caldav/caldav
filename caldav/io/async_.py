"""
Asynchronous I/O implementation using aiohttp library.
"""

from typing import Optional

import aiohttp

from caldav.protocol.types import DAVRequest, DAVResponse


class AsyncIO:
    """
    Asynchronous I/O shell using aiohttp library.

    This is a thin wrapper that executes DAVRequest objects via HTTP
    and returns DAVResponse objects.

    Example:
        async with AsyncIO() as io:
            request = protocol.propfind_request("/calendars/", ["displayname"])
            response = await io.execute(request)
            results = protocol.parse_propfind(response)
    """

    def __init__(
        self,
        session: Optional[aiohttp.ClientSession] = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ):
        """
        Initialize the async I/O handler.

        Args:
            session: Existing aiohttp ClientSession to use (creates new if None)
            timeout: Request timeout in seconds
            verify_ssl: Verify SSL certificates
        """
        self._session = session
        self._owns_session = session is None
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.verify_ssl = verify_ssl

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None:
            connector = aiohttp.TCPConnector(ssl=self.verify_ssl)
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                connector=connector,
            )
        return self._session

    async def execute(self, request: DAVRequest) -> DAVResponse:
        """
        Execute a DAVRequest and return DAVResponse.

        Args:
            request: The request to execute

        Returns:
            DAVResponse with status, headers, and body
        """
        session = await self._get_session()

        async with session.request(
            method=request.method.value,
            url=request.url,
            headers=request.headers,
            data=request.body,
        ) as response:
            body = await response.read()
            return DAVResponse(
                status=response.status,
                headers=dict(response.headers),
                body=body,
            )

    async def close(self) -> None:
        """Close the session if we created it."""
        if self._session and self._owns_session:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "AsyncIO":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        await self.close()
