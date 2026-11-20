# Stalwart Test Server

[Stalwart](https://stalw.art/) is a mail and collaboration server with CalDAV
and CardDAV support.  This configuration runs the `stalwartlabs/stalwart`
image and sets it up over JMAP.

## Quick Start

```bash
cd tests/docker-test-servers/stalwart
./start.sh
```

## Configuration

- **URL**: http://localhost:8809/dav/cal/testuser%40example.org/
- **Admin**: admin / adminpass (web UI: http://localhost:8809/admin/)
- **Test user**: testuser@example.org / testcaldav
- **Scheduling users**: user1, user2, user3 @example.org / caldavtest1..3

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STALWART_HOST` | localhost | Host the client and setup script talk to |
| `STALWART_PORT` | 8809 | Port the client and setup script talk to (`docker-compose.yml` maps 8809 itself) |
| `STALWART_USERNAME` | testuser | Test user, a local part or a full `@example.org` address |
| `STALWART_PASSWORD` | testcaldav | Test password |
| `STALWART_MAX_RESULTS` | 50 | `WebDav.maxResults` |

## Result limit

Stalwart caps PROPFIND, sync-collection, calendar-query and
calendar-multiget answers at
`WebDav.maxResults` members, with a 507 for the collection.  The default
is 2000; this container lowers it to 50, so caldav-server-tester can see
the limit with few objects (`CALDAV_SERVER_TESTER_LIMIT_OBJECTS`).  A test
putting more than 50 objects in one calendar will hit it: raise
`STALWART_MAX_RESULTS` for that.
