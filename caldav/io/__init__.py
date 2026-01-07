"""
I/O layer for CalDAV protocol.

This module provides sync and async implementations for executing
DAVRequest objects and returning DAVResponse objects.

The I/O layer is intentionally thin - it only handles HTTP transport.
All protocol logic (XML building/parsing) is in caldav.protocol.

Example (sync):
    from caldav.protocol import CalDAVProtocol
    from caldav.io import SyncIO

    protocol = CalDAVProtocol(base_url="https://cal.example.com")
    with SyncIO() as io:
        request = protocol.propfind_request("/calendars/", ["displayname"])
        response = io.execute(request)
        results = protocol.parse_propfind(response)

Example (async):
    from caldav.protocol import CalDAVProtocol
    from caldav.io import AsyncIO

    protocol = CalDAVProtocol(base_url="https://cal.example.com")
    async with AsyncIO() as io:
        request = protocol.propfind_request("/calendars/", ["displayname"])
        response = await io.execute(request)
        results = protocol.parse_propfind(response)
"""

from .base import AsyncIOProtocol, SyncIOProtocol
from .sync import SyncIO
from .async_ import AsyncIO

__all__ = [
    # Protocols
    "SyncIOProtocol",
    "AsyncIOProtocol",
    # Implementations
    "SyncIO",
    "AsyncIO",
]
