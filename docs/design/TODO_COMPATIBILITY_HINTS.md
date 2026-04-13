# FeatureSet Cleanup TODO

This document records simplification opportunities found in `caldav/compatibility_hints.py`
after reviewing the `FeatureSet` class.  The class was written with a more ambitious
type-system vision (multiple feature types with different semantics, collapsible
sub-feature hierarchies) that was only partially realised.  Several methods carry dead
code or over-complexity that can now be trimmed.

## 1. Dead/buggy bool branch in `_convert_node`

**Location**: `FeatureSet._convert_node`, the final `else` branch (~line 708)

```python
else:
    ## TODO: this may be improved
    return not node.get('enable') and not node.get('behaviour') and not node.get('observed')
```

This branch handles `bool` return for non-`server-feature` types (i.e. `client-feature`,
`server-peculiarity`, `server-observation`).  The logic is **inverted**: when
`enable=False`, `not False` returns `True`, which would read a disabled client-feature as
"supported".

In practice this branch is unreachable: every `is_supported` call on features of those
types uses `return_type=dict` (e.g. `is_supported("rate-limit", dict)`,
`is_supported("search-cache", dict)`).  Nobody queries them for a bool.

**Fix**: Replace the else-branch with a guard that surfaces misuse:
```python
else:
    raise AssertionError(
        f"is_supported(return_type=bool) is not meaningful for feature type "
        f"{feature_info.get('type')!r}; use return_type=dict"
    )
```
Or simply document the restriction.

## 2. Redundant `_derive_from_subfeatures` call in `is_supported`

**Location**: `FeatureSet.is_supported`, lines ~594 and ~606

When the original feature has no dots (no parent), `_derive_from_subfeatures` is called
twice on the same `feature_` during the same lookup: once in the while-loop body (line 594)
and once in the post-loop block (line 606).  The second call (line 606) uses the original
`feature_info` but `feature_` may have walked up past the original feature.

Needs careful review; may be an off-by-one in the loop termination logic, or the two
conditions are truly independent and the second call is simply redundant.

## 3. `_old_flags` — in-progress migration, clear removal path

**Location**: `FeatureSet.__init__`, `FeatureSet.copyFeatureSet`, and ~12 server config
dicts in `compatibility_hints.py`

`_old_flags` is explicitly marked `## TODO: remove this when it can be removed`.  It is
a shim that carries forward the legacy flat-list quirk system while server configs are
being migrated to the new dotted-feature style.

`test_caldav.py:1006` still reads `self.caldav.features._old_flags` to validate that old
flags are known strings.  The test at line 1015-1016 confirms all flags are present in
`incompatibility_description`.

**Fix**: For each server dict that still has `'old_flags': [...]`, translate the listed
flags into equivalent new-style features and remove the `old_flags` key.  Once all server
dicts are migrated:
- Remove the `if feature == 'old_flags':` special-case in `copyFeatureSet`
- Remove `self._old_flags = []` from `__init__`
- Remove the `_old_flags` copy in the copy-constructor branch
- Remove the validation in `test_caldav.py`

## 4. `feature_tree` / `_dots_to_tree` — internal detail that can be simplified

**Location**: `FeatureSet.feature_tree`, `FeatureSet._dots_to_tree`

`feature_tree()` builds and caches a full nested-dict tree of all feature names.  Its
only consumer is `find_feature()`, which traverses one level of the tree to populate the
`subfeatures` key on a feature.  Building and caching a full tree to answer one-level
lookups is overkill.

**Fix**: In `find_feature`, compute subfeatures directly:
```python
prefix = feature + "."
cls.FEATURES[feature]['subfeatures'] = [
    f[len(prefix):]
    for f in cls.FEATURES
    if f.startswith(prefix) and '.' not in f[len(prefix):]
]
```
Then remove `feature_tree` and `_dots_to_tree`.  The `feature_tree` docstring already
questions its own existence ("TODO: is this in use at all?").

**Note**: Before removing `feature_tree`, confirm no external code (e.g.
`caldav-server-tester`) calls it.

## 5. `_collapse_key` — vestigial `enable`/`observed` fields

**Location**: `FeatureSet._collapse_key`

```python
return (
    feature_dict.get('support'),
    feature_dict.get('enable'),
    feature_dict.get('observed'),
)
```

The `enable` and `observed` slots exist to correctly compare `client-feature` and
`server-observation` nodes during collapse.  In practice, collapse is only ever invoked
on server-feature nodes (the only type that appears in the server config dicts, aside
from `old_flags`).  The extra slots add noise without effect.

**Fix**: Simplify to `return feature_dict.get('support')` once the broader type-system
simplification is settled.

## 6. `copyFeatureSet` — rename to `copy_feature_set`

**Location**: `FeatureSet.copyFeatureSet`

There is already a TODO comment on the method noting the camelCase name is inconsistent.
The method has no external callers (grepping the repo outside `compatibility_hints.py`
finds none); all calls originate within the class itself plus `set_feature`.

**Fix**: Rename to `copy_feature_set`.  Trivial.

## 7. Split this file

Possibly into three files (or four, with the original compatibility_hints.py being a compatibility shim only importing things from the new files).

There are three quite different things in the file now, the database of the feature names/flags, the database of server compatibility, and the match logic.

## Ordering / dependencies

Items 3 (old_flags) and 6 (rename) are independent and safe to do first.  Items 1, 2,
4, 5 are interrelated around the type-system simplification and are best tackled together.
