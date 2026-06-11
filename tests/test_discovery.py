#!/usr/bin/env python
"""
Unit tests for caldav.discovery — RFC 6764 service discovery.

No network communication; DNS and HTTP are mocked.
"""

from unittest import mock

import pytest

from caldav.discovery import ServiceInfo, _well_known_lookup, discover_service


def _make_redirect_response(location: str, status_code: int = 302):
    """Return a minimal mock HTTP response that redirects to *location*."""
    resp = mock.MagicMock()
    resp.status_code = status_code
    resp.headers = {"Location": location}
    return resp


def _make_ok_response():
    resp = mock.MagicMock()
    resp.status_code = 200
    resp.headers = {}
    return resp


class TestRequireTLSDowngradeBlocked:
    """§3.1: require_tls=True must be enforced on the well-known redirect target.

    _well_known_lookup always probes https:// but never received require_tls,
    so a same-domain redirect to http:// passed the domain-validation check and
    was returned as ServiceInfo(tls=False).  discover_service returned it
    unchecked — a misconfigured or MITM server could silently downgrade TLS.
    """

    @mock.patch("caldav.discovery.requests.get")
    @mock.patch("caldav.discovery._srv_lookup", return_value=[])
    def test_http_redirect_rejected_when_require_tls(self, _srv, mock_get):
        """discover_service(require_tls=True) must return None when the
        well-known URI redirects to a plain-HTTP URL."""
        mock_get.return_value = _make_redirect_response(
            "http://example.com/caldav/"  # same domain, but HTTP
        )

        result = discover_service("example.com", require_tls=True)

        assert result is None, f"Expected None (TLS downgrade rejected), got {result}"

    @mock.patch("caldav.discovery.requests.get")
    @mock.patch("caldav.discovery._srv_lookup", return_value=[])
    def test_http_redirect_accepted_when_require_tls_false(self, _srv, mock_get):
        """discover_service(require_tls=False) must accept an HTTP redirect."""
        mock_get.return_value = _make_redirect_response("http://example.com/caldav/")

        result = discover_service("example.com", require_tls=False)

        assert result is not None
        assert result.tls is False
        assert result.url == "http://example.com/caldav/"

    @mock.patch("caldav.discovery.requests.get")
    @mock.patch("caldav.discovery._srv_lookup", return_value=[])
    def test_https_redirect_accepted_when_require_tls(self, _srv, mock_get):
        """HTTPS redirect is always accepted regardless of require_tls."""
        mock_get.return_value = _make_redirect_response("https://caldav.example.com/dav/")

        result = discover_service("example.com", require_tls=True)

        assert result is not None
        assert result.tls is True
        assert "caldav.example.com" in result.url

    @mock.patch("caldav.discovery.requests.get")
    @mock.patch("caldav.discovery._srv_lookup", return_value=[])
    def test_cross_domain_http_redirect_also_rejected(self, _srv, mock_get):
        """A cross-domain HTTP redirect must be rejected (domain check fires first,
        but require_tls must also be a backstop)."""
        mock_get.return_value = _make_redirect_response("http://evil.attacker.com/caldav/")

        result = discover_service("example.com", require_tls=True)

        assert result is None
