#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
Tests for async CalDAV client functionality.
"""
import pytest
from unittest import mock

from caldav.async_davclient import AsyncDAVClient, AsyncDAVResponse
from caldav.lib import error


class TestAsyncDAVClient:
    """Basic tests for AsyncDAVClient"""

    @pytest.mark.asyncio
    async def testInit(self):
        """Test AsyncDAVClient initialization"""
        client = AsyncDAVClient(url="http://calendar.example.com/")
        assert client.url.hostname == "calendar.example.com"
        await client.close()

    @pytest.mark.asyncio
    async def testContextManager(self):
        """Test async context manager"""
        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            assert client.url.hostname == "calendar.example.com"

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testRequestNonAscii(self, mocked):
        """Test async request with non-ASCII content"""
        mocked.return_value = mock.MagicMock()
        mocked.return_value.status_code = 200
        mocked.return_value.headers = {}
        mocked.return_value.content = b""

        cal_url = "http://me:hunter2@calendar.møøh.example:80/"
        async with AsyncDAVClient(url=cal_url) as client:
            # This should not raise an exception
            await client.request("/")

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testRequestCustomHeaders(self, mocked):
        """Test async request with custom headers"""
        mocked.return_value = mock.MagicMock()
        mocked.return_value.status_code = 200
        mocked.return_value.headers = {}
        mocked.return_value.content = b""

        cal_url = "http://me:hunter2@calendar.example.com/"
        async with AsyncDAVClient(
            url=cal_url,
            headers={"X-NC-CalDAV-Webcal-Caching": "On", "User-Agent": "MyAsyncApp"},
        ) as client:
            assert client.headers["Content-Type"] == "text/xml"
            assert client.headers["X-NC-CalDAV-Webcal-Caching"] == "On"
            assert client.headers["User-Agent"] == "MyAsyncApp"

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testPropfind(self, mocked):
        """Test async PROPFIND request"""
        mocked.return_value = mock.MagicMock()
        mocked.return_value.status_code = 207
        mocked.return_value.headers = {"Content-Type": "text/xml"}
        mocked.return_value.content = b"""<?xml version="1.0" encoding="utf-8"?>
<multistatus xmlns="DAV:">
  <response>
    <href>/calendars/user/</href>
    <propstat>
      <status>HTTP/1.1 200 OK</status>
      <prop>
        <displayname>My Calendar</displayname>
      </prop>
    </propstat>
  </response>
</multistatus>"""

        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            response = await client.propfind("/calendars/user/", depth=0)
            assert response.status == 207

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testOptions(self, mocked):
        """Test async OPTIONS request"""
        mocked.return_value = mock.MagicMock()
        mocked.return_value.status_code = 200
        mocked.return_value.headers = {
            "DAV": "1, 2, 3, calendar-access",
            "Content-Length": "0",
        }
        mocked.return_value.content = b""

        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            response = await client.options("/")
            assert response.headers.get("DAV") == "1, 2, 3, calendar-access"

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testCheckCalDAVSupport(self, mocked):
        """Test async CalDAV support check"""
        mocked.return_value = mock.MagicMock()
        mocked.return_value.status_code = 200
        mocked.return_value.headers = {
            "DAV": "1, 2, 3, calendar-access",
            "Content-Length": "0",
        }
        mocked.return_value.content = b""

        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            # check_cdav_support will call check_dav_support which calls options
            # Since principal() is not implemented yet, it will use the fallback
            has_caldav = await client.check_cdav_support()
            assert has_caldav is True

    @pytest.mark.asyncio
    async def testPrincipalNotImplemented(self):
        """Test that principal() raises NotImplementedError (Phase 3 feature)"""
        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            with pytest.raises(NotImplementedError):
                await client.principal()

    @pytest.mark.asyncio
    async def testCalendarNotImplemented(self):
        """Test that calendar() raises NotImplementedError (Phase 3 feature)"""
        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            with pytest.raises(NotImplementedError):
                client.calendar()

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testAuthDigest(self, mocked):
        """Test async digest authentication"""
        # First request returns 401 with WWW-Authenticate header
        first_response = mock.MagicMock()
        first_response.status_code = 401
        first_response.headers = {"WWW-Authenticate": "Digest realm='test'"}
        first_response.content = b""

        # Second request succeeds
        second_response = mock.MagicMock()
        second_response.status_code = 200
        second_response.headers = {}
        second_response.content = b""

        mocked.side_effect = [first_response, second_response]

        async with AsyncDAVClient(
            url="http://calendar.example.com/",
            username="testuser",
            password="testpass",
        ) as client:
            response = await client.request("/")
            assert response.status == 200
            # Should have made 2 requests (first failed, second with auth)
            assert mocked.call_count == 2

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testAuthBasic(self, mocked):
        """Test async basic authentication"""
        # First request returns 401
        first_response = mock.MagicMock()
        first_response.status_code = 401
        first_response.headers = {"WWW-Authenticate": "Basic realm='test'"}
        first_response.content = b""

        # Second request succeeds
        second_response = mock.MagicMock()
        second_response.status_code = 200
        second_response.headers = {}
        second_response.content = b""

        mocked.side_effect = [first_response, second_response]

        async with AsyncDAVClient(
            url="http://calendar.example.com/",
            username="testuser",
            password="testpass",
        ) as client:
            response = await client.request("/")
            assert response.status == 200
            assert mocked.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
