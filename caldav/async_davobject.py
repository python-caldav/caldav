#!/usr/bin/env python
"""
Async-first DAVObject implementation for the caldav library.

This module provides async versions of the DAV object classes.
For sync usage, see the davobject.py wrapper.
"""

import sys
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple, Union
from urllib.parse import ParseResult, SplitResult, quote, unquote

from lxml import etree

from caldav.elements import cdav, dav
from caldav.elements.base import BaseElement
from caldav.lib import error
from caldav.lib.python_utilities import to_wire
from caldav.lib.url import URL
from caldav.objects import errmsg, log

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

if TYPE_CHECKING:
    from caldav.async_davclient import AsyncDAVClient


class AsyncDAVObject:
    """
    Async base class for all DAV objects. Can be instantiated by a client
    and an absolute or relative URL, or from the parent object.
    """

    id: Optional[str] = None
    url: Optional[URL] = None
    client: Optional["AsyncDAVClient"] = None
    parent: Optional["AsyncDAVObject"] = None
    name: Optional[str] = None

    def __init__(
        self,
        client: Optional["AsyncDAVClient"] = None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        parent: Optional["AsyncDAVObject"] = None,
        name: Optional[str] = None,
        id: Optional[str] = None,
        props: Optional[Dict[str, Any]] = None,
        **extra: Any,
    ) -> None:
        """
        Default constructor.

        Args:
          client: An AsyncDAVClient instance
          url: The url for this object.  May be a full URL or a relative URL.
          parent: The parent object - used when creating objects
          name: A displayname - to be removed at some point, see https://github.com/python-caldav/caldav/issues/128 for details
          props: a dict with known properties for this object
          id: The resource id (UID for an Event)
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

    async def children(self, type: Optional[str] = None) -> List[Tuple[URL, Any, Any]]:
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
        ## Late import to avoid circular imports
        from .async_collection import AsyncCalendarSet

        c = []

        depth = 1

        if self.url is None:
            raise ValueError("Unexpected value None for self.url")

        props = [dav.DisplayName()]
        multiprops = [dav.ResourceType()]
        props_multiprops = props + multiprops
        response = await self._query_properties(props_multiprops, depth)
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
                if (isinstance(self, AsyncCalendarSet) and type == cdav.Calendar.tag) or (
                    self.url.canonical().strip_trailing_slash()
                    != self.url.join(path).canonical().strip_trailing_slash()
                ):
                    c.append((self.url.join(path), resource_types, resource_name))

        ## TODO: return objects rather than just URLs, and include
        ## the properties we've already fetched
        return c

    async def _query_properties(
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

        if self.url is None:
            raise ValueError("Unexpected value None for self.url")
        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        ret = await self.client.propfind(str(self.url), body, depth)

        if ret.status == 404:
            raise error.NotFoundError(errmsg(ret))
        if ret.status >= 400:
            ## COMPATIBILITY HACK - see https://github.com/python-caldav/caldav/issues/309
            ## TODO: server quirks!
            body_bytes = to_wire(body)
            if (
                ret.status == 500
                and b"D:getetag" not in body_bytes
                and b"<C:calendar-data" in body_bytes
            ):
                body_bytes = body_bytes.replace(
                    b"<C:calendar-data", b"<D:getetag/><C:calendar-data"
                )
                return await self._query_properties_with_body(body_bytes, depth)
            raise error.PropfindError(errmsg(ret))
        return ret

    async def _query_properties_with_body(self, body: bytes, depth: int = 0):
        """Helper method for retrying propfind with modified body."""
        if self.url is None:
            raise ValueError("Unexpected value None for self.url")
        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        ret = await self.client.propfind(str(self.url), body, depth)
        if ret.status == 404:
            raise error.NotFoundError(errmsg(ret))
        if ret.status >= 400:
            raise error.PropfindError(errmsg(ret))
        return ret

    async def get_property(
        self, prop: BaseElement, use_cached: bool = False, **passthrough: Any
    ) -> Optional[str]:
        """
        Wrapper for the get_properties, when only one property is wanted

        Args:

         prop: the property to search for
         use_cached: don't send anything to the server if we've asked before

        Other parameters are sent directly to the get_properties method
        """
        ## TODO: use_cached should probably be true
        if use_cached:
            if prop.tag in self.props:
                return self.props[prop.tag]
        foo = await self.get_properties([prop], **passthrough)
        return foo.get(prop.tag, None)

    async def get_properties(
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
        AsyncDAVResponse object will be returned, and it's up to the caller
        to decode.  With parse_props set to false but
        parse_response_xml set to true, xml elements will be returned
        rather than values.

        Args:
         props: ``[dav.ResourceType(), dav.DisplayName(), ...]``

        Returns:
          ``{proptag: value, ...}``

        """
        from .async_collection import AsyncPrincipal  ## late import to avoid cyclic dependencies

        rc = None
        response = await self._query_properties(props, depth)
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
            if not isinstance(self, AsyncPrincipal):
                ## Some caldav servers reports the URL for the current
                ## principal to end with / when doing a propfind for
                ## current-user-principal - I believe that's a bug,
                ## the principal is not a collection and should not
                ## end with /.  (example in rfc5397 does not end with /).
                ## ... but it gets worse ... when doing a propfind on the
                ## principal, the href returned may be without the slash.
                ## Such inconsistency is clearly a bug.
                log.warning(
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
            log.warning(
                "Possibly the server has a path handling problem, possibly the URL configured is wrong.\n"
                "Path expected: %s, path found: %s %s.\n"
                "Continuing, probably everything will be fine"
                % (path, str(list(properties)), error.ERR_FRAGMENT)
            )
            rc = list(properties.values())[0]
        else:
            log.warning(
                "Possibly the server has a path handling problem.  Path expected: %s, paths found: %s %s"
                % (path, str(list(properties)), error.ERR_FRAGMENT)
            )
            error.assert_(False)

        if parse_props:
            if rc is None:
                raise ValueError("Unexpected value None for rc")

            self.props.update(rc)
        return rc

    async def set_properties(self, props: Optional[Any] = None) -> Self:
        """
        Set properties (PROPPATCH) for this object.

         * props = [dav.DisplayName('name'), ...]

        Returns:
         * self
        """
        props = [] if props is None else props
        prop = dav.Prop() + props
        set_elem = dav.Set() + prop
        root = dav.PropertyUpdate() + set_elem

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

        if self.url is None:
            raise ValueError("Unexpected value None for self.url")
        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        r = await self.client.proppatch(str(self.url), body)

        statuses = r.tree.findall(".//" + dav.Status.tag)
        for s in statuses:
            if " 200 " not in s.text:
                raise error.PropsetError(s.text)

        return self

    async def save(self) -> Self:
        """
        Save the object. This is an abstract method, that all classes
        derived from AsyncDAVObject implement.

        Returns:
         * self
        """
        raise NotImplementedError()

    async def delete(self) -> None:
        """
        Delete the object.
        """
        if self.url is not None:
            if self.client is None:
                raise ValueError("Unexpected value None for self.client")

            r = await self.client.delete(str(self.url))

            # TODO: find out why we get 404
            if r.status not in (200, 204, 404):
                raise error.DeleteError(errmsg(r))

    async def get_display_name(self) -> Optional[str]:
        """
        Get display name (calendar, principal, ...more?)
        """
        return await self.get_property(dav.DisplayName(), use_cached=True)

    def __str__(self) -> str:
        try:
            # Use cached property if available, otherwise return URL
            # We can't await async methods in __str__
            return (
                str(self.props.get(dav.DisplayName.tag)) or str(self.url)
            )
        except Exception:
            return str(self.url)

    def __repr__(self) -> str:
        return "%s(%s)" % (self.__class__.__name__, self.url)


class AsyncCalendarObjectResource(AsyncDAVObject):
    """
    Async version of CalendarObjectResource.

    Ref RFC 4791, section 4.1, a "Calendar Object Resource" can be an
    event, a todo-item, a journal entry, or a free/busy entry.

    NOTE: This is a streamlined implementation for Phase 2. Full feature
    parity with sync CalendarObjectResource will be achieved in later phases.
    """

    _ENDPARAM: Optional[str] = None

    _vobject_instance: Any = None
    _icalendar_instance: Any = None
    _data: Any = None

    def __init__(
        self,
        client: Optional["AsyncDAVClient"] = None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        data: Optional[Any] = None,
        parent: Optional["AsyncDAVObject"] = None,
        id: Optional[Any] = None,
        props: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        AsyncCalendarObjectResource has an additional parameter for its constructor:
         * data = "...", vCal data for the event
        """
        super().__init__(
            client=client, url=url, parent=parent, id=id, props=props
        )
        if data is not None:
            self.data = data  # type: ignore
            if id:
                try:
                    import icalendar
                    old_id = self.icalendar_component.pop("UID", None)
                    self.icalendar_component.add("UID", id)
                except Exception:
                    pass  # If icalendar is not available or data is invalid

    @property
    def data(self) -> Any:
        """Get the iCalendar data."""
        from caldav.lib.python_utilities import to_normal_str

        if self._data is None and self._icalendar_instance is not None:
            self._data = to_normal_str(self._icalendar_instance.to_ical())
        if self._data is None and self._vobject_instance is not None:
            self._data = to_normal_str(self._vobject_instance.serialize())
        return self._data

    @data.setter
    def data(self, value: Any) -> None:
        """Set the iCalendar data and invalidate cached instances."""
        self._data = value
        self._icalendar_instance = None
        self._vobject_instance = None

    @property
    def icalendar_instance(self) -> Any:
        """Get the icalendar instance, parsing data if needed."""
        if self._icalendar_instance is None and self._data:
            try:
                import icalendar
                self._icalendar_instance = icalendar.Calendar.from_ical(self._data)
            except Exception as e:
                log.error(f"Failed to parse icalendar data: {e}")
        return self._icalendar_instance

    @property
    def icalendar_component(self) -> Any:
        """Get the main icalendar component (Event, Todo, Journal, etc.)."""
        if not self.icalendar_instance:
            return None
        import icalendar
        for component in self.icalendar_instance.subcomponents:
            if not isinstance(component, icalendar.Timezone):
                return component
        return None

    @property
    def vobject_instance(self) -> Any:
        """Get the vobject instance, parsing data if needed."""
        if self._vobject_instance is None and self._data:
            try:
                import vobject
                self._vobject_instance = vobject.readOne(self._data)
            except Exception as e:
                log.error(f"Failed to parse vobject data: {e}")
        return self._vobject_instance

    def is_loaded(self) -> bool:
        """Returns True if there exists data in the object."""
        return (
            (self._data and str(self._data).count("BEGIN:") > 1)
            or self._vobject_instance is not None
            or self._icalendar_instance is not None
        )

    async def load(self, only_if_unloaded: bool = False) -> Self:
        """
        (Re)load the object from the caldav server.
        """
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
            self.data = r.raw  # type: ignore
        except error.NotFoundError:
            raise
        except Exception:
            return await self.load_by_multiget()

        if "Etag" in r.headers:
            self.props[dav.GetEtag.tag] = r.headers["Etag"]
        if "Schedule-Tag" in r.headers:
            self.props[cdav.ScheduleTag.tag] = r.headers["Schedule-Tag"]
        return self

    async def load_by_multiget(self) -> Self:
        """
        Some servers do not accept a GET, but we can still do a REPORT
        with a multiget query.

        NOTE: This requires async collection support (Phase 3).
        """
        raise NotImplementedError(
            "load_by_multiget() requires async collections (Phase 3). "
            "For now, use the regular load() method or the sync API."
        )

    async def _put(self, retry_on_failure: bool = True) -> None:
        """Upload the calendar data to the server."""
        if self.url is None:
            raise ValueError("Unexpected value None for self.url")
        if self.client is None:
            raise ValueError("Unexpected value None for self.client")

        r = await self.client.put(
            str(self.url), str(self.data), {"Content-Type": 'text/calendar; charset="utf-8"'}
        )

        if r.status == 302:
            # Handle redirects
            path = [x[1] for x in r.headers if x[0] == "location"][0]
            self.url = URL.objectify(path)
        elif r.status not in (204, 201):
            if retry_on_failure:
                try:
                    import vobject
                    # This looks like a noop, but the object may be "cleaned"
                    # See https://github.com/python-caldav/caldav/issues/43
                    self.vobject_instance
                    return await self._put(False)
                except ImportError:
                    pass
            raise error.PutError(errmsg(r))

    async def _create(self, id: Optional[str] = None, path: Optional[str] = None) -> None:
        """Create a new calendar object on the server."""
        await self._find_id_path(id=id, path=path)
        await self._put()

    async def _find_id_path(self, id: Optional[str] = None, path: Optional[str] = None) -> None:
        """
        Determine the ID and path for this calendar object.

        With CalDAV, every object has a URL.  With icalendar, every object
        should have a UID.  This UID may or may not be copied into self.id.

        This method will determine the proper UID and generate the URL if needed.
        """
        import re
        import uuid

        i = self.icalendar_component
        if not i:
            raise ValueError("No icalendar component found")

        if not id and getattr(self, "id", None):
            id = self.id
        if not id:
            id = i.pop("UID", None)
            if id:
                id = str(id)
        if not path and getattr(self, "path", None):
            path = self.path  # type: ignore
        if id is None and path is not None and str(path).endswith(".ics"):
            id = re.search(r"(/|^)([^/]*).ics", str(path)).group(2)
        if id is None:
            id = str(uuid.uuid1())

        i.pop("UID", None)
        i.add("UID", id)

        self.id = id
        # Invalidate cached data since we modified the icalendar component
        self._data = None

        if path is None:
            path = self._generate_url()
        else:
            if self.parent is None:
                raise ValueError("Unexpected value None for self.parent")
            path = self.parent.url.join(path)  # type: ignore

        self.url = URL.objectify(path)

    def _generate_url(self) -> URL:
        """Generate a URL for this calendar object based on its UID."""
        if not self.id:
            self.id = self.icalendar_component["UID"]
        if self.parent is None:
            raise ValueError("Unexpected value None for self.parent")
        # See https://github.com/python-caldav/caldav/issues/143 for the rationale behind double-quoting slashes
        return self.parent.url.join(quote(str(self.id).replace("/", "%2F")) + ".ics")  # type: ignore

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
        """
        Save the object, can be used for creation and update.

        NOTE: This is a simplified implementation for Phase 2.
        Full recurrence handling and all edge cases will be implemented in later phases.

        Args:
            no_overwrite: Raise an error if the object already exists
            no_create: Raise an error if the object doesn't exist
            obj_type: Object type (event, todo, journal) for searching
            increase_seqno: Increment the SEQUENCE field
            if_schedule_tag_match: Match schedule tag (TODO: implement)
            only_this_recurrence: Save only this recurrence instance
            all_recurrences: Save all recurrences

        Returns:
            self
        """
        # Basic validation
        if (
            self._vobject_instance is None
            and self._data is None
            and self._icalendar_instance is None
        ):
            return self

        path = self.url.path if self.url else None

        # NOTE: no_create/no_overwrite validation is handled in the sync wrapper
        # because it requires collection methods (event_by_uid, etc.) which are Phase 3 work.
        # For Phase 2, the sync wrapper performs the validation before calling async save().

        # TODO: Implement full recurrence handling

        # Handle SEQUENCE increment
        if increase_seqno and "SEQUENCE" in self.icalendar_component:
            seqno = self.icalendar_component.pop("SEQUENCE", None)
            if seqno is not None:
                self.icalendar_component.add("SEQUENCE", seqno + 1)

        await self._create(id=self.id, path=path)
        return self


class AsyncEvent(AsyncCalendarObjectResource):
    """Async version of Event. Uses DTEND as the end parameter."""

    _ENDPARAM = "DTEND"


class AsyncTodo(AsyncCalendarObjectResource):
    """Async version of Todo. Uses DUE as the end parameter."""

    _ENDPARAM = "DUE"


class AsyncJournal(AsyncCalendarObjectResource):
    """Async version of Journal. Has no end parameter."""

    _ENDPARAM = None


class AsyncFreeBusy(AsyncCalendarObjectResource):
    """Async version of FreeBusy. Has no end parameter."""

    _ENDPARAM = None
