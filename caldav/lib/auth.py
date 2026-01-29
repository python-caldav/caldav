"""
Authentication utilities for CalDAV clients.

This module contains shared authentication logic used by both
DAVClient (sync) and AsyncDAVClient (async).
"""

from __future__ import annotations


def extract_auth_types(header: str) -> set[str]:
    """
    Extract authentication types from WWW-Authenticate header.

    Parses the WWW-Authenticate header value and extracts the
    authentication scheme names (e.g., "basic", "digest", "bearer").

    Args:
        header: WWW-Authenticate header value from server response.

    Returns:
        Set of lowercase auth type strings.

    Example:
        >>> extract_auth_types('Basic realm="test", Digest realm="test"')
        {'basic', 'digest'}

    Reference:
        https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/WWW-Authenticate#syntax
    """
    return {h.split()[0] for h in header.lower().split(",")}


def select_auth_type(
    auth_types: set[str] | list[str],
    has_username: bool,
    has_password: bool,
    prefer_digest: bool = True,
) -> str | None:
    """
    Select the best authentication type from available options.

    Args:
        auth_types: Available authentication types from server.
        has_username: Whether a username is configured.
        has_password: Whether a password is configured.
        prefer_digest: Whether to prefer Digest over Basic auth.

    Returns:
        Selected auth type string, or None if no suitable type found.

    Selection logic:
        - If username is set: prefer Digest (more secure) or Basic
        - If only password is set: use Bearer token auth
        - Otherwise: return None
    """
    auth_types_set = set(auth_types) if not isinstance(auth_types, set) else auth_types

    if has_username:
        if prefer_digest and "digest" in auth_types_set:
            return "digest"
        if "basic" in auth_types_set:
            return "basic"
    elif has_password:
        # Password without username suggests bearer token
        if "bearer" in auth_types_set:
            return "bearer"

    return None
