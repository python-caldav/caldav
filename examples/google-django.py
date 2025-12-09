"""
Contributed by Abe Hanoka in https://github.com/python-caldav/caldav/issues/119#issuecomment-2652650972

> I got this working using django-allauth. Here's a minimal working example that demonstrates how to connect to Google Calendar via CalDAV using OAuth tokens from django-allauth"

> Make sure your Google OAuth configuration includes the CalDAV scope: https://www.googleapis.com/auth/calendar

> This approach lets you leverage django-allauth's token management while using caldav for actual calendar operations. The calendar URL format is https://apidata.googleusercontent.com/caldav/v2/{calendar_id}/events.

> For the allauth setup, I followed this guide: https://stackoverflow.com/questions/51575127/use-google-api-with-a-token-django-allauth

This code is not tested by the caldav library maintainer.
"""
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.models import SocialToken
from google.oauth2.credentials import Credentials

from caldav.davclient import get_davclient
from caldav.requests import HTTPBearerAuth


def get_google_credentials(user):
    """Get Google OAuth2 credentials from django-allauth"""
    token = SocialToken.objects.filter(
        account__user=user,
        account__provider="google",
    ).first()

    if not token:
        raise Exception("No Google account connected")

    google = SocialApp.objects.get(provider="google")
    return Credentials(
        token=token.token,
        refresh_token=token.token_secret,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=google.client_id,
        client_secret=google.secret,
    )


def sync_calendar(user, calendar_id):
    """Sync with Google Calendar using CalDAV"""
    # Get credentials from django-allauth
    credentials = get_google_credentials(user)

    # Set up CalDAV client with OAuth token
    client = get_davclient(
        url=f"https://apidata.googleusercontent.com/caldav/v2/{calendar_id}/events",
        auth=HTTPBearerAuth(credentials.token),
    )

    # Access calendar
    principal = client.principal()
    calendar = principal.calendars()[0]

    # Now you can work with events
    events = calendar.events()
    # ...etc
