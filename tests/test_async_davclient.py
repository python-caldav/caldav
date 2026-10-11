#!/usr/bin/env python
"""
Unit tests for async_davclient module.

Rule: None of the tests in this file should initiate any internet
communication. We use Mock/MagicMock to emulate server communication.
"""

import inspect
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from caldav.async_davclient import AsyncDAVClient, DAVResponse, get_davclient
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


class TestDAVResponse:
    """Tests for DAVResponse class."""

    def test_response_with_xml_content(self) -> None:
        """Test parsing XML response."""
        resp = create_mock_response(
            content=SAMPLE_MULTISTATUS_XML,
            status_code=207,
            reason="Multi-Status",
            headers={"Content-Type": "text/xml; charset=utf-8"},
        )

        dav_response = DAVResponse(resp)

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

        dav_response = DAVResponse(resp)

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

        dav_response = DAVResponse(resp)

        assert dav_response.status == 200
        assert dav_response.tree is None
        assert b"Plain text response" in dav_response._raw

    def test_response_raw_property(self) -> None:
        """Test raw property returns string."""
        resp = create_mock_response(content=b"test content")

        dav_response = DAVResponse(resp)

        assert isinstance(dav_response.raw, str)
        assert "test content" in dav_response.raw

    def test_response_crlf_normalization(self) -> None:
        """Test that CRLF is normalized to LF."""
        resp = create_mock_response(content=b"line1\r\nline2\r\nline3")

        dav_response = DAVResponse(resp)

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

    def test_session_creation_without_proxy_does_not_pass_proxy_kwarg(self) -> None:
        """Regression test for issue #632: proxy=None must not be passed to httpx.AsyncClient.

        httpx < 0.23.0 does not accept a 'proxy' keyword argument at all, so
        passing proxy=None unconditionally breaks initialization even when no
        proxy is configured.
        """
        from caldav.async_davclient import _USE_HTTPX

        if not _USE_HTTPX:
            pytest.skip("test only relevant for httpx backend")

        with patch("caldav.async_davclient.httpx.AsyncClient") as mock_client:
            AsyncDAVClient(url="https://caldav.example.com/dav/")
            _, call_kwargs = mock_client.call_args
            assert "proxy" not in call_kwargs, (
                "proxy kwarg must not be passed to httpx.AsyncClient when no proxy is configured"
            )

    def test_session_creation_with_proxy_passes_proxy_kwarg(self) -> None:
        """When a proxy is configured, it must be forwarded to httpx.AsyncClient."""
        from caldav.async_davclient import _USE_HTTPX

        if not _USE_HTTPX:
            pytest.skip("test only relevant for httpx backend")

        with patch("caldav.async_davclient.httpx.AsyncClient") as mock_client:
            AsyncDAVClient(
                url="https://caldav.example.com/dav/",
                proxy="proxy.example.com:8080",
            )
            _, call_kwargs = mock_client.call_args
            assert call_kwargs.get("proxy") == "http://proxy.example.com:8080"

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

        assert isinstance(response, DAVResponse)
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
    async def test_propfind_props_as_raw_xml_string_is_rejected(self) -> None:
        """A raw XML body belongs in ``body``, not in ``props``.

        ``DAVClient.propfind`` accepts either a list of property names or a raw
        XML body in ``props``; that is its legacy shape.  The async twin used
        to assume a list, so a string was iterated character by character and
        silently turned into an empty ``<D:prop/>`` request - servers answered
        that with an empty or useless multistatus (Robur returns an empty
        body), which is why the bug went unnoticed.  Rather than copy the
        legacy shape into a new API, the async client has a dedicated ``body``
        parameter and rejects a string here outright.
        """
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")
        client.session.request = AsyncMock()

        raw = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<D:propfind xmlns:D="DAV:"><D:allprop/></D:propfind>'
        )
        with pytest.raises(TypeError, match="body"):
            await client.propfind("https://caldav.example.com/dav/", props=raw)
        client.session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_propfind_body_is_sent_verbatim(self) -> None:
        """The supported way to send a raw request: ``body``."""
        client = AsyncDAVClient(url="https://caldav.example.com/dav/")

        mock_response = create_mock_response(
            content=SAMPLE_PROPFIND_XML,
            status_code=207,
            headers={"Content-Type": "text/xml"},
        )
        client.session.request = AsyncMock(return_value=mock_response)

        raw = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<D:propfind xmlns:D="DAV:"><D:allprop/></D:propfind>'
        )
        await client.propfind("https://caldav.example.com/dav/", body=raw)

        kwargs = client.session.request.call_args.kwargs
        assert "allprop" in str(kwargs.get("data") or kwargs.get("content") or "")

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
            mock_response_obj = DAVResponse(mock_response)
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


class TestAsyncCalendarAddObject:
    """Tests for Calendar.add_object/add_event/add_todo with async clients (issue #631)."""

    SIMPLE_EVENT = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:test-async-add-event@example.com
DTSTART:20200101T100000Z
DTEND:20200101T110000Z
SUMMARY:Test Async Add Event
END:VEVENT
END:VCALENDAR"""

    @pytest.mark.asyncio
    async def test_add_event_returns_coroutine_with_async_client(self) -> None:
        """Calendar.add_event() must be awaitable when using AsyncDAVClient.

        Regression test for issue #631: o.save() returns a coroutine for async
        clients, so add_object() must await it instead of doing o.url on the
        coroutine object.
        """
        import inspect

        from caldav.aio import AsyncEvent
        from caldav.collection import Calendar

        client = AsyncDAVClient(url="https://caldav.example.com/dav/")
        calendar = Calendar(client=client, url="https://caldav.example.com/dav/calendars/test/")

        with patch.object(AsyncEvent, "_async_create", new_callable=AsyncMock):
            result = calendar.add_event(self.SIMPLE_EVENT)
            # With an async client, add_event must return a coroutine
            assert inspect.isawaitable(result), (
                "add_event() should return a coroutine when using AsyncDAVClient, "
                "got %r instead" % result
            )
            event = await result
        assert isinstance(event, AsyncEvent)

    @pytest.mark.asyncio
    async def test_add_event_result_has_url(self) -> None:
        """Awaiting add_event() with async client returns an Event with a URL."""
        from caldav.aio import AsyncEvent
        from caldav.collection import Calendar

        client = AsyncDAVClient(url="https://caldav.example.com/dav/")
        calendar = Calendar(client=client, url="https://caldav.example.com/dav/calendars/test/")

        with patch.object(AsyncEvent, "_async_create", new_callable=AsyncMock):
            event = await calendar.add_event(self.SIMPLE_EVENT)
        # Should have a URL set (or None, but not crash)
        _ = event.url  # must not raise AttributeError


class TestAsyncLoadMultigetFallback:
    """load(multiget_fallback=...) on the async twin.

    Mirrors testLoadFallsBackToMultigetByDefault and
    testLoadWithoutMultigetFallbackRaisesTheServersOwnError in
    test_caldav_unit.py.
    """

    def _forbidden_event(self):
        from caldav.aio import AsyncEvent
        from caldav.collection import Calendar

        client = AsyncDAVClient(url="https://caldav.example.com/dav/")
        client.request = AsyncMock(
            side_effect=error.AuthorizationError(
                url="https://caldav.example.com/dav/calendars/test/x.ics",
                reason="Forbidden",
            )
        )
        calendar = Calendar(client=client, url="https://caldav.example.com/dav/calendars/test/")
        return AsyncEvent(
            client=client,
            url="https://caldav.example.com/dav/calendars/test/x.ics",
            parent=calendar,
        )

    @pytest.mark.asyncio
    async def test_load_falls_back_to_multiget_by_default(self) -> None:
        """A refused GET is retried as a calendar-multiget REPORT."""
        from caldav.aio import AsyncCalendarObjectResource

        event = self._forbidden_event()
        with patch.object(
            AsyncCalendarObjectResource, "load_by_multiget", new_callable=AsyncMock
        ) as multiget:
            multiget.return_value = event
            assert await event.load() is event
        multiget.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_load_without_multiget_fallback_raises_the_servers_own_error(self) -> None:
        """multiget_fallback=False surfaces the 403 and sends no REPORT."""
        from caldav.aio import AsyncCalendarObjectResource

        event = self._forbidden_event()
        with patch.object(
            AsyncCalendarObjectResource, "load_by_multiget", new_callable=AsyncMock
        ) as multiget:
            with pytest.raises(error.AuthorizationError):
                await event.load(multiget_fallback=False)
        multiget.assert_not_awaited()


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


class TestAsyncUnpromptedBasicAuth:
    """Issue #713, async side. Mirrors TestUnpromptedBasicAuth in test_caldav_unit.py."""

    def _make_response(self, status_code, headers=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.headers = headers or {}
        resp.reason = "Unauthorized" if status_code == 401 else "OK"
        resp.reason_phrase = resp.reason
        return resp

    @pytest.mark.asyncio
    @pytest.mark.parametrize("retry_status", [200, 401])
    async def test_connection_abort_probe_can_guess_basic_once(self, retry_status):
        client = AsyncDAVClient(url="https://cal.example.com/", username="user", password="pass")
        client.session.request = AsyncMock(
            side_effect=[
                ConnectionError("server aborted connection"),
                self._make_response(401),
                self._make_response(retry_status),
            ]
        )

        if retry_status == 200:
            response = await client.request("/calendar/item.ics", "PUT", "calendar data")
            assert response.status == 200
        else:
            with pytest.raises(error.AuthorizationError):
                await client.request("/calendar/item.ics", "PUT", "calendar data")
            assert client.auth is None

        calls = client.session.request.call_args_list
        assert [call.kwargs["method"] for call in calls] == ["PUT", "GET", "PUT"]
        assert calls[0].kwargs["auth"] is None
        assert calls[1].kwargs.get("auth") is None
        assert calls[2].kwargs["auth"] is not None
        assert {key: value for key, value in calls[2].kwargs.items() if key != "auth"} == {
            key: value for key, value in calls[0].kwargs.items() if key != "auth"
        }
        assert client._unprompted_basic_tried is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "probe_status, scheme, response_url",
        [(401, "http", None), (401, "https", "http://cal.example.com/"), (200, "https", None)],
    )
    async def test_connection_abort_probe_without_safe_auth_reraises(
        self, probe_status, scheme, response_url
    ):
        client = AsyncDAVClient(
            url=f"{scheme}://cal.example.com/", username="user", password="pass"
        )
        original_error = ConnectionError("server aborted connection")
        probe = self._make_response(probe_status)
        probe.url = response_url
        client.session.request = AsyncMock(side_effect=[original_error, probe])

        with pytest.raises(ConnectionError) as exc_info:
            await client.request("/calendar/item.ics", "PUT", "calendar data")

        assert exc_info.value is original_error
        assert client.session.request.call_count == 2
        assert client.auth is None

    @pytest.mark.asyncio
    async def test_connection_abort_after_basic_guess_unwinds_the_guess(self):
        """A guessed Basic retry that is aborted again must not leave the guess set."""
        client = AsyncDAVClient(url="https://cal.example.com/", username="user", password="pass")
        second_error = ConnectionError("aborted again")
        client.session.request = AsyncMock(
            side_effect=[
                ConnectionError("server aborted connection"),
                self._make_response(401),
                second_error,
            ]
        )

        with pytest.raises(ConnectionError) as exc_info:
            await client.request("/calendar/item.ics", "PUT", "calendar data")

        assert exc_info.value is second_error
        assert client.auth is None
        assert client.auth_type is None
        assert client._unprompted_basic_tried is True

    @pytest.mark.asyncio
    async def test_connection_abort_guess_kept_when_server_answers(self):
        """A guessed retry the server answers (here: 429) keeps the guessed auth."""
        client = AsyncDAVClient(
            url="https://cal.example.com/",
            username="user",
            password="pass",
            rate_limit_handle=False,
        )
        client.session.request = AsyncMock(
            side_effect=[
                ConnectionError("server aborted connection"),
                self._make_response(401),
                self._make_response(429, {"Retry-After": "4"}),
            ]
        )
        with pytest.raises(error.RateLimitError):
            await client.request("/calendar/item.ics", "PUT", "calendar data")
        assert client.auth is not None
        assert client.auth_type == "basic"

    @pytest.mark.asyncio
    async def test_connection_abort_probe_does_not_guess_twice(self):
        """After a failed guess, a later abort-probe-401 re-raises without guessing again."""
        client = AsyncDAVClient(url="https://cal.example.com/", username="user", password="pass")
        client.session.request = AsyncMock(
            side_effect=[
                ConnectionError("server aborted connection"),
                self._make_response(401),
                self._make_response(401),
            ]
        )
        with pytest.raises(error.AuthorizationError):
            await client.request("/calendar/item.ics", "PUT", "calendar data")

        original_error = ConnectionError("server aborted connection")
        client.session.request = AsyncMock(side_effect=[original_error, self._make_response(401)])
        with pytest.raises(ConnectionError) as exc_info:
            await client.request("/calendar/item.ics", "PUT", "calendar data")

        assert exc_info.value is original_error
        assert client.session.request.call_count == 2
        assert client.auth is None

    @pytest.mark.asyncio
    async def test_401_without_www_authenticate_retries_with_basic_over_tls(self):
        client = AsyncDAVClient(url="https://cal.example.com/", username="user", password="pass")
        client.session.request = AsyncMock(
            side_effect=[self._make_response(401), self._make_response(200)]
        )
        response = await client.request("/")
        assert response.status == 200
        assert client.session.request.call_count == 2
        assert client.auth_type == "basic"
        second_call_kwargs = client.session.request.call_args_list[1].kwargs
        assert second_call_kwargs["auth"] is not None

    @pytest.mark.asyncio
    async def test_401_without_www_authenticate_over_plain_http_does_not_guess(self):
        client = AsyncDAVClient(url="http://cal.example.com/", username="user", password="pass")
        client.session.request = AsyncMock(return_value=self._make_response(401))
        with pytest.raises(error.AuthorizationError):
            await client.request("/")
        assert client.session.request.call_count == 1
        assert client.auth is None

    @pytest.mark.asyncio
    async def test_401_without_www_authenticate_does_not_loop_forever(self):
        client = AsyncDAVClient(url="https://cal.example.com/", username="user", password="pass")
        client.session.request = AsyncMock(return_value=self._make_response(401))
        with pytest.raises(error.AuthorizationError):
            await client.request("/")
        assert client.session.request.call_count == 2

    @pytest.mark.asyncio
    async def test_explicit_auth_type_is_not_overridden(self):
        client = AsyncDAVClient(
            url="https://cal.example.com/",
            username="user",
            password="pass",
            auth_type="digest",
        )
        client.session.request = AsyncMock(return_value=self._make_response(401))
        with pytest.raises(error.AuthorizationError):
            await client.request("/")
        assert client.auth_type == "digest"

    @pytest.mark.asyncio
    async def test_explicit_auth_object_is_not_overridden(self):
        client = AsyncDAVClient(
            url="https://cal.example.com/",
            username="user",
            password="pass",
            auth=object(),
        )
        client.session.request = AsyncMock(return_value=self._make_response(401))
        with pytest.raises(error.AuthorizationError):
            await client.request("/")
        assert client.session.request.call_count == 1
        assert client.auth_type is None

    @pytest.mark.asyncio
    async def test_401_with_www_authenticate_still_negotiates_normally(self):
        client = AsyncDAVClient(url="https://cal.example.com/", username="user", password="pass")
        client.session.request = AsyncMock(
            side_effect=[
                self._make_response(401, {"WWW-Authenticate": 'Basic realm="x"'}),
                self._make_response(200),
            ]
        )
        response = await client.request("/")
        assert response.status == 200
        assert client.session.request.call_count == 2
        assert client.auth is not None
        assert client.auth_type is None  # negotiation doesn't set auth_type, only auth

    @pytest.mark.asyncio
    async def test_failed_guess_does_not_stick_and_does_not_retry(self):
        client = AsyncDAVClient(url="https://cal.example.com/", username="user", password="pass")
        client.session.request = AsyncMock(return_value=self._make_response(401))
        with pytest.raises(error.AuthorizationError):
            await client.request("/")
        assert client.session.request.call_count == 2
        assert client.auth is None
        assert client.auth_type is None
        assert client._unprompted_basic_tried is True

        # A later request on the same client, now facing a real challenge, still negotiates.
        client.session.request = AsyncMock(
            side_effect=[
                self._make_response(401, {"WWW-Authenticate": 'Digest realm="x"'}),
                self._make_response(200),
            ]
        )
        response = await client.request("/")
        assert response.status == 200
        assert client.auth is not None
        assert client.auth_type is None


class TestAsyncAuthorizationErrorPreconditions:
    """Async twin of TestAuthorizationErrorPreconditions in test_caldav_unit.py
    (https://github.com/python-caldav/caldav/issues/738).
    """

    VALID_SYNC_TOKEN_BODY = (
        b'<?xml version="1.0" encoding="utf-8"?>\n'
        b'<D:error xmlns:D="DAV:"><D:valid-sync-token/></D:error>'
    )

    def _make_response(self, status_code, body=b"", content_type="application/xml"):
        resp = MagicMock()
        resp.status_code = status_code
        resp.headers = {"Content-Type": content_type} if body else {}
        resp.reason = "Forbidden"
        resp.reason_phrase = resp.reason
        resp.content = body
        resp.text = body.decode() if body else ""
        return resp

    @pytest.mark.asyncio
    async def test_403_precondition_is_kept(self):
        from caldav.elements import dav

        client = AsyncDAVClient(url="https://cal.example.com/", username="user", password="pass")
        client.session.request = AsyncMock(
            return_value=self._make_response(403, self.VALID_SYNC_TOKEN_BODY)
        )
        with pytest.raises(error.AuthorizationError) as exc_info:
            await client.request("/")
        assert exc_info.value.preconditions == [dav.ValidSyncToken.tag]
        assert exc_info.value.body == self.VALID_SYNC_TOKEN_BODY
        assert exc_info.value.reason == "Forbidden"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "body,content_type",
        [
            (b"", "application/xml"),
            (b"<html><body>Forbidden</body></html>", "text/html"),
            (b"not xml at all <", "text/plain"),
            (b"<html>forbidden", "application/xml"),
            (b"<?xml version='1.0'?><foo><bar/></foo>", "application/xml"),
        ],
    )
    async def test_403_without_precondition(self, body, content_type):
        client = AsyncDAVClient(url="https://cal.example.com/", username="user", password="pass")
        client.session.request = AsyncMock(
            return_value=self._make_response(403, body, content_type)
        )
        with pytest.raises(error.AuthorizationError) as exc_info:
            await client.request("/")
        assert exc_info.value.preconditions == []

    def test_httpx_response_reason_phrase(self):
        """httpx names the reason ``reason_phrase``; a real httpx.Response,
        not a mock carrying both attributes."""
        httpx = pytest.importorskip("httpx")
        from caldav.elements import dav

        client = AsyncDAVClient(url="https://cal.example.com/")
        r = httpx.Response(
            403,
            content=self.VALID_SYNC_TOKEN_BODY,
            headers={"Content-Type": "application/xml"},
        )
        with pytest.raises(error.AuthorizationError) as exc_info:
            client._raise_authorization_error("https://cal.example.com/", r)
        assert exc_info.value.reason == "Forbidden"
        assert exc_info.value.body == self.VALID_SYNC_TOKEN_BODY
        assert exc_info.value.preconditions == [dav.ValidSyncToken.tag]

    def _calendar(self, report_error, sync_token_support=None):
        from caldav.collection import Calendar

        client = AsyncDAVClient(url="https://cal.example.com/")
        if sync_token_support:
            client.features.set_feature("sync-token", sync_token_support)
        calendar = Calendar(client=client, url="https://cal.example.com/cal/")
        report = patch.object(
            Calendar,
            "_request_report_build_resultlist",
            new_callable=AsyncMock,
            side_effect=report_error,
        )
        search = patch.object(Calendar, "search", new_callable=AsyncMock, return_value=[])
        return calendar, report, search

    @pytest.mark.asyncio
    async def test_sync_token_expired_falls_back(self):
        from caldav.elements import dav

        e = error.AuthorizationError(
            url="/cal/", reason="Forbidden", preconditions=[dav.ValidSyncToken.tag]
        )
        calendar, report, search = self._calendar(e)
        with report, search as mocked_search:
            result = await calendar.get_objects_by_sync_token("http://example.com/sync/1")
        mocked_search.assert_awaited_once()
        assert result.sync_token.startswith("fake-")

    @pytest.mark.asyncio
    async def test_bare_403_propagates_when_sync_token_is_known_to_work(self):
        e = error.AuthorizationError(url="/cal/", reason="Forbidden")
        calendar, report, search = self._calendar(e, sync_token_support="full")
        with report, search as mocked_search:
            with pytest.raises(error.AuthorizationError):
                await calendar.get_objects_by_sync_token("http://example.com/sync/1")
        mocked_search.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("support", [None, "fragile"])
    async def test_bare_403_falls_back_unless_sync_token_is_known_to_work(self, support):
        e = error.AuthorizationError(url="/cal/", reason="Forbidden")
        calendar, report, search = self._calendar(e, sync_token_support=support)
        with report, search as mocked_search:
            result = await calendar.get_objects_by_sync_token("http://example.com/sync/1")
        mocked_search.assert_awaited_once()
        assert result.sync_token.startswith("fake-")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("support", [None, "full"])
    async def test_403_unsupported_report_falls_back(self, support):
        """Zimbra answers the sync REPORT with 403 and DAV:supported-report:
        the report is not supported, which is no permission problem."""
        from caldav.elements import dav

        e = error.AuthorizationError(
            url="/cal/", reason="Forbidden", preconditions=[dav.SupportedReport.tag]
        )
        calendar, report, search = self._calendar(e, sync_token_support=support)
        with report, search as mocked_search:
            result = await calendar.get_objects_by_sync_token("http://example.com/sync/1")
        mocked_search.assert_awaited_once()
        assert result.sync_token.startswith("fake-")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("support", [None, "full"])
    async def test_403_with_other_precondition_propagates(self, support):
        e = error.AuthorizationError(
            url="/cal/", reason="Forbidden", preconditions=["{DAV:}need-privileges"]
        )
        calendar, report, search = self._calendar(e, sync_token_support=support)
        with report, search as mocked_search:
            with pytest.raises(error.AuthorizationError):
                await calendar.get_objects_by_sync_token("http://example.com/sync/1")
        mocked_search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_collection_sync_propagates_genuine_403(self):
        """SynchronizableCalendarObjectCollection.sync() must not hide what
        get_objects_by_sync_token() raises."""
        from caldav.collection import SynchronizableCalendarObjectCollection

        e = error.AuthorizationError(url="/cal/", reason="Forbidden")
        calendar, report, search = self._calendar(e, sync_token_support="full")
        collection = SynchronizableCalendarObjectCollection(
            calendar, [], "http://example.com/sync/1"
        )
        with report, search:
            with pytest.raises(error.AuthorizationError):
                await collection.sync()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("support,raises", [("full", True), (None, False)])
    async def test_collection_sync_load_403(self, support, raises):
        from caldav.calendarobjectresource import Event
        from caldav.collection import Calendar, SynchronizableCalendarObjectCollection

        e = error.AuthorizationError(url="/cal/x.ics", reason="Forbidden")
        calendar, _, search = self._calendar(e, sync_token_support=support)
        obj = Event(calendar.client, url="https://cal.example.com/cal/x.ics", parent=calendar)
        page = SynchronizableCalendarObjectCollection(calendar, [obj], "tok-2")
        collection = SynchronizableCalendarObjectCollection(calendar, [], "tok-1")
        with (
            search as mocked_search,
            patch.object(
                Calendar, "get_objects_by_sync_token", new_callable=AsyncMock, return_value=page
            ),
            patch.object(Event, "load", new_callable=AsyncMock, side_effect=e),
        ):
            if raises:
                with pytest.raises(error.AuthorizationError):
                    await collection.sync()
                mocked_search.assert_not_awaited()
            else:
                await collection.sync()
                mocked_search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_report_error_still_falls_back(self):
        calendar, report, search = self._calendar(error.ReportError("nope"))
        with report, search as mocked_search:
            await calendar.get_objects_by_sync_token("http://example.com/sync/1")
        mocked_search.assert_awaited_once()


class TestAsyncPrincipalCalendar:
    """``principal.calendar()`` must work with async clients.

    Regression test: ``principal.calendar(cal_id=<plain id>)`` used to raise
    ``TypeError: argument of type 'coroutine' is not a container or iterable``
    for async clients, because the synchronous ``calendar_home_set`` property
    evaluated ``"@" in <coroutine>`` without awaiting the async ``get_property``.
    The cleanup blocks in the integration tests wrapped the call in a bare
    ``except``, so calendars leaked silently and a later MKCALENDAR 405'd.
    """

    @pytest.mark.asyncio
    async def test_calendar_by_cal_id_returns_awaitable(self) -> None:
        """A plain cal_id needs the home set, so async returns a coroutine."""
        from caldav.collection import Calendar, Principal

        client = AsyncDAVClient(url="https://caldav.example.com/dav/")
        principal = Principal(client=client, url="https://caldav.example.com/dav/principals/user/")

        ## The calendar-home-set discovery is the only would-be round-trip; mock
        ## the async get_property so the test stays offline.
        with patch.object(
            Principal,
            "get_property",
            new=AsyncMock(return_value="https://caldav.example.com/dav/calendars/user/"),
        ):
            result = principal.calendar(cal_id="testcal")
            assert inspect.iscoroutine(result), "async calendar() must return a coroutine"
            calendar = await result

        assert isinstance(calendar, Calendar)
        assert str(calendar.url).endswith("/calendars/user/testcal/")

    @pytest.mark.asyncio
    async def test_calendar_by_full_url_stays_synchronous(self) -> None:
        """A full-URL cal_id needs no home set, so it must NOT become a coroutine.

        ``test_calendar_by_full_url`` calls this without ``await`` and reads
        ``.url`` directly, so the sync short-circuit must be preserved.
        """
        from caldav.collection import Calendar, Principal

        client = AsyncDAVClient(url="https://caldav.example.com/dav/")
        principal = Principal(client=client, url="https://caldav.example.com/dav/principals/user/")

        calendar = principal.calendar(
            cal_id="https://caldav.example.com/dav/calendars/user/testcal/"
        )
        assert isinstance(calendar, Calendar)
        assert str(calendar.url).endswith("/calendars/user/testcal/")

    @pytest.mark.asyncio
    async def test_calendar_by_name_returns_awaitable(self) -> None:
        """Gate finding F5: only the bare-``cal_id`` half was fixed.  A
        ``name`` lookup went on to iterate the *coroutine* returned by the
        async ``get_calendars()``, raising ``TypeError: 'coroutine' object is
        not iterable``."""
        from caldav.collection import Calendar, CalendarSet, Principal

        client = AsyncDAVClient(url="https://caldav.example.com/dav/")
        principal = Principal(client=client, url="https://caldav.example.com/dav/principals/user/")

        wanted = Calendar(client, url="https://caldav.example.com/dav/calendars/user/wanted/")
        other = Calendar(client, url="https://caldav.example.com/dav/calendars/user/other/")

        async def fake_display_name(self: Calendar) -> str:
            return "Wanted" if str(self.url).endswith("/wanted/") else "Other"

        with (
            patch.object(
                Principal,
                "get_property",
                new=AsyncMock(return_value="https://caldav.example.com/dav/calendars/user/"),
            ),
            patch.object(CalendarSet, "get_calendars", new=AsyncMock(return_value=[other, wanted])),
            patch.object(Calendar, "get_display_name", new=fake_display_name),
        ):
            result = principal.calendar(name="Wanted")
            assert inspect.iscoroutine(result), "async calendar() must return a coroutine"
            calendar = await result

        assert isinstance(calendar, Calendar)
        assert str(calendar.url).endswith("/calendars/user/wanted/")

    @pytest.mark.asyncio
    async def test_calendar_by_unknown_name_raises_notfound(self) -> None:
        from caldav.collection import Calendar, CalendarSet, Principal
        from caldav.lib import error

        client = AsyncDAVClient(url="https://caldav.example.com/dav/")
        principal = Principal(client=client, url="https://caldav.example.com/dav/principals/user/")
        other = Calendar(client, url="https://caldav.example.com/dav/calendars/user/other/")

        async def fake_display_name(self: Calendar) -> str:
            return "Other"

        with (
            patch.object(
                Principal,
                "get_property",
                new=AsyncMock(return_value="https://caldav.example.com/dav/calendars/user/"),
            ),
            patch.object(CalendarSet, "get_calendars", new=AsyncMock(return_value=[other])),
            patch.object(Calendar, "get_display_name", new=fake_display_name),
        ):
            with pytest.raises(error.NotFoundError):
                await principal.calendar(name="Wanted")


class TestAsyncGetCalendarsWithoutHomeSet:
    """Async twin of the sync no-calendar-home-set discovery tests."""

    @staticmethod
    def _client(principal_depth1_xml):
        from .public_share_fixtures import PUBLIC_SHARE_URL, public_share_propfind_xml

        client = AsyncDAVClient(url=PUBLIC_SHARE_URL)
        client.requests = []

        async def fake_request(url, method="GET", body="", headers=None):
            depth = headers["Depth"]
            client.requests.append((str(url), depth))
            xml = public_share_propfind_xml(url, depth, principal_depth1_xml)
            return DAVResponse(create_mock_response(xml.encode(), status_code=207))

        client.request = fake_request
        return client

    @pytest.mark.asyncio
    async def test_client_url_is_calendar(self) -> None:
        from caldav.collection import Principal

        from .public_share_fixtures import (
            PUBLIC_SHARE_PRINCIPAL_DEPTH1_XML,
            PUBLIC_SHARE_PRINCIPAL_URL,
            PUBLIC_SHARE_URL,
        )

        client = self._client(PUBLIC_SHARE_PRINCIPAL_DEPTH1_XML)
        principal = Principal(client=client, url=PUBLIC_SHARE_PRINCIPAL_URL)
        calendars = await client.get_calendars(principal)
        assert [str(c.url) for c in calendars] == [PUBLIC_SHARE_URL + "/"]

    @pytest.mark.asyncio
    async def test_prefers_principal(self) -> None:
        from caldav.collection import Principal

        from .public_share_fixtures import (
            GMX_LIKE_PRINCIPAL_DEPTH1_XML,
            PUBLIC_SHARE_PRINCIPAL_URL,
            PUBLIC_SHARE_URL,
        )

        client = self._client(GMX_LIKE_PRINCIPAL_DEPTH1_XML)
        principal = Principal(client=client, url=PUBLIC_SHARE_PRINCIPAL_URL)
        calendars = await client.get_calendars(principal)
        assert [str(c.url) for c in calendars] == [PUBLIC_SHARE_PRINCIPAL_URL + "work/"]
        assert all(PUBLIC_SHARE_URL not in url for url, _ in client.requests)


class TestAsyncHttpLibrarySelection:
    """Which async HTTP library the module picks, and what happens when none is there.

    niquests is preferred; failing that, the httpx family is tried in order.
    These tests exercise the selection itself rather than whichever library the
    test run happens to have installed - one process can only ever have made
    one choice, so the choosing has to be testable on its own.
    """

    def test_httpx2_is_an_accepted_library(self) -> None:
        """https://github.com/python-caldav/caldav/issues/611 - httpx2 is Pydantic's
        continuation of httpx and has to be usable as a fallback."""
        from caldav.async_davclient import _ASYNC_HTTPX_CANDIDATES

        assert "httpx2" in _ASYNC_HTTPX_CANDIDATES

    def test_httpx2_is_preferred_over_httpxyz_and_httpx(self) -> None:
        """A deliberate ordering decision, not an accident of the list: httpx2 is
        the maintained continuation of httpx, httpxyz is a fork of it."""
        from caldav.async_davclient import _ASYNC_HTTPX_CANDIDATES

        order = {name: i for i, name in enumerate(_ASYNC_HTTPX_CANDIDATES)}
        assert order["httpx2"] < order["httpxyz"] < order["httpx"]

    def test_candidates_are_tried_in_order_and_stop_at_the_first_hit(self) -> None:
        from caldav.async_davclient import _import_first_available

        wanted = MagicMock(name="httpx2")
        tried = []

        def importer(name: str) -> MagicMock:
            tried.append(name)
            if name == "httpx2":
                return wanted
            raise ImportError(f"No module named {name!r}")

        assert _import_first_available(("httpxyz", "httpx2", "httpx"), importer) == (
            "httpx2",
            wanted,
        )
        assert tried == ["httpxyz", "httpx2"], "should not keep importing after a hit"

    def test_nothing_importable_yields_no_library(self) -> None:
        from caldav.async_davclient import _import_first_available

        def importer(name: str) -> None:
            raise ImportError(f"No module named {name!r}")

        assert _import_first_available(("httpxyz", "httpx2", "httpx"), importer) == (None, None)

    def test_the_missing_library_error_names_every_option(self) -> None:
        """The error is the only guidance a user gets, so it must list all of them."""
        from caldav.async_davclient import _ASYNC_HTTPX_CANDIDATES, _NO_ASYNC_LIBRARY_ERROR

        for name in ("niquests", *_ASYNC_HTTPX_CANDIDATES):
            assert name in _NO_ASYNC_LIBRARY_ERROR

    def test_the_flavour_names_the_library_that_was_imported(self) -> None:
        """_HTTPX_FLAVOUR is asserted on by name in the CI fallback jobs, so it
        has to keep saying which fork specifically got imported rather than
        just "some httpx-alike".  None means the httpx family was not reached
        at all, which is niquests' case."""
        from caldav.async_davclient import _ASYNC_HTTPX_CANDIDATES, _HTTPX_FLAVOUR, _USE_HTTPX

        assert _HTTPX_FLAVOUR in (None, *_ASYNC_HTTPX_CANDIDATES)
        assert _USE_HTTPX == (_HTTPX_FLAVOUR is not None)


class TestAsyncMkcalendarMultistatus:
    """Async twin of ``TestMkcalendarMultistatus`` in test_caldav_unit.py:
    a MKCALENDAR answered with an all-success 207 Multi-Status (Bedework 5)
    created the calendar; one reporting a failing propstat did not."""

    URL = "https://caldav.example.com/dav/user/mycal/"

    def _multistatus(self, status: str) -> bytes:
        return (
            '<multistatus xmlns="DAV:">'
            "<response><href>/dav/user/mycal</href>"
            "<propstat><prop><displayname/></prop>"
            f"<status>{status}</status>"
            "</propstat></response></multistatus>"
        ).encode()

    async def _save_calendar(self, status_code: int, content: bytes):
        from caldav import Calendar, CalendarSet

        client = AsyncDAVClient(url="https://caldav.example.com/dav/")
        client.session.request = AsyncMock(
            return_value=create_mock_response(
                content=content,
                status_code=status_code,
                reason="Multi-Status",
                headers={"Content-Type": "text/xml"},
            )
        )
        calendar_set = CalendarSet(client, url="https://caldav.example.com/dav/user/")
        calendar = Calendar(client, parent=calendar_set, name="My Calendar", id="mycal")
        return await calendar.save()

    @pytest.mark.asyncio
    async def test_all_ok_multistatus_is_a_created_calendar(self) -> None:
        calendar = await self._save_calendar(207, self._multistatus("HTTP/1.1 200 ok"))
        assert str(calendar.url) == self.URL

    @pytest.mark.asyncio
    async def test_failing_propstat_still_raises(self) -> None:
        with pytest.raises(error.MkcalendarError):
            await self._save_calendar(207, self._multistatus("HTTP/1.1 403 Forbidden"))


class TestAsyncCalendarDelete:
    """Async ``Calendar.delete()``: its wipe logic lives in
    ``_async_delete_calendar()``, and the plain DELETE in the inherited
    ``DAVObject._async_delete()``."""

    URL = "https://caldav.example.com/dav/user/mycal/"

    def _calendar(self):
        from caldav import Calendar

        client = AsyncDAVClient(url="https://caldav.example.com/dav/")
        client.delete = AsyncMock(
            return_value=DAVResponse(create_mock_response(status_code=204, reason="No Content"))
        )
        return client, Calendar(client, url=self.URL)

    @pytest.mark.asyncio
    async def test_delete_sends_one_delete(self) -> None:
        client, calendar = self._calendar()
        result = await calendar.delete(wipe=False)
        assert result is None
        client.delete.assert_awaited_once_with(self.URL)

    @pytest.mark.asyncio
    async def test_wipe_deletes_the_objects_not_the_calendar(self) -> None:
        client, calendar = self._calendar()
        objects = [MagicMock(delete=AsyncMock()), MagicMock(delete=AsyncMock())]
        calendar.search = AsyncMock(return_value=objects)
        await calendar.delete(wipe=True)
        client.delete.assert_not_awaited()
        for obj in objects:
            obj.delete.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_unsupported_delete_falls_back_to_wipe(self) -> None:
        client, calendar = self._calendar()
        client.features.set_feature("delete-calendar", {"support": "unsupported"})
        obj = MagicMock(delete=AsyncMock())
        calendar.search = AsyncMock(return_value=[obj])
        await calendar.delete()
        client.delete.assert_not_awaited()
        obj.delete.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_fragile_delete_retries_until_gone(self) -> None:
        """The retry loop re-issues the plain DELETE, not the wipe."""
        client, calendar = self._calendar()
        client.features.set_feature("delete-calendar", {"support": "fragile"})
        calendar.search = AsyncMock(side_effect=[[MagicMock()], error.NotFoundError("gone")])
        with patch("asyncio.sleep", new=AsyncMock()):
            await calendar.delete()
        ## two rounds of the loop, then the final DELETE once it is known gone
        assert client.delete.await_count == 3
        assert all(c.args == (self.URL,) for c in client.delete.await_args_list)
        assert all(c.kwargs == {"event": True} for c in calendar.search.await_args_list)


class TestAsyncGetCalendarsPropfindErrors:
    """Async twin of ``TestGetCalendarsPropfindErrors``: a failing PROPFIND
    in ``get_calendars()`` must raise, not return ``[]``, ref
    https://github.com/python-caldav/caldav/issues/741
    """

    HOME_SET_XML = b"""<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/principals/user/</d:href>
    <d:propstat>
      <d:prop><c:calendar-home-set><d:href>/calendars/user/</d:href></c:calendar-home-set></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""

    @staticmethod
    def _response(status: int, content: bytes = b"") -> DAVResponse:
        return DAVResponse(create_mock_response(content=content, status_code=status))

    async def _get_calendars(self, *responses):
        from caldav.collection import Principal

        client = AsyncDAVClient(url="https://cal.example.com/")
        principal = Principal(client=client, url="https://cal.example.com/principals/user/")
        with patch.object(client, "propfind", new=AsyncMock(side_effect=list(responses))):
            return await client.get_calendars(principal)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("status", "exc"),
        [
            (503, error.PropfindError),
            (500, error.PropfindError),
            (405, error.PropfindError),
            (404, error.NotFoundError),
        ],
    )
    async def test_home_set_propfind_failure_raises(self, status, exc) -> None:
        with pytest.raises(exc):
            await self._get_calendars(
                self._response(status), self._response(207, b"<multistatus/>")
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("status", "exc"),
        [
            (503, error.PropfindError),
            (500, error.PropfindError),
            (405, error.PropfindError),
            (404, error.NotFoundError),
        ],
    )
    async def test_calendar_list_propfind_failure_raises(self, status, exc) -> None:
        with pytest.raises(exc):
            await self._get_calendars(
                self._response(207, self.HOME_SET_XML), self._response(status)
            )

    NO_HOME_SET_XML = b"<d:multistatus xmlns:d='DAV:'/>"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [403, 404, 405, 500])
    async def test_client_url_fallback_failure_returns_empty(self, status) -> None:
        calendars = await self._get_calendars(
            self._response(207, self.NO_HOME_SET_XML),
            self._response(207, self.NO_HOME_SET_XML),
            self._response(status),
        )
        assert calendars == []

    @pytest.mark.asyncio
    async def test_principal_propfind_failure_without_home_set_raises(self) -> None:
        with pytest.raises(error.PropfindError):
            await self._get_calendars(
                self._response(207, self.NO_HOME_SET_XML),
                self._response(503),
                self._response(207, self.NO_HOME_SET_XML),
            )

    @pytest.mark.asyncio
    async def test_client_url_fallback_refused_by_auth_returns_empty(self) -> None:
        refused = error.AuthorizationError(url="https://cal.example.com/", reason="Forbidden")
        calendars = await self._get_calendars(
            self._response(207, self.NO_HOME_SET_XML),
            self._response(207, self.NO_HOME_SET_XML),
            refused,
        )
        assert calendars == []

    @pytest.mark.asyncio
    async def test_principal_refused_by_auth_without_home_set_raises(self) -> None:
        refused = error.AuthorizationError(url="https://cal.example.com/", reason="Forbidden")
        with pytest.raises(error.AuthorizationError):
            await self._get_calendars(self._response(207, self.NO_HOME_SET_XML), refused)

    @pytest.mark.asyncio
    async def test_client_url_fallback_refusal_keeps_unprompted_basic_auth(self) -> None:
        from caldav.collection import Principal

        client = AsyncDAVClient(url="https://cal.example.com/")
        principal = Principal(client=client, url="https://cal.example.com/principals/user/")
        client._unprompted_basic_tried = True
        client.auth_type = "basic"
        client.auth = auth = object()
        responses = iter([self._response(207, self.NO_HOME_SET_XML)] * 2)

        async def propfind(*largs, **kwargs):
            try:
                return next(responses)
            except StopIteration:
                ## what _raise_authorization_error() does on a 401
                client._unwind_unprompted_basic()
                raise error.AuthorizationError(
                    url="https://cal.example.com/", reason="no"
                ) from None

        with patch.object(client, "propfind", new=propfind):
            assert await client.get_calendars(principal) == []
        assert (client.auth, client.auth_type) == (auth, "basic")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "client_url",
        [
            "https://cal.example.com/principals/user/",
            "https://cal.example.com/principals/user",
            "https://cal.example.com:443/principals/user/",
            "https://user:pw@cal.example.com/principals/user/",
        ],
    )
    async def test_client_url_equal_to_principal_is_not_queried_twice(self, client_url) -> None:
        from caldav.collection import Principal

        client = AsyncDAVClient(url=client_url)
        principal = Principal(client=client, url="https://cal.example.com/principals/user/")
        responses = [self._response(207, self.NO_HOME_SET_XML)] * 2
        propfind = AsyncMock(side_effect=responses)
        with patch.object(client, "propfind", new=propfind):
            assert await client.get_calendars(principal) == []
        assert propfind.call_count == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("status", "exc"), [(503, error.PropfindError), (404, error.NotFoundError)]
    )
    async def test_calendar_set_propfind_failure_raises(self, status, exc) -> None:
        from caldav.collection import CalendarSet

        client = AsyncDAVClient(url="https://cal.example.com/")
        calendar_set = CalendarSet(client, url="https://cal.example.com/calendars/user/")
        with patch.object(client, "propfind", new=AsyncMock(return_value=self._response(status))):
            with pytest.raises(exc):
                await calendar_set.get_calendars()


class TestAsyncSyncCollectionTruncated:
    """A truncated sync-collection reply (RFC 6578 section 3.6), async.

    Mirrors TestSyncCollectionTruncated in test_caldav_unit.py;
    https://github.com/python-caldav/caldav/issues/737
    """

    def _calendar(self, *pages: bytes, path: str = "/dav/cal/"):
        from caldav.collection import Calendar

        client = AsyncDAVClient(url="https://caldav.example.com/dav/")
        client.report = AsyncMock(side_effect=[DAVResponse.from_bytes(p) for p in pages])
        calendar = Calendar(client=client, url="https://caldav.example.com" + path)
        calendar.search = AsyncMock(side_effect=AssertionError("fell back to a full fetch"))
        return client, calendar

    @pytest.mark.asyncio
    async def test_follows_the_token_until_complete(self) -> None:
        from caldav.elements import dav
        from caldav.lib.python_utilities import to_normal_str

        from .test_caldav_unit import sync_page

        client, calendar = self._calendar(
            sync_page({"a.ics": '"a1"', "b.ics": '"b1"'}, "tok-2", truncated=True),
            sync_page({"c.ics": '"c1"', "a.ics": None}, "tok-3", truncated=False),
        )
        result = await calendar.get_objects_by_sync_token("tok-1")

        assert client.report.await_count == 2
        bodies = [to_normal_str(c.args[1]) for c in client.report.call_args_list]
        assert "tok-1" in bodies[0]
        assert "tok-2" in bodies[1]
        assert result.sync_token == "tok-3"
        assert result.truncated is False
        assert sorted(str(o.url.path) for o in result) == [
            "/dav/cal/a.ics",
            "/dav/cal/b.ics",
            "/dav/cal/c.ics",
        ]
        by_name = {str(o.url.path).rsplit("/", 1)[1]: o for o in result}
        assert by_name["a.ics"].props.get(dav.GetEtag.tag) is None

    @pytest.mark.asyncio
    async def test_iteration_cap(self) -> None:
        from caldav.collection import Calendar

        from .test_caldav_unit import sync_page

        pages = [
            sync_page({f"{i}.ics": f'"e{i}"'}, f"tok-{i + 2}", truncated=True)
            for i in range(Calendar.sync_max_pages + 5)
        ]
        client, calendar = self._calendar(*pages)
        result = await calendar.get_objects_by_sync_token("tok-1")
        assert client.report.await_count == Calendar.sync_max_pages
        assert result.truncated is True
        assert len(result) == Calendar.sync_max_pages

    @pytest.mark.asyncio
    async def test_stops_when_the_token_does_not_move(self) -> None:
        from .test_caldav_unit import sync_page

        client, calendar = self._calendar(sync_page({"a.ics": '"a1"'}, "tok-1", truncated=True))
        result = await calendar.get_objects_by_sync_token("tok-1")
        assert client.report.await_count == 1
        assert result.truncated is True
        assert result.sync_token == "tok-1"

    @pytest.mark.asyncio
    async def test_507_for_another_href_is_not_a_truncation(self) -> None:
        from .test_caldav_unit import sync_page

        page = sync_page({"a.ics": '"a1"'}, "tok-2", truncated=True).replace(
            b"<D:href>/dav/cal/</D:href>", b"<D:href>/dav/othercal/</D:href>"
        )
        _, calendar = self._calendar(page)
        with pytest.raises(error.DAVError):
            await calendar.get_objects_by_sync_token("tok-1", disable_fallback=True)

    @pytest.mark.asyncio
    async def test_at_sign_in_calendar_path(self) -> None:
        from .test_caldav_unit import sync_page

        base = "/dav/u@example.com/cal/"
        client, calendar = self._calendar(
            sync_page({"a.ics": '"a1"'}, "tok-2", truncated=True, base=base),
            sync_page({"b.ics": '"b1"'}, "tok-3", truncated=False, base=base),
            path=base,
        )
        result = await calendar.get_objects_by_sync_token("tok-1", disable_fallback=True)
        assert client.report.await_count == 2
        assert result.sync_token == "tok-3"
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_sync_max_pages_below_one_still_makes_one_request(self) -> None:
        from .test_caldav_unit import sync_page

        client, calendar = self._calendar(sync_page({"a.ics": '"a1"'}, "tok-2", truncated=True))
        calendar.sync_max_pages = 0
        result = await calendar.get_objects_by_sync_token("tok-1")
        assert client.report.await_count == 1
        assert result.truncated is True

    @pytest.mark.asyncio
    async def test_sync_collection_reports_truncation(self) -> None:
        """AsyncDAVClient.sync_collection() keeps the members of a truncated page."""
        from .test_caldav_unit import sync_page

        client = AsyncDAVClient(url="https://caldav.example.com/dav/cal/")
        client.request = AsyncMock(
            return_value=DAVResponse.from_bytes(
                sync_page({"a.ics": '"a1"'}, "tok-2", truncated=True)
            )
        )
        response = await client.sync_collection(sync_token="tok-1")
        assert response.sync_truncated is True
        assert response.sync_token == "tok-2"
        assert [r.href for r in response.results] == ["/dav/cal/a.ics"]
