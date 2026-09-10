# Bedework 5 CalDAV Test Server

[Bedework](https://bedework.github.io/bedework/) is an enterprise calendar
system running on Wildfly.  This directory builds an image for the current
release; `../bedework3/` runs the 2018 3.10.3 image that used to be the only
one we had.

## Why we build it ourselves

There is no public Bedework image newer than `ioggstream/bedework` (2018), and
there is no single repository to build from either: upstream is spread over
~20 git repos assembled into a Wildfly *galleon feature pack*.  What upstream
tells deployers to install is that feature pack, so that is what the Dockerfile
does — `org.bedework.deploy:bw-wf-feature-pack`, layers `bw-demoall-h2` and
`web-console`, on JDK 21.  See
<https://bedework.github.io/bedework/#featurepack-install>.

Galleon resolves ~950 artifacts from Maven Central; the build takes ~15 minutes
and the finished image is around 1.1 GB.

## Build

```bash
./build.sh
```

To try another release or a smaller install:

```bash
./build.sh --build-arg BW_VERSION=5.1.0 --build-arg BW_LAYERS=bw-democaluser-h2,web-console
```

## Start

```bash
./start.sh
```

- CalDAV: `http://localhost:8811/ucaldav/user/vbede/`
- User: `vbede` / `bedework` (all demo accounts share that password)
- Web client: `http://localhost:8811/cal/`, Wildfly console: port 9990

The container runs four processes — apacheds (LDAP), h2, opensearch and
wildfly — and `run.sh` starts them in that order.

## Stop

```bash
./stop.sh
```

## Run tests

```bash
cd ../../..
pytest tests/test_caldav.py -k Bedework -v
```

Note that `-k Bedework` also matches the 3.10.3 server class; use
`-k "Bedework and not Bedework3"` to run only against this one.

## Three upstream bugs are patched at build time

Feature pack 5.0.0 does not come up on its own.  Each fix is a separate script
with the details in its header:

- **`migrate-h2.sh`** — the pre-seeded demo databases are H2 1.4.x files
  (`format:1`) but the installed driver is H2 2.2.224, which refuses to open
  them.  Each database is dumped with a contemporary H2 and reloaded with the
  new one.
- **`patch-modules.sh`** — the shared calendar service loads a dumprestore
  class through the thread context classloader, and the module behind `/cal`
  does not have it.  Because the failure happens in a static initialiser in a
  *shared* module, whichever request arrives first decides whether the whole
  server works; the fix adds the missing module dependency.
- **`apacheds-setenv.sh`** — the bundled ApacheDS cannot run on JDK 21 (it
  builds a self-signed certificate via `sun.security.x509`, which needs
  `--add-exports` plus a method JDK 18 removed).  It gets a JRE 17 carried in
  the image; without this every authenticated request returns 500.

`docker-compose.yml` also keeps the opensearch data directory on a named
volume: on the container's overlay filesystem OpenSearch dies at startup with
`AlreadyClosedException: Underlying file changed by an external force`.

## Compatibility profile

`caldav/compatibility_hints.py` has `bedework_5_0_0`, measured 2026-09-12 with
caldav-server-tester against this image as user `vbede`.  Nothing is inherited
from `bedework_3_10_3` — that is a different server.

Two things are worth knowing before reading a measurement against it:

- **Writes are asynchronous.**  A read-back issued immediately after a PUT may
  404 or hand back the pre-write copy, which made `save-load.mutable`,
  `save-load.event.timezone` and `search.time-range.comp-type-optional` come
  out differently in two consecutive runs.  The profile carries
  `write-delay: 3s`; without it a run measures the race rather than the server.
- **A client cannot create a collection that holds tasks.**  MKCALENDAR and
  extended MKCOL both answer `200 ok` for
  `CALDAV:supported-calendar-component-set` and then ignore it, and a
  PROPPATCH of the property afterwards is 403, so every collection a client
  creates is VEVENT-only and a VTODO PUT into it is 403.
  `vbede` has no usable `tasks` collection either: the Depth:1 PROPFIND of the
  calendar home lists `tasks`, `Notifications` and `.pendingInbox` with a
  `getlastmodified` of "now" that is renewed on every listing, and all three
  404 on any direct request.  `douglm`, whose demo data ships a real one, can
  store tasks in it.  So the profile grades task and journal storage `unknown`
  rather than unsupported: the tester had nowhere to put one.  The analysis is
  in https://github.com/Bedework/bedework/issues/5#issuecomment-5652203366
