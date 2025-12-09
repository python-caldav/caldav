"""
This code was provided by Bo Lopker in https://github.com/python-caldav/caldav/issues/311#issuecomment-1648524837

The code has not been tested by the caldav maintainer
"""
import json

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from requests.auth import AuthBase

from caldav.davclient import get_davclient


SERVICE_ACCOUNT_FILE = "service.json"


class OAuth(AuthBase):
    def __init__(self, credentials):
        self.credentials = credentials

    def __call__(self, r):
        self.credentials.apply(r.headers)
        return r


SCOPES = ["https://www.googleapis.com/auth/calendar"]

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
creds.refresh(Request())

calid = "{ID}@group.calendar.google.com"
url = "https://apidata.googleusercontent.com/caldav/v2/" + calid + "/events"

client = get_davclient(url, auth=OAuth(creds))

for calendar in client.principal().calendars():
    events = calendar.events()
    for event in events:
        ## Comment from caldav maintainer: this usage of vobject works out as
        ## long as there are only events (and no tasks) on the calendar and
        ## as long as there aren't complex recurrence objects on the calendar.
        e = event.instance.vevent
        eventTime = e.dtstart.value.strftime("%c")
        eventSummary = e.summary.value
        print("==================================")
        print(f"Event:    {eventSummary}")
        print(f"Time:     {eventTime}")

## The key here is that you get the oauth token (creds.token) by calling refresh on creds before you make the caldav client. You can store the result of the refresh to make the process a bit faster.

##creds = service_account.Credentials.from_service_account_file(
##    SERVICE_ACCOUNT_FILE, scopes=SCOPES
##)
##creds.refresh(Request())
