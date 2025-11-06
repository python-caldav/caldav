"""
Shared iCalendar business logic for both sync and async calendar objects.

This module contains pure functions and stateless operations on iCalendar data
that are used by both synchronous and asynchronous calendar object classes.
"""
import logging
import uuid
from typing import Optional
from urllib.parse import quote

log = logging.getLogger("caldav")


class ICalLogic:
    """
    Shared business logic for calendar objects.

    Contains static methods for operations on iCalendar data that don't
    require HTTP communication and are identical for both sync and async.
    """

    @staticmethod
    def extract_uid_from_data(data: str) -> Optional[str]:
        """
        Extract UID from iCalendar data using simple text parsing.

        This is a lightweight method that doesn't require parsing the full
        iCalendar structure. It's used during object initialization.

        Args:
            data: iCalendar data as string

        Returns:
            UID if found, None otherwise
        """
        try:
            for line in data.split("\n"):
                stripped = line.strip()
                if stripped.startswith("UID:"):
                    uid = stripped.split(":", 1)[1].strip()
                    log.debug(
                        f"[UID EXTRACT DEBUG] Extracted UID: '{uid}' from line: '{line[:80]}'"
                    )
                    return uid
            log.warning(
                f"[UID EXTRACT DEBUG] No UID found in data. First 500 chars: {data[:500]}"
            )
        except Exception as e:
            log.warning(f"[UID EXTRACT DEBUG] Exception extracting UID: {e}")
        return None

    @staticmethod
    def generate_uid() -> str:
        """
        Generate a unique identifier for a calendar object.

        Returns:
            A UUID string suitable for use as a calendar object UID
        """
        return str(uuid.uuid4())

    @staticmethod
    def generate_object_url(
        parent_url, uid: Optional[str] = None, quote_special_chars: bool = True
    ) -> str:
        """
        Generate a URL for a calendar object based on its parent and UID.

        Args:
            parent_url: URL object of the parent calendar
            uid: UID of the calendar object (will generate if not provided)
            quote_special_chars: If True, properly quote special characters in UID
                                 (particularly slashes which need double-quoting per issue #143)

        Returns:
            URL string for the calendar object
        """
        if uid is None:
            uid = ICalLogic.generate_uid()

        if quote_special_chars:
            # See https://github.com/python-caldav/caldav/issues/143
            # Slashes need to be replaced with %2F first, then the whole UID quoted
            uid_safe = quote(uid.replace("/", "%2F"))
        else:
            uid_safe = uid

        return parent_url.join(f"{uid_safe}.ics")
