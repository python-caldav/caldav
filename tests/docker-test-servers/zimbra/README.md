# Zimbra CalDAV Test Server

Zimbra Collaboration Suite running in Docker for the caldav library test suite.

## Overview

- **Image**: `zimbra/zcs-foss:latest` (Zimbra 8.8.3 pre-installed)
- **Port**: 8808 (mapped to container's 443/HTTPS)
- **Users**: testuser@zimbra.io / testpass, testuser2@zimbra.io / testpass
- **Protocol**: HTTPS with self-signed certificate (`ssl_verify_cert=False`)

## Resource Requirements

Zimbra is heavyweight compared to other test servers:

- **RAM**: ~6GB minimum
- **Disk**: ~3GB for image
- **First startup**: ~5-10 minutes (Zimbra configuration via zmsetup.pl)
- **Subsequent startups**: ~2-3 minutes (services restart only)

The container runs in **privileged mode** (required for dnsmasq and service
management). This server is treated as "on-demand" and is not started
automatically.

## Quick Start

```bash
./start.sh
```

The start script will:
1. Add `zimbra-docker.zimbra.io` to `/etc/hosts` (requires sudo)
2. Start the container
3. Wait for Zimbra setup to complete
4. Create test users via `zmprov`
5. Verify CalDAV endpoint accessibility

## Stop

```bash
./stop.sh
```

## Running Tests

```bash
cd ../../..
TEST_ZIMBRA=true pytest tests/test_caldav.py -k Zimbra -v
```

## Notes

- The container hostname must be `zimbra-docker.zimbra.io` — Zimbra's nginx
  proxy rejects requests with non-matching Host headers.
- A `/etc/hosts` entry mapping `zimbra-docker.zimbra.io` to `127.0.0.1` is
  required. The start script adds this automatically.
- The container uses HTTPS with a self-signed certificate. The test server
  class sets `ssl_verify_cert=False` to handle this.
- Usernames are in email format: `testuser@zimbra.io`
