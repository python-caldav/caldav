# Feature-Complete CalDAV Library Roadmap

- **Created:** 2026-01-28, **updated** 2026-08-24
- **Author:** AI-generated and human-edited based on RFC analysis and open issues
- **Status:** Planning document for work after issue [#599](https://github.com/python-caldav/caldav/issues/599) completion

## Overview

This document outlines the work needed to make the caldav library a **feature-complete CalDAV client** per the relevant IETF RFCs. It is intended as a continuation of the roadmap in issue [#599](https://github.com/python-caldav/caldav/issues/599), covering features beyond v3.3.

### Scope

The caldav library already implements:
- Core CalDAV (RFC 4791)
- Basic scheduling (RFC 6638)
- Service discovery (RFC 6764)
- WebDAV sync (RFC 6578)
- Extensive search capabilities
- Async support
- JMAP (`caldav/jmap/`) — not a CalDAV RFC, and not covered by this roadmap

This roadmap covers the **remaining gaps** to achieve full RFC compliance and addresses open feature requests.

Items are ordered by phase and priority; which release they land in is decided when the release is planned.  Work that has to break the API is marked as v4.0 material where it appears.

### Funding, and how it relates to these estimates

Part of this roadmap is funded through the [NGI Zero Core](https://nlnet.nl/core)
fund, established by [NLnet](https://nlnet.nl/) with financial support from the
European Commission's [Next Generation Internet](https://ngi.eu/) programme, under
the aegis of DG Communications Networks, Content and Technology.  The MoU allocates
365 hours to this library.  Three things about that number need saying plainly,
because a reader who puts the MoU's line items next to this document's estimates
will otherwise draw the wrong conclusion.

TODO: add the MoU's signing date and a public link to the NLnet project page here
as soon as they exist.  Until then the MoU figures below cannot be checked against
anything outside this repository.

**1. The MoU's estimates are more optimistic than this document's, deliberately so.**
For the seven items below, the MoU line is at or below this roadmap's *low*
estimate, and for several it is far below:

| Item | MoU | This roadmap |
|---|---|---|
| 1.1 WebDAV ACL (RFC 3744) | 16 h | 40-60 h |
| 1.2 Improved scheduling (RFC 6638) | 6 h | 40 h |
| 1.3 Calendar availability (RFC 7953) | 8 h | 16-24 h |
| 2.1 Negated searches | 6 h | 12-16 h |
| 4.2 Recurrence handling | 20 h | 24-32 h |
| 4.3 + 4.4 + 5.2 (as one "other issues" line) | 15 h | 32-48 h |
| 7.1 + 8.1 + 8.2 + 8.3 (as one "code quality" line) | 30 h | 80+ h |

The rest — RFC 7986, multiget, collations, managed attachments, sharing, extended
MKCOL, quota, WebDAV Push, collision avoidance, retry logic — sits inside this
roadmap's ranges.

Two MoU lines run the other way, and they are why chapter 7 looks unfunded here:
documentation is funded at 100 hours — 60 for keeping the documentation in sync
with the work above, plus two 20-hour lines for documentation issues and for
further documentation work — against this roadmap's 40-64 hours for **7.2 Server
Documentation** and **7.3 Example Code and Tutorials**.  A further 4-hour line
covers continued work on incoming issues and compatibility, which is ongoing
maintenance rather than a roadmap item and has no counterpart in this document.

The gap is not an error in either document.  The MoU funds *a useful increment* of
each item, not each item to completion; this roadmap estimates each item to
completion.  A funded line of 16 hours against an estimate of 40-60 means the ACL
work will be started and partly delivered, not that it will be finished for 16
hours.  Where an item cannot be usefully partly delivered, that will be noted on
the item itself.

**2. This roadmap begins after v3.3.0, and the v3.3.0 release is funded separately.**
The MoU carries a 12-hour line for cutting that release.  It is not an item in this
document, which is scoped as work *beyond* v3.3 — but it is charged to the same
grant, and it comes first.

**3. Some of this roadmap is deliberately outside the funded scope.**  Nothing in
the MoU corresponds to:

- **5.1 DNSSEC validation** — dropped from the funded scope as a deliberate call by
  the maintainer: low value for the money, given how few deployments would benefit
- **5.3 TLS enforcement** — small enough to fall out of other work
- **Phase 6, jCal and xCal** — covered elsewhere in the ecosystem; the MoU funds
  xCal support in the `icalendar` library and an `icalendar-converter` package
- **8.4 Internal refactoring backlog** and **8.5 Packaging and HTTP dependencies** —
  wanted, unfunded

The MoU's own summary line for this library says it "covers only parts of the
roadmap", and that is the accurate reading: it is a selection across chapters 1-5,
7 and 8, not a prefix ending at some chapter number.

---

## Phase 1: RFC Compliance - Core Features

### 1.1 WebDAV Access Control (RFC 3744) - ACL Support

- **Priority:** High
- **Estimated effort:** 40-60 hours
- **RFC:** [RFC 3744](https://datatracker.ietf.org/doc/html/rfc3744)
- **Related issues:** [#699](https://github.com/python-caldav/caldav/issues/699), [#701](https://github.com/python-caldav/caldav/issues/701) (3.2 — the sharing alternative to the same problem)

Current state: The library has basic principal support but lacks ACL manipulation.

**Tasks:**
- [ ] Implement ACL REPORT for reading access control lists
- [ ] Implement ACL method for setting permissions
- [ ] Support standard privileges: `DAV:read`, `DAV:write`, `DAV:read-acl`, `DAV:write-acl`
- [ ] Support CalDAV-specific privileges: `CALDAV:read-free-busy`
- [ ] Add principal search improvements
- [ ] Implement inherited ACL support
- [ ] Add helper methods for common permission patterns (read-only, read-write, owner)

---

### 1.2 Improved Scheduling (RFC 6638)

- **Priority:** High
- **Estimated effort:** 40 hours (partially covered in [#599](https://github.com/python-caldav/caldav/issues/599) for v3.2)
- **RFC:** [RFC 6638](https://datatracker.ietf.org/doc/html/rfc6638)
- **Related issues:** [#524](https://github.com/python-caldav/caldav/issues/524), [#399](https://github.com/python-caldav/caldav/issues/399), [#596](https://github.com/python-caldav/caldav/issues/596), [#544](https://github.com/python-caldav/caldav/issues/544) — all four are now closed; what remains here is the iTIP/`SCHEDULE-AGENT`/delegation work, which has no issue of its own

The v3.2 roadmap covers basic scheduling improvements. Additional work for full compliance:

**Tasks:**
- [x] Complete Schedule-Tag header support (`If-Schedule-Tag-Match`) — **done in v3.2.0**, see [#660](https://github.com/python-caldav/caldav/issues/660)
- [ ] Full iTIP method support: REQUEST, REPLY, CANCEL, ADD, REFRESH, COUNTER, DECLINECOUNTER
- [ ] Implicit scheduling with `SCHEDULE-AGENT` parameter handling
- [x] `SEQUENCE` property management per iTIP requirements — **done in v3.2.0**: absent SEQUENCE is treated as 0 (RFC 5546 2.1.4), and `save(increase_seqno=False)` opts out
- [ ] Better conflict detection and resolution
- [ ] Delegation support for scheduling
- [x] Add `organizer.change_status()` and similar convenience methods — **done**: `change_attendee_status()`, `accept_invite()`, `decline_invite()`, `tentatively_accept_invite()`, `add_organizer()`

---

### 1.3 Calendar Availability (RFC 7953)

- **Priority:** Medium
- **Estimated effort:** 16-24 hours
- **RFC:** [RFC 7953](https://datatracker.ietf.org/doc/html/rfc7953)
- **Related issue:** [#425](https://github.com/python-caldav/caldav/issues/425)

**Tasks:**
- [ ] Implement `VAVAILABILITY` component support
- [ ] Support `AVAILABLE` subcomponents
- [ ] Add availability query methods to Principal
- [ ] Integrate with free/busy lookups
- [ ] Create `Availability` class similar to Event/Todo
- [ ] Add server feature detection for availability support

---

### 1.4 Extended iCalendar Properties (RFC 7986)

- **Priority:** Medium
- **Estimated effort:** 8-12 hours
- **RFC:** [RFC 7986](https://datatracker.ietf.org/doc/html/rfc7986)

**Tasks:**
- [ ] Support calendar-level properties: `NAME`, `DESCRIPTION`, `COLOR`, `REFRESH-INTERVAL`, `SOURCE`
- [ ] Support component properties: `IMAGE`, `CONFERENCE`
- [ ] Add helper methods: `calendar.set_color()`, `calendar.set_name()`
- [ ] Map to/from CalDAV properties where applicable

---

## Phase 2: Enhanced Search and Sync

### 2.1 Negated Searches

- **Priority:** Medium
- **Estimated effort:** 12-16 hours
- **Related issue:** [#568](https://github.com/python-caldav/caldav/issues/568)

**Tasks:**
- [x] Add `negate="yes"` attribute support in text-match filters — the `cdav.TextMatch(..., negate=True)` element exists and is used internally (`search.py` `vNotCompleted`/`vNotCancelled`); what is missing is exposing it through the public search API
- [ ] Update `CalDAVSearcher` to support `!=` operator
- [ ] Add server compatibility detection
- [ ] Implement client-side fallback filtering for non-supporting servers
- [ ] Unit and functional tests

---

### 2.2 Improved Collation Support

- **Priority:** Low
- **Estimated effort:** 8-12 hours
- **Related issue:** [#567](https://github.com/python-caldav/caldav/issues/567)

**Tasks:**
- [x] Better support for `i;unicode-casemap` collation — `_collation_to_caldav()` in `search.py` maps the `Collation` enum to `i;octet` / `i;ascii-casemap` / `i;unicode-casemap`, selectable per property
- [ ] Locale-aware case-insensitive matching — `Collation.LOCALE` currently falls back to `i;ascii-casemap`, so this is a stub
- [ ] Server capability detection for collation support
- [ ] Documentation of collation behavior per server

---

### 2.3 Multiget Optimization

- **Priority:** Medium
- **Estimated effort:** 8 hours
- **Related issue:** [#487](https://github.com/python-caldav/caldav/issues/487)

**Tasks:**
- [ ] Use `calendar-multiget` REPORT when server doesn't return object data in search
- [x] Batch retrieval of multiple objects — **done**: `Collection.multiget()`, `AsyncDAVClient.calendar_multiget()`, shared body builder `_build_calendar_multiget_body()`.  The remaining gap is the [#487](https://github.com/python-caldav/caldav/issues/487) ask: using it *automatically* when a search response carried no object data
- [ ] Configurable batch sizes

---

## Phase 3: Advanced Features

### 3.1 Managed Attachments (RFC 8607)

- **Priority:** Low
- **Estimated effort:** 24-32 hours
- **RFC:** [RFC 8607](https://datatracker.ietf.org/doc/html/rfc8607)
- **Related issue:** [#700](https://github.com/python-caldav/caldav/issues/700)

**Tasks:**
- [ ] Detect server support for `calendar-managed-attachments`
- [ ] Implement POST operations for add/update/remove attachments
- [ ] Support `MANAGED-ID` parameter
- [ ] Add `event.add_attachment()`, `event.remove_attachment()` methods
- [ ] Handle `FMTTYPE`, `FILENAME`, `SIZE` parameters

---

### 3.2 Calendar Sharing

- **Priority:** Medium
- **Estimated effort:** 32-40 hours
- **Spec:** [draft-pot-caldav-sharing](https://datatracker.ietf.org/doc/html/draft-pot-caldav-sharing)
- **Related issues:** [#701](https://github.com/python-caldav/caldav/issues/701), [#699](https://github.com/python-caldav/caldav/issues/699) (the ACL alternative to the same problem)

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

- **Priority:** Low
- **Estimated effort:** 4-8 hours
- **RFC:** [RFC 5689](https://datatracker.ietf.org/doc/html/rfc5689)
- **Related issue:** [#702](https://github.com/python-caldav/caldav/issues/702)

**Tasks:**
- [x] Support extended MKCOL as alternative to MKCALENDAR — **done**: `Calendar._create()` builds a `DAV:mkcol` with `resourcetype` = collection + calendar, and uses it when the server declares `create-calendar: {support: quirk, behaviour: mkcol-required}`
- [x] Set calendar properties atomically during creation — display name and `supported-calendar-component-set` go into the creation request; PROPPATCH is only a fallback
- [ ] Detect server support — today the MKCOL path is only taken when a server profile declares `mkcol-required` (only `baikal_old` does); nothing probes for it and nothing tests it
- [ ] Handle a `207 Multi-Status` reply (RFC 5689 section 3, a property that could not be set): `expected_return_value=201` makes it raise instead

---

### 3.4 Quota Support (RFC 4331)

- **Priority:** Low
- **Estimated effort:** 4-8 hours
- **RFC:** [RFC 4331](https://datatracker.ietf.org/doc/html/rfc4331)

**Tasks:**
- [ ] Add `calendar.get_quota()` method
- [ ] Support `DAV:quota-available-bytes` and `DAV:quota-used-bytes`
- [ ] Handle HTTP 507 (Insufficient Storage) gracefully

---

### 3.5 WebDAV Push

- **Priority:** Medium
- **Estimated effort:** 24-40 hours (rough)
- **Spec:** [draft-bitfire-webdav-push](https://bitfireat.github.io/webdav-push/draft-bitfire-webdav-push-00.html)
- **Related issue:** [#674](https://github.com/python-caldav/caldav/issues/674)

Not an IETF standard — a proposal from the bitfire team (DAVx⁵), already
implemented as a Nextcloud extension.  Replaces polling with server-pushed
change notifications.  Requested by the proposal authors themselves.

**Tasks:**
- [ ] Decide whether to support a non-IETF draft at all, and how prominently
- [ ] Detect push support on the collection
- [ ] Subscribe / refresh / unsubscribe
- [ ] Some way of receiving notifications that makes sense for a client library
      (this is the hard part: the library does not own an event loop or a
      public endpoint)
- [ ] Server feature detection

---

## Phase 4: Robustness and Edge Cases

### 4.1 Collision Avoidance

- **Priority:** High
- **Estimated effort:** 16-24 hours
- **Related issue:** [#152](https://github.com/python-caldav/caldav/issues/152)

**Tasks:**
- [x] Robust ETag-based collision detection — **done in v3.2.0**: the ETag from PUT/GET responses is cached in `self.props` and `ETagMismatchError` is raised on 412
- [ ] Proper `If-Match` / `If-None-Match` header usage — half done: `If-Match` is sent when an ETag is cached (and `If-Schedule-Tag-Match` takes precedence when a Schedule-Tag is), but `If-None-Match` is not used for create-only semantics
- [ ] Handle UID vs path name mismatches
- [ ] Race condition mitigation
- [ ] Clear error messages for conflicts

---

### 4.2 Recurrence Handling Improvements

- **Priority:** High
- **Estimated effort:** 24-32 hours (much of it now spent — see the ticked items)
- **Related issues:** [#398](https://github.com/python-caldav/caldav/issues/398), [#597](https://github.com/python-caldav/caldav/issues/597), [#598](https://github.com/python-caldav/caldav/issues/598)

**Tasks:**
- [ ] Helper methods for identifying recurrence states ([#597](https://github.com/python-caldav/caldav/issues/597)) — still nothing; there is
      no `is_recurring()` / `is_recurrence_instance()` / "find my master" on the object API
- [ ] Intelligent deletion of single recurrences ([#598](https://github.com/python-caldav/caldav/issues/598)) — still nothing; the library never
      writes `EXDATE`, so cancelling one occurrence is left entirely to the caller
- [x] Better RECURRENCE-ID handling — **done**: `save()` grew `only_this_recurrence` (a tristate:
      merge into the master, merge-or-PUT-as-is, or PUT as-is) and `all_recurrences`,
      `_incorporate_recurrence_into_parent()` does the merge, orphaned recurrences no longer crash,
      and `RANGE=THISANDFUTURE` is handled when completing recurring tasks
- [x] Documentation and examples for recurrence editing ([#398](https://github.com/python-caldav/caldav/issues/398)) — largely done in
      `docs/source/tutorial.rst`: the "big caveat" section explaining that one recurring event is
      several components, and a worked example editing a single recurrence
- [x] Timezone-aware recurrence expansion — **done**, but elsewhere: expansion moved to the
      `icalendar_searcher` package (built on `recurring_ical_events`), and `expand_rrule()` is now
      deprecated in this library
- [x] Tests for complex recurrence scenarios — **done**: `testEditSingleRecurrence`,
      `testAddOrphanedRecurrence`, the recurring-todo completion tests including THISANDFUTURE, and
      their async twins.  Server quirks are captured as flags
      (`save-load.event.recurrences.exception.reschedule`, `search.recurrences.expanded.exception`)

---

### 4.3 PROPFIND Redirect Handling

- **Priority:** Low
- **Estimated effort:** 4-8 hours
- **Related issue:** [#552](https://github.com/python-caldav/caldav/issues/552)

**Tasks:**
- [ ] Follow 3xx redirects on PROPFIND — still open, and there is a comment in `davclient.py` marking the spot
- [ ] Update internal URLs after redirect
- [ ] Prevent redirect loops

---

### 4.4 Alarm Support

- **Priority:** Medium
- **Estimated effort:** 12-16 hours
- **Related issue:** [#132](https://github.com/python-caldav/caldav/issues/132)

**Tasks:**
- [ ] Add `event.add_alarm()`, `event.remove_alarm()` methods — nothing on the object API; VALARM only appears in search filters and as `alarm_*` arguments to `vcal.create_ical()`
- [ ] Support VALARM with ACTION (DISPLAY, AUDIO, EMAIL)
- [ ] Trigger types: relative (before/after) and absolute
- [ ] Snooze/dismiss support where servers allow

---

### 4.5 Transport Robustness: Connection Retries and Rate Limiting

- **Priority:** Medium
- **Estimated effort:** 8-12 hours
- **Design document:** [`RETRY_AND_RESILIENCE_DESIGN.md`](RETRY_AND_RESILIENCE_DESIGN.md) — specifies all of the retry work below; read it first
- **Related issues:** [#695](https://github.com/python-caldav/caldav/issues/695), [#647](https://github.com/python-caldav/caldav/issues/647), [#620](https://github.com/python-caldav/caldav/issues/620) (superseded by the design document), [#697](https://github.com/python-caldav/caldav/issues/697), [PR #648](https://github.com/python-caldav/caldav/pull/648) (to be closed, not merged)

Partly in place already: 429/503 `Retry-After` handling with `RateLimitError`
and the `rate-limit` server peculiarity exist.

**Tasks:** see the ordered steps in the design document linked above.

Also related: [#697](https://github.com/python-caldav/caldav/issues/697) - smarter rate-limit throttling

---

## Phase 5: Service Discovery and Security

### 5.1 DNSSEC Validation

- **Priority:** Medium
- **Estimated effort:** 16-24 hours
- **Related issue:** [#571](https://github.com/python-caldav/caldav/issues/571)
- **RFC:** [RFC 6764 Section 8](https://datatracker.ietf.org/doc/html/rfc6764#section-8)
- **Not funded** — deliberately dropped from the NLnet scope as low value for the
  money.  DNSSEC-signed SRV/TXT records for CalDAV are rare, and a client-side
  validator helps only the deployments that already have them.  It stays on the
  roadmap because it is the right thing to do eventually, not because it is next.

**Tasks:**
- [ ] Add optional DNSSEC validation for SRV/TXT lookups
- [ ] Integrate with dnspython DNSSEC support
- [ ] Configuration option for security policy
- [ ] Clear warnings when DNSSEC unavailable
- [ ] Documentation of security implications

---

### 5.2 Server Auto-Detection Improvements

- **Priority:** Medium
- **Estimated effort:** 16-24 hours
- **Related issues:** [#600](https://github.com/python-caldav/caldav/issues/600), [#592](https://github.com/python-caldav/caldav/issues/592)

**Tasks:**
- [ ] Auto-detect server quirks on first connection
- [ ] Cache detected quirks
- [ ] Improve feature detection heuristics
- [ ] Better handling of unknown servers
- [ ] Composable feature configuration — `include` and/or `extra_features`, so a
      deployment can start from a named profile and override individual
      features ([#592](https://github.com/python-caldav/caldav/issues/592))

---

### 5.3 TLS Enforcement

- **Priority:** Medium
- **Estimated effort:** 2-4 hours
- **Related issue:** [#687](https://github.com/python-caldav/caldav/issues/687)

**Tasks:**
- [ ] `require_tls` is only enforced on RFC 6764 discovery, not on an explicitly
      passed URL — a plain `http://` URL is accepted despite the setting

---

## Phase 6: Alternative Formats (Optional)

### 6.1 jCal Support (RFC 7265)

- **Priority:** Low
- **Estimated effort:** 16-24 hours
- **RFC:** [RFC 7265](https://datatracker.ietf.org/doc/html/rfc7265)

**Tasks:**
- [ ] Accept `application/calendar+json` responses
- [ ] Convert jCal to iCalendar internally
- [ ] Optional: produce jCal output

---

### 6.2 xCal Support (RFC 6321)

- **Priority:** Low
- **Estimated effort:** 16-24 hours
- **RFC:** [RFC 6321](https://datatracker.ietf.org/doc/html/rfc6321)

**Tasks:**
- [ ] Accept `application/calendar+xml` responses
- [ ] Convert xCal to iCalendar internally
- [ ] Optional: produce xCal output

---

## Phase 7: Testing and Documentation

### 7.1 Test Coverage Expansion

- **Priority:** High
- **Estimated effort:** 40+ hours (ongoing)
- **Related issues:** [#93](https://github.com/python-caldav/caldav/issues/93), [#45](https://github.com/python-caldav/caldav/issues/45), [#595](https://github.com/python-caldav/caldav/issues/595), [#667](https://github.com/python-caldav/caldav/issues/667)

**Tasks:**
- [ ] Increase unit test coverage to 90%+
- [x] Add DAViCal docker container for testing ([#595](https://github.com/python-caldav/caldav/issues/595)) — **done**, `tests/docker-test-servers/davical/`
- [x] Add more server docker containers — **done**: baikal, bedework, ccs, cyrus, davical, davis, nextcloud, ox, sogo, stalwart and zimbra all have docker test setups
- [ ] Edge case testing for all RFCs
- [x] Make the async test suite symmetric with the sync one ([#667](https://github.com/python-caldav/caldav/issues/667)) —
      substantially done; the issue is still open for the remaining gap in
      `change_attendee_status()` ([#678](https://github.com/python-caldav/caldav/issues/678))
- [ ] Performance regression tests

---

### 7.2 Server Documentation

- **Priority:** Medium
- **Estimated effort:** 24-40 hours
- **Related issue:** [#120](https://github.com/python-caldav/caldav/issues/120)

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

- **Priority:** Medium
- **Estimated effort:** 16-24 hours
- **Related issue:** [#513](https://github.com/python-caldav/caldav/issues/513), [#541](https://github.com/python-caldav/caldav/issues/541)

**Tasks:**
- [ ] Update all examples to use icalendar `.new()` method
- [x] Add howto guides for common tasks — `docs/source/howtos.rst` exists ([#513](https://github.com/python-caldav/caldav/issues/513) is still open, so presumably not considered complete)
- [ ] Scheduling example code
- [ ] Recurrence editing examples
- [ ] Service discovery examples
- [x] Migration guide from v2.x to v3.x — `docs/source/v3-migration.rst`

---

## Phase 8: Code Quality and Maintenance

### 8.1 Deprecation Cleanup

- **Priority:** Medium
- **Estimated effort:** 8-16 hours
- **Related issues:** [#585](https://github.com/python-caldav/caldav/issues/585), [#482](https://github.com/python-caldav/caldav/issues/482), [#128](https://github.com/python-caldav/caldav/issues/128), [#619](https://github.com/python-caldav/caldav/issues/619), [#515](https://github.com/python-caldav/caldav/issues/515)

**Tasks:**
- [ ] Remove old incompatibility flags ([#585](https://github.com/python-caldav/caldav/issues/585))
- [ ] Obsolete `get_duration`, `get_due`, `get_dtend` ([#482](https://github.com/python-caldav/caldav/issues/482))
- [ ] v4.0: remove everything that raises a `DeprecationWarning`, and add the
      warning to methods deprecated without one ([#619](https://github.com/python-caldav/caldav/issues/619))
- [ ] Find and kill remaining uses of `event.component['uid']` and friends ([#515](https://github.com/python-caldav/caldav/issues/515))
- [x] Review `DAVObject.name` removal ([#128](https://github.com/python-caldav/caldav/issues/128)) — **done**: [#128](https://github.com/python-caldav/caldav/issues/128) is closed and `name` is a property raising `DeprecationWarning`, pointing at `get_display_name()`.  Actual removal is a 4.0 matter

---

### 8.2 Test Infrastructure

- **Priority:** Medium
- **Estimated effort:** 16-24 hours
- **Related issues:** [#577](https://github.com/python-caldav/caldav/issues/577), [#593](https://github.com/python-caldav/caldav/issues/593) ([#509](https://github.com/python-caldav/caldav/issues/509) and [#518](https://github.com/python-caldav/caldav/issues/518) are closed)

**Tasks:**
- [ ] Clean up `tests/conf.py` ([#577](https://github.com/python-caldav/caldav/issues/577))
- [x] Refactor test configuration ([#509](https://github.com/python-caldav/caldav/issues/509)) — issue closed
- [ ] Refactor setup/teardown methods ([#593](https://github.com/python-caldav/caldav/issues/593))
- [x] Mute expected error logging, break on unexpected ([#518](https://github.com/python-caldav/caldav/issues/518)) — issue closed

---

### 8.3 Search Module Refactoring

- **Priority:** Low
- **Estimated effort:** 16-24 hours
- **Related issue:** [#580](https://github.com/python-caldav/caldav/issues/580)

**Status: largely done** — [#580](https://github.com/python-caldav/caldav/issues/580) is closed, and the matching logic now lives in the
external `icalendar_searcher` library, which `search.py` imports.

**Tasks:**
- [x] Refactor `search.py` for better maintainability
- [x] Separate concerns more cleanly
- [ ] Improve documentation

---

### 8.4 Internal Refactoring Backlog

- **Priority:** Medium
- **Estimated effort:** 24-40 hours
- **Related issues:** [#659](https://github.com/python-caldav/caldav/issues/659), [#664](https://github.com/python-caldav/caldav/issues/664), [#665](https://github.com/python-caldav/caldav/issues/665), [#698](https://github.com/python-caldav/caldav/issues/698), [#634](https://github.com/python-caldav/caldav/issues/634), [#94](https://github.com/python-caldav/caldav/issues/94)

Housekeeping that does not change what the library can do, but that the code
needs.  Collected here so the roadmap does not pretend the backlog is only
features.

**Tasks:**
- [ ] `FeatureSet` cleanup — simplify the over-complex type-system remnants in
      `compatibility_hints.py` ([#659](https://github.com/python-caldav/caldav/issues/659))
- [ ] Decide the fate of the sans-I/O "protocol layer": XML parsing lives both in
      `caldav/protocol/xml*.py` and in the `Response` class, and the two overlap
      ([#664](https://github.com/python-caldav/caldav/issues/664))
- [ ] Reduce the remaining sync/async code duplication ([#665](https://github.com/python-caldav/caldav/issues/665))
- [ ] Parse all server iCalendar through `vcal.parse_ical()` consistently ([#698](https://github.com/python-caldav/caldav/issues/698))
- [ ] Shrink the ruff ignore list ([#634](https://github.com/python-caldav/caldav/issues/634))
- [ ] `object.id` should always work ([#94](https://github.com/python-caldav/caldav/issues/94))
- [ ] v4.0: a major API review — no issue for this, and it is the kind of thing
      that needs one before it means anything

---

### 8.5 Packaging and HTTP Dependencies

- **Priority:** Medium
- **Estimated effort:** 8-16 hours
- **Related issues:** [#690](https://github.com/python-caldav/caldav/issues/690), [#611](https://github.com/python-caldav/caldav/issues/611), [#696](https://github.com/python-caldav/caldav/issues/696)

**Tasks:**
- [ ] Make the HTTP transport an extra, so `caldav` can be installed without
      `niquests` ([#690](https://github.com/python-caldav/caldav/issues/690))
- [ ] Settle the v4.0 HTTP-library question ([#611](https://github.com/python-caldav/caldav/issues/611))
- [ ] Sync-mode support for the httpx family — async already has it ([#696](https://github.com/python-caldav/caldav/issues/696))

---

## Not Covered Here

These open issues are bug reports, support questions or automated noise rather
than roadmap items, and are deliberately left out:
[#71](https://github.com/python-caldav/caldav/issues/71) (`add_event` can update as well),
[#545](https://github.com/python-caldav/caldav/issues/545) (searches return full-day events of adjacent days),
[#612](https://github.com/python-caldav/caldav/issues/612) (support question),
[#624](https://github.com/python-caldav/caldav/issues/624) (GMX calendar creation),
[#678](https://github.com/python-caldav/caldav/issues/678) (`change_attendee_status()` async safety — see 7.1),
[#680](https://github.com/python-caldav/caldav/issues/680), [#681](https://github.com/python-caldav/caldav/issues/681), [#684](https://github.com/python-caldav/caldav/issues/684) (server-specific breakage reports),
[#685](https://github.com/python-caldav/caldav/issues/685) (automated link-checker report).

Bugs get fixed when they get fixed; they do not need a phase.

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
| Medium | WebDAV Push (3.5) | 24-40 |
| Medium | Transport Robustness (4.5) | 8-12 |
| Medium | Internal Refactoring Backlog (8.4) | 24-40 |
| Medium | Packaging / HTTP Dependencies (8.5) | 8-16 |
| Medium | Server Documentation (7.2) | 24-40 |
| Medium | Examples/Tutorials (7.3) | 16-24 |
| Medium | Deprecation Cleanup (8.1) | 8-16 |
| Medium | Test Infrastructure (8.2) | 16-24 |
| Low | Multiget Optimization (2.3) | 8 |
| Low | Collation Support (2.2) | 8-12 |
| Low | Managed Attachments (3.1) | 24-32 |
| Low | Extended MKCOL (3.3) | 4-8 |
| Low | Quota Support (3.4) | 4-8 |
| Low | PROPFIND Redirects (4.3) | 4-8 |
| Low | jCal/xCal (6.1-6.2) | 32-48 |
| Low | Search Refactoring (8.3) | 16-24 |
| Low | TLS Enforcement (5.3) | 2-4 |

**Total estimated effort:** 447-673 hours (depending on scope and depth).

Note that this total is *not* adjusted for the items ticked off as already done
in the 2026-08-20 QA pass, so the real remaining figure is lower.

---

## References

### Core Standards
- [RFC 4791 - CalDAV](https://datatracker.ietf.org/doc/html/rfc4791)
- [RFC 6638 - CalDAV Scheduling](https://datatracker.ietf.org/doc/html/rfc6638)
- [RFC 4918 - WebDAV](https://datatracker.ietf.org/doc/html/rfc4918)
- [RFC 3744 - WebDAV ACL](https://datatracker.ietf.org/doc/html/rfc3744)
- [RFC 5545 - iCalendar](https://datatracker.ietf.org/doc/html/rfc5545)

### Extensions
- [RFC 6764 - Service Discovery](https://datatracker.ietf.org/doc/html/rfc6764)
- [RFC 6578 - WebDAV Sync](https://datatracker.ietf.org/doc/html/rfc6578)
- [RFC 7953 - Calendar Availability](https://datatracker.ietf.org/doc/html/rfc7953)
- [RFC 7986 - New iCalendar Properties](https://datatracker.ietf.org/doc/html/rfc7986)
- [RFC 8607 - Managed Attachments](https://datatracker.ietf.org/doc/html/rfc8607)

### Related
- [RFC 5546 - iTIP](https://datatracker.ietf.org/doc/html/rfc5546)
- [RFC 6321 - xCal](https://datatracker.ietf.org/doc/html/rfc6321)
- [RFC 7265 - jCal](https://datatracker.ietf.org/doc/html/rfc7265)
- [CalConnect Developer Guide](https://devguide.calconnect.org/)

---

*This roadmap was generated with AI assistance based on analysis of CalDAV RFCs and the python-caldav issue tracker.*
