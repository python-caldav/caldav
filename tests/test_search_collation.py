#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
Tests for caldav.search.CalDAVSearcher collation support

Tests that verify collation attributes are correctly passed from
icalendar-searcher to CalDAV XML queries.
"""
import pytest
from icalendar_searcher.collation import Collation

from caldav.search import _collation_to_caldav
from caldav.search import CalDAVSearcher


def test_collation_to_caldav_simple_case_sensitive() -> None:
    """Test mapping from Collation.SIMPLE (case-sensitive) to CalDAV i;octet."""
    assert _collation_to_caldav(Collation.SIMPLE, case_sensitive=True) == "i;octet"


def test_collation_to_caldav_simple_case_insensitive() -> None:
    """Test mapping from Collation.SIMPLE (case-insensitive) to CalDAV i;ascii-casemap."""
    assert (
        _collation_to_caldav(Collation.SIMPLE, case_sensitive=False)
        == "i;ascii-casemap"
    )


def test_collation_to_caldav_unicode_case_sensitive() -> None:
    """Test mapping from Collation.UNICODE (case-sensitive) to CalDAV i;octet."""
    assert _collation_to_caldav(Collation.UNICODE, case_sensitive=True) == "i;octet"


def test_collation_to_caldav_unicode_case_insensitive() -> None:
    """Test mapping from Collation.UNICODE (case-insensitive) to CalDAV i;unicode-casemap."""
    assert (
        _collation_to_caldav(Collation.UNICODE, case_sensitive=False)
        == "i;unicode-casemap"
    )


def test_collation_to_caldav_locale() -> None:
    """Test mapping from Collation.LOCALE to CalDAV fallback."""
    # Locale-specific collations are not widely supported in CalDAV,
    # so we fall back to i;ascii-casemap
    assert _collation_to_caldav(Collation.LOCALE) == "i;ascii-casemap"


def test_build_search_xml_query_default_collation() -> None:
    """Test that build_search_xml_query uses default binary collation when not specified."""
    searcher = CalDAVSearcher(event=True)
    searcher.add_property_filter("SUMMARY", "test")

    xml, comp_class = searcher.build_search_xml_query()
    xml_str = str(xml)

    # Should contain text-match with i;octet collation (binary/case-sensitive)
    assert 'collation="i;octet"' in xml_str


def test_build_search_xml_query_case_insensitive_collation() -> None:
    """Test that build_search_xml_query uses i;ascii-casemap for case-insensitive searches."""
    searcher = CalDAVSearcher(event=True)
    searcher.add_property_filter("SUMMARY", "test", case_sensitive=False)

    xml, comp_class = searcher.build_search_xml_query()
    xml_str = str(xml)

    # Should contain text-match with i;ascii-casemap collation (case-insensitive)
    assert 'collation="i;ascii-casemap"' in xml_str


def test_build_search_xml_query_explicit_simple_case_sensitive_collation() -> None:
    """Test that build_search_xml_query respects explicit SIMPLE collation with case_sensitive=True."""
    searcher = CalDAVSearcher(event=True)
    searcher.add_property_filter(
        "SUMMARY", "test", collation=Collation.SIMPLE, case_sensitive=True
    )

    xml, comp_class = searcher.build_search_xml_query()
    xml_str = str(xml)

    # Should contain text-match with i;octet collation
    assert 'collation="i;octet"' in xml_str


def test_build_search_xml_query_explicit_simple_case_insensitive_collation() -> None:
    """Test that build_search_xml_query respects explicit SIMPLE collation with case_sensitive=False."""
    searcher = CalDAVSearcher(event=True)
    searcher.add_property_filter(
        "SUMMARY", "test", collation=Collation.SIMPLE, case_sensitive=False
    )

    xml, comp_class = searcher.build_search_xml_query()
    xml_str = str(xml)

    # Should contain text-match with i;ascii-casemap collation
    assert 'collation="i;ascii-casemap"' in xml_str


def test_build_search_xml_query_unicode_collation() -> None:
    """Test that build_search_xml_query uses i;unicode-casemap for UNICODE collation (case-insensitive)."""
    searcher = CalDAVSearcher(event=True)
    searcher.add_property_filter(
        "SUMMARY", "test", collation=Collation.UNICODE, case_sensitive=False
    )

    xml, comp_class = searcher.build_search_xml_query()
    xml_str = str(xml)

    # Should contain text-match with i;unicode-casemap collation
    assert 'collation="i;unicode-casemap"' in xml_str


def test_build_search_xml_query_locale_collation() -> None:
    """Test that build_search_xml_query falls back to i;ascii-casemap for LOCALE collation."""
    searcher = CalDAVSearcher(event=True)
    searcher.add_property_filter(
        "SUMMARY", "test", collation=Collation.LOCALE, locale="de_DE"
    )

    xml, comp_class = searcher.build_search_xml_query()
    xml_str = str(xml)

    # Should contain text-match with i;ascii-casemap collation (fallback)
    assert 'collation="i;ascii-casemap"' in xml_str


def test_build_search_xml_query_multiple_properties_different_collations() -> None:
    """Test that different properties can have different collations."""
    searcher = CalDAVSearcher(event=True)
    searcher.add_property_filter("SUMMARY", "test", case_sensitive=True)  # Binary
    searcher.add_property_filter(
        "LOCATION", "room", case_sensitive=False
    )  # Case-insensitive

    xml, comp_class = searcher.build_search_xml_query()
    xml_str = str(xml)

    # Should contain both collations
    assert 'collation="i;octet"' in xml_str
    assert 'collation="i;ascii-casemap"' in xml_str


def test_build_search_xml_query_collation_with_case_sensitive() -> None:
    """Test that case_sensitive parameter works with explicit collation."""
    searcher = CalDAVSearcher(event=True)
    # SIMPLE collation with case_sensitive=True should use i;octet
    searcher.add_property_filter(
        "SUMMARY", "test", case_sensitive=True, collation=Collation.SIMPLE
    )

    xml, comp_class = searcher.build_search_xml_query()
    xml_str = str(xml)

    # Should use i;octet (case-sensitive)
    assert 'collation="i;octet"' in xml_str


def test_build_search_xml_query_todo_with_collation() -> None:
    """Test that collation works with todo searches."""
    searcher = CalDAVSearcher(todo=True)
    searcher.add_property_filter("SUMMARY", "task", case_sensitive=False)

    xml, comp_class = searcher.build_search_xml_query()
    xml_str = str(xml)

    # Should contain text-match with i;ascii-casemap collation
    assert 'collation="i;ascii-casemap"' in xml_str
    # Should be a VTODO query
    assert "VTODO" in xml_str


def test_build_search_xml_query_journal_with_collation() -> None:
    """Test that collation works with journal searches."""
    searcher = CalDAVSearcher(journal=True)
    searcher.add_property_filter("SUMMARY", "note", case_sensitive=False)

    xml, comp_class = searcher.build_search_xml_query()
    xml_str = str(xml)

    # Should contain text-match with i;ascii-casemap collation
    assert 'collation="i;ascii-casemap"' in xml_str
    # Should be a VJOURNAL query
    assert "VJOURNAL" in xml_str


def test_build_search_xml_query_description_with_collation() -> None:
    """Test that collation works with DESCRIPTION property."""
    searcher = CalDAVSearcher(event=True)
    searcher.add_property_filter("DESCRIPTION", "important", case_sensitive=False)

    xml, comp_class = searcher.build_search_xml_query()
    xml_str = str(xml)

    # Should contain text-match with i;ascii-casemap collation
    assert 'collation="i;ascii-casemap"' in xml_str
    # Should have DESCRIPTION property filter
    assert "DESCRIPTION" in xml_str


def test_build_search_xml_query_categories_with_collation() -> None:
    """Test that collation works with CATEGORIES property."""
    searcher = CalDAVSearcher(event=True)
    searcher.add_property_filter("CATEGORIES", "work", case_sensitive=False)

    xml, comp_class = searcher.build_search_xml_query()
    xml_str = str(xml)

    # Should contain text-match with i;ascii-casemap collation
    assert 'collation="i;ascii-casemap"' in xml_str
    # Should have CATEGORIES property filter
    assert "CATEGORIES" in xml_str
