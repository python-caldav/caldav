from caldav import DAVClient, error
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import uuid
import sys

## Some inital setup.  We'll need three caldav client objects, with
## corresponding principal objects and calendars.
class TestUser:
    def __init__(self, i):
        self.client = DAVClient(username = "testuser%i" % i, password = "testpass%i" %i, url = "http://calendar.tobixen.no/caldav.php/")
        self.principal = self.client.principal()
        calendar_id = "schedulingtestcalendar%i" % i
        calendar_name = "calendar #%i for scheduling demo" % i
        try:
            self.calendar = self.principal.calendar(name=calendar_name)
        except error.NotFoundError:
            self.calendar = self.principal.make_calendar(name=calendar_name, cal_id=calendar_id)
organizer = TestUser(1)
attendee1 = TestUser(2)
attendee2 = TestUser(3)

## Verify that the calendar server supports scheduling
if not organizer.client.check_scheduling_support():
    print("Server does not support RFC6638")
    sys.exit(1)

## We'll be using the icalendar library to set up a mock meeting,
## at some far point in the future.
caldata = Calendar()
caldata.add('prodid', '-//tobixen//python-icalendar//en_DK')
caldata.add('version', '2.0')

uid = uuid.uuid1()
event=Event()
event.add('dtstamp', datetime.now())
event.add('dtstart', datetime.now() + timedelta(days=4000))
event.add('dtend', datetime.now() + timedelta(days=4000, hours=1))
event.add('uid', uid)
event.add('summary', 'Some test event made to test scheduling in the caldav library')
caldata.add_component(event)

## print to stdout
print("Here is our test event:")
print(caldata.to_ical().decode('utf-8'))

## that event is without any attendee information.  If saved to the
## calendar, it will only be stored locally, no invitations sent.

## There are two ways to send calendar invites:

## * Add Attendee-lines and an Organizer-line to the event data, and
##   then use calendar.save_event(caldata) ... see RFC6638, appendix B.1
##   for an example.

## * Use convenience-method calendar.send_invites(caldata, attendees).
##   It will fetch organizer from the principal object.  Method should
##   accept different kind of attendees: strings, VCalAddress, (cn,
##   email)-tuple and principal object.

## In the example below, the organizer is inviting itself (by
## VCalAddress), attendee1 (by CN/email tuple) and attendee2 (by
## principle object).  (Arguably it would have been easy to use
## attendee2.principle instead of building a new principle object -
## but remember, the attendee2-object contains credentials for
## attendee2, the organizer is not supposed to have access to this
## object).

organizer.calendar.send_schedule_request(
    caldata, attendees=(
        organizer.principal.get_vcal_address(),
        ('Test User 2', 't-caldav-test2@tobixen.no'),
        organizer.client.principal(url=organizer.principal.url.replace('testuser1', 'testuser2'))
    ))

## Invite shipped.  The attendees should now respond to it.
for inbox_item in attendee1.schedule_inbox.get_items():
    ## an inbox_item is an ordinary CalendarResourceObject/Event/Todo etc.
    ## is_invite() will be implemented on the base class and will yield True
    ## for invite messages.
    if inbox_item.is_invite():
        
        ## Ref RFC6638, example B.3 ... to respond to an invite, it's
        ## needed to edit the ical data, find the correct
        ## "attendee"-field, change the attendee "partstat", put the
        ## ical object back to the server.  In addition one has to
        ## look out for race conflicts and retry the whole operation
        ## in case of race conflicts.  Editing ical data is a bit
        ## outside the scope of the CalDAV client library, but ... the
        ## library clearly needs convenience methods to deal with this.

        ## Invite objects will have methods accept_invite(),
        ## reject_invite(),
        ## tentative_accept_invite().  .delete() is also an option
        ## (ref RFC6638, example B.2)
        inbox_item.accept_invite()

## Testuser3 has other long-term plans and can't join the event
for inbox_item in attendee2.principal.schedule_inbox.get_items():
    if inbox_item.is_invite():
        inbox_item.reject_invite()

## Testuser0 will have an update on the participant status in the
## inbox (or perhaps two updates?)  If I've understood the standard
## correctly, testuser0 should not get an invite and should not have
## to respond to it, but just in case we'll accept it.  As far as I've
## understood, deleting the ical objects in the inbox should be
## harmless, it should still exist on the organizers calendar.
## (Example B.4 in RFC6638)
for inbox_item in organizer.principal.schedule_inbox.get_items():
    if inbox_item.is_invite():
        inbox_item.accept_invite()
    elif inbox_item.is_reply():
        inbox_item.delete()

## RFC6638/RFC5546 allows an organizer to check the freebusy status of
## multiple principals identified by email address.  It's covered in
## section 4.3.2. in RFC5546 and chapter 5 / example B.5 in RFC6638.
## Most of the logic is on the icalendar format (covered in RFC5546),
## and is a bit outside the scope of the caldav client library.
## However, I will probably make a convenience method for doing the
## query, and leaving the parsing of the returned icalendar data to
## the user of the library:
some_ical_returned = organizer.principal.freebusy_request(
    start_time=datetime.now() + timedelta(days=3999),
    end_time=datetime.now() + timedelta(days=4001),
    participants=[
        ('Test User 2', 't-caldav-test2@tobixen.no'),
        ('Test User 3', 't-caldav-test3@tobixen.no')])

## Examples in RFC6638 goes on to describing how to accept and decline
## particular instances of a recurring events, and RFC5546 has a lot
## of extra information, like ways for a participant to signal back
## new suggestions for the meeting time, delegations, cancelling of
## events and whatnot.  It is possible to use the library for such
## things by saving appropriate icalendar data to the outbox and
## reading things from the inbox, but as for now there aren't any
## planned convenience methods for covering such things.
