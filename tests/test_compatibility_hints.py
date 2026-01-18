#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
Unit tests for compatibility_hints module.

Rule: None of the tests in this file should initiate any internet
communication, and there should be no dependencies on a working caldav
server for the tests in this file.
"""
import pytest

from caldav.compatibility_hints import FeatureSet


class TestFeatureSetCollapse:
    """Test the collapse method which consolidates subfeatures into parent features"""

    def test_collapse_all_subfeatures_same_value(self) -> None:
        """When all subfeatures have the same value, they should collapse into parent"""
        fs = FeatureSet()

        # Use search.recurrences.expanded which has multiple subfeatures: event, todo, exception
        fs._server_features = {
            "search.recurrences.expanded.event": {"support": "unsupported"},
            "search.recurrences.expanded.todo": {"support": "unsupported"},
            "search.recurrences.expanded.exception": {"support": "unsupported"},
        }

        fs.collapse()

        # All subfeatures should be removed and parent should have the value
        assert "search.recurrences.expanded.event" not in fs._server_features
        assert "search.recurrences.expanded.todo" not in fs._server_features
        assert "search.recurrences.expanded.exception" not in fs._server_features
        assert "search.recurrences.expanded" in fs._server_features
        assert fs._server_features["search.recurrences.expanded"] == {
            "support": "unsupported"
        }

    def test_collapse_different_values_no_collapse(self) -> None:
        """When subfeatures have different values, they should NOT collapse"""
        fs = FeatureSet()

        # Set subfeatures to different values
        fs._server_features = {
            "search.text.case-sensitive": {"support": "full"},
            "search.text.case-insensitive": {"support": "unsupported"},
            "search.text.substring": {"support": "unsupported"},
        }

        fs.collapse()

        # Subfeatures should remain, parent should not be created
        assert "search.text.case-sensitive" in fs._server_features
        assert "search.text.case-insensitive" in fs._server_features
        assert "search.text.substring" in fs._server_features
        assert "search.text" not in fs._server_features

    def test_collapse_missing_subfeature_no_collapse(self) -> None:
        """When not all subfeatures are present, should NOT collapse"""
        fs = FeatureSet()

        # Only set some subfeatures
        fs._server_features = {
            "search.text.case-sensitive": {"support": "unsupported"},
            "search.text.case-insensitive": {"support": "unsupported"},
            # Missing search.text.substring
        }

        fs.collapse()

        # Subfeatures should remain since not all are present
        assert "search.text.case-sensitive" in fs._server_features
        assert "search.text.case-insensitive" in fs._server_features
        assert "search.text" not in fs._server_features

    def test_collapse_nested_features(self) -> None:
        """Collapse should work with nested features, processing deepest first"""
        fs = FeatureSet()

        # Set up nested features - all principal-search.by-name subfeatures the same
        fs._server_features = {
            "principal-search.by-name.self": {"support": "unsupported"},
        }

        fs.collapse()

        # Since there's only one subfeature, it should collapse if parent allows it
        # Check the actual behavior based on the feature definition
        # This depends on whether principal-search.by-name has other subfeatures defined

    def test_collapse_with_behaviour_field(self) -> None:
        """Collapse should work with features that have behaviour field"""
        fs = FeatureSet()

        fs._server_features = {
            "save.duplicate-uid.cross-calendar": {
                "support": "unsupported",
                "behaviour": "silently-ignored",
            },
        }

        # Since there's only one subfeature under save.duplicate-uid,
        # check if it attempts to collapse
        fs.collapse()

        # The feature should remain as is (single subfeature shouldn't collapse)

    def test_collapse_multiple_levels(self) -> None:
        """Test collapse with multiple nesting levels"""
        fs = FeatureSet()

        # Hypothetical multi-level feature structure
        # (using search.recurrences as example which has multiple subfeatures)
        fs._server_features = {
            "search.recurrences.expanded.event": {"support": "full"},
            "search.recurrences.expanded.todo": {"support": "full"},
            "search.recurrences.expanded.exception": {"support": "full"},
        }

        fs.collapse()

        # All search.recurrences.expanded.* should collapse to search.recurrences.expanded
        assert "search.recurrences.expanded.event" not in fs._server_features
        assert "search.recurrences.expanded.todo" not in fs._server_features
        assert "search.recurrences.expanded.exception" not in fs._server_features
        assert "search.recurrences.expanded" in fs._server_features
        assert fs._server_features["search.recurrences.expanded"] == {"support": "full"}

    def test_collapse_parent_already_exists(self) -> None:
        """When parent already has a value, subfeatures shouldn't collapse if different"""
        fs = FeatureSet()

        fs._server_features = {
            "search.text": {"support": "fragile"},
            "search.text.case-sensitive": {"support": "unsupported"},
            "search.text.case-insensitive": {"support": "unsupported"},
            "search.text.substring": {"support": "unsupported"},
        }

        fs.collapse()

        # Parent has different value, so subfeatures should not collapse
        assert "search.text.case-sensitive" in fs._server_features
        assert "search.text.case-insensitive" in fs._server_features
        assert "search.text.substring" in fs._server_features
        assert fs._server_features["search.text"] == {"support": "fragile"}

    def test_collapse_parent_exists_same_value(self) -> None:
        """When parent exists with same value as subfeatures, should still collapse"""
        fs = FeatureSet()

        fs._server_features = {
            "sync-token": {"support": "unsupported"},
            "sync-token.delete": {"support": "unsupported"},
        }

        fs.collapse()

        # All have same value, so subfeature should be removed
        assert "sync-token.delete" not in fs._server_features
        assert fs._server_features["sync-token"] == {"support": "unsupported"}

    def test_collapse_empty_featureset(self) -> None:
        """Collapse should handle empty featureset without errors"""
        fs = FeatureSet()
        fs._server_features = {}

        fs.collapse()

        assert fs._server_features == {}

    def test_collapse_no_parent_features(self) -> None:
        """When features have no dots (no parent), collapse should do nothing"""
        fs = FeatureSet()
        fs._server_features = {
            "sync-token": {"support": "full"},
        }

        fs.collapse()

        # Should remain unchanged
        assert fs._server_features == {"sync-token": {"support": "full"}}

    def test_collapse_single_subfeature_no_collapse(self) -> None:
        """Single subfeature without parent value should NOT collapse"""
        fs = FeatureSet()

        # sync-token only has one subfeature: delete
        fs._server_features = {
            "sync-token.delete": {"support": "unsupported"},
        }

        fs.collapse()

        # Single subfeature should remain (no collapse unless parent has value)
        assert "sync-token.delete" in fs._server_features
        assert "sync-token" not in fs._server_features

    def test_collapse_with_complex_dict_values(self) -> None:
        """Collapse should handle complex dictionary values"""
        fs = FeatureSet()

        complex_value = {
            "support": "fragile",
            "behaviour": "time-based",
            "extra": "metadata",
        }

        fs._server_features = {
            "sync-token": complex_value.copy(),
            "sync-token.delete": complex_value.copy(),
        }

        fs.collapse()

        # Both have same value, should collapse
        assert "sync-token.delete" not in fs._server_features
        assert fs._server_features["sync-token"] == complex_value

    def test_collapse_principal_search_real_scenario(self) -> None:
        """Test user's real scenario: principal-search subfeatures with same value should collapse"""
        fs = FeatureSet()

        # Real scenario from user: both principal-search subfeatures have same unsupported value
        fs._server_features = {
            "get-current-user-principal": {"support": "full"},
            "principal-search.by-name": {
                "support": "unsupported",
                "behaviour": "Search by name failed: AuthorizationError at 'http://localhost:8802/dav/calendars/user/user1', reason Forbidden",
            },
            "principal-search.list-all": {
                "support": "unsupported",
                "behaviour": "List all principals failed: AuthorizationError at 'http://localhost:8802/dav/calendars/user/user1', reason Forbidden",
            },
        }

        fs.collapse()

        # Both principal-search subfeatures should collapse,
        # even if the behaviour message is different.
        assert "principal-search.list-all" not in fs._server_features
        assert "principal-search" in fs._server_features

    def test_independent_subfeature_not_derived(self) -> None:
        """Test that independent subfeatures (with explicit defaults) don't affect parent derivation"""
        fs = FeatureSet()

        # Scenario: create-calendar.auto is set to unsupported, but it's an independent
        # feature (has explicit default) and should NOT cause create-calendar to be
        # derived as unsupported
        fs._server_features = {
            "create-calendar.auto": {"support": "unsupported"},
        }

        # create-calendar should return its default (full), NOT derive from .auto
        result = fs.is_supported("create-calendar", return_type=dict)
        assert result == {"support": "full"}, (
            f"create-calendar should default to 'full' when only independent "
            f"subfeature .auto is set, but got {result}"
        )

        # Verify that the independent subfeature itself is still accessible
        auto_result = fs.is_supported("create-calendar.auto", return_type=dict)
        assert auto_result == {"support": "unsupported"}

    def test_hierarchical_vs_independent_subfeatures(self) -> None:
        """Test that hierarchical subfeatures derive parent, but independent ones don't"""
        fs = FeatureSet()

        # Hierarchical subfeatures: principal-search.by-name and principal-search.list-all
        # These should cause parent to derive to "unknown" when mixed
        fs.set_feature("principal-search.by-name", {"support": "unknown"})
        fs.set_feature("principal-search.list-all", {"support": "unsupported"})

        # Should derive to "unknown" due to mixed hierarchical subfeatures
        result = fs.is_supported("principal-search", return_type=dict)
        assert result == {"support": "unknown"}, (
            f"principal-search should derive to 'unknown' from mixed hierarchical "
            f"subfeatures, but got {result}"
        )

        # Now test independent subfeature: create-calendar.auto
        # This should NOT affect create-calendar parent
        fs2 = FeatureSet()
        fs2.set_feature("create-calendar.auto", {"support": "unsupported"})

        # Should return default, NOT derive from independent subfeature
        result2 = fs2.is_supported("create-calendar", return_type=dict)
        assert result2 == {"support": "full"}, (
            f"create-calendar should default to 'full' ignoring independent "
            f"subfeature .auto, but got {result2}"
        )
