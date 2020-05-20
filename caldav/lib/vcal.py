#!/usr/bin/env python
# -*- encoding: utf-8 -*-


import re
from caldav.lib.python_utilities import to_local

## Fixups to the icalendar data to work around compatbility issues.
## TODO: would be nice with proper documentation on what systems are
## generating broken data.  Compatibility issues should also be collected
## in the documentation. somewhere.
## 1) COMPLETED MUST be a datetime in UTC according to the RFC, but sometimes
## a date is given.
## 2) The RFC does not specify any range restrictions on the dates, but clearly it doesn't make sense with a CREATED-timestamp that is centuries or decades before RFC2445 was published in 1998.  Apparently some calendar servers generate nonsensical CREATED timestamps while other calendar servers can't handle CREATED timestamps prior to 1970.  Probably it would make more sense to drop the CREATED line completely rather than moving it from the end of year 0AD to the beginning of year 1970.
def fix(event):
    fixed = re.sub('COMPLETED:(\d+)\s', 'COMPLETED:\g<1>T120000Z',
                   to_local(event))
    # The following line fixes a data bug in some Google Calendar events
    fixed = re.sub('CREATED:00001231T000000Z',
                   'CREATED:19700101T000000Z', fixed)
    fixed = re.sub(r"\\+('\")", r"\1", fixed)

    return fixed
