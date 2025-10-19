"""
Async calendar object resources: AsyncEvent, AsyncTodo, AsyncJournal, etc.

These classes represent individual calendar objects (events, todos, journals)
and provide async APIs for loading, saving, and manipulating them.
"""
import logging
import uuid
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union
from urllib.parse import ParseResult
from urllib.parse import SplitResult

from .async_davobject import AsyncDAVObject
from .elements import cdav
from .lib.url import URL

if TYPE_CHECKING:
    from .async_davclient import AsyncDAVClient
    from .async_collection import AsyncCalendar

log = logging.getLogger("caldav")


class AsyncCalendarObjectResource(AsyncDAVObject):
    """
    Base class for async calendar objects (events, todos, journals).

    This mirrors CalendarObjectResource but provides async methods.
    """

    _comp_name = "VEVENT"  # Overridden in subclasses
    _data: Optional[str] = None

    def __init__(
        self,
        client: Optional["AsyncDAVClient"] = None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        data: Optional[str] = None,
        parent: Optional["AsyncCalendar"] = None,
        id: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Create a calendar object resource.

        Args:
            client: AsyncDAVClient instance
            url: URL of the object
            data: iCalendar data as string
            parent: Parent calendar
            id: UID of the object
        """
        super().__init__(client=client, url=url, parent=parent, id=id, **kwargs)
        self._data = data

        # If data is provided, extract UID if not already set
        if data and not id:
            self.id = self._extract_uid_from_data(data)

        # Generate URL if not provided
        if not self.url and parent:
            uid = self.id or str(uuid.uuid4())
            self.url = parent.url.join(f"{uid}.ics")

    def _extract_uid_from_data(self, data: str) -> Optional[str]:
        """Extract UID from iCalendar data"""
        try:
            for line in data.split("\n"):
                stripped = line.strip()
                if stripped.startswith("UID:"):
                    uid = stripped.split(":", 1)[1].strip()
                    log.debug(
                        f"[UID EXTRACT DEBUG] Extracted UID: '{uid}' from line: '{line[:80]}'"
                    )
                    return uid
            log.warning(
                f"[UID EXTRACT DEBUG] No UID found in data. First 500 chars: {data[:500]}"
            )
        except Exception as e:
            log.error(f"[UID EXTRACT DEBUG] Exception extracting UID: {e}")
            pass
        return None

    @property
    def data(self) -> Optional[str]:
        """Get the iCalendar data for this object"""
        return self._data

    @data.setter
    def data(self, value: str):
        """Set the iCalendar data for this object"""
        self._data = value
        # Update UID if present in data
        if value and not self.id:
            self.id = self._extract_uid_from_data(value)

    async def load(
        self, only_if_unloaded: bool = False
    ) -> "AsyncCalendarObjectResource":
        """
        Load the object data from the server.

        Args:
            only_if_unloaded: Only load if data not already present

        Returns:
            self (for chaining)
        """
        if only_if_unloaded and self._data:
            return self

        # GET the object
        response = await self.client.request(str(self.url), "GET")
        self._data = response.raw
        return self

    async def save(
        self, if_schedule_tag_match: Optional[str] = None, **kwargs
    ) -> "AsyncCalendarObjectResource":
        """
        Save the object to the server.

        Args:
            if_schedule_tag_match: Schedule-Tag for conditional update

        Returns:
            self (for chaining)
        """
        if not self._data:
            raise ValueError("Cannot save object without data")

        # Ensure we have a URL
        if not self.url:
            if not self.parent:
                raise ValueError("Cannot save without URL or parent calendar")
            uid = self.id or str(uuid.uuid4())
            log.debug(
                f"[SAVE DEBUG] Generating URL: parent.url={self.parent.url}, uid={uid}, self.id={self.id}"
            )
            self.url = self.parent.url.join(f"{uid}.ics")
            log.debug(f"[SAVE DEBUG] Generated URL: {self.url}")

        headers = {
            "Content-Type": "text/calendar; charset=utf-8",
        }

        if if_schedule_tag_match:
            headers["If-Schedule-Tag-Match"] = if_schedule_tag_match

        # PUT the object
        log.debug(f"[SAVE DEBUG] PUTting to URL: {str(self.url)}")
        await self.client.put(str(self.url), self._data, headers=headers)
        log.debug(f"[SAVE DEBUG] PUT completed successfully")
        return self

    async def delete(self) -> None:
        """Delete this object from the server"""
        await self.client.delete(str(self.url))

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.url})"


class AsyncEvent(AsyncCalendarObjectResource):
    """
    Async event object.

    Represents a VEVENT calendar component.
    """

    _comp_name = "VEVENT"

    async def save(self, **kwargs) -> "AsyncEvent":
        """Save the event to the server"""
        return await super().save(**kwargs)


class AsyncTodo(AsyncCalendarObjectResource):
    """
    Async todo object.

    Represents a VTODO calendar component.
    """

    _comp_name = "VTODO"

    async def save(self, **kwargs) -> "AsyncTodo":
        """Save the todo to the server"""
        return await super().save(**kwargs)


class AsyncJournal(AsyncCalendarObjectResource):
    """
    Async journal object.

    Represents a VJOURNAL calendar component.
    """

    _comp_name = "VJOURNAL"

    async def save(self, **kwargs) -> "AsyncJournal":
        """Save the journal to the server"""
        return await super().save(**kwargs)


class AsyncFreeBusy(AsyncCalendarObjectResource):
    """
    Async free/busy object.

    Represents a VFREEBUSY calendar component.
    """

    _comp_name = "VFREEBUSY"

    async def save(self, **kwargs) -> "AsyncFreeBusy":
        """Save the freebusy to the server"""
        return await super().save(**kwargs)
