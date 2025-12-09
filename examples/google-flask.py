#!/usr/bin/env python3
"""
Code contributed by github user seidnerj in
https://github.com/python-caldav/caldav/issues/119#issuecomment-2561980368

This code has not been tested by the maintainer of the caldav library.
"""
import os

from flask import Flask
from flask import jsonify
from flask import Response
from google.oauth2.credentials import Credentials

from caldav.davclient import get_davclient
from caldav.requests import HTTPBearerAuth


app = Flask(__name__)

# Constants
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
CALDAV_URL_TEMPLATE = (
    "https://apidata.googleusercontent.com/caldav/v2/{calendar_id}/user"
)

# Cache to store calendar summaries and IDs
CALENDAR_CACHE = {}


def get_google_credentials():
    """
    Load or refresh Google OAuth2 credentials.
    """

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE)
    else:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE, scopes=["https://www.googleapis.com/auth/calendar"]
        )
        creds = flow.run_local_server(port=0)

        # save credentials for future use
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def get_calendar_list():
    """
    Fetch the list of calendars and store them in the cache.
    """

    creds = get_google_credentials()
    from googleapiclient.discovery import build

    service = build("calendar", "v3", credentials=creds)

    calendars = service.calendarList().list().execute()
    for calendar in calendars.get("items", []):
        CALENDAR_CACHE[calendar["summary"]] = calendar["id"]


@app.route("/calendars", methods=["GET"])
def list_calendars():
    """
    Endpoint to list all available calendars.
    """
    if not CALENDAR_CACHE:
        get_calendar_list()

    return jsonify({"calendars": list(CALENDAR_CACHE.keys())})


@app.route("/calendar/<calendar_name>.ics", methods=["GET"])
def serve_calendar_ics(calendar_name):
    """
    Endpoint to serve .ics data for a specific calendar.
    """
    if calendar_name not in CALENDAR_CACHE:
        return jsonify({"error": "Calendar not found"}), 404

    calendar_id = CALENDAR_CACHE[calendar_name]
    creds = get_google_credentials()
    access_token = creds.token

    try:
        calendar_url = CALDAV_URL_TEMPLATE.format(calendar_id=calendar_id)

        # connect to the calendar using CalDAV
        client = get_davclient(url=calendar_url, auth=HTTPBearerAuth(access_token))
        principal = client.principal()
        calendars = principal.calendars()

        # fetch events from the first calendar (usually the only one)
        calendar = calendars[0]
        ics_data = ""
        for event in calendar.events():
            ics_data += event.data

        # serve the calendar as an ICS file
        return Response(ics_data, mimetype="text/calendar")
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


# requirements: flask, caldav, google-auth, google-auth-oauthlib, google-api-python-client
if __name__ == "__main__":
    # preload calendar list on server start
    get_calendar_list()
    app.run(host="0.0.0.0", port=5000)
