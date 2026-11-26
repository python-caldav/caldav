"""How a DAV client reacts to rate-limit (429/503) responses.

Shared by the sync and async clients, which differ only in how they sleep
(``time.sleep`` vs ``asyncio.sleep``) before retrying.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from caldav.lib import error

if TYPE_CHECKING:
    from caldav.compatibility_hints import FeatureSet


@dataclass
class RateLimitPolicy:
    """Rate-limit settings of a client and the retry decision based on them."""

    handle: bool = False
    default_sleep: int | None = None
    max_sleep: int | None = None

    @classmethod
    def from_settings(
        cls,
        features: FeatureSet,
        handle: bool | None,
        default_sleep: int | None,
        max_sleep: int | None,
    ) -> RateLimitPolicy:
        """Resolve the constructor arguments into a policy.

        When ``handle`` is None it is auto-detected from the ``rate-limit``
        feature; an enabled feature may also supply default and max sleep
        durations (explicit constructor arguments are not overridden because
        the feature values only fill in the auto-detected branch).
        """
        rate_limit = features.is_supported("rate-limit", dict)
        if handle is None:
            if rate_limit and rate_limit.get("enable"):
                handle = True
                if "default_sleep" in rate_limit:
                    default_sleep = rate_limit["default_sleep"]
                if "max_sleep" in rate_limit:
                    max_sleep = rate_limit["max_sleep"]
            else:
                handle = False
        return cls(handle, default_sleep, max_sleep)

    def sleep_seconds(self, exc: error.RateLimitError, time_slept: float) -> float:
        """Decide how long to sleep before retrying a rate-limited request.

        Returns the sleep duration in seconds.  Re-raises ``exc`` when no retry
        should happen (rate-limit handling disabled, no usable duration, or the
        accumulated sleep already exceeds ``max_sleep``).  The caller is
        responsible for actually sleeping and retrying with
        ``time_slept + <returned value>``.
        """
        if not self.handle:
            raise exc
        sleep_seconds = error.compute_sleep_seconds(
            exc.retry_after_seconds,
            self.default_sleep,
            self.max_sleep,
        )
        if sleep_seconds is None or (self.max_sleep is not None and time_slept > self.max_sleep):
            raise exc
        if time_slept:
            sleep_seconds += time_slept / 2
        return sleep_seconds
