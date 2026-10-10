"""
Mocked PROPFIND responses shared by the sync and async unit tests of
calendar discovery on servers without a calendar-home-set.
"""

from urllib.parse import urlparse

## Nextcloud public calendar share: the client URL is the calendar itself, the
## principal is a system principal without calendars and without a
## calendar-home-set.
PUBLIC_SHARE_URL = "https://nc.example.com/remote.php/dav/public-calendars/ABC123"
PUBLIC_SHARE_PRINCIPAL_URL = "https://nc.example.com/remote.php/dav/principals/system/public/"

PUBLIC_SHARE_PRINCIPAL_DEPTH0_XML = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/remote.php/dav/principals/system/public/</d:href>
    <d:propstat>
      <d:prop><cal:calendar-home-set/></d:prop>
      <d:status>HTTP/1.1 404 Not Found</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""

PUBLIC_SHARE_PRINCIPAL_DEPTH1_XML = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/remote.php/dav/principals/system/public/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:principal/></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""

PUBLIC_SHARE_CALENDAR_DEPTH1_XML = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/remote.php/dav/public-calendars/ABC123/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/><cal:calendar/></d:resourcetype>
        <d:displayname>Personal (alice)</d:displayname>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/public-calendars/ABC123/event1.ics</d:href>
    <d:propstat>
      <d:prop><d:resourcetype/></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""

## GMX-like server: no calendar-home-set, calendars live below the principal.
GMX_LIKE_PRINCIPAL_DEPTH1_XML = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/remote.php/dav/principals/system/public/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:principal/></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/principals/system/public/work/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/><cal:calendar/></d:resourcetype>
        <d:displayname>Work</d:displayname>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""


def public_share_propfind_xml(url, depth, principal_depth1_xml=PUBLIC_SHARE_PRINCIPAL_DEPTH1_XML):
    """Return the mocked PROPFIND body for a URL and depth on a public share server."""
    path = urlparse(str(url)).path.rstrip("/")
    if path == urlparse(PUBLIC_SHARE_PRINCIPAL_URL).path.rstrip("/"):
        return PUBLIC_SHARE_PRINCIPAL_DEPTH0_XML if depth == "0" else principal_depth1_xml
    if path == urlparse(PUBLIC_SHARE_URL).path.rstrip("/") and depth == "1":
        return PUBLIC_SHARE_CALENDAR_DEPTH1_XML
    raise AssertionError(f"unexpected PROPFIND {url} depth {depth}")
