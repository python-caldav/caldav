"""
High-level client using Sans-I/O protocol layer.

This module provides SyncProtocolClient and AsyncProtocolClient classes
that use the Sans-I/O protocol layer for all operations. These are
alternative implementations that demonstrate the protocol layer's
capabilities and can be used by advanced users who want more control.

For most users, the standard DAVClient and AsyncDAVClient are recommended.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union

from caldav.io import AsyncIO, SyncIO
from caldav.protocol import (
    CalDAVProtocol,
    CalendarQueryResult,
    DAVResponse,
    PropfindResult,
    SyncCollectionResult,
)


class SyncProtocolClient:
    """
    Synchronous CalDAV client using Sans-I/O protocol layer.

    This is a clean implementation that separates protocol logic from I/O,
    making it easier to test and understand.

    Example:
        client = SyncProtocolClient(
            base_url="https://cal.example.com",
            username="user",
            password="pass",
        )
        with client:
            calendars = client.propfind("/calendars/", ["displayname"], depth=1)
            for cal in calendars:
                print(f"{cal.href}: {cal.properties}")
    """

    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ):
        """
        Initialize the client.

        Args:
            base_url: CalDAV server URL
            username: Username for authentication
            password: Password for authentication
            timeout: Request timeout in seconds
            verify_ssl: Verify SSL certificates
        """
        self.protocol = CalDAVProtocol(
            base_url=base_url,
            username=username,
            password=password,
        )
        self.io = SyncIO(timeout=timeout, verify=verify_ssl)

    def close(self) -> None:
        """Close the HTTP session."""
        self.io.close()

    def __enter__(self) -> "SyncProtocolClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _execute(self, request) -> DAVResponse:
        """Execute a request and return the response."""
        return self.io.execute(request)

    # High-level operations

    def propfind(
        self,
        path: str,
        props: Optional[List[str]] = None,
        depth: int = 0,
    ) -> List[PropfindResult]:
        """
        Execute PROPFIND to get properties of resources.

        Args:
            path: Resource path
            props: Property names to retrieve
            depth: Depth (0=resource only, 1=immediate children)

        Returns:
            List of PropfindResult with properties
        """
        request = self.protocol.propfind_request(path, props, depth)
        response = self._execute(request)
        return self.protocol.parse_propfind(response)

    def calendar_query(
        self,
        path: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        event: bool = False,
        todo: bool = False,
        journal: bool = False,
        expand: bool = False,
    ) -> List[CalendarQueryResult]:
        """
        Execute calendar-query REPORT to search for calendar objects.

        Args:
            path: Calendar collection path
            start: Start of time range
            end: End of time range
            event: Include events
            todo: Include todos
            journal: Include journals
            expand: Expand recurring events

        Returns:
            List of CalendarQueryResult with calendar data
        """
        request = self.protocol.calendar_query_request(
            path,
            start=start,
            end=end,
            event=event,
            todo=todo,
            journal=journal,
            expand=expand,
        )
        response = self._execute(request)
        return self.protocol.parse_calendar_query(response)

    def calendar_multiget(
        self,
        path: str,
        hrefs: List[str],
    ) -> List[CalendarQueryResult]:
        """
        Execute calendar-multiget REPORT to retrieve specific objects.

        Args:
            path: Calendar collection path
            hrefs: List of object URLs to retrieve

        Returns:
            List of CalendarQueryResult with calendar data
        """
        request = self.protocol.calendar_multiget_request(path, hrefs)
        response = self._execute(request)
        return self.protocol.parse_calendar_multiget(response)

    def sync_collection(
        self,
        path: str,
        sync_token: Optional[str] = None,
        props: Optional[List[str]] = None,
    ) -> SyncCollectionResult:
        """
        Execute sync-collection REPORT for efficient synchronization.

        Args:
            path: Calendar collection path
            sync_token: Previous sync token (None for initial sync)
            props: Properties to include

        Returns:
            SyncCollectionResult with changes and new sync token
        """
        request = self.protocol.sync_collection_request(path, sync_token, props)
        response = self._execute(request)
        return self.protocol.parse_sync_collection(response)

    def get(self, path: str) -> DAVResponse:
        """
        Execute GET request.

        Args:
            path: Resource path

        Returns:
            DAVResponse with the resource content
        """
        request = self.protocol.get_request(path)
        return self._execute(request)

    def put(
        self,
        path: str,
        data: Union[str, bytes],
        content_type: str = "text/calendar; charset=utf-8",
        etag: Optional[str] = None,
    ) -> DAVResponse:
        """
        Execute PUT request to create/update a resource.

        Args:
            path: Resource path
            data: Resource content
            content_type: Content-Type header
            etag: If-Match header for conditional update

        Returns:
            DAVResponse
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        request = self.protocol.put_request(path, data, content_type, etag)
        return self._execute(request)

    def delete(self, path: str, etag: Optional[str] = None) -> DAVResponse:
        """
        Execute DELETE request.

        Args:
            path: Resource path
            etag: If-Match header for conditional delete

        Returns:
            DAVResponse
        """
        request = self.protocol.delete_request(path, etag)
        return self._execute(request)

    def mkcalendar(
        self,
        path: str,
        displayname: Optional[str] = None,
        description: Optional[str] = None,
    ) -> DAVResponse:
        """
        Execute MKCALENDAR request to create a calendar.

        Args:
            path: Path for the new calendar
            displayname: Calendar display name
            description: Calendar description

        Returns:
            DAVResponse
        """
        request = self.protocol.mkcalendar_request(
            path,
            displayname=displayname,
            description=description,
        )
        return self._execute(request)

    def options(self, path: str = "") -> DAVResponse:
        """
        Execute OPTIONS request.

        Args:
            path: Resource path

        Returns:
            DAVResponse with allowed methods in headers
        """
        request = self.protocol.options_request(path)
        return self._execute(request)


class AsyncProtocolClient:
    """
    Asynchronous CalDAV client using Sans-I/O protocol layer.

    This is the async version of SyncProtocolClient.

    Example:
        async with AsyncProtocolClient(
            base_url="https://cal.example.com",
            username="user",
            password="pass",
        ) as client:
            calendars = await client.propfind("/calendars/", ["displayname"], depth=1)
            for cal in calendars:
                print(f"{cal.href}: {cal.properties}")
    """

    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ):
        """
        Initialize the client.

        Args:
            base_url: CalDAV server URL
            username: Username for authentication
            password: Password for authentication
            timeout: Request timeout in seconds
            verify_ssl: Verify SSL certificates
        """
        self.protocol = CalDAVProtocol(
            base_url=base_url,
            username=username,
            password=password,
        )
        self.io = AsyncIO(timeout=timeout, verify_ssl=verify_ssl)

    async def close(self) -> None:
        """Close the HTTP session."""
        await self.io.close()

    async def __aenter__(self) -> "AsyncProtocolClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def _execute(self, request) -> DAVResponse:
        """Execute a request and return the response."""
        return await self.io.execute(request)

    # High-level operations (async versions)

    async def propfind(
        self,
        path: str,
        props: Optional[List[str]] = None,
        depth: int = 0,
    ) -> List[PropfindResult]:
        """Execute PROPFIND to get properties of resources."""
        request = self.protocol.propfind_request(path, props, depth)
        response = await self._execute(request)
        return self.protocol.parse_propfind(response)

    async def calendar_query(
        self,
        path: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        event: bool = False,
        todo: bool = False,
        journal: bool = False,
        expand: bool = False,
    ) -> List[CalendarQueryResult]:
        """Execute calendar-query REPORT to search for calendar objects."""
        request = self.protocol.calendar_query_request(
            path,
            start=start,
            end=end,
            event=event,
            todo=todo,
            journal=journal,
            expand=expand,
        )
        response = await self._execute(request)
        return self.protocol.parse_calendar_query(response)

    async def calendar_multiget(
        self,
        path: str,
        hrefs: List[str],
    ) -> List[CalendarQueryResult]:
        """Execute calendar-multiget REPORT to retrieve specific objects."""
        request = self.protocol.calendar_multiget_request(path, hrefs)
        response = await self._execute(request)
        return self.protocol.parse_calendar_multiget(response)

    async def sync_collection(
        self,
        path: str,
        sync_token: Optional[str] = None,
        props: Optional[List[str]] = None,
    ) -> SyncCollectionResult:
        """Execute sync-collection REPORT for efficient synchronization."""
        request = self.protocol.sync_collection_request(path, sync_token, props)
        response = await self._execute(request)
        return self.protocol.parse_sync_collection(response)

    async def get(self, path: str) -> DAVResponse:
        """Execute GET request."""
        request = self.protocol.get_request(path)
        return await self._execute(request)

    async def put(
        self,
        path: str,
        data: Union[str, bytes],
        content_type: str = "text/calendar; charset=utf-8",
        etag: Optional[str] = None,
    ) -> DAVResponse:
        """Execute PUT request to create/update a resource."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        request = self.protocol.put_request(path, data, content_type, etag)
        return await self._execute(request)

    async def delete(self, path: str, etag: Optional[str] = None) -> DAVResponse:
        """Execute DELETE request."""
        request = self.protocol.delete_request(path, etag)
        return await self._execute(request)

    async def mkcalendar(
        self,
        path: str,
        displayname: Optional[str] = None,
        description: Optional[str] = None,
    ) -> DAVResponse:
        """Execute MKCALENDAR request to create a calendar."""
        request = self.protocol.mkcalendar_request(
            path,
            displayname=displayname,
            description=description,
        )
        return await self._execute(request)

    async def options(self, path: str = "") -> DAVResponse:
        """Execute OPTIONS request."""
        request = self.protocol.options_request(path)
        return await self._execute(request)
