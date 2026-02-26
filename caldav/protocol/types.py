"""
Core protocol types for Sans-I/O CalDAV implementation.

These dataclasses represent HTTP requests and responses at the protocol level,
independent of any I/O implementation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DAVMethod(Enum):
    """WebDAV/CalDAV HTTP methods."""

    GET = "GET"
    PUT = "PUT"
    DELETE = "DELETE"
    PROPFIND = "PROPFIND"
    PROPPATCH = "PROPPATCH"
    REPORT = "REPORT"
    MKCALENDAR = "MKCALENDAR"
    MKCOL = "MKCOL"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"
    MOVE = "MOVE"
    COPY = "COPY"
    POST = "POST"


@dataclass(frozen=True)
class DAVRequest:
    """
    Represents an HTTP request to be made.

    This is a pure data structure with no I/O. It describes what request
    should be made, but does not make it.

    Attributes:
        method: HTTP method (GET, PUT, PROPFIND, etc.)
        url: Full URL for the request
        headers: HTTP headers as dict
        body: Request body as bytes (optional)
    """

    method: DAVMethod
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None

    def with_header(self, name: str, value: str) -> "DAVRequest":
        """Return new request with additional header."""
        new_headers = {**self.headers, name: value}
        return DAVRequest(
            method=self.method,
            url=self.url,
            headers=new_headers,
            body=self.body,
        )

    def with_body(self, body: bytes) -> "DAVRequest":
        """Return new request with body."""
        return DAVRequest(
            method=self.method,
            url=self.url,
            headers=self.headers,
            body=body,
        )


@dataclass(frozen=True)
class DAVResponse:
    """
    Represents an HTTP response received.

    This is a pure data structure with no I/O. It contains the response
    data but does not fetch it.

    Attributes:
        status: HTTP status code
        headers: HTTP headers as dict
        body: Response body as bytes
    """

    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def ok(self) -> bool:
        """True if status indicates success (2xx)."""
        return 200 <= self.status < 300

    @property
    def is_multistatus(self) -> bool:
        """True if this is a 207 Multi-Status response."""
        return self.status == 207

    @property
    def reason(self) -> str:
        """Return a reason phrase for the status code."""
        reasons = {
            200: "OK",
            201: "Created",
            204: "No Content",
            207: "Multi-Status",
            301: "Moved Permanently",
            302: "Found",
            304: "Not Modified",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            409: "Conflict",
            412: "Precondition Failed",
            415: "Unsupported Media Type",
            500: "Internal Server Error",
            501: "Not Implemented",
            502: "Bad Gateway",
            503: "Service Unavailable",
        }
        return reasons.get(self.status, "Unknown")


@dataclass
class PropfindResult:
    """
    Parsed result of a PROPFIND request for a single resource.

    Attributes:
        href: URL/path of the resource
        properties: Dict of property name -> value
        status: HTTP status for this resource (default 200)
    """

    href: str
    properties: dict[str, Any] = field(default_factory=dict)
    status: int = 200


@dataclass
class CalendarQueryResult:
    """
    Parsed result of a calendar-query REPORT for a single object.

    Attributes:
        href: URL/path of the calendar object
        etag: ETag of the object (for conditional updates)
        calendar_data: iCalendar data as string
        status: HTTP status for this resource (default 200)
    """

    href: str
    etag: str | None = None
    calendar_data: str | None = None
    status: int = 200


@dataclass
class MultiGetResult:
    """
    Parsed result of a calendar-multiget REPORT for a single object.

    Same structure as CalendarQueryResult but semantically different operation.
    """

    href: str
    etag: str | None = None
    calendar_data: str | None = None
    status: int = 200


@dataclass
class SyncCollectionResult:
    """
    Parsed result of a sync-collection REPORT.

    Attributes:
        changed: List of changed/new resources
        deleted: List of deleted resource hrefs
        sync_token: New sync token for next sync
    """

    changed: list[CalendarQueryResult] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    sync_token: str | None = None


@dataclass
class MultistatusResponse:
    """
    Parsed multi-status response containing multiple results.

    This is the raw parsed form of a 207 Multi-Status response.

    Attributes:
        responses: List of individual response results
        sync_token: Sync token if present (for sync-collection)
    """

    responses: list[PropfindResult] = field(default_factory=list)
    sync_token: str | None = None


@dataclass
class PrincipalInfo:
    """
    Information about a CalDAV principal.

    Attributes:
        url: Principal URL
        calendar_home_set: URL of calendar home
        displayname: Display name of principal
        calendar_user_address_set: Set of calendar user addresses (email-like)
    """

    url: str
    calendar_home_set: str | None = None
    displayname: str | None = None
    calendar_user_address_set: list[str] = field(default_factory=list)
