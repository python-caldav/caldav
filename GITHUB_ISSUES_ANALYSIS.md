# GitHub Issues Analysis - python-caldav/caldav
**Analysis Date:** 2025-12-05
**Total Open Issues:** 46

## Executive Summary

This analysis categorizes all 46 open GitHub issues for the python-caldav/caldav repository into actionable groups. The repository is actively maintained with recent issues from December 2025, showing ongoing development and community engagement.

Some issues were already closed and has been deleted from this report

## 2. Low-Hanging Fruit (9 issues)

### #541 - Docs and example code: use the icalendar .new method
- **Priority:** Documentation update
- **Effort:** 1-2 hours
- **Description:** Update example code to use icalendar 7.0.0's .new() method
- **Blocking:** None

### #513 - Documentation howtos
- **Priority:** Documentation
- **Effort:** 2-4 hours per howto
- **Description:** Create howtos for: local backup, various servers, Google Calendar
- **Blocking:** First howto depends on `get_calendars` function


### #518 - Test setup: try to mute expected error/warning logging
- **Priority:** Test improvement
- **Effort:** 2-4 hours
- **Description:** Improve logging in tests to show only unexpected errors/warnings
- **Blocking:** None

### #509 - Refactor the test configuration again
- **Priority:** Test improvement
- **fEfort:** 3-5 hours
- **Description:** Use config file format instead of Python code for test servers
- **Blocking:** None

### #482 - Refactoring - `get_duration`, `get_due`, `get_dtend` to be obsoleted
- **Priority:** Deprecation
- **Effort:** 3-4 hours
- **Description:** Wrap icalendar properties and add deprecation warnings
- **Blocking:** None
- **Labels:** deprecation


---

## 3. Needs Test Code and Documentation (4 issues)

### #524 - event.add_organizer needs some TLC
- **Status:** Feature exists but untested
- **Needs:**
  - Test coverage
  - Handle existing organizer field
  - Accept optional organizer parameter (email or Principal object)
- **Effort:** 4-6 hours

### #398 - Improvements, test code and documentation needed for editing and selecting recurrence instances
- **Status:** Feature exists, needs polish
- **Description:** Editing recurring event instances needs better docs and tests
- **Comments:** "This is a quite complex issue, it will probably slip the 3.0 milestone"
- **Related:** #35
- **Effort:** 8-12 hours

### #132 - Support for alarms
- **Status:** Partially implemented
- **Description:** Alarm discovery methods needed (not processing)
- **Comments:** Search for alarms not expected on all servers; Radicale supports, Xandikos doesn't
- **Needs:**
  - Better test coverage
  - Documentation
- **Effort:** 8-10 hours
- **Labels:** enhancement

## 4. Major Features (9 issues)

### #590 - Rething the new search API
- **Created:** 2025-12-05 (VERY RECENT)
- **Description:** New search API pattern in 2.2 needs redesign
- **Proposed:** `searcher = calendar.searcher(...); searcher.add_property_filter(...); results = searcher.search()`
- **Related:** #92 (API design principle: avoid direct class constructors)
- **Effort:** 12-20 hours

### #568 - Support negated searches
- **Description:** CalDAV supports negated text matches, not fully implemented
- **Requires:**
  - caldav-server-tester updates
  - icalendar-searcher support for != operator
  - build_search_xml_query updates in search.py
  - Workaround for servers without support (client-side filtering)
  - Unit and functional tests
- **Effort:** 12-16 hours

### #567 - Improved collation support for non-ascii case-insensitive text-match
- **Description:** Support Unicode case-insensitive search (i;unicode-casemap)
- **Current:** Only i;ascii-casemap (ASCII only)
- **Needs:**
  - Non-ASCII character detection
  - Workarounds for unsupported servers
  - Test cases: crème brûlée, Smörgåsbord, Ukrainian text, etc.
- **Effort:** 16-24 hours

### #487 - In search - use multiget if server didn't give us the object data
- **Description:** Use calendar_multiget when server doesn't return objects
- **Depends:** #402
- **Challenge:** Needs testing with server that doesn't send objects
- **Effort:** 8-12 hours

### #425 - Support RFC 7953 Availability
- **Description:** Implement RFC 7953 (calendar availability)
- **References:** Related issues in python-recurring-ical-events and icalendar
- **Effort:** 20-30 hours
- **Labels:** enhancement

### #424 - Implement support for JMAP protocol
- **Description:** Support JMAP alongside CalDAV
- **Vision:** Consistent Python API regardless of protocol
- **References:** jmapc library exists
- **Effort:** 80-120 hours (major project)
- **Related:** #92 (API design)

### #342 - Need support asyncio
- **Description:** Add asynchronous support for performance
- **Comments:** "I agree, but I probably have no capacity to follow up this year"
- **Backward compatibility:** Must not break existing sync API
- **Related:** #92 (version 3.0 API changes)
- **Effort:** 60-100 hours
- **Labels:** enhancement

### #571 - DNSSEC validation for automatic service discovery
- **Description:** Validate DNS lookups from service discovery can be trusted
- **Continuation of:** #102
- **Effort:** 12-20 hours

---

## 5. Bugs (5 issues)

### #564 - Digest Authentication error with niquests
- **Severity:** HIGH
- **Created:** 2025-11-20
- **Updated:** 2025-12-05
- **Status:** Active regression since 2.1.0
- **Impact:** Baikal server with digest auth fails
- **Root cause:** Works with requests (HTTP/1.1), fails with niquests (HTTP/2)
- **Workaround:** Revert to 2.0.1 or use requests instead of niquests
- **Comments:** v2.2.1 (requests) should work, v2.2.2 (niquests) won't
- **Related:** #530, #457 (requests vs niquests discussion)
- **Effort:** 8-16 hours


### #545 - Searching also returns full-day events of adjacent days
- **Severity:** MEDIUM
- **Description:** Full-day events from previous day returned when searching for today+
- **Comments:** "I'm currently working on client-side filtering, but I've procrastinated to deal with date-searches and timezone handling"
- **Related:** Timezone handling complexity
- **Effort:** 12-20 hours
 
### #552 - Follow PROPFIND redirects
- **Severity:** LOW-MEDIUM
- **Description:** Some servers (GMX) redirect on first PROPFIND
- **Status:** Needs implementation
- **Comments:** "If you can write a pull request... Otherwise, I'll fix it myself when I get time"
- **Effort:** 4-8 hours

### #544 - Check calendar owner
- **Severity:** LOW
- **Description:** No way to identify if calendar was shared and by whom
- **Status:** Feature request with workaround available
- **Comments:** "I will reopen this, I would like to include this in the examples and/or compatibility test suite"
- **Effort:** 6-10 hours
- **Labels:** None (should be enhancement)

---

## 6. Technical Debt / Refactoring (11 issues)

### #589 - Replace "black style" with ruff
- **Priority:** HIGH (maintainer preference)
- **Created:** 2025-12-04
- **Description:** Switch from black to ruff for better code style checking
- **Challenge:** Will cause pain for forks and open PRs
- **Timing:** After closing outstanding PRs, before next release
- **Options:** All at once vs. gradual file-by-file migration
- **Effort:** 4-8 hours + coordination

### #586 - Implement workarounds for servers not implementing text search and uid search
- **Created:** 2025-12-03
- **Description:** Client-side filtering when server lacks search support
- **Prerequisites:** Refactor search.py first (code duplication issue)
- **Questions:** Do servers exist that support uid search but not text search?
- **Consider:** Remove compatibility feature "search.text.by-uid" if not needed
- **Effort:** 8-12 hours

### #585 - Remove the old incompatibility flags completely
- **Created:** 2025-12-03
- **Description:** Remove incompatibility_description list from compatibility_hints.py
- **Continuation of:** #402
- **Process per flag:**
  - Find better name for features structure
  - Update FeatureSet.FEATURES
  - Fix caldav-server-tester to check for it
  - Create workarounds if feasible
  - Update test code to use features instead of flags
  - Validate by running tests
- **Challenge:** Several hours per flag, many flags remaining
- **Comments:** "I found Claude to be quite helpful at this"
- **Effort:** 40-80 hours total

### #580 - search.py is already ripe for refactoring
- **Created:** 2025-11-29
- **Priority:** MEDIUM
- **Description:** Duplicated recursive search logic with cloned searcher objects
- **Comments:** "I'm a bit allergic to code duplication"
- **Related:** #562, #586
- **Effort:** 8-12 hours

### #577 - `tests/conf.py` is a mess
- **Created:** 2025-11-29
- **Status:** Work done in PR #578
- **Description:** File no longer reflects configuration purpose, too big
- **Needs:**
  - Rename or split file
  - Consolidate docker-related code
  - Move docker code to docker directory
  - Remove redundant client() method
- **Comments:** "Some comments at the top of the file with suggestions for further process"
- **Effort:** 6-10 hours

### #515 - Find and kill instances of `event.component['uid']` et al
- **Updated:** 2025-12-05
- **Description:** Replace event.component['uid'] with event.id
- **Blocker:** "I found that we cannot trust event.id to always give the correct uid"
- **Related:** #94
- **Effort:** 6-10 hours (needs research first)

### #128 - DAVObject.name should probably go away
- **Description:** Remove name parameter from DAVObject.__init__
- **Reason:** DisplayName not universal for all DAV objects
- **Alternative:** Use DAVObject.props, update .save() and .load()
- **Comments:** "Perhaps let name be a property that mirrors the DisplayName"
- **Effort:** 8-12 hours
- **Labels:** refactoring

### #94 - object.id should always work
- **Updated:** 2025-12-05
- **Description:** Make event.id always return correct UID
- **Current issue:** Sometimes set, sometimes not
- **Proposed:** Move to _id, create getter that digs into data
- **Comments:** "event.id cannot always be trusted. We need unit tests and functional tests covering all edge-cases"
- **Related:** #515
- **Effort:** 12-16 hours
- **Labels:** refactoring

### #152 - Collision avoidance
- **Description:** Save method's collision prevention not robust enough
- **Issues:**
  - Path name may not correspond to UID
  - Possible to create two items with same UID but different paths
  - Race condition: check then PUT
- **Comments:** Maintainer frustrated with CalDAV standard design
- **Effort:** 16-24 hours
- **Labels:** enhancement

### #92 - API changes in version 3.0?
- **Type:** Planning/Discussion
- **Updated:** 2025-12-05
- **Description:** Track API changes for major version
- **Key principles:**
  - Start with davclient.get_davclient (never direct constructors)
  - Consistently use verbs for methods
  - Properties should never communicate with server
  - Methods should be CalDAV-agnostic (prefix caldav_ or dav_ for specific)
- **Related:** #342 (async), #424 (JMAP), #590 (search API)
- **Comments:** "Perhaps the GitHub Issue model is not the best way of discussing API-changes?"
- **Labels:** roadmap

### #45 - Caldav test servers
- **Type:** Infrastructure
- **Updated:** 2025-12-02
- **Description:** Need more test servers and accounts
- **Current:** Local (xandikos, radicale, Baikal, Nextcloud, Cyrus, SOHo, Bedework)
- **Private stable:** eCloud, Zimbra, Synology, Robur, Posteo
- **Unstable/down:** DAViCal, GMX, various Nextcloud variants
- **Missing:** Open eXchange, Apple CalendarServer
- **Call to action:** "Please help! Donate credentials for working test account(s)"
- **Effort:** Ongoing coordination
- **Labels:** help wanted, roadmap, testing regime

---

## 7. Documentation (3 issues)

### #120 - Documentation for each server/cloud provider
- **Description:** Separate document per server/provider with:
  - Links to relevant GitHub issues
  - Caveats/unsupported features
  - CalDAV URL format
  - Principal URL format
- **Comments:** "I've considered that this belongs to a HOWTO-section"
- **Effort:** 2-4 hours per server
- **Labels:** enhancement, doc

### #93 - Increase test coverage
- **Description:** Code sections not exercised by tests
- **Comments:** "After 2.1, we should take out a complete coverage report once more"
- **Status:** Ongoing effort
- **Effort:** Ongoing
- **Labels:** testing regime

### #474 - Roadmap 2025/2026
- **Type:** Planning document
- **Updated:** 2025-12-04
- **Description:** Prioritize outstanding work with estimates
- **Status:** Being tracked
- **Comments:** Estimates have been relatively accurate so far
- **Labels:** None (should be roadmap)

---

## 8. Dependency/Packaging Issues (2 issues)

### #530 - Please restore compatibility with requests, as niquests is not suitable for packaging
- **Severity:** HIGH for packagers
- **Description:** niquests forks urllib3, h2, aioquic and overwrites urllib3
- **Impact:** Cannot coexist with regular urllib3, effectively non-installable for some use cases
- **Status:** No clean solution via pyproject.toml
- **Workaround:** Packagers must sed the dependency themselves
- **Related:** #457, #564
- **Comments:** 8 comments, active discussion
- **Effort:** 8-16 hours (architecture decision needed)

### #457 - Replace requests with niquests or httpx?
- **Type:** Architecture decision
- **Status:** Under discussion
- **Options:**
  - requests (feature freeze, 3.0 overdue)
  - niquests (newer, fewer maintainers, supply chain concerns)
  - httpx (more maintainers, similar features)
- **Concerns:**
  - Auth code is fragile with weird server setups
  - Supply chain security
  - Breaking changes for HomeAssistant users
- **Comments:** "That's an awesome offer" (PR offer from community)
- **Decision:** Wait for next major release
- **Related:** #530, #564
- **Labels:** help wanted, question

---

## Priority Recommendations

### Critical Path (Do First)
1. **#564** - Fix digest auth with niquests (affects production users)
2. **#530/#457** - Resolve requests/niquests/httpx dependency strategy
3. **#585** - Continue removing incompatibility flags (long-term cleanup)

### Quick Wins (High Value, Low Effort)
1. **#420** - Close vobject dependency issue
2. **#180** - Close current-user-principal issue
3. **#541** - Update docs for icalendar .new method
4. **#535** - Document build process
5. **#504** - Add DTSTAMP to compatibility fixer

### Major Initiatives (Plan & Execute)
1. **#342** - Async support (ties into v3.0 planning)
2. **#92** - API redesign for v3.0
3. **#590** - New search API pattern
4. **#

585** - Complete incompatibility flags removal

### Community Engagement
1. **#45** - Recruit more test server access
2. **#232** - Good first issue for new contributors
3. **#457** - Accept community PR for httpx migration

---

## Statistics by Category

| Category | Count | Percentage |
|----------|-------|------------|
| Can Be Closed | 2 | 4.3% |
| Low-Hanging Fruit | 9 | 19.6% |
| Needs Test/Docs | 4 | 8.7% |
| Major Features | 9 | 19.6% |
| Bugs | 5 | 10.9% |
| Technical Debt | 11 | 23.9% |
| Documentation | 3 | 6.5% |
| Dependency/Packaging | 2 | 4.3% |
| **TOTAL** | **46** | **100%** |

## Labels Analysis

- **enhancement:** 9 issues
- **help wanted:** 5 issues
- **roadmap:** 3 issues
- **testing regime:** 3 issues
- **refactoring:** 3 issues
- **good first issue:** 1 issue
- **deprecation:** 1 issue
- **pending resolve:** 1 issue
- **need-feedback:** 1 issue
- **compatibility:** 1 issue
- **doc:** 2 issues
- **question:** 1 issue
- **No labels:** 23 issues (50%)

## Recent Activity

**Last 7 days (since 2025-11-28):**
- #590 (2025-12-05) - Rethink search API
- #589 (2025-12-04) - Replace black with ruff
- #586 (2025-12-03) - Workarounds for missing text/uid search
- #585 (2025-12-03) - Remove incompatibility flags
- #580 (2025-11-29) - Refactor search.py

The repository shows very active maintenance with 5 new issues in the past week, all from the maintainer (tobixen) documenting technical debt and improvements.

---

## Conclusion

The python-caldav repository is actively maintained with a healthy mix of issues. The majority fall into technical debt/refactoring (24%) and low-hanging fruit (20%), suggesting opportunities for both incremental improvements and major cleanup. The maintainer is actively documenting issues and planning work, as evidenced by 5 issues created in the past week alone.

Key recommendations:
1. Address the critical auth regression (#564) immediately
2. Resolve the dependency strategy (#530/#457) to unblock packaging
3. Tackle quick documentation wins for user benefit
4. Continue systematic technical debt reduction (#585)
5. Plan v3.0 API redesign in conjunction with async support (#92, #342)
