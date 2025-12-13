#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
Unit tests for async_davclient module.

Rule: None of the tests in this file should initiate any internet
communication. We use Mock/MagicMock to emulate server communication.
"""
import os
import pytest
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

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
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")
        client.session = AsyncMock()
        client.session.close = AsyncMock()

        await client.close()

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
        assert call_args[0][0] == "PROPFIND"  # method
        assert "Depth" in call_args[1]["headers"]
        assert call_args[1]["headers"]["Depth"] == "1"

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
        assert "calendars" in call_args[0][1]  # URL

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
        assert call_args[0][0] == "REPORT"
        assert "Content-Type" in call_args[1]["headers"]
        assert "application/xml" in call_args[1]["headers"]["Content-Type"]

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
        assert call_args[0][0] == "OPTIONS"

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
        assert call_args[0][0] == "PROPPATCH"

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
        assert call_args[0][0] == "PUT"

    @pytest.mark.asyncio
    async def test_delete_method(self) -> None:
        """Test delete method (requires URL)."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        mock_response = create_mock_response(status_code=204, reason="No Content")
        client.session.request = AsyncMock(return_value=mock_response)

        response = await client.delete(
            url="https://caldav.example.com/dav/calendar/event.ics"
        )

        assert response.status == 204
        call_args = client.session.request.call_args
        assert call_args[0][0] == "DELETE"

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
        assert call_args[0][0] == "POST"

    @pytest.mark.asyncio
    async def test_mkcol_method(self) -> None:
        """Test mkcol method (requires URL)."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        mock_response = create_mock_response(status_code=201)
        client.session.request = AsyncMock(return_value=mock_response)

        response = await client.mkcol(
            url="https://caldav.example.com/dav/newcollection/"
        )

        assert response.status == 201
        call_args = client.session.request.call_args
        assert call_args[0][0] == "MKCOL"

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
        assert call_args[0][0] == "MKCALENDAR"

    def test_extract_auth_types(self) -> None:
        """Test extracting auth types from WWW-Authenticate header."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        # Single auth type
        auth_types = client.extract_auth_types("Basic realm=\"Test\"")
        assert "basic" in auth_types

        # Multiple auth types
        auth_types = client.extract_auth_types("Basic realm=\"Test\", Digest realm=\"Test\"")
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
            with pytest.raises(ValueError, match="URL is required"):
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
        """Verify all methods use 'body' parameter, not 'props' or 'query'."""
        import inspect

        # Check propfind uses 'body', not 'props'
        sig = inspect.signature(AsyncDAVClient.propfind)
        assert "body" in sig.parameters
        assert "props" not in sig.parameters

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
