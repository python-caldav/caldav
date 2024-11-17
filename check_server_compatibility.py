#!/usr/bin/env python

from tests.conf import client
from tests.conf import CONNKEYS
from tests.compatibility_issues import incompatibility_description
from caldav.lib.error import AuthorizationError, DAVError, NotFoundError
from caldav.lib.python_utilities import to_local
from caldav.elements import dav
import datetime
import click
import time
import json
import uuid

class ServerQuirkChecker():
    def __init__(self, client_obj):
        self.client_obj = client_obj
        self.flags_checked = {}
        self.other_info = {}

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
            ## calendar creation probably went OK
            calmade = True
            self.flags_checked['no_mkcalendar'] = False
            self.flags_checked['read_only'] = False
        except Exception as e:
            ## calendar creation created an exception - return exception
            cal = self.principal.calendar(cal_id=cal_id)
            if not cal:
                ## cal not made and does not exist, exception thrown.
                ## Caller to decide why the calendar was not made
                return (False, e)

        assert(cal)
        
        try:
            cal.delete()
            try:
                cal = self.principal.calendar(cal_id=cal_id)
                cal.events()
            except NotFoundError:
                cal = None
            ## Delete throw no exceptions, but was the calendar deleted?
            if calmade and (not cal or self.flags_checked.get('non_existing_calendar_found')):
                self.flags_checked['no_delete_calendar'] = False
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
                    assert(cal)
                    cal.events()
                    ## Calendar not deleted, but no exception thrown.
                    ## Perhaps it's a "move to thrashbin"-regime on the server
                    self.flags_checked['no_delete_calendar'] = 'maybe'
                except NotFoundError as e:
                    ## Calendar was deleted, it just took some time.
                    self.flags_checked['no_delete_calendar'] = False
                    self.flags_checked['rate_limited'] = True
                    return (calmade, e)
            return (calmade, None)
        except Exception as e:
            self.flags_checked['no_delete_calendar'] = True
            time.sleep(10)
            try:
                cal.delete()
                self.flags_Checked['no_delete_calendar'] = False
                self.flags_Checked['rate_limited'] = True
            except Exception as e2:
                pass
            return (calmade, e)

    def check_principal(self):
        ## TODO
        ## There was a sabre server having this issue.
        ## I'm not sure if this will give the right result, as I don't have
        ## access to any test servers with this compatibility-quirk.
        ## In any case, this test will stop the script on authorization problems
        try:
            self.principal = self.client_obj.principal()
            self.flags_checked['no-current-user-principal'] = False
        except AuthorizationError:
            raise
        except DAVError:
            self.flags_checked['no-current-user-principal'] = True

    def check_mkcalendar(self):
        try:
            cal = self.principal.calendar(cal_id="this_should_not_exist")
            cal.events()
            self.flags_checked["non_existing_calendar_found"] = True
        except NotFoundError:
            self.flags_checked["non_existing_calendar_found"] = False
        except:
            import pdb; pdb.set_trace()
        makeret = self._try_make_calendar(name="Yep", cal_id="pythoncaldav-test")
        if makeret[0]:
            self._default_calendar = self.principal.make_calendar(name="Yep", cal_id="pythoncaldav-test")
            return
        makeret = self._try_make_calendar(cal_id="pythoncaldav-test")
        if makeret[0]:
            self._default_calendar = self.principal.make_calendar(cal_id="pythoncaldav-test")
            self.flags_checked['no_displayname'] = True
            return
        unique_id1 = "testcalendar-" + str(uuid.uuid4())
        unique_id2 = "testcalendar-" + str(uuid.uuid4())
        makeret = self._try_make_calendar(cal_id=unique_id1)
        if makeret[0]:
            self._default_calendar = self.principal.make_calendar(cal_id=unique_id2)
            self.flags_checked['unique_calendar_ids'] = True
        unique_id = "testcalendar-" + str(uuid.uuid4())
        makeret = self._try_make_calendar(cal_id=unique_id, name='Yep')
        if not makeret[0]:
            self.flags_checked['no_displayname'] = True

    def check_support(self):
        self.flags_checked['dav_not_supported'] = True
        self.flags_checked['no_scheduling'] = True
        try:
            self.flags_checked['dav_not_supported'] = not self.client_obj.check_dav_support()
            self.flags_checked['no_scheduling'] = not self.client_obj.check_scheduling_support()
        except:
            pass
        if not self.flags_checked['no_scheduling']:
            try:
                inbox = self.principal.schedule_inbox()
                outbox = self.principal.schedule_outbox()
                self.flags_checked['no_scheduling_mailbox'] = False
            except:
                self.flags_checked['no_scheduling_mailbox'] = True

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
            self.flags_checked['propfind_allprop_failure'] = False
        except:
            self.flags_checked['propfind_allprop_failure'] = True

    def check_event(self):
        try:
            cal = self._default_calendar
            cal.add_event(dtstart=datetime.datetime.now(), summary="Test event 1", categories=['foo','bar'], uid='check_event_1')
            cal.add_event(dtstart=datetime.datetime.now(), summary="Test event 2", categories=['zoo','test'], uid='check_event_2')
            try:
                try:
                    objcnt = len(cal.objects()) == 2
                except:
                    objcnt = 0
                if objcnt != 2:
                    if len(cal.events()) == 2:
                        self.flags_checked['search_always_needs_comptype'] = True
                    else:
                        import pdb; pdb.set_trace()
                        ## we should not be here
                else:
                    self.flags_checked['search_always_needs_comptype'] = False

                events = cal.search(summary='Test event 1')
                if len(events) == 0:
                    events = cal.search(summary='Test event 1', event=True)
                    if len(events)==1:
                        self.flags_checked['search_needs_comptype'] = True
                        self.flags_checked['no_search'] = False
                        self.flags_checked['text_search_not_working'] = False
                    else:
                        import pdb; pdb.set_trace()
                        ## we should not be here ... unless search is not working?
                elif len(events) == 1:        
                    self.flags_checked['no_search'] = False
                    self.flags_checked['text_search_not_working'] = False
                    self.flags_checked['search_always_needs_comptype'] = False
                events = cal.search(summary='test event 1', event=True)
                if len(events) == 1:
                    self.flags_checked['text_search_is_case_insensitive'] = True
                elif  len(events)==0:
                    self.flags_checked['text_search_is_case_insensitive'] = False
                else:
                    ## we should not be here
                    import pdb; pdb.set_trace()
                    pass
                events = cal.search(summary='test event', event=True)
                if len(events)==2:
                    self.flags_checked['text_search_is_exact_match_only'] = False
                elif len(events)==0:
                    self.flags_checked['text_search_is_exact_match_only'] = 'maybe'
                    ## may also be text_search_is_exact_match_sometimes
                try:
                    events = cal.search(category='foo', event=True)
                except:
                    events = []
                if len(events) == 1:
                    self.flags_checked["category_search_yields_nothing"] = False
                elif len(events) == 0:
                    self.flags_checked["category_search_yields_nothing"] = True
                else:
                    ## we should not be here
                    import pdb; pdb.set_trace()
                    pass
                    
            except:
                import pdb; pdb.set_trace()
                ## TODO ...
                raise
        except:
            import pdb; pdb.set_trace()
            raise

    def check_all(self):
        try:
            self.check_principal()
            self.check_support()
            self.check_propfind()
            self.check_mkcalendar()
            self.check_event()
        finally:
            if self._default_calendar:
                self._default_calendar.delete()

    def report(self, verbose, json):
        if self.client_obj.incompatibilities is not None:
            flags_found = set([x for x in self.flags_checked if self.flags_checked[x]])
            self.diff1 = set(self.client_obj.incompatibilities) - flags_found
            self.diff2 = flags_found - set(self.client_obj.incompatibilities)
        if json:
            click.echo(json.dumps({'flags_checked': self.flags_checked, 'diff1': self.diff1, 'diff2': self.diff2}))
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
                    click.echo("differences between configured quirk list and found quirk list:")
                    for x in self.diff1:
                        click.echo(f"-{x}")
                    for x in self.diff2:
                        click.echo(f"+{x}")
                for x in self.flags_checked:
                    if self.flags_checked[x]:
                        click.echo(f"## {x}")
                        click.echo(incompatibility_description[x]) ## todo: format with linebreaks ... and indentation?
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
@click.option("--idx", type=int, help="Choose a server from the test config, by index number")
@click.option("--verbose/--quiet", help="More output")
@click.option("--json/--text", help="JSON output.  Overrides verbose")
def check_server_compatibility(verbose, json, **kwargs):
    conn = client(**kwargs)
    obj = ServerQuirkChecker(conn)
    obj.check_all()
    obj.report(verbose=verbose, json=json)
    conn.teardown(conn)

if __name__ == '__main__':
    check_server_compatibility()
