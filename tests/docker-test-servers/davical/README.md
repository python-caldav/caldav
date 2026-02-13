# DAViCal Test Server

[DAViCal](https://www.davical.org/) is a CalDAV server that uses PostgreSQL as its backend. This Docker configuration provides a complete DAViCal server for testing.

## Quick Start

```bash
cd tests/docker-test-servers/davical
./start.sh
```

This will:
1. Start PostgreSQL and DAViCal containers
2. Wait for database initialization (~60s)
3. Create a test user with CalDAV access
4. Verify connectivity

## Configuration

- **URL**: http://localhost:8805/caldav.php/
- **Admin**: admin / testpass
- **Test User**: testuser / testpass

## CalDAV Endpoints

- **Principal URL**: `http://localhost:8805/caldav.php/{username}/`
- **Calendar Home**: `http://localhost:8805/caldav.php/{username}/calendar/` (auto-created on first MKCALENDAR)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DAVICAL_HOST` | localhost | Server hostname |
| `DAVICAL_PORT` | 8805 | HTTP port |
| `DAVICAL_USERNAME` | testuser | Test username |
| `DAVICAL_PASSWORD` | testpass | Test password |

## Docker Image

Uses [tuxnvape/davical-standalone](https://hub.docker.com/r/tuxnvape/davical-standalone) with a separate [postgres:16-alpine](https://hub.docker.com/_/postgres) container. Despite the image name, it requires an external PostgreSQL service.

## User Setup Details

DAViCal stores users in PostgreSQL:
- `usr` table: `(username, password, fullname, email)` — passwords are prefixed with `**`
- `principal` table: `(type_id, user_no, displayname)` — type_id 1 = Person

The `setup_davical.sh` script handles user creation automatically.

## Troubleshooting

### Container won't start
Check if port 8805 is already in use:
```bash
lsof -i :8805
```

### Database initialization takes long
The first startup takes ~60s for PostgreSQL initialization plus DAViCal schema setup. Check logs:
```bash
docker-compose logs -f
```

### Testing connectivity
```bash
curl -X PROPFIND -H "Depth: 0" -u testuser:testpass http://localhost:8805/caldav.php/testuser/
```
