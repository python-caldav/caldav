#!/usr/bin/env python
import datetime
import time
import uuid
from json import dumps

import click

import caldav
from caldav.elements import dav
from caldav.lib.error import AuthorizationError
from caldav.lib.error import DAVError
from caldav.lib.error import NotFoundError
from caldav.lib.python_utilities import to_local
from tests.compatibility_issues import incompatibility_description
from tests.conf import client
from tests.conf import CONNKEYS


def _delay_decorator(f, delay=10):
    def foo(*a, **kwa):
        time.sleep(delay)
        return f(*a, **kwa)

    return foo


class ServerQuirkChecker:
    def __init__(self, client_obj):
        self.client_obj = client_obj
        self.flags_checked = {}
        self.other_info = {}

    def set_flag(self, flag, value=True):
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
        except Exception as e:
            ## calendar creation created an exception - return exception
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
            self.set_flag("no-current-user-principal", True)

    def check_mkcalendar(self):
        try:
            cal = self.principal.calendar(cal_id="this_should_not_exist")
            cal.events()
            self.set_flag("non_existing_calendar_found", True)
        except NotFoundError:
            self.set_flag("non_existing_calendar_found", False)
        except Exception as e:
            import pdb

            pdb.set_trace()
            pass
        ## Check on "no_default_calendar" flag
        try:
            cals = self.principal.calendars()
            cals[0].events()
            self.set_flag("no_default_calendar", False)
            self._default_calendar = cals[0]
        except:
            self.set_flag("no_default_calendar", True)

        makeret = self._try_make_calendar(name="Yep", cal_id="pythoncaldav-test")
        if makeret[0]:
            try:
                self._default_calendar = self.principal.make_calendar(
                    name="Yep", cal_id="pythoncaldav-test"
                )
            except:
                self._default_calendar = self.principal.calendar(
                    cal_id="pythoncaldav-test"
                )
            self._default_calendar.events()
            return
        makeret = self._try_make_calendar(cal_id="pythoncaldav-test")
        if makeret[0]:
            self._default_calendar = self.principal.make_calendar(
                cal_id="pythoncaldav-test"
            )
            self.set_flag("no_displayname", True)
            return
        unique_id1 = "testcalendar-" + str(uuid.uuid4())
        unique_id2 = "testcalendar-" + str(uuid.uuid4())
        makeret = self._try_make_calendar(cal_id=unique_id1)
        if makeret[0]:
            self._default_calendar = self.principal.make_calendar(cal_id=unique_id2)
            self.set_flag("unique_calendar_ids", True)
        unique_id = "testcalendar-" + str(uuid.uuid4())
        makeret = self._try_make_calendar(cal_id=unique_id, name="Yep")
        if not makeret[0] and not self.flags_checked.get("no_mkcalendar", True):
            self.flags_checked["no_displayname"] = True
        if not "no_mkcalendar" in self.flags_checked:
            self.set_flag("no_mkcalendar", True)

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

    def check_event(self):
        cal = self._default_calendar

        ## Two simple events with text fields, dtstart=now and no dtend
        obj1 = cal.add_event(
            dtstart=datetime.datetime.now(),
            summary="Test event 1",
            categories=["foo", "bar"],
            class_="CONFIDENTIAL",
            uid="check_event_1",
        )
        obj2 = cal.add_event(
            dtstart=datetime.datetime.now(),
            summary="Test event 2",
            categories=["zoo", "test"],
            uid="check_event_2",
        )
        try:  ## try-finally-block covering testing of obj1 and obj2
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
                    self.set_flag("search_always_needs_comptype", True)
                else:
                    import pdb

                    pdb.set_trace()
                    pass
                    ## we should not be here
            else:
                self.set_flag("search_always_needs_comptype", False)

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
                self.set_flag("search_always_needs_comptype", False)

            if not self.flags_checked["text_search_not_working"]:
                events = cal.search(summary="test event 1", event=True)
                if len(events) == 1:
                    self.set_flag("text_search_is_case_insensitive", True)
                elif len(events) == 0:
                    self.set_flag("text_search_is_case_insensitive", False)
                else:
                    ## we should not be here
                    import pdb

                    pdb.set_trace()
                    pass
                events = cal.search(summary="test event", event=True)
                if len(events) == 2:
                    self.set_flag("text_search_is_exact_match_only", False)
                elif len(events) == 0:
                    self.set_flag("text_search_is_exact_match_only", "maybe")
                    ## may also be text_search_is_exact_match_sometimes
                events = cal.search(
                    summary="Test event 1", class_="CONFIDENTIAL", event=True
                )
                if len(events) == 1:
                    self.set_flag("combined_search_not_working", False)
                elif len(events) == 0:
                    self.set_flag("combined_search_not_working", True)
                else:
                    import pdb

                    pdb.set_trace()
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
                import pdb

                pdb.set_trace()
                pass

            events = cal.search(summary="test event", class_="CONFIDENTIAL", event=True)
        finally:
            obj1.delete()
            obj2.delete()

        ## Recurring events
        try:
            yearly_time = cal.add_event(
                dtstart=datetime.datetime(2000, 1, 1, 0, 0),
                summary="Yearly timed event",
                uid="firework_event",
                rrule={"FREQ": "YEARLY"},
            )
            yearly_day = cal.add_event(
                dtstart=datetime.date(2000, 5, 1),
                summary="Yearly day event",
                uid="full_day_event",
                rrule={"FREQ": "YEARLY"},
            )
        except:
            ## should not be here
            import pdb

            pdb.set_trace()
            raise
        try:
            try:
                events = cal.search(
                    start=datetime.datetime(2001, 4, 1),
                    end=datetime.datetime(2002, 2, 2),
                    event=True,
                )
                assert len(events) == 2
                self.set_flag("no_recurring", False)
            except:
                self.set_flag("no_recurring", True)

            if not (self.flags_checked["no_recurring"]):
                events = cal.search(
                    start=datetime.datetime(2001, 4, 1),
                    end=datetime.datetime(2002, 2, 2),
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
                    if (
                        "RECURRENCE-ID" in events[0].data
                        and "DTSTART:2001" in events[0].data
                    ):
                        assert "RECURRENCE-ID" in events[1].data
                        self.set_flag("broken_expand", False)
                    else:
                        self.set_flag("broken_expand", True)

        finally:
            yearly_time.delete()
            yearly_day.delete()

    def check_todo(self):
        cal = self._default_calendar

        try:
            ## Add a simplest possible todo
            todo1 = cal.add_todo(
                summary="This is a summary",
                uid="check_todo_1",
            )
        except:
            import pdb; pdb.set_trace()
            pass
        

    def check_all(self):
        try:
            self.check_principal()
            self.check_support()
            self.check_propfind()
            self.check_mkcalendar()
            self.check_event()
        except:
            import pdb

            pdb.set_trace()
            raise
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
        if json:
            click.echo(
                dumps(
                    {
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
    conn = client(**kwargs)
    obj = ServerQuirkChecker(conn)
    obj.check_all()
    obj.report(verbose=verbose, json=json)
    conn.teardown(conn)


if __name__ == "__main__":
    check_server_compatibility()
