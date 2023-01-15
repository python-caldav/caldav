#!/usr/bin/env python
import re
import uuid
from datetime import datetime
from datetime import timedelta
from unittest import TestCase

import icalendar
import pytest
import pytz
import vobject
from caldav.lib import vcal
from caldav.lib.python_utilities import to_normal_str
from caldav.lib.python_utilities import to_wire
from caldav.lib.vcal import create_ical
from caldav.lib.vcal import fix

# from datetime import timezone
# utc = timezone.utc
utc = pytz.utc

# example from http://www.rfc-editor.org/rfc/rfc5545.txt
ev = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:19970901T130000Z-123403@example.com
DTSTAMP:19970901T130000Z
DTSTART;VALUE=DATE:19971102
SUMMARY:Our Blissful Anniversary
TRANSP:TRANSPARENT
CLASS:CONFIDENTIAL
CATEGORIES:ANNIVERSARY,PERSONAL,SPECIAL OCCASION
RRULE:FREQ=YEARLY
END:VEVENT
END:VCALENDAR"""


class TestVcal(TestCase):
    def assertSameICal(self, ical1, ical2, ignore_uid=False):
        """helper method"""

        def normalize(s, ignore_uid):
            s = to_wire(s).replace(b"\r\n", b"\n").strip().split(b"\n")
            s.sort()
            if ignore_uid:
                s = [x for x in s if not x.startswith(b"UID:")]
            return b"\n".join(s)

        self.assertEqual(normalize(ical1, ignore_uid), normalize(ical2, ignore_uid))
        return ical2

    def verifyICal(self, ical):
        """
        Does a best effort on verifying that the ical is correct, by
        pushing it through the vobject and icalendar library
        """
        vobj = vobject.readOne(to_normal_str(ical))
        icalobj = icalendar.Calendar.from_ical(ical)
        self.assertSameICal(icalobj.to_ical(), ical)
        self.assertSameICal(vobj.serialize(), ical)
        return icalobj.to_ical()

    ## TODO: create a test_fix, should be fairly simple - for each
    ## "fix" that's done in the code, make up some broken ical data
    ## that demonstrates the brokenness we're dealing with (preferably
    ## real-world examples). Then ...
    # for bical in broken_ical:
    #    verifyICal(vcal.fix(bical))

    def test_create_ical(self):
        def create_and_validate(**args):
            return self.verifyICal(create_ical(**args))

        ## First, a fully valid ical_fragment should go through as is
        self.assertSameICal(create_and_validate(ical_fragment=ev), ev)

        ## One may add stuff to a fully valid ical_fragment
        self.assertSameICal(
            create_and_validate(ical_fragment=ev, priority=3), ev + "\nPRIORITY:3\n"
        )

        ## binary string or unicode string ... shouldn't matter
        self.assertSameICal(
            create_and_validate(ical_fragment=ev.encode("utf-8"), priority=3),
            ev + "\nPRIORITY:3\n",
        )

        ## The returned ical_fragment should always contain BEGIN:VCALENDAR and END:VCALENDAR
        ical_fragment = ev.replace("BEGIN:VCALENDAR", "").replace("END:VCALENDAR", "")
        self.assertSameICal(create_and_validate(ical_fragment=ical_fragment), ev)

        ## Create something with a dtstart and verify that we get it back in the ical
        some_ical0 = create_and_validate(
            summary="gobledok",
            dtstart=datetime(2032, 10, 10, 10, 10, 10, tzinfo=utc),
            duration=timedelta(hours=5),
        )
        some_ical1 = create_and_validate(
            summary=b"gobledok",
            dtstart=datetime(2032, 10, 10, 10, 10, 10, tzinfo=utc),
            duration=timedelta(hours=5),
        )
        assert re.search(b"DTSTART(;VALUE=DATE-TIME)?:20321010T101010Z", some_ical0)
        self.assertSameICal(some_ical0, some_ical1, ignore_uid=True)

        ## Verify that ical_fragment works as intended
        some_ical = create_and_validate(
            summary="gobledok",
            ical_fragment="PRIORITY:3",
            dtstart=datetime(2032, 10, 10, 10, 10, 10, tzinfo=utc),
            duration=timedelta(hours=5),
        )
        assert re.search(b"DTSTART(;VALUE=DATE-TIME)?:20321010T101010Z", some_ical)
        assert some_ical.count(b"PRIORITY") == 1

        some_ical = create_and_validate(
            summary="gobledok",
            ical_fragment=b"PRIORITY:3",
            dtstart=datetime(2032, 10, 10, 10, 10, 10, tzinfo=utc),
            duration=timedelta(hours=5),
        )
        assert re.search(b"DTSTART(;VALUE=DATE-TIME)?:20321010T101010Z", some_ical)

        some_ical = create_and_validate(
            summary=b"gobledok",
            ical_fragment="",
            dtstart=datetime(2032, 10, 10, 10, 10, 10, tzinfo=utc),
            duration=timedelta(hours=5),
        )
        assert re.search(b"DTSTART(;VALUE=DATE-TIME)?:20321010T101010Z", some_ical)

    def test_vcal_fixups(self):
        """
        There is an obscure function lib.vcal that attempts to fix up
        known ical standard breaches from various calendar servers.
        """
        broken_ical = [
            ## This first one contains duplicated DTSTAMP in the event data
            """BEGIN:VCALENDAR
X-EXPANDED:True
X-MASTER-DTSTART:20200517T060000Z
X-MASTER-RRULE:FREQ=YEARLY
BEGIN:VEVENT
DTSTAMP:20210205T101751Z
UID:20200516T060000Z-123401@example.com
DTSTAMP:20200516T060000Z
SUMMARY:Do the needful
DTSTART:20210517T060000Z
DTEND:20210517T230000Z
RECURRENCE-ID:20210517T060000Z
END:VEVENT
BEGIN:VEVENT
DTSTAMP:20210205T101751Z
UID:20200516T060000Z-123401@example.com
DTSTAMP:20200516T060000Z
SUMMARY:Do the needful
DTSTART:20220517T060000Z
DTEND:20220517T230000Z
RECURRENCE-ID:20220517T060000Z
END:VEVENT
BEGIN:VEVENT
DTSTAMP:20210205T101751Z
UID:20200516T060000Z-123401@example.com
DTSTAMP:20200516T060000Z
SUMMARY:Do the needful
DTSTART:20230517T060000Z
DTEND:20230517T230000Z
RECURRENCE-ID:20230517T060000Z
END:VEVENT
END:VCALENDAR""",  ## Next one contains DTEND and DURATION.
            """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTAMP:20210205T101751Z
UID:20200516T060000Z-123401@example.com
SUMMARY:Do the needful
DTSTART:20210517T060000Z
DURATION:PT15M
DTEND:20210517T230000Z
END:VEVENT
END:VCALENDAR""",  ## Same, but real example:
            """BEGIN:VCALENDAR
PRODID:Zimbra-Calendar-Provider
VERSION:2.0
BEGIN:VTIMEZONE
TZID:Europe/Brussels
BEGIN:STANDARD
DTSTART:16010101T030000
TZOFFSETTO:+0100
TZOFFSETFROM:+0200
RRULE:FREQ=YEARLY;WKST=MO;INTERVAL=1;BYMONTH=10;BYDAY=-1SU
TZNAME:CET
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:16010101T020000
TZOFFSETTO:+0200
TZOFFSETFROM:+0100
RRULE:FREQ=YEARLY;WKST=MO;INTERVAL=1;BYMONTH=3;BYDAY=-1SU
TZNAME:CEST
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VEVENT
UID:e42481ad-aabf-43c1-bbc0-04754373678d
RRULE:FREQ=WEEKLY;UNTIL=20221222T225959Z;BYDAY=WE
SUMMARY:Competence Lunch
DESCRIPTION: *removed*
ATTENDEE;CN=Tobias Brox;PARTSTAT=TENTATIVE:mailto:tobias@redpill-linpro.com
PRIORITY:9
ORGANIZER;CN=Someone:mailto:noreply@redpill-linpro.com
DTSTART;TZID="Europe/Brussels":20220817T110000
DTEND;TZID="Europe/Brussels":20220817T113000
DURATION:PT30M
STATUS:CONFIRMED
CLASS:PUBLIC
TRANSP:OPAQUE
LAST-MODIFIED:20220916T120601Z
DTSTAMP:20220906T125002Z
SEQUENCE:1
EXDATE;TZID="Europe/Brussels":20221005T110000
EXDATE;TZID="Europe/Brussels":20221116T110000
BEGIN:VALARM
ACTION:DISPLAY
TRIGGER;RELATED=START:-PT15M
DESCRIPTION:Reminder
END:VALARM
END:VEVENT
END:VCALENDAR""",
        ]  ## todo: add more broken ical here

        for ical in broken_ical:
            ## This should raise error
            with pytest.raises(vobject.base.ValidateError):
                vobject.readOne(ical).serialize()
            ## This should not raise error
            vobject.readOne(vcal.fix(ical)).serialize()
