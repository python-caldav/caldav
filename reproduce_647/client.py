#!/usr/bin/env python3
"""
Client script for reproducing the stale HTTP/2 connection issue.

Run the server first:
    python server.py          # scenario A: stale connection
    python server.py --slow   # scenario B: never respond

Then run this client:
    python client.py [--timeout SECONDS] [--multiplexed] [--wait SECONDS]

Scenario A (stale connection):
    With --wait 0 (default): server closes connection right after the first
    response.  The client then makes a second request.  Expected outcomes:
      - Ideal:   niquests reconnects transparently → both requests succeed.
      - Buggy:   second request hangs until timeout (or OS socket timeout if
                 no timeout is configured), then raises ConnectionError.

Scenario B (slow server, --slow on server side):
    Use --timeout 5.  The server never responds.  Expected outcomes:
      - Correct: raises after ~5 seconds.
      - Buggy:   hangs for OS socket timeout (~120 s) regardless of --timeout.
    Add --multiplexed to explicitly exercise the lazy _gather() code path.
"""

import argparse
import time
from pathlib import Path

import niquests

CERT_FILE = Path(__file__).parent / "cert.pem"
URL = "https://127.0.0.1:8444/"


def run(timeout, multiplexed, wait, n_requests, args_keepalive_idle_window=None):
    print(f"[client] niquests {niquests.__version__}")
    print(f"[client] timeout={timeout!r}  multiplexed={multiplexed}  "
          f"wait={wait}s  n_requests={n_requests}")
    print()

    # Use cert.pem as the CA bundle so we trust our self-signed cert.
    verify = str(CERT_FILE) if CERT_FILE.exists() else False

    # keepalive_idle_window: how long to wait before sending a PING on an idle
    # HTTP/2 connection.  Default is 60s; use a short value to test whether
    # PINGs catch stale connections before the next request.
    session_kwargs = {"multiplexed": multiplexed}
    if args_keepalive_idle_window is not None:
        session_kwargs["keepalive_idle_window"] = args_keepalive_idle_window

    with niquests.Session(**session_kwargs) as session:
        for i in range(1, n_requests + 1):
            if i > 1 and wait > 0:
                print(f"[client] sleeping {wait}s before request {i} …")
                time.sleep(wait)

            print(f"[client] sending request {i} …")
            t0 = time.monotonic()
            try:
                r = session.get(
                    URL,
                    timeout=timeout,
                    verify=verify,
                )
                # For multiplexed=True responses, accessing status_code
                # triggers _gather() — this is where the lazy timeout issue
                # would surface.
                elapsed = time.monotonic() - t0
                print(
                    f"[client] request {i} OK: "
                    f"status={r.status_code}  elapsed={elapsed:.2f}s"
                )
            except niquests.exceptions.ConnectionError as exc:
                elapsed = time.monotonic() - t0
                print(
                    f"[client] request {i} ConnectionError "
                    f"after {elapsed:.2f}s: {exc}"
                )
            except niquests.exceptions.Timeout as exc:
                elapsed = time.monotonic() - t0
                print(
                    f"[client] request {i} Timeout "
                    f"after {elapsed:.2f}s: {exc}"
                )
            except Exception as exc:
                elapsed = time.monotonic() - t0
                print(
                    f"[client] request {i} {type(exc).__name__} "
                    f"after {elapsed:.2f}s: {exc}"
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--timeout", type=float, default=None,
        help="Per-request timeout in seconds (default: None = no timeout)",
    )
    parser.add_argument(
        "--multiplexed", action="store_true",
        help="Use niquests multiplexed mode (exercises lazy _gather() path)",
    )
    parser.add_argument(
        "--wait", type=float, default=0,
        help="Seconds to sleep between requests (default: 0)",
    )
    parser.add_argument(
        "--n", type=int, default=3,
        dest="n_requests",
        help="Number of requests to send (default: 3)",
    )
    parser.add_argument(
        "--keepalive-idle-window", type=float, default=None,
        dest="keepalive_idle_window",
        help="Seconds before PING is sent on idle HTTP/2 connection (default: 60)",
    )
    args = parser.parse_args()
    run(args.timeout, args.multiplexed, args.wait, args.n_requests,
        args.keepalive_idle_window)
