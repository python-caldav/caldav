This document was AI-generated, but has been reviewed and edited by a human.

# Retry and resilience design

- **Status:** proposal, not implemented.
- **Supersedes:** issue #620 (`sleep-retry-logic`), PR #648 (`issue647` branch).
- **Tracking issue:** https://github.com/python-caldav/caldav/issues/695
- **Milestone:** v3.x (after 3.3).

This document is the single place where retry behaviour for the CalDAV library is
specified.  It exists because three tickets turned out to describe the same
feature from three different angles:

| ticket | angle |
| --- | --- |
| https://github.com/python-caldav/caldav/issues/620 | opt-in, configurable *sleep-and-retry on transient server errors*, driven from the `features` config |
| https://github.com/python-caldav/caldav/issues/695 | retry on *connection failures*, particularly a keep-alive socket the server closed while idle |
| https://github.com/python-caldav/caldav/pull/648 | a concrete implementation: catch `ConnectionError`/`Timeout` from niquests and retry once for idempotent methods |
| https://github.com/python-caldav/caldav/issues/647 | the user-visible bug that triggered #648 - `c.events()` intermittently dies with `ConnectionError: None: Read timed out` |

Everything below about the HTTP libraries was verified by reading the installed
source, not from memory.  Versions checked: `niquests` 3.15.2,
`urllib3-future` 2.15.901, `requests` 2.34.2, `urllib3` 2.7.0, `httpx` 0.28.1,
`httpx2` 2.3.0, `httpcore` 1.0.9 (August 2026).

## 1. Three failure classes, not one

Retry logic gets muddled when "transient error" is treated as one thing.  It is
three, and they need different handling:

**(A) The request never reached the server.**  DNS failure, TCP connect
refused/timed out, TLS handshake failure, or - the #695 case - a pooled
keep-alive connection that the server closed while idle and that the client
picked for the next request.  A retry here cannot duplicate a write, because
nothing was written.  Safe for *every* method, including POST.

**(B) The request reached the server but the response did not come
back.**  Read timeout, connection reset mid-response, HTTP/2 stream
error.  The server may or may not have processed the request.  Safe
for methods that are idempotent by definition.  Not safe for POST -
but POST is not used in the caldav standard.  DELETE may result in an
error as the resource was already deleted, but that is already caught:
`DAVObject._post_delete()` accepts 404 as success today.  Of the ten
methods the library actually sends, that leaves only `MKCOL` and
`MKCALENDAR` with a real wrinkle (a retry after a lost success gives
405 or 409) - see §4.1 for the full method-by-method answer.

**(C) The server answered, with a status saying "not now".**  429, 503, and
arguably 500/502/504.  This is #620's original subject.  Retrying is safe (the
server declined to act), but it needs a *sleep*, ideally honouring
`Retry-After`.

The library already handles a subset of (C): `raise_if_rate_limited()` raises
`RateLimitError` on 429/503, and `DAVClient.request()` /
`AsyncDAVClient._async_request()` sleep and retry via
`error.compute_sleep_seconds()` when `rate_limit_handle` is set, with
`rate_limit_default_sleep` / `rate_limit_max_sleep` as bounds and a `rate-limit`
client-feature in `compatibility_hints.py` carrying `interval`, `count`,
`max_sleep`, `default_sleep`.  **Nothing new is built on top of that machinery,
and nothing new duplicates it.**  Whether it should eventually be deleted in
favour of `Retry(status_forcelist=[429, 503])` is taken up in §4.5 - the answer
is "yes, in 4.0, once urllib3-future can cap `Retry-After`".

Nothing at all handles (A) or (B) today: there is no `except ConnectionError`
anywhere under `caldav/`, and no adapter is mounted, so we run on library
defaults - and the library defaults are "retry nothing" in every one of the five
libraries we support.

## 2. What the HTTP libraries already give us

We support five libraries: niquests (sync + async, default), requests (sync
fallback), and httpx2 / httpxyz / httpx (async fallbacks).  See
`docs/source/http-libraries.rst`.

niquests is the supported and recommended http library - the priority is to solve things for niquests.

### Summary

| | niquests / urllib3-future | requests / urllib3 | httpx family / httpcore |
| --- | --- | --- | --- |
| retries on by default | no (`DEFAULT_RETRIES = 0`) | no (`HTTPAdapter(max_retries=0)`) | no (`retries=0`) |
| how to configure | `Session(retries=...)` / `AsyncSession(retries=...)` - no adapter mounting needed | `session.mount(scheme, HTTPAdapter(max_retries=Retry(...)))` | `Client(transport=HTTPTransport(retries=int))` |
| class (A) connect errors | yes, `Retry(connect=N)` | yes, `Retry(connect=N)` | yes, but *only* connect - `retries=int` |
| class (B) read errors | yes, `Retry(read=N)`, method-filtered | yes, `Retry(read=N)`, method-filtered | **no** |
| class (C) status retries | yes, `status_forcelist` + `Retry(status=N)` | yes, `status_forcelist` + `Retry(status=N)` | **no** |
| honours `Retry-After` | yes, `respect_retry_after_header=True` | yes (+ `retry_after_max=21600`) | **no** |
| backoff control | `backoff_factor`, `backoff_max=120`, `backoff_jitter` | same | hardcoded `0.5 * 2**n`, not configurable |
| method allow-list | `allowed_methods` | `allowed_methods` | **no** |
| proactive rate limiting | yes - `LeakyBucketLimiter`, `TokenBucketLimiter` (+ async variants) | no | no |
| keep-alive liveness | HTTP/2+ PING: `keepalive_delay=600`, `keepalive_idle_window=60` | no | no |

### niquests / urllib3-future - batteries fully included

`niquests.Session` and `niquests.AsyncSession` both take `retries: RetryType`
directly in the constructor, defaulting to `DEFAULT_RETRIES = 0`.  It accepts an
int or a `Retry` object; `niquests.RetryConfiguration` is a re-export of
`urllib3_future.util.retry.Retry`, so there is a public, documented name for it
that does not require importing `urllib3_future`.  The session pushes the value
into every adapter it builds, so **no `mount()` call is needed** - which matters,
because caldav never mounts anything today.

`Retry.__init__` (identical parameter list in `urllib3` 2.7.0 and
`urllib3_future` 2.15.901, except that urllib3 additionally has
`retry_after_max=21600`):

```python
Retry(total=10, connect=None, read=None, redirect=None, status=None, other=None,
      allowed_methods=frozenset({'OPTIONS','TRACE','DELETE','GET','HEAD','PUT'}),
      status_forcelist=None, backoff_factor=0, backoff_max=120,
      raise_on_redirect=True, raise_on_status=True, history=None,
      respect_retry_after_header=True,
      remove_headers_on_redirect=frozenset({'Proxy-Authorization','Cookie','Authorization'}),
      backoff_jitter=0.0)
```

Two details from the classification code that decide our design:

```python
def _is_connection_error(self, err):      # -> counts against `connect`
    return isinstance(err, ConnectTimeoutError)   # NewConnectionError subclasses this

def _is_read_error(self, err):            # -> counts against `read`
    return isinstance(err, (ReadTimeoutError, ProtocolError))
```

and `increment()` retries a *read* error only when
`self._is_method_retryable(method)`, i.e. when the method is in
`allowed_methods`.

**Consequence, and this is the single most important finding in this document:**
"Remote end closed connection without response" surfaces as a `ProtocolError`,
so urllib3 classifies it as a **read** error, not a connect error - even though
in this particular case nothing was ever delivered.  It is therefore
method-filtered, and the default `allowed_methods` contains neither `PROPFIND`
nor `REPORT`.  Handing the library a plain `Retry(3)` would leave the exact
failure #695 is about **unretried**, because CalDAV's two most-used methods are
not on urllib3's allow-list.  `allowed_methods` must be set explicitly.

Also worth knowing: `HTTPConnectionPool._get_conn()` already discards a dead
pooled connection - `if conn and is_connection_dropped(conn): conn.close()`.
That is a `select()` on the socket, so it closes the common window but not the
race: the server can close between the check and the write.  This is why #695
still happens even though the pool "already handles" stale connections, and why
a retry, not a liveness check, is the fix.

Related knobs that reduce how often we get there in the first place:
`keepalive_delay` (default 600s) and `keepalive_idle_window` (default 60s) make
niquests send HTTP/2+ PING frames on idle connections.  They do nothing for
HTTP/1.1, and CalDAV servers behind nginx with digest auth are on HTTP/1.1 for
us today (multiplexing is off by default - see the `http.multiplexing` feature).

niquests also ships *proactive* rate limiters (`LeakyBucketLimiter`,
`TokenBucketLimiter`, and async variants).  Those map onto the `interval`/`count`
half of our existing `rate-limit` client-feature, which we currently implement in
test code.  Out of scope here, but noted: there is a wheel we could stop
reinventing.

### requests / urllib3 - same batteries, one extra step

`HTTPAdapter.__init__(pool_connections=10, pool_maxsize=10, max_retries=0,
pool_block=False)` - retries off.  `requests.Session.__init__` takes no
arguments at all, so configuring retries means constructing an adapter and
mounting it on both `http://` and `https://`.  Same `Retry` class, same
semantics, so one `Retry`-building helper serves both libraries.

### httpx family - nearly no batteries

`httpx.HTTPTransport` / `AsyncHTTPTransport` (identical signature in httpx
0.28.1 and httpx2 2.3.0 - httpx2 brings *nothing* extra here) accept
`retries: int = 0`, forwarded to `httpcore.ConnectionPool(retries=...)`.  In
httpcore that value is consumed in exactly one place, `HTTPConnection._connect`:

```python
retries_left = self._retries
...
except (ConnectError, ConnectTimeout):
    if retries_left <= 0:
        raise
    retries_left -= 1
```

So: connection *establishment* only.  No read retries, no status retries, no
`Retry-After`, no method filter, no configurable backoff (httpcore sleeps
`0.5 * 2**n` internally).  For the httpx family, classes (B) and (C) can only be
handled by caldav itself, or by a third-party transport such as `httpx-retries`
(`RetryTransport`), which we should *not* take on as a dependency.

## 3. Layering decision

```
   ┌──────────────────────────────────────────────────────────────────┐
   │ caldav: DAVClient.request() / AsyncDAVClient._async_request()    │
   │                                                                  │
   │  Layer B - status retries (class C)                              │
   │    429/503 today, opt-in 5xx tomorrow, reuses compute_sleep_..() │
   │  Layer C - the niquests lazy-gather catch (class B, special)      │
   │    wrap ConnectionError/Timeout raised at attribute access        │
   ├──────────────────────────────────────────────────────────────────┤
   │ Layer A - transport retries (classes A and B)                    │
   │   niquests:  Session(retries=Retry(...))                         │
   │   requests:  mount(HTTPAdapter(max_retries=Retry(...)))          │
   │   httpx*:    HTTPTransport(retries=n)   [connect only, degraded] │
   └──────────────────────────────────────────────────────────────────┘
```

**Layer A handles what caldav cannot see.**  A socket that dies before or during
the write, a DNS hiccup, a TLS renegotiation - by the time an exception reaches
`DAVClient.request()`, the connection is gone, the response body is
unrecoverable, and all caldav can do is send the whole request again from
scratch.  urllib3 can do better: it retries inside the pool, reuses the
connection machinery, tracks the budget across redirects, and honours
`Retry-After`.  It is also far better tested than anything we would write.
**Do not hand-roll this.**

**Layer B is where the existing 429/503 handling already lives, and it gets no
new code.**  `status_forcelist` in `Retry` does the job for niquests and requests,
and duplicating it in caldav would mean two mechanisms racing over the same
responses.  So for 3.x the existing `rate_limit_handle` loop stays as it is, and
429/503 deliberately stay *out* of `status_forcelist` so the two never overlap.
Whether that loop can be **deleted** and the job handed to niquests entirely is a
separate and attractive question - see §4.5, where the answer turns out to be
"yes, but not yet, and not for free".

**Layer C is the only part that genuinely needs new caldav-side code for class
(B),** and it is the part PR #648 got right.  niquests gathers HTTP/2 responses
lazily: the request returns a `Response` whose `status_code`/`headers`/`content`
are resolved on first access, and that resolution can raise
`niquests.exceptions.ConnectionError`.  #647's traceback shows it firing from
`log.debug("server responded with %i %s" % (r.status_code, r.reason))` inside
`request()` - i.e. **after** `adapter.send()` returned, therefore **outside**
urllib3's retry scope.  No `Retry` configuration can cover this.  It needs a
`try`/`except` around the point where caldav first touches response attributes.

### 3.1 Scope: niquests first - and what the others actually cost

niquests is the supported and recommended library, so it sets the schedule.  The
question worth asking is whether to stop there.  Measured against the real code,
the answer is "no, but nearly" - because the expensive part of this feature is
not the per-library plumbing, it is deciding the policy (defaults,
`allowed_methods`, the config surface), and that is shared by all of them.

**niquests: one keyword argument, twice.**  Both session constructors already sit
behind a `try`/`except TypeError` that exists to tell niquests and the fallback
apart:

```python
## caldav/davclient.py:261-265, as it stands today
try:
    multiplexed = self.features.is_supported("http.multiplexing")
    self.session = requests.Session(multiplexed=multiplexed)
except TypeError:
    self.session = requests.Session()
```

The niquests fix is `retries=retry_cfg` added to that call, and the same in
`AsyncDAVClient._create_session()` for `AsyncSession`.  Two lines of diff.
Everything else is the shared `_build_retry()` helper and the config plumbing.

**requests: four more lines, same `Retry` object.**  `requests.Session` takes no
constructor arguments, so it needs a mounted adapter - but the `Retry` class has
an identical parameter list in `urllib3` 2.7.0 and `urllib3_future` 2.15.901, and
`niquests.Session.__init__` even converts a vanilla urllib3 `Retry` for you
(`urllib3_ensure_type()` when `"urllib3_future" not in str(type(self.retries))`).
So one builder serves both; only the import differs
(`niquests.RetryConfiguration` when niquests is in use, `urllib3.util.retry.Retry`
otherwise - and the module already has `_USE_NIQUESTS` to branch on):

```python
except TypeError:
    self.session = requests.Session()
    if retry_cfg is not None:
        adapter = requests.adapters.HTTPAdapter(max_retries=retry_cfg)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
```

Excluding requests would save four lines and one conditional import.  That is a
false economy, and the audience argues against it too: the requests fallback
exists because a distro packager objected to niquests, and
`docs/source/http-libraries.rst` recommends requests for "a very sharp production
environment" - which is exactly the deployment that needs retries most.  **Do
requests in the same change.**

**httpx family: cheap-looking, actually a refactor - defer it.**  `retries=` is
an int on the *transport*, not on the client, and `httpx.AsyncClient(transport=...)`
**ignores** the `verify`, `cert`, `http2` and `limits` keywords when a transport
is supplied - they only configure the default transport it would otherwise build.
`_create_session()` passes exactly those keywords today, so adding a transport
means moving TLS configuration into the transport constructor.  The failure mode
if that is done carelessly is silently disabled certificate verification.  For
that risk we would buy connect-retries only: no read retries, so **not even the
failure this design is named after**.  Defer, and document that the httpx
fallbacks get no retries.

**Layer C cannot be delegated to any library.**  Worth being explicit, because it
is the one place where "this belongs in the HTTP library" does not get us out of
writing code: the lazy-gather `ConnectionError` is raised after `adapter.send()`
has returned, so it is outside every retry mechanism niquests has.  If we do
Layer A only, https://github.com/python-caldav/caldav/issues/647 - the bug that
started this - stays open.  It should *also* be reported upstream to
https://github.com/jawah/niquests, with the traceback and the observation that
the session's retry budget does not extend to lazy response gathering; that is
where the fix belongs long-term.  Note that a previous report in this area
(jawah/niquests#352) was closed as "Not Planned" because the analysis handed to
the maintainer was AI-hallucinated nonsense, so this one needs to be precise,
minimal and reproducible, or not filed at all.

**Total.** The niquests-only version is roughly an hour of work: two keyword
arguments, a ~25-line `_build_retry()`, the `retry` config key, and unit tests
asserting the constructed `Retry` (no server needed).  Including requests adds
minutes.  Including httpx adds a TLS-adjacent refactor and buys the least.  So:
niquests and requests now, httpx when someone asks for it.

The cost of divergence is a documentation cost, not a code cost - the §2 table is
written for users as much as for us, and `docs/source/http-libraries.rst` needs
the one-liner "the httpx fallbacks do not retry".  A `retry` setting that cannot
be honoured should say so rather than pretend, so constructing an httpx-backed
client with an explicit `retry` config should warn.

## 4. Proposed behaviour

### 4.1 Method classification

The library sends exactly ten HTTP methods - grepped from `davclient.py`,
`async_davclient.py` and `base_client.py`, not assumed: `GET`, `OPTIONS`,
`PROPFIND`, `PROPPATCH`, `REPORT`, `PUT`, `DELETE`, `MKCOL`, `MKCALENDAR`, and
`POST`.  No `MOVE`, no `COPY` (`CalendarObjectResource.copy()` builds a new
object client-side rather than issuing an HTTP `COPY`), no `HEAD`.

One shared frozenset, defined once in `caldav/base_client.py` and used both for
`Retry(allowed_methods=...)` and for the Layer C decision:

```python
IDEMPOTENT_METHODS = frozenset({
    "GET", "HEAD", "OPTIONS", "PROPFIND", "REPORT",   # reads
    "PUT", "DELETE", "PROPPATCH", "MKCOL", "MKCALENDAR",
})
# POST is deliberately absent and must never be retried.
# HEAD is listed although the library never sends one - it costs nothing and
# keeps the set readable as "everything except POST".
```

`PUT` and `DELETE` belong in there.  This is not a compromise, it is what the
protocol says: a CalDAV `PUT` writes a complete object at a known URL and a
second identical `PUT` produces the same end state; `DELETE` on an
already-deleted URL is a 404, not a second deletion.  urllib3's own default
`allowed_methods` includes both, for the same reason.  `POST` is the only method
where a duplicate can produce a duplicate side effect, and CalDAV barely uses
it.

The DELETE objection raised in the #648 review - "a retried DELETE returns 404
and the user gets `NotFoundError` from `event.delete()`, which reads as *it was
never there*" - **does not reproduce.**  `DAVObject._post_delete()` is:

```python
if r.status not in (200, 204, 404):
    raise error.DeleteError(errmsg(r))
```

404 is already accepted, and `DAVResponse` does not raise on a 404 for a plain
DELETE (only 401/403 raise, in `_raise_authorization_error`).  So a
retried-and-404 DELETE already succeeds silently at the object layer.  A user
calling `client.delete(url)` directly gets a 404 response object, which is
correct and unambiguous.  No special handling is needed; the concern is
withdrawn.

`MKCALENDAR`/`MKCOL` are the genuinely awkward ones: if the first attempt
succeeded and its response was lost, the retry gets 405 or 409.  See open
question Q3.

### 4.2 Configuration

One new client-feature in `compatibility_hints.py`, named `retry` - not #620's
suggested `high-availability`, which promises load balancing and failover that
we do not provide, and not `retry-on-transient-error`, which is a mouthful and
misdescribes class (A):

```python
"retry": {
    "type": "client-feature",
    "description": "The client retries requests that failed for transport "
                   "reasons, and optionally requests answered with a "
                   "server-error status.  The retrying itself is done by the "
                   "HTTP library, not by the CalDAV library: these keys are "
                   "mapped onto urllib3's Retry for niquests and requests.  "
                   "The httpx fallbacks can only retry connection setup, and "
                   "ignore the rest.  429/503 are NOT covered here - they "
                   "belong to the 'rate-limit' feature.",
    "extra_keys": {
        "connect": "retries when the connection could not be established (default 2)",
        "read": "retries when the connection broke after the request was sent (default 1)",
        "status": "retries on a status in status_forcelist (default 0 - off)",
        "status_forcelist": "statuses to retry, e.g. [500, 502, 504].  Empty by default.",
        "initial_delay": "seconds to sleep before the first retry (default 0)",
        "backoff_factor": "exponential backoff multiplier (default 0.5)",
        "max_delay": "cap on the sleep between retries (default 30)",
        "jitter": "add randomness to the backoff (default true)",
    },
},
```

Defaults, chosen to satisfy #695 ("by default at least one retry whenever a
keep-alive connection has been closed") without turning fast failures into slow
ones:

* `connect=2`, `read=1`, `status=0`, `status_forcelist=[]` - **on by default**
* everything in class (C) beyond 429/503 - **opt-in**, as #620 asked
* `backoff_factor=0.5`, `max_delay=30`, `jitter=true`, `initial_delay=0`

Rationale for `read=1` being on by default: the #695 case is a *read* error in
urllib3's taxonomy (see section 2) even though nothing was delivered, so a
default of `read=0` would leave the reported bug unfixed.  One retry is enough
for a closed idle socket - the second attempt gets a fresh connection - and a
budget of one bounds the worst case at two timeouts rather than N.

`retry` also becomes a `DAVClient`/`AsyncDAVClient` keyword accepting a dict (or
`None`, or `False` to disable), plumbed through `CONNKEYS` like the other
connection parameters, so it can come from a config file or environment as well
as from the `features` config.

### 4.3 Exceptions

Add `DAVNetworkError(DAVError)` as PR #648 proposed, raised when a transport
failure survives all retries, wrapping the underlying library exception with
`raise ... from e`.  This is the only user-visible API addition, and it is
worth it: today the caller has to catch
`niquests.exceptions.ConnectionError` *or* `requests.exceptions.ConnectionError`
*or* `httpx.TransportError` depending on which library happens to be installed,
which defeats the whole point of the fallback chain.  Export it from
`caldav.lib.error` and document it in the release notes.

### 4.4 Interaction with timeouts

A retry converts a fast failure into a slow one.  With `timeout=None` and
`read=1`, a hung server produces an unbounded wait, twice.  The documentation
must state the worst case plainly: **wall-clock ≈ (retries + 1) × timeout +
accumulated backoff**, and repeat the existing advice to set an explicit
`timeout`.  Consider warning when `retry` is enabled and `timeout is None`.

### 4.5 Can the 429/503 handling be deleted?

If the HTTP library is the right home for retry logic, then the ~40 lines of
rate-limit handling in caldav - `raise_if_rate_limited()`,
`compute_sleep_seconds()`, `RateLimitError.retry_after_seconds`, the recursive
sleep-and-retry in `request()` and `_async_request()`, three constructor
arguments - are complexity we are hosting for no good reason.  `Retry` can do it:
`status_forcelist=[429, 503]`, `status=N`, `respect_retry_after_header=True`
(the default), and `sleep_for_retry()` sleeps for exactly the header value.

The direction is right.  Three things stand in the way of doing it now, and one
of them is a genuine functional loss:

1. **niquests has no `rate_limit_max_sleep` equivalent.**  Verified in the
   source: `urllib3` 2.7.0 clamps the header in `parse_retry_after()` -
   "*Check the seconds do not exceed the specified maximum*", `retry_after_max`,
   default 21600 - but **`urllib3_future` 2.15.901 has no such clamp and no such
   parameter**.  A server answering `Retry-After: 86400`, or an HTTP-date a week
   out, parks the client in `time.sleep()` for that long, with no way to bound it.
   `rate_limit_max_sleep` exists precisely to prevent that.  So the *unbounded*
   implementation is the one in our recommended library, and this is the piece
   that cannot simply be deleted.  It is also an easy upstream contribution:
   port `retry_after_max` from urllib3 2.7 to urllib3-future.  **File that first**
   - if it lands, this whole objection evaporates.
2. **It is an API break, so it belongs in 4.0.**  `rate_limit_handle`,
   `rate_limit_default_sleep` and `rate_limit_max_sleep` are documented
   constructor parameters, and `RateLimitError` is a documented exception with a
   `retry_after_seconds` attribute that callers can act on.  Delegating means
   either dropping them (breaking) or keeping them as a mapping onto `Retry`
   (which keeps most of the code we wanted to delete).  4.0 is already the
   release that reworks the HTTP-library relationship, so that is where this
   belongs.
3. **Behaviour changes in ways worth choosing deliberately.**  Today the default
   is *not* to sleep: `rate_limit_handle=None` auto-detects from the `rate-limit`
   feature, and with no such feature the client raises `RateLimitError` and lets
   the caller decide.  Under `status_forcelist` the client sleeps silently
   instead, and when the budget runs out the caller gets a niquests `RetryError`
   rather than our typed exception - so a `except RateLimitError` in downstream
   code (plann, for instance) stops firing.  Also: the httpx fallbacks lose 429
   handling completely, since httpcore has no status retries at all.

Recommended sequence, therefore: propose `retry_after_max` upstream in
urllib3-future; keep the caldav loop untouched through 3.x; and in 4.0 delete it
in favour of `status_forcelist=[429, 503]`, deprecating the three constructor
arguments in favour of the `retry` config and keeping `RateLimitError` only for
the "raise, do not sleep" default.  The `interval`/`count` half of the
`rate-limit` feature - proactive throttling, currently implemented in test code -
is unaffected by all of this, and niquests' `LeakyBucketLimiter` /
`TokenBucketLimiter` are the obvious home for it if it ever moves into the
library.

## 5. Consequences for PR #648

PR #648 is closed rather than merged.  It is not wrong about the bug - it is at
the wrong layer, and it is now `CONFLICTING` against the branch anyway:

* its `_SAFE_METHODS` frozenset is superseded by `IDEMPOTENT_METHODS` (§4.1),
  which additionally has to be handed to `Retry(allowed_methods=...)` - the PR
  cannot do that, because it never touches session construction;
* its hand-rolled retry loop for classes (A) and (B) duplicates urllib3's, with
  no backoff, no jitter, no `Retry-After`, and a one-shot `_connection_retried`
  flag instead of a budget;
* the 105-line async restructuring it needs is what the PR's own review flagged
  as the riskiest part of it, and Layer A makes it unnecessary: the async fix is
  one constructor argument;
* its `except Exception` interaction in the async auth-workaround (network
  errors reaching the auth-detection branch when `password` is set but `auth` is
  not) is a real pre-existing bug, but it is a bug about auth negotiation and
  should be fixed on its own, not inside a retry PR.

What survives from it, and should be re-submitted as a small PR: `DAVNetworkError`
(§4.3) and the Layer C lazy-gather catch (§3), which is roughly 15 lines per
client instead of 250 across four files.

## 6. Implementation plan

Ordered so that each step is independently shippable, and so that the two steps
that fix a reported bug come first.  Effort figures are for the code plus its
unit tests, and assume no surprises.

1. **`DAVNetworkError`** in `caldav/lib/error.py`, plus `IDEMPOTENT_METHODS` in
   `caldav/base_client.py`.  Unit tests only.  *Small.*
2. **Layer C**, the niquests lazy-gather catch, in both clients - roughly 15
   lines each, around the first access to response attributes.  This is what
   actually fixes https://github.com/python-caldav/caldav/issues/647.
   Unit-testable with a `Response` stub whose `status_code` property raises.
   *Small.*  Report the same thing upstream at
   https://github.com/jawah/niquests as a separate, non-blocking action.
3. **Layer A for niquests**: a `_build_retry()` helper in `base_client.py`
   mapping the `retry` config dict onto a `Retry`, and `retries=` passed to
   `Session(...)` in `DAVClient.__init__` and to `AsyncSession(...)` in
   `AsyncDAVClient._create_session()`.  Two lines of session diff plus the
   helper.  *~1 hour including tests.*  This is the step that closes
   https://github.com/python-caldav/caldav/issues/695 for the default,
   recommended configuration.
4. **Layer A for requests**: the mounted-adapter branch in the existing
   `except TypeError:` path, reusing the same `Retry` object.  *Minutes.*  Do it
   in the same change as step 3 - splitting it costs more in review than in code.
5. **The `retry` feature** in `compatibility_hints.py`, the `retry` kwarg,
   `CONNKEYS`, and config-file/env plumbing.  Until this lands, step 3 can ship
   with hardcoded defaults.  *Small.*
6. **Docs**: the guarantees-per-library table from §2 into
   `docs/source/http-libraries.rst`, the timeout warning from §4.4, and a
   CHANGELOG entry.
7. **Layer A for the httpx family** - deferred, not scheduled.  Needs the
   transport refactor described in §3.1 (moving `verify`/`cert`/`http2` into the
   transport constructor) and buys connect-retries only.  Do it when someone
   asks, or when `_create_session()` is being touched anyway for another reason.

Steps 1-2 are the bug fix and are worth doing on their own.  Steps 3-5 are the
feature.  Step 7 is optional and step 6 is not.

## 7. Testing

* Unit tests, per layer, with no server: a session stub that raises
  `ProtocolError` on the first call and succeeds on the second; a `Response`
  stub whose `status_code` raises (Layer C); assertions that POST is *not*
  retried and that `PROPFIND`/`REPORT` *are* in `allowed_methods` on the
  constructed `Retry` object.
* Assertions on the constructed `Retry`/transport rather than on network
  behaviour, so the tests run identically under all five libraries and in CI
  where only some are installed.
* No mocking in the integration tests.  If a server-side scenario cannot be
  provoked, skip.
* The `retries` attribute on the urllib3 response (`Retry` with a `.history` of
  `RequestHistory(method, url, error, status, redirect_location)`, present in
  both urllib3 and urllib3-future) lets an integration test assert *that* a
  retry happened, without mocking.  Useful for a `tests-behaviour` check if we
  ever want one.
* A regression test for #647 is not possible without a server that reproduces
  stale HTTP/2 gathering; the unit test on the stub is the substitute.

## 8. Open questions

* **Q1.** Should `read` retries default to 1 (as proposed) or 0?  1 fixes #695
  out of the box but means a hung server is waited on twice.  Decision needed
  before implementation, since it is the one default that can surprise people.
* **Q2.** For the httpx family, classes (B) and (C) are unreachable at Layer A.
  Proposal (§3.1): accept the degradation, document it in the §2 table and in
  `http-libraries.rst`, warn if a `retry` config is given to an httpx-backed
  client, and do not schedule httpx support.  niquests is the recommended
  library; httpx is a fallback for people with a specific objection, and they can
  live with a specific limitation.
* **Q3.** `MKCALENDAR`/`MKCOL` retried after a lost response gives 405/409.
  Tolerate it as "the calendar exists, fine" the way `_post_delete` tolerates
  404, or drop them from `IDEMPOTENT_METHODS`?
* **Q4.** #620's original phrasing put the whole thing in the *server*
  configuration.  Retry policy is a property of the client's environment (a
  flaky VPN is not a server peculiarity), which is why §4.2 makes it a
  `client-feature` *and* a constructor argument.  Confirm that is the intent.
* **Q5.** Should the niquests-only `keepalive_idle_window` / `keepalive_delay`
  be exposed?  They prevent class (A) failures rather than retrying them, but
  only over HTTP/2+, which we mostly do not use (multiplexing is off by
  default).  Probably not worth a knob.
* **Q6.** §4.5: delete the caldav-side 429/503 handling in 4.0 and let
  `status_forcelist` do it?  Blocked on `retry_after_max` reaching
  urllib3-future, since without a cap on `Retry-After` the delegation is a
  regression, not a simplification.  Sub-question: is filing that upstream
  something we want to spend the effort on?

## 9. Rejected alternatives

* **Hand-roll everything in `caldav`** (what #648 does).  Rejected: reimplements
  urllib3's `Retry` badly, and cannot see the failures that happen inside the
  connection pool.
* **Take a dependency on `httpx-retries`.**  Rejected: another HTTP-adjacent
  dependency, in a project that is actively trying to shed its HTTP dependency
  by v4.0.
* **`Retry(total=N)` and nothing else.**  Rejected: urllib3's default
  `allowed_methods` excludes `PROPFIND` and `REPORT`, so the headline bug would
  stay unfixed.  See §2.
* **Retry 429/503 at Layer A via `status_forcelist`, *in addition to* the
  existing handling.**  Rejected: two mechanisms racing over the same responses.
  Replacing the existing handling with it is a different proposal, and a good
  one - see §4.5 and Q6.
* **Reimplement status retries in caldav for cross-library parity.**  Proposed in
  an earlier draft of this document, rejected: it adds a caldav-side retry loop
  for something urllib3 already does, to benefit a fallback library that most
  users do not have installed.  The §2 table plus a warning is the cheaper
  answer to the parity problem.
* **Retry everything, POST included, on class (A).**  Tempting, since nothing
  was delivered.  Rejected for now: urllib3 counts the #695-style
  connection-closed case as a *read* error, so "class (A) only" is not a
  distinction we can reliably make at the transport layer, and getting it wrong
  means a duplicated scheduling POST.
