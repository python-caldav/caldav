import sys
import uuid
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from icalendar import Calendar
from icalendar import Event

from caldav import DAVClient
from caldav import error


###############
### SETUP START
### rfc6638_users should be a list with three dicts containing credential details.
### if none is given, attempt to use three test users on tobixens private calendar
###
try:
    from tests.conf_private import rfc6638_users
except:
    rfc6638_users = None


## Some initial setup.  We'll need three caldav client objects, with
## corresponding principal objects and calendars.
class TestUser:
    def __init__(self, i):
        if rfc6638_users and len(rfc6638_users) > i - 1:
            conndata = rfc6638_users[i - 1].copy()
            if "incompatibilities" in conndata:
                conndata.pop("incompatibilities")
            self.client = DAVClient(**conndata)
        else:
            self.client = DAVClient(
                username="testuser%i" % i,
                password="testpass%i" % i,
                url="http://calendar.tobixen.no/caldav.php/",
            )
        self.principal = self.client.principal()
        calendar_id = "schedulingtestcalendar%i" % i
        calendar_name = "calendar #%i for scheduling demo" % i
        self.cleanup(calendar_name)
        self.calendar = self.principal.make_calendar(
            name=calendar_name, cal_id=calendar_id
        )

    def cleanup(self, calendar_name):
        ## Cleanup from earlier runs
        try:
            self.calendar = self.principal.calendar(name=calendar_name)
            self.calendar.delete()
        except error.NotFoundError:
            pass

        ## Hmm ... perhaps we shouldn't delete inbox items
        # for inbox_item in self.principal.schedule_inbox().get_items():
        # inbox_item.delete()


organizer = TestUser(1)
attendee1 = TestUser(2)
attendee2 = TestUser(3)

### SETUP  END
###############

## Verify that the calendar server(s) supports scheduling
for test_user in organizer, attendee1, attendee2:
    if not test_user.client.check_scheduling_support():
        print("Server does not support RFC6638")
        sys.exit(1)

## We'll be using the icalendar library to set up a mock meeting,
## at some far point in the future.
caldata = Calendar()
caldata.add("prodid", "-//tobixen//python-icalendar//en_DK")
caldata.add("version", "2.0")

uid = uuid.uuid1()
event = Event()
event.add("dtstamp", datetime.now())
event.add("dtstart", datetime.now() + timedelta(days=4000))
event.add("dtend", datetime.now() + timedelta(days=4000, hours=1))
event.add("uid", uid)
event.add("summary", "Some test event made to test scheduling in the caldav library")
caldata.add_component(event)

caldata2 = Calendar()
caldata2.add("prodid", "-//tobixen//python-icalendar//en_DK")
caldata2.add("version", "2.0")

uid = uuid.uuid1()
event = Event()
event.add("dtstamp", datetime.now())
event.add("dtstart", datetime.now() + timedelta(days=4000))
event.add("dtend", datetime.now() + timedelta(days=4000, hours=1))
event.add("uid", uid)
event.add("summary", "Test event with participants but without invites")
caldata2.add_component(event)


## that event is without any attendee information.  If saved to the
## calendar, it will only be stored locally, no invitations sent.

## There are two ways to send calendar invites:

## * Add Attendee-lines and an Organizer-line to the event data, and
##   then use calendar.save_event(caldata) ... see RFC6638, appendix B.1
##   for an example.

## * Use convenience-method calendar.save_with_invites(caldata, attendees).
##   It will fetch organizer from the principal object.  Method should
##   accept different kind of attendees: strings, VCalAddress, (cn,
##   email)-tuple and principal object.

## Lets make a list of attendees
attendees = []

## The organizer will invite himself.  We'll pass a vCalAddress (from
## the icalendar library).
attendees.append(organizer.principal.get_vcal_address())

## Let's make it easy and add the other attendees by the Principal objects.
## note that we've used login credentials to get the principal
## objects below.  One would normally need to know the principal
## URLs to create principal objects of other users, or perhaps use
## the principal-collection-set prop to get a list.
attendees.append(attendee1.principal)
attendees.append(attendee2.principal)

## An attendee can also be added by email address
attendees.append("some-random-guy@example.com")

## Or by a (common_name, email) tuple
attendees.append(("Some Other Random Guy", "some-other-random-guy@example.com"))

print("Sending a calendar invite")
organizer.calendar.save_with_invites(caldata, attendees=attendees)

print(
    "Storing another calendar event with the same participants, but without sending out emails"
)
organizer.calendar.save_with_invites(
    caldata2, attendees=attendees, schedule_agent="NONE"
)

## There are some attendee parameters that may be set (TODO: add
## example code), the convenience method above will use sensible
## defaults.

## The invite has now been shipped.  The attendees should now respond to it.

print("looking into the inbox of attendee1")
all_cnt = 0
invite_req_cnt = 0
for inbox_item in attendee1.principal.schedule_inbox().get_items():
    all_cnt += 1
    ## an inbox_item is an ordinary CalendarResourceObject/Event/Todo etc.
    ## is_invite_request will be implemented on the base class and will yield True
    ## for invite messages.
    print("Inbox item found for attendee1.  Here is the ical:")
    print(inbox_item.data)

    if inbox_item.is_invite_request():
        print("Inbox item is an invite request")
        invite_req_cnt += 1  ## TODO: assert(invite_req_cnt == 1) after loop

        ## Ref RFC6638, example B.3 ... to respond to an invite, it's
        ## needed to edit the ical data, find the correct
        ## "attendee"-field, change the attendee "partstat", put the
        ## ical object back to the server.  In addition one has to
        ## look out for race conflicts and retry the whole operation
        ## in case of race conflicts.  Editing ical data is a bit
        ## outside the scope of the CalDAV client library, but ... the
        ## library clearly needs convenience methods to deal with this.

        ## Invite objects will have methods accept_invite(),
        ## decline_invite(),
        ## tentatively_accept_invite().  .delete() is also an option
        ## (ref RFC6638, example B.2)
        inbox_item.accept_invite()
        inbox_item.delete()

## attendee2 has other long-term plans and can't join the event
for inbox_item in attendee2.principal.schedule_inbox().get_items():
    print("found an inbox item for attendee 2, here is the ical:")
    print(inbox_item.data)
    if inbox_item.is_invite_request():
        print("declining invite")
        inbox_item.decline_invite()
        inbox_item.delete()

## Oganizer will have an update on the participant status in the
## inbox (or perhaps two updates?)  If I've understood the standard
## correctly, testuser0 should not get an invite and should not have
## to respond to it, but just in case we'll accept it.  As far as I've
## understood, deleting the ical objects in the inbox should be
## harmless, it should still exist on the organizers calendar.
## (Example B.4 in RFC6638)
print("looking into organizers inbox")
for inbox_item in organizer.principal.schedule_inbox().get_items():
    print("Inbox item found, here is the ical:")
    print(inbox_item.data)
    if inbox_item.is_invite_request():
        print("It's an invite request, let's accept it")
        inbox_item.accept_invite()
    elif inbox_item.is_invite_reply():
        print("It's an invite reply, now that we've read it, we can delete it")
        inbox_item.delete()

## RFC6638/RFC5546 allows an organizer to check the freebusy status of
## multiple principals identified by email address.  It's covered in
## section 4.3.2. in RFC5546 and chapter 5 / example B.5 in RFC6638.
## Most of the logic is on the icalendar format (covered in RFC5546),
## and is a bit outside the scope of the caldav client library.
## However, I will probably make a convenience method for doing the
## query, and leaving the parsing of the returned icalendar data to
## the user of the library:
import pdb

pdb.set_trace()
some_data_returned = organizer.principal.freebusy_request(
    dtstart=datetime.now().astimezone(timezone.utc) + timedelta(days=399),
    dtend=datetime.now().astimezone(timezone.utc) + timedelta(days=399, hours=1),
    attendees=[attendee1.principal, attendee2.principal],
)

## Examples in RFC6638 goes on to describing how to accept and decline
## particular instances of a recurring events, and RFC5546 has a lot
## of extra information, like ways for a participant to signal back
## new suggestions for the meeting time, delegations, cancelling of
## events and whatnot.  It is possible to use the library for such
## things by saving appropriate icalendar data to the outbox and
## reading things from the inbox, but as for now there aren't any
## planned convenience methods for covering such things.
