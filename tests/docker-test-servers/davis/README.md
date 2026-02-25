# Davis Test Server

[Davis](https://github.com/tchapi/davis) is a modern admin interface and standalone server for sabre/dav (Symfony 7). This Docker configuration uses the standalone image which bundles PHP-FPM + Caddy with a SQLite backend.

## Quick Start

```bash
cd tests/docker-test-servers/davis
./start.sh
```

This will:
1. Start the Davis container
2. Wait for it to be healthy
3. Run database migrations
4. Create a test user with CalDAV access
5. Verify connectivity

## Configuration

- **URL**: http://localhost:8806/dav/
- **Admin**: admin / admin
- **Test User**: testuser / testpass

## CalDAV Endpoints

- **DAV root**: `http://localhost:8806/dav/`
- **Principal URL**: `http://localhost:8806/dav/principals/testuser/`
- **Calendar Home**: `http://localhost:8806/dav/calendars/testuser/`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DAVIS_HOST` | localhost | Server hostname |
| `DAVIS_PORT` | 8806 | HTTP port |
| `DAVIS_USERNAME` | testuser | Test username |
| `DAVIS_PASSWORD` | testpass | Test password |

## Docker Image

Uses [ghcr.io/tchapi/davis-standalone](https://github.com/tchapi/davis) — a single container with PHP-FPM, Caddy, and SQLite.

## User Setup Details

Davis uses sabre/dav which requires entries in multiple database tables:
- `users` table: `(username, digesta1)` where digesta1 = `md5("username:realm:password")`
- `principals` table: `(uri, email, displayname)` where uri = `principals/username`
- Calendar-proxy principals for delegation support

The `setup_davis.sh` script handles all of this automatically.

## Troubleshooting

### Container won't start
Check if port 8806 is already in use:
```bash
lsof -i :8806
```

### Database issues
Check container logs:
```bash
docker-compose logs -f
```

### Testing connectivity
```bash
curl -X PROPFIND -H "Depth: 0" -u testuser:testpass http://localhost:8806/dav/
```
