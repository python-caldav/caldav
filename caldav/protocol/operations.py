"""
CalDAV protocol operations combining request building and response parsing.

This class provides a high-level interface to CalDAV operations while
remaining completely I/O-free.
"""

import base64
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from .types import (
    CalendarQueryResult,
    DAVMethod,
    DAVRequest,
    DAVResponse,
    PropfindResult,
    SyncCollectionResult,
)
from .xml_builders import (
    build_calendar_multiget_body,
    build_calendar_query_body,
    build_freebusy_query_body,
    build_mkcalendar_body,
    build_propfind_body,
    build_proppatch_body,
    build_sync_collection_body,
)
from .xml_parsers import (
    parse_calendar_multiget_response,
    parse_calendar_query_response,
    parse_propfind_response,
    parse_sync_collection_response,
)


class CalDAVProtocol:
    """
    Sans-I/O CalDAV protocol handler.

    Builds requests and parses responses without doing any I/O.
    All HTTP communication is delegated to an external I/O implementation.

    Example:
        protocol = CalDAVProtocol(base_url="https://cal.example.com/")

        # Build request
        request = protocol.propfind_request("/calendars/user/", ["displayname"])

        # Execute with your I/O (not shown)
        response = io.execute(request)

        # Parse response
        results = protocol.parse_propfind(response)
    """

    def __init__(
        self,
        base_url: str = "",
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize the protocol handler.

        Args:
            base_url: Base URL for the CalDAV server
            username: Username for Basic authentication
            password: Password for Basic authentication
        """
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.username = username
        self.password = password
        self._auth_header = self._build_auth_header(username, password)

    def _build_auth_header(
        self,
        username: Optional[str],
        password: Optional[str],
    ) -> Optional[str]:
        """Build Basic auth header if credentials provided."""
        if username and password:
            credentials = f"{username}:{password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            return f"Basic {encoded}"
        return None

    def _base_headers(self) -> Dict[str, str]:
        """Return base headers for all requests."""
        headers = {
            "Content-Type": "application/xml; charset=utf-8",
        }
        if self._auth_header:
            headers["Authorization"] = self._auth_header
        return headers

    def _resolve_url(self, path: str) -> str:
        """
        Resolve a path to a full URL.

        Args:
            path: Relative path or absolute URL

        Returns:
            Full URL
        """
        if not path:
            return self.base_url or ""

        # Already a full URL
        parsed = urlparse(path)
        if parsed.scheme:
            return path

        # Relative path - join with base
        if self.base_url:
            # Ensure base_url ends with / for proper joining
            base = self.base_url
            if not base.endswith("/"):
                base += "/"
            return urljoin(base, path.lstrip("/"))

        return path

    # =========================================================================
    # Request builders
    # =========================================================================

    def propfind_request(
        self,
        path: str,
        props: Optional[List[str]] = None,
        depth: int = 0,
    ) -> DAVRequest:
        """
        Build a PROPFIND request.

        Args:
            path: Resource path or URL
            props: Property names to retrieve (None for minimal)
            depth: Depth header value (0, 1, or "infinity")

        Returns:
            DAVRequest ready for execution
        """
        body = build_propfind_body(props)
        headers = {
            **self._base_headers(),
            "Depth": str(depth),
        }
        return DAVRequest(
            method=DAVMethod.PROPFIND,
            url=self._resolve_url(path),
            headers=headers,
            body=body,
        )

    def proppatch_request(
        self,
        path: str,
        set_props: Optional[Dict[str, str]] = None,
    ) -> DAVRequest:
        """
        Build a PROPPATCH request to set properties.

        Args:
            path: Resource path or URL
            set_props: Properties to set (name -> value)

        Returns:
            DAVRequest ready for execution
        """
        body = build_proppatch_body(set_props)
        return DAVRequest(
            method=DAVMethod.PROPPATCH,
            url=self._resolve_url(path),
            headers=self._base_headers(),
            body=body,
        )

    def calendar_query_request(
        self,
        path: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        expand: bool = False,
        event: bool = False,
        todo: bool = False,
        journal: bool = False,
    ) -> DAVRequest:
        """
        Build a calendar-query REPORT request.

        Args:
            path: Calendar collection path or URL
            start: Start of time range
            end: End of time range
            expand: Expand recurring events
            event: Include events
            todo: Include todos
            journal: Include journals

        Returns:
            DAVRequest ready for execution
        """
        body, _ = build_calendar_query_body(
            start=start,
            end=end,
            expand=expand,
            event=event,
            todo=todo,
            journal=journal,
        )
        headers = {
            **self._base_headers(),
            "Depth": "1",
        }
        return DAVRequest(
            method=DAVMethod.REPORT,
            url=self._resolve_url(path),
            headers=headers,
            body=body,
        )

    def calendar_multiget_request(
        self,
        path: str,
        hrefs: List[str],
    ) -> DAVRequest:
        """
        Build a calendar-multiget REPORT request.

        Args:
            path: Calendar collection path or URL
            hrefs: List of calendar object URLs to retrieve

        Returns:
            DAVRequest ready for execution
        """
        body = build_calendar_multiget_body(hrefs)
        headers = {
            **self._base_headers(),
            "Depth": "1",
        }
        return DAVRequest(
            method=DAVMethod.REPORT,
            url=self._resolve_url(path),
            headers=headers,
            body=body,
        )

    def sync_collection_request(
        self,
        path: str,
        sync_token: Optional[str] = None,
        props: Optional[List[str]] = None,
    ) -> DAVRequest:
        """
        Build a sync-collection REPORT request.

        Args:
            path: Calendar collection path or URL
            sync_token: Previous sync token (None for initial sync)
            props: Properties to include in response

        Returns:
            DAVRequest ready for execution
        """
        body = build_sync_collection_body(sync_token, props)
        headers = {
            **self._base_headers(),
            "Depth": "1",
        }
        return DAVRequest(
            method=DAVMethod.REPORT,
            url=self._resolve_url(path),
            headers=headers,
            body=body,
        )

    def freebusy_request(
        self,
        path: str,
        start: datetime,
        end: datetime,
    ) -> DAVRequest:
        """
        Build a free-busy-query REPORT request.

        Args:
            path: Calendar or scheduling outbox path
            start: Start of free-busy period
            end: End of free-busy period

        Returns:
            DAVRequest ready for execution
        """
        body = build_freebusy_query_body(start, end)
        headers = {
            **self._base_headers(),
            "Depth": "1",
        }
        return DAVRequest(
            method=DAVMethod.REPORT,
            url=self._resolve_url(path),
            headers=headers,
            body=body,
        )

    def mkcalendar_request(
        self,
        path: str,
        displayname: Optional[str] = None,
        description: Optional[str] = None,
        timezone: Optional[str] = None,
        supported_components: Optional[List[str]] = None,
    ) -> DAVRequest:
        """
        Build a MKCALENDAR request.

        Args:
            path: Path for new calendar
            displayname: Calendar display name
            description: Calendar description
            timezone: VTIMEZONE data
            supported_components: Supported component types

        Returns:
            DAVRequest ready for execution
        """
        body = build_mkcalendar_body(
            displayname=displayname,
            description=description,
            timezone=timezone,
            supported_components=supported_components,
        )
        return DAVRequest(
            method=DAVMethod.MKCALENDAR,
            url=self._resolve_url(path),
            headers=self._base_headers(),
            body=body,
        )

    def get_request(
        self,
        path: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> DAVRequest:
        """
        Build a GET request.

        Args:
            path: Resource path or URL
            headers: Additional headers

        Returns:
            DAVRequest ready for execution
        """
        req_headers = self._base_headers()
        req_headers.pop("Content-Type", None)  # GET doesn't need Content-Type
        if headers:
            req_headers.update(headers)

        return DAVRequest(
            method=DAVMethod.GET,
            url=self._resolve_url(path),
            headers=req_headers,
        )

    def put_request(
        self,
        path: str,
        data: bytes,
        content_type: str = "text/calendar; charset=utf-8",
        etag: Optional[str] = None,
    ) -> DAVRequest:
        """
        Build a PUT request to create/update a resource.

        Args:
            path: Resource path or URL
            data: Resource content
            content_type: Content-Type header
            etag: If-Match header for conditional update

        Returns:
            DAVRequest ready for execution
        """
        headers = self._base_headers()
        headers["Content-Type"] = content_type
        if etag:
            headers["If-Match"] = etag

        return DAVRequest(
            method=DAVMethod.PUT,
            url=self._resolve_url(path),
            headers=headers,
            body=data,
        )

    def delete_request(
        self,
        path: str,
        etag: Optional[str] = None,
    ) -> DAVRequest:
        """
        Build a DELETE request.

        Args:
            path: Resource path to delete
            etag: If-Match header for conditional delete

        Returns:
            DAVRequest ready for execution
        """
        headers = self._base_headers()
        headers.pop("Content-Type", None)  # DELETE doesn't need Content-Type
        if etag:
            headers["If-Match"] = etag

        return DAVRequest(
            method=DAVMethod.DELETE,
            url=self._resolve_url(path),
            headers=headers,
        )

    def options_request(
        self,
        path: str = "",
    ) -> DAVRequest:
        """
        Build an OPTIONS request.

        Args:
            path: Resource path or URL (empty for server root)

        Returns:
            DAVRequest ready for execution
        """
        headers = self._base_headers()
        headers.pop("Content-Type", None)

        return DAVRequest(
            method=DAVMethod.OPTIONS,
            url=self._resolve_url(path),
            headers=headers,
        )

    # =========================================================================
    # Response parsers
    # =========================================================================

    def parse_propfind(
        self,
        response: DAVResponse,
        huge_tree: bool = False,
    ) -> List[PropfindResult]:
        """
        Parse a PROPFIND response.

        Args:
            response: The DAVResponse from the server
            huge_tree: Allow parsing very large XML documents

        Returns:
            List of PropfindResult with properties for each resource
        """
        return parse_propfind_response(
            response.body,
            status_code=response.status,
            huge_tree=huge_tree,
        )

    def parse_calendar_query(
        self,
        response: DAVResponse,
        huge_tree: bool = False,
    ) -> List[CalendarQueryResult]:
        """
        Parse a calendar-query REPORT response.

        Args:
            response: The DAVResponse from the server
            huge_tree: Allow parsing very large XML documents

        Returns:
            List of CalendarQueryResult with calendar data
        """
        return parse_calendar_query_response(
            response.body,
            status_code=response.status,
            huge_tree=huge_tree,
        )

    def parse_calendar_multiget(
        self,
        response: DAVResponse,
        huge_tree: bool = False,
    ) -> List[CalendarQueryResult]:
        """
        Parse a calendar-multiget REPORT response.

        Args:
            response: The DAVResponse from the server
            huge_tree: Allow parsing very large XML documents

        Returns:
            List of CalendarQueryResult with calendar data
        """
        return parse_calendar_multiget_response(
            response.body,
            status_code=response.status,
            huge_tree=huge_tree,
        )

    def parse_sync_collection(
        self,
        response: DAVResponse,
        huge_tree: bool = False,
    ) -> SyncCollectionResult:
        """
        Parse a sync-collection REPORT response.

        Args:
            response: The DAVResponse from the server
            huge_tree: Allow parsing very large XML documents

        Returns:
            SyncCollectionResult with changed items, deleted hrefs, and sync token
        """
        return parse_sync_collection_response(
            response.body,
            status_code=response.status,
            huge_tree=huge_tree,
        )

    # =========================================================================
    # Convenience methods
    # =========================================================================

    def check_response_ok(
        self,
        response: DAVResponse,
        expected_status: Optional[List[int]] = None,
    ) -> bool:
        """
        Check if a response indicates success.

        Args:
            response: The DAVResponse to check
            expected_status: List of acceptable status codes (default: 2xx)

        Returns:
            True if response is successful
        """
        if expected_status:
            return response.status in expected_status
        return response.ok
