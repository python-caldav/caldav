"""
Shared core functionality for DAV objects.

This module contains the common state management and non-HTTP operations
that are shared between synchronous and asynchronous DAV objects.
"""
import logging
from typing import Any
from typing import Optional
from typing import Union
from urllib.parse import ParseResult
from urllib.parse import SplitResult

from .url import URL

log = logging.getLogger("caldav")


class DAVObjectCore:
    """
    Core functionality shared between sync and async DAV objects.

    This class contains all the state management and non-HTTP operations
    that are identical for both synchronous and asynchronous implementations.
    It's designed to be used via composition or inheritance.
    """

    def __init__(
        self,
        client: Optional[Any] = None,
        url: Union[str, ParseResult, SplitResult, URL, None] = None,
        parent: Optional[Any] = None,
        name: Optional[str] = None,
        id: Optional[str] = None,
        props: Optional[Any] = None,
        **extra,
    ) -> None:
        """
        Initialize core DAV object state.

        Args:
            client: A DAVClient or AsyncDAVClient instance
            url: The url for this object (may be full or relative)
            parent: The parent object - used when creating objects
            name: A displayname
            props: a dict with known properties for this object
            id: The resource id (UID for an Event)
            **extra: Additional initialization options
        """
        # Inherit client from parent if not provided
        if client is None and parent is not None:
            client = parent.client

        self.client = client
        self.parent = parent
        self.name = name
        self.id = id
        self.props = props or {}
        self.extra_init_options = extra

        # Handle URL initialization
        self._initialize_url(client, url)

    def _initialize_url(
        self,
        client: Optional[Any],
        url: Union[str, ParseResult, SplitResult, URL, None],
    ) -> None:
        """
        Initialize the URL for this object.

        This handles various URL formats and relative/absolute URLs.
        """
        if client and url:
            # URL may be relative to the caldav root
            self.url = client.url.join(url)
        elif url is None:
            self.url = None
        else:
            self.url = URL.objectify(url)

    def get_canonical_url(self) -> str:
        """
        Get the canonical URL for this object.

        Returns:
            Canonical URL as string
        """
        if self.url is None:
            raise ValueError("Unexpected value None for self.url")
        return str(self.url.canonical())

    def get_display_name(self) -> Optional[str]:
        """
        Get the display name for this object (synchronous access).

        Returns:
            Display name if set, None otherwise
        """
        return self.name

    def __str__(self) -> str:
        """String representation showing class name and URL"""
        return f"{self.__class__.__name__}({self.url})"

    def __repr__(self) -> str:
        """Detailed representation for debugging"""
        return f"{self.__class__.__name__}(url={self.url!r}, client={self.client!r})"
