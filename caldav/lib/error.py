#!/usr/bin/env python
import logging
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

from caldav import __version__

debug_dump_communication = False
try:
    import os

    ## Environmental variables prepended with "PYTHON_CALDAV" are used for debug purposes,
    ## environmental variables prepended with "CALDAV_" are for connection parameters
    debug_dump_communication = os.environ.get("PYTHON_CALDAV_COMMDUMP", False)
    ## one of DEBUG_PDB, DEBUG, DEVELOPMENT, PRODUCTION
    debugmode = os.environ["PYTHON_CALDAV_DEBUGMODE"]
except:
    if "dev" in __version__ or __version__ == "(unknown)":
        debugmode = "DEVELOPMENT"
    else:
        debugmode = "PRODUCTION"

log = logging.getLogger("caldav")
if debugmode.startswith("DEBUG"):
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.WARNING)


def errmsg(r) -> str:
    """Utility for formatting a an error response to an error string"""
    return "%s %s\n\n%s" % (r.status, r.reason, r.raw)


def weirdness(*reasons):
    from caldav.lib.debug import xmlstring

    reason = " : ".join([xmlstring(x) for x in reasons])
    log.warning(f"Deviation from expectations found: {reason}")
    if debugmode == "DEBUG_PDB":
        log.error(f"Dropping into debugger due to {reason}")
        import pdb

        pdb.set_trace()


def assert_(condition: object) -> None:
    try:
        assert condition
    except AssertionError:
        if debugmode == "PRODUCTION":
            log.error("Deviation from expectations found.  %s" % ERR_FRAGMENT, exc_info=True)
        elif debugmode == "DEBUG_PDB":
            log.error("Deviation from expectations found.  Dropping into debugger")
            import pdb

            pdb.set_trace()
        else:
            raise


ERR_FRAGMENT: str = "Please consider raising an issue at https://github.com/python-caldav/caldav/issues or reach out to t-caldav@tobixen.no, include this error and the traceback (if any) and tell what server you are using"


class DAVError(Exception):
    url: str | None = None
    reason: str = "no reason"

    def __init__(self, url: str | None = None, reason: str | None = None) -> None:
        if url:
            self.url = url
        if reason:
            self.reason = reason

    def __str__(self) -> str:
        return "%s at '%s', reason %s" % (
            self.__class__.__name__,
            self.url,
            self.reason,
        )


class AuthorizationError(DAVError):
    """
    The client encountered an HTTP 403 error and is passing it on
    to the user. The url property will contain the url in question,
    the reason property will contain the excuse the server sent.
    """

    pass


class PropsetError(DAVError):
    pass


class ProppatchError(DAVError):
    pass


class PropfindError(DAVError):
    pass


class ReportError(DAVError):
    pass


class MkcolError(DAVError):
    pass


class MkcalendarError(DAVError):
    pass


class PutError(DAVError):
    pass


class DeleteError(DAVError):
    pass


class NotFoundError(DAVError):
    pass


class ConsistencyError(DAVError):
    pass


class ResponseError(DAVError):
    pass


class RateLimitError(DAVError):
    """Raised when the server responds with 429 Too Many Requests or
    503 Service Unavailable with a Retry-After header."""

    def __init__(
        self,
        url: str | None = None,
        reason: str | None = None,
        retry_after: str | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(url=url, reason=reason)
        self.retry_after = retry_after
        self.retry_after_seconds = retry_after_seconds


def parse_retry_after(retry_after_header: str) -> Optional[float]:
    """Parse a Retry-After header value into seconds from now.

    Handles both the integer-seconds form (RFC 7231 §7.1.3) and the HTTP-date
    form.  Returns None if the value cannot be parsed.
    """
    try:
        return float(int(retry_after_header))
    except ValueError:
        pass
    try:
        retry_date = parsedate_to_datetime(retry_after_header)
        now = datetime.now(timezone.utc)
        return max(0.0, (retry_date - now).total_seconds())
    except (ValueError, TypeError):
        return None


def compute_sleep_seconds(
    retry_after_seconds: Optional[float],
    default_sleep: Optional[int],
    max_sleep: Optional[int],
) -> Optional[float]:
    """Compute the effective sleep duration for rate-limit handling.

    Returns None when there is no usable duration (meaning the caller should
    re-raise the RateLimitError rather than sleeping).

    Args:
        retry_after_seconds: Parsed seconds from server Retry-After header,
            or None if the server did not provide one.
        default_sleep: Fallback duration when retry_after_seconds is None.
            None means no fallback; re-raise.
        max_sleep: Hard cap on sleep duration.  None means no cap; 0 means
            never sleep.
    """
    effective: Optional[float] = (
        retry_after_seconds
        if retry_after_seconds is not None
        else (float(default_sleep) if default_sleep is not None else None)
    )
    if effective is None or effective <= 0:
        return None
    if max_sleep is not None:
        effective = min(effective, float(max_sleep))
    if effective <= 0:
        return None
    return effective


def raise_if_rate_limited(
    status_code: int,
    url: str,
    retry_after_header: Optional[str],
) -> None:
    """Raise RateLimitError when the response indicates rate limiting.

    Raises for:
    - Any 429 response (regardless of Retry-After presence)
    - 503 responses that include a Retry-After header

    Args:
        status_code: HTTP status code from the response.
        url: Request URL (included in exception for context).
        retry_after_header: Raw Retry-After header value, or None.
    """
    if status_code not in (429, 503):
        return
    if status_code != 429 and retry_after_header is None:
        return
    retry_seconds = parse_retry_after(retry_after_header) if retry_after_header else None
    raise RateLimitError(
        url=url,
        reason=f"Rate limited or service unavailable. Retry after: {retry_after_header}",
        retry_after=retry_after_header,
        retry_after_seconds=retry_seconds,
    )


exception_by_method: dict[str, DAVError] = defaultdict(lambda: DAVError)
for method in (
    "delete",
    "put",
    "mkcalendar",
    "mkcol",
    "report",
    "propset",
    "propfind",
    "proppatch",
):
    exception_by_method[method] = locals()[method[0].upper() + method[1:] + "Error"]
