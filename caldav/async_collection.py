"""
Async collection classes for CalDAV: AsyncCalendar, AsyncPrincipal, etc.

These are async equivalents of the sync collection classes, providing
async/await APIs for calendar and principal operations.
"""
import logging
from typing import Any, List, Optional, TYPE_CHECKING, Union
from urllib.parse import ParseResult, SplitResult

from .async_davobject import AsyncDAVObject
from .elements import cdav, dav
from .lib.url import URL

if TYPE_CHECKING:
    from .async_davclient import AsyncDAVClient
    from .async_objects import AsyncEvent, AsyncTodo, AsyncJournal

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
                    cal_name = displayname_elem.text if displayname_elem is not None else ""

                    # Extract calendar ID from URL
                    try:
                        cal_id = cal_url.path.rstrip('/').split('/')[-1]
                    except:
                        cal_id = None

                    cals.append(
                        AsyncCalendar(
                            self.client, id=cal_id, url=cal_url, parent=self, name=cal_name
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

        return AsyncCalendar(self.client, url=cal_url, parent=self, name=name, id=cal_id)

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
            return AsyncCalendar(self.client, url=cal_url, parent=self, id=cal_id, name=name)
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
            name, cal_id, supported_calendar_component_set=supported_calendar_component_set
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
                chs = AsyncCalendarSet(self.client, url=self._calendar_home_set, parent=self)
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
        from .async_objects import AsyncEvent
        return await self.search(comp_class=AsyncEvent)

    async def todos(self) -> List["AsyncTodo"]:
        """
        List all todos from the calendar.

        Returns:
         * [AsyncTodo(), ...]
        """
        from .async_objects import AsyncTodo
        return await self.search(comp_class=AsyncTodo)

    async def journals(self) -> List["AsyncJournal"]:
        """
        List all journals from the calendar.

        Returns:
         * [AsyncJournal(), ...]
        """
        from .async_objects import AsyncJournal
        return await self.search(comp_class=AsyncJournal)

    async def search(
        self,
        comp_class=None,
        **kwargs
    ) -> List[Any]:
        """
        Search for calendar objects.

        This is a simplified version focusing on basic component retrieval.

        Args:
            comp_class: The class to instantiate (AsyncEvent, AsyncTodo, AsyncJournal)

        Returns:
            List of calendar objects
        """
        if comp_class is None:
            from .async_objects import AsyncEvent
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
            cdav.CalendarQuery()
            + [dav.Prop() + cdav.CalendarData()]
            + filter_element
        )

        body = etree.tostring(query.xmlelement(), encoding="utf-8", xml_declaration=True)
        log.debug(f"[SEARCH DEBUG] Sending calendar-query REPORT to {self.url}")
        log.debug(f"[SEARCH DEBUG] Request body: {body[:500]}")
        response = await self.client.report(str(self.url), body, depth=1)

        # Parse response
        log.debug(f"[SEARCH DEBUG] Response type: {type(response)}")
        if hasattr(response, 'raw'):
            log.debug(f"[SEARCH DEBUG] Full raw response: {response.raw}")
        objects = []
        response_data = response.expand_simple_props([cdav.CalendarData()])
        log.debug(f"[SEARCH DEBUG] Received {len(response_data)} items in response")
        log.debug(f"[SEARCH DEBUG] Response data keys: {list(response_data.keys())}")

        for href, props in response_data.items():
            if href == str(self.url):
                continue

            cal_data = props.get(cdav.CalendarData.tag)
            if cal_data:
                obj = comp_class(
                    client=self.client,
                    url=href,
                    data=cal_data,
                    parent=self,
                )
                log.debug(f"[SEARCH DEBUG] Created {comp_class.__name__} object with id={obj.id}, url={href}")
                log.debug(f"[SEARCH DEBUG] First 200 chars of cal_data: {cal_data[:200]}")
                objects.append(obj)

        log.debug(f"[SEARCH DEBUG] Returning {len(objects)} objects")
        return objects

    async def save_event(
        self,
        ical: Optional[str] = None,
        **kwargs
    ) -> "AsyncEvent":
        """
        Save an event to this calendar.

        Args:
            ical: iCalendar data as string

        Returns:
            AsyncEvent object
        """
        from .async_objects import AsyncEvent
        return await self._save_object(ical, AsyncEvent, **kwargs)

    async def save_todo(
        self,
        ical: Optional[str] = None,
        **kwargs
    ) -> "AsyncTodo":
        """
        Save a todo to this calendar.

        Args:
            ical: iCalendar data as string

        Returns:
            AsyncTodo object
        """
        from .async_objects import AsyncTodo
        return await self._save_object(ical, AsyncTodo, **kwargs)

    async def _save_object(self, ical, obj_class, **kwargs):
        """Helper to save a calendar object"""
        obj = obj_class(client=self.client, data=ical, parent=self, **kwargs)
        await obj.save()
        return obj

    async def event_by_uid(self, uid: str) -> "AsyncEvent":
        """Find an event by UID"""
        from .async_objects import AsyncEvent
        log.debug(f"[EVENT_BY_UID DEBUG] Searching for event with UID: {uid}")
        results = await self.search(comp_class=AsyncEvent)
        log.debug(f"[EVENT_BY_UID DEBUG] Search returned {len(results)} events")
        for event in results:
            log.debug(f"[EVENT_BY_UID DEBUG] Comparing event.id='{event.id}' with uid='{uid}'")
            if event.id == uid:
                log.debug(f"[EVENT_BY_UID DEBUG] Match found!")
                return event
        log.error(f"[EVENT_BY_UID DEBUG] No match found. Available UIDs: {[e.id for e in results]}")
        raise Exception(f"Event with UID {uid} not found")

    async def todo_by_uid(self, uid: str) -> "AsyncTodo":
        """Find a todo by UID"""
        from .async_objects import AsyncTodo
        results = await self.search(comp_class=AsyncTodo)
        for todo in results:
            if todo.id == uid:
                return todo
        raise Exception(f"Todo with UID {uid} not found")
