# JMAP Roadmap

This document covers what `caldav.jmap` currently does, what it doesn't, where
the conversion layer loses fidelity, which servers work, and where things go
next.

---

## What Is Implemented

### Clients and session

Two clients — `JMAPClient` (sync) and `AsyncJMAPClient` (async) — with
identical public APIs. Both support Basic and Bearer token auth, read from
environment variables and the same YAML/JSON config file as the CalDAV client,
and work as context managers.

Session setup follows RFC 8620 §2: GET `/.well-known/jmap`, parse `apiUrl`
(resolved via `urljoin` because Cyrus returns a relative path, not the absolute
URL the spec requires), pick the account from
`primaryAccounts["urn:ietf:params:jmap:calendars"]` with a fallback scan across
all accounts. The session is cached for the client's lifetime — one GET per
process, not one per call.

Auth is inferred from what you pass: username + password → Basic; password
alone → Bearer. No 401-challenge-retry dance — JMAP sends credentials upfront on
every request, and a 401/403 is a hard failure.

### Calendars

`get_calendars()` — issues `Calendar/get` and returns a list of `JMAPCalendar`
dataclass objects with `id`, `name`, `description`, `color`, `is_subscribed`,
`my_rights`, `sort_order`, `is_visible`.

`JMAPCalendar.to_jmap()` can serialize back to a JMAP dict (ready for
`Calendar/set`), but the client has no method to call `Calendar/set` yet.

### Events — CRUD, search, incremental sync

The calendar-scoped methods mirror `caldav.collection.Calendar` exactly:

| Calendar method | Client method | JMAP call |
|-----------------|---------------|-----------|
| `cal.add_event(ical_str)` → event_id | `create_event(calendar_id, ical_str)` | `CalendarEvent/set` (create) |
| `cal.get_object_by_uid(uid)` → ical_str | — | `CalendarEvent/query` + `CalendarEvent/get` (fetches all events in calendar, scans locally for UID match; see limitation below) |
| `cal.search(event=True, start=, end=, text=)` → list[ical_str] | `search_events(calendar_id, start, end, text)` | `CalendarEvent/query` + result reference into `CalendarEvent/get` in one round-trip |
| — | `get_event(event_id)` → ical_str | `CalendarEvent/get` — lower-level, takes JMAP event ID directly |
| — | `update_event(event_id, ical_str)` | `CalendarEvent/set` (update patch; `uid` stripped as it's server-immutable post-creation) |
| — | `delete_event(event_id)` | `CalendarEvent/set` (destroy) |
| — | `get_sync_token()` → state | `CalendarEvent/get` with empty ids list (no event data transferred, only state) |
| — | `get_objects_by_sync_token(token)` → (added, modified, deleted) | `CalendarEvent/changes` + `CalendarEvent/get` for changed ids |

Events go in and come out as iCalendar strings. Conversion to/from JSCalendar
happens inside the library.

`get_object_by_uid` currently fetches all events in the calendar and scans them
locally for a matching UID. `CalendarEvent/query` has a `uid` filter that would
make this a single targeted lookup — not yet wired.

One notable detail in `get_objects_by_sync_token`: if the server sets
`hasMoreChanges: true`, the client raises `JMAPMethodError` rather than silently
returning a partial result. The caller must call `get_sync_token()` to establish
a new baseline. Partial sync state is worse than no sync.

### Tasks — CRUD

| Client method | JMAP call |
|---------------|-----------|
| `get_task_lists()` → list[JMAPTaskList] | `TaskList/get` |
| `create_task(task_list_id, title, **kwargs)` → task_id | `Task/set` (create) |
| `get_task(task_id)` → JMAPTask | `Task/get` |
| `update_task(task_id, patch)` | `Task/set` (update) |
| `delete_task(task_id)` | `Task/set` (destroy) |

Task methods use `urn:ietf:params:jmap:tasks` in the `using` array. If the
server doesn't advertise that capability, they raise `JMAPMethodError`. Accepted
kwargs for `create_task`: `description`, `due`, `start`, `time_zone`,
`estimated_duration`, `percent_complete`, `progress`, `priority`.

### iCalendar ↔ JSCalendar conversion

The conversion layer (`caldav.jmap.convert`) handles:

| iCalendar | JSCalendar | Notes |
|-----------|------------|-------|
| `SUMMARY` | `title` | |
| `DTSTART` / `DTEND` / `DURATION` | `start` + `duration` + `timeZone` | `start` is always a LocalDateTime string per RFC 8984 |
| `VALUE=DATE` | `showWithoutTime: true` | Stored as `T00:00:00` in `start` |
| `DESCRIPTION` | `description` | |
| `SEQUENCE` | `sequence` | |
| `PRIORITY` | `priority` | Skipped when value is 0 (undefined in iCalendar) |
| `CLASS:PRIVATE` | `privacy: "private"` | |
| `CLASS:CONFIDENTIAL` | `privacy: "secret"` | |
| `TRANSP:TRANSPARENT` | `freeBusyStatus: "free"` | `OPAQUE` is the implicit default; only `TRANSPARENT` is emitted |
| `COLOR` | `color` | |
| `CATEGORIES` | `keywords` | Handles multi-value, multi-line, and bare string forms |
| `LOCATION` | `locations` | Wrapped in `{uuid: {name: ...}}` map |
| `ORGANIZER` | `participants` (owner + organizer roles) | `CN` → `name`, `mailto:` → `sendTo.imip` |
| `ATTENDEE` | `participants` (attendee role) | `PARTSTAT`, `RSVP`, `CUTYPE`, `ROLE=CHAIR` mapped |
| `RRULE` | `recurrenceRules` | Full `RecurrenceRule` objects with `@type`, `rscale`, `skip`, `firstDayOfWeek` |
| `EXRULE` | `excludedRecurrenceRules` | Same structure as `recurrenceRules` |
| `EXDATE` | `recurrenceOverrides` (`excluded: true`) | |
| `RECURRENCE-ID` override VEVENTs | `recurrenceOverrides` patch dicts | Only fields differing from master included in the patch |
| `VALARM` | `alerts` | Relative triggers → `SignedDuration` string; absolute → UTCDateTime string |

Non-IANA timezone identifiers (e.g. Outlook's `Eastern Standard Time`) pass
through unchanged rather than being mapped to IANA equivalents. Mapping is
ambiguous and would introduce silent data corruption; the raw TZID roundtrips
intact so the receiving calendar client can resolve it.

The `jscal_to_ical` direction handles `ZoneInfoNotFoundError` for non-IANA
TZIDs by attaching the raw TZID as a parameter on `DTSTART` rather than
resolving it — same principle in reverse.

### Error hierarchy

All JMAP errors extend `JMAPError`, which extends `DAVError`. Code that already
catches `DAVError` catches JMAP errors without modification.

- `JMAPAuthError` — HTTP 401/403; also inherits `AuthorizationError`
- `JMAPCapabilityError` — server doesn't advertise `urn:ietf:params:jmap:calendars`
- `JMAPMethodError` — a JMAP method returned an `error` response; `error_type`
  carries the RFC 8620 error type string (`"unknownMethod"`, `"invalidArguments"`,
  `"stateMismatch"`, etc.)

### Tests

264 unit tests, zero network calls. They cover session parsing (including
Cyrus-specific relative `apiUrl`), method builders and response parsers, all
iCalendar ↔ JSCalendar conversion paths including recurrence, participants,
alarms, and timezone edge cases, and both sync and async client paths via mocks.

17 integration tests against Cyrus IMAP via Docker on port 8802. They exercise
the full event lifecycle: create, get, update, delete, search by date range and
text, incremental sync with `changes`, and the session account discovery path.
6 of the 17 are async equivalents using `AsyncJMAPClient`.

---

## What Is Not Yet Implemented

Roughly ordered by impact on parity with the CalDAV client.

### Scheduling and invitations

CalDAV handles scheduling through `save_with_invites()`, `schedule_inbox()`,
`inbox_item.accept_invite()`, and `freebusy_request()` (RFC 6638 / iTIP). These
require the client to construct and parse iMIP messages.

JMAP's approach is cleaner. The server handles all iMIP delivery internally:

1. Pass `sendSchedulingMessages: true` on `CalendarEvent/set` when creating or
   modifying an event with participants. The server dispatches the iTIP
   `REQUEST`/`CANCEL`/`UPDATE` messages automatically.

2. Call `CalendarEvent/participantReply` to respond as an attendee: pass the
   event ID, participant ID (derived from the user's email), and new
   `participationStatus` (`accepted`, `declined`, `tentative`). The server sends
   the iTIP `REPLY`. No iMIP construction needed.

3. Query `CalendarEventNotification/get` to see what changed: the server
   maintains a log of notification objects recording changes made by external
   participants. Read them to keep attendance current, then clear with
   `CalendarEventNotification/set` (destroy).

None of this is implemented. It's the largest missing feature for any multi-user
calendar application.

### Free/busy queries

CalDAV exposes free/busy via `calendar.freebusy_request()`, which returns a
VFREEBUSY component to parse.

The JMAP equivalent is `Principal/getAvailability`. You give it account IDs (or
email addresses the server can resolve to principals) and a time range. The
response is structured JSON — no parsing. It also handles cross-account and
cross-principal availability queries in a single call.

`Principal/getAvailability` requires `Principal/get` first, to resolve the
current user's principal ID. Neither is implemented.

### Calendar management

Calendars are currently read-only. `get_calendars()` works; there's no way to
create, rename, delete, or share a calendar.

`JMAPCalendar.to_jmap()` is already there. What's missing:

- A `build_calendar_set()` method builder (the `build_calendar_changes()` builder
  exists for `Calendar/changes` but not `Calendar/set`)
- A `parse_calendar_set()` response parser
- Client methods: `create_calendar()`, `update_calendar()`, `delete_calendar()`

Beyond basic CRUD, `Calendar/set` also controls:

- `shareWith` — grant or revoke access per principal ID with fine-grained rights:
  `mayReadItems`, `mayWriteAll`, `mayWriteOwn`, `mayUpdatePrivate`, `mayRSVP`,
  `mayDelete`, `mayAdmin`
- `isSubscribed` — subscribe/unsubscribe from a shared calendar without changing
  the underlying sharing grants
- `defaultAlertsWithTime` / `defaultAlertsWithoutTime` — per-calendar default
  alarms applied to all events unless overridden at the event level
- `includeInAvailability` — whether this calendar's events count toward the
  user's free/busy

### CalendarEvent/parse

`CalendarEvent/parse` lets the client hand the server a raw iCalendar blob and
get back structured `CalendarEvent` JSON, bypassing the client-side conversion
layer. Useful for import flows and for previewing iCalendar attachments without
writing your own parser.

Server support is optional (sub-capability
`urn:ietf:params:jmap:calendars:parse`). Cyrus doesn't advertise it and returns
`unknownMethod`. Stalwart explicitly supports it, configurable via
`jmap.calendar.parse.max-items`. Not implemented.

### CalendarEvent/copy

`CalendarEvent/copy` duplicates events across calendars or accounts in a single
server-side operation. Not implemented. The workaround is fetch + modify
`calendarIds` + create, which costs an extra round-trip and doesn't work
cross-account.

### CalendarEvent/query — partial coverage

`cal.search()` works but only uses a subset of `CalendarEvent/query`'s
`FilterCondition`. The lower-level `search_events()` on the client exposes the
same filters.

Currently exposed: `inCalendars` (automatically scoped when called via
`cal.search()`; also available as `calendar_id` on `search_events()`), `after`
(via `start`), `before` (via `end`), `text`.

Not yet exposed:

- `uid` — exact UID lookup; wiring this would replace the current linear scan in
  `get_object_by_uid` with a single targeted query
- `hasKeyword` / `notKeyword` — filter by category/tag
- `isUndecided` / `isRejected` — filter by current user's RSVP status ("events
  you haven't responded to" is a very common UI need)
- `participantIs` — filter to events where a given email has a specific role
- `hasAttachment` — filter to events with blob links

The query + result-reference pattern already batches everything into one
round-trip regardless of filter complexity, so adding more filter options is
purely additive — no protocol changes needed.

### CalendarEvent/queryChanges

`CalendarEvent/changes` gives a global diff of all events since a state token.
`CalendarEvent/queryChanges` is more targeted: it tracks a specific filtered
query and tells you which event IDs entered or left the result set, without
re-running the full query locally.

A client maintaining a "this week's events" view calls `queryChanges` and gets
exactly the IDs to add or remove. Not implemented.

### Task sync and search

Task CRUD works. The following don't:

- `Task/changes` — incremental sync, same pattern as `CalendarEvent/changes`
- `Task/query` — filter tasks by date range, progress, keyword, etc.
- `Task/queryChanges` — query-scoped incremental sync
- `Task/copy` — cross-list or cross-account task duplication

No integration tests for tasks because Cyrus doesn't implement
`urn:ietf:params:jmap:tasks`. Stalwart does.

### Task list management

`TaskList/set` (create, rename, delete task lists) is not implemented. Task
lists are currently read-only.

### Push notifications

JMAP's push model via `PushSubscription` eliminates polling. A client registers
a push endpoint; the server sends `StateChange` objects whenever tracked data
types change.

The `StateChange` object is deliberately minimal: it lists which data types have
a new state string. The client then calls the relevant `*/changes` method to get
the actual delta. Push and sync are decoupled by design.

Two transports:
- **EventSource** — persistent HTTP connection (SSE); practical for long-lived
  server-side processes. Cyrus supports this.
- **Web Push** — encrypted delivery to a third-party push gateway (FCM, APNs);
  practical for mobile and background delivery. Stalwart supports this.

Note: RFC 8887 also defines a WebSocket binding for JMAP as an alternative to
EventSource for real-time push. Neither is implemented. `get_objects_by_sync_token()`
is the polling alternative.

### Sharing and delegation

`Calendar.shareWith` maps a principal ID to a set of rights. `ParticipantIdentity`
lists the current user's own email addresses and display names as the server
knows them — this is how the client reliably identifies which `participants`
entry in an event is the current user, needed for showing the user's own RSVP
status without fragile email-string matching.

Multi-account delegation uses `Principal` objects. The client currently picks the
first calendar-capable account in the session with no mechanism to switch or
enumerate delegates.

None of the sharing/delegation surface is implemented.

### Blob and attachment support

JMAP blob upload is defined in RFC 8620 §6: POST to `uploadUrl` (from the
session object), get a `blobId` back. The JMAP Blob Management Extension (RFC
9404, published Aug 2023) adds `Blob/get`, `Blob/lookup`, and `Blob/copy`
methods for more flexible blob operations within a standard JMAP method call
batch.

`CalendarEvent` records reference blobs via the `links` property — a map of
link IDs to objects with `href`, `rel`, `title`, `contentType`, and `size`.

`JMAPEvent` stores whatever `links` data the server returns, but the conversion
layer doesn't map iCalendar `ATTACH` properties to or from `links`. Neither
upload nor download is implemented.

Blob support is also the prerequisite for `CalendarEvent/parse` via blob upload:
upload the iCalendar file as a blob, pass the `blobId` to parse, get structured
events back.

---

## Known Conversion Limitations

### iCalendar fields dropped in ical_to_jscal

| Field | Why it's dropped |
|-------|------------------|
| `RDATE` | JSCalendar has no direct equivalent; all recurrence is expressed via `recurrenceRules` |
| `COMMENT` | No JSCalendar equivalent |
| `RELATED-TO` | JSCalendar has `relatedTo` but it's not populated |
| `ATTACH` with URI | JSCalendar `links` is the equivalent; mapping isn't wired |
| `GEO` | Deprecated in favor of `COORDINATES` (draft-ietf-calext-icalendar-jscalendar-extensions); JSCalendar has `locations[].coordinates`; neither field is mapped |
| `CONFERENCE` (RFC 7986) | JSCalendar `virtualLocations`; mapping not implemented |
| `IMAGE` (RFC 7986) | No JSCalendar equivalent |
| `SHOW-WITHOUT-TIME` (new draft property) | Defined in draft-ietf-calext-icalendar-jscalendar-extensions; not yet in the conversion layer |
| `X-*` custom properties | Dropped unconditionally |
| `DTSTAMP`, `CREATED`, `LAST-MODIFIED` | Server-managed; not preserved |
| `PARTICIPANT` (RFC 9073) | Could map to `participants`; not wired |
| `REQUEST-STATUS` | Used in scheduling replies; not used in the conversion layer |

### JSCalendar fields with no iCalendar equivalent

| Field | Notes |
|-------|-------|
| `virtualLocations` | Video conference links; maps to `CONFERENCE` (RFC 7986) but conversion isn't implemented |
| `links` | Arbitrary URL references; would map to `ATTACH` but conversion isn't implemented |
| `relatedTo` | Component relationships; `RELATED-TO` (RFC 9073) is the iCalendar side |
| `replyTo` | Set of URIs/methods for scheduling replies; richer than `ORGANIZER` alone |
| `sentBy` | Who sent the invitation on behalf of the organizer; iCalendar has `SENT-BY` parameter on `ORGANIZER` |
| Per-user properties | `alerts`, `color`, `keywords` can be per-user on shared events; iCalendar has no concept of this |
| `localizations` | Per-language overrides for title, description, locations; no iCalendar equivalent |

### Fidelity issues

- Fractional seconds in ISO 8601 durations are truncated to whole seconds
  (`int(float(sec_str))` in `_duration_to_timedelta`)
- Multiple `LOCATION` properties collapse to one on round-trip back from
  JSCalendar (`_locations_to_location` returns the first name it finds)
- `DTSTAMP` is regenerated on each `jscal_to_ical` call (`datetime.now(utc)`)
  rather than preserved; this increments the timestamp on every fetch-and-store
- `RECURRENCE-ID;RANGE=THISANDFUTURE` is not handled — this construct splits a
  recurring series into two; JSCalendar has no equivalent and the conversion
  spec defers on it
- `VALARM` `ACKNOWLEDGED` property (RFC 9074) is not preserved

---

## Specification Status

| Specification | Status |
|---------------|--------|
| [RFC 8620](https://www.rfc-editor.org/rfc/rfc8620) — JMAP Core | Published (2019). Stable. Session bootstrap, method dispatch, error types, blob upload/download via `uploadUrl`/`downloadUrl`. |
| [RFC 8984](https://www.rfc-editor.org/rfc/rfc8984) — JSCalendar | Published (2021). The data format this library converts to and from. Being superseded by JSCalendar 2.0. |
| [JMAP Calendars](https://datatracker.ietf.org/doc/draft-ietf-jmap-calendars/) (draft-ietf-jmap-calendars-26) | In the RFC Editor queue in **IESG hold state** as of this writing (submitted Nov 2024; 66+ weeks in queue). The document is awaiting IESG action before it can proceed to editing and publication. IANA expert reviews are approved. Defines `Calendar/get/set/changes`, `CalendarEvent/get/set/query/changes/copy/parse`, `CalendarEventNotification`, `Principal/get/getAvailability`, `ParticipantIdentity`, and `PushSubscription`. |
| [RFC 9404](https://www.rfc-editor.org/rfc/rfc9404) — JMAP Blob Management | Published (Aug 2023). Adds `Blob/get`, `Blob/lookup`, `Blob/copy` methods for inline blob operations within a JMAP batch. Blob upload/download is defined in RFC 8620 §6. |
| [RFC 9610](https://www.rfc-editor.org/rfc/rfc9610) — JMAP for Contacts | Published (Dec 2024). Defines `AddressBook/get/set/changes/query`, `ContactCard/get/set/changes/query`. Uses JSContact (RFC 9553) as the data format. Shares the same JMAP session and account model as calendars. |
| [JSCalendar 2.0](https://datatracker.ietf.org/doc/draft-ietf-calext-jscalendarbis/) (draft-ietf-calext-jscalendarbis-15) | Active draft (rev. 15, Feb 2026; expires Aug 2026). AD Followup under Orie Steele; WG milestone Jul 2026 for IESG submission. Obsoletes RFC 8984. Aligns type annotations and registry policy with JSContact; deprecates properties that conflict semantically with iCalendar. |
| [iCalendar ↔ JSCalendar conversion](https://datatracker.ietf.org/doc/draft-ietf-calext-jscalendar-icalendar/) (draft-ietf-calext-jscalendar-icalendar-22) | In WG Last Call (rev. 22, Jan 2026; expires Jul 2026). WG milestone Jul 2026 for IESG submission. Defines authoritative bidirectional conversion rules for every IANA-registered iCalendar property. The conversion layer here predates this draft; alignment work needed once published. |
| [iCalendar extensions for JSCalendar](https://datatracker.ietf.org/doc/draft-ietf-calext-icalendar-jscalendar-extensions/) (draft-ietf-calext-icalendar-jscalendar-extensions-05) | In WG Last Call (rev. 05, expires Jul 2026). Defines new iCalendar properties to close the iCal↔JSCal round-trip gap: `COORDINATES` (replacing deprecated `GEO`; uses geo: URI), `SHOW-WITHOUT-TIME` (boolean flag), and a new `OWNER` participation role. Updates RFCs 5545, 7986, and 9073. |
| [JMAP Tasks](https://jmap.io/spec-tasks.html) | Specification at jmap.io only. The IETF draft (draft-ietf-jmap-tasks) expired September 2023 without progressing to RFC. The `urn:ietf:params:jmap:tasks` URN is defined at jmap.io, not in any RFC. This is the most spec-unstable part of the implementation. |
| [JMAP File Storage](https://datatracker.ietf.org/doc/draft-ietf-jmap-filenode/) (draft-ietf-jmap-filenode) | Active draft. Defines `FileNode` objects exposing blobs as a filesystem (metadata: name, parentId, blobId, size). Stalwart implements this. Not yet standardized. |
| [RFC 7986](https://www.rfc-editor.org/rfc/rfc7986) — iCalendar extensions | Published (2016). Defines `CONFERENCE`, `IMAGE`, `COLOR`, `NAME`, `REFRESH-INTERVAL`. `COLOR` is mapped; `CONFERENCE` → `virtualLocations` is not. |
| [RFC 9073](https://www.rfc-editor.org/rfc/rfc9073) — iCalendar relationships | Published (2021). Defines `PARTICIPANT`, `STRUCTURED-DATA`, `STYLED-DESCRIPTION`. |
| [RFC 9074](https://www.rfc-editor.org/rfc/rfc9074) — VALARM extensions | Published (2021). Defines `ACKNOWLEDGED`, `PROXIMITY` on alarms. `ACKNOWLEDGED` is not mapped. |
| [RFC 8887](https://www.rfc-editor.org/rfc/rfc8887) — JMAP WebSocket | Published (2021). Defines a WebSocket binding for JMAP as an alternative to HTTP for real-time push. Not implemented. |

---

## Server Compatibility

### Cyrus IMAP

**Tested.** The only server with integration tests. Docker setup at
`tests/docker-test-servers/cyrus/`, port 8802, user1/x.

Known gaps and quirks:

- `apiUrl` in the session response is a relative path (e.g. `/jmap/api`) rather
  than the absolute URL RFC 8620 requires. The client resolves it via `urljoin`.
- `CalendarEvent/parse` returns `unknownMethod`. The
  `urn:ietf:params:jmap:calendars:parse` sub-capability is not advertised.
- `urn:ietf:params:jmap:tasks` is absent from session capabilities. All task
  methods are untested against Cyrus.
- `CalendarEvent/participantReply` behavior is unknown — untested.
- Cyrus does not implement JMAP authentication (no session-level auth flow). Each
  request requires HTTP Basic Auth credentials sent directly.
- Push/EventSource support status is not documented; Cyrus notes JMAP
  implementation is a work in progress.

### Stalwart Mail

**Not yet tested.** In late 2025, Stalwart became the first open-source server
to implement the full JMAP collaboration suite: calendars, tasks, contacts (RFC
9610), file storage (draft-ietf-jmap-filenode), and sharing. Stalwart's
implementation was partly funded by NLNet's NGI Zero grant — the same program
that funds python-caldav's JMAP work.

Features Stalwart has that Cyrus doesn't:

- `CalendarEvent/parse` (configurable via `jmap.calendar.parse.max-items`)
- `urn:ietf:params:jmap:tasks` — task support (specific method coverage not yet
  verified against their documentation)
- `Calendar.shareWith` + `ParticipantIdentity` — full sharing model
- `PushSubscription` with EventSource and Web Push
- `Principal/getAvailability` — free/busy queries
- JMAP Contacts (RFC 9610) and JSContact (RFC 9553)
- JMAP File Storage (draft-ietf-jmap-filenode)

Adding a Stalwart Docker Compose setup to `tests/docker-test-servers/` would
unlock integration testing for almost every unimplemented feature in this library.

### Fastmail

**Not tested.** Fastmail runs Cyrus as its backend and layers its own JMAP
extensions. A paid account is required; automated testing isn't feasible.

As of early 2026, Fastmail exposes JMAP for mail only —
`urn:ietf:params:jmap:calendars` is not in their public API. Calendar access is
CalDAV only. Their documentation says JMAP calendar access will open once the
spec is published as an RFC. So: blocked on draft-ietf-jmap-calendars clearing
the RFC Editor queue.

### Apple iCloud Calendar

CalDAV only. No JMAP endpoint.

### Google Calendar

Proprietary REST API. Not CalDAV, not JMAP.

### Apache James

JMAP email only (`urn:ietf:params:jmap:mail`). Calendar support is not
implemented.

### CalDAV-only servers

Nextcloud, Baikal, Radicale, SOGo, DAViCal — none speak JMAP.

---

## Future Direction

### Stalwart integration tests

The highest-priority next step. Add a Stalwart Docker Compose setup to
`tests/docker-test-servers/stalwart/` and a `TestStalwart*` section to
`tests/test_jmap_integration.py`. This unlocks testing for `CalendarEvent/parse`,
task methods, sharing, free/busy, and `PushSubscription` — features impossible to
verify against Cyrus.

### Scheduling

JMAP scheduling is simpler to implement than CalDAV's because the server handles
all iMIP construction and delivery:

1. Add `"sendSchedulingMessages": true` to the `CalendarEvent/set` arguments
   dict. No other client change needed — the server dispatches iTIP.

2. Add `CalendarEvent/participantReply` — one builder, one parser, one client
   method `reply_to_event(event_id, participant_id, status)`.

3. Add `CalendarEventNotification/get` + `CalendarEventNotification/set` to read
   and clear the server's participant-change log.

4. Wire a high-level `save_with_invites()`-style method that combines step 1 with
   participant construction from the conversion layer.

Cyrus supports scheduling, so this doesn't need Stalwart.

### Calendar management

`JMAPCalendar.to_jmap()` is already there. Needed additions:

- `build_calendar_set(account_id, create, update, destroy)` method builder
- `parse_calendar_set(response_args)` response parser
- Client methods: `create_calendar(name, **kwargs)`, `update_calendar(id, patch)`,
  `delete_calendar(id)`

`shareWith`, `isSubscribed`, `defaultAlerts*`, and `includeInAvailability` all
follow naturally as keyword arguments or separate methods once `Calendar/set` is
wired.

### Richer event search

The `cal.search()` API (and its lower-level `search_events()` counterpart on the
client) currently exposes only `calendar_id`, `start`, `end`, `text`.
The `build_event_query()` function already accepts an arbitrary filter dict — the
client method just needs to expose more of it.

A fluent builder analogous to `CalDAVSearcher` is the right eventual API shape
(not yet implemented — `cal.search()` currently takes keyword args only):

```python
# future
events = (
    cal.search()
       .after("2026-01-01T00:00:00")
       .has_keyword("work")
       .is_undecided()
       .fetch()
)
```

### CalendarEvent/queryChanges

One method builder + one parser + one client method
`get_query_changes(query_state, filter, sort)`. Useful for applications that
maintain a filtered view (e.g. "this week's events") and want efficient delta
updates instead of re-running the full query.

### Task sync and search

`Task/changes` and `Task/query` are structurally identical to their
`CalendarEvent` equivalents — same builder pattern, same result reference trick
for batching query + get into one round-trip. Straightforward to implement once
Stalwart is available for testing.

### JSCalendar 2.0 readiness

When `draft-ietf-calext-jscalendarbis` becomes an RFC (WG milestone Jul 2026),
the conversion layer needs an audit. Likely changes based on rev 15:

- `@type` annotation convention aligned with JSContact
- Top-level `version` field on JSCalendar objects
- Deprecated properties that "semantically conflict with iCalendar elements" —
  exact list to review from the spec diff
- Updated IANA registry procedures

No breaking changes to the public API are expected.

### iCalendar ↔ JSCalendar conversion alignment

Once `draft-ietf-calext-jscalendar-icalendar` is published (WG milestone Jul
2026), the conversion layer should be audited. Fields currently unhandled that
will have well-defined mappings:

- `CONFERENCE` (RFC 7986) → `virtualLocations` — Stalwart uses this in practice;
  worth prioritizing
- `RELATED-TO` → `relatedTo` — needs only the `RELTYPE` parameter mapped
- `ATTACH` with URI → `links` — straightforward once blob support is in place
- `RDATE` → `recurrenceOverrides` — the draft may define a conversion via
  fabricated override entries

Also: the new iCalendar extensions draft
(`draft-ietf-calext-icalendar-jscalendar-extensions`) introduces `COORDINATES`
(replacing `GEO`) and `SHOW-WITHOUT-TIME` as a proper iCalendar property.
Once those properties appear in real-world data from Stalwart, the conversion
layer should handle them. `SHOW-WITHOUT-TIME` is particularly
relevant since the library already maps the JSCalendar `showWithoutTime` field —
the new iCalendar property is the round-trip complement.

### Attachment support

Upload: POST to `uploadUrl` (from session) → `blobId` → embed in
`CalendarEvent.links`. Download: GET to `downloadUrl` with `blobId`
interpolated. Wire `ATTACH` → `links` in `ical_to_jscal` and `links` → `ATTACH`
in `jscal_to_ical`.

The RFC 9404 Blob Management Extension (`Blob/get`, `Blob/lookup`, `Blob/copy`)
enables batching blob operations within a normal JMAP method call, which is
useful for retrieving blob metadata without a separate HTTP fetch.

Blob upload also enables `CalendarEvent/parse`: upload the iCalendar file as a
blob, pass the `blobId` to the parse method, get structured events back.

### Free/busy

`Principal/getAvailability` — give it principal IDs or email addresses and a
time range; get structured availability JSON back. No VFREEBUSY to parse.

Requires `Principal/get` first: resolve the current user's principal ID and
resolve email addresses to principal IDs for querying other users' availability.
Both `Principal/get` and `Principal/getAvailability` are defined in the JMAP
Calendars spec (in RFC Editor queue now).

### Push notifications

`PushSubscription/set` registers an EventSource or Web Push endpoint. The server
sends `StateChange` objects when data changes; the client calls the relevant
`*/changes` method for the delta.

EventSource push is the right first target — persistent HTTP connection, no
third-party gateway, and testable with Cyrus. Once in place, the same
infrastructure works for any data type that has a `*/changes` method, including
tasks and contacts.

### Sharing

`Calendar.shareWith` + `ParticipantIdentity` + `Principal` objects. The
`ParticipantIdentity` resource is particularly important: it gives the client the
canonical list of the current user's email addresses and identities as the server
knows them, enabling reliable self-identification in event participants without
email-string matching.

Depends on Stalwart for testing. Cyrus doesn't implement the sharing model.

### Contacts integration

Since RFC 9610 (JMAP for Contacts) is already published and Stalwart implements
it, contacts become accessible as soon as Stalwart is in the test matrix.
`urn:ietf:params:jmap:contacts` is a separate capability on the same JMAP
session — same `apiUrl`, same `accountId`, no additional auth. A `JMAPContactsClient`
that wraps `AddressBook/get` and `ContactCard/get/query` could be added without
touching any existing code.

This is valuable for calendar use: resolving participant email addresses to
contact cards, auto-populating organizer display names, and letting users query
their address book when building event participant lists.

### Unified protocol-agnostic client

Not in scope for `python-caldav`. Making `get_davclient()` return JMAP clients
would create a hard-to-reverse public API commitment before JMAP Calendars has
even been published as an RFC, and it would tangle the two protocol libraries
together. The right home is a future higher-level `calendaring-client` library
that wraps both `DAVClient` and `JMAPClient` once the spec stabilises.

```python
# future, in a separate library
client = get_calendar_client(url="https://cal.example.com", username="alice", password="s3cr3t")
calendars = client.get_calendars()  # works regardless of protocol
```

The groundwork is already there. Both clients now share the same calendar-scoped
method names — `get_calendars()`, `cal.search()`, `cal.get_object_by_uid()`,
`cal.add_event()` — which is what makes unification tractable at all. The main
remaining design problem is that JMAP events are identified by opaque
server-assigned IDs while CalDAV events use URLs; this leaks through at the CRUD
layer and needs a clean abstraction.

Discovery: RFC 6764 DNS-SRV handles CalDAV. JMAP uses `/.well-known/jmap` (RFC
8620 §2.2) and optionally a `_jmap._tcp` SRV record. A unified client would probe
both and use whichever responds.
