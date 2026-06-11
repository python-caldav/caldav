# Full Codebase Review — June 2026

**Date:** 2026-06-11
**Reviewer:** Claude Fable 5 via Claude Code (AI multi-agent review)
**Scope:** The entire `caldav/` package (~18,800 lines) at commit `672a8c06`
(branch `fix/issue-681-timerange-vcalendar`). Not a differential review —
every source file was read.
**Method:** Seven parallel "finder" agents (four correctness sweeps split by
layer, plus JMAP, cleanup/duplication, and security/altitude angles) produced
~54 candidates; every candidate not already proven by a live repro was then
passed to an independent verifier agent. **All 31 externally verified
candidates came back CONFIRMED; none were refuted.** Each finding below is
tagged `[repro]` (demonstrated by executing code) or `[code]` (confirmed by
code reading / cross-referencing).

Tests were *not* run as part of this review (integration tests are slow);
line numbers refer to commit `672a8c06`.

---

## Executive summary

The codebase is in good shape architecturally — the sans-I/O search generator,
the compatibility-hints feature matrix, and the discovery module's TLS
handling were all noted positively. But the review found a substantial crop of
real bugs, clustering around four themes:

1. **Sync/async drift is the dominant bug source.** The parallel
   sync/async implementations (`davclient` vs `async_davclient`,
   `jmap/client` vs `jmap/async_client`, sync/async twins in
   `calendarobjectresource`) have diverged in at least seven places:
   fixes/workarounds applied to one side only (§1.3, §2.9, §2.10, §2.11),
   different credential precedence (§1.2), and outright broken async paths
   (§1.4, §1.5). The ~600 lines of remaining duplication (§6) is the root
   cause.
2. **String/regex-level iCalendar and URL fixups are brittle.** Three of the
   four documented fixups in `vcal.fix()` are broken (one actively corrupts
   data, two are dead code), and `URL.canonical()` both leaks credentials and
   mutates the object during `==` (§2.1–§2.5).
3. **The search workaround layer can silently drop filters** — three confirmed
   paths return wrong (over-broad) result sets (§2.6–§2.8).
4. **The JMAP backend has correctness gaps in the JSCalendar converters**
   (wrong DTSTART on overrides, floating EXDATEs that don't exclude anything,
   STATUS dropped both directions) and in update semantics (§5).

**Counts:** 13 crash bugs, 21 silent-wrong-result bugs, 3 security findings,
8 JMAP findings (overlapping the previous categories), 8 cleanup items,
2 altitude/design notes.

---

## 1. Crash bugs (realistic trigger → unhandled exception)

### 1.1 `calendarobjectresource.py:1167` + `:1187` — 302 handling iterates headers as tuples `[repro]` ✅ FIXED (commit 22b9cc66+1)
`[x[1] for x in r.headers if x[0] == "location"][0]` — iterating a dict-like
`Headers` object (niquests `CaseInsensitiveDict` sync, `httpx.Headers` async)
yields key *strings*, so `x[0]` is the first character of each header name.
The list is always empty and **any 302 response to a PUT raises IndexError**
instead of following the redirect. The same broken pattern appears twice
because the whole block is pasted twice (see §6.2; the second copy is partly
dead code). Fix: `r.headers.get("location")`.

### 1.2 `davclient.py:302` — URL with username but no password → TypeError `[repro]`
`DAVClient(url='https://user@example.com/dav/', password='secret')`:
`self.url.username` is set, so `unquote(self.url.password)` runs with
`password=None` → TypeError inside `urllib.parse.unquote`. The async client
(`async_davclient.py:229–237`) checks username/password independently — and
also gives **explicit kwargs precedence over URL credentials, while sync does
the opposite**. Pick one precedence (kwargs should win) and share the code.

### 1.3 `davclient.py:836` / `async_davclient.py:376` — rate-limit retry: `None + float` `[code]`
`sleep_seconds += rate_limit_time_slept / 2` executes *before* the
`sleep_seconds is None` check. With `rate_limit_handle=True` and
`rate_limit_default_sleep=None`: first 429 has `Retry-After: 5` → retried;
second 429 has no usable Retry-After (`compute_sleep_seconds` returns None,
e.g. `Retry-After: 0`) → `None += 2.5` → TypeError instead of the documented
`RateLimitError`. Same bug copy-pasted in both clients.

### 1.4 `async_davclient.py:1272` — `aio.get_calendars(calendar_name=...)` can never work `[code]`
The async module-level helper awaits the *synchronous* `Principal.calendar()`,
which has no async dispatch (`collection.py:448–475`): `calendar_home_set` →
`get_property` returns a coroutine for async clients, and
`CalendarSet.calendar()` iterates `self.get_calendars()` which is also a
coroutine → TypeError (swallowed into an empty result when
`raise_errors=False`). Name-based calendar lookup via `caldav.aio` is broken
end-to-end.

### 1.5 `collection.py:601` — async `freebusy_request` with Principal attendees → AttributeError `[code]`
`add_attendee(attendee)` is called *before* the `is_async_client` branch at
line 604. For a `Principal` attendee on an async client,
`get_vcal_address()` returns a coroutine, and `add_attendee` then does
`attendee_obj.params[...]` → AttributeError (plus a never-awaited warning).
`_async_save_with_invites` (`collection.py:983–984`) already does the awaited
conversion correctly — the same dance is missing here.

### 1.6 `calendarobjectresource.py:727` — `add_attendee("MAILTO:user@example.com")` → UnboundLocalError `[code]`
The string-branch chain is case-sensitive: uppercase `MAILTO:` (common in
real-world iCalendar; RFC 3986 schemes are case-insensitive) fails
`startswith("mailto:")` and fails the `":" not in attendee` branch, so
`attendee_obj` is never assigned and line 742 raises UnboundLocalError.

### 1.7 `calendarobjectresource.py:1272` — `change_attendee_status` raises bare KeyError; `:1284` literal `%s` `[repro]`
When the component has no ATTENDEE property at all, `ical_obj['attendee']`
raises `KeyError('ATTENDEE')` — not `error.NotFoundError`, which is the only
thing the principal-address loops catch — so the "Principal is not invited"
fallback is unreachable. Additionally the genuine not-found raise is
`error.NotFoundError("Participant %s not found in attendee list")` with no
`% attendee`: the user literally sees `%s`.

### 1.8 `lib/auth.py:31` — IndexError on malformed WWW-Authenticate `[repro]`
`extract_auth_types('Basic realm="x",')` (trailing comma — seen in the wild)
→ the empty segment makes `h.split()[0]` raise IndexError, aborting the auth
negotiation with an unrelated traceback. Guard with
`for h in header.split(",") if h.strip()`.

### 1.9 `config.py:37` — missing section raises KeyError instead of returning empty `[repro]`
`expand_config_section` does `config[section]` for non-glob names. A config
file with only named sections (no `default`) makes plain
`caldav.get_calendars()` crash with `KeyError: 'default'` instead of falling
through to "no configuration found".

### 1.10 `compatibility_hints.py:611` — `copyFeatureSet` crashes merging plain-string features `[repro]`
`FeatureSet({'scheduling': 'unsupported'}).copyFeatureSet({'scheduling':
'fragile'})` → bare AssertionError: the `'support' not in server_node` guard
makes string-valued updates of an existing feature fall through to the final
`else: raise AssertionError`. Plain strings are the dominant style in the
hint dicts, so any two-layer merge expressing the same feature crashes.

### 1.11 `compatibility_hints.py:605` — unknown feature names: warn now, crash later `[repro]`
A typoed feature name in a user's config produces only a UserWarning at set
time, but the bad key is still stored — a later `collapse()` /
`is_supported()` hits a message-less AssertionError in `find_feature`, far
from the config that caused it. Reject (or drop) the key at intake instead.

### 1.12 `lib/vcal.py:93` — bare `assert` on server-supplied data `[repro]`
Truncated/garbage iCalendar without DTSTAMP and without an `END:` line makes
`fix()` raise a bare AssertionError. Under `python -O` the assert (and thus
the DTSTAMP fixup logic it guards) is silently skipped. Should be
`error.assert_` or a proper parse error.

### 1.13 `jmap/client.py:576` / `jmap/async_client.py:461` — `create_task` missing the guard `create_event` has `[code]`
`create_event` handles an empty `created` dict with a descriptive
`JMAPMethodError` (`client.py:294–298`); `create_task` does
`created["new-0"]["id"]` unguarded → bare KeyError, bypassing the JMAP error
hierarchy callers are told to catch. Copy-paste gap in both clients.

---

## 2. Silent wrong results / data corruption

### 2.1 `lib/vcal.py:80` — COMPLETED fixup merges the next line into the property ⚠ data corruption `[repro]` ✅ FIXED (commit 22b9cc66)
`fix()` normalizes CRLF→LF first, then the COMPLETED date-to-datetime regex
`(\d+)\s` *consumes the newline without restoring it*:
`COMPLETED:20240101\nSUMMARY:hello` becomes
`COMPLETED:20240101T120000ZSUMMARY:hello`. The following property is
destroyed and the object parses with corrupted data. This runs on every
inbound object.

### 2.2 `lib/vcal.py:242` — `create_ical(ical_fragment=...)` injects the fragment inside VALARM `[repro]`
The fragment is re-inserted before the first `^END:V` line — which is
`END:VALARM` when any `alarm_*` props were given. `ical_fragment='RRULE:...'`
plus an alarm produces an event *without* recurrence and with an invalid
RRULE inside the alarm. Should target `END:VEVENT|VTODO|VJOURNAL`.

### 2.3 `lib/vcal.py:88` — trailing-whitespace fixup is dead code `[repro]`
`re.sub(" *$", "", fixed)` without `re.MULTILINE` only touches the document
end, never the per-line trailing spaces (iCloud X-APPLE-STRUCTURED-EVENT)
that docstring fix #4 targets. The vobject traceback it was written to
prevent still occurs.

### 2.4 `lib/vcal.py:85` — backslash-unescape regex is a no-op `[repro]`
`re.sub(r"\\+('\")", r"\1", fixed)` matches only the literal two-character
sequence `'"`; the group should be a character class `['\"]`. Harmless for
compliant data, but the fix does nothing.

### 2.5 `lib/url.py:143` + `:159` — `canonical()` keeps credentials and mutates self `[repro]` ✅ FIXED
Two related bugs: (a) `canonical()` builds its result from `self.url_parsed`
instead of the `unauth()`'ed URL, so
`URL('https://user:pass@example.com/cal/').canonical()` **retains the
credentials** — and `__eq__`/`__hash__` between the client URL and the same
URL from a server href (no credentials) is False, breaking URL comparison.
(b) When there's no auth part, `unauth()` returns `self` and `canonical()`
then overwrites `url_raw`/`url_parsed` **in place** — a mere `==` comparison
silently rewrites the URL (port added, path re-quoted; a literal `+` becomes
`%2B`), so subsequent requests can go to a different resource.

### 2.6 `search.py:648` — `combined-is-logical-and` workaround silently drops property filters `[code]` ✅ FIXED
The workaround strips property filters from the server query but passes the
*ambient* `post_filter` (still `None` on otherwise-capable servers — e.g.
Nextcloud, whose only relevant flag is `search.combined-is-logical-and:
False`) to `filter_search_results`, which short-circuits on falsy. A search
with a time range plus a SUMMARY filter returns **every** object in the time
range. The sibling workarounds at 597–604 and 625–632 correctly force
`post_filter=True`; this branch also uniquely lacks the
`post_filter is not False` guard.

### 2.7 `search.py:193` — `undef` operator misses the category→CATEGORIES alias `[code]`
The `undef` branch emits `PropFilter(property.upper())` without the alias
mapping the non-undef branch applies, so
`add_property_filter('category', '', operator='undef')` queries the
nonexistent property `CATEGORY` — `is-not-defined` on it matches *every*
object, returning events that do have categories.

### 2.8 `search.py:362`/`:506` — documented `'=='` exact-match is never enforced `[code]`
The docstring promises "`==` — exact match required, enforced client-side",
but no code path inspects the `==` operator (only `'contains'` is checked at
line 617) and the post-filter default block ignores it. On a fully-capable
server, RFC 4791 substring `text-match` semantics leak through: `'=='`
`'rain'` matches "Training".

### 2.9 `calendarobjectresource.py:1570` — `_set_data` leaves a stale `DataState` cache `[repro]` ✅ FIXED
The raw-string branch clears the legacy instance attributes but never resets
`self._state`. Sequence: fetch event → touch `event.id` / `is_loaded()`
(caches state v1) → `event.load()` assigns `self.data = r.raw` → afterwards
`get_data()` / `get_icalendar_instance()` / `id` still serve the **pre-reload
content** while `.data` returns the new content.

### 2.10 `datastate.py:152` (+ `:67`, `:78`) — `BEGIN:FREEBUSY` never matches `VFREEBUSY` `[repro]` ✅ FIXED
The component-type sniffing tests for `BEGIN:FREEBUSY`; real data says
`BEGIN:VFREEBUSY`. A `FreeBusy` object holding raw data gets
`get_component_type() → None`, so `is_loaded()`/`has_component()` are False,
`save()` **silently no-ops** at the early return, and
`load(only_if_unloaded=True)` reloads spuriously.

### 2.11 `calendarobjectresource.py:1943` — `_get_duration` isinstance check on the wrapper, not `.dt` `[repro]`
`isinstance(i["DTSTART"], datetime)` tests the icalendar `vDDDTypes` wrapper
(never a datetime), so the date-vs-datetime branch always takes the date
path: a VTODO with a timed DTSTART and no DUE/DURATION gets duration **1 day
instead of 0**. Completing a recurring task then sets the next DUE a full day
late, and `Todo._next` shifts the recurrence.

### 2.12 `calendarobjectresource.py:2140` — sync safe-mode completion ignores `completion_timestamp` `[code]`
`_complete_recurring_safe` calls `completed.complete()` (defaults to *now*)
while the async twin passes the caller's timestamp through. Sync/async
divergence with user-visible effect on the recorded COMPLETED time.

### 2.13 `base_client.py:689` — calendar with displayname `""` dropped from results `[code]`
`if _try(calendar.get_display_name, ...)` is a truthiness check, so a
calendar explicitly requested by URL whose displayname is the empty string is
silently omitted. The async counterpart (`async_davclient.py:1262`) correctly
uses `is not None`.

### 2.14 `async_davclient.py:957` — async `get_calendars()` lacks the GMX principal-URL fallback `[code]`
Sync `get_calendars()` (`davclient.py:486–489`) falls back to the principal
URL when `calendar-home-set` is missing; async returns `[]` for the same
server. Parity gap.

### 2.15 `async_davclient.py:487` — issue-#158 workaround can return the probe response as the real one `[code]`
When the original request dies with a connection abort, the workaround sends
a probe GET; if that GET is *not* 401+WWW-Authenticate (e.g. 200 with a login
page), the code falls through and returns the **probe GET's response as the
original request's response** — the caller sees status 200 for a PUT that
never happened, and the real connection error is lost. Also: the sync client
has no #158 workaround at all (parity gap in the other direction).

### 2.16 `async_davclient.py:435` — HTML-on-401 hint checks the wrong headers `[code]`
The diagnostic checks `self.headers` (the client's own request headers) for
`text/html` instead of `r.headers`, so the intended "server returned HTML,
maybe set auth_type" hint can never fire.

### 2.17 `config.py:50` — `disable: true` ignored for named sections `[repro]`
`expand_config_section` checks `config.get("section", ...)` with the string
literal `"section"` instead of the variable. `disable` only works under
`section='*'`; sections pulled in via a meta-section's `contains` list (or by
name) connect to servers the user explicitly disabled.

### 2.18 `config.py:265` — explicit params without url/features silently discarded `[code]`
`get_connection_params` honors `explicit_params` only when `url` or
`features` is present, and never merges them with the env/file source that
wins: `get_davclient(password='secret')` with `CALDAV_URL`/`CALDAV_USERNAME`
in env returns a config **without the password**, contradicting the
docstring's "explicit parameters take highest priority".

### 2.19 `config.py:180` + `testing.py:127`/`:263` — shared module-level hint dicts get mutated `[repro]`
`resolve_features` with a string name returns the module-level
`compatibility_hints` dict itself (the `base` branch deepcopies; this branch
doesn't). `XandikosServer`/`RadicaleServer` then do a *shallow* `.copy()` and
mutate the nested `auto-connect.url` dict — after instantiating
`XandikosServer({'port': 9999})`, `compatibility_hints.xandikos` is
permanently polluted for the whole process, redirecting any later
`features='xandikos'` client. Fix at the source: deepcopy in
`resolve_features` for all branches.

---

## 3. Security

### 3.1 `discovery.py:329` — `require_tls=True` not enforced on well-known redirect target `[code]` ✅ FIXED
`_well_known_lookup` never receives `require_tls`; a same-domain `Location:
http://...` passes the `_is_subdomain_or_same` check and is returned as
`ServiceInfo(tls=False)`, which `discover_service` returns unchecked. A
misconfigured or MITM'd server can downgrade the documented "ONLY accept TLS"
guarantee to plaintext, and credentials follow. (Otherwise the discovery
module's security posture is good: require_tls defaults True, same-domain
redirect validation, single manual redirect hop.)

### 3.2 `response.py:277` — XML parser for untrusted server data lacks entity hardening `[code]` ✅ FIXED
`etree.XMLParser(remove_blank_text=True, huge_tree=self.huge_tree)` relies on
libxml2 defaults for entity resolution. Current libxml2 blocks the classic
XXE paths, but the library makes no guarantee across the unpinned dependency
range, and `huge_tree=True` lifts expansion limits. This is the *only* parser
of server data in the package — one line fixes it: add
`resolve_entities=False` (and consider `no_network=True`, `dtd_validation=False`
explicitly).

**Fixed**: added `resolve_entities=False, no_network=True` to the `etree.XMLParser` call in `response.py:277`.  `dtd_validation=False` is lxml's default so was not added explicitly.

### 3.3 `lib/error.py:51` — `PYTHON_CALDAV_COMMDUMP` persists bodies/headers in /tmp (low) `[code]`
`NamedTemporaryFile(delete=False)` dumps full request/response headers and
bodies (calendar PII, custom auth headers) to files that accumulate
indefinitely. Files are 0600, and the niquests-applied Authorization header
is added after the dump point, so exposure is limited — but a cleanup policy
or a documented warning would be appropriate.

**Ruled out** (checked, found safe): SSRF via server-returned hrefs
(`_normalize_href` reduces absolute URLs to path-only); credential leak on
cross-host redirects (auth applied via auth callable, stripped by
`rebuild_auth`); eval/shell/format-string injection from iCalendar content.

---

## 4. JMAP backend

### 4.1 `jmap/convert/jscal_to_ical.py:384` — override child VEVENT gets the master's DTSTART `[repro]`
`child_start = patch.get("start", start_str)` defaults to the master start.
An override that doesn't move the occurrence (e.g. title-only change — the
common case) renders a child VEVENT with RECURRENCE-ID at the occurrence but
DTSTART at the *master's* start, relocating the occurrence. Default must be
the override key (`rid_dt`).

### 4.2 `jmap/convert/jscal_to_ical.py:375` — EXDATE/RECURRENCE-ID value-type mismatch `[repro]`
Override keys are rendered as naive floating DATE-TIMEs regardless of the
event's `timeZone`/`showWithoutTime`: a TZID-anchored event gets
`EXDATE:20260620T100000` (floating — per RFC 5545 it does not match the
instance, so the **excluded occurrence reappears**), and an all-day event
gets a DATETIME EXDATE against a `VALUE=DATE` DTSTART.

### 4.3 `jmap/convert/ical_to_jscal.py:100` (via `_utils.py:129`) — `Z`-suffix in LocalDateTime slots `[repro]`
UTC inputs produce `...Z` strings for RRULE `until` and recurrenceOverrides
keys; RFC 8984 requires LocalDateTime there. Strict servers reject with
`invalidArguments`; lenient ones mis-set the boundary, and a `Z`-suffixed
override key can never match a LocalDateTime occurrence key.

### 4.4 `jmap/convert/*` — STATUS dropped in both directions `[code]`
Neither converter maps `STATUS` ↔ `status` (only
participationStatus/freeBusyStatus exist). `STATUS:CANCELLED` round-trips to
the JSCalendar default `confirmed`; cancelled meetings come back as active.

### 4.5 `jmap/client.py:346` / `async_client.py:233` — `update_event` patch never clears removed properties `[code]`
The full converted object is sent as the RFC 8620 PatchObject; the converter
only includes keys conditionally, so a property deleted client-side (e.g.
LOCATION, VALARM) is simply *absent* from the patch and **persists on the
server**. Clearing requires explicit `null` entries.

### 4.6 `jmap/objects/calendar.py:113` — search `after`/`before` are not UTCDate `[code]`
`datetime.isoformat()` is passed straight through (naive → no `Z`, aware →
`+02:00` offset, plus microseconds); JMAP requires `...Z` UTCDate. Strict
servers reject the query; lenient ones interpret the window inconsistently.

### 4.7 `jmap/client.py:462` / `async_client.py:347` — `newState` from `/changes` discarded `[code]`
`get_objects_by_sync_token` unpacks `new_state` into `_`. Callers' only
option for a new baseline is a separate `get_sync_token()` call — changes
landing in between are silently skipped on the next sync.

(See also §1.13 — `create_task` KeyError.)

---

## 5. Cleanup: duplication, simplification, efficiency

These don't break anything today, but §1–§4 show the duplication is already
producing drift bugs.

1. **`jmap/async_client.py` duplicates ~400 lines of `client.py` verbatim**
   modulo `await`. The build-side is already shared via `_JMAPClientBase` /
   `jmap/_methods`; moving the response-parsing glue into shared pure
   methods would shrink each sync/async method to ~3 lines. (The §1.13 and
   §4.5 bugs are duplicated exactly because of this.)
2. **`calendarobjectresource.py:1166–1205` — `_post_put` block pasted twice
   in sequence**; the second `elif r.status not in (204, 201)` is
   unreachable. Also factor the Etag/Schedule-Tag header→props snippet
   repeated in `load`/`_async_load` (the code itself carries a "consider
   refactoring - this is repeated many places now" comment).
3. **`async_davclient.py` re-implements ~200 lines of `DAVClient`**
   (init tail, get_calendars, rate-limit retry loop — byte-identical except
   `time.sleep` vs `asyncio.sleep`). The §2.14 GMX gap and §1.3 retry bug
   are direct drift products. Move into `BaseDAVClient` / `lib/error.py`.
4. **`search.py:869` — post-processing loads unloaded results one GET at a
   time**; `Calendar._multiget` can fetch them in a single REPORT. On the
   issue-#201 workaround path a 200-event search costs ~200 extra
   round-trips.
5. **JMAP clients open a fresh HTTP connection per request** (async:
   `async with AsyncSession()` per `_request`; sync: module-level
   `requests.post`). `__exit__`/`__aexit__` already exist but do nothing —
   hold one session in `_JMAPClientBase` and close it there.
6. **`Todo._async_complete_recurring_thisandfuture` copies ~60 lines of its
   sync twin** (the file says "TERRIBLY much code duplication here"), and
   the async safe-variant has drifted: it PUTs the completed copy twice.
   Extract a pure icalendar-mutation helper; keep 5-line sync/async
   wrappers.
7. **`response.py` carries two parallel multistatus-parsing stacks** —
   legacy `_find_objects_and_props`/`expand_simple_props` (still load-bearing
   for `_multiget`, report-result building, `search_principals`) vs the
   newer dataclass parsers. Every parsing quirk (Confluence %2540,
   purelymail 404) must be maintained twice; the TODO at line 577 already
   acknowledges this.
8. **`search.py` sync/async driver loops duplicated** (~80 lines including
   the Phase-1/Phase-2 exception-rethrow protocol and
   `_search_with_comptypes`). A small executor object with sync/async
   implementations would leave one driver.

---

## 6. Altitude / design notes

1. **`response.py:464` — server fingerprints hardcoded in the generic
   parser.** purelymail's `{https://purelymail.com}does-not-exist` tag,
   Stalwart's "No resources found" string, and SOGo status notes live in the
   core multistatus path instead of going through the compatibility-hints
   feature matrix. Adding the next server's 404 shape means editing generic
   parsing — the exact inversion the hints mechanism exists to avoid.
2. **`vcal.fix()` is a regex-rewriting layer applied to every inbound
   object.** §2.1–§2.4 show the current fixups are individually broken in
   four different ways; the module's own TODOs flag the approach. Worth
   considering parser-level normalization (icalendar) or at least
   regression-testing each fixup against the exact server output it was
   written for.

---

## 7. Recommended priorities

| Priority | Items |
|----------|-------|
| **Fix before next release** | §2.1 (data corruption on every fetch), §2.5 (URL credential leak + mutation during `==`), §2.6 (silently unfiltered search results), §1.1 (302 IndexError), §2.9/§2.10 (stale data / silent save no-op), §3.1 (require_tls downgrade), §3.2 (one-line XML hardening) |
| **Fix soon** | Remaining §1 crashes (1.2–1.13), §2.11–§2.19, §4.1–§4.5 (JMAP correctness) |
| **Schedule** | §5 dedup work (it is the bug factory behind at least 7 findings), §6 altitude items, §4.6–§4.7 |
| **Test gaps suggested by this review** | sync/async parity tests that diff behavior of twin methods; round-trip property tests for `jmap/convert`; unit tests for `vcal.fix()` fixups #1–#4; URL `canonical()`/`__eq__` immutability test |
