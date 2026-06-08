#!/usr/bin/env python
"""
Unit tests for compatibility_hints module.

Rule: None of the tests in this file should initiate any internet
communication, and there should be no dependencies on a working caldav
server for the tests in this file.
"""

import warnings

import pytest

from caldav.compatibility_hints import VALID_SUPPORT_LEVELS, FeatureSet
from caldav.config import resolve_features as _resolve_features


class TestConfigValidation:
    """Test configuration validation in FeatureSet"""

    def test_invalid_support_level_warns(self) -> None:
        """Invalid support level should emit a warning"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            FeatureSet({"save-load.event": {"support": "invalid-level"}})
            assert len(w) == 1
            assert "invalid support level" in str(w[0].message).lower()
            assert "invalid-level" in str(w[0].message)

    def test_valid_support_levels_no_warning(self) -> None:
        """Valid support levels should not emit warnings"""
        for level in VALID_SUPPORT_LEVELS:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                FeatureSet({"save-load.event": {"support": level}})
                # Filter to only UserWarnings about support levels
                support_warnings = [x for x in w if "support level" in str(x.message).lower()]
                assert len(support_warnings) == 0, f"Level '{level}' should be valid"

    def test_unknown_feature_warns(self) -> None:
        """Unknown feature name should emit a warning"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            FeatureSet({"typo-feature-name": {"support": "full"}})
            assert len(w) == 1
            assert "unknown feature" in str(w[0].message).lower()
            assert "typo-feature-name" in str(w[0].message)

    def test_known_feature_no_warning(self) -> None:
        """Known feature names should not emit warnings"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            FeatureSet({"save-load.event": {"support": "full"}})
            # Filter to only UserWarnings about unknown features
            unknown_warnings = [x for x in w if "unknown feature" in str(x.message).lower()]
            assert len(unknown_warnings) == 0

    def test_boolean_shortcut_no_warning(self) -> None:
        """Boolean shortcuts (True/False) should not emit warnings"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            FeatureSet({"save-load.event": True})
            FeatureSet({"save-load.todo": False})
            # Filter to only UserWarnings about support levels
            support_warnings = [x for x in w if "support level" in str(x.message).lower()]
            assert len(support_warnings) == 0

    def test_string_shortcut_validates(self) -> None:
        """String shortcuts should also be validated"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            FeatureSet({"save-load.event": "bad-value"})
            assert len(w) == 1
            assert "invalid support level" in str(w[0].message).lower()


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
        assert fs._server_features["search.recurrences.expanded"] == {"support": "unsupported"}

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
        """When parent exists with same value as subfeatures, should still collapse.

        Uses a genuine *grouping* parent (principal-search.by-name has no
        explicit default); independent parents such as sync-token are
        intentionally never collapsed (see
        test_collapse_independent_parent_not_collapsed).  by-name's parent
        principal-search has a second, unset child (list-all), so the collapse
        does not cascade further up.
        """
        fs = FeatureSet()

        fs._server_features = {
            "principal-search.by-name": {"support": "unsupported"},
            "principal-search.by-name.self": {"support": "unsupported"},
        }

        fs.collapse()

        # All have same value, so subfeature should be removed
        assert "principal-search.by-name.self" not in fs._server_features
        assert fs._server_features["principal-search.by-name"] == {"support": "unsupported"}

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

    def test_collapse_single_subfeature(self) -> None:
        """Single subfeature should collapse since a grouping parent derives from children"""
        fs = FeatureSet()

        # principal-search.by-name (a grouping node) only has one subfeature: self
        fs._server_features = {
            "principal-search.by-name.self": {"support": "unsupported"},
        }

        fs.collapse()

        # Parent status is derived from the single child, so collapse is valid
        assert "principal-search.by-name" in fs._server_features
        assert "principal-search.by-name.self" not in fs._server_features

    def test_collapse_with_complex_dict_values(self) -> None:
        """Collapse should handle complex dictionary values"""
        fs = FeatureSet()

        complex_value = {
            "support": "fragile",
            "behaviour": "inconsistent",
            "extra": "metadata",
        }

        fs._server_features = {
            "principal-search.by-name": complex_value.copy(),
            "principal-search.by-name.self": complex_value.copy(),
        }

        fs.collapse()

        # Both have same value, should collapse
        assert "principal-search.by-name.self" not in fs._server_features
        assert fs._server_features["principal-search.by-name"] == complex_value

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

    def test_collapse_independent_parent_not_collapsed(self) -> None:
        """An independent parent (one with its own explicit default) is never
        folded away by its children.

        sync-token carries a default, so even when its only child
        sync-token.delete is unsupported the parent keeps its own (separately
        probed) status: the two represent distinct capabilities and must not be
        conflated.
        """
        fs = FeatureSet()
        fs._server_features = {
            "sync-token": {"support": "full"},
            "sync-token.delete": {"support": "unsupported"},
        }

        fs.collapse()

        assert fs._server_features["sync-token"] == {"support": "full"}
        assert fs._server_features["sync-token.delete"] == {"support": "unsupported"}


class TestImplicitDerivation:
    """Test is_supported() implicit derivation: parent→child, child→parent, explicit defaults.

    Covers:
    - Children without explicit defaults derive the parent value.
    - Parent set explicitly propagates down to unset children.
    - Features with explicit defaults ignore subfeature derivation.
    - Partial/incomplete child sets fall through to the feature's default.
    """

    ## TODO: the tests covering "all children" may need to be
    ## protected against future additions in compatibility_hints.py

    @pytest.mark.parametrize(
        "scenario, config, query, expected_support",
        [
            (
                "all_children_unsupported",
                {
                    "search.recurrences.expanded": {"support": "unsupported"},
                    "search.recurrences.includes-implicit": {"support": "unsupported"},
                },
                "search.recurrences",
                "unsupported",
            ),
            (
                "parent_unsupported",
                {
                    "save-load": {"support": "unsupported"},
                },
                "save-load.event",
                "unsupported",
            ),
            (
                "parent_with_explicit_default_unsupported",
                {
                    "create-calendar": {"support": "unsupported"},
                },
                "create-calendar.auto",
                "unsupported",
            ),
            (
                "all_children_supported",
                {
                    "search.recurrences.expanded": {"support": "full"},
                    "search.recurrences.includes-implicit": {"support": "full"},
                },
                "search.recurrences",
                "full",
            ),
            (
                "mixed_children",
                {
                    "search.recurrences.expanded": {"support": "unsupported"},
                    "search.recurrences.includes-implicit": {"support": "full"},
                },
                "search.recurrences",
                "unknown",
            ),
            (
                "partial_one_child_unsupported_falls_to_default",
                {
                    "search.recurrences.expanded": {"support": "unsupported"},
                },
                "search.recurrences",
                "full",  # default - partial negative info is inconclusive
            ),
            (
                "partial_one_child_supported",
                {
                    "search.recurrences.includes-implicit": {"support": "full"},
                },
                "search.recurrences",
                "full",  # any positive support → derive as supported
            ),
            (
                ## Earlier logic had it that if a node has only one child, the parent should not be affected by the child, but if there are more children and all are unsupported, the parent is automatically flipped to unsupported.  However, this special case logic should have been rendered obsolete by the new logic that every node having an explicit default is considered independent
                "independent_feature_always_trumps",
                {
                    "save-load.mutable.attendee-partstat": {"support": "unsupported"},
                    "save-load.mutable.if-match-optional": {"support": "unsupported"},
                },
                "save-load.mutable",
                "full",
            ),
            (
                "gmx_partial_unsupported_query_unset_sibling_child",
                {
                    "search.recurrences.expanded": {"support": "unsupported"},
                },
                "search.recurrences.includes-implicit.todo",
                "full",  # should NOT inherit unsupported from sibling
            ),
            (
                "parent_explicit_overrides_children",
                {
                    "search.recurrences": {"support": "fragile"},
                },
                "search.recurrences.includes-implicit.todo",
                "fragile",
            ),
            (
                "child_explicit_overrides_parent",
                {
                    "search.recurrences": {"support": "unsupported"},
                    "search.recurrences.includes-implicit.todo": {"support": "full"},
                },
                "search.recurrences.includes-implicit.todo",
                "full",
            ),
            (
                "mixed_children_incomplete_unset_sibling_falls_to_default",
                {
                    "save-load.todo": {"support": "full"},
                    "save-load.journal": {"support": "unsupported"},
                },
                "save-load.event",
                "full",  # incomplete set: cannot derive anything about unset siblings
            ),
            (
                "explicit_default_overrides_children",
                {
                    "create-calendar.auto": {"support": "unsupported"},
                    "create-calendar.set-displayname": {"support": "unsupported"},
                },
                "create-calendar",
                "full",  # this feature does not depend on the sub-features
            ),
            (
                "partial_mixed_children_query_parent_falls_to_default",
                {
                    "search.text.case-sensitive": {"support": "unsupported"},
                    "search.text.case-insensitive": {"support": "full"},
                },
                "search.text",
                "full",  # partial+mixed: cannot conclude unsupported; default applies
            ),
        ],
        ids=lambda x: x if isinstance(x, str) and "_" in x else "",
    )
    def test_derivation_matrix(
        self,
        scenario: str,
        config: dict,
        query: str,
        expected_support: str,
    ) -> None:
        fs = FeatureSet(config)
        result = fs.is_supported(query, return_type=str)
        assert result == expected_support, (
            f"Scenario '{scenario}': querying '{query}' with config {config} "
            f"expected '{expected_support}', got '{result}'"
        )


class TestResolveFeatures:
    """Test _resolve_features base+override resolution."""

    def test_none_returns_none(self) -> None:
        assert _resolve_features(None) is None

    def test_string_resolves_profile(self) -> None:
        import caldav.compatibility_hints as ch

        result = _resolve_features("synology")
        assert result is ch.synology

    def test_string_with_prefix(self) -> None:
        import caldav.compatibility_hints as ch

        result = _resolve_features("compatibility_hints.synology")
        assert result is ch.synology

    def test_dict_without_base_passes_through(self) -> None:
        features = {"search.text": {"support": "unsupported"}}
        result = _resolve_features(features)
        assert result is features

    def test_base_with_overrides(self) -> None:
        import caldav.compatibility_hints as ch

        original_sync_token = ch.synology.get("sync-token")
        features = {
            "base": "synology",
            "sync-token": "full",
            "search.text.substring": {"support": "unsupported"},
        }
        result = _resolve_features(features)
        # Should have the overrides
        assert result["sync-token"] == "full"
        assert result["search.text.substring"] == {"support": "unsupported"}
        # Should still have base features
        assert result["search.text.case-sensitive"] == {"support": "unsupported"}
        # Should not have modified the original synology dict
        assert ch.synology.get("sync-token") == original_sync_token
        assert "search.text.substring" not in ch.synology
        # Should not contain the "base" key
        assert "base" not in result

    def test_base_with_prefix(self) -> None:
        result = _resolve_features(
            {
                "base": "compatibility_hints.synology",
                "sync-token": "full",
            }
        )
        assert result["sync-token"] == "full"
        # Original base feature should be overridden
        assert result["sync-token"] != "fragile"
