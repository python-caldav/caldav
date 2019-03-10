#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""
A "DAV object" is anything we get from the caldav server or push into the
caldav server, notably principal, calendars and calendar events.
"""

import vobject
import uuid
import re
import datetime
import tzlocal
from lxml import etree

try:
    from urllib.parse import unquote
except ImportError:
    from urllib import unquote

from caldav.lib import error, vcal
from caldav.lib.url import URL
from caldav.elements import dav, cdav
from caldav.lib.python_utilities import to_unicode


def errmsg(r):
    """Utility for formatting a response xml tree to an error string"""
    return "%s %s\n\n%s" % (r.status, r.reason, r.raw)

def _fix_tz(dt):
    """
    if the dt object is a date, do nothing.  if the dt object is a
    datetime and it has no tzinfo, assume it's localtime and set the
    tzinfo explicitly.
    """
    if hasattr(dt, 'tzname') and dt.tzname() is None:
        import pytz
        return dt.replace(tzinfo=pytz.utc)
        return dt.replace(tzinfo=tzlocal.get_localzone())

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

    def __init__(self, client=None, url=None, parent=None, name=None, id=None,
                 **extra):
        """
        Default constructor.

        Parameters:
         * client: A DAVClient instance
         * url: The url for this object.  May be a full URL or a relative URL.
         * parent: The parent object - used when creating objects
         * name: A displayname
         * id: The resource id (UID for an Event)
        """

        if client is None and parent is not None:
            client = parent.client
        self.client = client
        self.parent = parent
        self.name = name
        self.id = id
        self.extra_init_options = extra
        # url may be a path relative to the caldav root
        if client and url:
            self.url = client.url.join(url)
        else:
            self.url = URL.objectify(url)

    @property
    def canonical_url(self):
        return str(self.url.unauth())

    def children(self, type=None):
        """
        List children, using a propfind (resourcetype) on the parent object,
        at depth = 1.
        """
        c = []

        depth = 1
        properties = {}

        props = [dav.ResourceType(), dav.DisplayName()]
        response = self._query_properties(props, depth)
        properties = self._handle_prop_response(
            response=response, props=props, type=type, what='tag')

        for path in list(properties.keys()):
            resource_type = properties[path][dav.ResourceType.tag]
            resource_name = properties[path][dav.DisplayName.tag]

            if resource_type == type or type is None:
                # TODO: investigate the RFCs thoroughly - why does a "get
                # members of this collection"-request also return the
                # collection URL itself?
                # And why is the strip_trailing_slash-method needed?
                # The collection URL should always end with a slash according
                # to RFC 2518, section 5.2.
                if (self.url.strip_trailing_slash() !=
                        self.url.join(path).strip_trailing_slash()):
                    c.append((self.url.join(path), resource_type,
                              resource_name))

        return c

    def _query_properties(self, props=[], depth=0):
        """
        This is an internal method for doing a propfind query.  It's a
        result of code-refactoring work, attempting to consolidate
        similar-looking code into a common method.
        """
        root = None
        # build the propfind request
        if len(props) > 0:
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
        # ref https://bitbucket.org/cyrilrbt/caldav/issues/46 -
        # COMPATIBILITY ISSUE. The lines below seems to solve real
        # world problems, though I believe it's the wrong place to
        # inject the missing slash.
        # TODO: find out why the slash is missing and fix
        # it properly.
        # Background: Collection URLs ends with a slash,
        # non-collection URLs does not end with a slash.  If the
        # slash is missing, Servers MAY pretend it's present (RFC
        # 4918, section 5.2, collection resources), hence only some
        # few servers break when the slash is missing.  RFC 4918
        # specifies that collection URLs end with a slash while
        # non-collection URLs should not end with a slash.
        if url is None:
            url = self.url
            if not url.endswith('/'):
                url = URL(str(url) + '/')

        body = ""
        if root:
            body = etree.tostring(root.xmlelement(), encoding="utf-8",
                                  xml_declaration=True)
        ret = getattr(self.client, query_method)(
            url, body, depth)
        if ret.status == 404:
            raise error.NotFoundError(errmsg(ret))
        if ((expected_return_value is not None and
             ret.status != expected_return_value) or
            ret.status >= 400):
            raise error.exception_by_method[query_method](errmsg(ret))
        return ret

    def _handle_prop_response(self, response, props=[], type=None,
                              what='text'):
        """
        Internal method to massage an XML response into a dict.  (This
        method is a result of some code refactoring work, attempting
        to consolidate similar-looking code)
        """
        properties = {}
        # All items should be in a <D:response> element
        for r in response.tree.findall('.//' + dav.Response.tag):
            status = r.find('.//' + dav.Status.tag)
            if (' 200 ' not in status.text and
                ' 207 ' not in status.text and
                ' 404 ' not in status.text):
                raise error.ReportError(errmsg(response))
                # TODO: may be wrong error class
            href = unquote(r.find('.//' + dav.Href.tag).text)
            properties[href] = {}
            for p in props:
                t = r.find(".//" + p.tag)
                if t is None:
                    val = None
                elif t is not None and list(t):
                    if type is not None:
                        val = t.find(".//" + type)
                    else:
                        val = t.find(".//*")
                    if val is not None:
                        val = getattr(val, what)
                    else:
                        val = None
                else:
                    val = t.text
                properties[href][p.tag] = val

        return properties

    def get_properties(self, props=[], depth=0):
        """
        Get properties (PROPFIND) for this object. Works only for
        properties, that don't have complex types.

        Parameters:
         * props = [dav.ResourceType(), dav.DisplayName(), ...]

        Returns:
         * {proptag: value, ...}
        """
        rc = None
        response = self._query_properties(props, depth)
        properties = self._handle_prop_response(response, props)
        path = unquote(self.url.path)
        if path.endswith('/'):
            exchange_path = path[:-1]
        else:
            exchange_path = path + '/'

        if path in properties:
            rc = properties[path]
        elif exchange_path in properties:
            rc = properties[exchange_path]
        else:
            raise Exception("The CalDAV server you are using has "
                            "a problem with path handling.")

        return rc

    def set_properties(self, props=[]):
        """
        Set properties (PROPPATCH) for this object.

         * props = [dav.DisplayName('name'), ...]

        Returns:
         * self
        """
        prop = dav.Prop() + props
        set = dav.Set() + prop
        root = dav.PropertyUpdate() + set

        r = self._query(root, query_method='proppatch')

        statuses = r.tree.findall(".//" + dav.Status.tag)
        for s in statuses:
            if ' 200 ' not in s.text:
                raise error.PropsetError(errmsg(r))

        return self

    def save(self):
        """
        Save the object. This is an abstract method, that all classes
        derived .from DAVObject implement.

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
        return str(self.url)

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.url)


class CalendarSet(DAVObject):
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
        The calendar method will return a calendar object.  It will not
        initiate any communication with the server.

        Parameters:
         * name: return the calendar with this name
         * cal_id: return the calendar with this calendar id

        Returns:
         * Calendar(...)-object
        """
        return Calendar(self.client, name=name, parent=self,
                        url=self.url.join(cal_id), id=cal_id)


class Principal(DAVObject):
    """
    This class represents a DAV Principal. It doesn't do much, except
    keep track of the URLs for the calendar-home-set, etc.

    A principal MUST have a non-empty DAV:displayname property
    (defined in Section 13.2 of [RFC2518]),
    and a DAV:resourcetype property (defined in Section 13.9 of [RFC2518]).
    Additionally, a principal MUST report the DAV:principal XML element
    in the value of the DAV:resourcetype property.
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
        self.client = client
        self._calendar_home_set = None

        # backwards compatibility.
        if url is not None:
            self.url = client.url.join(URL.objectify(url))
        else:
            self.url = self.client.url
            cup = self.get_properties([dav.CurrentUserPrincipal()])
            self.url = self.client.url.join(
                URL.objectify(cup['{DAV:}current-user-principal']))

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

    @property
    def calendar_home_set(self):
        if not self._calendar_home_set:
            chs = self.get_properties([cdav.CalendarHomeSet()])
            self.calendar_home_set = chs[
                '{urn:ietf:params:xml:ns:caldav}calendar-home-set']
        return self._calendar_home_set

    @calendar_home_set.setter
    def calendar_home_set(self, url):
        if isinstance(url, CalendarSet):
            self._calendar_home_set = url
            return
        sanitized_url = URL.objectify(url)
        if (sanitized_url.hostname and
            sanitized_url.hostname != self.client.url.hostname):
            # icloud (and others?) having a load balanced system,
            # where each principal resides on one named host
            self.client.url = sanitized_url
        self._calendar_home_set = CalendarSet(
            self.client, self.client.url.join(sanitized_url))

    def calendars(self):
        """
        Return the principials calendars
        """
        return self.calendar_home_set.calendars()


class Calendar(DAVObject):
    """
    The `Calendar` object is used to represent a calendar collection.
    Refer to the RFC for details: http://www.ietf.org/rfc/rfc4791.txt
    """
    def _create(self, name, id=None, supported_calendar_component_set=None):
        """
        Create a new calendar with display name `name` in `parent`.
        """
        if id is None:
            id = str(uuid.uuid1())
        self.id = id

        path = self.parent.url.join(id)
        self.url = path

        # TODO: mkcalendar seems to ignore the body on most servers?
        # at least the name doesn't get set this way.
        # zimbra gives 500 (!) if body is omitted ...

        # ehm ... this element seems non-existent in the RFC?
        # Breaks with baikal, too ...
        # cal = cdav.CalendarCollection()
        # coll = dav.Collection() # + cal # also breaks on baikal,
        #                                # and probably not needed?
        # type = dav.ResourceType() ## probably not needed?

        prop = dav.Prop()  # + [type,]
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
        # (DAViCal, Zimbra, ...).  Better to be explicit.
        if name:
            try:
                self.set_properties([display_name])
            except:
                self.delete()
                raise

        # Special hack for Zimbra!  The calendar we've made exists at
        # the specified URL, and we can do operations like ls, even
        # PUT an event to the calendar.  Zimbra will enforce that the
        # event uuid matches the event url, and return either 201 or
        # 302 - but alas, try to do a GET towards the event and we
        # get 404!  But turn around and replace the calendar ID with
        # the calendar name in the URL and hey ... it works!

        # TODO: write test cases for calendars with non-trivial
        # names and calendars with names already matching existing
        # calendar urls and ensure they pass.
        zimbra_url = self.parent.url.join(name)
        try:
            ret = self.client.request(zimbra_url)
            if ret.status == 404:
                raise error.NotFoundError
            # special hack for radicale.
            # It will happily accept any calendar-URL without returning 404.
            ret = self.client.request(self.parent.url.join(
                'ANYTHINGGOESHEREthisshouldforsurereturn404'))
            if ret.status == 404:
                # insane server
                self.url = zimbra_url
        except error.NotFoundError:
            # sane server
            pass

    def add_event(self, ical):
        """
        Add a new event to the calendar, with the given ical.

        Parameters:
         * ical - ical object (text)
        """
        return Event(self.client, data=ical, parent=self).save()

    def add_todo(self, ical):
        """
        Add a new task to the calendar, with the given ical.

        Parameters:
         * ical - ical object (text)
        """
        return Todo(self.client, data=ical, parent=self).save()

    def add_journal(self, ical):
        """
        Add a new journal entry to the calendar, with the given ical.

        Parameters:
         * ical - ical object (text)
        """
        return Journal(self.client, data=ical, parent=self).save()

    def save(self):
        """
        The save method for a calendar is only used to create it, for now.
        We know we have to create it when we don't have a url.

        Returns:
         * self
        """
        if self.url is None:
            self._create(name=self.name, id=self.id, **self.extra_init_options)
            if not self.url.endswith('/'):
                self.url = URL.objectify(str(self.url) + '/')
        return self

    def date_search(self, start, end=None, compfilter="VEVENT", expand="maybe"):
        """
        Search events by date in the calendar. Recurring events are
        expanded if they are occuring during the specified time frame
        and if an end timestamp is given.

        Parameters:
         * start = datetime.today().
         * end = same as above.
         * compfilter = defaults to events only.  Set to None to fetch all
           calendar components.
         * expand - should recurrent events be expanded?  (to preserve backward-compatibility the default "maybe" will be changed into True unless the date_search is open-ended)

        Returns:
         * [CalendarObjectResource(), ...]

        """
        matches = []

        # build the request

        # fix missing tzinfo in the start and end datetimes
        start = _fix_tz(start)
        end = _fix_tz(end)

        ## fror backward compatibility
        if expand == 'maybe':
            expand = end

        # Some servers will raise an error if we send the expand flag
        # but don't set any end-date - expand doesn't make much sense
        # if we have one recurring event describing an indefinite
        # series of events.  Hence, if the end date is not set, we
        # skip asking for expanded events.
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
        response = self._query(root, 1, 'report')
        results = self._handle_prop_response(
            response=response, props=[cdav.CalendarData()])
        for r in results:
            matches.append(
                Event(self.client, url=self.url.join(r),
                      data=results[r][cdav.CalendarData.tag], parent=self))

        return matches

    def freebusy_request(self, start, end):
        """
        Search the calendar, but return only the free/busy information.

        Parameters:
         * start = datetime.today().
         * end = same as above.

        Returns:
         * [FreeBusy(), ...]

        """
        # fix missing tzinfo in the start and end datetimes
        start = _fix_tz(start)
        end = _fix_tz(end)

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

        response = self._query(root, 1, 'report')
        results = self._handle_prop_response(
            response=response, props=[cdav.CalendarData()])
        for r in results:
            matches.append(
                Todo(self.client, url=self.url.join(r),
                     data=results[r][cdav.CalendarData.tag], parent=self))
        return matches

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
                if not str(todo.url) in match_set:
                    match_set.add(str(todo.url))
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
                         datetime.datetime.now().strftime('%F%H%M%S')),
                'hasnt_started':
                    (hasattr(vtodo, 'dtstart') and
                     vtodo.dtstart.value.strftime('%F%H%M%S') >
                     datetime.datetime.now().strftime('%F%H%M%S'))
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
        for line in data.split('\n'):
            if line == 'BEGIN:VEVENT':
                return Event
            if line == 'BEGIN:VTODO':
                return Todo
            if line == 'BEGIN:VJOURNAL':
                return Journal
            if line == 'BEGIN:VFREEBUSY':
                return FreeBusy

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

        response = self._query(root, 1, 'report')

        if response.status == 404:
            raise error.NotFoundError(errmsg(response))
        elif response.status == 400:
            raise error.ReportError(errmsg(response))

        items_found = response.tree.findall(".//" + dav.Response.tag)
        for r in items_found:
            href = unquote(r.find(".//" + dav.Href.tag).text)
            data = unquote(r.find(".//" + cdav.CalendarData.tag).text)
            # Ref Lucas Verney, we've actually done a substring search, if the
            # uid given in the query is short (i.e. just "0") we're likely to
            # get false positives back from the server.
            #
            # Long uids are folded, so splice the lines together here before
            # attempting a match.
            item_uid = re.search(r'\nUID:((.|\n[ \t])*)\n', data)
            if (not item_uid or
                    re.sub(r'\n[ \t]', '', item_uid.group(1)) != uid):
                continue
            return self._calendar_comp_class_by_data(data)(
                self.client, url=URL.objectify(href), data=data, parent=self)
        raise error.NotFoundError(errmsg(response))

    def todo_by_uid(self, uid):
        return self.object_by_uid(uid, comp_filter=cdav.CompFilter("VTODO"))

    def event_by_uid(self, uid):
        return self.object_by_uid(uid, comp_filter=cdav.CompFilter("VEVENT"))
    # alias for backward compatibility
    event = event_by_uid

    def events(self):
        """
        List all events from the calendar.

        Returns:
         * [Event(), ...]
        """
        all = []

        data = cdav.CalendarData()
        prop = dav.Prop() + data
        vevent = cdav.CompFilter("VEVENT")
        vcalendar = cdav.CompFilter("VCALENDAR") + vevent
        filter = cdav.Filter() + vcalendar
        root = cdav.CalendarQuery() + [prop, filter]

        response = self._query(root, 1, query_method='report')
        results = self._handle_prop_response(
            response, props=[cdav.CalendarData()])
        for r in results:
            all.append(Event(
                self.client, url=self.url.join(r),
                data=results[r][cdav.CalendarData.tag], parent=self))

        return all

    def journals(self):
        """
        List all journals from the calendar.

        Returns:
         * [Journal(), ...]
        """
        # TODO: this is basically a copy of events() - can we do more
        # refactoring and consolidation here?  Maybe it's wrong to do
        # separate methods for journals, todos and events?
        all = []

        data = cdav.CalendarData()
        prop = dav.Prop() + data
        vevent = cdav.CompFilter("VJOURNAL")
        vcalendar = cdav.CompFilter("VCALENDAR") + vevent
        filter = cdav.Filter() + vcalendar
        root = cdav.CalendarQuery() + [prop, filter]

        response = self._query(root, 1, query_method='report')
        results = self._handle_prop_response(
            response, props=[cdav.CalendarData()])
        for r in results:
            all.append(Journal(
                self.client, url=self.url.join(r),
                data=results[r][cdav.CalendarData.tag], parent=self))

        return all


class CalendarObjectResource(DAVObject):
    """
    Ref RFC 4791, section 4.1, a "Calendar Object Resource" can be an
    event, a todo-item, a journal entry, or a free/busy entry
    """
    _vobject_instance = None
    _data = None

    def __init__(self, client=None, url=None, data=None, parent=None, id=None):
        """
        CalendarObjectResource has an additional parameter for its constructor:
         * data = "...", vCal data for the event
        """
        DAVObject.__init__(self, client=client, url=url, parent=parent, id=id)
        if data is not None:
            self.data = data

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
        return self

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
                    id = obj.uid.value
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
                    obj.uid = id
                    break
        if path is None:
            path = id + ".ics"
        path = self.parent.url.join(path)
        r = self.client.put(path, data,
                            {"Content-Type": 'text/calendar; charset="utf-8"'})

        if r.status == 302:
            path = [x[1] for x in r.headers if x[0] == 'location'][0]
        elif not (r.status in (204, 201)):
            raise error.PutError(errmsg(r))

        self.url = URL.objectify(path)
        self.id = id

    def save(self):
        """
        Save the object, can be used for creation and update.

        Returns:
         * self
        """
        if self._vobject_instance is None and self._data is None:
            return self
        path = self.url.path if self.url else None

        if self._vobject_instance is None:
            ## ref https://github.com/python-caldav/caldav/issues/43
            ## we don't want to use vobject unless needed, but
            ## sometimes the caldav server may balk on slightly
            ## non-conforming icalendar data.  We'll just throw in a
            ## try-send-data-except-wash-through-vobject-logic here.
            try:
                self._create(self._data, self.id, path)
            except error.PutError:
                self._create(self.vobject_instance.serialize(), self.id, path)
        else:
            self._create(self._vobject_instance.serialize(), self.id, path)
        return self

    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, self.url)

    def _set_data(self, data):
        if type(data).__module__.startswith("vobject"):
            self._data = self._vobject_instance
            self._vobject_instance = data
        else:
            self._data = vcal.fix(data)
            self._vobject_instance = None
            #self._instance = vobject.readOne(to_unicode(self._data))
        return self

    def _get_data(self):
        return self._data
    data = property(_get_data, _set_data,
                    doc="vCal representation of the object")

    def _set_vobject_instance(self, inst):
        self._vobject_instance = inst
        self._data = inst.serialize()
        return self

    def _get_vobject_instance(self):
        if not self._vobject_instance and self._data:
            self._vobject_instance = vobject.readOne(to_unicode(self._data))
        return self._vobject_instance

    vobject_instance = property(_get_vobject_instance, _set_vobject_instance,
                        doc="vobject instance of the object")
    ## for backward-compatibility
    instance = vobject_instance


class Event(CalendarObjectResource):
    """
    The `Event` object is used to represent an event (VEVENT).
    """
    pass


class Journal(CalendarObjectResource):
    """
    The `Journal` object is used to represent a journal entry (VJOURNAL).
    """
    pass


class FreeBusy(CalendarObjectResource):
    """
    The `FreeBusy` object is used to represent a freebusy response from the
    server.
    """
    def __init__(self, parent, data):
        """
        A freebusy response object has no URL or ID (TODO: reconsider the
        class hierarchy?  most of the inheritated methods are moot and
        will fail?).  Raw response can be accessed through self.data,
        instantiated vobject as self.vobject_instance.
        """
        CalendarObjectResource.__init__(self, client=parent.client, url=None,
                                        data=data, parent=parent, id=None)


class Todo(CalendarObjectResource):
    """
    The `Todo` object is used to represent a todo item (VTODO).
    """
    def complete(self, completion_timestamp=None):
        """
        Marks the task as completed.

        Parameters:
         * completion_timestamp - datetime object.  Defaults to
           datetime.datetime.now().
        """
        if not completion_timestamp:
            completion_timestamp = datetime.datetime.now()
        if not hasattr(self.vobject_instance.vtodo, 'status'):
            self.vobject_instance.vtodo.add('status')
        self.vobject_instance.vtodo.status.value = 'COMPLETED'
        self.vobject_instance.vtodo.add('completed').value = completion_timestamp
        self.save()
