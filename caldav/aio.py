#!/usr/bin/env python
"""
Modern async CalDAV client with a clean, Pythonic API.

This module provides async CalDAV access without the baggage of backward
compatibility. It's designed from the ground up for async/await.

Example:
    async with CalDAVClient(url, username, password) as client:
        calendars = await client.get_calendars()
        for cal in calendars:
            events = await cal.get_events(start=date.today())
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union
from urllib.parse import ParseResult, SplitResult

from lxml import etree

try:
    from niquests import AsyncSession
    from niquests.auth import AuthBase, HTTPBasicAuth, HTTPDigestAuth
    from niquests.models import Response
except ImportError:
    raise ImportError(
        "Async CalDAV requires niquests. Install with: pip install -U niquests"
    )

from .elements import cdav, dav
from .lib import error
from .lib.python_utilities import to_normal_str, to_wire
from .lib.url import URL
from . import __version__

log = logging.getLogger("caldav.aio")


class CalDAVClient:
    """
    Modern async CalDAV client.

    Args:
        url: CalDAV server URL
        username: Authentication username
        password: Authentication password
        auth: Custom auth object (overrides username/password)
        timeout: Request timeout in seconds (default: 90)
        verify_ssl: Verify SSL certificates (default: True)
        ssl_cert: Client SSL certificate path
        headers: Additional HTTP headers

    Example:
        async with CalDAVClient("https://cal.example.com", "user", "pass") as client:
            calendars = await client.get_calendars()
            print(f"Found {len(calendars)} calendars")
    """

    def __init__(
        self,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        *,
        auth: Optional[AuthBase] = None,
        timeout: int = 90,
        verify_ssl: bool = True,
        ssl_cert: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.url = URL.objectify(url)
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.ssl_cert = ssl_cert

        # Setup authentication
        if auth:
            self.auth = auth
        elif username and password:
            # Try Digest first, fall back to Basic
            self.auth = HTTPDigestAuth(username, password)
        else:
            self.auth = None

        # Setup headers
        self.headers = headers or {}
        if "User-Agent" not in self.headers:
            self.headers["User-Agent"] = f"caldav-async/{__version__}"

        # Create async session
        self.session = AsyncSession()

    async def __aenter__(self) -> "CalDAVClient":
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit"""
        await self.close()

    async def close(self) -> None:
        """Close the session"""
        if self.session:
            await self.session.close()

    async def request(
        self,
        url: Union[str, URL],
        method: str = "GET",
        body: Union[str, bytes] = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        """
        Low-level HTTP request method.

        Returns the raw response object. Most users should use higher-level
        methods like get_calendars() instead.
        """
        headers = headers or {}
        combined_headers = {**self.headers, **headers}

        if not body and "Content-Type" in combined_headers:
            del combined_headers["Content-Type"]

        url_obj = URL.objectify(url)

        log.debug(
            f"{method} {url_obj}\n"
            f"Headers: {combined_headers}\n"
            f"Body: {to_normal_str(body)[:500]}"
        )

        response = await self.session.request(
            method,
            str(url_obj),
            data=to_wire(body) if body else None,
            headers=combined_headers,
            auth=self.auth,
            timeout=self.timeout,
            verify=self.verify_ssl,
            cert=self.ssl_cert,
        )

        log.debug(f"Response: {response.status_code} {response.reason}")

        if response.status_code >= 400:
            raise error.AuthorizationError(
                url=str(url_obj),
                reason=f"{response.status_code} {response.reason}"
            )

        return response

    async def propfind(
        self,
        url: Union[str, URL],
        props: Optional[List] = None,
        depth: int = 0,
    ) -> etree._Element:
        """
        PROPFIND request - returns parsed XML tree.

        Args:
            url: Resource URL
            props: List of property elements to request
            depth: Depth header (0, 1, or infinity)

        Returns:
            Parsed XML tree of the response
        """
        body = ""
        if props:
            prop = dav.Prop() + props
            root = dav.Propfind() + prop
            body = etree.tostring(
                root.xmlelement(),
                encoding="utf-8",
                xml_declaration=True,
            )

        response = await self.request(
            url,
            "PROPFIND",
            body,
            {"Depth": str(depth), "Content-Type": "application/xml; charset=utf-8"},
        )

        return etree.fromstring(response.content)

    async def report(
        self,
        url: Union[str, URL],
        query: Union[str, bytes, etree._Element],
        depth: int = 0,
    ) -> etree._Element:
        """
        REPORT request - returns parsed XML tree.

        Args:
            url: Resource URL
            query: Report query (XML string, bytes, or element)
            depth: Depth header

        Returns:
            Parsed XML tree of the response
        """
        if isinstance(query, etree._Element):
            body = etree.tostring(query, encoding="utf-8", xml_declaration=True)
        else:
            body = query

        response = await self.request(
            url,
            "REPORT",
            body,
            {"Depth": str(depth), "Content-Type": "application/xml; charset=utf-8"},
        )

        return etree.fromstring(response.content)

    async def get_principal_url(self) -> URL:
        """
        Get the principal URL for the current user.

        Returns:
            URL of the principal resource
        """
        tree = await self.propfind(
            self.url,
            [dav.CurrentUserPrincipal()],
            depth=0,
        )

        # Parse the response to extract principal URL
        namespaces = {"d": "DAV:"}
        principal_elements = tree.xpath(
            "//d:current-user-principal/d:href/text()",
            namespaces=namespaces
        )

        if not principal_elements:
            raise error.PropfindError("Could not find current-user-principal")

        return self.url.join(principal_elements[0])

    async def get_calendar_home_url(self) -> URL:
        """
        Get the calendar-home-set URL.

        Returns:
            URL of the calendar home collection
        """
        principal_url = await self.get_principal_url()

        tree = await self.propfind(
            principal_url,
            [cdav.CalendarHomeSet()],
            depth=0,
        )

        # Parse the response
        namespaces = {"c": "urn:ietf:params:xml:ns:caldav"}
        home_elements = tree.xpath(
            "//c:calendar-home-set/d:href/text()",
            namespaces={**namespaces, "d": "DAV:"}
        )

        if not home_elements:
            raise error.PropfindError("Could not find calendar-home-set")

        return self.url.join(home_elements[0])

    async def get_calendars(self) -> List["Calendar"]:
        """
        Get all calendars for the current user.

        Returns:
            List of Calendar objects

        Example:
            async with CalDAVClient(...) as client:
                calendars = await client.get_calendars()
                for cal in calendars:
                    print(f"{cal.name}: {cal.url}")
        """
        home_url = await self.get_calendar_home_url()

        tree = await self.propfind(
            home_url,
            [dav.DisplayName(), dav.ResourceType()],
            depth=1,
        )

        calendars = []
        namespaces = {"d": "DAV:", "c": "urn:ietf:params:xml:ns:caldav"}

        for response in tree.xpath("//d:response", namespaces=namespaces):
            # Check if this is a calendar
            is_calendar = response.xpath(
                ".//d:resourcetype/c:calendar",
                namespaces=namespaces
            )

            if is_calendar:
                href = response.xpath(".//d:href/text()", namespaces=namespaces)[0]
                name_elements = response.xpath(
                    ".//d:displayname/text()",
                    namespaces=namespaces
                )
                name = name_elements[0] if name_elements else None

                cal_url = self.url.join(href)
                calendars.append(Calendar(self, cal_url, name=name))

        return calendars

    async def get_calendar(self, name: str) -> Optional["Calendar"]:
        """
        Get a specific calendar by name.

        Args:
            name: Display name of the calendar

        Returns:
            Calendar object or None if not found
        """
        calendars = await self.get_calendars()
        for cal in calendars:
            if cal.name == name:
                return cal
        return None


class Calendar:
    """
    Represents a CalDAV calendar.

    This class provides methods to interact with calendar events.
    """

    def __init__(
        self,
        client: CalDAVClient,
        url: URL,
        name: Optional[str] = None,
    ) -> None:
        self.client = client
        self.url = url
        self.name = name

    def __repr__(self) -> str:
        return f"<Calendar(name={self.name!r}, url={self.url})>"

    async def get_events(
        self,
        start: Optional[Union[date, datetime]] = None,
        end: Optional[Union[date, datetime]] = None,
    ) -> List["Event"]:
        """
        Get events from this calendar.

        Args:
            start: Filter events starting after this date/time
            end: Filter events ending before this date/time

        Returns:
            List of Event objects

        Example:
            events = await calendar.get_events(
                start=date.today(),
                end=date.today() + timedelta(days=7)
            )
        """
        # Build calendar-query
        query_elem = cdav.CalendarQuery()
        prop_elem = dav.Prop() + [cdav.CalendarData()]
        query_elem += prop_elem

        # Add time-range filter if specified
        if start or end:
            comp_filter = cdav.CompFilter(name="VCALENDAR")
            event_filter = cdav.CompFilter(name="VEVENT")

            if start or end:
                time_range = cdav.TimeRange()
                if start:
                    time_range.attributes["start"] = _format_datetime(start)
                if end:
                    time_range.attributes["end"] = _format_datetime(end)
                event_filter += time_range

            comp_filter += event_filter
            filter_elem = cdav.Filter() + comp_filter
            query_elem += filter_elem

        query_xml = etree.tostring(
            query_elem.xmlelement(),
            encoding="utf-8",
            xml_declaration=True,
        )

        tree = await self.client.report(self.url, query_xml, depth=1)

        # Parse events from response
        events = []
        namespaces = {"d": "DAV:", "c": "urn:ietf:params:xml:ns:caldav"}

        for response in tree.xpath("//d:response", namespaces=namespaces):
            href = response.xpath(".//d:href/text()", namespaces=namespaces)[0]
            cal_data_elements = response.xpath(
                ".//c:calendar-data/text()",
                namespaces=namespaces
            )

            if cal_data_elements:
                event_url = self.url.join(href)
                ical_data = cal_data_elements[0]
                events.append(Event(self.client, event_url, ical_data))

        return events

    async def create_event(
        self,
        ical_data: str,
        uid: Optional[str] = None,
    ) -> "Event":
        """
        Create a new event in this calendar.

        Args:
            ical_data: iCalendar data (VEVENT component)
            uid: Optional UID (will be generated if not provided)

        Returns:
            Created Event object
        """
        import uuid
        from .lib.python_utilities import to_wire

        if not uid:
            uid = str(uuid.uuid4())

        event_url = self.url.join(f"{uid}.ics")

        await self.client.request(
            event_url,
            "PUT",
            ical_data,
            {"Content-Type": "text/calendar; charset=utf-8"},
        )

        return Event(self.client, event_url, ical_data)


class Event:
    """
    Represents a CalDAV event.
    """

    def __init__(
        self,
        client: CalDAVClient,
        url: URL,
        ical_data: str,
    ) -> None:
        self.client = client
        self.url = url
        self.ical_data = ical_data

        # Parse basic info from ical_data
        self._parse_ical()

    def _parse_ical(self) -> None:
        """Parse iCalendar data to extract basic properties"""
        # This is simplified - in production you'd use the icalendar library
        import icalendar

        try:
            cal = icalendar.Calendar.from_ical(self.ical_data)
            for component in cal.walk():
                if component.name == "VEVENT":
                    self.summary = str(component.get("summary", ""))
                    self.uid = str(component.get("uid", ""))
                    self.dtstart = component.get("dtstart")
                    self.dtend = component.get("dtend")
                    break
        except:
            self.summary = ""
            self.uid = ""
            self.dtstart = None
            self.dtend = None

    def __repr__(self) -> str:
        return f"<Event(summary={self.summary!r}, uid={self.uid!r})>"

    async def delete(self) -> None:
        """Delete this event"""
        await self.client.request(self.url, "DELETE")

    async def update(self, ical_data: str) -> None:
        """Update this event with new iCalendar data"""
        await self.client.request(
            self.url,
            "PUT",
            ical_data,
            {"Content-Type": "text/calendar; charset=utf-8"},
        )
        self.ical_data = ical_data
        self._parse_ical()


def _format_datetime(dt: Union[date, datetime]) -> str:
    """Format date/datetime for CalDAV time-range queries"""
    if isinstance(dt, datetime):
        return dt.strftime("%Y%m%dT%H%M%SZ")
    else:
        return dt.strftime("%Y%m%d")


__all__ = ["CalDAVClient", "Calendar", "Event"]
