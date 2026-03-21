# Reproducer for HTTP/2 stale-connection / timeout issue (caldav #647)

## Requirements

```
pip install niquests h2 cryptography
```

A self-signed TLS certificate (`cert.pem` / `key.pem`) is generated automatically
on first run of `server.py`.

## Server modes

| Flag | What happens |
|------|--------------|
| *(none)* | Respond to first request, close TCP **without GOAWAY** |
| `--slow` | Never send any HTTP response |
| `--half-open` | Respond to first request, keep TCP open, ignore further HTTP/2 frames |

## Test results (niquests 3.17.0)

### A – clean TCP close (server closes connection after first response)

```
$ python server.py &
$ python client.py --timeout 5 --n 2
request 1 OK:           elapsed=0.03s
request 2 ConnectionError after 0.00s: Remote end closed connection without response
```

niquests detects the TCP FIN/RST immediately. ✓

---

### B – slow server (never responds), timeout=5

```
$ python server.py --slow &
$ python client.py --timeout 5 --n 1
request 1 Timeout after 5.03s
```

Configured timeout is respected. ✓

Same with `--multiplexed` (exercises the lazy `_gather()` path):

```
$ python client.py --timeout 5 --multiplexed --n 1
request 1 ConnectionError after 5.03s
```

Configured timeout is still respected. ✓

---

### C – half-open (TCP alive, server ignores HTTP/2 frames after first response)

#### Without a configured timeout (`timeout=None`)

```
$ python server.py --half-open &
$ python client.py --n 2          # no --timeout
request 1 OK:           elapsed=0.03s
request 2  … hangs …              # waits for OS-level TCP timeout (~minutes)
```

**This is the bug scenario.** caldav's `DAVClient` defaults to `timeout=None`;
a stale HTTP/2 connection causes a multi-minute freeze.

#### With a configured timeout

```
$ python client.py --timeout 5 --n 2
request 1 OK:           elapsed=0.03s
request 2 Timeout after 5.01s
```

With a timeout the error surfaces quickly. ✓

---

### C – half-open with keepalive PING detection

The default `keepalive_idle_window` is **60 seconds** — a PING is only sent
after the connection has been idle for 60 s.  Rapid requests are therefore
**not** protected by PINGs.

Forcing a short window shows that PING detection does work when given enough
idle time:

```
$ python server.py --half-open &
$ python client.py --timeout 10 --wait 3 --keepalive-idle-window 2 --n 2
request 1 OK:           elapsed=0.03s
sleeping 3.0s …
request 2 ConnectionError after 5.01s
```

Here niquests sends a PING after 2 s of idle; the server's h2 state machine
replies with PING_ACK (the connection looks alive), the next request is sent,
and the error comes from the server eventually closing the connection due to
its own idle timer.

---

## Root cause summary

1. caldav passes `timeout=None` to niquests by default → no application-level
   timeout on socket reads.
2. HTTP/2 connections can go stale (server closes them) within the default
   60 s PING window.
3. When niquests reuses a stale connection and the server no longer responds,
   the socket blocks until the OS TCP timeout fires (~1-2 minutes).
4. The error surfaces lazily — when accessing `r.status_code` or `r.headers`
   — because niquests defers response completion for HTTP/2 connections.

**Fix in caldav:** catch `ConnectionError`/`Timeout` and retry once for
idempotent methods (PR on branch `issue647`).

**Recommended user-side mitigation:** always pass a reasonable `timeout=` to
`DAVClient`, e.g. `DAVClient(url=..., timeout=30)`.
