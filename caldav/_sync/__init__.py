"""
Sync CalDAV client implementation - thin wrappers around async implementation.

This module provides synchronous API by wrapping the async implementation
using anyio.from_thread.run().
"""
from .davclient import DAVClient

__all__ = ["DAVClient"]
