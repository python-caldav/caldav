"""
Async collection classes for CalDAV: AsyncCalendar, AsyncPrincipal, etc.

These are async equivalents of the sync collection classes, providing
async/await APIs for calendar and principal operations.
"""
import logging
from typing import Any
from typing import List
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union
from urllib.parse import ParseResult
from urllib.parse import SplitResult

from .async_davobject import AsyncDAVObject
from .elements import cdav
from .elements import dav
from .lib.ical_logic import ICalLogic
from .lib.url import URL

if TYPE_CHECKING:
    from .async_davclient import AsyncDAVClient, AsyncDAVResponse

log = logging.getLogger("caldav")


class AsyncCalendarSet(AsyncDAVObject):
    """
    Async calendar set, contains a list of calendars.

    This is typically the parent object of calendars.
    """

    async def calendars(self) -> List["AsyncCalendar"]:
        """
        List all calendar collections in this set.

        Returns:
         * [AsyncCalendar(), ...]
        """
        cals = []

        # Get children of type calendar
        props = [dav.ResourceType(), dav.DisplayName()]
        response = await self.get_properties(props, depth=1, parse_props=False)

        for href, props_dict in response.items():
            if href == str(self.url):
                # Skip the collection itself
                continue

            # Check if this is a calendar by looking at resourcetype
            resource_type_elem = props_dict.get(dav.ResourceType.tag)
            if resource_type_elem is not None:
                # Check if calendar tag is in the children
                is_calendar = False
                for child in resource_type_elem:
                    if child.tag == cdav.Calendar.tag:
                        is_calendar = True
                        break

                if is_calendar:
                    cal_url = URL.objectify(href)

                    # Get displayname
                    displayname_elem = props_dict.get(dav.DisplayName.tag)
                    cal_name = (
                        displayname_elem.text if displayname_elem is not None else ""
                    )

                    # Extract calendar ID from URL
                    try:
                        cal_id = cal_url.path.rstrip("/").split("/")[-1]
                    except:
                        cal_id = None

                    cals.append(
                        AsyncCalendar(
                            self.client,
                            id=cal_id,
                            url=cal_url,
                            parent=self,
                            name=cal_name,
                        )
                    )

        return cals

    async def make_calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        supported_calendar_component_set: Optional[Any] = None,
    ) -> "AsyncCalendar":
        """
        Create a new calendar in this calendar set.

        Args:
            name: Display name for the calendar
            cal_id: Calendar ID (will be part of URL)
            supported_calendar_component_set: Component types supported

        Returns:
            AsyncCalendar object
        """
        if not cal_id:
            import uuid

            cal_id = str(uuid.uuid4())

        if not name:
            name = cal_id

        cal_url = self.url.join(cal_id + "/")

        # Build MKCALENDAR request body
        from .elements import cdav, dav
        from lxml import etree

        set_element = dav.Set() + dav.Prop()
        props = set_element.find(".//" + dav.Prop.tag)

        # Add display name
        name_element = dav.DisplayName(name)
        props.append(name_element.xmlelement())

        # Add supported calendar component set if specified
        if supported_calendar_component_set:
            sccs = cdav.SupportedCalendarComponentSet()
            for comp in supported_calendar_component_set:
                sccs += cdav.Comp(name=comp)
            props.append(sccs.xmlelement())

        root = cdav.Mkcalendar() + set_element
        body = etree.tostring(root.xmlelement(), encoding="utf-8", xml_declaration=True)

        await self.client.mkcalendar(str(cal_url), body)

        return AsyncCalendar(
            self.client, url=cal_url, parent=self, name=name, id=cal_id
        )

    def calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
    ) -> "AsyncCalendar":
        """
        Get a calendar object (doesn't verify it exists on server).

        Args:
            name: Display name
            cal_id: Calendar ID

        Returns:
            AsyncCalendar object
        """
        if cal_id:
            cal_url = self.url.join(cal_id + "/")
            return AsyncCalendar(
                self.client, url=cal_url, parent=self, id=cal_id, name=name
            )
        elif name:
            return AsyncCalendar(self.client, parent=self, name=name)
        else:
            raise ValueError("Either name or cal_id must be specified")


class AsyncPrincipal(AsyncDAVObject):
    """
    Async principal object, represents the logged-in user.

    A principal typically has a calendar home set containing calendars.
    """

    def __init__(
        self,
        client: Optional["AsyncDAVClient"] = None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        calendar_home_set: URL = None,
        **kwargs,
    ) -> None:
        """
        Create an AsyncPrincipal.

        Args:
          client: an AsyncDAVClient() object
          url: The principal URL, if known
          calendar_home_set: the calendar home set, if known

        If url is not given, will try to discover it via PROPFIND.
        """
        self._calendar_home_set = calendar_home_set
        super(AsyncPrincipal, self).__init__(client=client, url=url, **kwargs)

    async def _ensure_principal_url(self):
        """Ensure we have a principal URL (async initialization helper)"""
        if self.url is None:
            if self.client is None:
                raise ValueError("Unexpected value None for self.client")

            self.url = self.client.url
            cup = await self.get_property(dav.CurrentUserPrincipal())

            if cup is None:
                log.warning("calendar server lacking a feature:")
                log.warning("current-user-principal property not found")
                log.warning("assuming %s is the principal URL" % self.client.url)
            else:
                self.url = self.client.url.join(URL.objectify(cup))

    @property
    async def calendar_home_set(self) -> AsyncCalendarSet:
        """
        Get the calendar home set for this principal.

        The calendar home set is the collection that contains the user's calendars.
        """
        await self._ensure_principal_url()

        if self._calendar_home_set is None:
            chs = await self.get_property(cdav.CalendarHomeSet())
            if chs is None:
                raise Exception("calendar-home-set property not found")
            self._calendar_home_set = URL.objectify(chs)

        return AsyncCalendarSet(
            self.client,
            url=self._calendar_home_set,
            parent=self,
        )

    async def calendars(self) -> List["AsyncCalendar"]:
        """
        List all calendars for this principal.

        Returns:
            List of AsyncCalendar objects
        """
        chs = await self.calendar_home_set
        return await chs.calendars()

    async def make_calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        supported_calendar_component_set: Optional[Any] = None,
    ) -> "AsyncCalendar":
        """
        Create a new calendar for this principal.

        Convenience method, bypasses the calendar_home_set object.
        """
        chs = await self.calendar_home_set
        return await chs.make_calendar(
            name,
            cal_id,
            supported_calendar_component_set=supported_calendar_component_set,
        )

    def calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        cal_url: Optional[str] = None,
    ) -> "AsyncCalendar":
        """
        Get a calendar object (doesn't verify existence on server).

        Args:
            name: Display name
            cal_id: Calendar ID
            cal_url: Full calendar URL

        Returns:
            AsyncCalendar object
        """
        if cal_url:
            if self.client is None:
                raise ValueError("Unexpected value None for self.client")
            return AsyncCalendar(self.client, url=self.client.url.join(cal_url))
        else:
            # This is synchronous - just constructs an object
            # For async lookup, user should use calendars() method
            if self._calendar_home_set:
                chs = AsyncCalendarSet(
                    self.client, url=self._calendar_home_set, parent=self
                )
                return chs.calendar(name, cal_id)
            else:
                raise ValueError("calendar_home_set not known, use calendars() instead")


class AsyncCalendar(AsyncDAVObject):
    """
    Async calendar collection.

    A calendar contains events, todos, and journals.
    """

    async def events(self) -> List["AsyncEvent"]:
        """
        List all events from the calendar.

        Returns:
         * [AsyncEvent(), ...]
        """
        return await self.search(comp_class=AsyncEvent)

    async def todos(self) -> List["AsyncTodo"]:
        """
        List all todos from the calendar.

        Returns:
         * [AsyncTodo(), ...]
        """
        return await self.search(comp_class=AsyncTodo)

    async def journals(self) -> List["AsyncJournal"]:
        """
        List all journals from the calendar.

        Returns:
         * [AsyncJournal(), ...]
        """
        return await self.search(comp_class=AsyncJournal)

    async def search(self, comp_class=None, **kwargs) -> List[Any]:
        """
        Search for calendar objects.

        This is a simplified version focusing on basic component retrieval.

        Args:
            comp_class: The class to instantiate (AsyncEvent, AsyncTodo, AsyncJournal)

        Returns:
            List of calendar objects
        """
        if comp_class is None:
            comp_class = AsyncEvent

        # Build calendar-query
        from .elements import cdav, dav
        from lxml import etree

        # Build proper nested comp-filter structure for Nextcloud compatibility
        # Filter must contain CompFilter, which can contain nested CompFilters
        inner_comp_filter = cdav.CompFilter(name=comp_class._comp_name)
        outer_comp_filter = cdav.CompFilter(name="VCALENDAR") + inner_comp_filter
        filter_element = cdav.Filter() + outer_comp_filter

        query = (
            cdav.CalendarQuery() + [dav.Prop() + cdav.CalendarData()] + filter_element
        )

        body = etree.tostring(
            query.xmlelement(), encoding="utf-8", xml_declaration=True
        )
        log.debug(f"[SEARCH DEBUG] Sending calendar-query REPORT to {self.url}")
        log.debug(f"[SEARCH DEBUG] Request body: {body[:500]}")
        response = await self.client.report(str(self.url), body, depth=1)

        # Parse response
        log.debug(f"[SEARCH DEBUG] Response type: {type(response)}")
        if hasattr(response, "raw"):
            log.debug(f"[SEARCH DEBUG] Full raw response: {response.raw}")
        objects = []
        response_data = response.expand_simple_props([cdav.CalendarData()])
        log.debug(f"[SEARCH DEBUG] Received {len(response_data)} items in response")
        log.debug(f"[SEARCH DEBUG] Response data keys: {list(response_data.keys())}")

        for href, props in response_data.items():
            log.debug(f"[SEARCH DEBUG] Processing href: {href}")
            if href == str(self.url):
                log.debug(f"[SEARCH DEBUG] Skipping - matches calendar URL")
                continue

            cal_data = props.get(cdav.CalendarData.tag)
            if cal_data:
                log.debug(f"[SEARCH DEBUG] Found calendar data for href: {href}")
                # Don't pass url - let object generate from UID to avoid relative URL issues
                obj = comp_class(
                    client=self.client,
                    data=cal_data,
                    parent=self,
                )
                log.debug(
                    f"[SEARCH DEBUG] Created {comp_class.__name__} object with id={obj.id}, url={obj.url}"
                )
                log.debug(
                    f"[SEARCH DEBUG] First 200 chars of cal_data: {cal_data[:200]}"
                )
                objects.append(obj)
            else:
                log.debug(f"[SEARCH DEBUG] No calendar data for href: {href}")

        log.debug(f"[SEARCH DEBUG] Returning {len(objects)} objects")
        return objects

    async def save_event(
        self, ical: Optional[str] = None, **kwargs
    ) -> tuple["AsyncEvent", "AsyncDAVResponse"]:
        """
        Save an event to this calendar.

        Args:
            ical: iCalendar data as string

        Returns:
            Tuple of (AsyncEvent object, response)
        """
        return await self._save_object(ical, AsyncEvent, **kwargs)

    async def save_todo(
        self, ical: Optional[str] = None, **kwargs
    ) -> tuple["AsyncTodo", "AsyncDAVResponse"]:
        """
        Save a todo to this calendar.

        Args:
            ical: iCalendar data as string

        Returns:
            Tuple of (AsyncTodo object, response)
        """
        return await self._save_object(ical, AsyncTodo, **kwargs)

    async def _save_object(self, ical, obj_class, **kwargs):
        """Helper to save a calendar object

        Returns:
            Tuple of (object, response)
        """
        obj = obj_class(client=self.client, data=ical, parent=self)
        obj, response = await obj.save(**kwargs)
        return obj, response

    async def event_by_uid(self, uid: str) -> "AsyncEvent":
        """Find an event by UID"""
        log.debug(f"[EVENT_BY_UID DEBUG] Searching for event with UID: {uid}")
        results = await self.search(comp_class=AsyncEvent)
        log.debug(f"[EVENT_BY_UID DEBUG] Search returned {len(results)} events")
        for event in results:
            log.debug(
                f"[EVENT_BY_UID DEBUG] Comparing event.id='{event.id}' with uid='{uid}'"
            )
            if event.id == uid:
                log.debug(f"[EVENT_BY_UID DEBUG] Match found!")
                return event
        log.warning(
            f"[EVENT_BY_UID DEBUG] No match found. Available UIDs: {[e.id for e in results]}"
        )
        raise Exception(f"Event with UID {uid} not found")

    async def todo_by_uid(self, uid: str) -> "AsyncTodo":
        """Find a todo by UID"""
        results = await self.search(comp_class=AsyncTodo)
        for todo in results:
            if todo.id == uid:
                return todo
        raise Exception(f"Todo with UID {uid} not found")


# Calendar Object Resources (Events, Todos, Journals, FreeBusy)


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
            self.id = ICalLogic.extract_uid_from_data(data)

        # Generate URL if not provided
        if not self.url and parent:
            self.url = ICalLogic.generate_object_url(parent.url, self.id)

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
            self.id = ICalLogic.extract_uid_from_data(value)

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
    ) -> tuple["AsyncCalendarObjectResource", "AsyncDAVResponse"]:
        """
        Save the object to the server.

        Args:
            if_schedule_tag_match: Schedule-Tag for conditional update

        Returns:
            Tuple of (self, response) for chaining and status checking
        """
        if not self._data:
            raise ValueError("Cannot save object without data")

        # Ensure we have a URL
        if not self.url:
            if not self.parent:
                raise ValueError("Cannot save without URL or parent calendar")
            uid = self.id or ICalLogic.generate_uid()
            log.debug(
                f"[SAVE DEBUG] Generating URL: parent.url={self.parent.url}, uid={uid}, self.id={self.id}"
            )
            self.url = ICalLogic.generate_object_url(self.parent.url, uid)
            log.debug(f"[SAVE DEBUG] Generated URL: {self.url}")

        headers = {
            "Content-Type": "text/calendar; charset=utf-8",
        }

        if if_schedule_tag_match:
            headers["If-Schedule-Tag-Match"] = if_schedule_tag_match

        # PUT the object
        log.debug(f"[SAVE DEBUG] PUTting to URL: {str(self.url)}")
        response = await self.client.put(str(self.url), self._data, headers=headers)
        log.debug(f"[SAVE DEBUG] PUT completed with status: {response.status}")
        return self, response

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

    async def save(self, **kwargs) -> tuple["AsyncEvent", "AsyncDAVResponse"]:
        """Save the event to the server

        Returns:
            Tuple of (event, response) for chaining and status checking
        """
        return await super().save(**kwargs)


class AsyncTodo(AsyncCalendarObjectResource):
    """
    Async todo object.

    Represents a VTODO calendar component.
    """

    _comp_name = "VTODO"

    async def save(self, **kwargs) -> tuple["AsyncTodo", "AsyncDAVResponse"]:
        """Save the todo to the server

        Returns:
            Tuple of (todo, response) for chaining and status checking
        """
        return await super().save(**kwargs)


class AsyncJournal(AsyncCalendarObjectResource):
    """
    Async journal object.

    Represents a VJOURNAL calendar component.
    """

    _comp_name = "VJOURNAL"

    async def save(self, **kwargs) -> tuple["AsyncJournal", "AsyncDAVResponse"]:
        """Save the journal to the server

        Returns:
            Tuple of (journal, response) for chaining and status checking
        """
        return await super().save(**kwargs)


class AsyncFreeBusy(AsyncCalendarObjectResource):
    """
    Async free/busy object.

    Represents a VFREEBUSY calendar component.
    """

    _comp_name = "VFREEBUSY"

    async def save(self, **kwargs) -> tuple["AsyncFreeBusy", "AsyncDAVResponse"]:
        """Save the freebusy to the server

        Returns:
            Tuple of (freebusy, response) for chaining and status checking
        """
        return await super().save(**kwargs)
