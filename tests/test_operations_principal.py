"""
Tests for the Principal operations module.

These tests verify the Sans-I/O business logic for Principal operations
like URL sanitization and vCalAddress creation.
"""

from caldav.operations.principal_ops import PrincipalData
from caldav.operations.principal_ops import _create_vcal_address as create_vcal_address
from caldav.operations.principal_ops import (
    _extract_calendar_user_addresses as extract_calendar_user_addresses,
)
from caldav.operations.principal_ops import (
    _sanitize_calendar_home_set_url as sanitize_calendar_home_set_url,
)
from caldav.operations.principal_ops import (
    _should_update_client_base_url as should_update_client_base_url,
)
from caldav.operations.principal_ops import (
    _sort_calendar_user_addresses as sort_calendar_user_addresses,
)


class TestSanitizeCalendarHomeSetUrl:
    """Tests for sanitize_calendar_home_set_url function."""

    def test_returns_none_for_none(self):
        """Returns None if input is None."""
        assert sanitize_calendar_home_set_url(None) is None

    def test_quotes_at_in_path(self):
        """Quotes @ character in path URLs (owncloud quirk)."""
        url = "/remote.php/dav/calendars/user@example.com/"
        result = sanitize_calendar_home_set_url(url)
        assert "%40" in result
        assert "@" not in result

    def test_preserves_full_urls(self):
        """Does not quote @ in full URLs."""
        url = "https://example.com/dav/calendars/user@example.com/"
        result = sanitize_calendar_home_set_url(url)
        # Full URLs should be returned as-is
        assert result == url

    def test_preserves_already_quoted(self):
        """Does not double-quote already quoted URLs."""
        url = "/remote.php/dav/calendars/user%40example.com/"
        result = sanitize_calendar_home_set_url(url)
        assert result == url
        # Should not have double-encoding like %2540
        assert "%2540" not in result

    def test_preserves_normal_path(self):
        """Preserves paths without special characters."""
        url = "/calendars/default/"
        result = sanitize_calendar_home_set_url(url)
        assert result == url


class TestSortCalendarUserAddresses:
    """Tests for sort_calendar_user_addresses function."""

    def test_sorts_by_preference(self):
        """Sorts addresses by preferred attribute (highest first)."""

        class FakeElement:
            def __init__(self, text, preferred=0):
                self.text = text
                self._preferred = preferred

            def get(self, key, default=0):
                if key == "preferred":
                    return self._preferred
                return default

        addresses = [
            FakeElement("mailto:secondary@example.com", preferred=0),
            FakeElement("mailto:primary@example.com", preferred=1),
            FakeElement("mailto:tertiary@example.com", preferred=0),
        ]

        result = sort_calendar_user_addresses(addresses)

        assert result[0].text == "mailto:primary@example.com"
        # Other two maintain relative order (stable sort)

    def test_handles_missing_preferred(self):
        """Handles elements without preferred attribute."""

        class FakeElement:
            def __init__(self, text):
                self.text = text

            def get(self, key, default=0):
                return default

        addresses = [
            FakeElement("mailto:a@example.com"),
            FakeElement("mailto:b@example.com"),
        ]

        # Should not raise, treats missing as 0
        result = sort_calendar_user_addresses(addresses)
        assert len(result) == 2


class TestExtractCalendarUserAddresses:
    """Tests for extract_calendar_user_addresses function."""

    def test_extracts_text(self):
        """Extracts text from address elements."""

        class FakeElement:
            def __init__(self, text, preferred=0):
                self.text = text
                self._preferred = preferred

            def get(self, key, default=0):
                if key == "preferred":
                    return self._preferred
                return default

        addresses = [
            FakeElement("mailto:primary@example.com", preferred=1),
            FakeElement("mailto:secondary@example.com", preferred=0),
        ]

        result = extract_calendar_user_addresses(addresses)

        assert result == ["mailto:primary@example.com", "mailto:secondary@example.com"]

    def test_returns_empty_for_empty_list(self):
        """Returns empty list for empty input."""
        assert extract_calendar_user_addresses([]) == []


class TestCreateVcalAddress:
    """Tests for create_vcal_address function."""

    def test_creates_vcal_address(self):
        """Creates vCalAddress with all parameters."""
        result = create_vcal_address(
            display_name="John Doe",
            address="mailto:john@example.com",
            calendar_user_type="INDIVIDUAL",
        )

        assert str(result) == "mailto:john@example.com"
        assert result.params["cn"] == "John Doe"
        assert result.params["cutype"] == "INDIVIDUAL"

    def test_creates_without_display_name(self):
        """Creates vCalAddress without display name."""
        result = create_vcal_address(
            display_name=None,
            address="mailto:john@example.com",
        )

        assert str(result) == "mailto:john@example.com"
        assert "cn" not in result.params

    def test_creates_without_cutype(self):
        """Creates vCalAddress without calendar user type."""
        result = create_vcal_address(
            display_name="John",
            address="mailto:john@example.com",
            calendar_user_type=None,
        )

        assert str(result) == "mailto:john@example.com"
        assert result.params["cn"] == "John"
        assert "cutype" not in result.params


class TestShouldUpdateClientBaseUrl:
    """Tests for should_update_client_base_url function."""

    def test_returns_false_for_none(self):
        """Returns False for None URL."""
        assert should_update_client_base_url(None, "example.com") is False

    def test_returns_false_for_same_host(self):
        """Returns False when hostname matches."""
        assert (
            should_update_client_base_url(
                "https://example.com/calendars/",
                "example.com",
            )
            is False
        )

    def test_returns_true_for_different_host(self):
        """Returns True when hostname differs (iCloud load balancing)."""
        assert (
            should_update_client_base_url(
                "https://p123-caldav.icloud.com/calendars/",
                "caldav.icloud.com",
            )
            is True
        )

    def test_returns_false_for_relative_path(self):
        """Returns False for relative paths (no host to compare)."""
        assert (
            should_update_client_base_url(
                "/calendars/user/",
                "example.com",
            )
            is False
        )


class TestPrincipalData:
    """Tests for PrincipalData dataclass."""

    def test_creates_principal_data(self):
        """Creates PrincipalData with all fields."""
        data = PrincipalData(
            url="/principals/user/",
            display_name="John Doe",
            calendar_home_set_url="/calendars/user/",
            calendar_user_addresses=["mailto:john@example.com"],
        )

        assert data.url == "/principals/user/"
        assert data.display_name == "John Doe"
        assert data.calendar_home_set_url == "/calendars/user/"
        assert data.calendar_user_addresses == ["mailto:john@example.com"]

    def test_allows_none_values(self):
        """Allows None values for optional fields."""
        data = PrincipalData(
            url=None,
            display_name=None,
            calendar_home_set_url=None,
            calendar_user_addresses=[],
        )

        assert data.url is None
        assert data.display_name is None
        assert data.calendar_home_set_url is None
        assert data.calendar_user_addresses == []
