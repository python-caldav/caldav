"""
I'm trying to be consistent with the terminology in the RFCs:

CalendarSet is a collection of Calendars
Calendar is a collection of CalendarObjectResources
Principal is not a collection, but holds a CalendarSet.

There are also some Mailbox classes to deal with RFC6638.

A SynchronizableCalendarObjectCollection contains a local copy of objects from a calendar on the server.
"""

import logging
import uuid
import warnings
from datetime import datetime
from time import sleep
from typing import TYPE_CHECKING, Any, Optional, TypeVar
from urllib.parse import ParseResult, SplitResult, quote, unquote

import icalendar

try:
    from typing import Optional

    TimeStamp = Optional[date | datetime]
except:
    pass

if TYPE_CHECKING:
    from icalendar import vCalAddress

    from .davclient import DAVClient
    from .search import CalDAVSearcher

from collections.abc import Iterable, Iterator, Sequence
from typing import Literal

from .calendarobjectresource import (
    CalendarObjectResource,
    Event,
    FreeBusy,
    Journal,
    Todo,
)
from .davobject import DAVObject
from .elements import cdav, dav
from .lib import error, vcal
from .lib.python_utilities import to_wire
from .lib.url import URL

_CC = TypeVar("_CC", bound="CalendarObjectResource")
log = logging.getLogger("caldav")


class CalendarSet(DAVObject):
    """
    A CalendarSet is a set of calendars.
    """

    def get_calendars(self) -> list["Calendar"]:
        """
        List all calendar collections in this set.

        For sync clients, returns a list of Calendar objects directly.
        For async clients, returns a coroutine that must be awaited.

        Returns:
         * [Calendar(), ...]

        Example (sync):
            calendars = calendar_set.get_calendars()

        Example (async):
            calendars = await calendar_set.get_calendars()
        """
        # Delegate to client for dual-mode support
        if self.is_async_client:
            return self._async_calendars()

        cals = []
        data = self.children(cdav.Calendar.tag)
        for c_url, c_type, c_name in data:
            try:
                cal_id = c_url.split("/")[-2]
                if not cal_id:
                    continue
            except Exception:
                log.error(f"Calendar {c_name} has unexpected url {c_url}")
                cal_id = None
            cals.append(Calendar(self.client, id=cal_id, url=c_url, parent=self, name=c_name))

        return cals

    async def _async_calendars(self) -> list["Calendar"]:
        """Async implementation of calendars() using the client."""
        from caldav.operations.base import _is_calendar_resource as is_calendar_resource
        from caldav.operations.calendarset_ops import (
            _extract_calendar_id_from_url as extract_calendar_id_from_url,
        )

        # Fetch calendars via PROPFIND
        response = await self.client.propfind(
            str(self.url),
            props=[
                "{DAV:}resourcetype",
                "{DAV:}displayname",
                "{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set",
                "{http://apple.com/ns/ical/}calendar-color",
                "{http://calendarserver.org/ns/}getctag",
            ],
            depth=1,
        )

        # Process results to extract calendars
        calendars = []
        for result in response.results or []:
            # Check if this is a calendar resource
            if not is_calendar_resource(result.properties):
                continue

            # Extract calendar info
            url = result.href
            name = result.properties.get("{DAV:}displayname")
            cal_id = extract_calendar_id_from_url(url)

            if not cal_id:
                continue

            cal = Calendar(
                client=self.client,
                url=url,
                name=name,
                id=cal_id,
                parent=self,
            )
            calendars.append(cal)

        return calendars

    def calendars(self) -> list["Calendar"]:
        """
        Deprecated: Use :meth:`get_calendars` instead.

        This method is an alias kept for backwards compatibility.
        """
        return self.get_calendars()

    def make_calendar(
        self,
        name: str | None = None,
        cal_id: str | None = None,
        supported_calendar_component_set: Any | None = None,
        method: str | None = None,
    ) -> "Calendar":
        """
        Utility method for creating a new calendar.

        Args:
          name: the display name of the new calendar
          cal_id: the uuid of the new calendar
          supported_calendar_component_set: what kind of objects
           (EVENT, VTODO, VFREEBUSY, VJOURNAL) the calendar should handle.
           Should be set to ['VTODO'] when creating a task list in Zimbra -
           in most other cases the default will be OK.
          method: 'mkcalendar' or 'mkcol' - usually auto-detected

        For async clients, returns a coroutine that must be awaited.

        Returns:
          Calendar(...)-object
        """
        if self.is_async_client:
            return self._async_make_calendar(name, cal_id, supported_calendar_component_set, method)

        return Calendar(
            self.client,
            name=name,
            parent=self,
            id=cal_id,
            supported_calendar_component_set=supported_calendar_component_set,
        ).save(method=method)

    async def _async_make_calendar(
        self,
        name: str | None = None,
        cal_id: str | None = None,
        supported_calendar_component_set: Any | None = None,
        method: str | None = None,
    ) -> "Calendar":
        """Async implementation of make_calendar."""
        calendar = Calendar(
            self.client,
            name=name,
            parent=self,
            id=cal_id,
            supported_calendar_component_set=supported_calendar_component_set,
        )
        return await calendar._async_save(method=method)

    def calendar(self, name: str | None = None, cal_id: str | None = None) -> "Calendar":
        """
        The calendar method will return a calendar object.  If it gets a cal_id
        but no name, it will not initiate any communication with the server

        Args:
          name: return the calendar with this display name
          cal_id: return the calendar with this calendar id or URL

        Returns:
          Calendar(...)-object
        """
        # For name-based lookup, use calendars() which already uses async delegation
        if name and not cal_id:
            for calendar in self.get_calendars():
                display_name = calendar.get_display_name()
                if display_name == name:
                    return calendar
        if name and not cal_id:
            raise error.NotFoundError(f"No calendar with name {name} found under {self.url}")
        if not cal_id and not name:
            cals = self.get_calendars()
            if not cals:
                raise error.NotFoundError("no calendars found")
            return cals[0]

        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        if cal_id is None:
            raise ValueError("Unexpected value None for cal_id")

        if str(URL.objectify(cal_id).canonical()).startswith(str(self.client.url.canonical())):
            url = self.client.url.join(cal_id)
        elif isinstance(cal_id, URL) or (
            isinstance(cal_id, str)
            and (cal_id.startswith("https://") or cal_id.startswith("http://"))
        ):
            if self.url is None:
                raise ValueError("Unexpected value None for self.url")

            url = self.url.join(cal_id)
        else:
            if self.url is None:
                raise ValueError("Unexpected value None for self.url")

            if cal_id is None:
                raise ValueError("Unexpected value None for cal_id")

            url = self.url.join(quote(cal_id) + "/")

        return Calendar(self.client, name=name, parent=self, url=url, id=cal_id)


class Principal(DAVObject):
    """
    This class represents a DAV Principal. It doesn't do much, except
    keep track of the URLs for the calendar-home-set, etc.

    A principal MUST have a non-empty DAV:displayname property
    (defined in Section 13.2 of [RFC2518]),
    and a DAV:resourcetype property (defined in Section 13.9 of [RFC2518]).
    Additionally, a principal MUST report the DAV:principal XML element
    in the value of the DAV:resourcetype property.

    (TODO: the resourcetype is actually never checked, and the DisplayName
    is not stored anywhere)
    """

    def __init__(
        self,
        client: Optional["DAVClient"] = None,
        url: str | ParseResult | SplitResult | URL | None = None,
        calendar_home_set: URL | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Returns a Principal.

        End-users usually shouldn't need to construct Principal-objects directly.  Use davclient.principal() to get the principal object of the logged-in user  and davclient.principals() to get other principals.

        Args:
          client: a DAVClient() object
          url: The URL, if known.
          calendar_home_set: the calendar home set, if known

        If url is not given, deduct principal path as well as calendar home set
        path from doing propfinds.
        """
        self._calendar_home_set = calendar_home_set

        super(Principal, self).__init__(client=client, url=url, **kwargs)
        if url is None:
            if self.client is None:
                raise ValueError("Unexpected value None for self.client")

            self.url = self.client.url
            cup = self.get_property(dav.CurrentUserPrincipal())

            if cup is None:
                log.warning("calendar server lacking a feature:")
                log.warning("current-user-principal property not found")
                log.warning("assuming %s is the principal URL" % self.client.url)

            self.url = self.client.url.join(URL.objectify(cup))

    @classmethod
    async def create(
        cls,
        client: "DAVClient",
        url: str | ParseResult | SplitResult | URL | None = None,
        calendar_home_set: URL | None = None,
    ) -> "Principal":
        """
        Create a Principal, discovering URL if not provided.

        This is the recommended way to create a Principal with async clients
        as it handles async URL discovery.

        For sync clients, you can use the regular constructor: Principal(client)

        Args:
            client: A DAVClient or AsyncDAVClient instance
            url: The principal URL (if known)
            calendar_home_set: The calendar home set URL (if known)

        Returns:
            Principal with URL discovered if not provided

        Example (async):
            principal = await Principal.create(async_client)
        """
        # Create principal without URL discovery (pass url even if None to skip sync discovery)
        principal = cls(
            client=client,
            url=url or client.url,
            calendar_home_set=calendar_home_set,
        )

        if url is None:
            # Async URL discovery
            cup = await principal._async_get_property(dav.CurrentUserPrincipal())
            if cup is None:
                log.warning("calendar server lacking a feature:")
                log.warning("current-user-principal property not found")
                log.warning(f"assuming {client.url} is the principal URL")
            else:
                principal.url = client.url.join(URL.objectify(cup))

        return principal

    async def _async_get_property(self, prop):
        """Async version of get_property for use with async clients."""
        if self.url is None:
            raise ValueError("Unexpected value None for self.url")

        response = await self.client.propfind(
            str(self.url),
            props=[prop.tag if hasattr(prop, "tag") else str(prop)],
            depth=0,
        )

        if response.results:
            for result in response.results:
                value = result.properties.get(prop.tag if hasattr(prop, "tag") else str(prop))
                if value is not None:
                    return value
        return None

    def make_calendar(
        self,
        name: str | None = None,
        cal_id: str | None = None,
        supported_calendar_component_set: Any | None = None,
        method=None,
    ) -> "Calendar":
        """
        Convenience method, bypasses the self.calendar_home_set object.
        See CalendarSet.make_calendar for details.

        For async clients, returns a coroutine that must be awaited.
        """
        if self.is_async_client:
            return self._async_make_calendar(name, cal_id, supported_calendar_component_set, method)

        return self.calendar_home_set.make_calendar(
            name,
            cal_id,
            supported_calendar_component_set=supported_calendar_component_set,
            method=method,
        )

    async def _async_make_calendar(
        self,
        name: str | None = None,
        cal_id: str | None = None,
        supported_calendar_component_set: Any | None = None,
        method=None,
    ) -> "Calendar":
        """Async implementation of make_calendar."""
        calendar_home_set = await self._async_get_calendar_home_set()
        return await calendar_home_set._async_make_calendar(
            name,
            cal_id,
            supported_calendar_component_set=supported_calendar_component_set,
            method=method,
        )

    async def _async_get_calendar_home_set(self) -> "CalendarSet":
        """Async helper to get the calendar home set."""
        if self._calendar_home_set:
            return self._calendar_home_set

        calendar_home_set_url = await self._async_get_property(cdav.CalendarHomeSet())
        if (
            calendar_home_set_url is not None
            and "@" in calendar_home_set_url
            and "://" not in calendar_home_set_url
        ):
            calendar_home_set_url = quote(calendar_home_set_url)
        self.calendar_home_set = calendar_home_set_url
        return self._calendar_home_set

    def calendar(
        self,
        name: str | None = None,
        cal_id: str | None = None,
        cal_url: str | None = None,
    ) -> "Calendar":
        """
        The calendar method will return a calendar object.
        It will not initiate any communication with the server.
        """
        if not cal_url:
            return self.calendar_home_set.calendar(name, cal_id)
        else:
            if self.client is None:
                raise ValueError("Unexpected value None for self.client")

            return Calendar(self.client, url=self.client.url.join(cal_url))

    def get_vcal_address(self) -> "vCalAddress":
        """
        Returns the principal, as an icalendar.vCalAddress object.
        """
        from icalendar import vCalAddress, vText

        cn = self.get_display_name()
        ids = self.calendar_user_address_set()
        cutype = self.get_property(cdav.CalendarUserType())
        ret = vCalAddress(ids[0])
        ret.params["cn"] = vText(cn)
        ret.params["cutype"] = vText(cutype)
        return ret

    @property
    def calendar_home_set(self):
        if not self._calendar_home_set:
            calendar_home_set_url = self.get_property(cdav.CalendarHomeSet())
            ## owncloud returns /remote.php/dav/calendars/tobixen@e.email/
            ## in that case the @ should be quoted.  Perhaps other
            ## implementations return already quoted URLs.  Hacky workaround:
            if (
                calendar_home_set_url is not None
                and "@" in calendar_home_set_url
                and "://" not in calendar_home_set_url
            ):
                calendar_home_set_url = quote(calendar_home_set_url)
            self.calendar_home_set = calendar_home_set_url
        return self._calendar_home_set

    @calendar_home_set.setter
    def calendar_home_set(self, url) -> None:
        if isinstance(url, CalendarSet):
            self._calendar_home_set = url
            return
        sanitized_url = URL.objectify(url)
        ## TODO: sanitized_url should never be None, this needs more
        ## research.  added here as it solves real-world issues, ref
        ## https://github.com/python-caldav/caldav/pull/56
        if sanitized_url is not None:
            if sanitized_url.hostname and sanitized_url.hostname != self.client.url.hostname:
                # icloud (and others?) having a load balanced system,
                # where each principal resides on one named host
                ## TODO:
                ## Here be dragons.  sanitized_url will be the root
                ## of all future objects derived from client.  Changing
                ## the client.url root by doing a principal.get_calendars()
                ## is an unacceptable side effect and may be a cause of
                ## incompatibilities with icloud.  Do more research!
                self.client.url = sanitized_url
        self._calendar_home_set = CalendarSet(self.client, self.client.url.join(sanitized_url))

    def get_calendars(self) -> list["Calendar"]:
        """
        Return the principal's calendars.

        For sync clients, returns a list of Calendar objects directly.
        For async clients, returns a coroutine that must be awaited.

        Example (sync):
            calendars = principal.get_calendars()

        Example (async):
            calendars = await principal.get_calendars()
        """
        # Delegate to client for dual-mode support
        return self.client.get_calendars(self)

    def calendars(self) -> list["Calendar"]:
        """
        Deprecated: Use :meth:`get_calendars` instead.

        This method is an alias kept for backwards compatibility.
        """
        return self.get_calendars()

    def freebusy_request(self, dtstart, dtend, attendees):
        """Sends a freebusy-request for some attendee to the server
        as per RFC6638.
        """

        freebusy_ical = icalendar.Calendar()
        freebusy_ical.add("prodid", "-//tobixen/python-caldav//EN")
        freebusy_ical.add("version", "2.0")
        freebusy_ical.add("method", "REQUEST")
        uid = uuid.uuid1()
        freebusy_comp = icalendar.FreeBusy()
        freebusy_comp.add("uid", uid)
        freebusy_comp.add("dtstamp", datetime.now())
        freebusy_comp.add("dtstart", dtstart)
        freebusy_comp.add("dtend", dtend)
        freebusy_ical.add_component(freebusy_comp)
        outbox = self.schedule_outbox()
        caldavobj = FreeBusy(data=freebusy_ical, parent=outbox)
        caldavobj.add_organizer()
        for attendee in attendees:
            caldavobj.add_attendee(attendee, no_default_parameters=True)

        response = self.client.post(
            outbox.url,
            caldavobj.data,
            headers={"Content-Type": "text/calendar; charset=utf-8"},
        )
        return response._find_objects_and_props()

    def calendar_user_address_set(self) -> list[str | None]:
        """
        defined in RFC6638
        """
        _addresses: _Element | None = self.get_property(
            cdav.CalendarUserAddressSet(), parse_props=False
        )

        if _addresses is None:
            raise error.NotFoundError("No calendar user addresses given from server")

        assert not [x for x in _addresses if x.tag != dav.Href().tag]
        addresses = list(_addresses)
        ## possibly the preferred attribute is iCloud-specific.
        ## TODO: do more research on that
        addresses.sort(key=lambda x: -int(x.get("preferred", 0)))
        return [x.text for x in addresses]

    def schedule_inbox(self) -> "ScheduleInbox":
        """
        Returns the schedule inbox, as defined in RFC6638
        """
        return ScheduleInbox(principal=self)

    def schedule_outbox(self) -> "ScheduleOutbox":
        """
        Returns the schedule outbox, as defined in RFC6638
        """
        return ScheduleOutbox(principal=self)


class Calendar(DAVObject):
    """
    The `Calendar` object is used to represent a calendar collection.
    Refer to the RFC for details:
    https://tools.ietf.org/html/rfc4791#section-5.3.1
    """

    def __init__(
        self,
        client: Optional["DAVClient"] = None,
        url: str | ParseResult | SplitResult | URL | None = None,
        parent: Optional["DAVObject"] = None,
        name: str | None = None,
        id: str | None = None,
        props=None,
        **extra,
    ) -> None:
        """
        Initialize a Calendar object.

        Args:
            client: A DAVClient instance
            url: The url for this calendar. May be a full URL or a relative URL.
            parent: The parent object (typically a CalendarSet or Principal)
            name: The display name for the calendar (stored in props cache)
            id: The calendar id (used when creating new calendars)
            props: A dict with known properties for this calendar
        """
        super().__init__(
            client=client, url=url, parent=parent, id=id, props=props, name=name, **extra
        )

    def _create(
        self, name=None, id=None, supported_calendar_component_set=None, method=None
    ) -> None:
        """
        Create a new calendar with display name `name` in `parent`.

        For async clients, returns a coroutine that must be awaited.
        """
        if self.is_async_client:
            return self._async_create(name, id, supported_calendar_component_set, method)

        if id is None:
            id = str(uuid.uuid1())
        self.id = id

        if method is None:
            if self.client:
                supported = self.client.features.is_supported("create-calendar", return_type=dict)
                if supported["support"] not in ("full", "fragile", "quirk"):
                    raise error.MkcalendarError(
                        "Creation of calendars (allegedly) not supported on this server"
                    )
                if supported["support"] == "quirk" and supported["behaviour"] == "mkcol-required":
                    method = "mkcol"
                else:
                    method = "mkcalendar"
            else:
                method = "mkcalendar"

        path = self.parent.url.join(id + "/")
        self.url = path

        # TODO: mkcalendar seems to ignore the body on most servers?
        # at least the name doesn't get set this way.
        # zimbra gives 500 (!) if body is omitted ...

        prop = dav.Prop()
        if name:
            display_name = dav.DisplayName(name)
            prop += [
                display_name,
            ]
        if supported_calendar_component_set:
            sccs = cdav.SupportedCalendarComponentSet()
            for scc in supported_calendar_component_set:
                sccs += cdav.Comp(scc)
            prop += sccs
        if method == "mkcol":
            prop += dav.ResourceType() + [dav.Collection(), cdav.Calendar()]

        set = dav.Set() + prop

        mkcol = (dav.Mkcol() if method == "mkcol" else cdav.Mkcalendar()) + set

        r = self._query(root=mkcol, query_method=method, url=path, expected_return_value=201)

        # Some servers (e.g. GMX) use an internal canonical URL that
        # differs from the client-constructed URL (e.g. UUID-based path
        # vs username-based path).  Discover the server's canonical URL.
        try:
            # Check Location/Content-Location header first (standard mechanism)
            location = r.headers.get("Location") or r.headers.get("Content-Location")
            if location:
                server_url = self.client.url.join(location)
                if server_url.canonical() != path.canonical():
                    log.debug("MKCALENDAR Location header gives canonical URL: %s", server_url)
                    self.url = server_url
            else:
                # List parent's children and find our calendar by cal_id or name
                name_match = None
                for child_url, child_type, child_name in self.parent.children(cdav.Calendar.tag):
                    child_url_str = str(child_url)
                    # Best match: cal_id found in URL
                    if id and id in child_url_str:
                        server_url = self.client.url.join(child_url)
                        if server_url.canonical() != path.canonical():
                            log.debug("Canonical calendar URL (by id): %s", server_url)
                            self.url = server_url
                        name_match = None
                        break
                    # Fallback: match by display name (less reliable)
                    if name and child_name == name and name_match is None:
                        name_match = child_url
                if name_match is not None:
                    server_url = self.client.url.join(name_match)
                    if server_url.canonical() != path.canonical():
                        log.debug("Canonical calendar URL (by name): %s", server_url)
                        self.url = server_url
        except Exception:
            log.debug("Could not discover canonical calendar URL", exc_info=True)

        # COMPATIBILITY ISSUE
        # name should already be set, but we've seen caldav servers failing
        # on setting the DisplayName on calendar creation
        # (DAViCal, Zimbra, ...).  Doing an attempt on explicitly setting the
        # display name using PROPPATCH.
        if name:
            try:
                self.set_properties([display_name])
            except Exception:
                ## TODO: investigate.  Those asserts break.
                try:
                    current_display_name = self.get_display_name()
                    error.assert_(current_display_name == name)
                except:
                    log.warning(
                        "calendar server does not support display name on calendar?  Ignoring",
                        exc_info=True,
                    )

    async def _async_create(
        self, name=None, id=None, supported_calendar_component_set=None, method=None
    ) -> None:
        """Async implementation of _create."""
        if id is None:
            id = str(uuid.uuid1())
        self.id = id

        if method is None:
            if self.client:
                supported = self.client.features.is_supported("create-calendar", return_type=dict)
                if supported["support"] not in ("full", "fragile", "quirk"):
                    raise error.MkcalendarError(
                        "Creation of calendars (allegedly) not supported on this server"
                    )
                if supported["support"] == "quirk" and supported["behaviour"] == "mkcol-required":
                    method = "mkcol"
                else:
                    method = "mkcalendar"
            else:
                method = "mkcalendar"

        path = self.parent.url.join(id + "/")
        self.url = path

        prop = dav.Prop()
        if name:
            display_name = dav.DisplayName(name)
            prop += [
                display_name,
            ]
        if supported_calendar_component_set:
            sccs = cdav.SupportedCalendarComponentSet()
            for scc in supported_calendar_component_set:
                sccs += cdav.Comp(scc)
            prop += sccs
        if method == "mkcol":
            prop += dav.ResourceType() + [dav.Collection(), cdav.Calendar()]

        set = dav.Set() + prop

        mkcol = (dav.Mkcol() if method == "mkcol" else cdav.Mkcalendar()) + set

        r = await self._async_query(
            root=mkcol, query_method=method, url=path, expected_return_value=201
        )

        # Discover canonical URL (see sync _create for detailed comments)
        try:
            location = r.headers.get("Location") or r.headers.get("Content-Location")
            if location:
                server_url = self.client.url.join(location)
                if server_url.canonical() != path.canonical():
                    log.debug("MKCALENDAR Location header gives canonical URL: %s", server_url)
                    self.url = server_url
            else:
                name_match = None
                propfind = await self._async_query(depth=1, url=self.parent.url)
                for result in propfind.results or []:
                    result_href = result.href
                    if id and id in result_href:
                        server_url = self.client.url.join(result_href)
                        if server_url.canonical() != path.canonical():
                            log.debug("Canonical calendar URL (by id): %s", server_url)
                            self.url = server_url
                        name_match = None
                        break
                    result_name = result.properties.get("{DAV:}displayname")
                    if name and result_name == name and name_match is None:
                        name_match = result_href
                if name_match is not None:
                    server_url = self.client.url.join(name_match)
                    if server_url.canonical() != path.canonical():
                        log.debug("Canonical calendar URL (by name): %s", server_url)
                        self.url = server_url
        except Exception:
            log.debug("Could not discover canonical calendar URL", exc_info=True)

        # COMPATIBILITY ISSUE - try to set display name explicitly
        if name:
            try:
                await self._async_set_properties([display_name])
            except Exception:
                try:
                    current_display_name = await self._async_get_property(dav.DisplayName())
                    error.assert_(current_display_name == name)
                except:
                    log.warning(
                        "calendar server does not support display name on calendar?  Ignoring",
                        exc_info=True,
                    )

    def delete(self):
        """Delete the calendar.

        For async clients, returns a coroutine that must be awaited.
        """
        if self.is_async_client:
            return self._async_calendar_delete()

        ## TODO: remove quirk handling from the functional tests
        ## TODO: this needs test code
        quirk_info = self.client.features.is_supported("delete-calendar", dict)
        wipe = not self.client.features.is_supported("delete-calendar")
        if quirk_info["support"] == "fragile":
            ## Do some retries on deleting the calendar
            for x in range(0, 20):
                try:
                    super().delete()
                except error.DeleteError:
                    pass
                try:
                    x = self.get_events()
                    sleep(0.3)
                except error.NotFoundError:
                    wipe = False
                    break

        if wipe:
            for x in self.search():
                x.delete()
        else:
            super().delete()

    async def _async_calendar_delete(self):
        """Async implementation of Calendar.delete()."""
        import asyncio

        quirk_info = self.client.features.is_supported("delete-calendar", dict)
        wipe = not self.client.features.is_supported("delete-calendar")

        if quirk_info["support"] == "fragile":
            # Do some retries on deleting the calendar
            for _ in range(0, 20):
                try:
                    await self._async_delete()
                except error.DeleteError:
                    pass
                try:
                    await self.search(event=True)
                    await asyncio.sleep(0.3)
                except error.NotFoundError:
                    wipe = False
                    break

        if wipe:
            for obj in await self.search():
                await obj._async_delete()
        else:
            await self._async_delete()

    def get_supported_components(self) -> list[Any]:
        """
        returns a list of component types supported by the calendar, in
        string format (typically ['VJOURNAL', 'VTODO', 'VEVENT'])
        """
        if self.url is None:
            raise ValueError("Unexpected value None for self.url")

        props = [cdav.SupportedCalendarComponentSet()]
        response = self.get_properties(props, parse_response_xml=False)

        # Use protocol layer results if available
        if response.results:
            for result in response.results:
                components = result.properties.get(cdav.SupportedCalendarComponentSet().tag)
                if components:
                    return components
            return []

        # Fallback for mocked responses without protocol parsing
        response_list = response._find_objects_and_props()
        prop = response_list[unquote(self.url.path)][cdav.SupportedCalendarComponentSet().tag]
        return [supported.get("name") for supported in prop]

    def save_with_invites(self, ical: str, attendees, **attendeeoptions) -> None:
        """
        sends a schedule request to the server.  Equivalent with add_event, add_todo, etc,
        but the attendees will be added to the ical object before sending it to the server.
        """
        ## TODO: consolidate together with save_*
        obj = self._calendar_comp_class_by_data(ical)(data=ical, client=self.client)
        obj.parent = self
        obj.add_organizer()
        for attendee in attendees:
            obj.add_attendee(attendee, **attendeeoptions)
        obj.id = obj.icalendar_instance.walk("vevent")[0]["uid"]
        obj.save()
        return obj

    def _use_or_create_ics(self, ical, objtype, **ical_data):
        if ical_data or (
            (isinstance(ical, str) or isinstance(ical, bytes))
            and b"BEGIN:VCALENDAR" not in to_wire(ical)
        ):
            ## TODO: the ical_fragment code is not much tested
            if ical and "ical_fragment" not in ical_data:
                ical_data["ical_fragment"] = ical
            return vcal.create_ical(objtype=objtype, **ical_data)
        return ical

    def add_object(
        self,
        ## TODO: this should be made optional.  The class may be given in the ical object.
        ## TODO: also, accept a string.
        objclass: type[DAVObject],
        ## TODO: ical may also be a vobject or icalendar instance
        ical: str | None = None,
        no_overwrite: bool = False,
        no_create: bool = False,
        **ical_data,
    ) -> "CalendarResourceObject":
        """Add a new calendar object (event, todo, journal) to the calendar.

        This method is for adding new content to the calendar.  To update
        an existing object, fetch it first and use ``object.save()``.

        Args:
          objclass: Event, Journal or Todo
          ical: ical object (text, icalendar or vobject instance)
          no_overwrite: existing calendar objects should not be overwritten
          no_create: don't create a new object, existing calendar objects should be updated
          dtstart: properties to be inserted into the icalendar object
          dtend: properties to be inserted into the icalendar object
          summary: properties to be inserted into the icalendar object
          alarm_trigger: when given, one alarm will be added
          alarm_action: when given, one alarm will be added
          alarm_attach: when given, one alarm will be added

        Note that the list of parameters going into the icalendar
        object and alarms is not complete.  Refer to the RFC or the
        icalendar library for a full list of properties.
        """
        o = objclass(
            self.client,
            data=self._use_or_create_ics(
                ical, objtype=f"V{objclass.__name__.upper()}", **ical_data
            ),
            parent=self,
        )
        o = o.save(no_overwrite=no_overwrite, no_create=no_create)
        ## TODO: Saving nothing is currently giving an object with None as URL.
        ## This should probably be changed in some future version to raise an error
        ## See also CalendarObjectResource.save()
        if o.url is not None:
            o._handle_reverse_relations(fix=True)
        return o

    def add_event(self, *largs, **kwargs) -> "Event":
        """
        Add an event to the calendar.

        Returns ``self.add_object(Event, ...)`` - see :meth:`add_object`
        """
        return self.add_object(Event, *largs, **kwargs)

    def add_todo(self, *largs, **kwargs) -> "Todo":
        """
        Add a todo/task to the calendar.

        Returns ``self.add_object(Todo, ...)`` - see :meth:`add_object`
        """
        return self.add_object(Todo, *largs, **kwargs)

    def add_journal(self, *largs, **kwargs) -> "Journal":
        """
        Add a journal entry to the calendar.

        Returns ``self.add_object(Journal, ...)`` - see :meth:`add_object`
        """
        return self.add_object(Journal, *largs, **kwargs)

    ## Deprecated aliases - use add_* instead
    ## These will be removed in a future version

    def save_object(self, *largs, **kwargs) -> "CalendarResourceObject":
        """
        Deprecated: Use :meth:`add_object` instead.

        This method is an alias kept for backwards compatibility.
        See https://github.com/python-caldav/caldav/issues/71
        """
        return self.add_object(*largs, **kwargs)

    def save_event(self, *largs, **kwargs) -> "Event":
        """
        Deprecated: Use :meth:`add_event` instead.

        This method is an alias kept for backwards compatibility.
        See https://github.com/python-caldav/caldav/issues/71
        """
        return self.add_event(*largs, **kwargs)

    def save_todo(self, *largs, **kwargs) -> "Todo":
        """
        Deprecated: Use :meth:`add_todo` instead.

        This method is an alias kept for backwards compatibility.
        See https://github.com/python-caldav/caldav/issues/71
        """
        return self.add_todo(*largs, **kwargs)

    def save_journal(self, *largs, **kwargs) -> "Journal":
        """
        Deprecated: Use :meth:`add_journal` instead.

        This method is an alias kept for backwards compatibility.
        See https://github.com/python-caldav/caldav/issues/71
        """
        return self.add_journal(*largs, **kwargs)

    def save(self, method=None):
        """
        The save method for a calendar is only used to create it, for now.
        We know we have to create it when we don't have a url.

        For async clients, returns a coroutine that must be awaited.

        Returns:
         * self
        """
        if self.is_async_client:
            return self._async_save(method)

        if self.url is None:
            # Get display name from props cache
            display_name = self.props.get("{DAV:}displayname")
            self._create(id=self.id, name=display_name, method=method, **self.extra_init_options)
        return self

    async def _async_save(self, method=None):
        """Async implementation of save."""
        if self.url is None:
            # Get display name from props cache
            display_name = self.props.get("{DAV:}displayname")
            await self._async_create(
                name=display_name, id=self.id, method=method, **self.extra_init_options
            )
        return self

    # def data2object_class

    def _multiget(self, event_urls: Iterable[URL], raise_notfound: bool = False) -> Iterable[str]:
        """
        get multiple events' data.
        TODO: Does it overlap the _request_report_build_resultlist method
        """
        if self.url is None:
            raise ValueError("Unexpected value None for self.url")

        rv = []
        prop = dav.Prop() + cdav.CalendarData()
        root = cdav.CalendarMultiGet() + prop + [dav.Href(value=u.path) for u in event_urls]
        # RFC 4791 section 7.9: "the 'Depth' header MUST be ignored by the
        # server and SHOULD NOT be sent by the client" for calendar-multiget
        response = self._query(root, None, "report")
        results = response.expand_simple_props([cdav.CalendarData()])
        if raise_notfound:
            for href in response.statuses:
                status = response.statuses[href]
                if status and "404" in status:
                    raise error.NotFoundError(f"Status {status} in {href}")
        for r in results:
            yield (r, results[r][cdav.CalendarData.tag])

    ## Replace the last lines with
    def multiget(self, event_urls: Iterable[URL], raise_notfound: bool = False) -> Iterable[_CC]:
        """
        get multiple events' data
        TODO: Does it overlap the _request_report_build_resultlist method?
        @author mtorange@gmail.com (refactored by Tobias)
        """
        results = self._multiget(event_urls, raise_notfound=raise_notfound)
        for url, data in results:
            # Quote path to handle servers returning unencoded spaces (e.g., Zimbra)
            quoted_url = quote(unquote(str(url)), safe="/:@")
            yield self._calendar_comp_class_by_data(data)(
                self.client,
                url=self.url.join(quoted_url),
                data=data,
                parent=self,
            )

    def calendar_multiget(self, *largs, **kwargs):
        """
        get multiple events' data
        @author mtorange@gmail.com
        (refactored by Tobias)
        This is for backward compatibility.  It may be removed in 3.0 or later release.
        """
        return list(self.multiget(*largs, **kwargs))

    def date_search(
        self,
        start: datetime,
        end: datetime | None = None,
        compfilter: None = "VEVENT",
        expand: bool | Literal["maybe"] = "maybe",
        verify_expand: bool = False,
    ) -> Sequence["CalendarObjectResource"]:
        # type (TimeStamp, TimeStamp, str, str) -> CalendarObjectResource
        """
        .. deprecated:: 3.0
            Use :meth:`search` instead. This method will be removed in 4.0.

        Search events by date in the calendar.

        Args:
            start: Start of the date range to search.
            end: End of the date range (optional for open-ended search).
            compfilter: Component type to search for. Defaults to "VEVENT".
                Set to None to fetch all calendar components.
            expand: Should recurrent events be expanded? Default "maybe"
                becomes True unless the search is open-ended.
            verify_expand: Not in use anymore, kept for backward compatibility.

        Returns:
            List of CalendarObjectResource objects matching the search.

        Example (migrate to search)::

            # Legacy (deprecated):
            events = calendar.date_search(start, end, expand=True)

            # Recommended:
            events = calendar.search(start=start, end=end, event=True, expand=True)
        """
        ## date_search will be removed in 4.0
        warnings.warn(
            "use `calendar.search rather than `calendar.date_search`",
            DeprecationWarning,
            stacklevel=2,
        )

        if verify_expand:
            logging.warning(
                "verify_expand in date_search does not work anymore, as we're doing client side expansion instead"
            )

        ## for backward compatibility - expand should be false
        ## in an open-ended date search, otherwise true
        if expand == "maybe":
            expand = start is not None and end is not None

        if compfilter == "VEVENT":
            comp_class = Event
        elif compfilter == "VTODO":
            comp_class = Todo
        else:
            comp_class = None

        objects = self.search(
            start=start,
            end=end,
            comp_class=comp_class,
            expand=expand,
            split_expanded=False,
        )

        return objects

    ## TODO: this logic has been partly duplicated in calendar_multiget, but
    ## the code there is much more readable and condensed than this.
    ## Can code below be refactored?
    def _request_report_build_resultlist(
        self, xml, comp_class=None, props=None, no_calendardata=False
    ):
        """
        Takes some input XML, does a report query on a calendar object
        and returns the resource objects found.

        For async clients, returns a coroutine that must be awaited.
        """
        if self.is_async_client:
            return self._async_request_report_build_resultlist(
                xml, comp_class, props, no_calendardata
            )

        matches = []
        if props is None:
            props_ = [cdav.CalendarData()]
        else:
            props_ = [cdav.CalendarData()] + props
        response = self._query(xml, 1, "report")
        results = response.expand_simple_props(props_)
        for r in results:
            pdata = results[r]
            if cdav.CalendarData.tag in pdata:
                cdata = pdata.pop(cdav.CalendarData.tag)
                comp_class_ = (
                    self._calendar_comp_class_by_data(cdata) if comp_class is None else comp_class
                )
            else:
                cdata = None
            if comp_class_ is None:
                ## no CalendarData fetched - which is normal i.e. when doing a sync-token report and only asking for the URLs
                comp_class_ = CalendarObjectResource
            url = URL(r)
            if url.hostname is None:
                # Quote when result is not a full URL
                url = quote(r)
            ## icloud hack - icloud returns the calendar URL as well as the calendar item URLs
            if self.url.join(url) == self.url:
                continue
            matches.append(
                comp_class_(
                    self.client,
                    url=self.url.join(url),
                    data=cdata,
                    parent=self,
                    props=pdata,
                )
            )
        return (response, matches)

    async def _async_request_report_build_resultlist(
        self, xml, comp_class=None, props=None, no_calendardata=False
    ):
        """Async implementation of _request_report_build_resultlist."""
        matches = []
        if props is None:
            props_ = [cdav.CalendarData()]
        else:
            props_ = [cdav.CalendarData()] + props
        response = await self._async_query(xml, 1, "report")
        results = response.expand_simple_props(props_)
        for r in results:
            pdata = results[r]
            if cdav.CalendarData.tag in pdata:
                cdata = pdata.pop(cdav.CalendarData.tag)
                comp_class_ = (
                    self._calendar_comp_class_by_data(cdata) if comp_class is None else comp_class
                )
            else:
                cdata = None
            if comp_class_ is None:
                comp_class_ = CalendarObjectResource
            url = URL(r)
            if url.hostname is None:
                url = quote(r)
            if self.url.join(url) == self.url:
                continue
            matches.append(
                comp_class_(
                    self.client,
                    url=self.url.join(url),
                    data=cdata,
                    parent=self,
                    props=pdata,
                )
            )
        return (response, matches)

    def searcher(self, **searchargs) -> "CalDAVSearcher":
        """Create a searcher object for building complex search queries.

        This is the recommended way to perform advanced searches. The
        returned searcher can have filters added, and then be executed:

        .. code-block:: python

            searcher = calendar.searcher(event=True, start=..., end=...)
            searcher.add_property_filter("SUMMARY", "meeting")
            results = searcher.search()

        For simple searches, use :meth:`search` directly instead.

        :param searchargs: Search parameters (same as for :meth:`search`)
        :return: A CalDAVSearcher bound to this calendar

        See :class:`caldav.search.CalDAVSearcher` for available filter methods.
        """
        from .search import CalDAVSearcher

        my_searcher = CalDAVSearcher()
        my_searcher._calendar = self

        for key in searchargs:
            assert key[0] != "_"  ## not allowed
            alias = key
            if key == "class_":  ## because class is a reserved word
                alias = "class"
            if key == "no_category":
                alias = "no_categories"
            if key == "no_class_":
                alias = "no_class"
            if key == "sort_keys":
                sort_reverse = searchargs.get("sort_reverse", False)
                if isinstance(searchargs["sort_keys"], str):
                    searchargs["sort_keys"] = [searchargs["sort_keys"]]
                for sortkey in searchargs["sort_keys"]:
                    my_searcher.add_sort_key(sortkey, sort_reverse)
            elif key == "sort_reverse":
                pass  # handled with sort_keys
            elif key == "comp_class" or key in my_searcher.__dataclass_fields__:
                setattr(my_searcher, key, searchargs[key])
            elif alias.startswith("no_"):
                my_searcher.add_property_filter(alias[3:], searchargs[key], operator="undef")
            else:
                my_searcher.add_property_filter(alias, searchargs[key])

        return my_searcher

    def search(
        self,
        xml: str = None,
        server_expand: bool = False,
        split_expanded: bool = True,
        sort_reverse: bool = False,
        props: list[cdav.CalendarData] | None = None,
        filters=None,
        post_filter=None,
        _hacks=None,
        **searchargs,
    ) -> list[_CC]:
        """Sends a search request towards the server, processes the
        results if needed and returns the objects found.

        Refactoring 2025-11: a new class
        class:`caldav.search.CalDAVSearcher` has been made, and
        this method is sort of a wrapper for
        CalDAVSearcher.search, ensuring backward
        compatibility.  The documentation may be slightly overlapping.

        I believe that for simple tasks, this method will be easier to
        use than the new interface, hence there are no plans for the
        foreseeable future to deprecate it.  This search method will
        continue working as it has been doing before for all
        foreseeable future.  I believe that for simple tasks, this
        method will be easier to use than to construct a
        CalDAVSearcher object and do searches from there.  The
        refactoring was made necessary because the parameter list to
        `search` was becoming unmanagable.  Advanced searches should
        be done via the new interface.

        Caveat: The searching is done on the server side, the RFC is
        not very crystal clear on many of the corner cases, and
        servers often behave differently when presented with a search
        request.  There is planned work to work around server
        incompatibilities on the client side, but as for now
        complicated searches will give different results on different
        servers.

        ``todo`` - searches explicitly for todo.  Unless
        ``include_completed`` is specified, there is some special
        logic ensuring only pending tasks is returned.

        There is corresponding ``event`` and ``journal`` bools to
        specify that the search should be only for events or journals.
        When neither are set, one should expect to get all objects
        returned - but quite some calendar servers will return
        nothing.  This will be solved client-side in the future, as
        for 2.0 it's recommended to search separately for tasks,
        events and journals to ensure consistent behaviour across
        different calendar servers and providers.

        ``sort_keys`` refers to (case-insensitive) properties in the
        icalendar object, ``sort_reverse`` can also be given.  The
        sorting will be done client-side.

        Use ``start`` and ``end`` for time-range searches.  Open-ended
        searches are supported (i.e. "everything in the future"), but
        it's recommended to use closed ranges (i.e. have an "event
        horizon" of a year and ask for "everything from now and one
        year ahead") and get the data expanded.

        With the boolean ``expand`` set, you don't have to think too
        much about recurrences - they will be expanded, and with the
        (default) ``split_expanded`` set, each recurrence will be
        returned as a separate list object (otherwise all recurrences
        will be put into one ``VCALENDAR`` and returned as one
        ``Event``).  This makes it safe to use the ``event.component``
        property.  The non-expanded resultset may include events where
        the timespan doesn't match the date interval you searched for,
        as well as items with multiple components ("special"
        recurrences), meaning you may need logic on the client side to
        handle the recurrences.  *Only time range searches over closed
        time intervals may be expanded*.

        As for 2.0, the expand-logic is by default done on the
        client-side, for consistent results across various server
        incompabilities.  However, you may force server-side expansion
        by setting ``server_expand=True``

        Text attribute search parameters can be given to query the
        "properties" in the calendar data: category, uid, summary,
        comment, description, location, status.  According to the RFC,
        a substring search should be done.

        You may use no_category, no_summary, etc to search for objects
        that are missing those attributes.

        Negated text matches are not supported yet.

        For power-users, those parameters are also supported:

         * ``xml`` - use this search query, and ignore other filter parameters
         * ``comp_class`` - alternative to the ``event``, ``todo`` or ``journal`` booleans described above.
         * ``filters`` - other kind of filters (in lxml tree format)

        """
        ## Late import to avoid cyclic imports
        from .search import CalDAVSearcher

        ## This is basically a wrapper for CalDAVSearcher.search
        ## The logic below will massage the parameters in ``searchargs``
        ## and put them into the CalDAVSearcher object.

        ## In caldav 1, expand could be set to True, False, "server" or "client".
        ## in caldav 2, the extra argument `server_expand` was introduced
        ## and usage of "server"/"client" was deprecated.
        ## In caldav 3, the support for "server" or "client" will be shedded.
        ## For server-side expansion, set `expand=True, server_expand=True`
        assert isinstance(searchargs.get("expand", True), bool)

        ## Transfer all the arguments to CalDAVSearcher
        my_searcher = CalDAVSearcher()
        for key in searchargs:
            assert key[0] != "_"  ## not allowed
            alias = key
            if key == "class_":  ## because class is a reserved word
                alias = "class"
            if key == "no_category":
                alias = "no_categories"
            if key == "no_class_":
                alias = "no_class"
            if key == "sort_keys":
                if isinstance(searchargs["sort_keys"], str):
                    searchargs["sort_keys"] = [searchargs["sort_keys"]]
                for sortkey in searchargs["sort_keys"]:
                    my_searcher.add_sort_key(sortkey, sort_reverse)
                    continue
            elif key == "comp_class" or key in my_searcher.__dataclass_fields__:
                setattr(my_searcher, key, searchargs[key])
                continue
            elif alias.startswith("no_"):
                my_searcher.add_property_filter(alias[3:], searchargs[key], operator="undef")
            else:
                my_searcher.add_property_filter(alias, searchargs[key])

        if not xml and filters:
            xml = filters

        # For async clients, use async_search
        if self.is_async_client:
            return my_searcher.async_search(
                self, server_expand, split_expanded, props, xml, post_filter, _hacks
            )

        return my_searcher.search(
            self, server_expand, split_expanded, props, xml, post_filter, _hacks
        )

    def freebusy_request(self, start: datetime, end: datetime) -> "FreeBusy":
        """
        Search the calendar, but return only the free/busy information.

        Args:
          start : defaults to datetime.today().
          end : same as above.

        Returns:
          [FreeBusy(), ...]
        """

        root = cdav.FreeBusyQuery() + [cdav.TimeRange(start, end)]
        response = self._query(root, 1, "report")
        return FreeBusy(self, response.raw)

    def get_todos(
        self,
        sort_keys: Sequence[str] = ("due", "priority"),
        include_completed: bool = False,
        sort_key: str | None = None,
    ) -> list["Todo"]:
        """
        Fetches a list of todo items (this is a wrapper around search).

        For sync clients, returns a list of Todo objects directly.
        For async clients, returns a coroutine that must be awaited.

        Args:
          sort_keys: use this field in the VTODO for sorting (iterable of lower case string, i.e. ('priority','due')).
          include_completed: boolean - by default, only pending tasks are listed
          sort_key: DEPRECATED, for backwards compatibility with version 0.4.

        Example (sync):
            todos = calendar.get_todos()

        Example (async):
            todos = await calendar.get_todos()
        """
        if sort_key:
            sort_keys = (sort_key,)

        # Use search() for both sync and async - this ensures any
        # delay decorators applied to search() are respected
        return self.search(todo=True, include_completed=include_completed, sort_keys=sort_keys)

    def todos(self, *largs, **kwargs) -> list["Todo"]:
        """
        Deprecated: Use :meth:`get_todos` instead.

        This method is an alias kept for backwards compatibility.
        """
        return self.get_todos(*largs, **kwargs)

    def _calendar_comp_class_by_data(self, data):
        """
        takes some data, either as icalendar text or icalender object (TODO:
        consider vobject) and returns the appropriate
        CalendarResourceObject child class.
        """
        if data is None:
            ## no data received - we'd need to load it before we can know what
            ## class it really is.  Assign the base class as for now.
            return CalendarObjectResource
        if hasattr(data, "split"):
            for line in data.split("\n"):
                line = line.strip()
                if line == "BEGIN:VEVENT":
                    return Event
                if line == "BEGIN:VTODO":
                    return Todo
                if line == "BEGIN:VJOURNAL":
                    return Journal
                if line == "BEGIN:VFREEBUSY":
                    return FreeBusy
        elif hasattr(data, "subcomponents"):
            if not len(data.subcomponents):
                return CalendarObjectResource

            ical2caldav = {
                icalendar.Event: Event,
                icalendar.Todo: Todo,
                icalendar.Journal: Journal,
                icalendar.FreeBusy: FreeBusy,
            }
            for sc in data.subcomponents:
                if sc.__class__ in ical2caldav:
                    return ical2caldav[sc.__class__]
        return CalendarObjectResource

    def event_by_url(self, href, data: Any | None = None) -> "Event":
        """
        Returns the event with the given URL.
        """
        return Event(url=href, data=data, parent=self).load()

    def get_object_by_uid(
        self,
        uid: str,
        comp_filter: cdav.CompFilter | None = None,
        comp_class: Optional["CalendarObjectResource"] = None,
    ) -> "Event":
        """
        Get one calendar object from the calendar by UID.

        Args:
         uid: the object uid
         comp_class: filter by component type (Event, Todo, Journal)
         comp_filter: for backward compatibility.  Don't use!

        Returns:
         CalendarObjectResource (Event, Todo, or Journal)
        """
        ## late import to avoid cyclic dependencies
        from .search import CalDAVSearcher

        ## 2025-11: some logic validating the comp_filter and
        ## comp_class has been removed, and replaced with the
        ## recommendation not to use comp_filter.  We're still using
        ## comp_filter internally, but it's OK, it doesn't need to be
        ## validated.

        ## Lots of old logic has been removed, the new search logic
        ## can do the things for us:
        searcher = CalDAVSearcher(comp_class=comp_class)
        ## Default is substring
        searcher.add_property_filter("uid", uid, "==")
        items_found = searcher.search(self, xml=comp_filter, _hacks="insist", post_filter=True)

        if not items_found:
            raise error.NotFoundError("%s not found on server" % uid)
        error.assert_(len(items_found) == 1)
        return items_found[0]

    def get_todo_by_uid(self, uid: str) -> "CalendarObjectResource":
        """
        Get a task/todo from the calendar by UID.

        Returns the task with the given uid.
        See :meth:`get_object_by_uid` for more details.
        """
        return self.get_object_by_uid(uid, comp_filter=cdav.CompFilter("VTODO"))

    def get_event_by_uid(self, uid: str) -> "CalendarObjectResource":
        """
        Get an event from the calendar by UID.

        Returns the event with the given uid.
        See :meth:`get_object_by_uid` for more details.
        """
        return self.get_object_by_uid(uid, comp_filter=cdav.CompFilter("VEVENT"))

    def get_journal_by_uid(self, uid: str) -> "CalendarObjectResource":
        """
        Get a journal entry from the calendar by UID.

        Returns the journal with the given uid.
        See :meth:`get_object_by_uid` for more details.
        """
        return self.get_object_by_uid(uid, comp_filter=cdav.CompFilter("VJOURNAL"))

    ## Deprecated aliases - use get_*_by_uid instead

    def object_by_uid(self, *largs, **kwargs) -> "CalendarObjectResource":
        """
        Deprecated: Use :meth:`get_object_by_uid` instead.

        This method is an alias kept for backwards compatibility.
        """
        return self.get_object_by_uid(*largs, **kwargs)

    def event_by_uid(self, uid: str) -> "CalendarObjectResource":
        """
        Deprecated: Use :meth:`get_event_by_uid` instead.

        This method is an alias kept for backwards compatibility.
        """
        return self.get_event_by_uid(uid)

    def todo_by_uid(self, uid: str) -> "CalendarObjectResource":
        """
        Deprecated: Use :meth:`get_todo_by_uid` instead.

        This method is an alias kept for backwards compatibility.
        """
        return self.get_todo_by_uid(uid)

    def journal_by_uid(self, uid: str) -> "CalendarObjectResource":
        """
        Deprecated: Use :meth:`get_journal_by_uid` instead.

        This method is an alias kept for backwards compatibility.
        """
        return self.get_journal_by_uid(uid)

    # alias for backward compatibility
    event = event_by_uid

    def get_events(self) -> list["Event"]:
        """
        List all events from the calendar.

        For sync clients, returns a list of Event objects directly.
        For async clients, returns a coroutine that must be awaited.

        Returns:
         * [Event(), ...]

        Example (sync):
            events = calendar.get_events()

        Example (async):
            events = await calendar.get_events()
        """
        # Use search() for both sync and async - this ensures any
        # delay decorators applied to search() are respected
        return self.search(comp_class=Event)

    def events(self) -> list["Event"]:
        """
        Deprecated: Use :meth:`get_events` instead.

        This method is an alias kept for backwards compatibility.
        """
        return self.get_events()

    def _generate_fake_sync_token(self, objects: list["CalendarObjectResource"]) -> str:
        """
        Generate a fake sync token for servers without sync support.
        Uses a hash of all ETags to detect changes.

        Args:
            objects: List of calendar objects to generate token from

        Returns:
            A fake sync token string
        """
        import hashlib

        etags = []
        for obj in objects:
            if hasattr(obj, "props") and dav.GetEtag.tag in obj.props:
                etags.append(str(obj.props[dav.GetEtag.tag]))
            elif hasattr(obj, "url"):
                ## If no etag, use URL as fallback identifier
                etags.append(str(obj.url.canonical()))
        etags.sort()  ## Consistent ordering
        combined = "|".join(etags)
        hash_value = hashlib.md5(combined.encode()).hexdigest()
        return f"fake-{hash_value}"

    def get_objects_by_sync_token(
        self,
        sync_token: Any | None = None,
        load_objects: bool = False,
        disable_fallback: bool = False,
    ) -> "SynchronizableCalendarObjectCollection":
        """get_objects_by_sync_token aka get_objects

        Do a sync-collection report, ref RFC 6578 and
        https://github.com/python-caldav/caldav/issues/87

        This method will return all objects in the calendar if no
        sync_token is passed (the method should then be referred to as
        "objects"), or if the sync_token is unknown to the server.  If
        a sync-token known by the server is passed, it will return
        objects that are added, deleted or modified since last time
        the sync-token was set.

        If load_objects is set to True, the objects will be loaded -
        otherwise empty CalendarObjectResource objects will be returned.

        This method will return a SynchronizableCalendarObjectCollection object, which is
        an iterable.

        This method transparently falls back to retrieving all objects if the server
        doesn't support sync tokens. The fallback behavior is identical from the user's
        perspective, but less efficient as it transfers the entire calendar on each sync.

        If disable_fallback is set to True, the method will raise an exception instead
        of falling back to retrieving all objects. This is useful for testing whether
        the server truly supports sync tokens.
        """
        ## Check if we should attempt to use sync tokens
        ## (either server supports them, or we haven't checked yet, or this is a fake token)
        use_sync_token = True
        sync_support = self.client.features.is_supported("sync-token", return_type=dict)
        if sync_support.get("support") == "unsupported":
            if disable_fallback:
                raise error.ReportError("Sync tokens are not supported by the server")
            use_sync_token = False
        ## If sync_token looks like a fake token, don't try real sync-collection
        if sync_token and isinstance(sync_token, str) and sync_token.startswith("fake-"):
            use_sync_token = False

        if use_sync_token:
            try:
                cmd = dav.SyncCollection()
                token = dav.SyncToken(value=sync_token)
                level = dav.SyncLevel(value="1")
                props = dav.Prop() + dav.GetEtag()
                root = cmd + [level, token, props]
                (response, objects) = self._request_report_build_resultlist(
                    root, props=[dav.GetEtag()], no_calendardata=True
                )
                ## TODO: look more into this, I think sync_token should be directly available through response object
                try:
                    sync_token = response.sync_token
                except:
                    sync_token = response.tree.findall(".//" + dav.SyncToken.tag)[0].text

                ## this is not quite right - the etag we've fetched can already be outdated
                if load_objects:
                    for obj in objects:
                        try:
                            obj.load()
                        except error.NotFoundError:
                            ## The object was deleted
                            pass
                return SynchronizableCalendarObjectCollection(
                    calendar=self, objects=objects, sync_token=sync_token
                )
            except (error.ReportError, error.DAVError) as e:
                ## Server doesn't support sync tokens or the sync-collection REPORT failed
                if disable_fallback:
                    raise
                log.info(f"Sync-collection REPORT failed ({e}), falling back to full retrieval")
                ## Fall through to fallback implementation

        ## FALLBACK: Server doesn't support sync tokens
        ## Retrieve all objects and emulate sync token behavior
        log.debug("Using fallback sync mechanism (retrieving all objects)")

        ## Use search() to get all objects. search() will include CalendarData by default.
        ## We can't avoid this in the fallback mechanism without significant refactoring.
        all_objects = list(self.search())

        ## Load objects if requested (objects may already have data from search)
        if load_objects:
            for obj in all_objects:
                ## Only load if not already loaded
                if not hasattr(obj, "_data") or obj._data is None:
                    try:
                        obj.load()
                    except error.NotFoundError:
                        pass

        ## Fetch ETags for all objects if not already present
        ## ETags are crucial for detecting changes in the fallback mechanism
        if all_objects and (
            not hasattr(all_objects[0], "props") or dav.GetEtag.tag not in all_objects[0].props
        ):
            ## Use PROPFIND to fetch ETags for all objects
            try:
                ## Do a depth-1 PROPFIND on the calendar to get all ETags
                response = self._query_properties([dav.GetEtag()], depth=1)
                etag_props = response.expand_simple_props([dav.GetEtag()])

                ## Map ETags to objects by URL (using string keys for reliable comparison)
                url_to_obj = {str(obj.url.canonical()): obj for obj in all_objects}
                log.debug(f"Fallback: Fetching ETags for {len(url_to_obj)} objects")
                for url_str, props in etag_props.items():
                    canonical_url_str = str(self.url.join(url_str).canonical())
                    if canonical_url_str in url_to_obj:
                        if not hasattr(url_to_obj[canonical_url_str], "props"):
                            url_to_obj[canonical_url_str].props = {}
                        url_to_obj[canonical_url_str].props.update(props)
                        log.debug(f"Fallback: Added ETag to {canonical_url_str}")
            except Exception as e:
                ## If fetching ETags fails, we'll fall back to URL-based tokens
                ## which can't detect content changes, only additions/deletions
                log.debug(f"Failed to fetch ETags for fallback sync: {e}")
                pass

        ## Generate a fake sync token based on current state
        fake_sync_token = self._generate_fake_sync_token(all_objects)

        ## If a sync_token was provided, check if anything has changed
        if sync_token and isinstance(sync_token, str) and sync_token.startswith("fake-"):
            ## Compare the provided token with the new token
            if sync_token == fake_sync_token:
                ## Nothing has changed, return empty collection
                return SynchronizableCalendarObjectCollection(
                    calendar=self, objects=[], sync_token=fake_sync_token
                )
            ## If tokens differ, return all objects (emulating a full sync)
            ## In a real implementation, we'd return only changed objects,
            ## but that requires storing previous state which we don't have

        return SynchronizableCalendarObjectCollection(
            calendar=self, objects=all_objects, sync_token=fake_sync_token
        )

    def objects_by_sync_token(self, *largs, **kwargs) -> "SynchronizableCalendarObjectCollection":
        """
        Deprecated: Use :meth:`get_objects_by_sync_token` instead.

        This method is an alias kept for backwards compatibility.
        """
        return self.get_objects_by_sync_token(*largs, **kwargs)

    objects = objects_by_sync_token
    get_objects = get_objects_by_sync_token

    def get_journals(self) -> list["Journal"]:
        """
        List all journals from the calendar.

        Returns:
         * [Journal(), ...]
        """
        return self.search(comp_class=Journal)

    def journals(self) -> list["Journal"]:
        """
        Deprecated: Use :meth:`get_journals` instead.

        This method is an alias kept for backwards compatibility.
        """
        return self.get_journals()


class ScheduleMailbox(Calendar):
    """
    RFC6638 defines an inbox and an outbox for handling event scheduling.

    TODO: As ScheduleMailboxes works a bit like calendars, I've chosen
    to inheritate the Calendar class, but this is a bit incorrect, a
    ScheduleMailbox is a collection, but not really a calendar.  We
    should create a common base class for ScheduleMailbox and Calendar
    eventually.
    """

    def __init__(
        self,
        client: Optional["DAVClient"] = None,
        principal: Principal | None = None,
        url: str | ParseResult | SplitResult | URL | None = None,
    ) -> None:
        """
        Will locate the mbox if no url is given
        """
        super(ScheduleMailbox, self).__init__(client=client, url=url)
        self._items = None
        if not client and principal:
            self.client = principal.client
        if not principal and client:
            if self.client is None:
                raise ValueError("Unexpected value None for self.client")

            principal = self.client.principal
        if url is not None:
            if client is None:
                raise ValueError("Unexpected value None for client")

            self.url = client.url.join(URL.objectify(url))
        else:
            if principal is None:
                raise ValueError("Unexpected value None for principal")

            if self.client is None:
                raise ValueError("Unexpected value None for self.client")

            self.url = principal.url
            try:
                # we ignore the type here as this is defined in sub-classes only; require more changes to
                # properly fix in a future revision
                self.url = self.client.url.join(URL(self.get_property(self.findprop())))  # type: ignore
            except:
                logging.error("something bad happened", exc_info=True)
                error.assert_(self.client.check_scheduling_support())
                self.url = None
                # we ignore the type here as this is defined in sub-classes only; require more changes to
                # properly fix in a future revision
                raise error.NotFoundError(
                    "principal has no %s.  %s" % (str(self.findprop()), error.ERR_FRAGMENT)  # type: ignore
                )

    def get_items(self):
        """
        TODO: work in progress
        TODO: perhaps this belongs to the super class?
        """
        if not self._items:
            try:
                self._items = self.objects(load_objects=True)
            except:
                logging.debug(
                    "caldav server does not seem to support a sync-token REPORT query on a scheduling mailbox"
                )
                error.assert_("google" in str(self.url))
                self._items = [
                    CalendarObjectResource(url=x[0], client=self.client) for x in self.children()
                ]
                for x in self._items:
                    x.load()
        else:
            try:
                self._items.sync()
            except:
                self._items = [
                    CalendarObjectResource(url=x[0], client=self.client) for x in self.children()
                ]
                for x in self._items:
                    x.load()
        return self._items

    ## TODO: work in progress


#    def get_invites():
#        for item in self.get_items():
#            if item.vobject_instance.vevent.


class ScheduleInbox(ScheduleMailbox):
    findprop = cdav.ScheduleInboxURL


class ScheduleOutbox(ScheduleMailbox):
    findprop = cdav.ScheduleOutboxURL


class SynchronizableCalendarObjectCollection:
    """
    This class may hold a cached snapshot of a calendar, and changes
    in the calendar can easily be copied over through the sync method.

    To create a SynchronizableCalendarObjectCollection object, use
    calendar.objects(load_objects=True)
    """

    def __init__(self, calendar, objects, sync_token) -> None:
        self.calendar = calendar
        self.sync_token = sync_token
        self.objects = objects
        self._objects_by_url = None

    def __iter__(self) -> Iterator[Any]:
        return self.objects.__iter__()

    def __len__(self) -> int:
        return len(self.objects)

    def objects_by_url(self):
        """
        returns a dict of the contents of the SynchronizableCalendarObjectCollection, URLs -> objects.
        """
        if self._objects_by_url is None:
            self._objects_by_url = {}
            for obj in self:
                self._objects_by_url[obj.url.canonical()] = obj
        return self._objects_by_url

    def sync(self) -> tuple[Any, Any]:
        """
        This method will contact the caldav server,
        request all changes from it, and sync up the collection.

        This method transparently falls back to comparing full calendar state
        if the server doesn't support sync tokens.
        """
        updated_objs = []
        deleted_objs = []

        ## Check if we're using fake sync tokens (fallback mode)
        is_fake_token = isinstance(self.sync_token, str) and self.sync_token.startswith("fake-")

        if not is_fake_token:
            ## Try to use real sync tokens
            try:
                updates = self.calendar.get_objects_by_sync_token(
                    self.sync_token, load_objects=False
                )

                ## If we got a fake token back, we've fallen back
                if isinstance(updates.sync_token, str) and updates.sync_token.startswith("fake-"):
                    is_fake_token = True
                else:
                    ## Real sync token path
                    obu = self.objects_by_url()
                    for obj in updates:
                        obj.url = obj.url.canonical()
                        if (
                            obj.url in obu
                            and dav.GetEtag.tag in obu[obj.url].props
                            and dav.GetEtag.tag in obj.props
                        ):
                            if obu[obj.url].props[dav.GetEtag.tag] == obj.props[dav.GetEtag.tag]:
                                continue
                        obu[obj.url] = obj
                        try:
                            obj.load()
                            updated_objs.append(obj)
                        except error.NotFoundError:
                            deleted_objs.append(obj)
                            obu.pop(obj.url)

                    self.objects = list(obu.values())
                    self._objects_by_url = None  ## Invalidate cache
                    self.sync_token = updates.sync_token
                    return (updated_objs, deleted_objs)
            except (error.ReportError, error.DAVError):
                ## Sync failed, fall back
                is_fake_token = True

        if is_fake_token:
            ## FALLBACK: Compare full calendar state
            log.debug("Using fallback sync mechanism (comparing all objects)")

            ## Retrieve all current objects from server
            current_objects = list(self.calendar.search())

            ## Load them
            for obj in current_objects:
                try:
                    obj.load()
                except error.NotFoundError:
                    pass

            ## Build URL-indexed dicts for comparison
            current_by_url = {obj.url.canonical(): obj for obj in current_objects}
            old_by_url = self.objects_by_url()

            ## Find updated and new objects
            for url, obj in current_by_url.items():
                if url in old_by_url:
                    ## Object exists in both - check if modified
                    ## Compare data if available, otherwise consider it unchanged
                    old_data = old_by_url[url].data if hasattr(old_by_url[url], "data") else None
                    new_data = obj.data if hasattr(obj, "data") else None
                    if old_data != new_data and new_data is not None:
                        updated_objs.append(obj)
                else:
                    ## New object
                    updated_objs.append(obj)

            ## Find deleted objects
            for url in old_by_url:
                if url not in current_by_url:
                    deleted_objs.append(old_by_url[url])

            ## Update internal state
            self.objects = list(current_by_url.values())
            self._objects_by_url = None  ## Invalidate cache
            self.sync_token = self.calendar._generate_fake_sync_token(self.objects)

        return (updated_objs, deleted_objs)
