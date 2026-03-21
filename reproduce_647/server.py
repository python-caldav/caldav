#!/usr/bin/env python3
"""
Minimal HTTP/2 server for reproducing stale-connection behaviour.

Scenario A (default): respond to request 1, then close the TCP connection
    *without* sending a GOAWAY frame.  This simulates a server that abruptly
    drops idle connections.  A well-behaved client should either
      (a) detect the closure via keepalive PINGs before the next request, or
      (b) reconnect transparently on the next request.
    A misbehaving client will hang until the OS socket timeout fires.

Scenario B (--slow): accept the connection and request headers, but never
    send a response.  Used to verify that the per-request timeout= value is
    honoured even when the error surfaces during lazy _gather().

Scenario C (--half-open): respond to request 1, then keep the TCP connection
    open but silently ignore all further HTTP/2 frames.  This simulates a
    "half-open" or NAT-timeout scenario where packets are not dropped at TCP
    level but the application layer stops responding.

Usage:
    python server.py              # scenario A (stale connection, clean close)
    python server.py --slow       # scenario B (never respond)
    python server.py --half-open  # scenario C (half-open / silent drop)

The server generates a self-signed cert on first run (cert.pem / key.pem).
"""

import argparse
import asyncio
import datetime
import ipaddress
import ssl
import sys
from pathlib import Path

import h2.config
import h2.connection
import h2.events

CERT_FILE = Path(__file__).parent / "cert.pem"
KEY_FILE = Path(__file__).parent / "key.pem"
HOST = "127.0.0.1"
PORT = 8444


# ---------------------------------------------------------------------------
# Self-signed certificate helper
# ---------------------------------------------------------------------------

def _generate_cert() -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=365)
        )
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    CERT_FILE.write_bytes(
        cert.public_bytes(serialization.Encoding.PEM)
    )
    KEY_FILE.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    print(f"[server] generated self-signed cert → {CERT_FILE}")


def _ssl_context() -> ssl.SSLContext:
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        _generate_cert()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(CERT_FILE), str(KEY_FILE))
    ctx.set_alpn_protocols(["h2"])
    return ctx


# ---------------------------------------------------------------------------
# Per-connection HTTP/2 handler
# ---------------------------------------------------------------------------

async def handle_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    slow: bool,
    half_open: bool = False,
) -> None:
    peer = writer.get_extra_info("peername")
    print(f"[server] connection from {peer}")

    config = h2.config.H2Configuration(
        client_side=False,
        header_encoding="utf-8",
    )
    conn = h2.connection.H2Connection(config=config)
    conn.initiate_connection()
    writer.write(conn.data_to_send(65535))
    await writer.drain()

    requests_handled = 0

    try:
        while True:
            try:
                data = await asyncio.wait_for(reader.read(65535), timeout=5.0)
            except asyncio.TimeoutError:
                print("[server] idle timeout, closing")
                break

            if not data:
                print("[server] client closed connection")
                break

            events = conn.receive_data(data)

            for event in events:
                if isinstance(event, h2.events.RequestReceived):
                    stream_id = event.stream_id
                    path = next(
                        (v for k, v in event.headers if k == ":path"), "?"
                    )
                    method = next(
                        (v for k, v in event.headers if k == ":method"), "?"
                    )
                    print(
                        f"[server] request #{requests_handled + 1}: "
                        f"{method} {path} (stream {stream_id})"
                    )

                    if slow:
                        # Scenario B: never respond — just print and ignore.
                        print("[server] (slow mode) not responding to request")
                    elif half_open and requests_handled >= 1:
                        # Scenario C: silently ignore subsequent requests
                        # over the still-open TCP connection.
                        print(
                            "[server] (half-open mode) ignoring request "
                            f"#{requests_handled + 1} — TCP alive, no response"
                        )
                    else:
                        # Scenario A: respond, then close (or keep open for C).
                        requests_handled += 1
                        _send_response(conn, stream_id)
                        writer.write(conn.data_to_send(65535))
                        await writer.drain()
                        if not half_open:
                            print(
                                "[server] closing connection without GOAWAY "
                                "after first response"
                            )
                            writer.close()
                            return
                        else:
                            print(
                                "[server] (half-open mode) responded to "
                                "request 1; keeping TCP alive, ignoring future requests"
                            )

                elif isinstance(event, h2.events.DataReceived):
                    conn.acknowledge_received_data(
                        event.flow_controlled_length, event.stream_id
                    )

                elif isinstance(event, h2.events.PingReceived):
                    print(f"[server] PING received, sending PONG")

                elif isinstance(event, h2.events.WindowUpdated):
                    pass

                elif isinstance(event, h2.events.ConnectionTerminated):
                    print("[server] GOAWAY received from client")
                    return

            pending = conn.data_to_send(65535)
            if pending:
                writer.write(pending)
                await writer.drain()

    finally:
        try:
            writer.close()
        except Exception:
            pass


def _send_response(conn: h2.connection.H2Connection, stream_id: int) -> None:
    conn.send_headers(
        stream_id,
        [
            (":status", "200"),
            ("content-type", "text/plain"),
            ("content-length", "2"),
        ],
    )
    conn.send_data(stream_id, b"ok", end_stream=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(slow: bool, half_open: bool) -> None:
    ssl_ctx = _ssl_context()

    def factory(r, w):
        return handle_connection(r, w, slow=slow, half_open=half_open)

    server = await asyncio.start_server(factory, HOST, PORT, ssl=ssl_ctx)
    if slow:
        mode = "slow (never respond)"
    elif half_open:
        mode = "half-open (respond once, then ignore HTTP/2 frames over live TCP)"
    else:
        mode = "stale-connection (close after first response)"
    print(f"[server] listening on https://{HOST}:{PORT}  mode={mode}")
    print("[server] press Ctrl-C to stop")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--slow", action="store_true",
        help="Scenario B: accept connections but never send responses",
    )
    parser.add_argument(
        "--half-open", action="store_true", dest="half_open",
        help="Scenario C: respond once, then keep TCP open but ignore HTTP/2",
    )
    args = parser.parse_args()
    try:
        asyncio.run(main(args.slow, args.half_open))
    except KeyboardInterrupt:
        print("\n[server] stopped")
