"""
Async base class for all DAV objects.

This module provides AsyncDAVObject which is the async equivalent of DAVObject.
It serves as the base class for AsyncPrincipal, AsyncCalendar, AsyncEvent, etc.
"""
import logging
import sys
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import TYPE_CHECKING
from typing import Union
from urllib.parse import ParseResult
from urllib.parse import SplitResult

from lxml import etree

from .elements import cdav
from .elements import dav
from .elements.base import BaseElement
from .lib import error
from .lib.python_utilities import to_wire
from .lib.url import URL

if TYPE_CHECKING:
    from .async_davclient import AsyncDAVClient

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

log = logging.getLogger("caldav")


class AsyncDAVObject:
    """
    Async base class for all DAV objects.

    This mirrors DAVObject but provides async methods for all operations
    that require HTTP communication.
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
          name: A display name
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

        # URL handling
        path = None
        if url is not None:
            self.url = URL.objectify(url)
        elif parent is not None:
            if name is not None:
                path = name
            elif id is not None:
                path = id
                if not path.endswith(".ics"):
                    path += ".ics"
            if path:
                self.url = parent.url.join(path)
            # else: Don't set URL to parent.url - let subclass or save() generate it properly

    def canonical_url(self) -> str:
        """Return the canonical URL for this object"""
        return str(self.url.canonical() if hasattr(self.url, "canonical") else self.url)

    async def _query_properties(
        self, props: Optional[List[BaseElement]] = None, depth: int = 0
    ):
        """
        Query properties for this object.

        Internal method used by get_properties and get_property.
        """
        from .elements import dav

        root = dav.Propfind() + [dav.Prop() + props]
        return await self._query(root, depth)

    async def _query(
        self, root: BaseElement, depth: int = 0, query_method: str = "propfind"
    ):
        """
        Execute a DAV query.

        Args:
            root: The XML element to send
            depth: Query depth
            query_method: HTTP method to use (propfind, report, etc.)
        """
        body = etree.tostring(root.xmlelement(), encoding="utf-8", xml_declaration=True)
        ret = await getattr(self.client, query_method)(
            self.url.canonical() if hasattr(self.url, "canonical") else str(self.url),
            body,
            depth,
        )
        return ret

    async def get_property(
        self, prop: BaseElement, use_cached: bool = False, **passthrough
    ) -> Any:
        """
        Get a single property for this object.

        Args:
            prop: The property to fetch
            use_cached: Whether to use cached properties
            **passthrough: Additional arguments for get_properties
        """
        foo = await self.get_properties([prop], **passthrough)
        keys = [x for x in foo.keys()]
        error.assert_(len(keys) == 1)
        val = foo[keys[0]]
        if prop.tag in val:
            return val[prop.tag]
        return None

    async def get_properties(
        self,
        props: Optional[List[BaseElement]] = None,
        depth: int = 0,
        parse_response_xml: bool = True,
        parse_props: bool = True,
    ) -> Dict:
        """
        Get multiple properties for this object.

        Args:
            props: List of properties to fetch
            depth: Query depth
            parse_response_xml: Whether to parse response XML
            parse_props: Whether to parse property values
        """
        if props is None or len(props) == 0:
            props = []
            for p in [
                dav.ResourceType(),
                dav.DisplayName(),
                dav.Href(),
                dav.SyncToken(),
                cdav.CalendarDescription(),
                cdav.CalendarColor(),
                dav.CurrentUserPrincipal(),
                cdav.CalendarHomeSet(),
                cdav.CalendarUserAddressSet(),
            ]:
                props.append(p)

        response = await self._query_properties(props, depth)
        if not parse_response_xml:
            return response
        if not parse_props:
            return response.find_objects_and_props()
        return response.expand_simple_props(props)

    async def set_properties(self, props: Optional[List] = None) -> Self:
        """
        Set properties for this object using PROPPATCH.

        Args:
            props: List of properties to set
        """
        if props is None:
            props = []

        from .elements import dav

        prop = dav.Prop() + props
        set_element = dav.Set() + prop
        root = dav.PropertyUpdate() + [set_element]

        body = etree.tostring(root.xmlelement(), encoding="utf-8", xml_declaration=True)
        ret = await self.client.proppatch(str(self.url), body)
        return self

    async def save(self) -> Self:
        """Save any changes to this object to the server"""
        # For base DAVObject, save typically uses set_properties
        # Subclasses override this with specific save logic
        if hasattr(self, "data") and self.data:
            # This would be for CalendarObjectResource subclasses
            raise NotImplementedError(
                "save() for calendar objects should be implemented in subclass"
            )
        return self

    async def delete(self) -> None:
        """Delete this object from the server"""
        await self.client.delete(str(self.url))

    def get_display_name(self) -> Optional[str]:
        """Get the display name for this object (synchronous)"""
        return self.name

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.url})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(url={self.url!r}, client={self.client!r})"
