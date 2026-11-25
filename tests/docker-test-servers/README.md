# Docker Test Servers

This directory contains Docker-based test server configurations for running
integration tests against various CalDAV server implementations.

## Available Test Servers

Each directory has its own `README.md`.  Ports are on localhost; Zimbra is
reached as `https://zimbra-docker.zimbra.io:8808`, which needs an
`/etc/hosts` entry (see `zimbra/README.md`):

| Server | Directory | Port |
|---|---|---|
| Baikal | `baikal/` | 8800 |
| Nextcloud | `nextcloud/` | 8801 |
| Cyrus | `cyrus/` | 8802 |
| SOGo | `sogo/` | 8803 |
| Bedework 3 | `bedework3/` | 8804 |
| DAViCal | `davical/` | 8805 |
| Davis | `davis/` | 8806 |
| CCS (Apple Calendar Server) | `ccs/` | 8807 |
| Zimbra | `zimbra/` | 8808 |
| Stalwart | `stalwart/` | 8809 |
| OX App Suite | `ox/` | 8810 |
| Bedework 5 | `bedework/` | 8811 |

Only Baikal, Nextcloud, Cyrus, SOGo and Bedework 3 run in CI, as service
containers in `.github/workflows/tests.yaml`.  OX and Bedework 5 need a
local image build, and Zimbra needs about 6 GB RAM and privileged mode, and
minutes to start.

Docker servers need no entry in `tests/caldav_test_servers.yaml`: every
directory here that has a `start.sh` and a registered server class is
discovered and enabled automatically, provided `docker-compose` is
installed or the server is already running.  An entry is only needed to
switch one off, or to change its port or credentials;
`PYTHON_CALDAV_TEST_DOCKER=0` switches them all off.

## Adding New Test Servers

To add a new CalDAV server for testing:

1. Create `tests/docker-test-servers/<name>/` with `docker-compose.yml`,
   `start.sh`, `stop.sh` and a `README.md`; take the next free port.
2. Add a server class in `caldav/testing/docker.py` and register it with
   `register_server_class()`.
3. Add a hints dict for the server in `caldav/compatibility_hints.py`.
4. Add an entry in `tests/caldav_test_servers.yaml.example`.
5. Update `.github/workflows/tests.yaml` if it should run in CI.

## General Usage

### Local Testing

1. Navigate to the specific server directory
2. Start the container: `docker-compose up -d`
3. Configure the server (see server-specific README)
4. Run tests from project root with appropriate environment variables

### CI/CD Testing

Test servers are automatically started as GitHub Actions services. See
`.github/workflows/tests.yaml` for configuration.

## Environment Variables

Each server may use different environment variables. Common ones include:

- `<SERVER>_URL`: URL of the test server
- `<SERVER>_USERNAME`: Test user username
- `<SERVER>_PASSWORD`: Test user password

See individual server READMEs for specific variables.
