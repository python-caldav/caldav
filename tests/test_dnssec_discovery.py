"""
Tests for DNSSEC validation in RFC 6764 discovery.

These tests verify that the DNSSEC validation implementation works correctly,
though they may not pass on systems without proper DNSSEC support.
"""

import pytest
from unittest.mock import Mock, patch
import dns.resolver
import dns.flags

from caldav.discovery import (
    _validate_dnssec,
    _srv_lookup,
    _txt_lookup,
    discover_caldav,
    DiscoveryError,
)


def test_validate_dnssec_with_valid_signatures() -> None:
    """Test DNSSEC validation with valid RRSIG records."""
    # Create a mock DNS response with RRSIG records
    mock_response = Mock()
    mock_response.response.answer = [
        Mock(rdtype=46),  # RRSIG record type
    ]

    # Should return True when RRSIG records are present
    assert _validate_dnssec(mock_response) is True


def test_validate_dnssec_without_signatures() -> None:
    """Test DNSSEC validation fails without RRSIG records."""
    # Create a mock DNS response without RRSIG records
    mock_response = Mock()
    mock_response.response.answer = [
        Mock(rdtype=33),  # SRV record type
    ]

    # Should return False when no RRSIG records are present
    assert _validate_dnssec(mock_response) is False


def test_validate_dnssec_empty_response() -> None:
    """Test DNSSEC validation with empty response."""
    # Create a mock DNS response with no answer section
    mock_response = Mock()
    mock_response.response.answer = []

    # Should return False when no answer section
    assert _validate_dnssec(mock_response) is False


@patch('caldav.discovery.dns.resolver.Resolver')
def test_srv_lookup_with_dnssec_validation(mock_resolver_class) -> None:
    """Test SRV lookup with DNSSEC validation enabled."""
    # Create a mock response with both SRV and RRSIG records
    mock_target = Mock()
    mock_target.to_text.return_value = "caldav.example.com."
    mock_target.__str__ = Mock(return_value="caldav.example.com.")

    mock_srv_record = Mock()
    mock_srv_record.target = mock_target
    mock_srv_record.port = 443
    mock_srv_record.priority = 0
    mock_srv_record.weight = 1

    mock_response = Mock()
    mock_response.__iter__ = Mock(return_value=iter([mock_srv_record]))
    mock_response.response.answer = [
        Mock(rdtype=33),  # SRV record
        Mock(rdtype=46),  # RRSIG record
    ]

    # Mock the Resolver instance
    mock_resolver_instance = Mock()
    mock_resolver_instance.flags = None
    mock_resolver_instance.resolve.return_value = mock_response
    mock_resolver_class.return_value = mock_resolver_instance

    # Should succeed with DNSSEC validation
    results = _srv_lookup("example.com", "caldav", use_tls=True, verify_dnssec=True)

    assert len(results) == 1
    assert results[0][0] == "caldav.example.com"
    assert results[0][1] == 443
    assert results[0][2] == 0  # priority
    assert results[0][3] == 1  # weight


@patch('caldav.discovery.dns.resolver.Resolver')
def test_srv_lookup_dnssec_validation_fails(mock_resolver_class) -> None:
    """Test SRV lookup fails when DNSSEC validation detects missing signatures."""
    # Create a mock response without RRSIG records
    mock_srv_record = Mock()
    mock_srv_record.target.to_text.return_value = "caldav.example.com."
    mock_srv_record.port = 443
    mock_srv_record.priority = 0
    mock_srv_record.weight = 1

    mock_response = Mock()
    mock_response.__iter__ = Mock(return_value=iter([mock_srv_record]))
    mock_response.response.answer = [
        Mock(rdtype=33),  # SRV record only, no RRSIG
    ]

    # Mock the Resolver instance
    mock_resolver_instance = Mock()
    mock_resolver_instance.flags = None
    mock_resolver_instance.resolve.return_value = mock_response
    mock_resolver_class.return_value = mock_resolver_instance

    # Should raise DiscoveryError due to missing DNSSEC signatures
    with pytest.raises(DiscoveryError, match="DNSSEC validation failed"):
        _srv_lookup("example.com", "caldav", use_tls=True, verify_dnssec=True)


@patch('caldav.discovery.dns.resolver.Resolver')
def test_txt_lookup_with_dnssec_validation(mock_resolver_class) -> None:
    """Test TXT lookup with DNSSEC validation enabled."""
    # Create a mock response with both TXT and RRSIG records
    mock_txt_record = Mock()
    mock_txt_record.strings = [b'path=/caldav/']

    mock_response = Mock()
    mock_response.__iter__ = Mock(return_value=iter([mock_txt_record]))
    mock_response.response.answer = [
        Mock(rdtype=16),  # TXT record
        Mock(rdtype=46),  # RRSIG record
    ]

    # Mock the Resolver instance
    mock_resolver_instance = Mock()
    mock_resolver_instance.flags = None
    mock_resolver_instance.resolve.return_value = mock_response
    mock_resolver_class.return_value = mock_resolver_instance

    # Should succeed with DNSSEC validation
    result = _txt_lookup("example.com", "caldav", use_tls=True, verify_dnssec=True)

    assert result == "/caldav/"


@patch('caldav.discovery.dns.resolver.Resolver')
def test_txt_lookup_dnssec_validation_fails(mock_resolver_class) -> None:
    """Test TXT lookup fails when DNSSEC validation detects missing signatures."""
    # Create a mock response without RRSIG records
    mock_txt_record = Mock()
    mock_txt_record.strings = [b'path=/caldav/']

    mock_response = Mock()
    mock_response.__iter__ = Mock(return_value=iter([mock_txt_record]))
    mock_response.response.answer = [
        Mock(rdtype=16),  # TXT record only, no RRSIG
    ]

    # Mock the Resolver instance
    mock_resolver_instance = Mock()
    mock_resolver_instance.flags = None
    mock_resolver_instance.resolve.return_value = mock_response
    mock_resolver_class.return_value = mock_resolver_instance

    # Should raise DiscoveryError due to missing DNSSEC signatures
    with pytest.raises(DiscoveryError, match="DNSSEC validation failed"):
        _txt_lookup("example.com", "caldav", use_tls=True, verify_dnssec=True)


@patch('caldav.discovery._srv_lookup')
@patch('caldav.discovery._txt_lookup')
def test_discover_caldav_with_dnssec(mock_txt_lookup, mock_srv_lookup) -> None:
    """Test CalDAV discovery with DNSSEC validation."""
    # Mock successful SRV and TXT lookups with DNSSEC
    mock_srv_lookup.return_value = [("caldav.example.com", 443, 0, 1)]
    mock_txt_lookup.return_value = "/dav/"

    # Discover with DNSSEC enabled
    service_info = discover_caldav(
        "user@example.com",
        verify_dnssec=True,
    )

    # Verify that verify_dnssec was passed through (as positional argument)
    mock_srv_lookup.assert_called()
    args, kwargs = mock_srv_lookup.call_args
    # verify_dnssec is the 4th positional argument (domain, service_type, use_tls, verify_dnssec)
    assert len(args) >= 4
    assert args[3] is True  # verify_dnssec

    mock_txt_lookup.assert_called()
    args, kwargs = mock_txt_lookup.call_args
    # verify_dnssec is the 4th positional argument
    assert len(args) >= 4
    assert args[3] is True  # verify_dnssec

    # Verify the discovered service
    assert service_info is not None
    assert service_info.url == "https://caldav.example.com/dav/"
    assert service_info.username == "user"


def test_discover_caldav_dnssec_default_disabled() -> None:
    """Test that DNSSEC validation is disabled by default."""
    # This test verifies the parameter default without making actual DNS queries
    # We just check that the function accepts the parameter

    # Import to check function signature
    import inspect
    sig = inspect.signature(discover_caldav)

    # Check that verify_dnssec parameter exists and defaults to False
    assert 'verify_dnssec' in sig.parameters
    assert sig.parameters['verify_dnssec'].default is False
