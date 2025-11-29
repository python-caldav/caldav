#!/usr/bin/env python
"""
Async DAVObject base class - the foundation for all DAV objects.

This is the async implementation that the sync wrapper delegates to.
"""
import logging
import sys
from typing import Any
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import TYPE_CHECKING
from typing import Union
from urllib.parse import ParseResult
from urllib.parse import quote
from urllib.parse import SplitResult
from urllib.parse import unquote

from lxml import etree

if TYPE_CHECKING:
    from caldav._async.davclient import AsyncDAVClient

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

from caldav.elements import cdav, dav
from caldav.elements.base import BaseElement
from caldav.lib import error
from caldav.lib.error import errmsg
from caldav.lib.python_utilities import to_wire
from caldav.lib.url import URL

log = logging.getLogger("caldav")


class AsyncDAVObject:
    """
    Async base class for all DAV objects.
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
        props=None,
        **extra,
    ) -> None:
        """
        Default constructor.

        Args:
            client: An AsyncDAVClient instance
            url: The url for this object
            parent: The parent object
            name: A displayname
            props: a dict with known properties
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
        """List children using a propfind at depth=1."""
        from caldav._async.collection import AsyncCalendarSet

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
                    path = quote(path)
                if (
                    isinstance(self, AsyncCalendarSet) and type == cdav.Calendar.tag
                ) or (
                    self.url.canonical().strip_trailing_slash()
                    != self.url.join(path).canonical().strip_trailing_slash()
                ):
                    c.append((self.url.join(path), resource_types, resource_name))

        return c

    async def _query_properties(
        self, props: Optional[Sequence[BaseElement]] = None, depth: int = 0
    ):
        """Internal method for doing a propfind query."""
        root = None
        if props is not None and len(props) > 0:
            prop = dav.Prop() + props
            root = dav.Propfind() + prop

        return await self._query(root, depth)

    async def _query(
        self,
        root=None,
        depth=0,
        query_method="propfind",
        url=None,
        expected_return_value=None,
    ):
        """Internal method for doing a query."""
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
            body = to_wire(body)
            if (
                ret.status == 500
                and b"D:getetag" not in body
                and b"<C:calendar-data" in body
            ):
                body = body.replace(
                    b"<C:calendar-data", b"<D:getetag/><C:calendar-data"
                )
                return await self._query(
                    body, depth, query_method, url, expected_return_value
                )
            raise error.exception_by_method[query_method](errmsg(ret))
        return ret

    async def get_property(
        self, prop: BaseElement, use_cached: bool = False, **passthrough
    ) -> Optional[str]:
        """Get a single property."""
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
        """Get properties (PROPFIND) for this object."""
        from caldav._async.collection import AsyncPrincipal

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
                log.warning(
                    "potential path handling problem with ending slashes. Path given: %s, path found: %s. %s"
                    % (path, exchange_path, error.ERR_FRAGMENT)
                )
                error.assert_(False)
            rc = properties[exchange_path]
        elif self.url in properties:
            rc = properties[self.url]
        elif "/principal/" in properties and path.endswith("/principal/"):
            rc = properties["/principal/"]
        elif "//" in path and path.replace("//", "/") in properties:
            rc = properties[path.replace("//", "/")]
        elif len(properties) == 1:
            log.warning(
                "Possibly the server has a path handling problem, possibly the URL configured is wrong.\n"
                "Path expected: %s, path found: %s %s.\n"
                "Continuing, probably everything will be fine"
                % (path, str(list(properties)), error.ERR_FRAGMENT)
            )
            rc = list(properties.values())[0]
        else:
            log.warning(
                "Possibly the server has a path handling problem. Path expected: %s, paths found: %s %s"
                % (path, str(list(properties)), error.ERR_FRAGMENT)
            )
            error.assert_(False)

        if parse_props:
            if rc is None:
                raise ValueError("Unexpected value None for rc")
            self.props.update(rc)
        return rc

    async def set_properties(self, props: Optional[Any] = None) -> Self:
        """Set properties (PROPPATCH) for this object."""
        props = [] if props is None else props
        prop = dav.Prop() + props
        set = dav.Set() + prop
        root = dav.PropertyUpdate() + set

        r = await self._query(root, query_method="proppatch")

        statuses = r.tree.findall(".//" + dav.Status.tag)
        for s in statuses:
            if " 200 " not in s.text:
                raise error.PropsetError(s.text)

        return self

    async def save(self) -> Self:
        """Save the object - abstract method."""
        raise NotImplementedError()

    async def delete(self) -> None:
        """Delete the object."""
        if self.url is not None:
            if self.client is None:
                raise ValueError("Unexpected value None for self.client")

            r = await self.client.delete(str(self.url))

            if r.status not in (200, 204, 404):
                raise error.DeleteError(errmsg(r))

    async def get_display_name(self):
        """Get display name."""
        return await self.get_property(dav.DisplayName(), use_cached=True)

    def __str__(self) -> str:
        return str(self.url)

    def __repr__(self) -> str:
        return "%s(%s)" % (self.__class__.__name__, self.url)
