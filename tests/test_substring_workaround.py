#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
Tests for substring search workaround for servers that don't support it.

This test verifies that when a server doesn't support substring search
and the user explicitly requests it with operator="contains", the search
falls back to fetching all objects and filtering client-side.
"""
import pytest

from caldav.search import CalDAVSearcher


def test_explicit_operator_tracking() -> None:
    """Test that CalDAVSearcher tracks explicitly set operators."""
    searcher = CalDAVSearcher(event=True)

    # Default behavior - operator not tracked
    searcher.add_property_filter("SUMMARY", "test")
    assert "summary" not in searcher._explicit_operators

    # Explicit operator - should be tracked (keys are lowercased)
    searcher.add_property_filter("LOCATION", "room", operator="contains")
    assert "location" in searcher._explicit_operators

    # Another explicit operator
    searcher.add_property_filter("DESCRIPTION", "important", operator="==")
    assert "description" in searcher._explicit_operators


def test_no_tracking_when_operator_is_default() -> None:
    """Test that default operators are not tracked as explicit."""
    searcher = CalDAVSearcher(event=True)

    # Even though "contains" is the default, if not specified, don't track
    searcher.add_property_filter("SUMMARY", "meeting")
    assert "summary" not in searcher._explicit_operators
    assert searcher._property_operator.get("summary") == "contains"


def test_explicit_contains_vs_default_contains() -> None:
    """Test distinguishing explicit operator="contains" from default."""
    searcher = CalDAVSearcher(event=True)

    # Implicit default
    searcher.add_property_filter("SUMMARY", "test1")
    # Explicit contains
    searcher.add_property_filter("LOCATION", "test2", operator="contains")
    # Explicit equal
    searcher.add_property_filter("DESCRIPTION", "test3", operator="==")

    # Only explicitly set operators should be tracked (keys are lowercased)
    assert "summary" not in searcher._explicit_operators
    assert "location" in searcher._explicit_operators
    assert "description" in searcher._explicit_operators

    # But all have operators in _property_operator
    assert searcher._property_operator.get("summary") == "contains"
    assert searcher._property_operator.get("location") == "contains"
    assert searcher._property_operator.get("description") == "=="


def test_substring_workaround_only_for_explicit_contains() -> None:
    """Test that substring workaround only applies to explicit operator="contains"."""
    from unittest.mock import MagicMock

    # Create a mock calendar that doesn't support substring search
    calendar = MagicMock()
    calendar.client.features.is_supported = lambda feature: {
        "search.text.substring": False,
        "search.text.case-sensitive": True,
        "search.text.category": True,
        "search.combined-is-logical-and": True,
        "search.comp-type-optional": True,
    }.get(feature, True)

    searcher = CalDAVSearcher(event=True)

    # Add filter WITHOUT explicit operator (should use server default)
    searcher.add_property_filter("SUMMARY", "test1")

    # Mock the build_search_xml_query to check what gets sent
    original_build = searcher.build_search_xml_query

    def mock_build(*args, **kwargs):
        xml, comp_class = original_build(*args, **kwargs)
        xml_str = str(xml)
        # Should still contain SUMMARY filter since operator wasn't explicit
        assert "SUMMARY" in xml_str
        return xml, comp_class

    searcher.build_search_xml_query = mock_build
    calendar._request_report_build_resultlist = MagicMock(return_value=(None, []))

    # This should NOT trigger the workaround
    searcher.search(calendar)


def test_substring_workaround_applies_for_explicit_contains() -> None:
    """Test that substring workaround applies when operator="contains" is explicit."""
    from unittest.mock import MagicMock

    # Create a mock calendar that doesn't support substring search
    calendar = MagicMock()
    calendar.client.features.is_supported = lambda feature: {
        "search.text.substring": False,
        "search.text.case-sensitive": True,
        "search.text.category": True,
        "search.combined-is-logical-and": True,
        "search.comp-type-optional": True,
    }.get(feature, True)

    searcher = CalDAVSearcher(event=True)

    # Add filter WITH explicit operator="contains"
    searcher.add_property_filter("SUMMARY", "meeting", operator="contains")

    # Verify the explicit operator was tracked
    assert "summary" in searcher._explicit_operators

    # Mock _request_report_build_resultlist to capture XML
    xml_queries = []

    def capture_xml(xml, *args, **kwargs):
        xml_queries.append(str(xml))
        return (None, [])

    calendar._request_report_build_resultlist = capture_xml

    # This SHOULD trigger the workaround
    result = searcher.search(calendar)

    # Verify that at least one query was sent
    assert len(xml_queries) >= 1
    # The query sent to server should NOT contain SUMMARY filter
    # (it was removed and will be applied client-side)
    first_query = xml_queries[0].lower()
    assert "summary" not in first_query or "<c:text-match" not in first_query


def test_mixed_explicit_and_implicit_operators() -> None:
    """Test that mixing explicit and implicit operators works correctly."""
    from unittest.mock import MagicMock

    calendar = MagicMock()
    calendar.client.features.is_supported = lambda feature: {
        "search.text.substring": False,
        "search.text.case-sensitive": True,
        "search.text.category": True,
        "search.combined-is-logical-and": True,
        "search.comp-type-optional": True,
    }.get(feature, True)

    searcher = CalDAVSearcher(event=True)

    # Implicit operator (server default behavior)
    searcher.add_property_filter("SUMMARY", "meeting")
    # Explicit contains (client-side filtering)
    searcher.add_property_filter("LOCATION", "room", operator="contains")
    # Explicit equals (should still go to server)
    searcher.add_property_filter("STATUS", "CONFIRMED", operator="==")

    # Keys are lowercased
    assert "summary" not in searcher._explicit_operators
    assert "location" in searcher._explicit_operators
    assert "status" in searcher._explicit_operators

    original_build = searcher.build_search_xml_query

    def check_build(*args, **kwargs):
        xml, comp_class = original_build(*args, **kwargs)
        xml_str = str(xml)
        # SUMMARY should be in the query (implicit, server decides)
        # LOCATION should NOT be in query (explicit contains, removed)
        # STATUS should be in the query (explicit ==, supported)
        # Note: Properties are lowercased in internal storage
        return xml, comp_class

    searcher.build_search_xml_query = check_build
    calendar._request_report_build_resultlist = MagicMock(return_value=(None, []))

    searcher.search(calendar)
