"""
Synchronous I/O implementation using niquests library.
"""

from typing import Optional

try:
    import niquests as requests
except ImportError:
    import requests  # type: ignore[no-redef]

from caldav.protocol.types import DAVRequest, DAVResponse


class SyncIO:
    """
    Synchronous I/O shell using niquests library.

    This is a thin wrapper that executes DAVRequest objects via HTTP
    and returns DAVResponse objects.

    Example:
        io = SyncIO()
        request = protocol.propfind_request("/calendars/", ["displayname"])
        response = io.execute(request)
        results = protocol.parse_propfind(response)
    """

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: float = 30.0,
        verify: bool = True,
    ):
        """
        Initialize the sync I/O handler.

        Args:
            session: Existing requests Session to use (creates new if None)
            timeout: Request timeout in seconds
            verify: Verify SSL certificates
        """
        self._owns_session = session is None
        self.session = session or requests.Session()
        self.timeout = timeout
        self.verify = verify

    def execute(self, request: DAVRequest) -> DAVResponse:
        """
        Execute a DAVRequest and return DAVResponse.

        Args:
            request: The request to execute

        Returns:
            DAVResponse with status, headers, and body
        """
        response = self.session.request(
            method=request.method.value,
            url=request.url,
            headers=request.headers,
            data=request.body,
            timeout=self.timeout,
            verify=self.verify,
        )

        return DAVResponse(
            status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    def close(self) -> None:
        """Close the session if we created it."""
        if self._owns_session and self.session:
            self.session.close()

    def __enter__(self) -> "SyncIO":
        """Context manager entry."""
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit."""
        self.close()
