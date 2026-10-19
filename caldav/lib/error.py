#!/usr/bin/env python
import logging
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from caldav import __version__

debug_dump_communication = False
try:
    import os

    ## Environmental variables prepended with "PYTHON_CALDAV" are used for debug purposes,
    ## environmental variables prepended with "CALDAV_" are for connection parameters
    debug_dump_communication = os.environ.get("PYTHON_CALDAV_COMMDUMP", False)
    if debug_dump_communication:
        logging.getLogger("caldav").warning(
            "PYTHON_CALDAV_COMMDUMP is set: request/response bodies and headers "
            "(including credentials and calendar PII) will be written to uniquely-named "
            "files under /tmp.  These files accumulate indefinitely — remove them when done."
        )
    ## one of DEBUG_PDB, DEBUG, DEVELOPMENT, PRODUCTION
    debugmode = os.environ["PYTHON_CALDAV_DEBUGMODE"]
except KeyError:
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


def _dump_communication(method: str, url: str, combined_headers: dict, body, response) -> None:
    """Write a request/response exchange to a uniquely-named temp file.

    Called when ``debug_dump_communication`` is truthy.  Works for both the
    sync and async code paths because it only depends on the attributes that
    ``BaseDAVResponse`` exposes: ``.status``, ``.reason``, ``.headers``,
    ``.tree``, and ``._raw``.
    """
    import datetime
    from tempfile import NamedTemporaryFile

    from lxml import etree

    from caldav.lib.python_utilities import to_wire

    with NamedTemporaryFile(prefix="caldavcomm", delete=False) as commlog:
        commlog.write(b"=" * 80 + b"\n")
        commlog.write(f"{datetime.datetime.now():%FT%H:%M:%S}".encode())
        commlog.write(b"\n====>\n")
        commlog.write(f"{method} {url}\n".encode())
        commlog.write(b"\n".join(to_wire(f"{k}: {v}") for k, v in combined_headers.items()))
        commlog.write(b"\n\n")
        commlog.write(to_wire(body) or b"")
        commlog.write(b"\n<====\n")
        commlog.write(f"{response.status} {response.reason}\n".encode())
        commlog.write(b"\n".join(to_wire(f"{k}: {v}") for k, v in response.headers.items()))
        commlog.write(b"\n\n")
        if response.tree is not None:
            commlog.write(to_wire(etree.tostring(response.tree, pretty_print=True)))
        else:
            commlog.write(to_wire(response._raw) or b"")
        commlog.write(b"\n")


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
    """Base class for the errors raised on a failed request.

    ``preconditions`` holds the Clark-notation tags of any precondition
    elements in a ``DAV:error`` response body (RFC 4918 section 16), and
    ``body`` the raw response body (or None).  A server may explain any
    failure that way, whatever the status: e.g. ``["{DAV:}valid-sync-token"]``
    for an expired sync token (RFC 6578 section 3.2), or
    ``["{urn:ietf:params:xml:ns:caldav}no-uid-conflict"]`` for a create whose
    UID is already taken (RFC 4791 section 5.3.2.1).
    """

    url: str | None = None
    reason: str = "no reason"

    def __init__(
        self,
        url: str | None = None,
        reason: str | None = None,
        preconditions: list[str] | None = None,
        body: bytes | str | None = None,
    ) -> None:
        if url:
            self.url = url
        if reason:
            self.reason = reason
        self.preconditions = list(preconditions) if preconditions else []
        self.body = body

    def __str__(self) -> str:
        return "%s at '%s', reason %s" % (
            self.__class__.__name__,
            self.url,
            self.reason,
        )


def parse_preconditions(body: object) -> list[str]:
    """Return the precondition/postcondition element tags of a DAV:error body.

    RFC 4918 section 16 lets a server explain a 403/409 with a body like
    ``<D:error><D:valid-sync-token/></D:error>``; this returns the Clark-notation
    tags of the DAV:error children (e.g. ``["{DAV:}valid-sync-token"]``).
    Anything that is not a well-formed DAV:error document - an empty body, HTML,
    plain text, some other XML root - yields an empty list rather than an error.
    """
    if isinstance(body, str):
        body = body.encode("utf-8")
    if not isinstance(body, bytes) or not body.strip():
        return []
    from lxml import etree

    try:
        root = etree.fromstring(
            body,
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
    except Exception:
        return []
    if root.tag != "{DAV:}error":
        return []
    return [child.tag for child in root if isinstance(child.tag, str)]


class AuthorizationError(DAVError):
    """
    The client encountered an HTTP 401 or 403 error and is passing it on
    to the user. The url property will contain the url in question,
    the reason property will contain the excuse the server sent.

    A 403 with an empty ``preconditions`` list is most likely a genuine
    permission problem.
    """


def error_from_response(
    cls: type[DAVError], response: object, message: str | None = None
) -> DAVError:
    """Build a ``cls`` error for a failed ``DAVResponse``, keeping its body
    and the precondition elements in it (issue #756).  ``message`` defaults
    to ``errmsg(response)``."""
    body = getattr(response, "_raw", None) or None
    if not isinstance(body, (bytes, str)):
        body = None
    return cls(
        errmsg(response) if message is None else message,
        preconditions=parse_preconditions(body),
        body=body,
    )


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


## RFC 4791 section 5.3.2.1 and RFC 6638 section 3.2.4.1
UID_CONFLICT_PRECONDITIONS = frozenset(
    {
        "{urn:ietf:params:xml:ns:caldav}no-uid-conflict",
        "{urn:ietf:params:xml:ns:caldav}unique-scheduling-object-resource",
    }
)


class UidConflictError(PutError):
    """The server refused a PUT because another object in the calendar
    already holds its UID: ``CALDAV:no-uid-conflict`` (RFC 4791 section
    5.3.2.1) or ``CALDAV:unique-scheduling-object-resource`` (RFC 6638
    section 3.2.4.1).  Radicale answers 409, Xandikos and Stalwart 412,
    Cyrus 403.  https://github.com/python-caldav/caldav/issues/756

    Where earlier versions raised another error for the same answer, a
    subclass that is also that error is raised instead
    (``UID_CONFLICT_ERRORS``), so existing handlers keep catching it.
    """


class DeleteError(DAVError):
    pass


class NotFoundError(DAVError):
    pass


class ConsistencyError(DAVError):
    pass


class ResponseError(DAVError):
    pass


class ScheduleTagMismatchError(DAVError):
    pass


class ETagMismatchError(DAVError):
    pass


class UidConflictScheduleTagMismatchError(UidConflictError, ScheduleTagMismatchError):
    """A 412 UID conflict on a save sending If-Schedule-Tag-Match."""


class UidConflictETagMismatchError(UidConflictError, ETagMismatchError):
    """A 412 UID conflict on a save sending If-Match."""


class UidConflictAuthorizationError(UidConflictError, AuthorizationError):
    """A 403 UID conflict (Cyrus)."""


class UidConflictConsistencyError(UidConflictError, ConsistencyError):
    """A UID conflict on ``save(no_overwrite=True)`` or
    ``save(no_create=True)``.  Their UID search, which may now be left to
    the server, raised ConsistencyError for this."""


class UidConflictConsistencyAuthorizationError(UidConflictConsistencyError, AuthorizationError):
    """A 403 UID conflict (Cyrus) where a ConsistencyError is expected."""


## The UidConflictError to raise in place of what earlier versions raised
UID_CONFLICT_ERRORS: dict[type[DAVError], type[UidConflictError]] = {
    AuthorizationError: UidConflictAuthorizationError,
    ETagMismatchError: UidConflictETagMismatchError,
    ScheduleTagMismatchError: UidConflictScheduleTagMismatchError,
}
## The same, where a ConsistencyError is expected too
UID_CONFLICT_CONSISTENCY_ERRORS: dict[type[DAVError], type[UidConflictConsistencyError]] = {
    AuthorizationError: UidConflictConsistencyAuthorizationError,
}


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


def parse_retry_after(retry_after_header: str) -> float | None:
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
    retry_after_seconds: float | None,
    default_sleep: int | None,
    max_sleep: int | None,
) -> float | None:
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
    effective: float | None = (
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
    retry_after_header: str | None,
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


exception_by_method: dict[str, type[DAVError]] = defaultdict(lambda: DAVError)
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
