"""
Abstract I/O protocol definition.

This module defines the interface that all I/O implementations must follow.
"""

from typing import Protocol, runtime_checkable

from caldav.protocol.types import DAVRequest, DAVResponse


@runtime_checkable
class SyncIOProtocol(Protocol):
    """
    Protocol defining the synchronous I/O interface.

    Implementations must provide a way to execute DAVRequest objects
    and return DAVResponse objects synchronously.
    """

    def execute(self, request: DAVRequest) -> DAVResponse:
        """
        Execute a request and return the response.

        Args:
            request: The DAVRequest to execute

        Returns:
            DAVResponse with status, headers, and body
        """
        ...

    def close(self) -> None:
        """Close any resources (e.g., HTTP session)."""
        ...


@runtime_checkable
class AsyncIOProtocol(Protocol):
    """
    Protocol defining the asynchronous I/O interface.

    Implementations must provide a way to execute DAVRequest objects
    and return DAVResponse objects asynchronously.
    """

    async def execute(self, request: DAVRequest) -> DAVResponse:
        """
        Execute a request and return the response.

        Args:
            request: The DAVRequest to execute

        Returns:
            DAVResponse with status, headers, and body
        """
        ...

    async def close(self) -> None:
        """Close any resources (e.g., HTTP session)."""
        ...
