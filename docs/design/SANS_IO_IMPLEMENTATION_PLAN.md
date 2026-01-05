# Sans-I/O Implementation Plan

This document provides a detailed, actionable plan for implementing the Sans-I/O
architecture in the caldav library.

## Starting Point: Playground Branch

**Recommendation: Start from `playground/new_async_api_design` branch.**

### Rationale

The playground branch already contains work that aligns with Sans-I/O:

| Already Done (Playground) | Sans-I/O Step |
|---------------------------|---------------|
| `response.py` with `BaseDAVResponse` | Step 2: Response parsing extraction |
| `CalDAVSearcher.build_search_xml_query()` | Step 1: XML building extraction |
| `config.py` unified configuration | Infrastructure |
| Async implementation with shared logic | I/O layer foundation |

Starting from master would mean:
- Losing ~5000 lines of async implementation work
- Redoing protocol extraction already started
- No benefit to Sans-I/O goals

The playground branch provides:
- Working async/sync parity to build upon
- Already-extracted shared logic as examples
- Test infrastructure for both sync and async
- Foundation for I/O shell abstraction

## Implementation Phases

### Phase 1: Foundation (Protocol Types and Infrastructure)

**Goal:** Create the protocol package structure and core types.

#### Step 1.1: Create Protocol Package Structure

```bash
mkdir -p caldav/protocol
touch caldav/protocol/__init__.py
touch caldav/protocol/types.py
touch caldav/protocol/xml_builders.py
touch caldav/protocol/xml_parsers.py
touch caldav/protocol/operations.py
```

#### Step 1.2: Define Core Protocol Types

```python
# caldav/protocol/types.py
"""
Core protocol types for Sans-I/O CalDAV implementation.

These dataclasses represent HTTP requests and responses at the protocol level,
independent of any I/O implementation.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum, auto


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


@dataclass(frozen=True)
class DAVRequest:
    """
    Represents an HTTP request to be made.

    This is a pure data structure with no I/O. It describes what request
    should be made, but does not make it.
    """
    method: DAVMethod
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[bytes] = None

    def with_header(self, name: str, value: str) -> "DAVRequest":
        """Return new request with additional header."""
        new_headers = {**self.headers, name: value}
        return DAVRequest(
            method=self.method,
            path=self.path,
            headers=new_headers,
            body=self.body,
        )

    def with_body(self, body: bytes) -> "DAVRequest":
        """Return new request with body."""
        return DAVRequest(
            method=self.method,
            path=self.path,
            headers=self.headers,
            body=body,
        )


@dataclass(frozen=True)
class DAVResponse:
    """
    Represents an HTTP response received.

    This is a pure data structure with no I/O. It contains the response
    data but does not fetch it.
    """
    status: int
    headers: Dict[str, str]
    body: bytes

    @property
    def ok(self) -> bool:
        """True if status indicates success (2xx)."""
        return 200 <= self.status < 300

    @property
    def is_multistatus(self) -> bool:
        """True if this is a 207 Multi-Status response."""
        return self.status == 207


@dataclass
class PropfindResult:
    """Parsed result of a PROPFIND request."""
    href: str
    properties: Dict[str, Any]
    status: int = 200


@dataclass
class CalendarQueryResult:
    """Parsed result of a calendar-query REPORT."""
    href: str
    etag: Optional[str]
    calendar_data: Optional[str]  # iCalendar data
    status: int = 200


@dataclass
class MultistatusResponse:
    """Parsed multi-status response containing multiple results."""
    responses: List[PropfindResult]
    sync_token: Optional[str] = None
```

#### Step 1.3: Create Protocol Module Exports

```python
# caldav/protocol/__init__.py
"""
Sans-I/O CalDAV protocol implementation.

This module provides protocol-level operations without any I/O.
It builds requests and parses responses as pure data transformations.

Example usage:

    from caldav.protocol import CalDAVProtocol, DAVRequest, DAVResponse

    protocol = CalDAVProtocol()

    # Build a request (no I/O)
    request = protocol.propfind_request(
        path="/calendars/user/",
        props=["displayname", "resourcetype"],
        depth=1
    )

    # Execute via your preferred I/O (sync, async, or mock)
    response = your_http_client.execute(request)

    # Parse response (no I/O)
    result = protocol.parse_propfind_response(response)
"""
from .types import (
    DAVMethod,
    DAVRequest,
    DAVResponse,
    PropfindResult,
    CalendarQueryResult,
    MultistatusResponse,
)
from .xml_builders import (
    build_propfind_body,
    build_proppatch_body,
    build_calendar_query_body,
    build_calendar_multiget_body,
    build_sync_collection_body,
    build_freebusy_query_body,
)
from .xml_parsers import (
    parse_multistatus,
    parse_propfind_response,
    parse_calendar_query_response,
    parse_sync_collection_response,
)
from .operations import CalDAVProtocol

__all__ = [
    # Types
    "DAVMethod",
    "DAVRequest",
    "DAVResponse",
    "PropfindResult",
    "CalendarQueryResult",
    "MultistatusResponse",
    # Builders
    "build_propfind_body",
    "build_proppatch_body",
    "build_calendar_query_body",
    "build_calendar_multiget_body",
    "build_sync_collection_body",
    "build_freebusy_query_body",
    # Parsers
    "parse_multistatus",
    "parse_propfind_response",
    "parse_calendar_query_response",
    "parse_sync_collection_response",
    # Protocol
    "CalDAVProtocol",
]
```

### Phase 2: XML Builders Extraction

**Goal:** Extract all XML construction into pure functions.

#### Step 2.1: Extract from CalDAVSearcher

The `CalDAVSearcher.build_search_xml_query()` method already builds XML without I/O.
Extract and generalize:

```python
# caldav/protocol/xml_builders.py
"""
Pure functions for building CalDAV XML request bodies.

All functions in this module are pure - they take data in and return XML out,
with no side effects or I/O.
"""
from typing import Optional, List, Tuple, Any
from datetime import datetime
from lxml import etree

from caldav.elements import cdav, dav
from caldav.elements.base import BaseElement
from caldav.lib.namespace import nsmap


def build_propfind_body(
    props: List[str],
    include_calendar_data: bool = False,
) -> bytes:
    """
    Build PROPFIND request body XML.

    Args:
        props: List of property names to retrieve
        include_calendar_data: Whether to include calendar-data in response

    Returns:
        UTF-8 encoded XML bytes
    """
    prop_elements = []
    for prop_name in props:
        # Map property names to elements
        prop_element = _prop_name_to_element(prop_name)
        if prop_element is not None:
            prop_elements.append(prop_element)

    if include_calendar_data:
        prop_elements.append(cdav.CalendarData())

    propfind = dav.PropFind() + dav.Prop(*prop_elements)
    return etree.tostring(propfind.xmlelement(), encoding="utf-8", xml_declaration=True)


def build_calendar_query_body(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    expand: bool = False,
    comp_filter: str = "VCALENDAR",
    event: bool = False,
    todo: bool = False,
    journal: bool = False,
    include_data: bool = True,
) -> bytes:
    """
    Build calendar-query REPORT request body.

    This is the core CalDAV search operation for retrieving calendar objects
    matching specified criteria.

    Args:
        start: Start of time range filter
        end: End of time range filter
        expand: Whether to expand recurring events
        comp_filter: Component type filter (VCALENDAR, VEVENT, VTODO, etc.)
        event: Include VEVENT components
        todo: Include VTODO components
        journal: Include VJOURNAL components
        include_data: Include calendar-data in response

    Returns:
        UTF-8 encoded XML bytes
    """
    # Build the query using existing CalDAVSearcher logic
    # (refactored from search.py)
    ...


def build_calendar_multiget_body(
    hrefs: List[str],
    include_data: bool = True,
) -> bytes:
    """
    Build calendar-multiget REPORT request body.

    Used to retrieve multiple calendar objects by their URLs in a single request.

    Args:
        hrefs: List of calendar object URLs to retrieve
        include_data: Include calendar-data in response

    Returns:
        UTF-8 encoded XML bytes
    """
    elements = [dav.Prop(cdav.CalendarData())] if include_data else []
    for href in hrefs:
        elements.append(dav.Href(href))

    multiget = cdav.CalendarMultiGet(*elements)
    return etree.tostring(multiget.xmlelement(), encoding="utf-8", xml_declaration=True)


def build_sync_collection_body(
    sync_token: Optional[str] = None,
    props: Optional[List[str]] = None,
) -> bytes:
    """
    Build sync-collection REPORT request body.

    Used for efficient synchronization - only returns changed items since
    the given sync token.

    Args:
        sync_token: Previous sync token (None for initial sync)
        props: Properties to include in response

    Returns:
        UTF-8 encoded XML bytes
    """
    ...


def build_freebusy_query_body(
    start: datetime,
    end: datetime,
) -> bytes:
    """
    Build free-busy-query REPORT request body.

    Args:
        start: Start of free-busy period
        end: End of free-busy period

    Returns:
        UTF-8 encoded XML bytes
    """
    ...


def build_proppatch_body(
    set_props: Optional[dict] = None,
    remove_props: Optional[List[str]] = None,
) -> bytes:
    """
    Build PROPPATCH request body for setting/removing properties.

    Args:
        set_props: Properties to set (name -> value)
        remove_props: Property names to remove

    Returns:
        UTF-8 encoded XML bytes
    """
    ...


def build_mkcalendar_body(
    displayname: Optional[str] = None,
    description: Optional[str] = None,
    timezone: Optional[str] = None,
    supported_components: Optional[List[str]] = None,
) -> bytes:
    """
    Build MKCALENDAR request body.

    Args:
        displayname: Calendar display name
        description: Calendar description
        timezone: VTIMEZONE component data
        supported_components: List of supported component types

    Returns:
        UTF-8 encoded XML bytes
    """
    ...


# Helper functions

def _prop_name_to_element(name: str) -> Optional[BaseElement]:
    """Convert property name string to element object."""
    prop_map = {
        "displayname": dav.DisplayName,
        "resourcetype": dav.ResourceType,
        "getetag": dav.GetEtag,
        "getcontenttype": dav.GetContentType,
        "getlastmodified": dav.GetLastModified,
        "calendar-data": cdav.CalendarData,
        "calendar-home-set": cdav.CalendarHomeSet,
        "supported-calendar-component-set": cdav.SupportedCalendarComponentSet,
        # ... more mappings
    }
    element_class = prop_map.get(name.lower())
    return element_class() if element_class else None
```

#### Step 2.2: Migrate CalDAVSearcher to Use Builders

```python
# caldav/search.py (modified)
from caldav.protocol.xml_builders import build_calendar_query_body

@dataclass
class CalDAVSearcher(Searcher):
    def build_search_xml_query(self) -> bytes:
        """Build the XML query for server-side search."""
        # Delegate to protocol layer
        return build_calendar_query_body(
            start=self.start,
            end=self.end,
            expand=self.expand,
            event=self.event,
            todo=self.todo,
            journal=self.journal,
            # ... other parameters
        )
```

### Phase 3: XML Parsers Extraction

**Goal:** Extract all XML parsing into pure functions.

#### Step 3.1: Refactor BaseDAVResponse Methods

The `BaseDAVResponse` class already has parsing logic. Extract to pure functions:

```python
# caldav/protocol/xml_parsers.py
"""
Pure functions for parsing CalDAV XML responses.

All functions in this module are pure - they take XML bytes in and return
structured data out, with no side effects or I/O.
"""
from typing import List, Optional, Dict, Any, Tuple
from lxml import etree
from lxml.etree import _Element

from caldav.elements import dav, cdav
from caldav.lib import error
from caldav.lib.url import URL
from .types import (
    PropfindResult,
    CalendarQueryResult,
    MultistatusResponse,
    DAVResponse,
)


def parse_multistatus(body: bytes, huge_tree: bool = False) -> MultistatusResponse:
    """
    Parse a 207 Multi-Status response body.

    Args:
        body: Raw XML response bytes
        huge_tree: Allow parsing very large XML documents

    Returns:
        Structured MultistatusResponse with parsed results

    Raises:
        XMLSyntaxError: If body is not valid XML
        ResponseError: If response indicates an error
    """
    parser = etree.XMLParser(huge_tree=huge_tree)
    tree = etree.fromstring(body, parser)

    responses = []
    sync_token = None

    for response_elem in _iter_responses(tree):
        href, propstats, status = _parse_response_element(response_elem)
        properties = _extract_properties(propstats)
        responses.append(PropfindResult(
            href=href,
            properties=properties,
            status=_status_to_code(status) if status else 200,
        ))

    # Extract sync-token if present
    sync_token_elem = tree.find(f".//{{{dav.SyncToken.tag}}}")
    if sync_token_elem is not None and sync_token_elem.text:
        sync_token = sync_token_elem.text

    return MultistatusResponse(responses=responses, sync_token=sync_token)


def parse_propfind_response(response: DAVResponse) -> List[PropfindResult]:
    """
    Parse a PROPFIND response.

    Args:
        response: The DAVResponse from the server

    Returns:
        List of PropfindResult with properties for each resource
    """
    if response.status == 404:
        return []

    if response.status not in (200, 207):
        raise error.ResponseError(f"PROPFIND failed with status {response.status}")

    result = parse_multistatus(response.body)
    return result.responses


def parse_calendar_query_response(
    response: DAVResponse
) -> List[CalendarQueryResult]:
    """
    Parse a calendar-query REPORT response.

    Args:
        response: The DAVResponse from the server

    Returns:
        List of CalendarQueryResult with calendar data
    """
    if response.status not in (200, 207):
        raise error.ResponseError(f"REPORT failed with status {response.status}")

    parser = etree.XMLParser()
    tree = etree.fromstring(response.body, parser)

    results = []
    for response_elem in _iter_responses(tree):
        href, propstats, status = _parse_response_element(response_elem)

        calendar_data = None
        etag = None

        for propstat in propstats:
            for prop in propstat:
                if prop.tag == cdav.CalendarData.tag:
                    calendar_data = prop.text
                elif prop.tag == dav.GetEtag.tag:
                    etag = prop.text

        results.append(CalendarQueryResult(
            href=href,
            etag=etag,
            calendar_data=calendar_data,
            status=_status_to_code(status) if status else 200,
        ))

    return results


def parse_sync_collection_response(
    response: DAVResponse
) -> Tuple[List[CalendarQueryResult], Optional[str]]:
    """
    Parse a sync-collection REPORT response.

    Args:
        response: The DAVResponse from the server

    Returns:
        Tuple of (results list, new sync token)
    """
    result = parse_multistatus(response.body)

    calendar_results = []
    for r in result.responses:
        calendar_results.append(CalendarQueryResult(
            href=r.href,
            etag=r.properties.get("getetag"),
            calendar_data=r.properties.get("calendar-data"),
            status=r.status,
        ))

    return calendar_results, result.sync_token


# Helper functions (extracted from BaseDAVResponse)

def _iter_responses(tree: _Element):
    """Iterate over response elements in a multistatus."""
    if tree.tag == "xml" and len(tree) > 0 and tree[0].tag == dav.MultiStatus.tag:
        yield from tree[0]
    elif tree.tag == dav.MultiStatus.tag:
        yield from tree
    else:
        yield tree


def _parse_response_element(
    response: _Element
) -> Tuple[str, List[_Element], Optional[str]]:
    """
    Parse a single response element.

    Returns:
        Tuple of (href, propstat elements, status string)
    """
    status = None
    href = None
    propstats = []

    for elem in response:
        if elem.tag == dav.Status.tag:
            status = elem.text
        elif elem.tag == dav.Href.tag:
            href = elem.text
        elif elem.tag == dav.PropStat.tag:
            propstats.append(elem)

    return href or "", propstats, status


def _extract_properties(propstats: List[_Element]) -> Dict[str, Any]:
    """Extract properties from propstat elements into a dict."""
    properties = {}
    for propstat in propstats:
        prop_elem = propstat.find(f".//{dav.Prop.tag}")
        if prop_elem is not None:
            for prop in prop_elem:
                # Extract tag name without namespace
                name = prop.tag.split("}")[-1] if "}" in prop.tag else prop.tag
                properties[name] = prop.text or _element_to_value(prop)
    return properties


def _element_to_value(elem: _Element) -> Any:
    """Convert an element to a Python value."""
    if len(elem) == 0:
        return elem.text
    # For complex elements, return element for further processing
    return elem


def _status_to_code(status: str) -> int:
    """Extract status code from status string like 'HTTP/1.1 200 OK'."""
    if not status:
        return 200
    parts = status.split()
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            pass
    return 200
```

### Phase 4: Protocol Operations Class

**Goal:** Create the main protocol class that combines builders and parsers.

```python
# caldav/protocol/operations.py
"""
CalDAV protocol operations combining request building and response parsing.

This class provides a high-level interface to CalDAV operations while
remaining completely I/O-free.
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from urllib.parse import urljoin
import base64

from .types import DAVRequest, DAVResponse, DAVMethod, PropfindResult, CalendarQueryResult
from .xml_builders import (
    build_propfind_body,
    build_calendar_query_body,
    build_calendar_multiget_body,
    build_sync_collection_body,
    build_proppatch_body,
    build_mkcalendar_body,
)
from .xml_parsers import (
    parse_propfind_response,
    parse_calendar_query_response,
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
        self.base_url = base_url.rstrip("/")
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

    def _resolve_path(self, path: str) -> str:
        """Resolve a path relative to base_url."""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return urljoin(self.base_url + "/", path.lstrip("/"))

    # Request builders

    def propfind_request(
        self,
        path: str,
        props: List[str],
        depth: int = 0,
    ) -> DAVRequest:
        """
        Build a PROPFIND request.

        Args:
            path: Resource path
            props: Property names to retrieve
            depth: Depth header value (0, 1, or infinity)

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
            path=self._resolve_path(path),
            headers=headers,
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
            path: Calendar collection path
            start: Start of time range
            end: End of time range
            expand: Expand recurring events
            event: Include events
            todo: Include todos
            journal: Include journals

        Returns:
            DAVRequest ready for execution
        """
        body = build_calendar_query_body(
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
            path=self._resolve_path(path),
            headers=headers,
            body=body,
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
            path: Resource path
            data: Resource content
            content_type: Content-Type header
            etag: If-Match header for conditional update

        Returns:
            DAVRequest ready for execution
        """
        headers = {
            **self._base_headers(),
            "Content-Type": content_type,
        }
        if etag:
            headers["If-Match"] = etag

        return DAVRequest(
            method=DAVMethod.PUT,
            path=self._resolve_path(path),
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
        if etag:
            headers["If-Match"] = etag

        return DAVRequest(
            method=DAVMethod.DELETE,
            path=self._resolve_path(path),
            headers=headers,
        )

    def mkcalendar_request(
        self,
        path: str,
        displayname: Optional[str] = None,
        description: Optional[str] = None,
    ) -> DAVRequest:
        """
        Build a MKCALENDAR request.

        Args:
            path: Path for new calendar
            displayname: Calendar display name
            description: Calendar description

        Returns:
            DAVRequest ready for execution
        """
        body = build_mkcalendar_body(
            displayname=displayname,
            description=description,
        )
        return DAVRequest(
            method=DAVMethod.MKCALENDAR,
            path=self._resolve_path(path),
            headers=self._base_headers(),
            body=body,
        )

    # Response parsers (delegate to parser functions)

    def parse_propfind(self, response: DAVResponse) -> List[PropfindResult]:
        """Parse a PROPFIND response."""
        return parse_propfind_response(response)

    def parse_calendar_query(self, response: DAVResponse) -> List[CalendarQueryResult]:
        """Parse a calendar-query REPORT response."""
        return parse_calendar_query_response(response)

    def parse_sync_collection(
        self,
        response: DAVResponse,
    ) -> Tuple[List[CalendarQueryResult], Optional[str]]:
        """Parse a sync-collection REPORT response."""
        return parse_sync_collection_response(response)
```

### Phase 5: I/O Layer Abstraction

**Goal:** Create abstract I/O interface and implementations.

```python
# caldav/io/__init__.py
"""
I/O layer for CalDAV protocol.

This module provides sync and async implementations for executing
DAVRequest objects and returning DAVResponse objects.
"""
from .base import IOProtocol
from .sync import SyncIO
from .async_ import AsyncIO

__all__ = ["IOProtocol", "SyncIO", "AsyncIO"]
```

```python
# caldav/io/base.py
"""
Abstract I/O protocol definition.
"""
from typing import Protocol, runtime_checkable
from caldav.protocol.types import DAVRequest, DAVResponse


@runtime_checkable
class IOProtocol(Protocol):
    """
    Protocol defining the I/O interface.

    Implementations must provide a way to execute DAVRequest objects
    and return DAVResponse objects.
    """

    def execute(self, request: DAVRequest) -> DAVResponse:
        """
        Execute a request and return the response.

        This may be sync or async depending on implementation.
        """
        ...
```

```python
# caldav/io/sync.py
"""
Synchronous I/O implementation using requests library.
"""
from typing import Optional
import requests

from caldav.protocol.types import DAVRequest, DAVResponse, DAVMethod


class SyncIO:
    """
    Synchronous I/O shell using requests library.

    This is a thin wrapper that executes DAVRequest objects via HTTP
    and returns DAVResponse objects.
    """

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: float = 30.0,
    ):
        self.session = session or requests.Session()
        self.timeout = timeout

    def execute(self, request: DAVRequest) -> DAVResponse:
        """Execute request and return response."""
        response = self.session.request(
            method=request.method.value,
            url=request.path,
            headers=request.headers,
            data=request.body,
            timeout=self.timeout,
        )
        return DAVResponse(
            status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    def close(self) -> None:
        """Close the session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
```

```python
# caldav/io/async_.py
"""
Asynchronous I/O implementation using aiohttp library.
"""
from typing import Optional
import aiohttp

from caldav.protocol.types import DAVRequest, DAVResponse, DAVMethod


class AsyncIO:
    """
    Asynchronous I/O shell using aiohttp library.

    This is a thin wrapper that executes DAVRequest objects via HTTP
    and returns DAVResponse objects.
    """

    def __init__(
        self,
        session: Optional[aiohttp.ClientSession] = None,
        timeout: float = 30.0,
    ):
        self._session = session
        self._owns_session = session is None
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def execute(self, request: DAVRequest) -> DAVResponse:
        """Execute request and return response."""
        session = await self._get_session()
        async with session.request(
            method=request.method.value,
            url=request.path,
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
        """Close the session if we own it."""
        if self._session and self._owns_session:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
```

### Phase 6: Integration with Existing Classes

**Goal:** Refactor existing classes to use protocol layer internally.

#### Step 6.1: Refactor DAVClient

```python
# caldav/davclient.py (modified)
class DAVClient:
    def __init__(self, ...):
        # Existing initialization
        ...
        # Add protocol layer
        self._protocol = CalDAVProtocol(
            base_url=str(self.url),
            username=self.username,
            password=self.password,
        )
        self._io = SyncIO(session=self.session)

    def propfind(self, url, props, depth=0):
        """PROPFIND using protocol layer."""
        request = self._protocol.propfind_request(url, props, depth)
        response = self._io.execute(request)
        return self._protocol.parse_propfind(response)

    # Other methods similarly refactored...
```

#### Step 6.2: Refactor AsyncDAVClient

```python
# caldav/async_davclient.py (modified)
class AsyncDAVClient:
    def __init__(self, ...):
        # Existing initialization
        ...
        # Add protocol layer (same as sync - it's I/O-free!)
        self._protocol = CalDAVProtocol(
            base_url=str(self.url),
            username=self.username,
            password=self.password,
        )
        self._io = AsyncIO(session=self.session)

    async def propfind(self, url, props, depth=0):
        """PROPFIND using protocol layer."""
        request = self._protocol.propfind_request(url, props, depth)
        response = await self._io.execute(request)
        return self._protocol.parse_propfind(response)
```

### Phase 7: Testing

**Goal:** Add comprehensive tests for the protocol layer.

```python
# tests/test_protocol.py
"""
Unit tests for Sans-I/O protocol layer.

These tests verify protocol logic without any HTTP mocking required.
"""
import pytest
from datetime import datetime
from caldav.protocol import (
    CalDAVProtocol,
    DAVRequest,
    DAVResponse,
    DAVMethod,
    build_propfind_body,
    build_calendar_query_body,
    parse_propfind_response,
)


class TestXMLBuilders:
    """Test XML building functions."""

    def test_build_propfind_body(self):
        body = build_propfind_body(["displayname", "resourcetype"])
        assert b"<propfind" in body.lower() or b"<d:propfind" in body.lower()
        assert b"displayname" in body.lower()

    def test_build_calendar_query_with_time_range(self):
        body = build_calendar_query_body(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 12, 31),
            event=True,
        )
        assert b"calendar-query" in body.lower() or b"c:calendar-query" in body.lower()
        assert b"time-range" in body.lower()


class TestXMLParsers:
    """Test XML parsing functions."""

    def test_parse_propfind_response(self):
        xml = b'''<?xml version="1.0"?>
        <multistatus xmlns="DAV:">
            <response>
                <href>/calendars/user/</href>
                <propstat>
                    <prop>
                        <displayname>My Calendar</displayname>
                    </prop>
                    <status>HTTP/1.1 200 OK</status>
                </propstat>
            </response>
        </multistatus>'''

        response = DAVResponse(status=207, headers={}, body=xml)
        results = parse_propfind_response(response)

        assert len(results) == 1
        assert results[0].href == "/calendars/user/"
        assert results[0].properties["displayname"] == "My Calendar"


class TestCalDAVProtocol:
    """Test the protocol class."""

    def test_propfind_request_building(self):
        protocol = CalDAVProtocol(
            base_url="https://cal.example.com",
            username="user",
            password="pass",
        )

        request = protocol.propfind_request(
            path="/calendars/",
            props=["displayname"],
            depth=1,
        )

        assert request.method == DAVMethod.PROPFIND
        assert "calendars" in request.path
        assert request.headers["Depth"] == "1"
        assert "Authorization" in request.headers
        assert request.body is not None
```

## File Structure Summary

After implementation, the new structure:

```
caldav/
├── protocol/                    # NEW: Sans-I/O protocol layer
│   ├── __init__.py             # Package exports
│   ├── types.py                # DAVRequest, DAVResponse, result types
│   ├── xml_builders.py         # Pure XML construction functions
│   ├── xml_parsers.py          # Pure XML parsing functions
│   └── operations.py           # CalDAVProtocol class
│
├── io/                          # NEW: I/O shells
│   ├── __init__.py
│   ├── base.py                 # IOProtocol abstract interface
│   ├── sync.py                 # SyncIO (requests)
│   └── async_.py               # AsyncIO (aiohttp)
│
├── davclient.py                # MODIFIED: Uses protocol internally
├── async_davclient.py          # MODIFIED: Uses protocol internally
├── collection.py               # MODIFIED: Uses protocol internally
├── async_collection.py         # MODIFIED: Uses protocol internally
├── response.py                 # EXISTING: BaseDAVResponse (keep for compatibility)
├── search.py                   # EXISTING: CalDAVSearcher (delegates to protocol)
├── elements/                   # EXISTING: No changes
├── lib/                        # EXISTING: No changes
└── ...
```

## Migration Checklist

### Phase 1: Foundation
- [ ] Create `caldav/protocol/` package structure
- [ ] Implement `types.py` with DAVRequest, DAVResponse
- [ ] Create package `__init__.py` with exports
- [ ] Add basic unit tests for types

### Phase 2: XML Builders
- [ ] Extract PROPFIND body builder from existing code
- [ ] Extract calendar-query body builder from CalDAVSearcher
- [ ] Extract calendar-multiget body builder
- [ ] Extract sync-collection body builder
- [ ] Extract PROPPATCH body builder
- [ ] Extract MKCALENDAR body builder
- [ ] Add unit tests for all builders

### Phase 3: XML Parsers
- [ ] Extract multistatus parser from BaseDAVResponse
- [ ] Extract PROPFIND response parser
- [ ] Extract calendar-query response parser
- [ ] Extract sync-collection response parser
- [ ] Add unit tests for all parsers

### Phase 4: Protocol Class
- [ ] Implement CalDAVProtocol class
- [ ] Add request builder methods
- [ ] Add response parser methods
- [ ] Add authentication handling
- [ ] Add unit tests for protocol class

### Phase 5: I/O Layer
- [ ] Create `caldav/io/` package structure
- [ ] Implement SyncIO with requests
- [ ] Implement AsyncIO with aiohttp
- [ ] Add integration tests

### Phase 6: Integration
- [ ] Refactor DAVClient to use protocol layer
- [ ] Refactor AsyncDAVClient to use protocol layer
- [ ] Refactor Calendar to use protocol layer
- [ ] Refactor AsyncCalendar to use protocol layer
- [ ] Ensure all existing tests pass
- [ ] Run integration tests against live servers

### Phase 7: Documentation
- [ ] Update API documentation
- [ ] Add protocol layer usage examples
- [ ] Document migration for advanced users
- [ ] Update design documents

## Backward Compatibility

Throughout migration:

1. **Public API unchanged**: `DAVClient`, `Calendar`, etc. work exactly as before
2. **Existing imports work**: No changes to `caldav` or `caldav.aio` exports
3. **New optional API**: `caldav.protocol` available for advanced users
4. **Deprecation path**: Old internal methods can be deprecated gradually

## Timeline Estimate

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1: Foundation | 2-3 days | 2-3 days |
| Phase 2: XML Builders | 3-4 days | 5-7 days |
| Phase 3: XML Parsers | 3-4 days | 8-11 days |
| Phase 4: Protocol Class | 2-3 days | 10-14 days |
| Phase 5: I/O Layer | 2-3 days | 12-17 days |
| Phase 6: Integration | 5-7 days | 17-24 days |
| Phase 7: Documentation | 2-3 days | 19-27 days |

**Total: ~4-5 weeks of focused work**

This can be done incrementally - each phase delivers value and can be merged separately.
