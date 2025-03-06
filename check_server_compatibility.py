#!/usr/bin/env python
import os
import time
import uuid
from datetime import date
from datetime import datetime
from datetime import timedelta
from json import dumps

import click

import caldav
from caldav.elements import dav
from caldav.elements import ical
from caldav.lib.error import AuthorizationError
from caldav.lib.error import DAVError
from caldav.lib.error import NotFoundError
from caldav.lib.python_utilities import to_local
from caldav.objects import FreeBusy
from tests.compatibility_issues import incompatibility_description
from tests.conf import client
from tests.conf import CONNKEYS

ical_with_exception1 = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Mozilla.org/NONSGML Mozilla Calendar V1.1//EN
BEGIN:VEVENT
UID:c26921f4-0653-11ef-b756-58ce2a14e2e5
DTSTART:20240411T123000Z
DTEND:20240412T123000Z
DTSTAMP:20240429T181103Z
LAST-MODIFIED:20240429T181103Z
RRULE:FREQ=WEEKLY;INTERVAL=2
SEQUENCE:1
SUMMARY:Test
X-MOZ-GENERATION:1
END:VEVENT
BEGIN:VEVENT
UID:c26921f4-0653-11ef-b756-58ce2a14e2e5
RECURRENCE-ID:20240425T123000Z
DTSTART:20240425T123000Z
DTEND:20240426T123000Z
CREATED:20240429T181031Z
DTSTAMP:20240429T181103Z
LAST-MODIFIED:20240429T181103Z
SEQUENCE:1
SUMMARY:Test (edited)
X-MOZ-GENERATION:1
END:VEVENT
END:VCALENDAR"""

ical_with_exception2 = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Mozilla.org/NONSGML Mozilla Calendar V1.1//EN
BEGIN:VEVENT
UID:c26921f4-0653-11ef-b756-58ce2a14e2e5
DTSTART;VALUE=DATE:20240411
DTEND;VALUE=DATE:20240412
DTSTAMP:20240429T181103Z
LAST-MODIFIED:20240429T181103Z
RRULE:FREQ=WEEKLY;INTERVAL=2
SEQUENCE:1
SUMMARY:Test
X-MOZ-GENERATION:1
END:VEVENT
BEGIN:VEVENT
UID:c26921f4-0653-11ef-b756-58ce2a14e2e5
RECURRENCE-ID;VALUE=DATE:20240425
DTSTART;VALUE=DATE:20240425
DTEND;VALUE=DATE:20240426
CREATED:20240429T181031Z
DTSTAMP:20240429T181103Z
LAST-MODIFIED:20240429T181103Z
SEQUENCE:1
SUMMARY:Test (edited)
X-MOZ-GENERATION:1
END:VEVENT
END:VCALENDAR"""


def _debugger():
    if os.environ.get("PYTHON_CALDAV_DEBUGMODE") == "DEBUG_PDB":
        import pdb

        pdb.set_trace()


def _delay_decorator(f, delay=10):
    """
    Sometimes we need to pause between each request, i.e. due to servers
    that queues up work, rate-limits requests, etc.
    """

    def foo(*a, **kwa):
        time.sleep(delay)
        return f(*a, **kwa)

    return foo


class ServerQuirkChecker:
    """This class will ...

    * Keep the connection details to the server
    * Keep the state of what's already checked

    My idea was to create some clean, nice-looking self-explaining
    code ... but either I'm not qualified for making such code, or the
    problem was more complex than what I assumed.  Perhaps the right
    approach is to just hack on, and then later try to refactor the
    code.

    Having one test for each "quirk", as well as the ability to check
    quirks individually rather than running the full package would be
    nice.  In practice the "quicks" sometimes depend on each other, so
    they have to be run in order.  It's also significant speed
    benefits from not having to rig up and down the calendar for each
    test, and being able to run multiple tests towards the same data
    set.
    """

    def __init__(self, client_obj):
        self.client_obj = client_obj
        self.flags_checked = {}
        self.other_info = {}
        self._default_calendar = None

    def set_flag(self, flag, value=True):
        """
        Basically equivalent to `self._Flags_checked[flag]=value`,
        with a bit extra logics
        """
        assert flag in incompatibility_description
        if flag == "rate_limited":
            self.client_obj.request = _delay_decorator(self.client_obj.request)
        elif flag == "search_delay":
            caldav.Calendar.search = _delay_decorator(caldav.Calendar.search, 60)
            if hasattr(self, "_default_calendar"):
                self._default_calendar.search = _delay_decorator(
                    self._default_calendar.search, 60
                )
        self.flags_checked[flag] = value

    def _try_make_calendar(self, cal_id, **kwargs):
        """
        Does some attempts on creating and deleting calendars, and sets some
        flags - while others should be set by the caller.
        """
        calmade = False

        ## In case calendar already exists ... wipe it first
        try:
            self.principal.calendar(cal_id=cal_id).delete()
        except:
            pass

        ## create the calendar
        try:
            cal = self.principal.make_calendar(cal_id=cal_id, **kwargs)
            ## calendar creation probably went OK, but we need to be sure...
            cal.events()
            ## calendar creation must have gone OK.
            calmade = True
            self.set_flag("no_mkcalendar", False)
            self.set_flag("read_only", False)
            self.principal.calendar(cal_id=cal_id).events()
            if kwargs.get("name"):
                try:
                    name = "A calendar with this name should not exist"
                    self.principal.calendar(name=name).events()
                except:
                    ## This is not the exception, this is the normal
                    try:
                        cal2 = self.principal.calendar(name=kwargs["name"])
                        cal2.events()
                        assert cal2.id == cal.id
                        self.set_flag("no_displayname", False)
                    except:
                        self.set_flag("no_displayname", True)

        except Exception as e:
            ## calendar creation created an exception.  Maybe the calendar exists?
            ## in any case, return exception
            cal = self.principal.calendar(cal_id=cal_id)
            try:
                cal.events()
            except:
                cal = None
            if not cal:
                ## cal not made and does not exist, exception thrown.
                ## Caller to decide why the calendar was not made
                return (False, e)

        assert cal

        try:
            cal.delete()
            try:
                cal = self.principal.calendar(cal_id=cal_id)
                events = cal.events()
            except NotFoundError:
                cal = None
            ## Delete throw no exceptions, but was the calendar deleted?
            if not cal or (
                self.flags_checked.get(
                    "non_existing_calendar_found" and len(events) == 0
                )
            ):
                self.set_flag("no_delete_calendar", False)
                ## Calendar probably deleted OK.
                ## (in the case of non_existing_calendar_found, we should add
                ## some events t o the calendar, delete the calendar and make
                ## sure no events are found on a new calendar with same ID)
            else:
                ## Calendar not deleted.
                ## Perhaps the server needs some time to delete the calendar
                time.sleep(10)
                try:
                    cal = self.principal.calendar(cal_id=cal_id)
                    assert cal
                    cal.events()
                    ## Calendar not deleted, but no exception thrown.
                    ## Perhaps it's a "move to thrashbin"-regime on the server
                    self.set_flag("no_delete_calendar", "maybe")
                except NotFoundError as e:
                    ## Calendar was deleted, it just took some time.
                    self.set_flag("no_delete_calendar", False)
                    self.set_flag("rate_limited", True)
                    return (calmade, e)
            return (calmade, None)
        except Exception as e:
            self.set_flag("no_delete_calendar", True)
            time.sleep(10)
            try:
                cal.delete()
                self.set_flag("no_delete_calendar", False)
                self.set_flag("rate_limited", True)
            except Exception as e2:
                pass
            return (calmade, None)

    def check_principal(self):
        ## TODO
        ## There was a sabre server having this issue.
        ## I'm not sure if this will give the right result, as I don't have
        ## access to any test servers with this compatibility-quirk.
        ## In any case, this test will stop the script on authorization problems
        try:
            self.principal = self.client_obj.principal()
            self.set_flag("no-current-user-principal", False)
        except AuthorizationError:
            raise
        except DAVError:
            ## This probably applies to calendar.mail.ru
            ## TODO: investigate if there are any quick-fixes
            ## TODO: the workaround is to set a calendar path in the config
            ## and fix the rest of the check script so that it works even
            ## without a self.principal object.
            self.set_flag("no-current-user-principal", True)

    def check_mkcalendar(self):
        self.set_flag("unique_calendar_ids", False)
        try:
            cal = self.principal.calendar(cal_id="this_should_not_exist")
            cal.events()
            self.set_flag("non_existing_calendar_found", True)
        except NotFoundError:
            self.set_flag("non_existing_calendar_found", False)
        except Exception as e:
            _debugger()
            pass
        ## Check on "no_default_calendar" flag
        try:
            cals = self.principal.calendars()
            events = cals[0].events()
            ## We will not do any testing on a calendar that already contains events
            self.set_flag("no_default_calendar", False)
        except:
            self.set_flag("no_default_calendar", True)

        makeret = self._try_make_calendar(name="Yep", cal_id="pythoncaldav-test")
        if makeret[0]:
            ## calendar created
            return
        makeret = self._try_make_calendar(cal_id="pythoncaldav-test")
        if makeret[0]:
            self.set_flag("no_displayname", True)
            return
        unique_id1 = "testcalendar-" + str(uuid.uuid4())
        makeret = self._try_make_calendar(cal_id=unique_id1, name="Yep")
        if makeret[0]:
            self.set_flag("unique_calendar_ids", True)
            return
        unique_id = "testcalendar-" + str(uuid.uuid4())
        makeret = self._try_make_calendar(cal_id=unique_id)
        if makeret[0]:
            self.flags_checked["no_displayname"] = True
            return
        if not "no_mkcalendar" in self.flags_checked:
            self.set_flag("no_mkcalendar", True)

    def _fix_cal_if_needed(self, todo=False):
        if self.flags_checked["no_delete_event"]:
            return self._fix_cal(todo=todo)
        else:
            return self._default_calendar

    def _fix_cal(self, todo=False):
        kwargs = {}
        try:
            if self._default_calendar:
                self._default_calendar.delete()
        except:
            pass
        if self.flags_checked["no_mkcalendar"]:
            cal = self.principal.calendars()[0]
            if cal.events() or cal.todos():
                import pdb

                pdb.set_trace()
                raise "Refusing to run tests on a calendar with content"
            self._default_calendar = cal
            return cal
        if todo and self.flags_checked.get("no_todo_on_standard_calendar"):
            kwargs["supported_calendar_component_set"] = ["VTODO"]
        if self.flags_checked["unique_calendar_ids"]:
            kwargs["cal_id"] = "testcalendar-" + str(uuid.uuid4())
        else:
            kwargs["cal_id"] = "pythoncaldav-test"
        if self.flags_checked["no_displayname"]:
            kwargs["name"] = None
        else:
            kwargs["name"] = "CalDAV Server Testing"
        cal = self.principal.make_calendar(**kwargs)
        self._default_calendar = cal
        return cal

    def check_support(self):
        self.set_flag("dav_not_supported", True)
        self.set_flag("no_scheduling", True)
        try:
            self.set_flag("dav_not_supported", not self.client_obj.check_dav_support())
            self.set_flag(
                "no_scheduling", not self.client_obj.check_scheduling_support()
            )
        except:
            pass
        if not self.flags_checked["no_scheduling"]:
            try:
                inbox = self.principal.schedule_inbox()
                outbox = self.principal.schedule_outbox()
                self.set_flag("no_scheduling_mailbox", False)
            except:
                self.set_flag("no_scheduling_mailbox", True)

    def check_propfind(self):
        try:
            foo = self.client_obj.propfind(
                self.principal.url,
                props='<?xml version="1.0" encoding="UTF-8"?>'
                '<D:propfind xmlns:D="DAV:">'
                "  <D:allprop/>"
                "</D:propfind>",
            )
            assert "resourcetype" in to_local(foo.raw)

            # next, the internal _query_properties, returning an xml tree ...
            foo2 = self.principal._query_properties(
                [
                    dav.Status(),
                ]
            )
            assert "resourcetype" in to_local(foo.raw)
            self.set_flag("propfind_allprop_failure", False)
        except:
            self.set_flag("propfind_allprop_failure", True)

    def check_calendar_color_and_order(self):
        """
        Calendar color and order is not a part of the CalDAV standard, but
        many calendar servers supports it
        """
        try:
            self._check_prop(ical.CalendarColor, "goldenred", "blue")
            self.set_flag("calendar_color", True)
        except Exception as e:
            self.set_flag("calendar_color", False)
        try:
            self._check_prop(ical.CalendarOrder, "-143", "8")
            self.set_flag("calendar_order", True)
        except:
            self.set_flag("calendar_order", False)

    def _check_prop(self, propclass, silly_value, test_value):
        cal = self._default_calendar
        props = cal.get_properties([(propclass())])
        assert props[propclass.tag] != silly_value
        cal.set_properties(propclass(test_value))
        props = cal.get_properties([(propclass())])
        assert props[propclass.tag] == test_value

    def check_event(self):
        cal = self._default_calendar

        ## Two simple events with text fields, dtstart=now and no dtend
        obj1 = cal.add_event(
            dtstart=datetime.now(),
            summary="Test event 1",
            categories=["foo", "bar"],
            class_="CONFIDENTIAL",
            uid="check_event_1",
        )
        obj2 = cal.add_event(
            dtstart=datetime.now(),
            summary="Test event 2",
            categories=["zoo", "test"],
            uid="check_event_2",
        )

        try:  ## try-finally-block covering testing of obj1 and obj2
            self._check_simple_events(obj1, obj2)
        finally:
            obj1.delete()
            obj2.delete()

        ## Recurring events
        try:
            yearly_time = cal.add_event(
                dtstart=datetime(2000, 1, 1, 0, 0),
                summary="Yearly timed event",
                uid="firework_event",
                rrule={"FREQ": "YEARLY"},
            )
            yearly_day = cal.add_event(
                dtstart=date(2000, 5, 1),
                summary="Yearly day event",
                uid="full_day_event",
                rrule={"FREQ": "YEARLY"},
            )
        except:
            ## should not be here
            _debugger()
            raise
        try:
            self._check_freebusy()
            self._check_recurring_events(yearly_time, yearly_day)
        finally:
            yearly_time.delete()
            yearly_day.delete()

        if cal.events():
            ## Zimbra.  Probably related to event_by_url_is_broken
            self.set_flag("no_delete_event")
            cal = self._fix_cal()
        else:
            self.set_flag("no_delete_event", False)

        ## Finally, a check that searches involving timespans works as intended
        span = cal.add_event(
            dtstart=datetime(2000, 7, 1, 8),
            dtend=datetime(2000, 7, 1, 16),
            summary="An 8 hour event",
            uid="eight_hour_event1",
        )

        foo = self._date_search(span, assert_found=False, event=True)
        if len(foo) != 0:
            raise

        span = cal.add_event(
            dtstart=datetime(2000, 7, 1, 8),
            duration=timedelta(hours=8),
            summary="Another 8 hour event",
            uid="eight_hour_event2",
        )
        ret = self._date_search(span, assert_found=False, event=True)
        if ret == [4, 6, 7]:
            self.set_flag("date_search_ignores_duration")
        else:
            self.set_flag("date_search_ignores_duration", False)
            assert len(ret) == 0

    def check_exception(self):
        if self.flags_checked.get("broken_expand"):
            return
        self._check_exception(ical_with_exception1)
        self._check_exception(ical_with_exception2)

    def _check_exception(self, ical):
        cal = self._default_calendar
        obj = cal.add_event(ical)
        try:
            results = cal.search(
                start=datetime(2024, 3, 31, 0, 0),
                end=datetime(2024, 5, 4, 0, 0, 0),
                event=True,
                expand="server",
            )
            assert len(results) == 2
            for r in results:
                assert "RRULE" not in r.data
                recurrence_id = r.icalendar_component["RECURRENCE-ID"]
                assert isinstance(recurrence_id, icalendar.vDDDTypes)
            if not "broken_expand_on_exceptions" in self.flags_checked:
                self.set_flag("broken_expand_on_exceptions", False)
        except Exception as e:
            self.set_flag("broken_expand_on_exceptions")
        finally:
            obj.delete()

    def _check_freebusy(self):
        cal = self._default_calendar
        ## TODO:
        ## Surely we should do more tests on freebusy, how does it work wrg
        ## of tasks, recurring events, etc, etc.
        try:
            freebusy = cal.freebusy_request(
                datetime(1999, 12, 30, 17, 0, 0), datetime(2000, 1, 1, 12, 30, 0)
            )
            # TODO: assert something more complex on the return object
            assert isinstance(freebusy, FreeBusy)
            assert freebusy.instance.vfreebusy
            self.set_flag("no_freebusy_rfc4791", False)
        except Exception as e:
            self.set_flag("no_freebusy_rfc4791")

    def _check_simple_events(self, obj1, obj2):
        cal = self._default_calendar
        try:
            obj1_ = cal.event_by_url(obj1.url)
            assert "SUMMARY:Test event 1" in obj1_.data
            self.set_flag("event_by_url_is_broken", False)
        except:
            self.set_flag("event_by_url_is_broken")

        try:
            foo = cal.event_by_uid("check_event_2")
            assert foo
            self.set_flag("object_by_uid_is_broken", False)
        except:
            time.sleep(60)
            try:
                foo = cal.event_by_uid("check_event_2")
                assert foo
                self.set_flag("search_delay")
                self.set_flag("object_by_uid_is_broken", False)
            except:
                self.set_flag("object_by_uid_is_broken", True)

        try:
            objcnt = len(cal.objects())
        except:
            objcnt = 0
        if objcnt != 2:
            if len(cal.events()) == 2:
                self.set_flag("search_needs_comptype", True)
            else:
                _debugger()
                pass
                ## we should not be here
        else:
            self.set_flag("search_needs_comptype", False)

        ## purelymail writes things to an index as a background thread
        ## and have delayed search.  Let's test for that first.
        events = cal.search(summary="Test event 1", event=True)
        if len(events) == 0:
            events = cal.search(summary="Test event 1", event=True)
            if len(events) == 1:
                self.set_flag("rate_limited", True)
        if len(events) == 1:
            self.set_flag("no_search", False)
            self.set_flag("text_search_not_working", False)
        else:
            self.set_flag("text_search_not_working", True)

        objs = cal.search(summary="Test event 1")
        if len(objs) == 0 and len(events) == 1:
            self.set_flag("search_needs_comptype", True)
        elif len(objs) == 1:
            self.set_flag("search_needs_comptype", False)

        if not self.flags_checked["text_search_not_working"]:
            events = cal.search(summary="test event 1", event=True)
            if len(events) == 1:
                self.set_flag("text_search_is_case_insensitive", True)
            elif len(events) == 0:
                self.set_flag("text_search_is_case_insensitive", False)
            else:
                ## we should not be here
                _debugger()
                pass
            events = cal.search(summary="Test event", event=True)
            if len(events) == 2:
                self.set_flag("text_search_is_exact_match_only", False)
            elif len(events) == 0:
                self.set_flag("text_search_is_exact_match_only", "maybe")
                ## may also be text_search_is_exact_match_sometimes
            events1 = cal.search(
                summary="Test event 1", class_="CONFIDENTIAL", event=True
            )
            ## I don't expect this program to be in use by 2055.
            events2 = cal.search(
                start=datetime(2000, 1, 1),
                end=datetime(2055, 1, 1),
                class_="CONFIDENTIAL",
                event=True,
            )
            if len(events1) == 1 and len(events2) == 1:
                self.set_flag("combined_search_not_working", False)
            elif len(events1 + events2) in (0, 1, 3):
                self.set_flag("combined_search_not_working", True)
            else:
                _debugger()
                ## We should not be here
                pass
        try:
            events = cal.search(category="foo", event=True)
        except:
            events = []
        if len(events) == 1:
            self.set_flag("category_search_yields_nothing", False)
        elif len(events) == 0:
            self.set_flag("category_search_yields_nothing", True)
        else:
            ## we should not be here
            _debugger()
            pass

    def _check_recurring_events(self, yearly_time, yearly_day):
        cal = self._default_calendar
        try:
            events = cal.search(
                start=datetime(2001, 4, 1),
                end=datetime(2002, 2, 2),
                event=True,
            )
            assert len(events) == 2
            self.set_flag("no_recurring", False)
        except:
            self.set_flag("no_recurring", True)

        if self.flags_checked["no_recurring"]:
            return

        events = cal.search(
            start=datetime(2001, 4, 1),
            end=datetime(2002, 2, 2),
            event=True,
            expand="server",
        )
        assert len(events) == 2
        if "RRULE" in events[0].data:
            assert "RRULE" in events[1].data
            assert not "RECURRENCE-ID" in events[0].data
            assert not "RECURRENCE-ID" in events[1].data
            self.set_flag("no_expand", True)
        else:
            assert not "RRULE" in events[1].data
            self.set_flag("no_expand", False)
            if "RECURRENCE-ID" in events[0].data and "DTSTART:2001" in events[0].data:
                assert "RECURRENCE-ID" in events[1].data
                self.set_flag("broken_expand", False)
            else:
                self.set_flag("broken_expand", True)

    def _date_search(self, obj, has_duration=True, **kwargs):
        try:
            return self._do_date_search(has_duration=has_duration, **kwargs)
        finally:
            obj.delete()

    def _do_date_search(self, assert_found=True, has_duration=True, **kwargs):
        """
        returns a "disbehavior list".
        All those searches should find the event:
        0: open-ended search with end after event
        1: open-ended search with start before event
        2: search interval covers event
        3: open-ended search with end during event
        4: open-ended search with start during event
        5: search with end during event
        6: search with start and end during event
        7: search with start during event
        """
        cal = self._default_calendar
        longbefore = datetime(2000, 5, 30, 4)
        before = datetime(2000, 7, 1, 4)
        during1 = datetime(2000, 7, 1, 10)
        during2 = datetime(2000, 7, 1, 12)
        after = datetime(2000, 7, 1, 22)
        longafter = datetime(2000, 9, 2, 10)
        if self.flags_checked.get("inaccurate_datesearch"):
            before = before - timedelta(days=31)
            after = after + timedelta(days=31)
        one_event_lists = [
            ## open-ended searches, should yield object
            cal.search(end=after, **kwargs),  ## 0
            cal.search(start=before, **kwargs),  ## 1
            cal.search(start=before, end=after, **kwargs),  ## 2
        ]
        if has_duration:
            ## overlapping searches, everything should yield object
            one_event_lists.extend(
                [
                    cal.search(end=during1, **kwargs),  ## 3
                    cal.search(start=during1, **kwargs),  ## 4
                    cal.search(start=before, end=during1, **kwargs),  ## 5
                    cal.search(start=during1, end=during2, **kwargs),  ## 6
                    cal.search(start=during1, end=after, **kwargs),  ## 7
                ]
            )
        ret = []
        for i in range(0, len(one_event_lists)):
            if not assert_found and len(one_event_lists[i]) == 0:
                ret.append(i)
            else:
                assert len(one_event_lists[i]) == 1
        should_be_empty = cal.search(start=longbefore, end=before)
        if should_be_empty:
            assert len(should_be_empty) == 1
            ical = should_be_empty[0].icalendar_component
            assert "due" in ical and not "dtstart" in ical
            self.set_flag("vtodo_no_dtstart_infinite_duration")

        if kwargs.get("todo"):
            if len(cal.search(end=before, **kwargs)) == 0:
                if (
                    not "vtodo_datesearch_nostart_future_tasks_delivered"
                    in self.flags_checked
                ):
                    self.set_flag(
                        "vtodo_datesearch_nostart_future_tasks_delivered", False
                    )
            else:
                self.set_flag("vtodo_datesearch_nostart_future_tasks_delivered", True)
                assert len(cal.search(end=before, **kwargs)) == 1
        else:
            none = cal.search(end=before, **kwargs)
            if none:
                none = cal.search(end=longbefore, **kwargs)
                assert not none
                self.set_flag("inaccurate_datesearch")
                before = before - timedelta(days=31)
                after = after + timedelta(days=31)
            else:
                if not "inaccurate_Datesearch" in self.flags_checked:
                    self.set_flag("inaccurate_datesearch", False)

        assert len(cal.search(start=after, end=longafter)) == 0
        if len(cal.search(start=after, **kwargs)):
            import pdb

            pdb.set_trace()
        assert len(cal.search(start=after, **kwargs)) == 0
        return ret

    def check_todo(self):
        cal = self._default_calendar
        simple = {
            "summary": "This is a summary",
            "uid": "check_todo_1",
        }
        try:
            ## Add a simplest possible todo
            todo_simple = cal.add_todo(**simple)
            if not self.flags_checked["object_by_uid_is_broken"]:
                assert (
                    str(cal.todo_by_uid("check_todo_1").icalendar_component["UID"])
                    == "check_todo_1"
                )
            self.set_flag("no_todo", False)
        except Exception as e:
            self.set_flag("no_todo_on_standard_calendar")
            cal = self._fix_cal(todo=True)
            try:
                ## Add a simplest possible todo
                todo_simple = cal.add_todo(**simple)
                if not self.flags_checked["object_by_uid_is_broken"]:
                    assert (
                        str(cal.todo_by_uid("check_todo_1").icalendar_component["UID"])
                        == "check_todo_1"
                    )
                    self.set_flag("no_todo", False)
            except:
                self.set_flag("no_todo_on_standard_calendar", False)
                self.set_flag("no_todo")
                return
        try:
            self._check_simple_todo(todo_simple)
        finally:
            todo_simple.delete()
            self._fix_cal_if_needed()

        ## There are more corner cases to consider
        ## See RFC 4791, section 9.9
        ## For tasks missing DTSTART and DUE/DURATION, but having
        ## CREATED/COMPLETED, those time attributes should be
        ## considered.  TODO: test that, too.
        todo = cal.add_todo(
            summary="This has dtstart",
            dtstart=datetime(2000, 7, 1, 8),
            uid="check_todo_2",
        )
        foobar1 = self._date_search(
            todo, assert_found=False, has_duration=False, todo=True
        )

        todo = cal.add_todo(
            summary="This has due",
            due=datetime(2000, 7, 1, 16),
            uid="check_todo_3",
        )
        foobar2 = self._date_search(
            todo, assert_found=False, has_duration=False, todo=True
        )

        if not "vtodo_no_dtstart_infinite_duration" in self.flags_checked:
            self.set_flag("vtodo_no_dtstart_infinite_duration", False)

        todo = cal.add_todo(
            summary="This has dtstart and due",
            dtstart=datetime(2000, 7, 1, 8),
            due=datetime(2000, 7, 1, 16),
            uid="check_todo_4",
        )

        foobar3 = self._date_search(todo, assert_found=False, todo=True)

        todo = cal.add_todo(
            summary="This has dtstart and dur",
            dtstart=datetime(2000, 7, 1, 8),
            duration=timedelta(hours=1),
            uid="check_todo_5",
        )
        foobar4 = self._date_search(todo, assert_found=False, todo=True)

        if len(foobar1 + foobar2 + foobar3 + foobar4) == 22:
            ## no todos found
            self.set_flag("no_todo_datesearch")
            assert self.flags_checked.pop(
                "vtodo_datesearch_notime_task_is_skipped"
            )  ## redundant
            return

        self.set_flag("no_todo_datesearch", False)
        if foobar1 == [1, 2]:
            ## dtstart, but no due.
            ## open-ended search with end after event: found
            ## open-ended search with start before event: not found
            ## search with interval covering due: not found
            ## Weird!
            self.set_flag("no_dtstart_search_weirdness")
        else:
            assert not foobar1
            self.set_flag("vtodo_no_dtstart_search_weirdness", False)

        if len(foobar2) == 3:
            self.set_flag("vtodo_datesearch_nodtstart_task_is_skipped")
        else:
            self.set_flag("vtodo_datesearch_nodtstart_task_is_skipped", False)
            assert not foobar2

        assert not foobar3

        self.set_flag("vtodo_no_duration_search_weirdness", False)
        if foobar4 == [4, 6, 7]:
            self.set_flag("date_todo_search_ignores_duration")
        elif foobar4 == [1, 2, 4, 5, 6, 7]:
            ## Zimbra is weird!
            self.set_flag("vtodo_no_dtstart_search_weirdness")
        else:
            self.set_flag("date_todo_search_ignores_duration", False)
            assert len(foobar4) == 0

    def _check_simple_todo(self, todo):
        cal = self._default_calendar

        ## search for a simple todo
        try:
            sr = cal.search(summary="This is a summary", todo=True)
            assert len(sr) == 1
        except:
            _debugger()
            ## simple search for a todo won't work.
            ## I haven't seen that before.
            ## TODO: add a flag for this
            raise

        ## RFC says that a todo without dtstart/due is
        ## supposed to span over "infinite time".  So itshould always appear
        ## in date searches.
        try:
            todos = cal.search(
                start=datetime(2020, 1, 1), end=datetime(2020, 1, 2), todo=True
            )
            assert len(todos) in (0, 1)
            self.set_flag("vtodo_datesearch_notime_task_is_skipped", len(todos) == 0)
        except Exception as e:
            self.set_flag("no_todo_datesearch", True)

    def check_all(self):
        try:
            self.check_principal()
            self.check_support()
            self.check_propfind()
            self.check_mkcalendar()
            self._fix_cal()
            self.check_calendar_color_and_order()
            self.check_event()
            self.check_exception()
            self.check_todo()
        finally:
            if self._default_calendar and not self.flags_checked["no_mkcalendar"]:
                try:
                    self._default_calendar.delete()
                except:
                    pass

    def report(self, verbose, json):
        if verbose:
            if self.client_obj.server_name:
                click.echo(f"# {self.client_obj.server_name} - {self.client_obj.url}")
            else:
                click.echo(f"# {self.client_obj.url}")
            click.echo()
        if self.client_obj.incompatibilities is not None:
            flags_found = set([x for x in self.flags_checked if self.flags_checked[x]])
            self.diff1 = set(self.client_obj.incompatibilities) - flags_found
            self.diff2 = flags_found - set(self.client_obj.incompatibilities)
        else:
            self.diff1 = []
            self.diff2 = []
        if json:
            click.echo(
                dumps(
                    {
                        "caldav_version": caldav.__version__,
                        "ts": time.time(),
                        "name": self.client_obj.server_name,
                        "url": str(self.client_obj.url),
                        "flags_checked": self.flags_checked,
                        "diff1": list(self.diff1),
                        "diff2": list(self.diff2),
                    },
                    indent=4,
                )
            )
            click.echo()
            return
        if verbose is False:
            return
        else:
            for x in self.flags_checked:
                if self.flags_checked[x] or verbose:
                    click.echo(f"{x:28} {self.flags_checked[x]}")
            if verbose:
                click.echo()
                if self.diff1 or self.diff2:
                    click.echo(
                        "differences between configured quirk list and found quirk list:"
                    )
                    for x in self.diff1:
                        click.echo(f"-{x}")
                    for x in self.diff2:
                        click.echo(f"+{x}")
                    click.echo()
                for x in self.flags_checked:
                    if self.flags_checked[x]:
                        click.echo(f"## {x}")
                        click.echo(
                            incompatibility_description[x]
                        )  ## todo: format with linebreaks ... and indentation?
                        click.echo()
                for x in self.other_info:
                    click.echo(f"{x:28} {self.other_info[x]}")


## click-decorating ... this got messy, perhaps I should have used good,
## old argparse rather than "click" ...
def _set_conn_options(func):
    """
    Decorator adding all the caldav connection params
    """
    ## TODO: fetch this from the DAVClient.__init__ declaration
    types = {"timeout": int, "auth": object, "headers": dict, "huge_tree": bool}

    for foo in CONNKEYS:
        footype = types.get(foo, str)
        if footype == object:
            continue
        func = click.option(f"--{foo}", type=footype)(func)
    return func


@click.command()
@_set_conn_options
@click.option(
    "--idx", type=int, help="Choose a server from the test config, by index number"
)
@click.option("--verbose/--quiet", default=None, help="More output")
@click.option("--json/--text", help="JSON output.  Overrides verbose")
def check_server_compatibility(verbose, json, **kwargs):
    click.echo("WARNING: this script is not production-ready")
    conn = client(**kwargs)
    obj = ServerQuirkChecker(conn)
    obj.check_all()
    obj.report(verbose=verbose, json=json)
    conn.teardown(conn)


if __name__ == "__main__":
    check_server_compatibility()
