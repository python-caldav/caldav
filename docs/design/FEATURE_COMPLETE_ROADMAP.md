# Feature-Complete CalDAV Library Roadmap

**Created:** 2026-01-28
**Author:** AI-generated based on RFC analysis and open issues
**Status:** Planning document for work after issue #599 completion
**Branch:** v3.0-dev

## Overview

This document outlines the work needed to make the caldav library a **feature-complete CalDAV client** per the relevant IETF RFCs. It is intended as a continuation of the roadmap in issue #599, covering features beyond the v3.0 and v3.2 releases.

### Scope

The caldav library already implements:
- Core CalDAV (RFC 4791)
- Basic scheduling (RFC 6638)
- Service discovery (RFC 6764)
- WebDAV sync (RFC 6578)
- Extensive search capabilities
- Async support

This roadmap covers the **remaining gaps** to achieve full RFC compliance and addresses open feature requests.

---

## Phase 1: RFC Compliance - Core Features

### 1.1 WebDAV Access Control (RFC 3744) - ACL Support

**Priority:** High
**Estimated effort:** 40-60 hours
**RFC:** [RFC 3744](https://www.rfc-editor.org/rfc/rfc3744)

Current state: The library has basic principal support but lacks ACL manipulation.

**Tasks:**
- [ ] Implement ACL REPORT for reading access control lists
- [ ] Implement ACL method for setting permissions
- [ ] Support standard privileges: `DAV:read`, `DAV:write`, `DAV:read-acl`, `DAV:write-acl`
- [ ] Support CalDAV-specific privileges: `CALDAV:read-free-busy`
- [ ] Add principal search improvements
- [ ] Implement inherited ACL support
- [ ] Add helper methods for common permission patterns (read-only, read-write, owner)

**Related issues:** None currently open

---

### 1.2 Improved Scheduling (RFC 6638)

**Priority:** High
**Estimated effort:** 40 hours (partially covered in #599 for v3.2)
**RFC:** [RFC 6638](https://www.rfc-editor.org/rfc/rfc6638)

The v3.2 roadmap covers basic scheduling improvements. Additional work for full compliance:

**Tasks:**
- [ ] Complete Schedule-Tag header support (`If-Schedule-Tag-Match`)
- [ ] Full iTIP method support: REQUEST, REPLY, CANCEL, ADD, REFRESH, COUNTER, DECLINECOUNTER
- [ ] Implicit scheduling with `SCHEDULE-AGENT` parameter handling
- [ ] `SEQUENCE` property management per iTIP requirements
- [ ] Better conflict detection and resolution
- [ ] Delegation support for scheduling
- [ ] Add `organizer.change_status()` and similar convenience methods

**Related issues:** #524, #399, #596, #544

---

### 1.3 Calendar Availability (RFC 7953)

**Priority:** Medium
**Estimated effort:** 16-24 hours
**RFC:** [RFC 7953](https://www.rfc-editor.org/rfc/rfc7953)
**Related issue:** #425

**Tasks:**
- [ ] Implement `VAVAILABILITY` component support
- [ ] Support `AVAILABLE` subcomponents
- [ ] Add availability query methods to Principal
- [ ] Integrate with free/busy lookups
- [ ] Create `Availability` class similar to Event/Todo
- [ ] Add server feature detection for availability support

---

### 1.4 Extended iCalendar Properties (RFC 7986)

**Priority:** Medium
**Estimated effort:** 8-12 hours
**RFC:** [RFC 7986](https://www.rfc-editor.org/rfc/rfc7986)

**Tasks:**
- [ ] Support calendar-level properties: `NAME`, `DESCRIPTION`, `COLOR`, `REFRESH-INTERVAL`, `SOURCE`
- [ ] Support component properties: `IMAGE`, `CONFERENCE`
- [ ] Add helper methods: `calendar.set_color()`, `calendar.set_name()`
- [ ] Map to/from CalDAV properties where applicable

---

## Phase 2: Enhanced Search and Sync

### 2.1 Negated Searches

**Priority:** Medium
**Estimated effort:** 12-16 hours
**Related issue:** #568

**Tasks:**
- [ ] Add `negate="yes"` attribute support in text-match filters
- [ ] Update `CalDAVSearcher` to support `!=` operator
- [ ] Add server compatibility detection
- [ ] Implement client-side fallback filtering for non-supporting servers
- [ ] Unit and functional tests

---

### 2.2 Improved Collation Support

**Priority:** Low
**Estimated effort:** 8-12 hours
**Related issue:** #567

**Tasks:**
- [ ] Better support for `i;unicode-casemap` collation
- [ ] Locale-aware case-insensitive matching
- [ ] Server capability detection for collation support
- [ ] Documentation of collation behavior per server

---

### 2.3 Multiget Optimization

**Priority:** Medium
**Estimated effort:** 8 hours
**Related issue:** #487

**Tasks:**
- [ ] Use `calendar-multiget` REPORT when server doesn't return object data in search
- [ ] Batch retrieval of multiple objects
- [ ] Configurable batch sizes

---

## Phase 3: Advanced Features

### 3.1 Managed Attachments (RFC 8607)

**Priority:** Low
**Estimated effort:** 24-32 hours
**RFC:** [RFC 8607](https://www.rfc-editor.org/rfc/rfc8607)

**Tasks:**
- [ ] Detect server support for `calendar-managed-attachments`
- [ ] Implement POST operations for add/update/remove attachments
- [ ] Support `MANAGED-ID` parameter
- [ ] Add `event.add_attachment()`, `event.remove_attachment()` methods
- [ ] Handle `FMTTYPE`, `FILENAME`, `SIZE` parameters

---

### 3.2 Calendar Sharing

**Priority:** Medium
**Estimated effort:** 32-40 hours
**Spec:** [draft-pot-caldav-sharing](https://datatracker.ietf.org/doc/html/draft-pot-caldav-sharing)

Note: This is a draft standard but widely implemented by major servers.

**Tasks:**
- [ ] Detect shared calendars
- [ ] Enumerate calendars shared with user
- [ ] Share calendar with other users
- [ ] Accept/decline share invitations
- [ ] Per-user calendar data (separate alarms per user)
- [ ] Remove share access

---

### 3.3 Extended MKCOL (RFC 5689)

**Priority:** Low
**Estimated effort:** 4-8 hours
**RFC:** [RFC 5689](https://www.rfc-editor.org/rfc/rfc5689)

**Tasks:**
- [ ] Support extended MKCOL as alternative to MKCALENDAR
- [ ] Set calendar properties atomically during creation
- [ ] Detect server support

---

### 3.4 Quota Support (RFC 4331)

**Priority:** Low
**Estimated effort:** 4-8 hours
**RFC:** [RFC 4331](https://www.rfc-editor.org/rfc/rfc4331)

**Tasks:**
- [ ] Add `calendar.get_quota()` method
- [ ] Support `DAV:quota-available-bytes` and `DAV:quota-used-bytes`
- [ ] Handle HTTP 507 (Insufficient Storage) gracefully

---

## Phase 4: Robustness and Edge Cases

### 4.1 Collision Avoidance

**Priority:** High
**Estimated effort:** 16-24 hours
**Related issue:** #152

**Tasks:**
- [ ] Robust ETag-based collision detection
- [ ] Proper `If-Match` / `If-None-Match` header usage
- [ ] Handle UID vs path name mismatches
- [ ] Race condition mitigation
- [ ] Clear error messages for conflicts

---

### 4.2 Recurrence Handling Improvements

**Priority:** High
**Estimated effort:** 24-32 hours
**Related issues:** #398, #597, #598

**Tasks:**
- [ ] Helper methods for identifying recurrence states
- [ ] Intelligent deletion of single recurrences
- [ ] Better RECURRENCE-ID handling
- [ ] Documentation and examples for recurrence editing
- [ ] Timezone-aware recurrence expansion
- [ ] Tests for complex recurrence scenarios

---

### 4.3 PROPFIND Redirect Handling

**Priority:** Low
**Estimated effort:** 4-8 hours
**Related issue:** #552

**Tasks:**
- [ ] Follow 3xx redirects on PROPFIND
- [ ] Update internal URLs after redirect
- [ ] Prevent redirect loops

---

### 4.4 Alarm Support

**Priority:** Medium
**Estimated effort:** 12-16 hours
**Related issue:** #132

**Tasks:**
- [ ] Add `event.add_alarm()`, `event.remove_alarm()` methods
- [ ] Support VALARM with ACTION (DISPLAY, AUDIO, EMAIL)
- [ ] Trigger types: relative (before/after) and absolute
- [ ] Snooze/dismiss support where servers allow

---

## Phase 5: Service Discovery and Security

### 5.1 DNSSEC Validation

**Priority:** Medium
**Estimated effort:** 16-24 hours
**Related issue:** #571
**RFC:** [RFC 6764 Section 8](https://www.rfc-editor.org/rfc/rfc6764#section-8)

**Tasks:**
- [ ] Add optional DNSSEC validation for SRV/TXT lookups
- [ ] Integrate with dnspython DNSSEC support
- [ ] Configuration option for security policy
- [ ] Clear warnings when DNSSEC unavailable
- [ ] Documentation of security implications

---

### 5.2 Server Auto-Detection Improvements

**Priority:** Medium
**Estimated effort:** 16-24 hours
**Related issue:** #600

**Tasks:**
- [ ] Auto-detect server quirks on first connection
- [ ] Cache detected quirks
- [ ] Improve feature detection heuristics
- [ ] Better handling of unknown servers

---

## Phase 6: Alternative Formats (Optional)

### 6.1 jCal Support (RFC 7265)

**Priority:** Low
**Estimated effort:** 16-24 hours
**RFC:** [RFC 7265](https://www.rfc-editor.org/rfc/rfc7265)

**Tasks:**
- [ ] Accept `application/calendar+json` responses
- [ ] Convert jCal to iCalendar internally
- [ ] Optional: produce jCal output

---

### 6.2 xCal Support (RFC 6321)

**Priority:** Low
**Estimated effort:** 16-24 hours
**RFC:** [RFC 6321](https://www.rfc-editor.org/rfc/rfc6321)

**Tasks:**
- [ ] Accept `application/calendar+xml` responses
- [ ] Convert xCal to iCalendar internally
- [ ] Optional: produce xCal output

---

## Phase 7: Testing and Documentation

### 7.1 Test Coverage Expansion

**Priority:** High
**Estimated effort:** 40+ hours (ongoing)
**Related issues:** #93, #45, #595

**Tasks:**
- [ ] Increase unit test coverage to 90%+
- [ ] Add DAViCal docker container for testing (#595)
- [ ] Add more server docker containers
- [ ] Edge case testing for all RFCs
- [ ] Performance regression tests

---

### 7.2 Server Documentation

**Priority:** Medium
**Estimated effort:** 24-40 hours
**Related issue:** #120

**Tasks:**
- [ ] Document setup and quirks for each major server:
  - [ ] Nextcloud
  - [ ] Radicale
  - [ ] Baikal
  - [ ] DAViCal
  - [ ] Apple Calendar Server
  - [ ] Zimbra
  - [ ] Bedework
  - [ ] Google Calendar
  - [ ] iCloud
  - [ ] Fastmail
  - [ ] Microsoft 365 (if CalDAV supported)
- [ ] Troubleshooting guides per server
- [ ] Known limitations documentation

---

### 7.3 Example Code and Tutorials

**Priority:** Medium
**Estimated effort:** 16-24 hours
**Related issue:** #513, #541

**Tasks:**
- [ ] Update all examples to use icalendar `.new()` method
- [ ] Add howto guides for common tasks
- [ ] Scheduling example code
- [ ] Recurrence editing examples
- [ ] Service discovery examples
- [ ] Migration guide from v2.x to v3.x

---

## Phase 8: Code Quality and Maintenance

### 8.1 Deprecation Cleanup

**Priority:** Medium
**Estimated effort:** 8-16 hours
**Related issues:** #585, #482, #128

**Tasks:**
- [ ] Remove old incompatibility flags (#585)
- [ ] Obsolete `get_duration`, `get_due`, `get_dtend` (#482)
- [ ] Review `DAVObject.name` removal (#128)

---

### 8.2 Test Infrastructure

**Priority:** Medium
**Estimated effort:** 16-24 hours
**Related issues:** #577, #509, #593, #518

**Tasks:**
- [ ] Clean up `tests/conf.py` (#577)
- [ ] Refactor test configuration (#509)
- [ ] Refactor setup/teardown methods (#593)
- [ ] Mute expected error logging, break on unexpected (#518)

---

### 8.3 Search Module Refactoring

**Priority:** Low
**Estimated effort:** 16-24 hours
**Related issue:** #580

**Tasks:**
- [ ] Refactor `search.py` for better maintainability
- [ ] Separate concerns more cleanly
- [ ] Improve documentation

---

## Summary: Effort Estimates by Priority

| Priority | Phase | Estimated Hours |
|----------|-------|-----------------|
| High | ACL Support (1.1) | 40-60 |
| High | Collision Avoidance (4.1) | 16-24 |
| High | Recurrence Improvements (4.2) | 24-32 |
| High | Test Coverage (7.1) | 40+ |
| Medium | Availability RFC 7953 (1.3) | 16-24 |
| Medium | iCalendar Properties RFC 7986 (1.4) | 8-12 |
| Medium | Negated Searches (2.1) | 12-16 |
| Medium | Calendar Sharing (3.2) | 32-40 |
| Medium | Alarm Support (4.4) | 12-16 |
| Medium | DNSSEC (5.1) | 16-24 |
| Medium | Server Auto-Detection (5.2) | 16-24 |
| Medium | Server Documentation (7.2) | 24-40 |
| Medium | Examples/Tutorials (7.3) | 16-24 |
| Medium | Deprecation Cleanup (8.1) | 8-16 |
| Medium | Test Infrastructure (8.2) | 16-24 |
| Low | Multiget Optimization (2.2) | 8 |
| Low | Collation Support (2.2) | 8-12 |
| Low | Managed Attachments (3.1) | 24-32 |
| Low | Extended MKCOL (3.3) | 4-8 |
| Low | Quota Support (3.4) | 4-8 |
| Low | PROPFIND Redirects (4.3) | 4-8 |
| Low | jCal/xCal (6.1-6.2) | 32-48 |
| Low | Search Refactoring (8.3) | 16-24 |

**Total estimated effort:** 380-560 hours (depending on scope and depth)

---

## Version Planning Suggestion

Based on the roadmap, suggested version milestones after v3.2:

### v3.3 - Robustness Release
- Collision avoidance (#152)
- Recurrence handling improvements (#398, #597, #598)
- PROPFIND redirect handling (#552)

### v3.4 - Search & Sync Release
- Negated searches (#568)
- Multiget optimization (#487)
- Improved collation (#567)

### v3.5 - Extended Features Release
- Alarm support (#132)
- RFC 7986 iCalendar properties
- RFC 7953 Availability (#425)

### v4.0 - ACL & Sharing Release
- Full ACL support (RFC 3744)
- Calendar sharing (draft-pot-caldav-sharing)
- Managed attachments (RFC 8607)
- Major API review

### v4.1 - Security & Discovery Release
- DNSSEC validation (#571)
- Server auto-detection improvements (#600)

---

## References

### Core Standards
- [RFC 4791 - CalDAV](https://www.rfc-editor.org/rfc/rfc4791)
- [RFC 6638 - CalDAV Scheduling](https://www.rfc-editor.org/rfc/rfc6638)
- [RFC 4918 - WebDAV](https://www.rfc-editor.org/rfc/rfc4918)
- [RFC 3744 - WebDAV ACL](https://www.rfc-editor.org/rfc/rfc3744)
- [RFC 5545 - iCalendar](https://www.rfc-editor.org/rfc/rfc5545)

### Extensions
- [RFC 6764 - Service Discovery](https://www.rfc-editor.org/rfc/rfc6764)
- [RFC 6578 - WebDAV Sync](https://www.rfc-editor.org/rfc/rfc6578)
- [RFC 7953 - Calendar Availability](https://www.rfc-editor.org/rfc/rfc7953)
- [RFC 7986 - New iCalendar Properties](https://www.rfc-editor.org/rfc/rfc7986)
- [RFC 8607 - Managed Attachments](https://www.rfc-editor.org/rfc/rfc8607)

### Related
- [RFC 5546 - iTIP](https://www.rfc-editor.org/rfc/rfc5546)
- [RFC 6321 - xCal](https://www.rfc-editor.org/rfc/rfc6321)
- [RFC 7265 - jCal](https://www.rfc-editor.org/rfc/rfc7265)
- [CalConnect Developer Guide](https://devguide.calconnect.org/)

---

*This roadmap was generated with AI assistance based on analysis of CalDAV RFCs and the python-caldav issue tracker.*
