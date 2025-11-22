#!/usr/bin/env python
"""
Async Calendar Object Resources - Event, Todo, Journal, FreeBusy.

This is the async implementation that the sync wrapper delegates to.
"""
import logging
import re
import sys
import uuid
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import ClassVar
from typing import List
from typing import Optional
from typing import Set
from typing import TYPE_CHECKING
from typing import Union
from urllib.parse import ParseResult
from urllib.parse import quote
from urllib.parse import SplitResult

import icalendar
from icalendar import vCalAddress
from icalendar import vText

if TYPE_CHECKING:
    from caldav._async.davclient import AsyncDAVClient

if sys.version_info < (3, 9):
    from typing import Callable, Container
    from typing_extensions import DefaultDict
else:
    from collections import defaultdict as DefaultDict
    from collections.abc import Callable, Container

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

from caldav._async.davobject import AsyncDAVObject
from caldav.elements import cdav, dav
from caldav.lib import error, vcal
from caldav.lib.error import errmsg
from caldav.lib.python_utilities import to_normal_str, to_unicode, to_wire
from caldav.lib.url import URL


log = logging.getLogger("caldav")


class AsyncCalendarObjectResource(AsyncDAVObject):
    """Async Calendar Object Resource - base class for Event, Todo, Journal, FreeBusy."""

    RELTYPE_REVERSE_MAP: ClassVar = {
        "PARENT": "CHILD",
        "CHILD": "PARENT",
        "SIBLING": "SIBLING",
        "DEPENDS-ON": "FINISHTOSTART",
        "FINISHTOSTART": "DEPENDENT",
    }

    _ENDPARAM = None
    _vobject_instance = None
    _icalendar_instance = None
    _data = None

    def __init__(
        self,
        client: Optional["AsyncDAVClient"] = None,
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
        super(AsyncCalendarObjectResource, self).__init__(
            client=client, url=url, parent=parent, id=id, props=props
        )
        if data is not None:
            self.data = data
            if id:
                old_id = self.icalendar_component.pop("UID", None)
                self.icalendar_component.add("UID", id)

    def _get_icalendar_component(self, assert_one=False):
        """Returns the icalendar subcomponent."""
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
            my_instance.add("prodid", self.icalendar_instance["prodid"])
            my_instance.add("version", self.icalendar_instance["version"])
            my_instance.add_component(value)
            self.icalendar_instance = my_instance

    icalendar_component = property(
        _get_icalendar_component,
        _set_icalendar_component,
        doc="icalendar component",
    )
    component = icalendar_component

    def _set_data(self, data):
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

    data: Any = property(_get_data, _set_data, doc="vCal representation")
    wire_data = property(_get_wire_data, _set_data, doc="vCal in wire format")

    def _set_vobject_instance(self, inst):
        self._vobject_instance = inst
        self._data = None
        self._icalendar_instance = None
        return self

    def _get_vobject_instance(self):
        try:
            import vobject
        except ImportError:
            logging.critical("vobject library not installed")
            return None
        if not self._vobject_instance:
            if self._get_data() is None:
                return None
            try:
                self._set_vobject_instance(
                    vobject.readOne(to_unicode(self._get_data()))
                )
            except:
                log.critical(
                    "Error loading icalendar data into vobject. URL: " + str(self.url)
                )
                raise
        return self._vobject_instance

    vobject_instance = property(_get_vobject_instance, _set_vobject_instance)

    def _set_icalendar_instance(self, inst):
        if not isinstance(inst, icalendar.Calendar):
            try:
                cal = icalendar.Calendar.new()
            except:
                cal = icalendar.Calendar()
                cal.add("prodid", "-//python-caldav//caldav//en_DK")
                cal.add("version", "2.0")
            cal.add_component(inst)
            inst = cal
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

    icalendar_instance: Any = property(_get_icalendar_instance, _set_icalendar_instance)

    async def load(self, only_if_unloaded: bool = False) -> Self:
        """(Re)load the object from the caldav server."""
        if only_if_unloaded and self.is_loaded():
            return self

        if self.url is None:
            raise ValueError("Unexpected value None for self.url")
        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        try:
            r = await self.client.request(str(self.url))
            if r.status and r.status == 404:
                raise error.NotFoundError(errmsg(r))
            self.data = r.raw
        except error.NotFoundError:
            raise
        except:
            return await self.load_by_multiget()
        if "Etag" in r.headers:
            self.props[dav.GetEtag.tag] = r.headers["Etag"]
        if "Schedule-Tag" in r.headers:
            self.props[cdav.ScheduleTag.tag] = r.headers["Schedule-Tag"]
        return self

    async def load_by_multiget(self) -> Self:
        """Load via REPORT multiget query."""
        error.assert_(self.url)
        mydata = self.parent._multiget(event_urls=[self.url], raise_notfound=True)
        try:
            url, self.data = next(mydata)
        except StopIteration:
            raise error.NotFoundError(self.url)
        error.assert_(self.data)
        error.assert_(next(mydata, None) is None)
        return self

    def is_loaded(self):
        """Returns True if there is data in the object."""
        return (
            (self._data and self._data.count("BEGIN:") > 1)
            or self._vobject_instance
            or self._icalendar_instance
        )

    def _find_id_path(self, id=None, path=None) -> None:
        """Find or generate UID and path."""
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
            path = self._generate_url()
        else:
            path = self.parent.url.join(path)

        self.url = URL.objectify(path)

    async def _put(self, retry_on_failure=True):
        """PUT the calendar data to the server."""
        r = await self.client.put(
            self.url, self.data, {"Content-Type": 'text/calendar; charset="utf-8"'}
        )
        if r.status == 302:
            path = [x[1] for x in r.headers if x[0] == "location"][0]
        elif r.status not in (204, 201):
            if retry_on_failure:
                try:
                    import vobject
                except ImportError:
                    retry_on_failure = False
            if retry_on_failure:
                self.vobject_instance
                return await self._put(False)
            else:
                raise error.PutError(errmsg(r))

    async def _create(self, id=None, path=None, retry_on_failure=True) -> None:
        """Create the calendar object on the server."""
        self._find_id_path(id=id, path=path)
        await self._put()

    def _generate_url(self):
        """Generate URL from ID."""
        if not self.id:
            self.id = self._get_icalendar_component(assert_one=False)["UID"]
        return self.parent.url.join(quote(self.id.replace("/", "%2F")) + ".ics")

    async def save(
        self,
        no_overwrite: bool = False,
        no_create: bool = False,
        obj_type: Optional[str] = None,
        increase_seqno: bool = True,
        if_schedule_tag_match: bool = False,
        only_this_recurrence: bool = True,
        all_recurrences: bool = False,
    ) -> Self:
        """Save the object."""
        if not obj_type:
            obj_type = self.__class__.__name__.lower().replace("async", "")
        if (
            self._vobject_instance is None
            and self._data is None
            and self._icalendar_instance is None
        ):
            return self

        path = self.url.path if self.url else None

        async def get_self():
            self.id = self.id or self.icalendar_component.get("uid")
            if self.id:
                try:
                    if obj_type:
                        return await getattr(self.parent, "%s_by_uid" % obj_type)(
                            self.id
                        )
                    else:
                        return await self.parent.object_by_uid(self.id)
                except error.NotFoundError:
                    return None
            return None

        if no_overwrite or no_create:
            existing = await get_self()
            if not self.id and no_create:
                raise error.ConsistencyError("no_create flag was set, but no ID given")
            if no_overwrite and existing:
                raise error.ConsistencyError(
                    "no_overwrite flag was set, but object already exists"
                )
            if no_create and not existing:
                raise error.ConsistencyError(
                    "no_create flag was set, but object does not exist"
                )

        if (
            only_this_recurrence or all_recurrences
        ) and "RECURRENCE-ID" in self.icalendar_component:
            obj = await get_self()
            ici = obj.icalendar_instance
            if all_recurrences:
                occ = obj.icalendar_component
                ncc = self.icalendar_component.copy()
                for prop in ["exdate", "exrule", "rdate", "rrule"]:
                    if prop in occ:
                        ncc[prop] = occ[prop]
                dtstart_diff = (
                    ncc.start.astimezone() - ncc["recurrence-id"].dt.astimezone()
                )
                new_duration = ncc.duration
                ncc.pop("dtstart")
                ncc.add("dtstart", occ.start + dtstart_diff)
                for ep in ("duration", "dtend"):
                    if ep in ncc:
                        ncc.pop(ep)
                ncc.add("dtend", ncc.start + new_duration)
                ncc.pop("recurrence-id")
                s = ici.subcomponents
                comp_idxes = (
                    i
                    for i in range(0, len(s))
                    if not isinstance(s[i], icalendar.Timezone)
                )
                comp_idx = next(comp_idxes)
                s[comp_idx] = ncc
                if dtstart_diff:
                    for i in comp_idxes:
                        rid = s[i].pop("recurrence-id")
                        s[i].add("recurrence-id", rid.dt + dtstart_diff)
                return await obj.save(increase_seqno=increase_seqno)
            if only_this_recurrence:
                existing_idx = [
                    i
                    for i in range(0, len(ici.subcomponents))
                    if ici.subcomponents[i].get("recurrence-id")
                    == self.icalendar_component["recurrence-id"]
                ]
                error.assert_(len(existing_idx) <= 1)
                if existing_idx:
                    ici.subcomponents[existing_idx[0]] = self.icalendar_component
                else:
                    ici.add_component(self.icalendar_component)
                return await obj.save(increase_seqno=increase_seqno)

        if "SEQUENCE" in self.icalendar_component:
            seqno = self.icalendar_component.pop("SEQUENCE", None)
            if seqno is not None:
                self.icalendar_component.add("SEQUENCE", seqno + 1)

        await self._create(id=self.id, path=path)
        return self

    def copy(self, keep_uid: bool = False, new_parent: Optional[Any] = None) -> Self:
        """Copy the calendar object."""
        obj = self.__class__(
            parent=new_parent or self.parent,
            data=self.data,
            id=self.id if keep_uid else str(uuid.uuid1()),
        )
        if new_parent or not keep_uid:
            obj.url = obj._generate_url()
        else:
            obj.url = self.url
        return obj

    async def add_organizer(self) -> None:
        """Add organizer line to the event from the principal."""
        if self.client is None:
            raise ValueError("Unexpected value None for self.client")
        principal = await self.client.principal()
        self.icalendar_component.add("organizer", await principal.get_vcal_address())

    def add_attendee(
        self, attendee, no_default_parameters: bool = False, **parameters
    ) -> None:
        """Add an attendee to the event/todo/journal."""
        from caldav._async.collection import AsyncPrincipal

        if isinstance(attendee, AsyncPrincipal):
            raise NotImplementedError("Must await get_vcal_address for async principal")
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
                raise NotImplementedError("ATTENDEE string parsing not implemented")
            elif attendee.startswith("mailto:"):
                attendee_obj = vCalAddress(attendee)
            elif "@" in attendee and ":" not in attendee and ";" not in attendee:
                attendee_obj = vCalAddress("mailto:" + attendee)
        else:
            error.assert_(False)
            attendee_obj = vCalAddress()

        if not no_default_parameters:
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
        self.icalendar_component.add("attendee", attendee_obj)

    def get_duration(self) -> timedelta:
        """Get duration from DURATION or calculate from DTSTART and DUE/DTEND."""
        i = self.icalendar_component
        return self._get_duration(i)

    def _get_duration(self, i):
        if "DURATION" in i:
            return i["DURATION"].dt
        elif "DTSTART" in i and self._ENDPARAM in i:
            end = i[self._ENDPARAM].dt
            start = i["DTSTART"].dt
            if isinstance(end, datetime) != isinstance(start, datetime):
                start = datetime(start.year, start.month, start.day)
                end = datetime(end.year, end.month, end.day)
            return end - start
        elif "DTSTART" in i and not isinstance(i["DTSTART"], datetime):
            return timedelta(days=1)
        else:
            return timedelta(0)

    def __str__(self) -> str:
        return "%s: %s" % (self.__class__.__name__, self.url)


class AsyncEvent(AsyncCalendarObjectResource):
    """Async Event (VEVENT) object."""

    _ENDPARAM = "DTEND"
    set_dtend = (
        AsyncCalendarObjectResource.set_end
        if hasattr(AsyncCalendarObjectResource, "set_end")
        else None
    )


class AsyncJournal(AsyncCalendarObjectResource):
    """Async Journal (VJOURNAL) object."""

    pass


class AsyncFreeBusy(AsyncCalendarObjectResource):
    """Async FreeBusy (VFREEBUSY) object."""

    def __init__(
        self,
        parent,
        data,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        id: Optional[Any] = None,
    ) -> None:
        AsyncCalendarObjectResource.__init__(
            self, client=parent.client, url=url, data=data, parent=parent, id=id
        )


class AsyncTodo(AsyncCalendarObjectResource):
    """Async Todo (VTODO) object."""

    _ENDPARAM = "DUE"

    async def complete(
        self,
        completion_timestamp: Optional[datetime] = None,
        handle_rrule: bool = False,
        rrule_mode: str = "safe",
    ) -> None:
        """Mark the task as completed."""
        if not completion_timestamp:
            completion_timestamp = datetime.now(timezone.utc)

        if "RRULE" in self.icalendar_component and handle_rrule:
            return await getattr(self, "_complete_recurring_%s" % rrule_mode)(
                completion_timestamp
            )
        self._complete_ical(completion_timestamp=completion_timestamp)
        await self.save()

    def _complete_ical(self, i=None, completion_timestamp=None) -> None:
        if i is None:
            i = self.icalendar_component
        assert self.is_pending(i)
        status = i.pop("STATUS", None)
        i.add("STATUS", "COMPLETED")
        i.add("COMPLETED", completion_timestamp)

    def is_pending(self, i=None) -> Optional[bool]:
        if i is None:
            i = self.icalendar_component
        if i.get("COMPLETED", None) is not None:
            return False
        if i.get("STATUS", "NEEDS-ACTION") in ("NEEDS-ACTION", "IN-PROCESS"):
            return True
        if i.get("STATUS", "NEEDS-ACTION") in ("CANCELLED", "COMPLETED"):
            return False
        assert False

    async def uncomplete(self) -> None:
        """Undo completion - marks a completed task as not completed."""
        if "status" in self.icalendar_component:
            self.icalendar_component.pop("status")
        self.icalendar_component.add("status", "NEEDS-ACTION")
        if "completed" in self.icalendar_component:
            self.icalendar_component.pop("completed")
        await self.save()

    def get_due(self):
        """Get due date/time."""
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
