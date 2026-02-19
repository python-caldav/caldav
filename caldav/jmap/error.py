"""
JMAP error hierarchy.

Extends the existing caldav.lib.error.DAVError base so that JMAP errors
integrate naturally with existing exception handling in user code.

RFC 8620 §3.6.2 defines the standard method-level error types.
"""

from caldav.lib.error import AuthorizationError, DAVError


class JMAPError(DAVError):
    """Base class for all JMAP errors.

    Adds ``error_type`` to carry the RFC 8620 error type string
    (e.g. ``"unknownMethod"``, ``"invalidArguments"``).
    """

    error_type: str = "serverError"

    def __init__(
        self,
        url: str | None = None,
        reason: str | None = None,
        error_type: str | None = None,
    ) -> None:
        super().__init__(url=url, reason=reason)
        if error_type is not None:
            self.error_type = error_type

    def __str__(self) -> str:
        return "%s (type=%s) at '%s', reason: %s" % (
            self.__class__.__name__,
            self.error_type,
            self.url,
            self.reason,
        )


class JMAPCapabilityError(JMAPError):
    """Server does not advertise the required JMAP capability.

    Raised when the Session object returned by the server does not include
    ``urn:ietf:params:jmap:calendars`` in the account capabilities.
    """

    error_type = "capabilityNotSupported"
    reason = "Server does not support urn:ietf:params:jmap:calendars"


class JMAPAuthError(AuthorizationError, JMAPError):
    """HTTP 401 or 403 received from JMAP server.

    Unlike CalDAV, JMAP does not use a 401-challenge-retry dance.
    A 401/403 on the session GET or any API call is a hard failure.
    """

    error_type = "forbidden"
    reason = "Authentication failed"


class JMAPMethodError(JMAPError):
    """A JMAP method call returned an error response.

    RFC 8620 §3.6.2 error types that may be set as ``error_type``:

    - ``serverError``             — unexpected server-side error
    - ``unknownMethod``           — method name not recognised
    - ``invalidArguments``        — bad argument types or values
    - ``invalidResultReference``  — bad ``#result`` reference
    - ``forbidden``               — not allowed to perform this call
    - ``accountNotFound``         — ``accountId`` does not exist
    - ``accountNotSupportedByMethod`` — account lacks needed capability
    - ``accountReadOnly``         — account is read-only
    - ``requestTooLarge``         — request exceeds server limits
    - ``stateMismatch``           — ``ifInState`` check failed
    - ``serverPartialFail``       — partial failure; some calls succeeded
    - ``notFound``                — requested object does not exist
    - ``notDraft``                — object is not in draft state
    """

    error_type = "serverError"
