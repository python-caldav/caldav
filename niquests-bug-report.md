# Bug report: HTTP/2 lazy-gather timeout ignores per-request timeout setting

Claude made a wall of text below, sorry for that.

UPDATE: Claude has made some code reproducing the issue, and has also updated the text below.

⚠️ This bug report is AI-generated (Claude Sonnet 4.6 via Claude Code) on behalf of tobixen ⚠️

## Summary

When niquests uses HTTP/2 and a connection goes stale between requests (server
closes the idle connection within the 60 s PING window), the next request
blocks until the OS TCP retransmission timeout fires (~1-2 minutes).

A configured per-request `timeout=` **is** respected — the error then
surfaces within `timeout` seconds.  The problem is that `timeout=None` (no
application-level timeout) causes niquests to call `sock.settimeout(None)`,
leaving the socket in blocking mode.  The OS TCP timeout then fires after
~1-2 minutes, well past any reasonable user expectation.

This specifically affects callers who rely on the default `timeout=None`,
including caldav's `DAVClient` which defaults to no timeout.

This was discovered while investigating https://github.com/python-caldav/caldav/issues/647

## Environment

- niquests (version reported by the user): current release on NixOS 26.05
- urllib3-future: current release packaged with above
- Python 3.13
- Server: CalDAV server (exact implementation unknown, supports HTTP/2)

## Steps to reproduce

A self-contained reproducer is available at
[`reproduce_647/`](https://github.com/python-caldav/caldav/tree/issue647/reproduce_647)
in the python-caldav repository (requires `pip install niquests h2 cryptography`).

The critical scenario (half-open TCP connection, `timeout=None`):

```
# terminal 1
python reproduce_647/server.py --half-open

# terminal 2 — no timeout configured, mirrors caldav default
python reproduce_647/client.py --n 2
# request 1 OK (0.03 s)
# request 2 … hangs for ~1-2 minutes then raises ConnectionError
```

With a configured timeout the error surfaces in ~`timeout` seconds:

```
python reproduce_647/client.py --timeout 5 --n 2
# request 1 OK (0.03 s)
# request 2 Timeout after 5.01s  ← timeout IS respected when configured
```

Original reproduction (caldav + real server):

```python
import caldav

with caldav.DAVClient(url="https://example.com/dav", username="u", password="p") as client:
    principal = client.principal()          # request 1 — connection established
    calendars = principal.calendars()       # request 2 — connection reused
    # Server closes the idle HTTP/2 connection here (within 60 s PING window).
    for event in calendars[0].events():     # request 3 — stale connection
        print(event)
```

Freezes for 1-2 minutes then raises:

```
urllib3_future.exceptions.ReadTimeoutError: None: Read timed out.
...
niquests.exceptions.ConnectionError: None: Read timed out.
```

Full traceback from the original report:

```
  File ".../urllib3_future/backend/hface.py", line 1544, in __read_st
    events = self.__exchange_until(DataReceived, ...)
  File ".../urllib3_future/backend/hface.py", line 945, in __exchange_until
    data_in = sync_recv_gro(self.sock, self.blocksize)
  File ".../urllib3_future/contrib/ssa/_gro.py", line 88, in sync_recv_gro
    data, ancdata, _flags, addr = sock.recvmsg(bufsize, ancbufsize)
TimeoutError: timed out
...
  File ".../niquests/models.py", line 1436, in content
    self._content = self.raw.read(decode_content=True)
...
  File ".../niquests/adapters.py", line 1148, in _future_handler
    response.content
  File ".../niquests/adapters.py", line 1315, in gather
    next_resp = self._future_handler(response, low_resp)
  File ".../niquests/models.py", line 1035, in _gather
    super().__getattribute__("connection").gather(self)
  File ".../niquests/models.py", line 1049, in __getattribute__
    super().__getattribute__("_gather")()
  File ".../caldav/davclient.py", line 1034, in request
    log.debug("server responded with %i %s" % (r.status_code, r.reason))
                                               ^^^^^^^^^^^^^
niquests.exceptions.ConnectionError: None: Read timed out.
```

## Root cause analysis

### Timeout IS propagated correctly (verified in niquests 3.17.0)

Testing against a local HTTP/2 server confirms that when `timeout=` is
configured, the value is correctly honoured — both in non-multiplexed and
multiplexed (`_gather()`) paths.  `connection.py` calls
`sock.settimeout(self.timeout)` at the start of both `request()` and
`getresponse()`, so `conn.timeout = read_timeout` (set in `urlopen`) reaches
the socket before any blocking read.

### The actual bug: `timeout=None` + 60 s PING window

The multi-minute freeze occurs when **no application-level timeout is
configured** (`timeout=None`) *and* the connection goes stale within the
default PING idle window.

- `DEFAULT_KEEPALIVE_IDLE_WINDOW = 60.0 s` — a PING is only sent after 60 s
  of idle.  Requests made within 60 s of each other are not protected.
- When `timeout=None`, `sock.settimeout(None)` is set, meaning the socket
  blocks indefinitely.  The OS TCP retransmission timeout then fires after
  ~1-2 minutes.
- caldav's `DAVClient` defaults to `timeout=None`, so any user who doesn't
  explicitly pass a timeout hits this.

### PING detection gap

The PING-based keep-alive does detect dead connections, but only *after*
`keepalive_idle_window` seconds (default 60 s) of idle.  If a server closes
its HTTP/2 connection after, say, 30 s of idle (common), a client that makes
two rapid requests will reuse the stale connection without any PING having been
sent.  The second request then blocks on a dead connection.

Lowering `keepalive_idle_window` helps (confirmed in testing) but is not
exposed as a user-facing tuning parameter in the higher-level niquests API.

## Expected behaviour

When a request is made on a stale HTTP/2 connection and `timeout=None` is in
effect, the error should still surface within a reasonable time — either by:

1. A proactive PING before reusing a pooled connection that has been idle for
   any significant period (not only after `keepalive_idle_window`), or
2. Documentation / API that encourages callers to set a timeout, or warns that
   `timeout=None` can block for OS-level durations on stale HTTP/2 connections.

## Suggested investigation

1. Consider sending a PING before reusing any HTTP/2 connection that has been
   idle since the last request, rather than only on a fixed timer.
2. Document that `timeout=None` disables the application-level timeout
   entirely and can result in multi-minute hangs on stale HTTP/2 connections.
3. Consider a separate `pool_timeout` or "max connection age" parameter that
   caps how long a pooled HTTP/2 connection can be reused, independent of the
   per-request read timeout.

## Related existing issues

- **niquests #183** (closed, fixed in urllib3-future): timeout not respected in
  async scenarios — different root cause (DNS resolution over VPN).
- **urllib3.future #281** (closed): keepalive idle_timeout feature request.
  The maintainer's response says HTTP/2 connections are protected against
  staleness via automatic PING frames.  The issue we are reporting suggests
  PING-based protection is not always sufficient (or the PING cycle is slower
  than the server's idle-close window), since HTTP/2 connections do go stale
  in practice.
- **urllib3.future #323** (open): one broken connection causes two request
  errors (connection pool / threading).  Different scenario but shares the same
  lazy-`__getattribute__` code path in the traceback.

## Workaround applied in python-caldav

python-caldav wraps all response-attribute access in a `try/except
(ConnectionError, Timeout)` and retries once for idempotent methods.  This
recovers transparently, but the user still waits for the full OS-level socket
timeout before the retry fires.

⚠️ This bug report is AI-generated (Claude Sonnet 4.6 via Claude Code) on behalf of tobixen ⚠️
