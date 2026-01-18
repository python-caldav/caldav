# DAViCal Test Server

DAViCal is a CalDAV server that uses PostgreSQL as its backend. This Docker configuration provides a complete DAViCal server for testing.

## Quick Start

```bash
cd tests/docker-test-servers/davical
docker-compose up -d
```

Wait about 30 seconds for the database to initialize, then the server will be available.

## Configuration

- **URL**: http://localhost:8805/davical/caldav.php
- **Admin User**: admin
- **Admin Password**: testpass (set via DAVICAL_ADMIN_PASS)

## Creating Test Users

After the server starts, you can create test users via the admin interface:

1. Navigate to http://localhost:8805/davical/admin.php
2. Login with admin / testpass
3. Create a new user (e.g., testuser / testpass)

Alternatively, the container may pre-create a test user depending on the image configuration.

## CalDAV Endpoints

- **Principal URL**: `http://localhost:8805/davical/caldav.php/{username}/`
- **Calendar Home**: `http://localhost:8805/davical/caldav.php/{username}/calendar/`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DAVICAL_HOST` | localhost | Server hostname |
| `DAVICAL_PORT` | 8805 | HTTP port |
| `DAVICAL_USERNAME` | admin | Test username |
| `DAVICAL_PASSWORD` | testpass | Test password |

## Docker Image

This configuration uses the [tuxnvape/davical-standalone](https://hub.docker.com/r/tuxnvape/davical-standalone) Docker image, which provides a complete DAViCal installation with PostgreSQL.

## Troubleshooting

### Container won't start
Check if port 8805 is already in use:
```bash
lsof -i :8805
```

### Database initialization
The first startup may take 30+ seconds while PostgreSQL initializes. Check logs:
```bash
docker-compose logs -f
```

### Testing connectivity
```bash
curl -u admin:testpass http://localhost:8805/davical/caldav.php/admin/
```
