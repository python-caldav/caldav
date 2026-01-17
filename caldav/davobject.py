import logging
import sys
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

from lxml import etree

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

from .elements import cdav, dav
from .elements.base import BaseElement
from .lib import error
from .lib.error import errmsg
from .lib.python_utilities import to_wire
from .lib.url import URL

_CC = TypeVar("_CC", bound="CalendarObjectResource")
log = logging.getLogger("caldav")


"""
This file contains one class, the DAVObject which is the base
class for Calendar, Principal, CalendarObjectResource (Event) and many
others.  There is some code here for handling some of the DAV-related
communication, and the class lists some common methods that are shared
on all kind of objects.  Library users should not need to know a lot
about the DAVObject class, should never need to initialize one, but
may encounter inheritated methods coming from this class.
"""


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

        Args:
          client: A DAVClient instance
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

    @property
    def is_async_client(self) -> bool:
        """Check if this object is connected to an async client.

        Returns:
            True if the client is an AsyncDAVClient, False otherwise.
        """
        if self.client is None:
            return False
        # Use string check to avoid circular imports
        return type(self.client).__name__ == "AsyncDAVClient"

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
        ## Late import to avoid circular imports
        from .collection import CalendarSet

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

        For async clients, returns a coroutine that must be awaited.
        """
        if self.is_async_client:
            return self._async_query_properties(props, depth)

        root = None
        # build the propfind request
        if props is not None and len(props) > 0:
            prop = dav.Prop() + props
            root = dav.Propfind() + prop

        return self._query(root, depth)

    async def _async_query_properties(
        self, props: Optional[Sequence[BaseElement]] = None, depth: int = 0
    ):
        """Async implementation of _query_properties."""
        root = None
        # build the propfind request
        if props is not None and len(props) > 0:
            prop = dav.Prop() + props
            root = dav.Propfind() + prop

        return await self._async_query(root, depth)

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

        For async clients, returns a coroutine that must be awaited.
        """
        if self.is_async_client:
            return self._async_query(
                root, depth, query_method, url, expected_return_value
            )

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
            ## TODO: server quirks!
            body = to_wire(body)
            if (
                ret.status == 500
                and b"D:getetag" not in body
                and b"<C:calendar-data" in body
            ):
                body = body.replace(
                    b"<C:calendar-data", b"<D:getetag/><C:calendar-data"
                )
                return self._query(
                    body, depth, query_method, url, expected_return_value
                )
            raise error.exception_by_method[query_method](errmsg(ret))
        return ret

    async def _async_query(
        self,
        root=None,
        depth=0,
        query_method="propfind",
        url=None,
        expected_return_value=None,
    ):
        """Async implementation of _query."""
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
        ret = await getattr(self.client, query_method)(url, body, depth)
        if ret.status == 404:
            raise error.NotFoundError(errmsg(ret))
        if (
            expected_return_value is not None and ret.status != expected_return_value
        ) or ret.status >= 400:
            ## COMPATIBILITY HACK - see https://github.com/python-caldav/caldav/issues/309
            body = to_wire(body)
            if (
                ret.status == 500
                and b"D:getetag" not in body
                and b"<C:calendar-data" in body
            ):
                body = body.replace(
                    b"<C:calendar-data", b"<D:getetag/><C:calendar-data"
                )
                return await self._async_query(
                    body, depth, query_method, url, expected_return_value
                )
            raise error.exception_by_method[query_method](errmsg(ret))
        return ret

    def get_property(
        self, prop: BaseElement, use_cached: bool = False, **passthrough
    ) -> Optional[str]:
        """
        Wrapper for the :class:`get_properties`, when only one property is wanted

        Args:

         prop: the property to search for
         use_cached: don't send anything to the server if we've asked before

        Other parameters are sent directly to the :class:`get_properties` method

        For async clients, returns a coroutine that must be awaited.
        """
        if self.is_async_client:
            return self._async_get_property(prop, use_cached, **passthrough)

        ## TODO: use_cached should probably be true
        if use_cached:
            if prop.tag in self.props:
                return self.props[prop.tag]
        foo = self.get_properties([prop], **passthrough)
        return foo.get(prop.tag, None)

    async def _async_get_property(
        self, prop: BaseElement, use_cached: bool = False, **passthrough
    ) -> Optional[str]:
        """Async implementation of get_property."""
        if use_cached:
            if prop.tag in self.props:
                return self.props[prop.tag]
        foo = await self._async_get_properties([prop], **passthrough)
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

        Args:
         props: ``[dav.ResourceType(), dav.DisplayName(), ...]``

        Returns:
          ``{proptag: value, ...}``

        For async clients, returns a coroutine that must be awaited.
        """
        if self.is_async_client:
            return self._async_get_properties(
                props, depth, parse_response_xml, parse_props
            )

        from .collection import (
            Principal,
        )  ## late import to avoid cyclic dependencies

        rc = None
        response = self._query_properties(props, depth)
        if not parse_response_xml:
            return response

        # Use protocol layer results when available and parse_props=True
        if parse_props and response.results:
            # Convert results to the expected {href: {tag: value}} format
            properties = {}
            for result in response.results:
                # Start with None for all requested props (for backward compat)
                result_props = {}
                if props:
                    for prop in props:
                        if prop.tag:
                            result_props[prop.tag] = None
                # Then overlay with actual values from server
                result_props.update(result.properties)
                properties[result.href] = result_props
        elif not parse_props:
            # Caller wants raw XML elements - use deprecated method
            properties = response.find_objects_and_props()
        else:
            # Fallback to expand_simple_props for mocked responses
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
                log.warning(
                    f"The path {path} was not found in the properties, but {exchange_path} was. "
                    "This may indicate a server bug or a trailing slash issue."
                )
            rc = properties[exchange_path]
        else:
            error.assert_(False)
        self.props.update(rc)
        return rc

    async def _async_get_properties(
        self,
        props: Optional[Sequence[BaseElement]] = None,
        depth: int = 0,
        parse_response_xml: bool = True,
        parse_props: bool = True,
    ):
        """Async implementation of get_properties."""
        from .collection import (
            Principal,
        )  ## late import to avoid cyclic dependencies

        rc = None
        response = await self._async_query_properties(props, depth)
        if not parse_response_xml:
            return response

        # Use protocol layer results when available and parse_props=True
        if parse_props and response.results:
            # Convert results to the expected {href: {tag: value}} format
            properties = {}
            for result in response.results:
                # Start with None for all requested props (for backward compat)
                result_props = {}
                if props:
                    for prop in props:
                        if prop.tag:
                            result_props[prop.tag] = None
                # Then overlay with actual values from server
                result_props.update(result.properties)
                properties[result.href] = result_props
        elif not parse_props:
            # Caller wants raw XML elements - use deprecated method
            properties = response.find_objects_and_props()
        else:
            # Fallback to expand_simple_props for mocked responses
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
                log.warning(
                    f"The path {path} was not found in the properties, but {exchange_path} was. "
                    "This may indicate a server bug or a trailing slash issue."
                )
            rc = properties[exchange_path]
        else:
            error.assert_(False)
        self.props.update(rc)
        return rc

    def set_properties(self, props: Optional[Any] = None) -> Self:
        """
        Set properties (PROPPATCH) for this object.

         * props = [dav.DisplayName('name'), ...]

        For async clients, returns a coroutine that must be awaited.

        Returns:
         * self
        """
        if self.is_async_client:
            return self._async_set_properties(props)

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

        r = self.client.proppatch(str(self.url), body)

        if r.status >= 400:
            raise error.PropsetError(errmsg(r))

        return self

    async def _async_set_properties(self, props: Optional[Any] = None) -> Self:
        """Async implementation of set_properties."""
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

        if r.status >= 400:
            raise error.PropsetError(errmsg(r))

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

        For sync clients, deletes and returns None.
        For async clients, returns a coroutine that must be awaited.

        Example (sync):
            obj.delete()

        Example (async):
            await obj.delete()
        """
        if self.url is not None:
            if self.client is None:
                raise ValueError("Unexpected value None for self.client")

            # Delegate to client for dual-mode support
            if self.is_async_client:
                return self._async_delete()

            r = self.client.delete(str(self.url))

            # TODO: find out why we get 404
            if r.status not in (200, 204, 404):
                raise error.DeleteError(errmsg(r))

    async def _async_delete(self) -> None:
        """Async implementation of delete."""
        if self.url is not None and self.client is not None:
            r = await self.client.delete(str(self.url))
            if r.status not in (200, 204, 404):
                raise error.DeleteError(errmsg(r))

    def get_display_name(self):
        """
        Get display name (calendar, principal, ...more?)
        """
        return self.get_property(dav.DisplayName(), use_cached=True)

    def __str__(self) -> str:
        try:
            return (
                str(self.get_property(dav.DisplayName(), use_cached=True)) or self.url
            )
        except:
            return str(self.url)

    def __repr__(self) -> str:
        return "%s(%s)" % (self.__class__.__name__, self.url)
