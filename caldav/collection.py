"""
I'm trying to be consistent with the terminology in the RFCs:

CalendarSet is a collection of Calendars
Calendar is a collection of CalendarObjectResources
Principal is not a collection, but holds a CalendarSet.

There are also some Mailbox classes to deal with RFC6638.

A SynchronizableCalendarObjectCollection contains a local copy of objects from a calendar on the server.
"""
import logging
import sys
import uuid
import warnings
from datetime import datetime
from typing import Any
from typing import List
from typing import Optional
from typing import Tuple
from typing import TYPE_CHECKING
from typing import TypeVar
from typing import Union
from urllib.parse import ParseResult
from urllib.parse import quote
from urllib.parse import SplitResult
from urllib.parse import unquote

import icalendar

try:
    from typing import ClassVar, Optional, Union, Type

    TimeStamp = Optional[Union[date, datetime]]
except:
    pass

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

from .calendarobjectresource import CalendarObjectResource
from .calendarobjectresource import Event
from .calendarobjectresource import FreeBusy
from .calendarobjectresource import Journal
from .calendarobjectresource import Todo
from .davobject import DAVObject
from .elements.cdav import CalendarData
from .elements import cdav
from .elements import dav
from .lib import error
from .lib import vcal
from .lib.python_utilities import to_wire
from .lib.url import URL

_CC = TypeVar("_CC", bound="CalendarObjectResource")
log = logging.getLogger("caldav")


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
                if not cal_id:
                    continue
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

        Args:
          name: the display name of the new calendar
          cal_id: the uuid of the new calendar
          supported_calendar_component_set: what kind of objects
           (EVENT, VTODO, VFREEBUSY, VJOURNAL) the calendar should handle.
           Should be set to ['VTODO'] when creating a task list in Zimbra -
           in most other cases the default will be OK.

        Returns:
          Calendar(...)-object
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

        Args:
          name: return the calendar with this display name
          cal_id: return the calendar with this calendar id or URL

        Returns:
          Calendar(...)-object
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
            cals = self.calendars()
            if not cals:
                raise error.NotFoundError("no calendars found")
            return cals[0]

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
        calendar_home_set: URL = None,
        **kwargs,  ## to be passed to super.__init__
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
        """Sends a freebusy-request for some attendee to the server
        as per RFC6638
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
            except Exception as e:
                ## TODO: investigate.  Those asserts break.
                try:
                    current_display_name = self.get_display_name()
                    error.assert_(current_display_name == name)
                except:
                    log.warning(
                        "calendar server does not support display name on calendar?  Ignoring",
                        exc_info=True,
                    )

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

    def save_object(
        self,
        ## TODO: this should be made optional.  The class may be given in the ical object.
        ## TODO: also, accept a string.
        objclass: Type[DAVObject],
        ## TODO: ical may also be a vobject or icalendar instance
        ical: Optional[str] = None,
        no_overwrite: bool = False,
        no_create: bool = False,
        **ical_data,
    ) -> "CalendarResourceObject":
        """Add a new event to the calendar, with the given ical.

        Args:
          objclass: Event, Journal or Todo
          ical: ical object (text, icalendar or vobject instance)
          no_overwrite: existing calendar objects should not be overwritten
          no_create: don't create a new object, existing calendar objects should be updated
          dt_start: properties to be inserted into the icalendar object
        , dt_end: properties to be inserted into the icalendar object
          summary: properties to be inserted into the icalendar object
          alarm_trigger: when given, one alarm will be added
          alarm_action: when given, one alarm will be added
          alarm_attach: when given, one alarm will be added

        Note that the list of parameters going into the icalendar
        object and alamrs is not complete.  Refer to the RFC or the
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

    ## TODO: maybe we should deprecate those three
    def save_event(self, *largs, **kwargs) -> "Event":
        """
        Returns ``self.save_object(Event, ...)`` - see :class:`save_object`
        """
        return self.save_object(Event, *largs, **kwargs)

    def save_todo(self, *largs, **kwargs) -> "Todo":
        """
        Returns ``self.save_object(Todo, ...)`` - so see :class:`save_object`
        """
        return self.save_object(Todo, *largs, **kwargs)

    def save_journal(self, *largs, **kwargs) -> "Journal":
        """
        Returns ``self.save_object(Journal, ...)`` - so see :class:`save_object`
        """
        return self.save_object(Journal, *largs, **kwargs)

    ## legacy aliases
    ## TODO: should be deprecated

    ## TODO: think more through this - is `save_foo` better than `add_foo`?
    ## `save_foo` should not be used for updating existing content on the
    ## calendar!
    add_object = save_object
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

    # def data2object_class

    def _multiget(
        self, event_urls: Iterable[URL], raise_notfound: bool = False
    ) -> Iterable[str]:
        """
        get multiple events' data.
        TODO: Does it overlap the _request_report_build_resultlist method
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
        if raise_notfound:
            for href in response.statuses:
                status = response.statuses[href]
                if status and "404" in status:
                    raise error.NotFoundError(f"Status {status} in {href}")
        for r in results:
            yield (r, results[r][cdav.CalendarData.tag])

    ## Replace the last lines with
    def multiget(
        self, event_urls: Iterable[URL], raise_notfound: bool = False
    ) -> Iterable[_CC]:
        """
        get multiple events' data
        TODO: Does it overlap the _request_report_build_resultlist method?
        @author mtorange@gmail.com (refactored by Tobias)
        """
        results = self._multiget(event_urls, raise_notfound=raise_notfound)
        for url, data in results:
            yield self._calendar_comp_class_by_data(data)(
                self.client,
                url=self.url.join(url),
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
        end: Optional[datetime] = None,
        compfilter: None = "VEVENT",
        expand: Union[bool, Literal["maybe"]] = "maybe",
        verify_expand: bool = False,
    ) -> Sequence["CalendarObjectResource"]:
        # type (TimeStamp, TimeStamp, str, str) -> CalendarObjectResource
        """Deprecated.  Use self.search() instead.

        Search events by date in the calendar.

        Args
         start : defaults to datetime.today().
         end : same as above.
         compfilter : defaults to events only.  Set to None to fetch all calendar components.
         expand : should recurrent events be expanded?  (to preserve backward-compatibility the default "maybe" will be changed into True unless the date_search is open-ended)
         verify_expand : not in use anymore, but kept for backward compatibility

        Returns:
         * [CalendarObjectResource(), ...]

        Recurring events are expanded if they are occurring during the
        specified time frame and if an end timestamp is given.

        Note that this is a deprecated method.  The `search` method is
        nearly equivalent.  Differences: default for ``compfilter`` is
        to search for all objects, default for ``expand`` is
        ``False``, and it has a different default
        ``split_expanded=True``.
        """
        ## date_search will probably disappear in 3.0
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
            expand = end

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
        expand: bool = False,
        server_expand: bool = False,
        split_expanded: bool = True,
        props: Optional[List[cdav.CalendarData]] = None,
        **kwargs,
    ) -> List[_CC]:
        """Sends a search request towards the server, processes the
        results if needed and returns the objects found.

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
        if expand not in (True, False):
            warnings.warn(
                "in cal.search(), expand should be a bool",
                DeprecationWarning,
                stacklevel=2,
            )
            if expand == "client":
                expand = True
            if expand == "server":
                server_expand = True
                expand = False

        if expand or server_expand:
            if not kwargs.get("start") or not kwargs.get("end"):
                raise error.ReportError("can't expand without a date range")

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
                    if any(
                        x.get("STATUS") not in ("COMPLETED", "CANCELLED")
                        for x in item.icalendar_instance.subcomponents
                    ):
                        objects.append(item)
        else:
            if not xml:
                if server_expand:
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
                        sort_reverse=sort_reverse,
                        expand=expand,
                        server_expand=server_expand,
                        split_expanded=split_expanded,
                        props=props,
                        **kwargs,
                    )
                raise

        obj2 = []

        for o in objects:
            ## This would not be needed if the servers would follow the standard ...
            ## TODO: use self.calendar_multiget - see https://github.com/python-caldav/caldav/issues/487
            try:
                o.load(only_if_unloaded=True)
                obj2.append(o)
            except:
                logging.error(
                    "Server does not want to reveal details about the calendar object",
                    exc_info=True,
                )
                pass
        objects = obj2

        ## Google sometimes returns empty objects
        objects = [o for o in objects if o.has_component()]

        if expand:
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
                    o.expand_rrule(start, end, include_completed=include_completed)

            ## An expanded recurring object comes as one Event() with
            ## icalendar data containing multiple objects.  The caller may
            ## expect multiple Event()s.  This code splits events into
            ## separate objects:
        if (expand or server_expand) and split_expanded:
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
            ## ref https://github.com/python-caldav/caldav/issues/448 - allow strings instead of a sequence here
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
            if isinstance(sort_keys, str):
                sort_keys = (sort_keys,)
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
        journal=None,
        filters=None,
        expand=None,
        start=None,
        end=None,
        props=None,
        alarm_start=None,
        alarm_end=None,
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

        if alarm_start or alarm_end:
            filters.append(
                cdav.CompFilter("VALARM") + cdav.TimeRange(alarm_start, alarm_end)
            )

        ## Deal with event, todo, journal or comp_class
        for flagged, comp_name, comp_class_ in (
            (event, "VEVENT", Event),
            (todo, "VTODO", Todo),
            (journal, "VJOURNAL", Journal),
        ):
            if flagged is not None:
                if not flagged:
                    raise NotImplementedError(
                        f"Negated search for {comp_name} not supported yet"
                    )
                if flagged:
                    ## event/journal/todo is set, we adjust comp_class accordingly
                    if comp_class is not None and comp_class is not comp_class:
                        raise error.ConsistencyError(
                            f"inconsistent search parameters - comp_class = {comp_class}, want {comp_class_}"
                        )
                    comp_class = comp_class_

            if comp_class == comp_class_:
                comp_filter = cdav.CompFilter(comp_name)

        if comp_class and not comp_filter:
            raise error.ConsistencyError(
                f"unsupported comp class {comp_class} for search"
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

        Args:
          start : defaults to datetime.today().
          end : same as above.

        Returns:
          [FreeBusy(), ...]
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
        Fetches a list of todo events (this is a wrapper around search)

        Args:
          sort_keys: use this field in the VTODO for sorting (iterable of lower case string, i.e. ('priority','due')).
          include_completed: boolean - by default, only pending tasks are listed
          sort_key: DEPRECATED, for backwards compatibility with version 0.4.
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
        comp_filter: Optional[cdav.CompFilter] = None,
        comp_class: Optional["CalendarObjectResource"] = None,
    ) -> "Event":
        """
        Get one event from the calendar.

        Args:
         uid: the event uid
         comp_class: filter by component type (Event, Todo, Journal)
         comp_filter: for backward compatibility

        Returns:
         Event() or None
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
        """
        Returns the task with the given uid (wraps around :class:`object_by_uid`)
        """
        return self.object_by_uid(uid, comp_filter=cdav.CompFilter("VTODO"))

    def event_by_uid(self, uid: str) -> "CalendarObjectResource":
        """
        Returns the event with the given uid (wraps around :class:`object_by_uid`)
        """
        return self.object_by_uid(uid, comp_filter=cdav.CompFilter("VEVENT"))

    def journal_by_uid(self, uid: str) -> "CalendarObjectResource":
        """
        Returns the journal with the given uid (wraps around :class:`object_by_uid`)
        """
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
