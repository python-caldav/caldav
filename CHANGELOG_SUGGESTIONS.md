# Suggested CHANGELOG Additions for Unreleased Version

Based on analysis of commits between v2.1.2 and master (github/master).

## Issues and PRs Closed Since 2024-11-08

### Notable Issues Closed:

#### Long-standing Feature Requests Finally Implemented:
- #102 - Support for RFC6764 - find CalDAV URL through DNS lookup (created 2020, closed 2025-11-27) ⭐
- #311 - Google calendar - make authentication simpler and document it (created 2023, closed 2025-06-16)
- #402 - Server compatibility hints (created 2024, closed 2025-12-03)
- #463 - Try out paths to find caldav base URL (created 2025-03, closed 2025-11-10)

#### Recent Issues:
- #574 - SECURITY: check domain name on auto-discovery (2025-11-29)
- #532 - Replace compatibility flags list with compatibility matrix dict (2025-11-10)
- #461 - Path handling error with non-standard URL formats (2025-12-02)
- #434 - Search event with summary (2025-11-27)
- #401 - Some server needs explicit event or task when doing search (2025-07-19)

#### Other Notable Bug Fixes:
- #372 - Server says "Forbidden" when creating event with timezone (created 2024, closed 2025-12-03)
- #351 - `calendar.search`-method with timestamp filters yielding too much (created 2023, closed 2025-12-02)
- #340 - 507 error during collection sync (created 2023, closed 2025-12-03)
- #330 - Warning `server path handling problem` using Nextcloud (created 2023, closed 2025-05-21)
- #377 - Possibly the server has a path handling problem, possibly the URL configured is wrong (2024, closed 2025-05-06)

### PRs Merged:
- #584 - Bedework server support (2025-12-04)
- #583 - Transparent fallback for servers not supporting sync tokens (2025-12-02)
- #582 - Fix docstrings in Principal and Calendar classes (2025-12-02) - @moi90
- #581 - SOGo server support (2025-12-02)
- #579 - Sync-tokens compatibility feature flags (2025-11-29)
- #578 - Docker server testing cyrus (2025-12-02)
- #576 - Add RFC 6764 domain validation to prevent DNS hijacking attacks (2025-11-29)
- #575 - Add automated Nextcloud CalDAV/CardDAV testing framework (2025-11-29)
- #573 - Add Baikal Docker test server framework for CI/CD (2025-11-28)
- #570 - Add RFC 6764 DNS-based service discovery (2025-11-27)
- #569 - Improved substring search (2025-11-27)
- #566 - More compatibility work (2025-11-27)
- #563 - Refactoring search and filters (2025-11-19)
- #561 - Connection details in the server hints (2025-11-10)
- #560 - Python 3.14 support (2025-11-09)

### Contributors (Issues and PRs since 2024-11-08)

Many thanks to all contributors who reported issues, submitted pull requests, or provided feedback:

@ArtemIsmagilov, @cbcoutinho, @cdce8p, @dieterbahr, @dozed, @Ducking2180, @edel-macias-cubix, @erahhal, @greve, @jannistpl, @julien4215, @Kreijstal, @lbt, @lothar-mar, @mauritium, @moi90, @niccokunzmann, @oxivanisher, @paramazo, @pessimo, @Savvasg35, @seanmills1020, @siderai, @slyon, @smurfix, @soundstorm, @thogitnet, @thomasloven, @thyssentishman, @ugniusslev, @whoamiafterall, @yuwash, @zealseeker, @Zhx-Chenailuoding, @Zocker1999NET

Special acknowledgment to @tobixen for maintaining the project and implementing the majority of features and fixes in this release.

## MISSING SECTION: Fixed

The current CHANGELOG is missing a "Fixed" section. Here are the bugs fixed:

### Fixed

#### Security Fixes
- **DNS hijacking prevention in RFC 6764 auto-discovery** (#574, #576): Added domain validation to prevent attackers from redirecting CalDAV connections through DNS spoofing. The library now verifies that auto-discovered domains match the requested domain (e.g., `caldav.example.com` is accepted for `example.com`, but `evil.hacker.com` is rejected). Combined with the existing `require_tls=True` default, this significantly reduces the attack surface.

#### Search and Query Bugs
- **Search by summary property** (#434): Fixed search not filtering by summary attribute - searches with `calendar.search(summary="my event")` were incorrectly returning all events. The library now properly handles text-match filters for summary and other text properties, with automatic client-side filtering fallback for servers that don't support server-side text search.

- **Component type filtering in searches** (#401, #566): Fixed searches without explicit component type (`event=True`, `todo=True`, etc.) not working on some servers. Added workarounds for servers like Bedework that mishandle component type filters. The library now performs client-side component filtering when needed.

- **Improved substring search handling** (#569): Enhanced client-side substring matching for servers with incomplete text-match support. Searches for text properties now work consistently across all servers.

#### Path and URL Handling
- **Non-standard calendar paths** (#461): Fixed spurious "path handling problem" error messages for CalDAV servers using non-standard URL structures (e.g., `/calendars/user/` instead of `/calendars/principals/user/`). The library now handles various path formats more gracefully.

- **Auto-connect URL construction** (#463, #561): Fixed issues with automatic URL construction from compatibility hints, including proper integration with RFC 6764 discovery. The library now correctly builds URLs from domain names and compatibility hints.

#### Compatibility and Server-Specific Fixes
- **Bedework server compatibility** (#584): Added comprehensive workarounds for Bedework CalDAV server, including:
  - Component type filter issues (returns all objects when filtering for events)
  - Client-side filtering fallback for completed tasks
  - Test suite compatibility

- **SOGo server support** (#581): Added SOGo-specific compatibility hints and test infrastructure.

- **Sync token handling** (#579, #583):
  - Fixed sync token feature detection being incorrectly reported as "supported" when transparent fallback is active
  - Added `disable_fallback` parameter to `objects_by_sync_token()` for proper feature testing
  - Transparent fallback for servers without sync token support now correctly fetches full calendar without raising errors

- **FeatureSet constructor bug** (#584): Fixed bug in `FeatureSet` constructor that prevented proper copying of feature sets.

#### Logging and Error Messages
- **Downgraded HTML response log level** (#584): Changed "CRITICAL" log to "INFO" for servers returning HTML content-type on errors or empty responses, reducing noise in logs.

- **Documentation string fixes** (#582): Fixed spelling and consistency issues in Principal and Calendar class docstrings.

## Additional Notes

### Enhanced Test Coverage
The changes include significant test infrastructure improvements:
- Added Docker-based test servers: Bedework, SOGo, Cyrus, Nextcloud, Baikal
- Improved test code to verify library behavior rather than server quirks
- Many server-specific test workarounds removed thanks to client-side filtering

### Compatibility Hints Evolution
Major expansion of the compatibility hints system (`caldav/compatibility_hints.py`):
- New feature flags: `save-load.event.timezone`, `search.comp-type`, `search.text.by-uid`
- Server-specific compatibility matrices for Bedework, SOGo, Synology
- Better classification of server behaviors: "unsupported" vs "ungraceful"
- Deprecation notice added to old-style compatibility flags

### Python 3.14 Support
- Added Python 3.14 to supported versions (#560)

## Suggested CHANGELOG Format

```markdown
## [Unreleased]

### Fixed

#### Security
- **DNS hijacking prevention**: Added domain validation for RFC 6764 auto-discovery to prevent DNS spoofing attacks (#574, #576)

#### Search and Queries
- Fixed search by summary not filtering results (#434)
- Fixed searches without explicit component type on servers with incomplete support (#401, #566)
- Improved substring search handling for servers with limited text-match support (#569)

#### Server Compatibility
- Added Bedework CalDAV server support with comprehensive workarounds (#584)
- Added SOGo server support and test infrastructure (#581)
- Fixed sync token feature detection with transparent fallback (#579, #583)
- Fixed FeatureSet constructor bug preventing proper feature set copying (#584)

#### URL and Path Handling
- Fixed spurious path handling errors for non-standard calendar URL formats (#461)
- Fixed auto-connect URL construction issues with compatibility hints (#463, #561)

#### Logging
- Downgraded HTML response log from CRITICAL to INFO for better log hygiene (#584)
- Fixed spelling and consistency in Principal and Calendar docstrings (#582)

### Added

[... existing Added section content ...]

- Added `disable_fallback` parameter to `objects_by_sync_token()` for proper feature detection (#583)
- Python 3.14 support (#560)
- Docker test infrastructure for Bedework, SOGo, Cyrus servers (#584, #581, #578)

[... rest of existing content ...]
```
