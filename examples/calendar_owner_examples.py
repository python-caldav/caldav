"""
Examples for finding the owner of a calendar and looking up their address.

Use case: when a calendar is shared with you, you may want to know who owns
it and how to reach them.

See also: https://github.com/python-caldav/caldav/issues/544
"""

import sys

sys.path.insert(0, "..")
sys.path.insert(0, ".")

import caldav
from caldav import get_davclient
from caldav.elements import dav


def find_calendar_owner(calendar):
    """
    Return the owner URL of a calendar.

    Uses the DAV:owner property (WebDAV RFC 4918, section 14.17).  The owner
    is returned as a URL string pointing to the owner's principal resource.
    Returns None if the server does not expose the property.

    Args:
        calendar: a :class:`caldav.Calendar` object

    Returns:
        str | None: the owner's principal URL, or None
    """
    return calendar.get_property(dav.Owner())


def find_calendar_owner_address(calendar):
    """
    Return the calendar-user-address (typically an e-mail URI like
    ``mailto:user@example.com``) of a calendar's owner.

    This is a two-step operation:

    1. Fetch the DAV:owner property of the calendar to get the owner's
       principal URL.
    2. Construct a :class:`caldav.Principal` from that URL and call
       :meth:`~caldav.Principal.get_vcal_address` to retrieve the
       ``calendar-user-address-set`` property (RFC 6638 section 2.4.1).

    Requires the server to support both the DAV:owner property and the
    ``CALDAV:calendar-user-address-set`` principal property.  Returns None
    when either piece of information is unavailable.

    Args:
        calendar: a :class:`caldav.Calendar` object

    Returns:
        icalendar.vCalAddress | None: the owner's calendar address, or None
    """
    owner_url = find_calendar_owner(calendar)
    if owner_url is None:
        return None

    owner_principal = caldav.Principal(client=calendar.client, url=owner_url)
    try:
        return owner_principal.get_vcal_address()
    except Exception:
        return None


def run_examples():
    """
    Run the calendar-owner examples against a live server.

    Connects via :func:`caldav.get_davclient` (reads credentials from the
    environment or config file), creates a temporary calendar, and
    demonstrates how to retrieve its owner URL and calendar-user address.
    """
    with get_davclient() as client:
        principal = client.principal()
        calendar = principal.make_calendar(name="Owner example calendar")
        try:
            owner_url = find_calendar_owner(calendar)
            if owner_url is not None:
                print(f"Calendar owner URL: {owner_url}")

                owner_address = find_calendar_owner_address(calendar)
                if owner_address is not None:
                    print(f"Calendar owner address: {owner_address}")
                else:
                    print(
                        "Calendar owner address: not available (server may not support calendar-user-address-set)"
                    )
            else:
                print("DAV:owner property not exposed by this server")
        finally:
            calendar.delete()


if __name__ == "__main__":
    run_examples()
