#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""
A "DAV object" is anything we get from the caldav server or push into the
caldav server, notably principal, calendars and calendar events.

(This file has become huge and will be split up prior to the next
release.  I think it makes sense moving the CalendarObjectResource
class hierarchy into a separate file)
"""

import vobject
import uuid
import re
from datetime import datetime, date
from lxml import etree

try:
    # noinspection PyCompatibility
    from urllib.parse import unquote, quote
except ImportError:
    from urllib import unquote, quote

try:
    from typing import Union, Optional
    TimeStamp = Optional[Union[date,datetime]]
except:
    pass

from caldav.lib import error, vcal
from caldav.lib.url import URL
from caldav.elements import dav, cdav, ical
from caldav.lib.python_utilities import to_unicode, to_wire

import logging
log = logging.getLogger('caldav')

def errmsg(r):
    """Utility for formatting a response xml tree to an error string"""
    return "%s %s\n\n%s" % (r.status, r.reason, r.raw)

class DAVObject(object):

    """
    Base class for all DAV objects.  Can be instantiated by a client
    and an absolute or relative URL, or from the parent object.
    """
    id = None
    url = None
    client = None
    parent = None
    name = None

    def __init__(self, client=None, url=None, parent=None, name=None, id=None, props=None,
                 **extra):
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
        if props is None:
            self.props = {}
        else:
            self.props = props
        self.extra_init_options = extra
        # url may be a path relative to the caldav root
        if client and url:
            self.url = client.url.join(url)
        else:
            self.url = URL.objectify(url)

    @property
    def canonical_url(self):
        return str(self.url.canonical())

    def children(self, type=None):
        """
        List children, using a propfind (resourcetype) on the parent object,
        at depth = 1.
        """
        c = []

        depth = 1
        properties = {}

        props = [ dav.DisplayName()]
        multiprops = [ dav.ResourceType() ]
        response = self._query_properties(props+multiprops, depth)
        properties = response.expand_simple_props(props=props, multi_value_props=multiprops)

        for path in list(properties.keys()):
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
                if ((isinstance(self, CalendarSet) and type == cdav.Calendar.tag)
                    or (self.url.canonical().strip_trailing_slash() !=
                        self.url.join(path).canonical().strip_trailing_slash())):
                    c.append((self.url.join(path), resource_types,
                              resource_name))

        ## TODO: return objects rather than just URLs, and include
        ## the properties we've already fetched
        return c

    def _query_properties(self, props=None, depth=0):
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

    def _query(self, root=None, depth=0, query_method='propfind', url=None,
               expected_return_value=None):
        """
        This is an internal method for doing a query.  It's a
        result of code-refactoring work, attempting to consolidate
        similar-looking code into a common method.
        """
        body = ""
        if root:
            if hasattr(root, 'xmlelement'):
                body = etree.tostring(root.xmlelement(), encoding="utf-8",
                                      xml_declaration=True)
            else:
                body = root
        if url is None:
            url = self.url
        ret = getattr(self.client, query_method)(
            url, body, depth)
        if ret.status == 404:
            raise error.NotFoundError(errmsg(ret))
        if ((expected_return_value is not None and
             ret.status != expected_return_value) or
            ret.status >= 400):
            raise error.exception_by_method[query_method](errmsg(ret))
        return ret

    def get_property(self, prop, use_cached=False, **passthrough):
        ## TODO: use_cached should probably be true
        if use_cached:
            if prop.tag in self.props:
                return self.props[prop.tag]
        foo = self.get_properties([prop], **passthrough)
        return foo.get(prop.tag, None)

    def get_properties(self, props=None, depth=0, parse_response_xml=True, parse_props=True):
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

        path = unquote(self.url.path)
        if path.endswith('/'):
            exchange_path = path[:-1]
        else:
            exchange_path = path + '/'

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
                log.error("potential path handling problem with ending slashes.  Path given: %s, path found: %s.  %s" % (path, exchange_path, error.ERR_FRAGMENT))
                error._assert(False)
            rc = properties[exchange_path]
        elif self.url in properties:
            rc = properties[self.url]
        elif '/principal/' in properties and path.endswith('/principal/'):
            ## Workaround for a known iCloud bug.
            ## The properties key is expected to be the same as the path.
            ## path is on the format /123456/principal/ but properties key is /principal/
            ## tests apparently passed post bc589093a34f0ed0ef489ad5e9cba048750c9837 and 3ee4e42e2fa8f78b71e5ffd1ef322e4007df7a60, even without this workaround
            ## TODO: should probably be investigated more.
            ## (observed also by others, ref https://github.com/python-caldav/caldav/issues/168)
            rc = properties['/principal/']
        else:
            log.error("Possibly the server has a path handling problem.  Path expected: %s, path found: %s %s" % (path, str(list(properties.keys())), error.ERR_FRAGMENT))
            error.assert_(False)

        if parse_props:
            self.props.update(rc)
        return rc

    def set_properties(self, props=None):
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

        r = self._query(root, query_method='proppatch')

        statuses = r.tree.findall(".//" + dav.Status.tag)
        for s in statuses:
            if ' 200 ' not in s.text:
                raise error.PropsetError(s.text)

        return self

    def save(self):
        """
        Save the object. This is an abstract method, that all classes
        derived from DAVObject implement.

        Returns:
         * self
        """
        raise NotImplementedError()

    def delete(self):
        """
        Delete the object.
        """
        if self.url is not None:
            r = self.client.delete(self.url)

            # TODO: find out why we get 404
            if r.status not in (200, 204, 404):
                raise error.DeleteError(errmsg(r))

    def __str__(self):
        if dav.DisplayName.tag in self.props:
            return self.props[dav.DisplayName.tag]
        else:
            return str(self.url)

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))


class CalendarSet(DAVObject):
    """
    A CalendarSet is a set of calendars.
    """
    def calendars(self):
        """
        List all calendar collections in this set.

        Returns:
         * [Calendar(), ...]
        """
        cals = []

        data = self.children(cdav.Calendar.tag)
        for c_url, c_type, c_name in data:
            cals.append(Calendar(self.client, c_url, parent=self, name=c_name))

        return cals

    def make_calendar(self, name=None, cal_id=None,
                      supported_calendar_component_set=None):
        """
        Utility method for creating a new calendar.

        Parameters:
         * name: the name of the new calendar
         * cal_id: the uuid of the new calendar
         * supported_calendar_component_set: what kind of objects
           (EVENT, VTODO, VFREEBUSY, VJOURNAL) the calendar should handle.
           Should be set to ['VTODO'] when creating a task list in Zimbra -
           in most other cases the default will be OK.

        Returns:
         * Calendar(...)-object
        """
        return Calendar(
            self.client, name=name, parent=self, id=cal_id,
            supported_calendar_component_set=supported_calendar_component_set
        ).save()

    def calendar(self, name=None, cal_id=None):
        """
        The calendar method will return a calendar object.  If it gets a cal_id
        but no name, it will not initiate any communication with the server

        Parameters:
         * name: return the calendar with this name
         * cal_id: return the calendar with this calendar id or URL

        Returns:
         * Calendar(...)-object
        """
        if name and not cal_id:
            for calendar in self.calendars():
                display_name = calendar.get_property(dav.DisplayName())
                if display_name == name:
                    return calendar
        if name and not cal_id:
            raise error.NotFoundError("No calendar with name %s found under %s" % (name, self.url))
        if not cal_id and not name:
            return self.calendars()[0]

        if str(URL.objectify(cal_id).canonical()).startswith(str(self.client.url.canonical())):
            url = self.client.url.join(cal_id)
        elif isinstance(cal_id, URL):
            url = self.url.join(cal_id)
        else:
            url = self.url.join(quote(cal_id) + '/')

        return Calendar(self.client, name=name, parent=self,
                        url=url, id=cal_id)

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
    def __init__(self, client=None, url=None):
        """
        Returns a Principal.

        Parameters:
         * client: a DAVClient() oject
         * url: Deprecated - for backwards compatibility purposes only.

        If url is not given, deduct principal path as well as calendar home set
        path from doing propfinds.
        """
        super(Principal, self).__init__(client=client, url=url)
        self._calendar_home_set = None

        if url is None:
            self.url = self.client.url
            cup = self.get_property(dav.CurrentUserPrincipal())
            self.url = self.client.url.join(
                URL.objectify(cup))

    def make_calendar(self, name=None, cal_id=None,
                      supported_calendar_component_set=None):
        """
        Convenience method, bypasses the self.calendar_home_set object.
        See CalendarSet.make_calendar for details.
        """
        return self.calendar_home_set.make_calendar(
            name, cal_id,
            supported_calendar_component_set=supported_calendar_component_set)

    def calendar(self, name=None, cal_id=None):
        """
        The calendar method will return a calendar object.
        It will not initiate any communication with the server.
        """
        return self.calendar_home_set.calendar(name, cal_id)

    def get_vcal_address(self):
        """
        Returns the principal, as an icalendar.vCalAddress object
        """
        ## Late import.  Prior to 1.0, icalendar is only an optional dependency.
        from icalendar import vCalAddress, vText
        cn = self.get_property(dav.DisplayName())
        ids = self.calendar_user_address_set()
        cutype = self.get_property(cdav.CalendarUserType())
        ret = vCalAddress(ids[0])
        ret.params['cn'] = vText(cn)
        ret.params['cutype'] = vText(cutype)
        return ret

    @property
    def calendar_home_set(self):
        if not self._calendar_home_set:
            calendar_home_set_url = self.get_property(cdav.CalendarHomeSet())
            ## owncloud returns /remote.php/dav/calendars/tobixen@e.email/
            ## in that case the @ should be quoted.  Perhaps other
            ## implentations returns already quoted URLs.  Hacky workaround:
            if calendar_home_set_url is not None and '@' in calendar_home_set_url and not '://' in calendar_home_set_url:
                calendar_home_set_url = quote(calendar_home_set_url)
            self.calendar_home_set = calendar_home_set_url
        return self._calendar_home_set

    @calendar_home_set.setter
    def calendar_home_set(self, url):
        if isinstance(url, CalendarSet):
            self._calendar_home_set = url
            return
        sanitized_url = URL.objectify(url)
        ## TODO: sanitized_url should never be None, this needs more
        ## research.  added here as it solves real-world issues, ref
        ## https://github.com/python-caldav/caldav/pull/56
        if sanitized_url is not None:
            if (sanitized_url.hostname and
                sanitized_url.hostname != self.client.url.hostname):
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
            self.client, self.client.url.join(sanitized_url))

    def calendars(self):
        """
        Return the principials calendars
        """
        return self.calendar_home_set.calendars()

    def freebusy_request(self, dtstart, dtend, attendees):
        import icalendar
        freebusy_ical = icalendar.Calendar()
        freebusy_ical.add('prodid', '-//tobixen/python-caldav//EN')
        freebusy_ical.add('version', '2.0')
        freebusy_ical.add('method', 'REQUEST')
        uid = uuid.uuid1()
        freebusy_comp = icalendar.FreeBusy()
        freebusy_comp.add('uid', uid)
        freebusy_comp.add('dtstamp', datetime.now())
        freebusy_comp.add('dtstart', dtstart)
        freebusy_comp.add('dtend', dtend)
        freebusy_ical.add_component(freebusy_comp)
        outbox = self.schedule_outbox()
        caldavobj = FreeBusy(data=freebusy_ical, parent=outbox)
        caldavobj.add_organizer()
        for attendee in attendees:
            caldavobj.add_attendee(attendee, no_default_parameters=True)

        response = self.client.post(outbox.url, caldavobj.data, headers={'Content-Type': 'text/calendar; charset=utf-8'})
        return response.find_objects_and_props()

    def calendar_user_address_set(self):
        """
        defined in RFC6638
        """
        addresses = self.get_property(cdav.CalendarUserAddressSet(), parse_props=False)
        assert not [x for x in addresses if x.tag != dav.Href().tag]
        addresses = list(addresses)
        ## possibly the preferred attribute is iCloud-specific.
        ## TODO: do more research on that
        addresses.sort(key=lambda x: -int(x.get('preferred', 0)))
        return [x.text for x in addresses]

    def schedule_inbox(self):
        return ScheduleInbox(principal=self)

    def schedule_outbox(self):
        return ScheduleOutbox(principal=self)

class Calendar(DAVObject):
    """
    The `Calendar` object is used to represent a calendar collection.
    Refer to the RFC for details:
    https://tools.ietf.org/html/rfc4791#section-5.3.1
    """
    def _create(self, name=None, id=None, supported_calendar_component_set=None):
        """
        Create a new calendar with display name `name` in `parent`.
        """
        if id is None:
            id = str(uuid.uuid1())
        self.id = id

        path = self.parent.url.join(id + '/')
        self.url = path

        # TODO: mkcalendar seems to ignore the body on most servers?
        # at least the name doesn't get set this way.
        # zimbra gives 500 (!) if body is omitted ...

        prop = dav.Prop()
        if name:
            display_name = dav.DisplayName(name)
            prop += [display_name, ]
        if supported_calendar_component_set:
            sccs = cdav.SupportedCalendarComponentSet()
            for scc in supported_calendar_component_set:
                sccs += cdav.Comp(scc)
            prop += sccs
        set = dav.Set() + prop

        mkcol = cdav.Mkcalendar() + set

        r = self._query(root=mkcol, query_method='mkcalendar', url=path,
                        expected_return_value=201)

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
                    current_display_name = self.get_property(dav.DisplayName())
                    error.assert_(current_display_name == name)
                except:
                    log.warning("calendar server does not support display name on calendar?  Ignoring", exc_info=True)
                    error.assert_(False)

    def get_supported_components(self):
        """
        returns a list of component types supported by the calendar, in
        string format (typically ['VJOURNAL', 'VTODO', 'VEVENT'])
        """
        props = [cdav.SupportedCalendarComponentSet()]
        response = self.get_properties(props, parse_response_xml=False)
        response_list = response.find_objects_and_props()
        prop = response_list[unquote(self.url.path)][cdav.SupportedCalendarComponentSet().tag]
        return [supported.get('name') for supported in prop]

    def save_with_invites(self, ical, attendees, **attendeeoptions):
        """
        sends a schedule request to the server.  Equivalent with save_event, save_todo, etc,
        but the attendees will be added to the ical object before sending it to the server.
        """
        ## TODO: method supports raw strings, probably not icalendar nor vobject.
        obj = self._calendar_comp_class_by_data(ical)(data=ical, client=self.client)
        obj.parent = self
        obj.add_organizer()
        for attendee in attendees:
            obj.add_attendee(attendee, **attendeeoptions)
        obj.id = obj.icalendar_instance.walk('vevent')[0]['uid']
        obj.save()

    def _use_or_create_ics(self, ical, objtype, **ical_data):
        if ical_data or ((isinstance(ical, str) or isinstance(ical, bytes)) and not b'BEGIN:VCALENDAR' in to_wire(ical)):
            return vcal.create_ical(ical_fragment=ical, objtype=objtype, **ical_data)
        return ical

    def save_event(self, ical=None, no_overwrite=False, no_create=False, **ical_data):
        """
        Add a new event to the calendar, with the given ical.

        Parameters:
         * ical - ical object (text)
         * no_overwrite - existing calendar objects should not be overwritten
         * no_create - don't create a new object, existing calendar objects should be updated
         * ical_data - passed to lib.vcal.create_ical
        """
        e = Event(self.client, data=self._use_or_create_ics(ical, objtype='VEVENT', **ical_data), parent=self)
        e.save(no_overwrite=no_overwrite, no_create=no_create, obj_type='event')
        return e

    def save_todo(self, ical=None, no_overwrite=False, no_create=False, **ical_data):
        """
        Add a new task to the calendar, with the given ical.

        Parameters:
         * ical - ical object (text)
        """
        return Todo(self.client, data=self._use_or_create_ics(ical, objtype='VTODO', **ical_data), parent=self).save(no_overwrite=no_overwrite, no_create=no_create, obj_type='todo')

    def save_journal(self, ical=None, no_overwrite=False, no_create=False, **ical_data):
        """
        Add a new journal entry to the calendar, with the given ical.

        Parameters:
         * ical - ical object (text)
        """
        return Journal(self.client, data=self._use_or_create_ics(ical, objtype='VJOURNAL', **ical_data), parent=self).save(no_overwrite=no_overwrite, no_create=no_create, obj_type='journal')

    ## legacy aliases
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
            self._create(name=self.name, id=self.id, **self.extra_init_options)
        return self

    def calendar_multiget(self, event_urls):
        """
        get multiple events' data
        @author mtorange@gmail.com
        @type events list of Event
        """
        rv=[]
        prop = dav.Prop() + cdav.CalendarData()
        root = cdav.CalendarMultiGet() + prop + [dav.Href(value=u.path) for u in event_urls]
        response = self._query(root, 1, 'report')
        results = response.expand_simple_props([cdav.CalendarData()])
        for r in results:
            rv.append(
                Event(self.client, url=self.url.join(r), data=results[r][cdav.CalendarData.tag], parent=self))

        return rv


    def build_date_search_query(self, start, end=None, compfilter="VEVENT", expand="maybe"):
        """
        Split out from the date_search-method below.  The idea is that
        maybe the generated query can be amended, i.e. to filter out
        by category etc.  To be followed up in
        https://github.com/python-caldav/caldav/issues/16
        """
        ## for backward compatibility - expand should be false
        ## in an open-ended date search, otherwise true
        if expand == 'maybe':
            expand = end

        # Some servers will raise an error if we send the expand flag
        # but don't set any end-date - expand doesn't make much sense
        # if we have one recurring event describing an indefinite
        # series of events.  I think it's appropriate to raise an error
        # in this case.
        if not end and expand:
            raise error.ReportError("an open-ended date search cannot be expanded")
        elif expand:
            data = cdav.CalendarData() + cdav.Expand(start, end)
        else:
            data = cdav.CalendarData()
        prop = dav.Prop() + data

        query = cdav.TimeRange(start, end)
        if compfilter:
            query = cdav.CompFilter(compfilter) + query
        vcalendar = cdav.CompFilter("VCALENDAR") + query
        filter = cdav.Filter() + vcalendar
        root = cdav.CalendarQuery() + [prop, filter]
        return root

    def date_search(self, start, end=None, compfilter="VEVENT", expand="maybe", verify_expand=False):
        # type (TimeStamp, TimeStamp, str, str) -> CalendarObjectResource
        """Search events by date in the calendar. Recurring events are
        expanded if they are occuring during the specified time frame
        and if an end timestamp is given.

        Parameters:
         * start = datetime.today().
         * end = same as above.
         * compfilter = defaults to events only.  Set to None to fetch all
           calendar components.
         * expand - should recurrent events be expanded?  (to preserve
           backward-compatibility the default "maybe" will be changed into True
           unless the date_search is open-ended)
         * verify_expand - quite some servers does not support
           expansion.  If verify_expand is set to True, an error will
           be raised if expansion is requested but the server does not
           support expansion.  Defaults to False for
           backward-compatibility.

        Returns:
         * [CalendarObjectResource(), ...]

        """
        # build the query
        root = self.build_date_search_query(start, end, compfilter, expand)

        if compfilter == 'VEVENT': comp_class=Event
        else: comp_class = None

        ## xandikos now yields a 5xx-error when trying to pass
        ## expand=True, after I prodded the developer that it doesn't
        ## work.  By now there is some workaround in the test code to
        ## avoid sending expand=True to xandikos, but perhaps we
        ## should run a try-except-retry here with expand=False in the
        ## retry, and warnings logged ... or perhaps not.
        ##
        ## Perhaps not? Detect and raise an Exception. Since the library
        ## does not perform client side expansion, it should probably be
        ## left as a concious desicion for the API consumer to retry with
        ## expansion set to False.
        ##
        ## RFC4791, section 9.6.5 states that recurrence properties MUST NOT be
        ## returned.
        objects = self.search(root, comp_class)
        if expand:
            for o in objects:
                if not o.data:
                    continue
                components = o.vobject_instance.components()
                for i in components:
                    if i.name == 'VEVENT':
                        recurrance_properties = ['exdate', 'exrule', 'rdate', 'rrule']
                        if any(key in recurrance_properties for key in i.contents):
                            if verify_expand:
                                raise error.ReportError('CalDAV server did not expand recurring vevents as requested. See https://github.com/python-caldav/caldav/issues/157')
                            else:
                                logging.error('CalDAV server does not support recurring events properly.  See https://github.com/python-caldav/caldav/issues/157')
        return objects

    def _request_report_build_resultlist(self, xml, comp_class=None, props=None, no_calendardata=False):
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
        response = self._query(xml, 1, 'report')
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
                comp_class(self.client, url=self.url.join(url),
                           data=cdata, parent=self, props=pdata))

        return (response, matches)

    def search(self, xml, comp_class=None):
        """
        This method was partly written to approach
        https://github.com/python-caldav/caldav/issues/16 This is a
        result of some code refactoring, and after the next round of
        refactoring we've ended up with this:
        """
        (response, objects) = self._request_report_build_resultlist(xml, comp_class)
        return objects

    def freebusy_request(self, start, end):
        """
        Search the calendar, but return only the free/busy information.

        Parameters:
         * start = datetime.today().
         * end = same as above.

        Returns:
         * [FreeBusy(), ...]

        """

        root = cdav.FreeBusyQuery() + [cdav.TimeRange(start, end)]
        response = self._query(root, 1, 'report')
        return FreeBusy(self, response.raw)

    def _fetch_todos(self, filters):
        # ref https://www.ietf.org/rfc/rfc4791.txt, section 7.8.9
        matches = []

        # build the request
        data = cdav.CalendarData()
        prop = dav.Prop() + data

        vcalendar = cdav.CompFilter("VCALENDAR") + filters
        filter = cdav.Filter() + vcalendar

        root = cdav.CalendarQuery() + [prop, filter]

        return self.search(root, comp_class=Todo)

    def todos(self, sort_keys=('due', 'priority'), include_completed=False,
              sort_key=None):
        """
        fetches a list of todo events.

        Parameters:
         * sort_keys: use this field in the VTODO for sorting (iterable of
           lower case string, i.e. ('priority','due')).
         * include_completed: boolean -
           by default, only pending tasks are listed
         * sort_key: DEPRECATED, for backwards compatibility with version 0.4.
        """
        if sort_key:
            sort_keys = (sort_key,)

        if not include_completed:
            vnotcompleted = cdav.TextMatch('COMPLETED', negate=True)
            vnotcancelled = cdav.TextMatch('CANCELLED', negate=True)
            vstatusNotCompleted = cdav.PropFilter('STATUS') + vnotcompleted
            vstatusNotCancelled = cdav.PropFilter('STATUS') + vnotcancelled
            vstatusNotDefined = cdav.PropFilter('STATUS') + cdav.NotDefined()
            vnocompletedate = cdav.PropFilter('COMPLETED') + cdav.NotDefined()
            filters1 = (cdav.CompFilter("VTODO") + vnocompletedate +
                        vstatusNotCompleted + vstatusNotCancelled)
            ## This query is quite much in line with https://tools.ietf.org/html/rfc4791#section-7.8.9
            matches1 = self._fetch_todos(filters1)
            ## However ... some server implementations (i.e. NextCloud
            ## and Baikal) will yield "false" on a negated TextMatch
            ## if the field is not defined.  Hence, for those
            ## implementations we need to turn back and ask again
            ## ... do you have any VTODOs for us where the STATUS
            ## field is not defined? (ref
            ## https://github.com/python-caldav/caldav/issues/14)
            filters2 = (cdav.CompFilter("VTODO") + vnocompletedate +
                        vstatusNotDefined)
            matches2 = self._fetch_todos(filters2)

            ## For most caldav servers, everything in matches2 already exists
            ## in matches1.  We need to make a union ...
            match_set = set()
            matches = []
            for todo in matches1 + matches2:
                if not todo.url in match_set:
                    match_set.add(todo.url)
                    ## and still, Zimbra seems to deliver too many TODOs on the
                    ## filter2 ... let's do some post-filtering in case the
                    ## server fails in filtering things the right way
                    if (not '\nCOMPLETED:' in todo.data and
                        not '\nSTATUS:COMPLETED' in todo.data and
                        not '\nSTATUS:CANCELLED' in todo.data):
                        matches.append(todo)

        else:
            filters = cdav.CompFilter("VTODO")
            matches = self._fetch_todos(filters)

        def sort_key_func(x):
            ret = []
            vtodo = x.instance.vtodo
            defaults = {
                'due': '2050-01-01',
                'dtstart': '1970-01-01',
                'priority': '0',
                # JA: why compare datetime.strftime('%F%H%M%S')
                # JA: and not simply datetime?

                # tobixen: probably it was made like this because we can get
                # both dates and timestamps from the objects.
                # Python will yield an exception if trying to compare
                # a timestamp with a date.

                'isnt_overdue':
                    not (hasattr(vtodo, 'due') and
                         vtodo.due.value.strftime('%F%H%M%S') <
                         datetime.now().strftime('%F%H%M%S')),
                'hasnt_started':
                    (hasattr(vtodo, 'dtstart') and
                     vtodo.dtstart.value.strftime('%F%H%M%S') >
                     datetime.now().strftime('%F%H%M%S'))
            }
            for sort_key in sort_keys:
                val = getattr(vtodo, sort_key, None)
                if val is None:
                    ret.append(defaults.get(sort_key, '0'))
                    continue
                val = val.value
                if hasattr(val, 'strftime'):
                    ret.append(val.strftime('%F%H%M%S'))
                else:
                    ret.append(val)
            return ret
        if sort_keys:
            matches.sort(key=sort_key_func)
        return matches

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
        if hasattr(data, 'split'):
            for line in data.split('\n'):
                line = line.strip()
                if line == 'BEGIN:VEVENT':
                    return Event
                if line == 'BEGIN:VTODO':
                    return Todo
                if line == 'BEGIN:VJOURNAL':
                    return Journal
                if line == 'BEGIN:VFREEBUSY':
                    return FreeBusy
        elif hasattr(data, 'subcomponents'):
            if not len(data.subcomponents):
                return CalendarObjectResource

            ## Late import, as icalendar is not yet on the official dependency list
            import icalendar
            ical2caldav = {icalendar.Event: Event, icalendar.Todo: Todo, icalendar.Journal: Journal, icalendar.FreeBusy: FreeBusy}
            for sc in data.subcomponents:
                if sc.__class__ in ical2caldav:
                    return ical2caldav[sc.__class__]
        return CalendarObjectResource

    def event_by_url(self, href, data=None):
        """
        Returns the event with the given URL
        """
        return Event(url=href, data=data, parent=self).load()

    def object_by_uid(self, uid, comp_filter=None):
        """
        Get one event from the calendar.

        Parameters:
         * uid: the event uid

        Returns:
         * Event() or None
        """
        data = cdav.CalendarData()
        prop = dav.Prop() + data

        query = cdav.TextMatch(uid)
        query = cdav.PropFilter("UID") + query
        if comp_filter:
            query = comp_filter + query
        vcalendar = cdav.CompFilter("VCALENDAR") + query
        filter = cdav.Filter() + vcalendar

        root = cdav.CalendarQuery() + [prop, filter]

        try:
            items_found = self.search(root)
            if not items_found:
                raise error.NotFoundError("%s not found on server" % uid)
        except Exception as err:
            if comp_filter is not None:
                raise
            logging.warning("Error %s from server when doing an object_by_uid(%s).  search without compfilter set is not compatible with all server implementations, trying object_by_event + object_by_todo + object_by_journal instead" % (str(err), uid))
            items_found = []
            for compfilter in ("VTODO", "VEVENT", "VJOURNAL"):
                try:
                    items_found.append(self.object_by_uid(uid, cdav.CompFilter(compfilter)))
                except error.NotFoundError:
                    pass
            if len(items_found) >= 1:
                if len(items_found) > 1:
                    logging.error("multiple items found with same UID.  Returning the first one")
                return items_found[0]

        # Ref Lucas Verney, we've actually done a substring search, if the
        # uid given in the query is short (i.e. just "0") we're likely to
        # get false positives back from the server, we need to do an extra
        # check that the uid is correct
        for item in items_found:
            # Long uids are folded, so splice the lines together here before
            # attempting a match.
            item_uid = re.search(r'\nUID:((.|\n[ \t])*)\n', item.data)
            if (not item_uid or
                    re.sub(r'\n[ \t]', '', item_uid.group(1)) != uid):
                continue
            ## TODO: we should assert there is only one valid item
            return item
        raise error.NotFoundError("%s not found on server" % uid)

    def todo_by_uid(self, uid):
        return self.object_by_uid(uid, comp_filter=cdav.CompFilter("VTODO"))

    def event_by_uid(self, uid):
        return self.object_by_uid(uid, comp_filter=cdav.CompFilter("VEVENT"))

    def journal_by_uid(self, uid):
        return self.object_by_uid(uid, comp_filter=cdav.CompFilter("VJOURNAL"))

    # alias for backward compatibility
    event = event_by_uid

    def events(self):
        """
        List all events from the calendar.

        Returns:
         * [Event(), ...]
        """
        data = cdav.CalendarData()
        prop = dav.Prop() + data
        vevent = cdav.CompFilter("VEVENT")
        vcalendar = cdav.CompFilter("VCALENDAR") + vevent
        filter = cdav.Filter() + vcalendar
        root = cdav.CalendarQuery() + [prop, filter]

        return self.search(root, comp_class=Event)

    def objects_by_sync_token(self, sync_token=None, load_objects=False):
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
        level = dav.SyncLevel(value='1')
        props = dav.Prop() + dav.GetEtag()
        root = cmd + [level, token, props]
        (response, objects) = self._request_report_build_resultlist(root, props=[dav.GetEtag()], no_calendardata=True)
        ## TODO: look more into this, I think sync_token should be directly available through response object
        try:
            sync_token = response.sync_token
        except:
            sync_token = response.tree.findall('.//' + dav.SyncToken.tag)[0].text

        ## this is not quite right - the etag we've fetched can already be outdated
        if load_objects:
            for obj in objects:
                try:
                    obj.load()
                except error.NotFoundError:
                    ## The object was deleted
                    pass
        return SynchronizableCalendarObjectCollection(calendar=self, objects=objects, sync_token=sync_token)

    objects = objects_by_sync_token

    def journals(self):
        """
        List all journals from the calendar.

        Returns:
         * [Journal(), ...]
        """
        # TODO: this is basically a copy of events() - can we do more
        # refactoring and consolidation here?  Maybe it's wrong to do
        # separate methods for journals, todos and events?
        data = cdav.CalendarData()
        prop = dav.Prop() + data
        vevent = cdav.CompFilter("VJOURNAL")
        vcalendar = cdav.CompFilter("VCALENDAR") + vevent
        filter = cdav.Filter() + vcalendar
        root = cdav.CalendarQuery() + [prop, filter]

        return self.search(root, comp_class=Journal)

class ScheduleMailbox(Calendar):
    """
    RFC6638 defines an inbox and an outbox for handling event scheduling.

    TODO: As ScheduleMailboxes works a bit like calendars, I've chosen
    to inheritate the Calendar class, but this is a bit incorrect, a
    ScheduleMailbox is a collection, but not really a calendar.  We
    should create a common base class for ScheduleMailbox and Calendar
    eventually.
    """
    def __init__(self, client=None, principal=None, url=None):
        """
        Will locate the mbox if no url is given
        """
        super(ScheduleMailbox, self).__init__(client=client, url=url)
        self._items = None
        if not client and principal:
            self.client = principal.client
        if not principal and client:
            principal = self.client.principal
        if url is not None:
            self.url = client.url.join(URL.objectify(url))
        else:
            self.url = principal.url
            try:
                self.url = self.client.url.join(URL(self.get_property(self.findprop())))
            except:
                logging.error("something bad happened", exc_info=True)
                error.assert_(self.client.check_scheduling_support())
                self.url = None
                raise error.NotFoundError("principal has no %s.  %s" % (str(self.findprop()), error.ERR_FRAGMENT))

    def get_items(self):
        """
        TODO: work in progress
        TODO: perhaps this belongs to the super class?
        """
        if not self._items:
            try:
                self._items = self.objects(load_objects=True)
            except:
                logging.debug("caldav server does not seem to support a sync-token REPORT query on a scheduling mailbox")
                error.assert_('google' in str(self.url))
                self._items = [CalendarObjectResource(url=x[0], client=self.client) for x in self.children()]
                for x in self._items:
                    x.load()
        else:
            try:
                self._items.sync()
            except:
                self._items = [CalendarObjectResource(url=x[0], client=self.client) for x in self.children()]
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

class SynchronizableCalendarObjectCollection(object):
    """
    This class may hold a cached snapshot of a calendar, and changes
    in the calendar can easily be copied over through the sync method.

    To create a SynchronizableCalendarObjectCollection object, use
    calendar.objects(load_objects=True)
    """
    def __init__(self, calendar, objects, sync_token):
        self.calendar = calendar
        self.sync_token = sync_token
        self.objects = objects
        self._objects_by_url = None

    def __iter__(self):
        return self.objects.__iter__()

    def objects_by_url(self):
        """
        returns a dict of the contents of the SynchronizableCalendarObjectCollection, URLs -> objects.
        """
        if self._objects_by_url is None:
            self._objects_by_url = {}
            for obj in self:
                self._objects_by_url[obj.url] = obj
        return self._objects_by_url

    def sync(self):
        """
        This method will contact the caldav server,
        request all changes from it, and sync up the collection
        """
        updated_objs = []
        deleted_objs = []
        updates = self.calendar.objects_by_sync_token(self.sync_token, load_objects=False)
        obu = self.objects_by_url()
        for obj in updates:
            if obj.url in obu and dav.GetEtag.tag in obu[obj.url].props and dav.GetEtag.tag in obj.props:
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
    _vobject_instance = None
    _icalendar_instance = None
    _data = None

    def __init__(self, client=None, url=None, data=None, parent=None, id=None, props=None):
        """
        CalendarObjectResource has an additional parameter for its constructor:
         * data = "...", vCal data for the event
        """
        super(CalendarObjectResource, self).__init__(
            client=client, url=url, parent=parent, id=id, props=props)
        if data is not None:
            self.data = data

    def add_organizer(self):
        """
        goes via self.client, finds the principal, figures out the right attendee-format and adds an
        organizer line to the event
        """
        principal = self.client.principal()
        ## TODO: remove Organizer-field, if exists
        ## TODO: what if walk returns more than one vevent?
        self._icalendar_object().add('organizer', principal.get_vcal_address())

    def _icalendar_object(self):
        import icalendar
        for x in self.icalendar_instance.subcomponents:
            for cl in (icalendar.Event, icalendar.Journal, icalendar.Todo, icalendar.FreeBusy):
                if isinstance(x, cl):
                    return x

    def add_attendee(self, attendee, no_default_parameters=False, **parameters):
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
            if attendee[1].startswith('mailto:'):
                attendee_obj = vCalAddress(attendee[1])
            else:
                attendee_obj = vCalAddress('mailto:' + attendee[1])
            attendee_obj.params['cn'] = vText(attendee[0])
        elif isinstance(attendee, str):
            if attendee.startswith('ATTENDEE'):
                raise NotImplementedError("do we need to support this anyway?  Should be trivial, but can't figure out how to do it with the icalendar.Event/vCalAddress objects right now")
            elif attendee.startswith('mailto:'):
                attendee_obj = vCalAddress(attendee)
            elif '@' in attendee and not ':' in attendee and not ';' in attendee:
                attendee_obj = vCalAddress('mailto:' + attendee)
        else:
            error.assert_(False)
            attendee_obj = vCalAddress()

        ## TODO: if possible, check that the attendee exists
        ## TODO: check that the attendee will not be duplicated in the event.
        if not no_default_parameters:
            ## Sensible defaults:
            attendee_obj.params['partstat']='NEEDS-ACTION'
            if not 'cutype' in attendee_obj.params:
                attendee_obj.params['cutype']='UNKNOWN'
            attendee_obj.params['rsvp']='TRUE'
            attendee_obj.params['role']='REQ-PARTICIPANT'
        params = {}
        for key in parameters:
            new_key = key.replace('_', '-')
            if parameters[key] == True:
                params[new_key] = 'TRUE'
            else:
                params[new_key] = parameters[key]
        attendee_obj.params.update(params)
        ievent = self._icalendar_object()
        ievent.add('attendee', attendee_obj)

    def is_invite_request(self):
        if not self.data:
            self.load()
        return self.icalendar_instance.get('method', None) == 'REQUEST'

    def accept_invite(self, calendar=None):
        self._reply_to_invite_request('ACCEPTED', calendar)

    def decline_invite(self, calendar=None):
        self._reply_to_invite_request('DECLINED', calendar)

    def tentatively_accept_invite(self, calendar=None):
        self._reply_to_invite_request('TENTATIVE', calendar)

    ## TODO: DELEGATED is also a valid option, and for vtodos the
    ## partstat can also be set to COMPLETED and IN-PROGRESS.

    def _reply_to_invite_request(self, partstat, calendar):
        error.assert_(self.is_invite_request())
        if not calendar:
            calendar = self.client.principal().calendars()[0]
        ## we need to modify the icalendar code, update our own participant status
        self.icalendar_instance.pop('METHOD')
        self.change_attendee_status(partstat=partstat)
        self.get_property(cdav.ScheduleTag(), use_cached=True)
        try:
            calendar.save_event(self.data)
        except Exception as some_exception:
            ## TODO - TODO - TODO
            ## RFC6638 does not seem to be very clear (or
            ## perhaps I should read it more thoroughly) neither on
            ## how to handle conflicts, nor if the reply should be
            ## posted to the "outbox", saved back to the same url or
            ## sent to a calendar.
            self.load()
            self.get_property(cdav.ScheduleTag(), use_cached=False)
            outbox = self.client.principal().schedule_outbox()
            if calendar != outbox:
                self._reply_to_invite_request(partstat, calendar=outbox)
            else:
                self.save()

    def copy(self, keep_uid=False, new_parent=None):
        """
        Events, todos etc can be copied within the same calendar, to another
        calendar or even to another caldav server
        """
        return self.__class__(
            parent=new_parent or self.parent,
            data=self.data,
            id=self.id if keep_uid else str(uuid.uuid1()))

    def load(self):
        """
        Load the object from the caldav server.
        """
        r = self.client.request(self.url)
        if r.status == 404:
            raise error.NotFoundError(errmsg(r))
        self.data = vcal.fix(r.raw)
        if 'Etag' in r.headers:
            self.props[dav.GetEtag.tag] = r.headers['Etag']
        if 'Schedule-Tag' in r.headers:
            self.props[cdav.ScheduleTag.tag] = r.headers['Schedule-Tag']
        return self

    ## TODO: this method should be simplified and renamed, and probably
    ## some of the logic should be moved elsewhere
    def _create(self, data, id=None, path=None):
        if id is None and path is not None and str(path).endswith('.ics'):
            id = re.search('(/|^)([^/]*).ics', str(path)).group(2)
        elif id is None:
            for obj_type in ('vevent', 'vtodo', 'vjournal', 'vfreebusy'):
                obj = None
                if hasattr(self.vobject_instance, obj_type):
                    obj = getattr(self.vobject_instance, obj_type)
                elif self.vobject_instance.name.lower() == obj_type:
                    obj = self.vobject_instance
                if obj is not None:
                    try:
                        id = obj.uid.value
                    except AttributeError:
                        id = str(uuid.uuid1())
                        obj.add('uid')
                        obj.uid.value = id
                    break
        else:
            for obj_type in ('vevent', 'vtodo', 'vjournal', 'vfreebusy'):
                obj = None
                if hasattr(self.vobject_instance, obj_type):
                    obj = getattr(self.vobject_instance, obj_type)
                elif self.vobject_instance.name.lower() == obj_type:
                    obj = self.vobject_instance
                if obj is not None:
                    if not hasattr(obj, 'uid'):
                        obj.add('uid')
                    obj.uid.value = id
                    break
        if path is None:
            ## See https://github.com/python-caldav/caldav/issues/143 for the rationale behind double-quoting slashes
            ## TODO: should try to wrap my head around issues that arises when id contains weird characters.  maybe it's
            ## better to generate a new uuid here, particularly if id is in some unexpected format.
            path = quote(id.replace('/', '%2F')) + ".ics"
        path = self.parent.url.join(path)
        ## SECURITY TODO: we should probably have a check here to verify that no such object exists already
        r = self.client.put(path, data,
                            {"Content-Type": 'text/calendar; charset="utf-8"'})

        if r.status == 302:
            path = [x[1] for x in r.headers if x[0] == 'location'][0]
        elif not (r.status in (204, 201)):
            raise error.PutError(errmsg(r))

        self.url = URL.objectify(path)
        self.id = id

    def change_attendee_status(self, attendee=None, **kwargs):
        if not attendee:
            attendee = self.client.principal()

        cnt=0

        if isinstance(attendee, Principal):
            for addr in attendee.calendar_user_address_set():
                try:
                    self.change_attendee_status(addr, **kwargs)
                    ## TODO: can probably just return now
                    cnt += 1
                except error.NotFoundError:
                    pass
            if not cnt:
                raise error.NotFoundError("Principal %s is not invited to event" % str(attendee))
            error.assert_(cnt == 1)
            return

        ical_obj = self._icalendar_object()
        attendee_lines = ical_obj['attendee']
        if isinstance(attendee_lines, str):
            attendee_lines = [attendee_lines]
        strip_mailto = lambda x: str(x).replace('mailto:','').lower()
        for attendee_line in attendee_lines:
            if strip_mailto(attendee_line) == strip_mailto(attendee):
                   attendee_line.params.update(kwargs)
                   cnt += 1
        if not cnt:
            raise error.NotFoundError("Participant %s not found in attendee list")
        error.assert_(cnt == 1)

    def save(self, no_overwrite=False, no_create=False, obj_type=None, if_schedule_tag_match=False):
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
        if (self._vobject_instance is None and
            self._data is None and
            self._icalendar_instance is None):
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
                    if hasattr(component, 'uid'):
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
                methods = (self.parent.object_by_uid, self.parent.event_by_uid, self.parent.todo_by_uid, self.parent.journal_by_uid)
            for method in methods:
                try:
                    existing = method(self.id)
                    if no_overwrite:
                        raise error.ConsistencyError("no_overwrite flag was set, but object already exists")
                    break
                except error.NotFoundError:
                    pass

            if no_create and not existing:
                raise error.ConsistencyError("no_create flag was set, but object does not exists")


        ## ref https://github.com/python-caldav/caldav/issues/43
        ## we don't want to use vobject unless needed, but
        ## sometimes the caldav server may balk on slightly
        ## non-conforming icalendar data.  We'll just throw in a
        ## try-send-data-except-wash-through-vobject-logic here.
        try:
            self._create(self.data, self.id, path)
        except error.PutError:
            self._create(self.vobject_instance.serialize(), self.id, path)
        return self

    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, self.url)

    ## implementation of the properties self.data,
    ## self.vobject_instance and self.icalendar_instance follows.  The
    ## rule is that only one of them can be set at any time, this
    ## since vobject_instance and icalendar_instance are mutable,
    ## and any modification to those instances should apply
    def _set_data(self, data):
        ## The __init__ takes a data attribute, and it should be allowable to
        ## set it to an vobject object or an icalendar object, hence we should
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
            return self._data
        elif self._vobject_instance:
            return self._vobject_instance.serialize()
        elif self._icalendar_instance:
            return self._icalendar_instance.to_ical()
        return None

    data = property(_get_data, _set_data,
                    doc="vCal representation of the object")

    def _set_vobject_instance(self, inst):
        self._vobject_instance = inst
        self._data = None
        self._icalendar_instance = None
        return self

    def _get_vobject_instance(self):
        if not self._vobject_instance:
            if self._get_data() is None:
                return None
            try:
                self._set_vobject_instance(vobject.readOne(to_unicode(self._get_data())))
            except:
                log.critical("Something went wrong while loading icalendar data into the vobject class.  ical url: " + str(self.url))
                raise
        return self._vobject_instance

    vobject_instance = property(_get_vobject_instance, _set_vobject_instance,
                        doc="vobject instance of the object")

    def _set_icalendar_instance(self, inst):
        self._icalendar_instance = inst
        self._data = None
        self._vobject_instance = None
        return self

    def _get_icalendar_instance(self):
        import icalendar
        if not self._icalendar_instance:
            if not self.data:
                return None
            self.icalendar_instance = icalendar.Calendar.from_ical(to_unicode(self.data))
        return self._icalendar_instance

    icalendar_instance = property(_get_icalendar_instance, _set_icalendar_instance,
                        doc="icalendar instance of the object")

    ## for backward-compatibility - may be changed to
    ## icalendar_instance in version 1.0
    instance = vobject_instance

class Event(CalendarObjectResource):
    """
    The `Event` object is used to represent an event (VEVENT).

    As of 2020-12 it adds nothing to the inheritated class.  (I have
    frequently asked myself if we need those subclasses ... perhaps
    not)
    """
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

    Update: With RFC6638 a freebusy object can have an URL and an ID.
    """
    def __init__(self, parent, data, url=None, id=None):
        CalendarObjectResource.__init__(self, client=parent.client, url=url,
                                        data=data, parent=parent, id=id)

class Todo(CalendarObjectResource):
    """
    The `Todo` object is used to represent a todo item (VTODO).
    A Todo-object can be completed.
    """
    def complete(self, completion_timestamp=None):
        """Marks the task as completed.

        This method probably will do the wrong thing if the task is a
        recurring task, in version 1.0 this will likely be changed -
        see https://github.com/python-caldav/caldav/issues/127 for
        details.

        Parameters:
         * completion_timestamp - datetime object.  Defaults to
           datetime.now().

        """
        if not completion_timestamp:
            completion_timestamp = datetime.now()
        if not hasattr(self.vobject_instance.vtodo, 'status'):
            self.vobject_instance.vtodo.add('status')
        self.vobject_instance.vtodo.status.value = 'COMPLETED'
        self.vobject_instance.vtodo.add('completed').value = completion_timestamp
        self.save()
