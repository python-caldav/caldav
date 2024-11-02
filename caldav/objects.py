#!/usr/bin/env python
"""
A "DAV object" is anything we get from the caldav server or push into the
caldav server, notably principal, calendars and calendar events.

(This file has become huge and will be split up prior to the next
release.  I think it makes sense moving the CalendarObjectResource
class hierarchy into a separate file)
"""
import re
import sys
import uuid
from collections import defaultdict
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple
from typing import TYPE_CHECKING
from typing import TypeVar
from typing import Union
from urllib.parse import ParseResult
from urllib.parse import quote
from urllib.parse import SplitResult
from urllib.parse import unquote

import icalendar
import vobject
from dateutil.rrule import rrulestr
from lxml import etree
from lxml.etree import _Element
from vobject.base import VBase

from .elements.base import BaseElement
from .elements.cdav import CalendarData
from .elements.cdav import CompFilter
from caldav.lib.python_utilities import to_normal_str
from caldav.lib.python_utilities import to_unicode
from caldav.lib.python_utilities import to_wire

try:
    from typing import ClassVar, Optional, Union

    TimeStamp = Optional[Union[date, datetime]]
except:
    pass

import logging

from caldav.elements import cdav, dav
from caldav.lib import error, vcal
from caldav.lib.url import URL

if TYPE_CHECKING:
    from icalendar import vCalAddress

    from .davclient import DAVClient

if sys.version_info < (3, 9):
    from typing import Callable, Container, Iterable, Iterator, Sequence

    from typing_extensions import DefaultDict, Literal
else:
    from collections import defaultdict as DefaultDict
    from collections.abc import Callable, Container, Iterable, Iterator, Sequence
    from typing import Literal

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

_CC = TypeVar("_CC", bound="CalendarObjectResource")
log = logging.getLogger("caldav")


def errmsg(r) -> str:
    """Utility for formatting a response xml tree to an error string"""
    return "%s %s\n\n%s" % (r.status, r.reason, r.raw)


class DAVObject:
    """
    Base class for all DAV objects.  Can be instantiated by a client
    and an absolute or relative URL, or from the parent object.
    """

    id: Optional[str] = None
    url: Optional[URL] = None
    client: Optional["DAVClient"] = None
    parent: Optional["DAVObject"] = None
    name: Optional[str] = None

    def __init__(
        self,
        client: Optional["DAVClient"] = None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        parent: Optional["DAVObject"] = None,
        name: Optional[str] = None,
        id: Optional[str] = None,
        props=None,
        **extra,
    ) -> None:
        """
        Default constructor.

        Parameters:
         * client: A DAVClient instance
         * url: The url for this object.  May be a full URL or a relative URL.
         * parent: The parent object - used when creating objects
         * name: A displayname - to be removed in 1.0, see https://github.com/python-caldav/caldav/issues/128 for details
         * props: a dict with known properties for this object (as of 2020-12, only used for etags, and only when fetching CalendarObjectResource using the .objects or .objects_by_sync_token methods).
         * id: The resource id (UID for an Event)
        """

        if client is None and parent is not None:
            client = parent.client
        self.client = client
        self.parent = parent
        self.name = name
        self.id = id
        self.props = props or {}
        self.extra_init_options = extra
        # url may be a path relative to the caldav root
        if client and url:
            self.url = client.url.join(url)
        elif url is None:
            self.url = None
        else:
            self.url = URL.objectify(url)

    @property
    def canonical_url(self) -> str:
        if self.url is None:
            raise ValueError("Unexpected value None for self.url")
        return str(self.url.canonical())

    def children(self, type: Optional[str] = None) -> List[Tuple[URL, Any, Any]]:
        """List children, using a propfind (resourcetype) on the parent object,
        at depth = 1.

        TODO: This is old code, it's querying for DisplayName and
        ResourceTypes prop and returning a tuple of those.  Those two
        are relatively arbitrary.  I think it's mostly only calendars
        having DisplayName, but it may make sense to ask for the
        children of a calendar also as an alternative way to get all
        events?  It should be redone into a more generic method, and
        it should probably return a dict rather than a tuple.  We
        should also look over to see if there is any code duplication.
        """
        c = []

        depth = 1

        if self.url is None:
            raise ValueError("Unexpected value None for self.url")

        props = [dav.DisplayName()]
        multiprops = [dav.ResourceType()]
        props_multiprops = props + multiprops
        response = self._query_properties(props_multiprops, depth)
        properties = response.expand_simple_props(
            props=props, multi_value_props=multiprops
        )

        for path in properties:
            resource_types = properties[path][dav.ResourceType.tag]
            resource_name = properties[path][dav.DisplayName.tag]

            if type is None or type in resource_types:
                url = URL(path)
                if url.hostname is None:
                    # Quote when path is not a full URL
                    path = quote(path)
                # TODO: investigate the RFCs thoroughly - why does a "get
                # members of this collection"-request also return the
                # collection URL itself?
                # And why is the strip_trailing_slash-method needed?
                # The collection URL should always end with a slash according
                # to RFC 2518, section 5.2.
                if (isinstance(self, CalendarSet) and type == cdav.Calendar.tag) or (
                    self.url.canonical().strip_trailing_slash()
                    != self.url.join(path).canonical().strip_trailing_slash()
                ):
                    c.append((self.url.join(path), resource_types, resource_name))

        ## TODO: return objects rather than just URLs, and include
        ## the properties we've already fetched
        return c

    def _query_properties(
        self, props: Optional[Sequence[BaseElement]] = None, depth: int = 0
    ):
        """
        This is an internal method for doing a propfind query.  It's a
        result of code-refactoring work, attempting to consolidate
        similar-looking code into a common method.
        """
        root = None
        # build the propfind request
        if props is not None and len(props) > 0:
            prop = dav.Prop() + props
            root = dav.Propfind() + prop

        return self._query(root, depth)

    def _query(
        self,
        root=None,
        depth=0,
        query_method="propfind",
        url=None,
        expected_return_value=None,
    ):
        """
        This is an internal method for doing a query.  It's a
        result of code-refactoring work, attempting to consolidate
        similar-looking code into a common method.
        """
        body = ""
        if root:
            if hasattr(root, "xmlelement"):
                body = etree.tostring(
                    root.xmlelement(),
                    encoding="utf-8",
                    xml_declaration=True,
                    pretty_print=error.debug_dump_communication,
                )
            else:
                body = root
        if url is None:
            url = self.url
        ret = getattr(self.client, query_method)(url, body, depth)
        if ret.status == 404:
            raise error.NotFoundError(errmsg(ret))
        if (
            expected_return_value is not None and ret.status != expected_return_value
        ) or ret.status >= 400:
            ## COMPATIBILITY HACK - see https://github.com/python-caldav/caldav/issues/309
            body = to_wire(body)
            if (
                ret.status == 500
                and b"getetag" not in body
                and b"<C:calendar-data/>" in body
            ):
                body = body.replace(
                    b"<C:calendar-data/>", b"<D:getetag/><C:calendar-data/>"
                )
                return self._query(
                    body, depth, query_method, url, expected_return_value
                )
            raise error.exception_by_method[query_method](errmsg(ret))
        return ret

    def get_property(
        self, prop: BaseElement, use_cached: bool = False, **passthrough
    ) -> Optional[str]:
        ## TODO: use_cached should probably be true
        if use_cached:
            if prop.tag in self.props:
                return self.props[prop.tag]
        foo = self.get_properties([prop], **passthrough)
        return foo.get(prop.tag, None)

    def get_properties(
        self,
        props: Optional[Sequence[BaseElement]] = None,
        depth: int = 0,
        parse_response_xml: bool = True,
        parse_props: bool = True,
    ):
        """Get properties (PROPFIND) for this object.

        With parse_response_xml and parse_props set to True a
        best-attempt will be done on decoding the XML we get from the
        server - but this works only for properties that don't have
        complex types.  With parse_response_xml set to False, a
        DAVResponse object will be returned, and it's up to the caller
        to decode.  With parse_props set to false but
        parse_response_xml set to true, xml elements will be returned
        rather than values.

        Parameters:
         * props = [dav.ResourceType(), dav.DisplayName(), ...]

        Returns:
         * {proptag: value, ...}

        """
        rc = None
        response = self._query_properties(props, depth)
        if not parse_response_xml:
            return response

        if not parse_props:
            properties = response.find_objects_and_props()
        else:
            properties = response.expand_simple_props(props)

        error.assert_(properties)

        if self.url is None:
            raise ValueError("Unexpected value None for self.url")

        path = unquote(self.url.path)
        if path.endswith("/"):
            exchange_path = path[:-1]
        else:
            exchange_path = path + "/"

        if path in properties:
            rc = properties[path]
        elif exchange_path in properties:
            if not isinstance(self, Principal):
                ## Some caldav servers reports the URL for the current
                ## principal to end with / when doing a propfind for
                ## current-user-principal - I believe that's a bug,
                ## the principal is not a collection and should not
                ## end with /.  (example in rfc5397 does not end with /).
                ## ... but it gets worse ... when doing a propfind on the
                ## principal, the href returned may be without the slash.
                ## Such inconsistency is clearly a bug.
                log.error(
                    "potential path handling problem with ending slashes.  Path given: %s, path found: %s.  %s"
                    % (path, exchange_path, error.ERR_FRAGMENT)
                )
                error.assert_(False)
            rc = properties[exchange_path]
        elif self.url in properties:
            rc = properties[self.url]
        elif "/principal/" in properties and path.endswith("/principal/"):
            ## Workaround for a known iCloud bug.
            ## The properties key is expected to be the same as the path.
            ## path is on the format /123456/principal/ but properties key is /principal/
            ## tests apparently passed post bc589093a34f0ed0ef489ad5e9cba048750c9837 and 3ee4e42e2fa8f78b71e5ffd1ef322e4007df7a60, even without this workaround
            ## TODO: should probably be investigated more.
            ## (observed also by others, ref https://github.com/python-caldav/caldav/issues/168)
            rc = properties["/principal/"]
        elif "//" in path and path.replace("//", "/") in properties:
            ## ref https://github.com/python-caldav/caldav/issues/302
            ## though, it would be nice to find the root cause,
            ## self.url should not contain double slashes in the first place
            rc = properties[path.replace("//", "/")]
        elif len(properties) == 1:
            ## Ref https://github.com/python-caldav/caldav/issues/191 ...
            ## let's be pragmatic and just accept whatever the server is
            ## throwing at us.  But we'll log an error anyway.
            log.error(
                "Possibly the server has a path handling problem, possibly the URL configured is wrong.\n"
                "Path expected: %s, path found: %s %s.\n"
                "Continuing, probably everything will be fine"
                % (path, str(list(properties)), error.ERR_FRAGMENT)
            )
            rc = list(properties.values())[0]
        else:
            log.error(
                "Possibly the server has a path handling problem.  Path expected: %s, paths found: %s %s"
                % (path, str(list(properties)), error.ERR_FRAGMENT)
            )
            error.assert_(False)

        if parse_props:
            if rc is None:
                raise ValueError("Unexpected value None for rc")

            self.props.update(rc)
        return rc

    def set_properties(self, props: Optional[Any] = None) -> Self:
        """
        Set properties (PROPPATCH) for this object.

         * props = [dav.DisplayName('name'), ...]

        Returns:
         * self
        """
        props = [] if props is None else props
        prop = dav.Prop() + props
        set = dav.Set() + prop
        root = dav.PropertyUpdate() + set

        r = self._query(root, query_method="proppatch")

        statuses = r.tree.findall(".//" + dav.Status.tag)
        for s in statuses:
            if " 200 " not in s.text:
                raise error.PropsetError(s.text)

        return self

    def save(self) -> Self:
        """
        Save the object. This is an abstract method, that all classes
        derived from DAVObject implement.

        Returns:
         * self
        """
        raise NotImplementedError()

    def delete(self) -> None:
        """
        Delete the object.
        """
        if self.url is not None:
            if self.client is None:
                raise ValueError("Unexpected value None for self.client")

            r = self.client.delete(str(self.url))

            # TODO: find out why we get 404
            if r.status not in (200, 204, 404):
                raise error.DeleteError(errmsg(r))

    def get_display_name(self):
        """
        Get calendar display name
        """
        return self.get_property(dav.DisplayName())

    def __str__(self) -> str:
        try:
            return (
                str(self.get_property(dav.DisplayName(), use_cached=True)) or self.url
            )
        except:
            return str(self.url)

    def __repr__(self) -> str:
        return "%s(%s)" % (self.__class__.__name__, self.url)


class CalendarSet(DAVObject):
    """
    A CalendarSet is a set of calendars.
    """

    def calendars(self) -> List["Calendar"]:
        """
        List all calendar collections in this set.

        Returns:
         * [Calendar(), ...]
        """
        cals = []

        data = self.children(cdav.Calendar.tag)
        for c_url, c_type, c_name in data:
            try:
                cal_id = c_url.split("/")[-2]
            except:
                log.error(f"Calendar {c_name} has unexpected url {c_url}")
                cal_id = None
            cals.append(
                Calendar(self.client, id=cal_id, url=c_url, parent=self, name=c_name)
            )

        return cals

    def make_calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        supported_calendar_component_set: Optional[Any] = None,
    ) -> "Calendar":
        """
        Utility method for creating a new calendar.

        Parameters:
         * name: the display name of the new calendar
         * cal_id: the uuid of the new calendar
         * supported_calendar_component_set: what kind of objects
           (EVENT, VTODO, VFREEBUSY, VJOURNAL) the calendar should handle.
           Should be set to ['VTODO'] when creating a task list in Zimbra -
           in most other cases the default will be OK.

        Returns:
         * Calendar(...)-object
        """
        return Calendar(
            self.client,
            name=name,
            parent=self,
            id=cal_id,
            supported_calendar_component_set=supported_calendar_component_set,
        ).save()

    def calendar(
        self, name: Optional[str] = None, cal_id: Optional[str] = None
    ) -> "Calendar":
        """
        The calendar method will return a calendar object.  If it gets a cal_id
        but no name, it will not initiate any communication with the server

        Parameters:
         * name: return the calendar with this display name
         * cal_id: return the calendar with this calendar id or URL

        Returns:
         * Calendar(...)-object
        """
        if name and not cal_id:
            for calendar in self.calendars():
                display_name = calendar.get_display_name()
                if display_name == name:
                    return calendar
        if name and not cal_id:
            raise error.NotFoundError(
                "No calendar with name %s found under %s" % (name, self.url)
            )
        if not cal_id and not name:
            return self.calendars()[0]

        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        if cal_id is None:
            raise ValueError("Unexpected value None for cal_id")

        if str(URL.objectify(cal_id).canonical()).startswith(
            str(self.client.url.canonical())
        ):
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
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
    ) -> None:
        """
        Returns a Principal.

        Parameters:
         * client: a DAVClient() object
         * url: Deprecated - for backwards compatibility purposes only.

        If url is not given, deduct principal path as well as calendar home set
        path from doing propfinds.
        """
        super(Principal, self).__init__(client=client, url=url)
        self._calendar_home_set = None

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

    def make_calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        supported_calendar_component_set: Optional[Any] = None,
    ) -> "Calendar":
        """
        Convenience method, bypasses the self.calendar_home_set object.
        See CalendarSet.make_calendar for details.
        """
        return self.calendar_home_set.make_calendar(
            name,
            cal_id,
            supported_calendar_component_set=supported_calendar_component_set,
        )

    def calendar(
        self,
        name: Optional[str] = None,
        cal_id: Optional[str] = None,
        cal_url: Optional[str] = None,
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
        Returns the principal, as an icalendar.vCalAddress object
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
            if (
                sanitized_url.hostname
                and sanitized_url.hostname != self.client.url.hostname
            ):
                # icloud (and others?) having a load balanced system,
                # where each principal resides on one named host
                ## TODO:
                ## Here be dragons.  sanitized_url will be the root
                ## of all future objects derived from client.  Changing
                ## the client.url root by doing a principal.calendars()
                ## is an unacceptable side effect and may be a cause of
                ## incompatibilities with icloud.  Do more research!
                self.client.url = sanitized_url
        self._calendar_home_set = CalendarSet(
            self.client, self.client.url.join(sanitized_url)
        )

    def calendars(self) -> List["Calendar"]:
        """
        Return the principials calendars
        """
        return self.calendar_home_set.calendars()

    def freebusy_request(self, dtstart, dtend, attendees):
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
        return response.find_objects_and_props()

    def calendar_user_address_set(self) -> List[Optional[str]]:
        """
        defined in RFC6638
        """
        _addresses: Optional[_Element] = self.get_property(
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
        return ScheduleInbox(principal=self)

    def schedule_outbox(self) -> "ScheduleOutbox":
        return ScheduleOutbox(principal=self)


class Calendar(DAVObject):
    """
    The `Calendar` object is used to represent a calendar collection.
    Refer to the RFC for details:
    https://tools.ietf.org/html/rfc4791#section-5.3.1
    """

    def _create(
        self, name=None, id=None, supported_calendar_component_set=None
    ) -> None:
        """
        Create a new calendar with display name `name` in `parent`.
        """
        if id is None:
            id = str(uuid.uuid1())
        self.id = id

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
        set = dav.Set() + prop

        mkcol = cdav.Mkcalendar() + set

        r = self._query(
            root=mkcol, query_method="mkcalendar", url=path, expected_return_value=201
        )

        # COMPATIBILITY ISSUE
        # name should already be set, but we've seen caldav servers failing
        # on setting the DisplayName on calendar creation
        # (DAViCal, Zimbra, ...).  Doing an attempt on explicitly setting the
        # display name using PROPPATCH.
        if name:
            try:
                self.set_properties([display_name])
            except:
                ## TODO: investigate.  Those asserts break.
                error.assert_(False)
                try:
                    current_display_name = self.get_display_name()
                    error.assert_(current_display_name == name)
                except:
                    log.warning(
                        "calendar server does not support display name on calendar?  Ignoring",
                        exc_info=True,
                    )
                    error.assert_(False)

    def get_supported_components(self) -> List[Any]:
        """
        returns a list of component types supported by the calendar, in
        string format (typically ['VJOURNAL', 'VTODO', 'VEVENT'])
        """
        if self.url is None:
            raise ValueError("Unexpected value None for self.url")

        props = [cdav.SupportedCalendarComponentSet()]
        response = self.get_properties(props, parse_response_xml=False)
        response_list = response.find_objects_and_props()
        prop = response_list[unquote(self.url.path)][
            cdav.SupportedCalendarComponentSet().tag
        ]
        return [supported.get("name") for supported in prop]

    def save_with_invites(self, ical: str, attendees, **attendeeoptions) -> None:
        """
        sends a schedule request to the server.  Equivalent with save_event, save_todo, etc,
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

    ## TODO: consolidate save_* - too much code duplication here
    def save_event(
        self,
        ical: Optional[str] = None,
        no_overwrite: bool = False,
        no_create: bool = False,
        **ical_data,
    ) -> "Event":
        """
        Add a new event to the calendar, with the given ical.

        Parameters:
         * ical - ical object (text)
         * no_overwrite - existing calendar objects should not be overwritten
         * no_create - don't create a new object, existing calendar objects should be updated
         * ical_data - passed to lib.vcal.create_ical
        """
        e = Event(
            self.client,
            data=self._use_or_create_ics(ical, objtype="VEVENT", **ical_data),
            parent=self,
        )
        e.save(no_overwrite=no_overwrite, no_create=no_create, obj_type="event")
        self._handle_relations(e.id, ical_data)
        return e

    def save_todo(
        self,
        ical: Optional[str] = None,
        no_overwrite: bool = False,
        no_create: bool = False,
        **ical_data,
    ) -> "Todo":
        """
        Add a new task to the calendar, with the given ical.

        Parameters:
         * ical - ical object (text)
        """
        t = Todo(
            self.client,
            data=self._use_or_create_ics(ical, objtype="VTODO", **ical_data),
            parent=self,
        )
        t.save(no_overwrite=no_overwrite, no_create=no_create, obj_type="todo")
        self._handle_relations(t.id, ical_data)
        return t

    def save_journal(
        self,
        ical: Optional[str] = None,
        no_overwrite: bool = False,
        no_create: bool = False,
        **ical_data,
    ) -> "Journal":
        """
        Add a new journal entry to the calendar, with the given ical.

        Parameters:
         * ical - ical object (text)
        """
        j = Journal(
            self.client,
            data=self._use_or_create_ics(ical, objtype="VJOURNAL", **ical_data),
            parent=self,
        )
        j.save(no_overwrite=no_overwrite, no_create=no_create, obj_type="journal")
        self._handle_relations(j.id, ical_data)
        return j

    def _handle_relations(self, uid, ical_data) -> None:
        for reverse_reltype, other_uid in [
            ("parent", x) for x in ical_data.get("child", ())
        ] + [("child", x) for x in ical_data.get("parent", ())]:
            other = self.object_by_uid(other_uid)
            other.set_relation(other=uid, reltype=reverse_reltype, set_reverse=False)

    ## legacy aliases
    ## TODO: should be deprecated

    ## TODO: think more through this - is `save_foo` better than `add_foo`?
    ## `save_foo` should not be used for updating existing content on the
    ## calendar!

    add_event = save_event
    add_todo = save_todo
    add_journal = save_journal

    def save(self):
        """
        The save method for a calendar is only used to create it, for now.
        We know we have to create it when we don't have a url.

        Returns:
         * self
        """
        if self.url is None:
            self._create(id=self.id, name=self.name, **self.extra_init_options)
        return self

    def calendar_multiget(self, event_urls: Iterable[URL]) -> List["Event"]:
        """
        get multiple events' data
        @author mtorange@gmail.com
        @type events list of Event
        """
        if self.url is None:
            raise ValueError("Unexpected value None for self.url")

        rv = []
        prop = dav.Prop() + cdav.CalendarData()
        root = (
            cdav.CalendarMultiGet()
            + prop
            + [dav.Href(value=u.path) for u in event_urls]
        )
        response = self._query(root, 1, "report")
        results = response.expand_simple_props([cdav.CalendarData()])
        rv = [
            Event(
                self.client,
                url=self.url.join(r),
                data=results[r][cdav.CalendarData.tag],
                parent=self,
            )
            for r in results
        ]
        return rv

    ## TODO: Upgrade the warning to an error (and perhaps critical) in future
    ## releases, and then finally remove this method completely.
    def build_date_search_query(
        self,
        start,
        end: Optional[datetime] = None,
        compfilter: Optional[Literal["VEVENT"]] = "VEVENT",
        expand: Union[bool, Literal["maybe"]] = "maybe",
    ):
        """
        WARNING: DEPRECATED
        """
        ## This is dead code.  It has no tests.  It was made for usage
        ## by the date_search method, but I've decided not to use it
        ## there anymore.  Most likely nobody is using this, as it's
        ## sort of an internal method - but for the sake of backward
        ## compatibility I will keep it for a while.  I regret naming
        ## it build_date_search_query rather than
        ## _build_date_search_query...
        logging.warning(
            "DEPRECATION WARNING: The calendar.build_date_search_query method will be removed in caldav library from version 1.0 or perhaps earlier.  Use calendar.build_search_xml_query instead."
        )
        if expand == "maybe":
            expand = end

        if compfilter == "VEVENT":
            comp_class = Event
        elif compfilter == "VTODO":
            comp_class = Todo
        else:
            comp_class = None

        return self.build_search_xml_query(
            comp_class=comp_class, expand=expand, start=start, end=end
        )

    def date_search(
        self,
        start: datetime,
        end: Optional[datetime] = None,
        compfilter: None = "VEVENT",
        expand: Union[bool, Literal["maybe"]] = "maybe",
        verify_expand: bool = False,
    ) -> Sequence["CalendarObjectResource"]:
        # type (TimeStamp, TimeStamp, str, str) -> CalendarObjectResource
        """Deprecated.  Use self.search() instead.

        Search events by date in the calendar. Recurring events are
        expanded if they are occurring during the specified time frame
        and if an end timestamp is given.

        Parameters:
         * start = datetime.today().
         * end = same as above.
         * compfilter = defaults to events only.  Set to None to fetch all
           calendar components.
         * expand - should recurrent events be expanded?  (to preserve
           backward-compatibility the default "maybe" will be changed into True
           unless the date_search is open-ended)
         * verify_expand - not in use anymore, but kept for backward compatibility

        Returns:
         * [CalendarObjectResource(), ...]

        """
        ## TODO: upgrade to warning and error before removing this method
        logging.info(
            "DEPRECATION NOTICE: The calendar.date_search method may be removed in release 2.0 of the caldav library.  Use calendar.search instead"
        )

        if verify_expand:
            logging.warning(
                "verify_expand in date_search does not work anymore, as we're doing client side expansion instead"
            )

        ## for backward compatibility - expand should be false
        ## in an open-ended date search, otherwise true
        if expand == "maybe":
            expand = end

        if compfilter == "VEVENT":
            comp_class = Event
        elif compfilter == "VTODO":
            comp_class = Todo
        else:
            comp_class = None

        ## xandikos now yields a 5xx-error when trying to pass
        ## expand=True, after I prodded the developer that it doesn't
        ## work.  By now there is some workaround in the test code to
        ## avoid sending expand=True to xandikos, but perhaps we
        ## should run a try-except-retry here with expand=False in the
        ## retry, and warnings logged ... or perhaps not.
        objects = self.search(
            start=start,
            end=end,
            comp_class=comp_class,
            expand=expand,
            split_expanded=False,
        )

        return objects

    def _request_report_build_resultlist(
        self, xml, comp_class=None, props=None, no_calendardata=False
    ):
        """
        Takes some input XML, does a report query on a calendar object
        and returns the resource objects found.

        TODO: similar code is duplicated many places, we ought to do even more code
        refactoring
        """
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
                if comp_class is None:
                    comp_class = self._calendar_comp_class_by_data(cdata)
            else:
                cdata = None
            if comp_class is None:
                ## no CalendarData fetched - which is normal i.e. when doing a sync-token report and only asking for the URLs
                comp_class = CalendarObjectResource
            url = URL(r)
            if url.hostname is None:
                # Quote when result is not a full URL
                url = quote(r)
            ## icloud hack - icloud returns the calendar URL as well as the calendar item URLs
            if self.url.join(url) == self.url:
                continue
            matches.append(
                comp_class(
                    self.client,
                    url=self.url.join(url),
                    data=cdata,
                    parent=self,
                    props=pdata,
                )
            )

        return (response, matches)

    def search(
        self,
        xml=None,
        comp_class: Optional[_CC] = None,
        todo: Optional[bool] = None,
        include_completed: bool = False,
        sort_keys: Sequence[str] = (),
        sort_reverse: bool = False,
        expand: Union[bool, Literal["server"], Literal["client"]] = False,
        split_expanded: bool = True,
        props: Optional[List[CalendarData]] = None,
        **kwargs,
    ) -> List[_CC]:
        """Creates an XML query, does a REPORT request towards the
        server and returns objects found, eventually sorting them
        before delivery.

        This method contains some special logics to ensure that it can
        consistently return a list of pending tasks on any server
        implementation.  In the future it may also include workarounds
        and client side filtering to make sure other search results
        are consistent on different server implementations.

        LEGACY WARNING: the expand attribute currently takes four
        possible values - True, False, server and client.  The two
        latter value were hastily added just prior to launching
        version 1.4, the API may be reconsidered and changed without
        notice when launching version 2.0

        Parameters supported:

        * xml - use this search query, and ignore other filter parameters
        * comp_class - set to event, todo or journal to restrict search to this
          resource type.  Some server implementations require this to be set.
        * todo - sets comp_class to Todo, and restricts search to pending tasks,
          unless the next parameter is set ...
        * include_completed - include completed tasks
        * event - sets comp_class to event
        * text attribute search parameters: category, uid, summary, omment,
          description, location, status
        * no-category, no-summary, etc ... search for objects that does not
          have those attributes.  TODO: WRITE TEST CODE!
        * expand - expand recurring objects
        * start, end: do a time range search
        * filters - other kind of filters (in lxml tree format)
        * sort_keys - list of attributes to use when sorting
        * sort_reverse - reverse the sorting order

        not supported yet:
        * negated text match
        * attribute not set

        """
        ## special compatibility-case when searching for pending todos
        if todo and not include_completed:
            matches1 = self.search(
                todo=True,
                comp_class=comp_class,
                ignore_completed1=True,
                include_completed=True,
                **kwargs,
            )
            matches2 = self.search(
                todo=True,
                comp_class=comp_class,
                ignore_completed2=True,
                include_completed=True,
                **kwargs,
            )
            matches3 = self.search(
                todo=True,
                comp_class=comp_class,
                ignore_completed3=True,
                include_completed=True,
                **kwargs,
            )
            objects = []
            match_set = set()
            for item in matches1 + matches2 + matches3:
                if item.url not in match_set:
                    match_set.add(item.url)
                    ## and still, Zimbra seems to deliver too many TODOs in the
                    ## matches2 ... let's do some post-filtering in case the
                    ## server fails in filtering things the right way
                    if "STATUS:NEEDS-ACTION" in item.data or (
                        "\nCOMPLETED:" not in item.data
                        and "\nSTATUS:COMPLETED" not in item.data
                        and "\nSTATUS:CANCELLED" not in item.data
                    ):
                        objects.append(item)
        else:
            if not xml:
                if expand and expand != "client":
                    kwargs["expand"] = True
                (xml, comp_class) = self.build_search_xml_query(
                    comp_class=comp_class, todo=todo, props=props, **kwargs
                )
            elif kwargs:
                raise error.ConsistencyError(
                    "Inconsistent usage parameters: xml together with other search options"
                )
            try:
                (response, objects) = self._request_report_build_resultlist(
                    xml, comp_class, props=props
                )
            except error.ReportError as err:
                ## Hack for some calendar servers
                ## yielding 400 if the search does not include compclass.
                ## Partial fix for https://github.com/python-caldav/caldav/issues/401
                ## This assumes the client actually wants events and not tasks
                ## The calendar server in question did not support tasks
                ## However the most correct would probably be to join
                ## events, tasks and journals.
                ## TODO: we need server compatibility hints!
                ## https://github.com/python-caldav/caldav/issues/402
                if not comp_class and not "400" in err.reason:
                    return self.search(
                        event=True,
                        include_completed=include_completed,
                        sort_keys=sort_keys,
                        split_expanded=split_expanded,
                        props=props,
                        **kwargs,
                    )
                raise

        for o in objects:
            ## This would not be needed if the servers would follow the standard ...
            o.load(only_if_unloaded=True)

        ## Google sometimes returns empty objects
        objects = [o for o in objects if o.has_component()]

        if expand and expand != "server":
            ## expand can only be used together with start and end (and not
            ## with xml).  Error checking has already been done in
            ## build_search_xml_query above.
            start = kwargs["start"]
            end = kwargs["end"]

            ## Verify that any recurring objects returned are already expanded
            for o in objects:
                component = o.icalendar_component
                if component is None:
                    continue
                recurrence_properties = ["exdate", "exrule", "rdate", "rrule"]
                if any(key in component for key in recurrence_properties):
                    o.expand_rrule(start, end)

            ## An expanded recurring object comes as one Event() with
            ## icalendar data containing multiple objects.  The caller may
            ## expect multiple Event()s.  This code splits events into
            ## separate objects:
        if expand and split_expanded:
            objects_ = objects
            objects = []
            for o in objects_:
                objects.extend(o.split_expanded())

        def sort_key_func(x):
            ret = []
            comp = x.icalendar_component
            defaults = {
                ## TODO: all possible non-string sort attributes needs to be listed here, otherwise we will get type errors when comparing objects with the property defined vs undefined (or maybe we should make an "undefined" object that always will compare below any other type?  Perhaps there exists such an object already?)
                "due": "2050-01-01",
                "dtstart": "1970-01-01",
                "priority": 0,
                "status": {
                    "VTODO": "NEEDS-ACTION",
                    "VJOURNAL": "FINAL",
                    "VEVENT": "TENTATIVE",
                }[comp.name],
                "category": "",
                ## Usage of strftime is a simple way to ensure there won't be
                ## problems if comparing dates with timestamps
                "isnt_overdue": not (
                    "due" in comp
                    and comp["due"].dt.strftime("%F%H%M%S")
                    < datetime.now().strftime("%F%H%M%S")
                ),
                "hasnt_started": (
                    "dtstart" in comp
                    and comp["dtstart"].dt.strftime("%F%H%M%S")
                    > datetime.now().strftime("%F%H%M%S")
                ),
            }
            for sort_key in sort_keys:
                val = comp.get(sort_key, None)
                if val is None:
                    ret.append(defaults.get(sort_key.lower(), ""))
                    continue
                if hasattr(val, "dt"):
                    val = val.dt
                elif hasattr(val, "cats"):
                    val = ",".join(val.cats)
                if hasattr(val, "strftime"):
                    ret.append(val.strftime("%F%H%M%S"))
                else:
                    ret.append(val)
            return ret

        if sort_keys:
            objects.sort(key=sort_key_func, reverse=sort_reverse)

        ## partial workaround for https://github.com/python-caldav/caldav/issues/201
        for obj in objects:
            try:
                obj.load(only_if_unloaded=True)
            except:
                pass

        return objects

    def build_search_xml_query(
        self,
        comp_class=None,
        todo=None,
        ignore_completed1=None,
        ignore_completed2=None,
        ignore_completed3=None,
        event=None,
        filters=None,
        expand=None,
        start=None,
        end=None,
        props=None,
        **kwargs,
    ):
        """This method will produce a caldav search query as an etree object.

        It is primarily to be used from the search method.  See the
        documentation for the search method for more information.
        """
        # those xml elements are weird.  (a+b)+c != a+(b+c).  First makes b and c as list members of a, second makes c an element in b which is an element of a.
        # First objective is to let this take over all xml search query building and see that the current tests pass.
        # ref https://www.ietf.org/rfc/rfc4791.txt, section 7.8.9 for how to build a todo-query
        # We'll play with it and don't mind it's getting ugly and don't mind that the test coverage is lacking.
        # we'll refactor and create some unit tests later, as well as ftests for complicated queries.

        # build the request
        data = cdav.CalendarData()
        if expand:
            if not start or not end:
                raise error.ReportError("can't expand without a date range")
            data += cdav.Expand(start, end)
        if props is None:
            props_ = [data]
        else:
            props_ = [data] + props
        prop = dav.Prop() + props_
        vcalendar = cdav.CompFilter("VCALENDAR")

        comp_filter = None

        filters = filters or []

        vNotCompleted = cdav.TextMatch("COMPLETED", negate=True)
        vNotCancelled = cdav.TextMatch("CANCELLED", negate=True)
        vNeedsAction = cdav.TextMatch("NEEDS-ACTION")
        vStatusNotCompleted = cdav.PropFilter("STATUS") + vNotCompleted
        vStatusNotCancelled = cdav.PropFilter("STATUS") + vNotCancelled
        vStatusNeedsAction = cdav.PropFilter("STATUS") + vNeedsAction
        vStatusNotDefined = cdav.PropFilter("STATUS") + cdav.NotDefined()
        vNoCompleteDate = cdav.PropFilter("COMPLETED") + cdav.NotDefined()
        if ignore_completed1:
            ## This query is quite much in line with https://tools.ietf.org/html/rfc4791#section-7.8.9
            filters.extend([vNoCompleteDate, vStatusNotCompleted, vStatusNotCancelled])
        elif ignore_completed2:
            ## some server implementations (i.e. NextCloud
            ## and Baikal) will yield "false" on a negated TextMatch
            ## if the field is not defined.  Hence, for those
            ## implementations we need to turn back and ask again
            ## ... do you have any VTODOs for us where the STATUS
            ## field is not defined? (ref
            ## https://github.com/python-caldav/caldav/issues/14)
            filters.extend([vNoCompleteDate, vStatusNotDefined])
        elif ignore_completed3:
            ## ... and considering recurring tasks we really need to
            ## look a third time as well, this time for any task with
            ## the NEEDS-ACTION status set (do we need the first go?
            ## NEEDS-ACTION or no status set should cover them all?)
            filters.extend([vStatusNeedsAction])

        if start or end:
            filters.append(cdav.TimeRange(start, end))

        if todo is not None:
            if not todo:
                raise NotImplementedError()
            if todo:
                if comp_class is not None and comp_class is not Todo:
                    raise error.ConsistencyError(
                        "inconsistent search parameters - comp_class = %s, todo=%s"
                        % (comp_class, todo)
                    )
                comp_filter = cdav.CompFilter("VTODO")
                comp_class = Todo
        if event is not None:
            if not event:
                raise NotImplementedError()
            if event:
                if comp_class is not None and comp_class is not Event:
                    raise error.ConsistencyError(
                        "inconsistent search parameters - comp_class = %s, event=%s"
                        % (comp_class, event)
                    )
                comp_filter = cdav.CompFilter("VEVENT")
                comp_class = Event
        elif comp_class:
            if comp_class is Todo:
                comp_filter = cdav.CompFilter("VTODO")
            elif comp_class is Event:
                comp_filter = cdav.CompFilter("VEVENT")
            elif comp_class is Journal:
                comp_filter = cdav.CompFilter("VJOURNAL")
            else:
                raise error.ConsistencyError(
                    "unsupported comp class %s for search" % comp_class
                )

        for other in kwargs:
            find_not_defined = other.startswith("no_")
            find_defined = other.startswith("has_")
            if find_not_defined:
                other = other[3:]
            if find_defined:
                other = other[4:]
            if other in (
                "uid",
                "summary",
                "comment",
                "class_",
                "class",
                "category",
                "description",
                "location",
                "status",
                "due",
                "dtstamp",
                "dtstart",
                "dtend",
                "duration",
                "priority",
            ):
                ## category and class_ is special
                if other.endswith("category"):
                    ## TODO: we probably need to do client side filtering.  I would
                    ## expect --category='e' to fetch anything having the category e,
                    ## but not including all other categories containing the letter e.
                    ## As I read the caldav standard, the latter will be yielded.
                    target = other.replace("category", "categories")
                elif other == "class_":
                    target = "class"
                else:
                    target = other

                if find_not_defined:
                    match = cdav.NotDefined()
                elif find_defined:
                    raise NotImplementedError(
                        "Seems not to be supported by the CalDAV protocol?  or we can negate?  not supported yet, in any case"
                    )
                else:
                    match = cdav.TextMatch(kwargs[other])
                filters.append(cdav.PropFilter(target.upper()) + match)
            else:
                raise NotImplementedError("searching for %s not supported yet" % other)

        if comp_filter and filters:
            comp_filter += filters
            vcalendar += comp_filter
        elif comp_filter:
            vcalendar += comp_filter
        elif filters:
            vcalendar += filters

        filter = cdav.Filter() + vcalendar

        root = cdav.CalendarQuery() + [prop, filter]

        return (root, comp_class)

    def freebusy_request(self, start: datetime, end: datetime) -> "FreeBusy":
        """
        Search the calendar, but return only the free/busy information.

        Parameters:
         * start = datetime.today().
         * end = same as above.

        Returns:
         * [FreeBusy(), ...]

        """

        root = cdav.FreeBusyQuery() + [cdav.TimeRange(start, end)]
        response = self._query(root, 1, "report")
        return FreeBusy(self, response.raw)

    def todos(
        self,
        sort_keys: Sequence[str] = ("due", "priority"),
        include_completed: bool = False,
        sort_key: Optional[str] = None,
    ) -> List["Todo"]:
        """
        fetches a list of todo events (refactored to a wrapper around search)

        Parameters:
         * sort_keys: use this field in the VTODO for sorting (iterable of
           lower case string, i.e. ('priority','due')).
         * include_completed: boolean -
           by default, only pending tasks are listed
         * sort_key: DEPRECATED, for backwards compatibility with version 0.4.
        """
        if sort_key:
            sort_keys = (sort_key,)

        return self.search(
            todo=True, include_completed=include_completed, sort_keys=sort_keys
        )

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

    def event_by_url(self, href, data: Optional[Any] = None) -> "Event":
        """
        Returns the event with the given URL
        """
        return Event(url=href, data=data, parent=self).load()

    def object_by_uid(
        self,
        uid: str,
        comp_filter: Optional[CompFilter] = None,
        comp_class: Optional["CalendarObjectResource"] = None,
    ) -> "Event":
        """
        Get one event from the calendar.

        Parameters:
         * uid: the event uid
         * comp_class: filter by component type (Event, Todo, Journal)
         * comp_filter: for backward compatibility

        Returns:
         * Event() or None
        """
        if comp_filter:
            assert not comp_class
            if hasattr(comp_filter, "attributes"):
                if comp_filter.attributes is None:
                    raise ValueError(
                        "Unexpected None value for variable comp_filter.attributes"
                    )
                comp_filter = comp_filter.attributes["name"]
            if comp_filter == "VTODO":
                comp_class = Todo
            elif comp_filter == "VJOURNAL":
                comp_class = Journal
            elif comp_filter == "VEVENT":
                comp_class = Event
            else:
                raise error.ConsistencyError("Wrong compfilter")

        query = cdav.TextMatch(uid)
        query = cdav.PropFilter("UID") + query

        root, comp_class = self.build_search_xml_query(
            comp_class=comp_class, filters=[query]
        )

        try:
            items_found: List[Event] = self.search(root)
            if not items_found:
                raise error.NotFoundError("%s not found on server" % uid)
        except Exception as err:
            if comp_filter is not None:
                raise
            logging.warning(
                "Error %s from server when doing an object_by_uid(%s).  search without compfilter set is not compatible with all server implementations, trying event_by_uid + todo_by_uid + journal_by_uid instead"
                % (str(err), uid)
            )
            items_found = []
            for compfilter in ("VTODO", "VEVENT", "VJOURNAL"):
                try:
                    items_found.append(
                        self.object_by_uid(uid, cdav.CompFilter(compfilter))
                    )
                except error.NotFoundError:
                    pass
            if len(items_found) >= 1:
                if len(items_found) > 1:
                    logging.error(
                        "multiple items found with same UID.  Returning the first one"
                    )
                return items_found[0]

        # Ref Lucas Verney, we've actually done a substring search, if the
        # uid given in the query is short (i.e. just "0") we're likely to
        # get false positives back from the server, we need to do an extra
        # check that the uid is correct
        items_found2 = []
        for item in items_found:
            ## In v0.10.0 we used regexps here - it's probably more optimized,
            ## but at one point it broke due to an extra CR in the data.
            ## Usage of the icalendar library increases readability and
            ## reliability
            if item.icalendar_component:
                item_uid = item.icalendar_component.get("UID", None)
                if item_uid and item_uid == uid:
                    items_found2.append(item)
        if not items_found2:
            raise error.NotFoundError("%s not found on server" % uid)
        error.assert_(len(items_found2) == 1)
        return items_found2[0]

    def todo_by_uid(self, uid: str) -> "CalendarObjectResource":
        return self.object_by_uid(uid, comp_filter=cdav.CompFilter("VTODO"))

    def event_by_uid(self, uid: str) -> "CalendarObjectResource":
        return self.object_by_uid(uid, comp_filter=cdav.CompFilter("VEVENT"))

    def journal_by_uid(self, uid: str) -> "CalendarObjectResource":
        return self.object_by_uid(uid, comp_filter=cdav.CompFilter("VJOURNAL"))

    # alias for backward compatibility
    event = event_by_uid

    def events(self) -> List["Event"]:
        """
        List all events from the calendar.

        Returns:
         * [Event(), ...]
        """
        return self.search(comp_class=Event)

    def objects_by_sync_token(
        self, sync_token: Optional[Any] = None, load_objects: bool = False
    ) -> "SynchronizableCalendarObjectCollection":
        """objects_by_sync_token aka objects

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
        """
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

    objects = objects_by_sync_token

    def journals(self) -> List["Journal"]:
        """
        List all journals from the calendar.

        Returns:
         * [Journal(), ...]
        """
        return self.search(comp_class=Journal)


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
        principal: Optional[Principal] = None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
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
                    "principal has no %s.  %s"
                    % (str(self.findprop()), error.ERR_FRAGMENT)  # type: ignore
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
                    CalendarObjectResource(url=x[0], client=self.client)
                    for x in self.children()
                ]
                for x in self._items:
                    x.load()
        else:
            try:
                self._items.sync()
            except:
                self._items = [
                    CalendarObjectResource(url=x[0], client=self.client)
                    for x in self.children()
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

    def sync(self) -> Tuple[Any, Any]:
        """
        This method will contact the caldav server,
        request all changes from it, and sync up the collection
        """
        updated_objs = []
        deleted_objs = []
        updates = self.calendar.objects_by_sync_token(
            self.sync_token, load_objects=False
        )
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

        self.objects = obu.values()
        self.sync_token = updates.sync_token
        return (updated_objs, deleted_objs)


class CalendarObjectResource(DAVObject):
    """
    Ref RFC 4791, section 4.1, a "Calendar Object Resource" can be an
    event, a todo-item, a journal entry, or a free/busy entry
    """

    RELTYPE_REVERSER: ClassVar = {
        "PARENT": "CHILD",
        "CHILD": "PARENT",
        "SIBLING": "SIBLING",
    }

    _ENDPARAM = None

    _vobject_instance = None
    _icalendar_instance = None
    _data = None

    def __init__(
        self,
        client: Optional["DAVClient"] = None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        data: Optional[Any] = None,
        parent: Optional[Any] = None,
        id: Optional[Any] = None,
        props: Optional[Any] = None,
    ) -> None:
        """
        CalendarObjectResource has an additional parameter for its constructor:
         * data = "...", vCal data for the event
        """
        super(CalendarObjectResource, self).__init__(
            client=client, url=url, parent=parent, id=id, props=props
        )
        if data is not None:
            self.data = data
            if id:
                old_id = self.icalendar_component.pop("UID", None)
                self.icalendar_component.add("UID", id)

    def add_organizer(self) -> None:
        """
        goes via self.client, finds the principal, figures out the right attendee-format and adds an
        organizer line to the event
        """
        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        principal = self.client.principal()
        ## TODO: remove Organizer-field, if exists
        ## TODO: what if walk returns more than one vevent?
        self.icalendar_component.add("organizer", principal.get_vcal_address())

    def split_expanded(self) -> List[Self]:
        i = self.icalendar_instance.subcomponents
        tz_ = [x for x in i if isinstance(x, icalendar.Timezone)]
        ntz = [x for x in i if not isinstance(x, icalendar.Timezone)]
        if len(ntz) == 1:
            return [self]
        if tz_:
            error.assert_(len(tz_) == 1)
        ret = []
        for ical_obj in ntz:
            obj = self.copy(keep_uid=True)
            obj.icalendar_instance.subcomponents = []
            if tz_:
                obj.icalendar_instance.subcomponents.append(tz_[0])
            obj.icalendar_instance.subcomponents.append(ical_obj)
            ret.append(obj)
        return ret

    def expand_rrule(self, start: datetime, end: datetime) -> None:
        """This method will transform the calendar content of the
        event and expand the calendar data from a "master copy" with
        RRULE set and into a "recurrence set" with RECURRENCE-ID set
        and no RRULE set.  The main usage is for client-side expansion
        in case the calendar server does not support server-side
        expansion.  It should be safe to save back to the server, the
        server should recognize it as recurrences and should not edit
        the "master copy".  If doing a `self.load`, the calendar
        content will be replaced with the "master copy".  However, as
        of 2022-10 there is no test code verifying this.

        :param event: Event
        :param start: datetime
        :param end: datetime

        """
        import recurring_ical_events

        recurrings = recurring_ical_events.of(
            self.icalendar_instance, components=["VJOURNAL", "VTODO", "VEVENT"]
        ).between(start, end)
        recurrence_properties = ["exdate", "exrule", "rdate", "rrule"]
        # FIXME too much copying
        stripped_event = self.copy(keep_uid=True)

        if stripped_event.vobject_instance is None:
            raise ValueError(
                "Unexpected value None for stripped_event.vobject_instance"
            )

        # remove all recurrence properties
        for component in stripped_event.vobject_instance.components():  # type: ignore
            if component.name in ("VEVENT", "VTODO"):
                for key in recurrence_properties:
                    try:
                        del component.contents[key]
                    except KeyError:
                        pass

        calendar = self.icalendar_instance
        calendar.subcomponents = []
        for occurrence in recurrings:
            if "RECURRENCE-ID" not in occurrence:
                occurrence.add("RECURRENCE-ID", occurrence.get("DTSTART"))
            calendar.add_component(occurrence)
        # add other components (except for the VEVENT itself and VTIMEZONE which is not allowed on occurrence events)
        for component in stripped_event.icalendar_instance.subcomponents:
            if component.name not in ("VEVENT", "VTODO", "VTIMEZONE"):
                calendar.add_component(component)

    def set_relation(
        self, other, reltype=None, set_reverse=True
    ) -> None:  ## TODO: logic to find and set siblings?
        """
        Sets a relation between this object and another object (given by uid or object).
        """
        ##TODO: test coverage
        reltype = reltype.upper()
        if isinstance(other, CalendarObjectResource):
            if other.id:
                uid = other.id
            else:
                uid = other.icalendar_component["uid"]
        else:
            uid = other
            if set_reverse:
                other = self.parent.object_by_uid(uid)
        if set_reverse:
            reltype_reverse = self.RELTYPE_REVERSER[reltype]
            other.set_relation(other=self, reltype=reltype_reverse, set_reverse=False)

        existing_relation = self.icalendar_component.get("related-to", None)
        existing_relations = (
            existing_relation
            if isinstance(existing_relation, list)
            else [existing_relation]
        )
        for rel in existing_relations:
            if rel == uid:
                return

        # without str(…), icalendar ignores properties
        #  because if type(uid) == vText
        #  then Component._encode does miss adding properties
        #  see https://github.com/collective/icalendar/issues/557
        #  workaround should be safe to remove if issue gets fixed
        uid = str(uid)
        self.icalendar_component.add(
            "related-to", uid, parameters={"RELTYPE": reltype}, encode=True
        )

        self.save()

    ## TODO: this method is undertested in the caldav library.
    ## However, as this consolidated and eliminated quite some duplicated code in the
    ## plann project, it is extensively tested in plann.
    def get_relatives(
        self,
        reltypes: Optional[Container[str]] = None,
        relfilter: Optional[Callable[[Any], bool]] = None,
        fetch_objects: bool = True,
        ignore_missing: bool = True,
    ) -> DefaultDict[str, Set[str]]:
        """
        By default, loads all objects pointed to by the RELATED-TO
        property and loads the related objects.

        It's possible to filter, either by passing a set or a list of
        acceptable relation types in reltypes, or by passing a lambda
        function in relfilter.

        TODO: Make it possible to  also check up reverse relationships

        TODO: this is partially overlapped by plann.lib._relships_by_type
        in the plann tool.  Should consolidate the code.
        """
        ret = defaultdict(set)
        relations = self.icalendar_component.get("RELATED-TO", [])
        if not isinstance(relations, list):
            relations = [relations]
        for rel in relations:
            if relfilter and not relfilter(rel):
                continue
            reltype = rel.params.get("RELTYPE", "PARENT")
            if reltypes and reltype not in reltypes:
                continue
            ret[reltype].add(str(rel))

        if fetch_objects:
            for reltype in ret:
                uids = ret[reltype]
                reltype_set = set()

                if self.parent is None:
                    raise ValueError("Unexpected value None for self.parent")

                if not isinstance(self.parent, Calendar):
                    raise ValueError(
                        "self.parent expected to be of type Calendar but it is not"
                    )

                for obj in uids:
                    try:
                        reltype_set.add(self.parent.object_by_uid(obj))
                    except error.NotFoundError:
                        if not ignore_missing:
                            raise

                ret[reltype] = reltype_set

        return ret

    def _get_icalendar_component(self, assert_one=False):
        """Returns the icalendar subcomponent - which should be an
        Event, Journal, Todo or FreeBusy from the icalendar class

        See also https://github.com/python-caldav/caldav/issues/232
        """
        self.load(only_if_unloaded=True)
        if not self.icalendar_instance:
            return None
        ret = [
            x
            for x in self.icalendar_instance.subcomponents
            if not isinstance(x, icalendar.Timezone)
        ]
        error.assert_(len(ret) == 1 or not assert_one)
        for x in ret:
            for cl in (
                icalendar.Event,
                icalendar.Journal,
                icalendar.Todo,
                icalendar.FreeBusy,
            ):
                if isinstance(x, cl):
                    return x
        error.assert_(False)

    def _set_icalendar_component(self, value) -> None:
        s = self.icalendar_instance.subcomponents
        i = [i for i in range(0, len(s)) if not isinstance(s[i], icalendar.Timezone)]
        if len(i) == 1:
            self.icalendar_instance.subcomponents[i[0]] = value
        else:
            my_instance = icalendar.Calendar()
            my_instance.add("prodid", "-//python-caldav//caldav//" + language)
            my_instance.add("version", "2.0")
            my_instance.add_component(value)
            self.icalendar_instance = my_instance

    icalendar_component = property(
        _get_icalendar_component,
        _set_icalendar_component,
        doc="icalendar component - should not be used with recurrence sets",
    )

    def get_due(self):
        """
        A VTODO may have due or duration set.  Return or calculate due.

        WARNING: this method is likely to be deprecated and moved to
        the icalendar library.  If you decide to use it, please put
        caldav<2.0 in the requirements.
        """
        i = self.icalendar_component
        if "DUE" in i:
            return i["DUE"].dt
        elif "DTEND" in i:
            return i["DTEND"].dt
        elif "DURATION" in i and "DTSTART" in i:
            return i["DTSTART"].dt + i["DURATION"].dt
        else:
            return None

    get_dtend = get_due

    def add_attendee(
        self, attendee, no_default_parameters: bool = False, **parameters
    ) -> None:
        """
        For the current (event/todo/journal), add an attendee.

        The attendee can be any of the following:
        * A principal
        * An email address prepended with "mailto:"
        * An email address without the "mailto:"-prefix
        * A two-item tuple containing a common name and an email address
        * (not supported, but planned: an ical text line starting with the word "ATTENDEE")

        Any number of attendee parameters can be given, those will be used
        as defaults unless no_default_parameters is set to True:

        partstat=NEEDS-ACTION
        cutype=UNKNOWN (unless a principal object is given)
        rsvp=TRUE
        role=REQ-PARTICIPANT
        schedule-agent is not set
        """
        from icalendar import vCalAddress, vText

        if isinstance(attendee, Principal):
            attendee_obj = attendee.get_vcal_address()
        elif isinstance(attendee, vCalAddress):
            attendee_obj = attendee
        elif isinstance(attendee, tuple):
            if attendee[1].startswith("mailto:"):
                attendee_obj = vCalAddress(attendee[1])
            else:
                attendee_obj = vCalAddress("mailto:" + attendee[1])
            attendee_obj.params["cn"] = vText(attendee[0])
        elif isinstance(attendee, str):
            if attendee.startswith("ATTENDEE"):
                raise NotImplementedError(
                    "do we need to support this anyway?  Should be trivial, but can't figure out how to do it with the icalendar.Event/vCalAddress objects right now"
                )
            elif attendee.startswith("mailto:"):
                attendee_obj = vCalAddress(attendee)
            elif "@" in attendee and ":" not in attendee and ";" not in attendee:
                attendee_obj = vCalAddress("mailto:" + attendee)
        else:
            error.assert_(False)
            attendee_obj = vCalAddress()

        ## TODO: if possible, check that the attendee exists
        ## TODO: check that the attendee will not be duplicated in the event.
        if not no_default_parameters:
            ## Sensible defaults:
            attendee_obj.params["partstat"] = "NEEDS-ACTION"
            if "cutype" not in attendee_obj.params:
                attendee_obj.params["cutype"] = "UNKNOWN"
            attendee_obj.params["rsvp"] = "TRUE"
            attendee_obj.params["role"] = "REQ-PARTICIPANT"
        params = {}
        for key in parameters:
            new_key = key.replace("_", "-")
            if parameters[key] is True:
                params[new_key] = "TRUE"
            else:
                params[new_key] = parameters[key]
        attendee_obj.params.update(params)
        ievent = self.icalendar_component
        ievent.add("attendee", attendee_obj)

    def is_invite_request(self) -> bool:
        self.load(only_if_unloaded=True)
        return self.icalendar_instance.get("method", None) == "REQUEST"

    def accept_invite(self, calendar: Optional[Calendar] = None) -> None:
        self._reply_to_invite_request("ACCEPTED", calendar)

    def decline_invite(self, calendar: Optional[Calendar] = None) -> None:
        self._reply_to_invite_request("DECLINED", calendar)

    def tentatively_accept_invite(self, calendar: Optional[Any] = None) -> None:
        self._reply_to_invite_request("TENTATIVE", calendar)

    ## TODO: DELEGATED is also a valid option, and for vtodos the
    ## partstat can also be set to COMPLETED and IN-PROGRESS.

    def _reply_to_invite_request(self, partstat, calendar) -> None:
        error.assert_(self.is_invite_request())
        if not calendar:
            calendar = self.client.principal().calendars()[0]
        ## we need to modify the icalendar code, update our own participant status
        self.icalendar_instance.pop("METHOD")
        self.change_attendee_status(partstat=partstat)
        self.get_property(cdav.ScheduleTag(), use_cached=True)
        try:
            calendar.save_event(self.data)
        except Exception:
            ## TODO - TODO - TODO
            ## RFC6638 does not seem to be very clear (or
            ## perhaps I should read it more thoroughly) neither on
            ## how to handle conflicts, nor if the reply should be
            ## posted to the "outbox", saved back to the same url or
            ## sent to a calendar.
            self.load()
            self.get_property(cdav.ScheduleTag(), use_cached=False)
            outbox = self.client.principal().schedule_outbox()
            if calendar.url != outbox.url:
                self._reply_to_invite_request(partstat, calendar=outbox)
            else:
                self.save()

    def copy(self, keep_uid: bool = False, new_parent: Optional[Any] = None) -> Self:
        """
        Events, todos etc can be copied within the same calendar, to another
        calendar or even to another caldav server
        """
        obj = self.__class__(
            parent=new_parent or self.parent,
            data=self.data,
            id=self.id if keep_uid else str(uuid.uuid1()),
        )
        if new_parent or not keep_uid:
            obj.url = obj.generate_url()
        else:
            obj.url = self.url
        return obj

    def load(self, only_if_unloaded: bool = False) -> Self:
        """
        (Re)load the object from the caldav server.
        """
        if only_if_unloaded and self.is_loaded():
            return self

        if self.url is None:
            raise ValueError("Unexpected value None for self.url")

        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        r = self.client.request(str(self.url))
        if r.status == 404:
            raise error.NotFoundError(errmsg(r))
        self.data = vcal.fix(r.raw)
        if "Etag" in r.headers:
            self.props[dav.GetEtag.tag] = r.headers["Etag"]
        if "Schedule-Tag" in r.headers:
            self.props[cdav.ScheduleTag.tag] = r.headers["Schedule-Tag"]
        return self

    ## TODO: self.id should either always be available or never
    def _find_id_path(self, id=None, path=None) -> None:
        """
        With CalDAV, every object has a URL.  With icalendar, every object
        should have a UID.  This UID may or may not be copied into self.id.

        This method will:

        0) if ID is given, assume that as the UID, and set it in the object
        1) if UID is given in the object, assume that as the ID
        2) if ID is not given, but the path is given, generate the ID from the
           path
        3) If neither ID nor path is given, use the uuid method to generate an
           ID (TODO: recommendation is to concat some timestamp, serial or
           random number and a domain)
        4) if no path is given, generate the URL from the ID
        """
        i = self._get_icalendar_component(assert_one=False)
        if not id and getattr(self, "id", None):
            id = self.id
        if not id:
            id = i.pop("UID", None)
            if id:
                id = str(id)
        if not path and getattr(self, "path", None):
            path = self.path
        if id is None and path is not None and str(path).endswith(".ics"):
            id = re.search("(/|^)([^/]*).ics", str(path)).group(2)
        if id is None:
            id = str(uuid.uuid1())
        i.pop("UID", None)
        i.add("UID", id)

        self.id = id

        for x in self.icalendar_instance.subcomponents:
            if not isinstance(x, icalendar.Timezone):
                error.assert_(x.get("UID", None) == self.id)

        if path is None:
            path = self.generate_url()
        else:
            path = self.parent.url.join(path)

        self.url = URL.objectify(path)

    def _put(self, retry_on_failure=True):
        ## SECURITY TODO: we should probably have a check here to verify that no such object exists already
        r = self.client.put(
            self.url, self.data, {"Content-Type": 'text/calendar; charset="utf-8"'}
        )
        if r.status == 302:
            path = [x[1] for x in r.headers if x[0] == "location"][0]
        elif r.status not in (204, 201):
            if retry_on_failure:
                ## This looks like a noop, but the object may be "cleaned".
                ## See https://github.com/python-caldav/caldav/issues/43
                self.vobject_instance
                return self._put(False)
            else:
                raise error.PutError(errmsg(r))

    def _create(self, id=None, path=None, retry_on_failure=True) -> None:
        ## We're efficiently running the icalendar code through the icalendar
        ## library.  This may cause data modifications and may "unfix"
        ## https://github.com/python-caldav/caldav/issues/43
        self._find_id_path(id=id, path=path)
        self._put()

    def generate_url(self):
        ## See https://github.com/python-caldav/caldav/issues/143 for the rationale behind double-quoting slashes
        ## TODO: should try to wrap my head around issues that arises when id contains weird characters.  maybe it's
        ## better to generate a new uuid here, particularly if id is in some unexpected format.
        if not self.id:
            self.id = self._get_icalendar_component(assert_one=False)["UID"]
        return self.parent.url.join(quote(self.id.replace("/", "%2F")) + ".ics")

    def change_attendee_status(self, attendee: Optional[Any] = None, **kwargs) -> None:
        if not attendee:
            if self.client is None:
                raise ValueError("Unexpected value None for self.client")

            attendee = self.client.principal_address or self.client.principal()

        cnt = 0

        if isinstance(attendee, Principal):
            attendee_emails = attendee.calendar_user_address_set()
            for addr in attendee_emails:
                try:
                    self.change_attendee_status(addr, **kwargs)
                    ## TODO: can probably just return now
                    cnt += 1
                except error.NotFoundError:
                    pass
            if not cnt:
                raise error.NotFoundError(
                    "Principal %s is not invited to event" % str(attendee)
                )
            error.assert_(cnt == 1)
            return

        ical_obj = self.icalendar_component
        attendee_lines = ical_obj["attendee"]
        if isinstance(attendee_lines, str):
            attendee_lines = [attendee_lines]
        strip_mailto = lambda x: str(x).lower().replace("mailto:", "")
        for attendee_line in attendee_lines:
            if strip_mailto(attendee_line) == strip_mailto(attendee):
                attendee_line.params.update(kwargs)
                cnt += 1
        if not cnt:
            raise error.NotFoundError("Participant %s not found in attendee list")
        error.assert_(cnt == 1)

    def save(
        self,
        no_overwrite: bool = False,
        no_create: bool = False,
        obj_type: Optional[str] = None,
        increase_seqno: bool = True,
        if_schedule_tag_match: bool = False,
    ) -> Self:
        """
        Save the object, can be used for creation and update.

        no_overwrite and no_create will check if the object exists.
        Those two are mutually exclusive.  Some servers don't support
        searching for an object uid without explicitly specifying what
        kind of object it should be, hence obj_type can be passed.
        obj_type is only used in conjunction with no_overwrite and
        no_create.

        Returns:
         * self

        """
        if (
            self._vobject_instance is None
            and self._data is None
            and self._icalendar_instance is None
        ):
            return self

        path = self.url.path if self.url else None

        if no_overwrite or no_create:
            ## SECURITY TODO: path names on the server does not
            ## necessarily map cleanly to UUIDs.  We need to do quite
            ## some refactoring here to ensure all corner cases are
            ## covered.  Doing a GET first to check if the resource is
            ## found and then a PUT also gives a potential race
            ## condition.  (Possibly the API gives no safe way to ensure
            ## a unique new calendar item is created to the server without
            ## overwriting old stuff or vice versa - it seems silly to me
            ## to do a PUT instead of POST when creating new data).
            ## TODO: the "find id"-logic is duplicated in _create,
            ## should be refactored
            if not self.id:
                for component in self.vobject_instance.getChildren():
                    if hasattr(component, "uid"):
                        self.id = component.uid.value
            if not self.id and no_create:
                raise error.ConsistencyError("no_create flag was set, but no ID given")
            existing = None
            ## some servers require one to explicitly search for the right kind of object.
            ## todo: would arguably be nicer to verify the type of the object and take it from there
            if not self.id:
                methods = []
            elif obj_type:
                methods = (getattr(self.parent, "%s_by_uid" % obj_type),)
            else:
                methods = (
                    self.parent.object_by_uid,
                    self.parent.event_by_uid,
                    self.parent.todo_by_uid,
                    self.parent.journal_by_uid,
                )
            for method in methods:
                try:
                    existing = method(self.id)
                    if no_overwrite:
                        raise error.ConsistencyError(
                            "no_overwrite flag was set, but object already exists"
                        )
                    break
                except error.NotFoundError:
                    pass

            if no_create and not existing:
                raise error.ConsistencyError(
                    "no_create flag was set, but object does not exists"
                )

        if increase_seqno and b"SEQUENCE" in to_wire(self.data):
            seqno = self.icalendar_component.pop("SEQUENCE", None)
            if seqno is not None:
                self.icalendar_component.add("SEQUENCE", seqno + 1)

        self._create(id=self.id, path=path)
        return self

    def is_loaded(self):
        return (
            self._data or self._vobject_instance or self._icalendar_instance
        ) and self.data.count("BEGIN:") > 1

    def has_component(self):
        return (
            self._data
            or self._vobject_instance
            or (self._icalendar_instance and self.icalendar_component)
        ) and self.data.count("BEGIN:VEVENT") + self.data.count(
            "BEGIN:VTODO"
        ) + self.data.count(
            "BEGIN:VJOURNAL"
        ) > 0

    def __str__(self) -> str:
        return "%s: %s" % (self.__class__.__name__, self.url)

    ## implementation of the properties self.data,
    ## self.vobject_instance and self.icalendar_instance follows.  The
    ## rule is that only one of them can be set at any time, this
    ## since vobject_instance and icalendar_instance are mutable,
    ## and any modification to those instances should apply
    def _set_data(self, data):
        ## The __init__ takes a data attribute, and it should be allowable to
        ## set it to a vobject object or an icalendar object, hence we should
        ## do type checking on the data (TODO: but should probably use
        ## isinstance rather than this kind of logic
        if type(data).__module__.startswith("vobject"):
            self._set_vobject_instance(data)
            return self

        if type(data).__module__.startswith("icalendar"):
            self._set_icalendar_instance(data)
            return self

        self._data = vcal.fix(data)
        self._vobject_instance = None
        self._icalendar_instance = None
        return self

    def _get_data(self):
        if self._data:
            return to_normal_str(self._data)
        elif self._vobject_instance:
            return to_normal_str(self._vobject_instance.serialize())
        elif self._icalendar_instance:
            return to_normal_str(self._icalendar_instance.to_ical())
        return None

    def _get_wire_data(self):
        if self._data:
            return to_wire(self._data)
        elif self._vobject_instance:
            return to_wire(self._vobject_instance.serialize())
        elif self._icalendar_instance:
            return to_wire(self._icalendar_instance.to_ical())
        return None

    data: Any = property(
        _get_data, _set_data, doc="vCal representation of the object as normal string"
    )
    wire_data = property(
        _get_wire_data,
        _set_data,
        doc="vCal representation of the object in wire format (UTF-8, CRLN)",
    )

    def _set_vobject_instance(self, inst: vobject.base.Component):
        self._vobject_instance = inst
        self._data = None
        self._icalendar_instance = None
        return self

    def _get_vobject_instance(self) -> Optional[vobject.base.Component]:
        if not self._vobject_instance:
            if self._get_data() is None:
                return None
            try:
                self._set_vobject_instance(
                    vobject.readOne(to_unicode(self._get_data()))  # type: ignore
                )
            except:
                log.critical(
                    "Something went wrong while loading icalendar data into the vobject class.  ical url: "
                    + str(self.url)
                )
                raise
        return self._vobject_instance

    vobject_instance: VBase = property(
        _get_vobject_instance,
        _set_vobject_instance,
        doc="vobject instance of the object",
    )

    def _set_icalendar_instance(self, inst):
        self._icalendar_instance = inst
        self._data = None
        self._vobject_instance = None
        return self

    def _get_icalendar_instance(self):
        if not self._icalendar_instance:
            if not self.data:
                return None
            self.icalendar_instance = icalendar.Calendar.from_ical(
                to_unicode(self.data)
            )
        return self._icalendar_instance

    icalendar_instance: Any = property(
        _get_icalendar_instance,
        _set_icalendar_instance,
        doc="icalendar instance of the object",
    )

    def get_duration(self) -> timedelta:
        """According to the RFC, either DURATION or DUE should be set
        for a task, but never both - implicitly meaning that DURATION
        is the difference between DTSTART and DUE (personally I
        believe that's stupid.  If a task takes five minutes to
        complete - say, fill in some simple form that should be
        delivered before midnight at new years eve, then it feels
        natural for me to define "duration" as five minutes, DTSTART
        to "some days before new years eve" and DUE to 20xx-01-01
        00:00:00 - but I digress.

        This method will return DURATION if set, otherwise the
        difference between DUE and DTSTART (if both of them are set).

        TODO: should be fixed for Event class as well (only difference
        is that DTEND is used rather than DUE) and possibly also for
        Journal (defaults to one day, probably?)

        WARNING: this method is likely to be deprecated and moved to
        the icalendar library.  If you decide to use it, please put
        caldav<3.0 in the requirements.
        """
        i = self.icalendar_component
        return self._get_duration(i)

    def _get_duration(self, i):
        if "DURATION" in i:
            return i["DURATION"].dt
        elif "DTSTART" in i and self._ENDPARAM in i:
            end = i[self._ENDPARAM].dt
            start = i["DTSTART"].dt
            ## We do have a problem here if one is a date and the other is a
            ## datetime.  This is NOT explicitly defined as a technical
            ## breach in the RFC, so we need to work around it.
            if isinstance(end, datetime) != isinstance(start, datetime):
                start = datetime(start.year, start.month, start.day)
                end = datetime(end.year, end.month, end.day)
            return end - start
        elif "DTSTART" in i and not isinstance(i["DTSTART"], datetime):
            return timedelta(days=1)
        else:
            return timedelta(0)

    ## for backward-compatibility - may be changed to
    ## icalendar_instance in version 1.0
    instance: VBase = vobject_instance


class Event(CalendarObjectResource):
    """
    The `Event` object is used to represent an event (VEVENT).

    As of 2020-12 it adds nothing to the inheritated class.  (I have
    frequently asked myself if we need those subclasses ... perhaps
    not)
    """

    _ENDPARAM = "DTEND"
    pass


class Journal(CalendarObjectResource):
    """
    The `Journal` object is used to represent a journal entry (VJOURNAL).

    As of 2020-12 it adds nothing to the inheritated class.  (I have
    frequently asked myself if we need those subclasses ... perhaps
    not)
    """

    pass


class FreeBusy(CalendarObjectResource):
    """
    The `FreeBusy` object is used to represent a freebusy response from
    the server.  __init__ is overridden, as a FreeBusy response has no
    URL or ID.  The inheritated methods .save and .load is moot and
    will probably throw errors (perhaps the class hierarchy should be
    rethought, to prevent the FreeBusy from inheritating moot methods)

    Update: With RFC6638 a freebusy object can have a URL and an ID.
    """

    def __init__(
        self,
        parent,
        data,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        id: Optional[Any] = None,
    ) -> None:
        CalendarObjectResource.__init__(
            self, client=parent.client, url=url, data=data, parent=parent, id=id
        )


class Todo(CalendarObjectResource):
    """The `Todo` object is used to represent a todo item (VTODO).  A
    Todo-object can be completed.  Extra logic for different ways to
    complete one recurrence of a recurrent todo.  Extra logic to
    handle due vs duration.
    """

    _ENDPARAM = "DUE"

    def _next(self, ts=None, i=None, dtstart=None, rrule=None, by=None, no_count=True):
        """Special logic to fint the next DTSTART of a recurring
        just-completed task.

        If any BY*-parameters are present, assume the task should have
        fixed deadlines and preserve information from the previous
        dtstart.  If no BY*-parameters are present, assume the
        frequency is meant to be the interval between the tasks.

        Examples:

        1) Garbage collection happens every week on a Tuesday, but
        never earlier than 09 in the morning.  Hence, it may be
        important to take out the thrash Monday evenings or Tuesday
        morning.  DTSTART of the original task is set to Tuesday
        2022-11-01T08:50, DUE to 09:00.

        1A) Task is completed 07:50 on the 1st of November.  Next
        DTSTART should be Tuesday the 7th of November at 08:50.

        1B) Task is completed 09:15 on the 1st of November (which is
        probably OK, since they usually don't come before 09:30).
        Next DTSTART should be Tuesday the 7th of November at 08:50.

        1C) Task is completed at the 5th of November.  We've lost the
        DUE, but the calendar has no idea weather the DUE was a very
        hard due or not - and anyway, probably we'd like to do it
        again on Tuesday, so next DTSTART should be Tuesday the 7th of
        November at 08:50.

        1D) Task is completed at the 7th of November at 07:50.  Next
        DTSTART should be one hour later.  Now, this is very silly,
        but an algorithm cannot do guesswork on weather it's silly or
        not.  If DTSTART would be set to the earliest possible time
        one could start thinking on this task (like, Monday evening),
        then we would get Tue the 14th of November, which does make
        sense.  Unfortunately the icalendar standard does not specify
        what should be used for DTSTART and DURATION/DUE.

        1E) Task is completed on the 7th of November at 08:55.  This
        efficiently means we've lost the 1st of November recurrence
        but have done the 7th of November recurrence instead, so next
        timestamp will be the 14th of November.

        2) Floors at home should be cleaned like once a week, but
        there is no fixed deadline for it.  For some people it may
        make sense to have a routine doing it i.e. every Tuesday, but
        this is not a strict requirement.  If it wasn't done one
        Tuesday, it's probably even more important to do it Wednesday.
        If the floor was cleaned on a Saturday, it probably doesn't
        make sense cleaning it again on Tuesday, but it probably
        shouldn't wait until next Tuesday.  Rrule is set to
        FREQ=WEEKLY, but without any BYDAY.  The original VTODO is set
        up with DTSTART 16:00 on Tuesday the 1st of November and DUE
        17:00.  After 17:00 there will be dinner, so best to get it
        done before that.

        2A) Floor cleaning was finished 14:30.  The next recurrence
        has DTSTART set to 13:30 (and DUE set to 14:30).  The idea
        here is that since the floor starts accumulating dirt right
        after 14:30, obviously it is overdue at 16:00 Tuesday the 7th.

        2B) Floor cleaning was procrastinated with one day and
        finished Wednesday at 14:30.  Next instance will be Wednesday
        in a week, at 14:30.

        2C) Floor cleaning was procrastinated with two weeks and
        finished Tuesday the 14th at 14:30. Next instance will be
        Tuesday the 21st at 14:30.

        While scenario 2 is the most trivial to implement, it may not
        be the correct understanding of the RFC, and it may be tricky
        to get the RECURRENCE-ID set correctly.

        """
        if not i:
            i = self.icalendar_component
        if not rrule:
            rrule = i["RRULE"]
        if not dtstart:
            if by is True or (
                by is None and any((x for x in rrule if x.startswith("BY")))
            ):
                if "DTSTART" in i:
                    dtstart = i["DTSTART"].dt
                else:
                    dtstart = ts or datetime.now()
            else:
                dtstart = ts or datetime.now() - self._get_duration(i)
        ## dtstart should be compared to the completion timestamp, which
        ## is set in UTC in the complete() method.  However, dtstart
        ## may be a naïve or a floating timestamp
        ## (TODO: what if it's a date?)
        ## (TODO: we need test code for those corner cases!)
        if hasattr(dtstart, "astimezone"):
            dtstart = dtstart.astimezone(timezone.utc)
        if not ts:
            ts = dtstart
        ## Counting is taken care of other places
        if no_count and "COUNT" in rrule:
            rrule = rrule.copy()
            rrule.pop("COUNT")
        rrule = rrulestr(rrule.to_ical().decode("utf-8"), dtstart=dtstart)
        return rrule.after(ts)

    def _reduce_count(self, i=None) -> bool:
        if not i:
            i = self.icalendar_component
        if "COUNT" in i["RRULE"]:
            if i["RRULE"]["COUNT"][0] == 1:
                return False
            i["RRULE"]["COUNT"][0] -= 1
        return True

    def _complete_recurring_safe(self, completion_timestamp):
        """This mode will create a new independent task which is
        marked as completed, and modify the existing recurring task.
        It is probably the most safe way to handle the completion of a
        recurrence of a recurring task, though the link between the
        completed task and the original task is lost.
        """
        ## If count is one, then it is not really recurring
        if not self._reduce_count():
            return self.complete(handle_rrule=False)
        next_dtstart = self._next(completion_timestamp)
        if not next_dtstart:
            return self.complete(handle_rrule=False)

        completed = self.copy()
        completed.url = self.parent.url.join(completed.id + ".ics")
        completed.icalendar_component.pop("RRULE")
        completed.save()
        completed.complete()

        duration = self.get_duration()
        i = self.icalendar_component
        i.pop("DTSTART", None)
        i.add("DTSTART", next_dtstart)
        self.set_duration(duration, movable_attr="DUE")

        self.save()

    def _complete_recurring_thisandfuture(self, completion_timestamp) -> None:
        """The RFC is not much helpful, a lot of guesswork is needed
        to consider what the "right thing" to do wrg of a completion of
        recurring tasks is ... but this is my shot at it.

        1) The original, with rrule, will be kept as it is.  The rrule
        string is fetched from the first subcomponent of the
        icalendar.

        2) If there are multiple recurrence instances in subcomponents
        and the last one is marked with RANGE=THISANDFUTURE, then
        select this one.  If it has the rrule property set, use this
        rrule rather than the original one.  Drop the RANGE parameter.
        Calculate the next RECURRENCE-ID from the DTSTART of this
        object.  Mark task as completed.  Increase SEQUENCE.

        3) Create a new recurrence instance with RANGE=THISANDFUTURE,
        without RRULE set (Ref
        https://github.com/Kozea/Radicale/issues/1264).  Set the
        RECURRENCE-ID to the one calculated in #2.  Calculate the
        DTSTART based on rrule and completion timestamp/date.
        """
        recurrences = self.icalendar_instance.subcomponents
        orig = recurrences[0]
        if "STATUS" not in orig:
            orig["STATUS"] = "NEEDS-ACTION"

        if len(recurrences) == 1:
            ## We copy the original one
            just_completed = orig.copy()
            just_completed.pop("RRULE")
            just_completed.add(
                "RECURRENCE-ID", orig.get("DTSTART", completion_timestamp)
            )
            seqno = just_completed.pop("SEQUENCE", 0)
            just_completed.add("SEQUENCE", seqno + 1)
            recurrences.append(just_completed)

        prev = recurrences[-1]
        rrule = prev.get("RRULE", orig["RRULE"])
        thisandfuture = prev.copy()
        seqno = thisandfuture.pop("SEQUENCE", 0)
        thisandfuture.add("SEQUENCE", seqno + 1)

        ## If we have multiple recurrences, assume the last one is a THISANDFUTURE.
        ## (Otherwise, the data is coming from another client ...)
        ## The RANGE parameter needs to be removed
        if len(recurrences) > 2:
            if prev["RECURRENCE-ID"].params.get("RANGE", None) == "THISANDFUTURE":
                prev["RECURRENCE-ID"].params.pop("RANGE")
            else:
                raise NotImplementedError(
                    "multiple instances found, but last one is not of type THISANDFUTURE, possibly this has been created by some incompatible client, but we should deal with it"
                )
        self._complete_ical(prev, completion_timestamp)

        thisandfuture.pop("RECURRENCE-ID", None)
        thisandfuture.add("RECURRENCE-ID", self._next(i=prev, rrule=rrule))
        thisandfuture["RECURRENCE-ID"].params["RANGE"] = "THISANDFUTURE"
        rrule2 = thisandfuture.pop("RRULE", None)

        ## Counting logic
        if rrule2 is not None:
            count = rrule2.get("COUNT", None)
            if count is not None and count[0] in (0, 1):
                for i in recurrences:
                    self._complete_ical(i, completion_timestamp=completion_timestamp)
            thisandfuture.add("RRULE", rrule2)
        else:
            count = rrule.get("COUNT", None)
            if count is not None and count[0] <= len(
                [x for x in recurrences if not self._is_pending(x)]
            ):
                self._complete_ical(
                    recurrences[0], completion_timestamp=completion_timestamp
                )
                self.save(increase_seqno=False)
                return

        rrule = rrule2 or rrule

        duration = self._get_duration(i=prev)
        thisandfuture.pop("DTSTART", None)
        thisandfuture.pop("DUE", None)
        next_dtstart = self._next(i=prev, rrule=rrule, ts=completion_timestamp)
        thisandfuture.add("DTSTART", next_dtstart)
        self._set_duration(i=thisandfuture, duration=duration, movable_attr="DUE")
        self.icalendar_instance.subcomponents.append(thisandfuture)
        self.save(increase_seqno=False)

    def complete(
        self,
        completion_timestamp: Optional[datetime] = None,
        handle_rrule: bool = False,
        rrule_mode: Literal["safe", "this_and_future"] = "safe",
    ) -> None:
        """Marks the task as completed.

        Parameters:
         * completion_timestamp - datetime object.  Defaults to
           datetime.now().
         * handle_rrule - if set to True, the library will try to be smart if
           the task is recurring.  The default is False, for backward
           compatibility.  I may consider making this one mandatory.
         * rrule_mode -   The RFC leaves a lot of room for interpretation on how
           to handle recurring tasks, and what works on one server may break at
           another.  The following modes are accepted:
           * this_and_future - see doc for _complete_recurring_thisandfuture for details
           * safe - see doc for _complete_recurring_safe for details
        """
        if not completion_timestamp:
            completion_timestamp = datetime.now(timezone.utc)

        if "RRULE" in self.icalendar_component and handle_rrule:
            return getattr(self, "_complete_recurring_%s" % rrule_mode)(
                completion_timestamp
            )
        self._complete_ical(completion_timestamp=completion_timestamp)
        self.save()

    def _complete_ical(self, i=None, completion_timestamp=None) -> None:
        ## my idea was to let self.complete call this one ... but self.complete
        ## should use vobject and not icalendar library due to backward compatibility.
        if i is None:
            i = self.icalendar_component
        assert self._is_pending(i)
        status = i.pop("STATUS", None)
        i.add("STATUS", "COMPLETED")
        i.add("COMPLETED", completion_timestamp)

    def _is_pending(self, i=None) -> Optional[bool]:
        if i is None:
            i = self.icalendar_component
        if i.get("COMPLETED", None) is not None:
            return False
        if i.get("STATUS", None) in ("NEEDS-ACTION", "IN-PROCESS"):
            return True
        if i.get("STATUS", None) in ("CANCELLED", "COMPLETED"):
            return False
        if "STATUS" not in i:
            return True
        ## input data does not conform to the RFC
        assert False

    def uncomplete(self) -> None:
        """Undo completion - marks a completed task as not completed"""
        ### TODO: needs test code for code coverage!
        ## (it has been tested through the calendar-cli test code)
        if not hasattr(self.vobject_instance.vtodo, "status"):
            self.vobject_instance.vtodo.add("status")
        self.vobject_instance.vtodo.status.value = "NEEDS-ACTION"
        if hasattr(self.vobject_instance.vtodo, "completed"):
            self.vobject_instance.vtodo.remove(self.vobject_instance.vtodo.completed)
        self.save()

    ## TODO: should be moved up to the base class
    def set_duration(self, duration, movable_attr="DTSTART"):
        """
        If DTSTART and DUE/DTEND is already set, one of them should be moved.  Which one?  I believe that for EVENTS, the DTSTART should remain constant and DTEND should be moved, but for a task, I think the due date may be a hard deadline, hence by default we'll move DTSTART.

        TODO: can this be written in a better/shorter way?

        WARNING: this method is likely to be deprecated and moved to
        the icalendar library.  If you decide to use it, please put
        caldav<2.0 in the requirements.
        """
        i = self.icalendar_component
        return self._set_duration(i, duration, movable_attr)

    def _set_duration(self, i, duration, movable_attr="DTSTART") -> None:
        if ("DUE" in i or "DURATION" in i) and "DTSTART" in i:
            i.pop(movable_attr, None)
            if movable_attr == "DUE":
                i.pop("DURATION", None)
            if movable_attr == "DTSTART":
                i.add("DTSTART", i["DUE"].dt - duration)
            elif movable_attr == "DUE":
                i.add("DUE", i["DTSTART"].dt + duration)
        elif "DUE" in i:
            i.add("DTSTART", i["DUE"].dt - duration)
        elif "DTSTART" in i:
            i.add("DUE", i["DTSTART"].dt + duration)
        else:
            if "DURATION" in i:
                i.pop("DURATION")
            i.add("DURATION", duration)

    def set_due(self, due, move_dtstart=False, check_dependent=False):
        """The RFC specifies that a VTODO cannot have both due and
        duration, so when setting due, the duration field must be
        evicted

        check_dependent=True will raise some error if there exists a
        parent calendar component (through RELATED-TO), and the parents
        due or dtend is before the new dtend).

        WARNING: this method is likely to be deprecated and parts of
        it moved to the icalendar library.  If you decide to use it,
        please put caldav<2.0 in the requirements.

        WARNING: the check_dependent-logic may be rewritten to support
        RFC9253 in 1.x already
        """
        i = self.icalendar_component
        if hasattr(due, "tzinfo") and not due.tzinfo:
            due = due.astimezone(timezone.utc)
        if check_dependent:
            parents = self.get_relatives({"PARENT"})
            for parent in parents["PARENT"]:
                pend = parent.get_dtend()
                ## Make sure both timestamps aren't "naive":
                if hasattr(pend, "tzinfo") and not pend.tzinfo:
                    pend = pend.astimezone(timezone.utc)
                ## pend and due may be date and datetime, then they cannot be compared directly
                if pend and pend.strftime("%s") < due.strftime("%s"):
                    if check_dependent == "return":
                        return parent
                    raise error.ConsistencyError(
                        "parent object has due/end %s, cannot procrastinate child object without first procrastinating parent object"
                    )
        duration = self.get_duration()
        i.pop("DURATION", None)
        i.pop("DUE", None)

        if move_dtstart and duration and "DTSTART" in i:
            i.pop("DTSTART")
            i.add("DTSTART", due - duration)

        i.add("DUE", due)
