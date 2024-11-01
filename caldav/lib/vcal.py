#!/usr/bin/env python
import datetime
import logging
import re
import uuid

import icalendar

from caldav.lib.python_utilities import to_normal_str

## Global counter.  We don't want to be too verbose on the users, ref https://github.com/home-assistant/core/issues/86938
fixup_error_loggings = 0

## Fixups to the icalendar data to work around compatibility issues.

## TODO:

## 1) this should only be done if needed.  Use try-except around the
## fragments where icalendar/vobject is parsing ical data, and do the
## fixups there.

## 2) arguably, this is outside the scope of the caldav library.
## check if this can be done in vobject or icalendar libraries instead
## of here


## TODO: would be nice with proper documentation on what systems are
## generating broken data.  Compatibility issues should also be collected
## in the documentation. somewhere.
def fix(event):
    """This function receives some ical as it's given from the server, checks for
    breakages with the standard, and attempts to fix up known issues:

    1) COMPLETED MUST be a datetime in UTC according to the RFC, but sometimes
    a date is given. (Google Calendar?) SOGo!  Ref https://github.com/home-assistant/core/issues/106671


    2) The RFC does not specify any range restrictions on the dates,
    but clearly it doesn't make sense with a CREATED-timestamp that is
    centuries or decades before RFC2445 was published in 1998.
    Apparently some calendar servers generate nonsensical CREATED
    timestamps while other calendar servers can't handle CREATED
    timestamps prior to 1970.  Probably it would make more sense to
    drop the CREATED line completely rather than moving it from the
    end of year 0AD to the beginning of year 1970. (Google Calendar)

    3) iCloud apparently duplicates the DTSTAMP property sometimes -
    keep the first DTSTAMP encountered (arguably the DTSTAMP with earliest value
    should be kept).

    4) ref https://github.com/python-caldav/caldav/issues/37,
    X-APPLE-STRUCTURED-EVENT attribute sometimes comes with trailing
    white space.  I've decided to remove all trailing spaces, since
    they seem to cause a traceback with vobject and those lines are
    simply ignored by icalendar.

    5) Zimbra can apparently create events with both dtstart, dtend
    and duration set - which is forbidden according to the RFC.  We
    should probably verify that the data is consistent.  As for now,
    we'll just drop DURATION or DTEND (whatever comes last).
    """
    event = to_normal_str(event)
    if not event.endswith("\n"):
        event = event + "\n"

    ## TODO: add ^ before COMPLETED and CREATED?
    ## 1) Add an arbitrary time if completed is given as date
    fixed = re.sub(
        r"COMPLETED(?:;VALUE=DATE)?:(\d+)\s", r"COMPLETED:\g<1>T120000Z", event
    )

    ## 2) CREATED timestamps prior to epoch does not make sense,
    ## change from year 0001 to epoch.
    fixed = re.sub("CREATED:00001231T000000Z", "CREATED:19700101T000000Z", fixed)
    fixed = re.sub(r"\\+('\")", r"\1", fixed)

    ## 4) trailing whitespace probably never makes sense
    fixed = re.sub(" *$", "", fixed)

    ## 3 fix duplicated DTSTAMP ... and ...
    ## 5 prepare to remove DURATION or DTEND/DUE if both DURATION and
    ## DTEND/DUE is set.
    ## remove duplication of DTSTAMP
    fixed2 = (
        "\n".join(filter(LineFilterDiscardingDuplicates(), fixed.strip().split("\n")))
        + "\n"
    )

    if fixed2 != event:
        ## This obscure code will ensure efficient rate-limiting of the error
        ## logging. The "remove_bit" lambda will return 0 only for powers of
        ## two (2, 4, 8, 16, 32, 64, etc).
        global fixup_error_loggings
        fixup_error_loggings += 1
        is_power_of_two = lambda n: not (n & (n - 1))
        if is_power_of_two(fixup_error_loggings):
            log = logging.warning
        else:
            log = logging.debug

        log_message = [
            "Ical data was modified to avoid compatibility issues",
            "(Your calendar server breaks the icalendar standard)",
            "This is probably harmless, particularly if not editing events or tasks",
            f"(error count: {fixup_error_loggings} - this error is ratelimited)",
        ]

        try:
            import difflib

            diff = list(
                difflib.unified_diff(event.split("\n"), fixed2.split("\n"), lineterm="")
            )
        except:
            diff = ["Original: ", event, "Modified: ", fixed2]

        log("\n".join(log_message + diff))

    return fixed2


class LineFilterDiscardingDuplicates:
    """Needs to be a class because it keeps track of whether a certain
    group of date line was already encountered within a vobject.
    This must be called line by line in order on the complete text, at
    least comprising the complete vobject.
    """

    def __init__(self) -> None:
        self.stamped = 0
        self.ended = 0

    def __call__(self, line):
        if line.startswith("BEGIN:V"):
            self.stamped = 0
            self.ended = 0

        elif re.match("(DURATION|DTEND|DUE)[:;]", line):
            if self.ended:
                return False
            self.ended += 1

        elif re.match("DTSTAMP[:;]", line):
            if self.stamped:
                return False
            self.stamped += 1

        return True


## sorry for being english-language-euro-centric ... fits rather perfectly as default language for me :-)
def create_ical(ical_fragment=None, objtype=None, language="en_DK", **props):
    """
    I somehow feel this fits more into the icalendar library than here
    """
    ical_fragment = to_normal_str(ical_fragment)
    if not ical_fragment or not re.search("^BEGIN:V", ical_fragment, re.MULTILINE):
        my_instance = icalendar.Calendar()
        if objtype is None:
            objtype = "VEVENT"
        component = icalendar.cal.component_factory[objtype]()
        my_instance.add_component(component)
        ## STATUS should default to NEEDS-ACTION for tasks, if it's not set
        ## (otherwise we cannot easily add a task to a davical calendar and
        ## then find it again - ref https://gitlab.com/davical-project/davical/-/issues/281
        if (
            not props.get("status")
            and "\nSTATUS:" not in (ical_fragment or "")
            and objtype == "VTODO"
        ):
            props["status"] = "NEEDS-ACTION"

    else:
        if not ical_fragment.strip().startswith("BEGIN:VCALENDAR"):
            ical_fragment = (
                "BEGIN:VCALENDAR\n"
                + to_normal_str(ical_fragment.strip())
                + "\nEND:VCALENDAR\n"
            )
        my_instance = icalendar.Calendar.from_ical(ical_fragment)
        component = my_instance.subcomponents[0]
        ical_fragment = None

    ## Populate with mandatory fields, if missing
    if not my_instance.get("prodid"):
        my_instance.add("prodid", "-//python-caldav//caldav//" + language)
    if not my_instance.get("version"):
        my_instance.add("version", "2.0")
    if not component.get("dtstamp") and not props.get("dtstamp"):
        component.add("dtstamp", datetime.datetime.now(tz=datetime.timezone.utc))
    if not component.get("uid") and not props.get("uid"):
        component.add("uid", uuid.uuid1())

    for prop in props:
        if props[prop] is not None:
            if isinstance(props[prop], datetime.datetime) and not props[prop].tzinfo:
                ## We need to have a timezone!  Assume UTC.
                props[prop] = props[prop].astimezone(datetime.timezone.utc)
            if prop in ("child", "parent"):
                for value in props[prop]:
                    component.add(
                        "related-to",
                        str(value),
                        parameters={"reltype": prop.upper()},
                        encode=True,
                    )
            else:
                component.add(prop, props[prop])
    ret = to_normal_str(my_instance.to_ical())
    if ical_fragment and ical_fragment.strip():
        ret = re.sub(
            "^END:V",
            ical_fragment.strip() + "\nEND:V",
            ret,
            flags=re.MULTILINE,
            count=1,
        )
    return ret
