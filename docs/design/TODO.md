# Known Issues and TODO Items

## Server-side negated searches

`search()` decides the `!=` / `<>`, `!contains` and `def` operators client-side and leaves them out of the server query (https://github.com/python-caldav/caldav/issues/568).  A caldav-server-tester probe for `negate-condition` support, and the compatibility_hints flag it would feed, would let `search()` send `!contains` as a negated `text-match` to the servers that honour it.

## Calendar cleanup in integration tests

For servers where calendars cannot be created, the test will take the first available calendar it finds and wipe it.  That is not acceptable without the user explicitly configuring that this is OK.

## Nextcloud UNIQUE Constraint Violations

**Status**: Known issue, needs upstream investigation
**Priority**: Low (doesn't block caldav work)

### Problem
Nextcloud does not allow reusing a UID after deletion — the internal database retains the constraint even after the CalDAV object is deleted.  This causes intermittent UNIQUE constraint violation errors (500) when `ServerQuirkChecker.check_all()` deletes and recreates test objects with the same UID.

This violates CalDAV RFC expectations and is a Nextcloud bug.  Restarting the Docker container resolves it by clearing internal state.

### Next Steps
1. Search Nextcloud issue tracker for similar reports
2. File upstream bug report with reproduction steps
3. Consider adding server quirk detection in caldav_server_tester
4. Document workaround: avoid UID reuse with Nextcloud, or restart container between test runs

## Switch CHANGELOG to towncrier

**When**: right after the next release (3.5), so the Unreleased section is empty.

Parallel PRs (third-party and own) keep conflicting in `CHANGELOG.md`.  Use towncrier fragments (`changes/<issue>.<type>.md`, `changes/+slug.<type>.md` without an issue) instead.  Tested OK with towncrier 26.9; nested lists in fragments render fine.

Requirements kept: `towncrier build --version X` writes plain markdown, so the CHANGELOG can still be hand-edited and an executive summary added before the release commit.

Steps:
1. `[tool.towncrier]` in `pyproject.toml`: `directory = "changes"`, `start_string = "<!-- towncrier release notes start -->\n"` (marker after the "Meta" section), `title_format = "## [{version}] - {project_date}"`, `issue_format` pointing at GitHub issues, and one `[[tool.towncrier.type]]` per Keep-a-Changelog section (Breaking changes, Added, Changed, Deprecated, Removed, Fixed, Security).
2. `changes/README.md` explaining file naming.
3. Update CONTRIBUTING.md (commit types section and "Add an entry in the CHANGELOG.md").
4. Optional: `towncrier check` in CI, with a `no-changelog` label for test/docs-only PRs.
5. Release checklist: `towncrier build --version X` → reorder/hand-edit → add summary → commit → tag.

Known downsides: no Unreleased section visible on master (consider `sphinxcontrib-towncrier`), entries sorted by issue number rather than importance, `(issue URL)` appended to entries — use `+slug` names where URLs are cited inline.
