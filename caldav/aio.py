#!/usr/bin/env python
"""
Async API for caldav library.

This module provides a convenient entry point for async CalDAV operations.

Example:
    from caldav import aio

    async with await aio.get_davclient(url="...", username="...", password="...") as client:
        principal = await client.get_principal()
        calendars = await principal.calendars()
"""

# Re-export async components for convenience
from caldav.async_davclient import (
    AsyncDAVClient,
    AsyncDAVResponse,
    get_davclient,
)

__all__ = [
    "AsyncDAVClient",
    "AsyncDAVResponse",
    "get_davclient",
]
