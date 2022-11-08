#!/usr/bin/env python
import re
import uuid
from datetime import datetime
from datetime import timedelta
from unittest import TestCase

import icalendar
import pytz
import vobject
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
