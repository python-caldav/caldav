#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
Tests for async collection classes (AsyncPrincipal, AsyncCalendar, etc.)
"""
from unittest import mock

import pytest

from caldav.async_collection import AsyncCalendar
from caldav.async_collection import AsyncCalendarSet
from caldav.async_collection import AsyncPrincipal
from caldav.async_davclient import AsyncDAVClient
from caldav.async_objects import AsyncEvent
from caldav.async_objects import AsyncJournal
from caldav.async_objects import AsyncTodo


SAMPLE_EVENT_ICAL = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:test-event-123
DTSTART:20250120T100000Z
DTEND:20250120T110000Z
SUMMARY:Test Event
DESCRIPTION:This is a test event
END:VEVENT
END:VCALENDAR"""

SAMPLE_TODO_ICAL = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VTODO
UID:test-todo-456
SUMMARY:Test Todo
DESCRIPTION:This is a test todo
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""


class TestAsyncPrincipal:
    """Tests for AsyncPrincipal"""

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testPrincipalFromClient(self, mocked):
        """Test getting principal from client"""
        # Mock OPTIONS response
        options_response = mock.MagicMock()
        options_response.status_code = 200
        options_response.headers = {"DAV": "1, 2, calendar-access"}
        options_response.content = b""

        # Mock PROPFIND response for current-user-principal
        propfind_response = mock.MagicMock()
        propfind_response.status_code = 207
        propfind_response.headers = {"Content-Type": "text/xml"}
        propfind_response.content = b"""<?xml version="1.0" encoding="utf-8"?>
<multistatus xmlns="DAV:">
  <response>
    <href>/</href>
    <propstat>
      <status>HTTP/1.1 200 OK</status>
      <prop>
        <current-user-principal>
          <href>/principals/user/</href>
        </current-user-principal>
      </prop>
    </propstat>
  </response>
</multistatus>"""

        mocked.side_effect = [propfind_response]

        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            principal = await client.principal()
            assert isinstance(principal, AsyncPrincipal)
            assert "principals/user" in str(principal.url)

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testPrincipalCalendars(self, mocked):
        """Test listing calendars from principal"""
        # Mock calendar-home-set PROPFIND
        chs_response = mock.MagicMock()
        chs_response.status_code = 207
        chs_response.headers = {"Content-Type": "text/xml"}
        chs_response.content = b"""<?xml version="1.0" encoding="utf-8"?>
<multistatus xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <response>
    <href>/principals/user/</href>
    <propstat>
      <status>HTTP/1.1 200 OK</status>
      <prop>
        <C:calendar-home-set>
          <href>/calendars/user/</href>
        </C:calendar-home-set>
      </prop>
    </propstat>
  </response>
</multistatus>"""

        # Mock calendars list PROPFIND
        calendars_response = mock.MagicMock()
        calendars_response.status_code = 207
        calendars_response.headers = {"Content-Type": "text/xml"}
        # Note: resourcetype should have elements inside, not as attributes
        calendars_response.content = b"""<?xml version="1.0" encoding="utf-8"?>
<multistatus xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <response>
    <href>/calendars/user/personal/</href>
    <propstat>
      <status>HTTP/1.1 200 OK</status>
      <prop>
        <resourcetype>
          <collection/>
          <C:calendar/>
        </resourcetype>
        <displayname>Personal Calendar</displayname>
      </prop>
    </propstat>
  </response>
  <response>
    <href>/calendars/user/work/</href>
    <propstat>
      <status>HTTP/1.1 200 OK</status>
      <prop>
        <resourcetype>
          <collection/>
          <C:calendar/>
        </resourcetype>
        <displayname>Work Calendar</displayname>
      </prop>
    </propstat>
  </response>
</multistatus>"""

        mocked.side_effect = [chs_response, calendars_response]

        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            principal = AsyncPrincipal(client=client, url="/principals/user/")
            calendars = await principal.calendars()

            assert len(calendars) == 2
            assert all(isinstance(cal, AsyncCalendar) for cal in calendars)
            assert calendars[0].name == "Personal Calendar"
            assert calendars[1].name == "Work Calendar"


class TestAsyncCalendar:
    """Tests for AsyncCalendar"""

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testCalendarEvents(self, mocked):
        """Test listing events from calendar"""
        # Mock calendar-query REPORT response
        report_response = mock.MagicMock()
        report_response.status_code = 207
        report_response.headers = {"Content-Type": "text/xml"}
        report_response.content = f"""<?xml version="1.0" encoding="utf-8"?>
<multistatus xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <response>
    <href>/calendars/user/personal/event1.ics</href>
    <propstat>
      <status>HTTP/1.1 200 OK</status>
      <prop>
        <C:calendar-data>{SAMPLE_EVENT_ICAL}</C:calendar-data>
      </prop>
    </propstat>
  </response>
</multistatus>""".encode()

        mocked.return_value = report_response

        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            calendar = AsyncCalendar(client=client, url="/calendars/user/personal/")
            events = await calendar.events()

            assert len(events) == 1
            assert isinstance(events[0], AsyncEvent)
            assert events[0].data == SAMPLE_EVENT_ICAL
            assert "/calendars/user/personal/event1.ics" in str(events[0].url)

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testCalendarTodos(self, mocked):
        """Test listing todos from calendar"""
        # Mock calendar-query REPORT response
        report_response = mock.MagicMock()
        report_response.status_code = 207
        report_response.headers = {"Content-Type": "text/xml"}
        report_response.content = f"""<?xml version="1.0" encoding="utf-8"?>
<multistatus xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <response>
    <href>/calendars/user/personal/todo1.ics</href>
    <propstat>
      <status>HTTP/1.1 200 OK</status>
      <prop>
        <C:calendar-data>{SAMPLE_TODO_ICAL}</C:calendar-data>
      </prop>
    </propstat>
  </response>
</multistatus>""".encode()

        mocked.return_value = report_response

        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            calendar = AsyncCalendar(client=client, url="/calendars/user/personal/")
            todos = await calendar.todos()

            assert len(todos) == 1
            assert isinstance(todos[0], AsyncTodo)
            assert todos[0].data == SAMPLE_TODO_ICAL


class TestAsyncEvent:
    """Tests for AsyncEvent"""

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testEventSave(self, mocked):
        """Test saving an event"""
        # Mock PUT response
        put_response = mock.MagicMock()
        put_response.status_code = 201
        put_response.headers = {}
        put_response.content = b""

        mocked.return_value = put_response

        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            calendar = AsyncCalendar(client=client, url="/calendars/user/personal/")
            event = AsyncEvent(
                client=client,
                parent=calendar,
                data=SAMPLE_EVENT_ICAL,
                id="test-event-123",
            )

            await event.save()

            # Verify PUT was called
            mocked.assert_called_once()
            call_args = mocked.call_args
            # Check positional or keyword args
            if call_args[0]:  # Positional args
                assert call_args[0][0] == "PUT"
                assert "test-event-123.ics" in call_args[0][1]
            else:  # Keyword args
                assert call_args[1]["method"] == "PUT"
                assert "test-event-123.ics" in call_args[1]["url"]
                assert call_args[1]["content"] == SAMPLE_EVENT_ICAL.encode()

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testEventLoad(self, mocked):
        """Test loading an event"""
        # Mock GET response
        get_response = mock.MagicMock()
        get_response.status_code = 200
        get_response.headers = {"Content-Type": "text/calendar"}
        get_response.content = SAMPLE_EVENT_ICAL.encode()

        mocked.return_value = get_response

        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            event = AsyncEvent(client=client, url="/calendars/user/personal/event1.ics")

            await event.load()

            assert event.data == SAMPLE_EVENT_ICAL
            mocked.assert_called_once()
            call_args = mocked.call_args
            # Check positional or keyword args
            if call_args[0] and len(call_args[0]) > 0:
                assert "GET" in str(call_args) or call_args[0][0] == "GET"
            else:
                assert call_args[1].get("method") == "GET" or "GET" in str(call_args)

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testEventDelete(self, mocked):
        """Test deleting an event"""
        # Mock DELETE response
        delete_response = mock.MagicMock()
        delete_response.status_code = 204
        delete_response.headers = {}
        delete_response.content = b""

        mocked.return_value = delete_response

        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            event = AsyncEvent(
                client=client,
                url="/calendars/user/personal/event1.ics",
                data=SAMPLE_EVENT_ICAL,
            )

            await event.delete()

            mocked.assert_called_once()
            call_args = mocked.call_args
            # Check that DELETE was called
            assert "DELETE" in str(call_args) or (
                call_args[0] and call_args[0][0] == "DELETE"
            )


class TestAsyncTodo:
    """Tests for AsyncTodo"""

    @pytest.mark.asyncio
    @mock.patch("caldav.async_davclient.httpx.AsyncClient.request")
    async def testTodoSave(self, mocked):
        """Test saving a todo"""
        # Mock PUT response
        put_response = mock.MagicMock()
        put_response.status_code = 201
        put_response.headers = {}
        put_response.content = b""

        mocked.return_value = put_response

        async with AsyncDAVClient(url="http://calendar.example.com/") as client:
            calendar = AsyncCalendar(client=client, url="/calendars/user/tasks/")
            todo = AsyncTodo(
                client=client,
                parent=calendar,
                data=SAMPLE_TODO_ICAL,
                id="test-todo-456",
            )

            await todo.save()

            # Verify PUT was called
            mocked.assert_called_once()
            call_args = mocked.call_args
            # Check that PUT was called with the right URL
            assert "PUT" in str(call_args)
            assert "test-todo-456.ics" in str(call_args)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
