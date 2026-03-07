# OX App Suite CalDAV Test Server

[OX App Suite](https://www.open-xchange.com/) is a commercial groupware platform with CalDAV/CardDAV support.

## Prerequisites

Unlike the other test servers, OX requires building a Docker image locally — there is no usable pre-built public image. Building downloads ~1.5 GB of packages and takes several minutes.

## Build

```bash
./build.sh
```

This builds the `ox-caldav-test` image using the Dockerfile in this directory. The image is based on `debian:bookworm` with:

- Temurin 8 JDK (OX 7.10.x requires Java 8; Java 11+ is not supported)
- OX App Suite 7.10.x packages from the official OX APT repo
- MariaDB (embedded, for the config and groupware databases)
- Apache 2 (reverse proxy from port 80 to OX Grizzly on port 8009)

## Start

```bash
./start.sh
```

Checks that the image has been built, starts the container, and waits for OX to finish
initialising (~3 minutes). OX sets up its own databases on every start (tmpfs volumes
are used so the container always starts clean).

- CalDAV: `http://localhost:8810/caldav/`
- User: `oxadmin` / `oxadmin`

## Stop

```bash
./stop.sh
```

## Run tests

```bash
cd ../../..
TEST_OX=true pytest tests/test_caldav.py -k OX -v
```

## Notes

- **Build is manual**: `start.sh` will refuse to run if the image has not been built.
- **Startup time**: ~3 minutes on first run due to database initialisation.
- **Port**: 8810 (HTTP).
- The CalDAV servlet is at `/caldav/` (Apache rewrites to `/servlet/dav/caldav` on the backend).
- CardDAV is also available at `/carddav/`.
