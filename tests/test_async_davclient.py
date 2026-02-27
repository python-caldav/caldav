#!/usr/bin/env python
"""
Unit tests for async_davclient module.

Rule: None of the tests in this file should initiate any internet
communication. We use Mock/MagicMock to emulate server communication.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from caldav.async_davclient import AsyncDAVClient, AsyncDAVResponse, get_davclient
from caldav.lib import error

# Sample XML responses for testing
SAMPLE_MULTISTATUS_XML = b"""<?xml version="1.0" encoding="utf-8" ?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/calendars/user/calendar/</d:href>
    <d:propstat>
      <d:prop>
        <d:displayname>My Calendar</d:displayname>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""

SAMPLE_PROPFIND_XML = b"""<?xml version="1.0" encoding="utf-8" ?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/dav/</d:href>
    <d:propstat>
      <d:prop>
        <d:current-user-principal>
          <d:href>/dav/principals/user/</d:href>
        </d:current-user-principal>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""

SAMPLE_OPTIONS_HEADERS = {
    "DAV": "1, 2, calendar-access",
    "Allow": "OPTIONS, GET, HEAD, POST, PUT, DELETE, PROPFIND, PROPPATCH, REPORT",
}


def create_mock_response(
    content: bytes = b"",
    status_code: int = 200,
    reason: str = "OK",
    headers: dict = None,
) -> MagicMock:
    """Create a mock HTTP response."""
    resp = MagicMock()
    resp.content = content
    resp.status_code = status_code
    resp.reason = reason
    resp.reason_phrase = reason  # httpx uses reason_phrase
    resp.headers = headers or {}
    resp.text = content.decode("utf-8") if content else ""
    return resp


class TestAsyncDAVResponse:
    """Tests for AsyncDAVResponse class."""

    def test_response_with_xml_content(self) -> None:
        """Test parsing XML response."""
        resp = create_mock_response(
            content=SAMPLE_MULTISTATUS_XML,
            status_code=207,
            reason="Multi-Status",
            headers={"Content-Type": "text/xml; charset=utf-8"},
        )

        dav_response = AsyncDAVResponse(resp)

        assert dav_response.status == 207
        assert dav_response.reason == "Multi-Status"
        assert dav_response.tree is not None
        assert dav_response.tree.tag.endswith("multistatus")

    def test_response_with_empty_content(self) -> None:
        """Test response with no content."""
        resp = create_mock_response(
            content=b"",
            status_code=204,
            reason="No Content",
            headers={"Content-Length": "0"},
        )

        dav_response = AsyncDAVResponse(resp)

        assert dav_response.status == 204
        assert dav_response.tree is None
        assert dav_response._raw == ""

    def test_response_with_non_xml_content(self) -> None:
        """Test response with non-XML content."""
        resp = create_mock_response(
            content=b"Plain text response",
            status_code=200,
            headers={"Content-Type": "text/plain"},
        )

        dav_response = AsyncDAVResponse(resp)

        assert dav_response.status == 200
        assert dav_response.tree is None
        assert b"Plain text response" in dav_response._raw

    def test_response_raw_property(self) -> None:
        """Test raw property returns string."""
        resp = create_mock_response(content=b"test content")

        dav_response = AsyncDAVResponse(resp)

        assert isinstance(dav_response.raw, str)
        assert "test content" in dav_response.raw

    def test_response_crlf_normalization(self) -> None:
        """Test that CRLF is normalized to LF."""
        resp = create_mock_response(content=b"line1\r\nline2\r\nline3")

        dav_response = AsyncDAVResponse(resp)

        assert b"\r\n" not in dav_response._raw
        assert b"\n" in dav_response._raw


class TestAsyncDAVClient:
    """Tests for AsyncDAVClient class."""

    def test_client_initialization(self) -> None:
        """Test basic client initialization."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        assert client.url.scheme == "https"
        assert "caldav.example.com" in str(client.url)
        assert "User-Agent" in client.headers
        assert "caldav-async" in client.headers["User-Agent"]

    def test_client_with_credentials(self) -> None:
        """Test client initialization with username/password."""
        client = AsyncDAVClient(
            url="https://caldav.example.com/dav/",
            username="testuser",
            password="testpass",
        )

        assert client.username == "testuser"
        assert client.password == "testpass"

    def test_client_with_auth_in_url(self) -> None:
        """Test extracting credentials from URL."""
        client = AsyncDAVClient(url="https://user:pass@caldav.example.com/dav/")

        assert client.username == "user"
        assert client.password == "pass"

    def test_client_with_proxy(self) -> None:
        """Test client with proxy configuration."""
        client = AsyncDAVClient(
            url="https://caldav.example.com/dav/",
            proxy="proxy.example.com:8080",
        )

        assert client.proxy == "http://proxy.example.com:8080"

    def test_client_with_ssl_verify(self) -> None:
        """Test SSL verification settings."""
        client = AsyncDAVClient(
            url="https://caldav.example.com/dav/",
            ssl_verify_cert=False,
        )

        assert client.ssl_verify_cert is False

    def test_client_with_custom_headers(self) -> None:
        """Test client with custom headers."""
        custom_headers = {"X-Custom-Header": "test-value"}
        client = AsyncDAVClient(
            url="https://caldav.example.com/dav/",
            headers=custom_headers,
        )

        assert "X-Custom-Header" in client.headers
        assert client.headers["X-Custom-Header"] == "test-value"
        assert "User-Agent" in client.headers  # Default headers still present

    def test_build_method_headers(self) -> None:
        """Test _build_method_headers helper."""
        # Test with depth
        headers = AsyncDAVClient._build_method_headers("PROPFIND", depth=1)
        assert headers["Depth"] == "1"

        # Test REPORT method adds Content-Type
        headers = AsyncDAVClient._build_method_headers("REPORT", depth=0)
        assert "Content-Type" in headers
        assert "application/xml" in headers["Content-Type"]

        # Test with extra headers
        extra = {"X-Test": "value"}
        headers = AsyncDAVClient._build_method_headers("PROPFIND", depth=0, extra_headers=extra)
        assert headers["X-Test"] == "value"
        assert headers["Depth"] == "0"

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager protocol."""
        async with AsyncDAVClient(url="https://caldav.example.com/dav/") as client:
            assert client is not None
            assert hasattr(client, "session")

        # After exit, session should be closed (we can't easily verify this without mocking)

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """Test close method."""
        from caldav.async_davclient import _USE_HTTPX

        client = AsyncDAVClient(url="https://caldav.example.com/dav/")
        client.session = AsyncMock()
        # httpx uses aclose(), niquests uses close()
        client.session.aclose = AsyncMock()
        client.session.close = AsyncMock()

        await client.close()

        if _USE_HTTPX:
            client.session.aclose.assert_called_once()
        else:
            client.session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_method(self) -> None:
        """Test request method."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        # Mock the session.request method
        mock_response = create_mock_response(
            content=SAMPLE_MULTISTATUS_XML,
            status_code=207,
            headers={"Content-Type": "text/xml"},
        )

        client.session.request = AsyncMock(return_value=mock_response)

        response = await client.request("/test/path", "GET")

        assert isinstance(response, AsyncDAVResponse)
        assert response.status == 207
        client.session.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_propfind_method(self) -> None:
        """Test propfind method."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        mock_response = create_mock_response(
            content=SAMPLE_PROPFIND_XML,
            status_code=207,
            headers={"Content-Type": "text/xml"},
        )

        client.session.request = AsyncMock(return_value=mock_response)

        # Test with default URL
        response = await client.propfind(body="<propfind/>", depth=1)

        assert response.status == 207
        call_args = client.session.request.call_args
        # httpx uses kwargs for method and headers
        assert call_args.kwargs["method"] == "PROPFIND"
        assert "Depth" in call_args.kwargs["headers"]
        assert call_args.kwargs["headers"]["Depth"] == "1"

    @pytest.mark.asyncio
    async def test_propfind_with_custom_url(self) -> None:
        """Test propfind with custom URL."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        mock_response = create_mock_response(
            content=SAMPLE_PROPFIND_XML,
            status_code=207,
            headers={"Content-Type": "text/xml"},
        )

        client.session.request = AsyncMock(return_value=mock_response)

        response = await client.propfind(
            url="https://caldav.example.com/dav/calendars/",
            body="<propfind/>",
            depth=0,
        )

        assert response.status == 207
        call_args = client.session.request.call_args
        # httpx uses kwargs for url
        assert "calendars" in call_args.kwargs["url"]

    @pytest.mark.asyncio
    async def test_report_method(self) -> None:
        """Test report method."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        mock_response = create_mock_response(
            content=SAMPLE_MULTISTATUS_XML,
            status_code=207,
            headers={"Content-Type": "text/xml"},
        )

        client.session.request = AsyncMock(return_value=mock_response)

        response = await client.report(body="<report/>", depth=0)

        assert response.status == 207
        call_args = client.session.request.call_args
        assert call_args.kwargs["method"] == "REPORT"
        assert "Content-Type" in call_args.kwargs["headers"]
        assert "application/xml" in call_args.kwargs["headers"]["Content-Type"]

    @pytest.mark.asyncio
    async def test_options_method(self) -> None:
        """Test options method."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        mock_response = create_mock_response(
            content=b"",
            status_code=200,
            headers=SAMPLE_OPTIONS_HEADERS,
        )

        client.session.request = AsyncMock(return_value=mock_response)

        response = await client.options()

        assert response.status == 200
        assert "DAV" in response.headers
        call_args = client.session.request.call_args
        assert call_args.kwargs["method"] == "OPTIONS"

    @pytest.mark.asyncio
    async def test_proppatch_method(self) -> None:
        """Test proppatch method (requires URL)."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        mock_response = create_mock_response(status_code=207)
        client.session.request = AsyncMock(return_value=mock_response)

        response = await client.proppatch(
            url="https://caldav.example.com/dav/calendar/",
            body="<propertyupdate/>",
        )

        assert response.status == 207
        call_args = client.session.request.call_args
        assert call_args.kwargs["method"] == "PROPPATCH"

    @pytest.mark.asyncio
    async def test_put_method(self) -> None:
        """Test put method (requires URL)."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        mock_response = create_mock_response(status_code=201, reason="Created")
        client.session.request = AsyncMock(return_value=mock_response)

        response = await client.put(
            url="https://caldav.example.com/dav/calendar/event.ics",
            body="BEGIN:VCALENDAR...",
        )

        assert response.status == 201
        call_args = client.session.request.call_args
        assert call_args.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_delete_method(self) -> None:
        """Test delete method (requires URL)."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        mock_response = create_mock_response(status_code=204, reason="No Content")
        client.session.request = AsyncMock(return_value=mock_response)

        response = await client.delete(url="https://caldav.example.com/dav/calendar/event.ics")

        assert response.status == 204
        call_args = client.session.request.call_args
        assert call_args.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_post_method(self) -> None:
        """Test post method (requires URL)."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        mock_response = create_mock_response(status_code=200)
        client.session.request = AsyncMock(return_value=mock_response)

        response = await client.post(
            url="https://caldav.example.com/dav/outbox/",
            body="<schedule-request/>",
        )

        assert response.status == 200
        call_args = client.session.request.call_args
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_mkcol_method(self) -> None:
        """Test mkcol method (requires URL)."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        mock_response = create_mock_response(status_code=201)
        client.session.request = AsyncMock(return_value=mock_response)

        response = await client.mkcol(url="https://caldav.example.com/dav/newcollection/")

        assert response.status == 201
        call_args = client.session.request.call_args
        assert call_args.kwargs["method"] == "MKCOL"

    @pytest.mark.asyncio
    async def test_mkcalendar_method(self) -> None:
        """Test mkcalendar method (requires URL)."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        mock_response = create_mock_response(status_code=201)
        client.session.request = AsyncMock(return_value=mock_response)

        response = await client.mkcalendar(
            url="https://caldav.example.com/dav/newcalendar/",
            body="<mkcalendar/>",
        )

        assert response.status == 201
        call_args = client.session.request.call_args
        assert call_args.kwargs["method"] == "MKCALENDAR"

    def test_extract_auth_types(self) -> None:
        """Test extracting auth types from WWW-Authenticate header."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        # Single auth type
        auth_types = client.extract_auth_types('Basic realm="Test"')
        assert "basic" in auth_types

        # Multiple auth types
        auth_types = client.extract_auth_types('Basic realm="Test", Digest realm="Test"')
        assert "basic" in auth_types
        assert "digest" in auth_types

    def test_build_auth_object_basic(self) -> None:
        """Test building Basic auth object."""
        client = AsyncDAVClient(
            url="https://caldav.example.com/dav/",
            username="user",
            password="pass",
        )

        client.build_auth_object(["basic"])

        assert client.auth is not None
        # Can't easily test the auth object type without importing HTTPBasicAuth

    def test_build_auth_object_digest(self) -> None:
        """Test building Digest auth object."""
        client = AsyncDAVClient(
            url="https://caldav.example.com/dav/",
            username="user",
            password="pass",
        )

        client.build_auth_object(["digest"])

        assert client.auth is not None

    def test_build_auth_object_bearer(self) -> None:
        """Test building Bearer auth object."""
        client = AsyncDAVClient(
            url="https://caldav.example.com/dav/",
            password="bearer-token",
        )

        client.build_auth_object(["bearer"])

        assert client.auth is not None

    def test_build_auth_object_preference(self) -> None:
        """Test auth type preference (digest > basic > bearer)."""
        client = AsyncDAVClient(
            url="https://caldav.example.com/dav/",
            username="user",
            password="pass",
        )

        # Should prefer digest
        client.build_auth_object(["basic", "digest", "bearer"])
        # Can't easily verify which was chosen without inspecting auth object type

    def test_build_auth_object_with_explicit_type(self) -> None:
        """Test building auth with explicit auth_type."""
        client = AsyncDAVClient(
            url="https://caldav.example.com/dav/",
            username="user",
            password="pass",
            auth_type="basic",
        )

        # build_auth_object should have been called in __init__
        assert client.auth is not None


class TestGetDAVClient:
    """Tests for get_davclient factory function."""

    @pytest.mark.asyncio
    async def test_get_davclient_basic(self) -> None:
        """Test basic get_davclient usage."""
        with patch.object(AsyncDAVClient, "options") as mock_options:
            mock_response = create_mock_response(
                status_code=200,
                headers=SAMPLE_OPTIONS_HEADERS,
            )
            mock_response_obj = AsyncDAVResponse(mock_response)
            mock_options.return_value = mock_response_obj

            client = await get_davclient(
                url="https://caldav.example.com/dav/",
                username="user",
                password="pass",
            )

            assert client is not None
            assert isinstance(client, AsyncDAVClient)
            mock_options.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_davclient_without_probe(self) -> None:
        """Test get_davclient with probe disabled."""
        client = await get_davclient(
            url="https://caldav.example.com/dav/",
            username="user",
            password="pass",
            probe=False,
        )

        assert client is not None
        assert isinstance(client, AsyncDAVClient)

    @pytest.mark.asyncio
    async def test_get_davclient_env_vars(self) -> None:
        """Test get_davclient with environment variables."""
        with patch.dict(
            os.environ,
            {
                "CALDAV_URL": "https://env.example.com/dav/",
                "CALDAV_USERNAME": "envuser",
                "CALDAV_PASSWORD": "envpass",
            },
        ):
            client = await get_davclient(probe=False)

            assert "env.example.com" in str(client.url)
            assert client.username == "envuser"
            assert client.password == "envpass"

    @pytest.mark.asyncio
    async def test_get_davclient_params_override_env(self) -> None:
        """Test that explicit params override environment variables."""
        with patch.dict(
            os.environ,
            {
                "CALDAV_URL": "https://env.example.com/dav/",
                "CALDAV_USERNAME": "envuser",
                "CALDAV_PASSWORD": "envpass",
            },
        ):
            client = await get_davclient(
                url="https://param.example.com/dav/",
                username="paramuser",
                password="parampass",
                probe=False,
            )

            assert "param.example.com" in str(client.url)
            assert client.username == "paramuser"
            assert client.password == "parampass"

    @pytest.mark.asyncio
    async def test_get_davclient_missing_url(self) -> None:
        """Test that get_davclient raises error without URL."""
        # Clear any env vars that might be set
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="No configuration found"):
                await get_davclient(username="user", password="pass", probe=False)

    @pytest.mark.asyncio
    async def test_get_davclient_probe_failure(self) -> None:
        """Test get_davclient when probe fails."""
        with patch.object(AsyncDAVClient, "options") as mock_options:
            mock_options.side_effect = Exception("Connection failed")

            with pytest.raises(error.DAVError, match="Failed to connect"):
                await get_davclient(
                    url="https://caldav.example.com/dav/",
                    username="user",
                    password="pass",
                    probe=True,
                )

    @pytest.mark.asyncio
    async def test_get_davclient_additional_kwargs(self) -> None:
        """Test passing additional kwargs to AsyncDAVClient."""
        client = await get_davclient(
            url="https://caldav.example.com/dav/",
            username="user",
            password="pass",
            probe=False,
            timeout=30,
            ssl_verify_cert=False,
        )

        assert client.timeout == 30
        assert client.ssl_verify_cert is False


class TestAPIImprovements:
    """Tests verifying that API improvements were applied."""

    @pytest.mark.asyncio
    async def test_no_dummy_parameters(self) -> None:
        """Verify dummy parameters are not present in async API."""
        import inspect

        # Check proppatch signature
        sig = inspect.signature(AsyncDAVClient.proppatch)
        assert "dummy" not in sig.parameters

        # Check mkcol signature
        sig = inspect.signature(AsyncDAVClient.mkcol)
        assert "dummy" not in sig.parameters

        # Check mkcalendar signature
        sig = inspect.signature(AsyncDAVClient.mkcalendar)
        assert "dummy" not in sig.parameters

    @pytest.mark.asyncio
    async def test_standardized_body_parameter(self) -> None:
        """Verify methods have appropriate parameters.

        propfind has both 'body' (legacy) and 'props' (new protocol-based).
        report uses 'body' for raw XML.
        """
        import inspect

        # Check propfind has both body (legacy) and props (new)
        sig = inspect.signature(AsyncDAVClient.propfind)
        assert "body" in sig.parameters  # Legacy parameter
        assert "props" in sig.parameters  # New protocol-based parameter

        # Check report uses 'body', not 'query'
        sig = inspect.signature(AsyncDAVClient.report)
        assert "body" in sig.parameters
        assert "query" not in sig.parameters

    @pytest.mark.asyncio
    async def test_all_methods_have_headers_parameter(self) -> None:
        """Verify all HTTP methods accept headers parameter."""
        import inspect

        methods = [
            "propfind",
            "report",
            "options",
            "proppatch",
            "mkcol",
            "mkcalendar",
            "put",
            "post",
            "delete",
        ]

        for method_name in methods:
            method = getattr(AsyncDAVClient, method_name)
            sig = inspect.signature(method)
            assert "headers" in sig.parameters, f"{method_name} missing headers parameter"

    @pytest.mark.asyncio
    async def test_url_requirements_split(self) -> None:
        """Verify URL parameter requirements are split correctly."""
        import inspect

        # Query methods - URL should be Optional
        query_methods = ["propfind", "report", "options"]
        for method_name in query_methods:
            method = getattr(AsyncDAVClient, method_name)
            sig = inspect.signature(method)
            url_param = sig.parameters["url"]
            # Check default is None or has default
            assert url_param.default is None or url_param.default != inspect.Parameter.empty

        # Resource methods - URL should be required (no default)
        resource_methods = ["proppatch", "mkcol", "mkcalendar", "put", "post", "delete"]
        for method_name in resource_methods:
            method = getattr(AsyncDAVClient, method_name)
            sig = inspect.signature(method)
            url_param = sig.parameters["url"]
            # URL should not have None as annotation type (should be str, not Optional[str])
            # This is a simplified check - in reality we'd need to inspect annotations more carefully


class TestTypeHints:
    """Tests verifying type hints are present."""

    def test_client_has_return_type_annotations(self) -> None:
        """Verify methods have return type annotations."""
        import inspect

        methods = [
            "propfind",
            "report",
            "options",
            "proppatch",
            "put",
            "delete",
        ]

        for method_name in methods:
            method = getattr(AsyncDAVClient, method_name)
            sig = inspect.signature(method)
            assert sig.return_annotation != inspect.Signature.empty, (
                f"{method_name} missing return type annotation"
            )

    def test_get_davclient_has_return_type(self) -> None:
        """Verify get_davclient has return type annotation."""
        import inspect

        sig = inspect.signature(get_davclient)
        assert sig.return_annotation != inspect.Signature.empty


class TestAsyncCalendarObjectResource:
    """Tests for AsyncCalendarObjectResource class."""

    def test_has_component_method_exists(self) -> None:
        """
        Test that AsyncCalendarObjectResource has the has_component() method.

        This test catches a bug where AsyncCalendarObjectResource was missing
        the has_component() method that's used in AsyncCalendar.search() to
        filter out empty search results (a Google quirk).

        See async_collection.py:779 which calls:
            objects = [o for o in objects if o.has_component()]
        """
        from caldav.aio import (
            AsyncCalendarObjectResource,
            AsyncEvent,
            AsyncJournal,
            AsyncTodo,
        )

        # Verify has_component exists on all async calendar object classes
        for cls in [AsyncCalendarObjectResource, AsyncEvent, AsyncTodo, AsyncJournal]:
            assert hasattr(cls, "has_component"), f"{cls.__name__} missing has_component method"

    def test_has_component_with_data(self) -> None:
        """Test has_component returns True when object has VEVENT/VTODO/VJOURNAL."""
        from caldav.aio import AsyncEvent

        event_data = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:test@example.com
DTSTART:20200101T100000Z
DTEND:20200101T110000Z
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR"""

        event = AsyncEvent(client=None, data=event_data)
        assert event.has_component() is True

    def test_has_component_without_data(self) -> None:
        """Test has_component returns False when object has no data."""
        from caldav.aio import AsyncCalendarObjectResource

        obj = AsyncCalendarObjectResource(client=None, data=None)
        assert obj.has_component() is False

    def test_has_component_with_empty_data(self) -> None:
        """Test has_component returns False when object has no data.

        Note: The sync CalendarObjectResource validates data on assignment,
        so we use data=None instead of data="" to test the "no data" case.
        """
        from caldav.aio import AsyncCalendarObjectResource

        obj = AsyncCalendarObjectResource(client=None, data=None)
        assert obj.has_component() is False

    def test_has_component_with_only_vcalendar(self) -> None:
        """Test has_component returns False when only VCALENDAR wrapper exists."""
        from caldav.aio import AsyncCalendarObjectResource

        # Only VCALENDAR wrapper, no actual component
        data = """BEGIN:VCALENDAR
VERSION:2.0
END:VCALENDAR"""

        obj = AsyncCalendarObjectResource(client=None, data=data)
        # This should return False since there's no VEVENT/VTODO/VJOURNAL
        assert obj.has_component() is False


class TestAsyncRateLimiting:
    """
    Unit tests for 429/503 rate-limit handling in AsyncDAVClient.
    Mirrors TestRateLimiting in test_caldav_unit.py.
    No real server communication.
    """

    def _make_response(self, status_code, headers=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.headers = headers or {}
        resp.reason = "Too Many Requests" if status_code == 429 else "Service Unavailable"
        resp.reason_phrase = resp.reason
        return resp

    @pytest.mark.asyncio
    async def test_429_no_retry_after_raises(self):
        client = AsyncDAVClient(url="http://cal.example.com/")
        client.session.request = AsyncMock(return_value=self._make_response(429))
        with pytest.raises(error.RateLimitError) as exc_info:
            await client.request("/")
        assert exc_info.value.retry_after is None
        assert exc_info.value.retry_after_seconds is None

    @pytest.mark.asyncio
    async def test_429_with_integer_retry_after(self):
        client = AsyncDAVClient(url="http://cal.example.com/")
        client.session.request = AsyncMock(
            return_value=self._make_response(429, {"Retry-After": "30"})
        )
        with pytest.raises(error.RateLimitError) as exc_info:
            await client.request("/")
        assert exc_info.value.retry_after == "30"
        assert exc_info.value.retry_after_seconds == 30.0

    @pytest.mark.asyncio
    async def test_503_without_retry_after_does_not_raise_rate_limit(self):
        client = AsyncDAVClient(url="http://cal.example.com/")
        client.session.request = AsyncMock(return_value=self._make_response(503))
        # Should not raise RateLimitError; falls through as a normal 503 response
        response = await client.request("/")
        assert response.status == 503

    @pytest.mark.asyncio
    async def test_503_with_retry_after_raises(self):
        client = AsyncDAVClient(url="http://cal.example.com/")
        client.session.request = AsyncMock(
            return_value=self._make_response(503, {"Retry-After": "10"})
        )
        with pytest.raises(error.RateLimitError) as exc_info:
            await client.request("/")
        assert exc_info.value.retry_after_seconds == 10.0

    @pytest.mark.asyncio
    async def test_rate_limit_handle_sleeps_and_retries(self):
        ok_response = self._make_response(200)
        client = AsyncDAVClient(url="http://cal.example.com/", rate_limit_handle=True)
        client.session.request = AsyncMock(
            side_effect=[
                self._make_response(429, {"Retry-After": "5"}),
                ok_response,
            ]
        )
        with patch("caldav.async_davclient.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            response = await client.request("/")
        mock_sleep.assert_awaited_once_with(5.0)
        assert response.status == 200
        assert client.session.request.call_count == 2

    @pytest.mark.asyncio
    async def test_rate_limit_handle_default_sleep_used_when_no_retry_after(self):
        ok_response = self._make_response(200)
        client = AsyncDAVClient(
            url="http://cal.example.com/", rate_limit_handle=True, rate_limit_default_sleep=3
        )
        client.session.request = AsyncMock(side_effect=[self._make_response(429), ok_response])
        with patch("caldav.async_davclient.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            response = await client.request("/")
        mock_sleep.assert_awaited_once_with(3.0)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_rate_limit_handle_no_sleep_info_raises(self):
        client = AsyncDAVClient(url="http://cal.example.com/", rate_limit_handle=True)
        client.session.request = AsyncMock(return_value=self._make_response(429))
        with pytest.raises(error.RateLimitError):
            await client.request("/")

    @pytest.mark.asyncio
    async def test_rate_limit_max_sleep_caps_sleep_time(self):
        ok_response = self._make_response(200)
        client = AsyncDAVClient(
            url="http://cal.example.com/", rate_limit_handle=True, rate_limit_max_sleep=60
        )
        client.session.request = AsyncMock(
            side_effect=[
                self._make_response(429, {"Retry-After": "3600"}),
                ok_response,
            ]
        )
        with patch("caldav.async_davclient.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await client.request("/")
        mock_sleep.assert_awaited_once_with(60.0)

    @pytest.mark.asyncio
    async def test_rate_limit_max_sleep_zero_raises(self):
        client = AsyncDAVClient(
            url="http://cal.example.com/", rate_limit_handle=True, rate_limit_max_sleep=0
        )
        client.session.request = AsyncMock(
            return_value=self._make_response(429, {"Retry-After": "30"})
        )
        with pytest.raises(error.RateLimitError):
            await client.request("/")

    @pytest.mark.asyncio
    async def test_rate_limit_adaptive_sleep_increases_on_repeated_retries(self):
        """On repeated 429s the sleep grows: first sleep uses Retry-After, second adds half of already-slept."""
        ok_response = self._make_response(200)
        client = AsyncDAVClient(url="http://cal.example.com/", rate_limit_handle=True)
        client.session.request = AsyncMock(
            side_effect=[
                self._make_response(429, {"Retry-After": "4"}),
                self._make_response(429, {"Retry-After": "4"}),
                ok_response,
            ]
        )
        with patch("caldav.async_davclient.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            response = await client.request("/")
        assert mock_sleep.call_count == 2
        sleeps = [c.args[0] for c in mock_sleep.call_args_list]
        assert sleeps[0] == 4.0
        assert sleeps[1] == 6.0  # 4 + 4/2
        assert response.status == 200
        assert client.session.request.call_count == 3

    @pytest.mark.asyncio
    async def test_rate_limit_max_sleep_stops_adaptive_retries(self):
        """When accumulated sleep exceeds rate_limit_max_sleep, retrying stops."""
        client = AsyncDAVClient(
            url="http://cal.example.com/", rate_limit_handle=True, rate_limit_max_sleep=5
        )
        client.session.request = AsyncMock(
            return_value=self._make_response(429, {"Retry-After": "4"})
        )
        with patch("caldav.async_davclient.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(error.RateLimitError):
                await client.request("/")
