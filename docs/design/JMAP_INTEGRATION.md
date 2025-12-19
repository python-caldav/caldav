# JMAP Calendars Integration Design

This document analyzes the feasibility and challenges of adding JMAP Calendars support
to the caldav library, enabling a unified Python API for calendar access regardless of
the underlying protocol (CalDAV or JMAP).

## Background

### What is JMAP?

JMAP (JSON Meta Application Protocol) is a modern protocol designed to replace IMAP for
email, with extensions for calendars and contacts. Key characteristics:

- HTTP + JSON based (no XML/WebDAV complexity)
- Stateless with efficient sync via state tokens
- Batch operations in single requests
- Defined in RFC 8620 (core), with calendars in a separate spec

### Motivation

From the roadmap (#474):
> "JMAP is a new email protocol intended to replace IMAP - at FOSSDEM 2025 it appeared
> that both server developers and client developers found it superior compared to IMAP.
> The JMAP protocol also supports the exchange of calendaring data."

The goal is a library where high-level methods work seamlessly regardless of whether
CalDAV or JMAP is used underneath.

## Available JMAP Calendar Servers

For testing and development:

| Server | License | Calendar Support | Notes |
|--------|---------|------------------|-------|
| [Cyrus IMAP](https://www.cyrusimap.org/) | BSD | Full | Used by Fastmail, reference implementation |
| [Stalwart](https://stalw.art/) | AGPLv3 | Full | Rust-based, modern |
| Apache James | Apache 2.0 | Mail only | Calendar support unclear |

Fastmail offers JMAP access but requires a paid account.

## JMAP Calendars Specification Overview

### Primary Object Types

**Calendar**: Collection of events with properties:
- `id`, `name`, `description`, `color`, `sortOrder`
- `isSubscribed`, `isVisible`, `isDefault`
- `defaultAlertsWithTime`, `defaultAlertsWithoutTime`
- `shareWith` for sharing permissions
- `myRights` defining user access levels

**CalendarEvent**: Based on JSCalendar (RFC 8984):
- `id`, `calendarIds` (can belong to multiple calendars!)
- `uid`, `title`, `start`, `duration`, `timeZone`
- `isDraft`, `isOrigin` (scheduling control)
- `utcStart`, `utcEnd` (computed properties)
- `participants`, `alerts`, `recurrenceRules`, `recurrenceOverrides`

**ParticipantIdentity**: User identities within an account

**CalendarEventNotification**: Records external changes

### Available Methods

```
Calendar/get, Calendar/changes, Calendar/set
CalendarEvent/get, CalendarEvent/changes, CalendarEvent/set, CalendarEvent/copy
CalendarEvent/query, CalendarEvent/queryChanges
CalendarEvent/parse  (converts iCalendar blobs to CalendarEvent)
ParticipantIdentity/get, ParticipantIdentity/changes, ParticipantIdentity/set
Principal/getAvailability  (free/busy)
```

### Key JMAP Features

1. **Batch Operations**: Multiple method calls in single HTTP request
2. **Efficient Sync**: State tokens + `/changes` endpoint
3. **Server-side Expansion**: `expandRecurrences` in queries
4. **iCalendar Import**: `CalendarEvent/parse` accepts iCalendar blobs

## API Compatibility Analysis

### High-Level API Mapping (Feasible)

| caldav API | JMAP Equivalent | Compatibility |
|------------|-----------------|---------------|
| `DAVClient` | JMAP Session | High - both handle auth, discovery |
| `Principal` | JMAP Account | High - similar user identity concept |
| `Calendar` | Calendar object | High - very similar semantics |
| `calendar.calendars()` | `Calendar/get` | High |
| `calendar.search()` | `CalendarEvent/query` | High - both support time-range, filtering |
| `calendar.save_event()` | `CalendarEvent/set` | High - create/update operations |
| `event.load()` | `CalendarEvent/get` | High - fetch by ID |
| `event.delete()` | `CalendarEvent/set (destroy)` | High |
| `calendar.objects_by_sync_token()` | `CalendarEvent/changes` | High - incremental sync |
| `calendar.freebusy_request()` | `Principal/getAvailability` | Medium |

### Critical Challenges

#### 1. Data Model Translation (iCalendar ↔ JSCalendar)

The caldav library exposes `event.icalendar_instance` (python-icalendar objects).
JMAP uses JSCalendar (JSON-based, RFC 8984).

**Key Differences:**

| Aspect | iCalendar | JSCalendar |
|--------|-----------|------------|
| Format | Text with CRLF, line folding | JSON |
| Property names | UPPERCASE (DTSTART, DTEND) | camelCase (start, duration) |
| Time zones | Embedded VTIMEZONE | IANA identifiers |
| Recurrence | RRULE string syntax | JSON objects |

**Options:**
- A) Translate at the boundary (iCalendar ↔ JSCalendar conversion)
- B) Use JMAP's `CalendarEvent/parse` for iCalendar import
- C) Expose `.jscalendar_instance` property for JMAP connections

**Recommendation:** The python `icalendar` library is deeply embedded in caldav.
For JMAP, we should:
1. Use `CalendarEvent/parse` when users provide iCalendar data
2. Expose JSCalendar natively for JMAP-specific workflows
3. Consider a translation layer using a library like `icalendar-jscalendar` if one exists

#### 2. No Tasks/Journals in JMAP Calendars

**Critical limitation:** JMAP Calendars only supports events.

```
caldav:  Event, Todo, Journal, FreeBusy
JMAP:    CalendarEvent only
```

JMAP Tasks is a separate specification (RFC 9553). This means:
- `calendar.todos()` has no direct JMAP Calendars equivalent
- `calendar.journals()` has no JMAP equivalent at all
- Would need separate JMAP Tasks implementation

**Options:**
- Scope JMAP support to events only initially
- Implement JMAP Tasks as a separate effort
- Accept that unified API cannot cover all object types

#### 3. Recurrence Model Differences

| Aspect | CalDAV | JMAP |
|--------|--------|------|
| Storage | Each override can be separate VEVENT | Single object with `recurrenceOverrides` map |
| Expansion | Server-side `expand` in REPORT | `expandRecurrences` in query |
| Instance IDs | `RECURRENCE-ID` property | Server-generated synthetic IDs |
| This-and-future | Split into two VEVENTs | Update base + restore overrides |

The caldav `expand_rrule()` and `split_expanded` logic would need JMAP-specific paths.

#### 4. Multi-Calendar Membership

```python
# CalDAV: event belongs to ONE calendar
event.parent = calendar

# JMAP: event can belong to MULTIPLE calendars simultaneously
event.calendarIds = {"calendar-id-1": True, "calendar-id-2": True}
```

This is a semantic difference that affects the object model.

### Moderate Challenges

#### 5. Attendee/Participant Model

CalDAV uses `ATTENDEE`/`ORGANIZER` iCalendar properties.
JMAP uses a `participants` map with richer semantics:

```json
{
  "participants": {
    "participant-id": {
      "name": "Alice",
      "email": "alice@example.com",
      "roles": {"attendee": true},
      "participationStatus": "accepted",
      "sendTo": {"imip": "mailto:alice@example.com"}
    }
  }
}
```

The caldav `add_attendee()`, `add_organizer()` methods would need translation.

#### 6. Alerts/Alarms

Similar concepts, different structures:

```
CalDAV: VALARM components nested in VEVENT
JMAP:   "alerts" property with "useDefaultAlerts" support
```

JMAP also supports calendar-level default alerts, which CalDAV doesn't have.

#### 7. Per-User Properties in Shared Calendars

JMAP explicitly supports per-user properties (alerts, color, keywords) on shared
calendar events. CalDAV handles this server-side with less standardization.

## Architectural Options

### Option A: Extend caldav Library

```
caldav/
├── davclient.py           # Existing CalDAV client
├── jmapclient.py          # NEW: JMAP client
├── objects.py             # Unified Calendar, Event classes
├── backends/
│   ├── __init__.py
│   ├── caldav_backend.py  # CalDAV-specific operations
│   └── jmap_backend.py    # JMAP-specific operations
├── translation/
│   ├── __init__.py
│   └── jscalendar.py      # iCalendar ↔ JSCalendar
```

**Pros:**
- Single package, backward compatible
- Shared code (URL handling, caching, etc.)
- Natural evolution of existing library

**Cons:**
- Library name becomes misleading ("caldav" for JMAP?)
- Complex dual-protocol logic in objects
- Risk of CalDAV regressions during JMAP work

### Option B: New Unified Library

```
python-calendar-client/
├── client.py              # Auto-detects CalDAV vs JMAP
├── calendar.py            # Unified Calendar class
├── event.py               # Unified Event class
├── backends/
│   ├── caldav.py          # Wraps python-caldav
│   └── jmap.py            # New JMAP implementation
```

**Pros:**
- Clean architecture, proper naming
- caldav library remains focused and stable
- Clear separation of concerns

**Cons:**
- New package to maintain
- May duplicate some code
- Users need to migrate

### Option C: Separate JMAP Library + Shared Interface

```
python-jmapcal/            # New package for JMAP calendars
python-caldav/             # Existing package (unchanged)
python-calendar-api/       # Abstract interface package
```

**Pros:**
- Maximum separation of concerns
- Each library can evolve independently
- Clear responsibility boundaries

**Cons:**
- Three packages to coordinate
- More complex dependency management
- Interface package adds overhead

### Recommendation

**Start with Option A** (extend caldav) for pragmatic reasons:
1. Aligns with the existing roadmap and funding
2. Lower barrier to entry for contributors
3. Can refactor to Option B later if needed
4. The async refactoring already introduces a backend abstraction pattern

## Implementation Phases

### Phase 1: Foundation (Estimated: 15h)

1. **JMAP client basics**
   - Session establishment and authentication
   - Account discovery
   - Basic HTTP/JSON request handling

2. **Test infrastructure**
   - Set up Cyrus or Stalwart test server
   - Create JMAP-specific test fixtures
   - Add JMAP server to CI matrix

3. **Calendar listing**
   - `Calendar/get` implementation
   - Map to existing `Calendar` class

### Phase 2: Core Operations (Estimated: 15h)

1. **Event CRUD**
   - `CalendarEvent/get` → `event.load()`
   - `CalendarEvent/set` → `event.save()`, `event.delete()`
   - `CalendarEvent/query` → `calendar.search()`

2. **Data translation**
   - JSCalendar ↔ iCalendar conversion utilities
   - Handle common properties (title, start, end, description)
   - Expose raw JSCalendar for advanced users

3. **Sync support**
   - `CalendarEvent/changes` → `objects_by_sync_token()`
   - State token management

### Phase 3: Advanced Features (Estimated: 10h)

1. **Recurrence handling**
   - Expansion via query
   - Override management
   - Recurrence ID mapping

2. **Participants/Scheduling**
   - Participant translation
   - `sendSchedulingMessages` support

3. **Alerts**
   - Alert translation
   - Default alerts support

### Phase 4: Polish and Documentation (Estimated: 10h)

1. **Unified client factory**
   - Auto-detection of CalDAV vs JMAP
   - `get_calendar_client()` function

2. **Documentation**
   - JMAP-specific usage examples
   - Migration guide for CalDAV users
   - Protocol comparison docs

3. **Edge cases and compatibility**
   - Server quirks handling
   - Graceful degradation

## Open Questions

1. **Naming**: Should the library be renamed if JMAP support is added?
   - Options: `python-calendar`, `pycal`, keep `caldav`

2. **Tasks/Journals**: Should JMAP Tasks (RFC 9553) be in scope?
   - Adds significant complexity
   - Different spec, different servers may not support

3. **Minimum Python version**: Current caldav supports 3.8+
   - JMAP implementation could require 3.9+ for better typing

4. **Dependencies**: What JMAP/JSCalendar libraries to use?
   - `jmapc` exists but is email-focused
   - May need to implement calendar support from scratch

5. **iCalendar compatibility**: How much to preserve?
   - Some users depend on `event.icalendar_instance`
   - Could be expensive to maintain translation layer

## References

- [JMAP Calendars Specification](https://jmap.io/spec-calendars.html)
- [JSCalendar (RFC 8984)](https://www.rfc-editor.org/rfc/rfc8984.html)
- [JMAP Core (RFC 8620)](https://www.rfc-editor.org/rfc/rfc8620.html)
- [JMAP Tasks (RFC 9553)](https://www.rfc-editor.org/rfc/rfc9553.html)
- [caldav Roadmap Issue #474](https://github.com/python-caldav/caldav/issues/474)
- [JMAP Support Issue #424](https://github.com/python-caldav/caldav/issues/424)
- [JMAP Software Implementations](https://jmap.io/software.html)
- [Cyrus IMAP JMAP Support](https://www.cyrusimap.org/3.4/imap/developer/jmap.html)
