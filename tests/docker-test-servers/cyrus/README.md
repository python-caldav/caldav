# Testing with Cyrus IMAP CalDAV Server

This directory contains the Docker setup for running automated tests against a Cyrus IMAP CalDAV/CardDAV server. The setup works seamlessly in both local development and CI/CD environments.

## Requirements

- **Docker** and **docker-compose** must be installed
- If Docker is not available, Cyrus tests will be automatically skipped

## Automatic Setup

**Tests automatically start Cyrus if Docker is available!** Just run:

```bash
pytest tests/
# or
tox -e py
```

The test framework will:
1. Detect if docker-compose is available
2. Automatically start the Cyrus container if needed
3. Create a test user via the management API
4. Run tests against it
5. Clean up after tests complete

## Manual Setup (Optional)

If you prefer to start Cyrus manually:

```bash
cd tests/docker-test-servers/cyrus
./start.sh
```

This will:
1. Start the Cyrus container with the official test image
2. Wait for Cyrus to initialize (~10-15 seconds)
3. Create a test user via the management API
4. Cyrus will be available on `http://localhost:8802`

## Configuration

This Cyrus instance comes **pre-configured** with:
- Test users: `user1`, `user2`, `user3`, `user4`, `user5` (password: `x` for all)
- CalDAV URL: `http://localhost:8802/dav/calendars/user/user1`
- CardDAV URL: `http://localhost:8802/dav/addressbooks/user/user1`
- Management API: `http://localhost:8001` (for creating additional users)

**No manual configuration needed!** The container will start with 5 pre-created users ready to use.

**Note:** Cyrus uses a simple password scheme for testing where all passwords are `x`.

## Environment Variables

- `CYRUS_URL`: URL of the Cyrus server (default: `http://localhost:8802`)
- `CYRUS_USERNAME`: Test user username (default: `user1`)
- `CYRUS_PASSWORD`: Test user password (default: `x`)

## Disabling Cyrus Tests

If you want to skip Cyrus tests, create `tests/conf_private.py`:

```python
test_cyrus = False
```

Or simply don't install Docker - the tests will automatically skip Cyrus if Docker is not available.

## Troubleshooting

### Container won't start
```bash
# Check container logs
docker-compose logs cyrus

# Restart container
docker-compose restart cyrus
```

### Tests can't connect to Cyrus
```bash
# Check if Cyrus is accessible
curl -v http://localhost:8802/

# Check if container is running
docker-compose ps

# Check container health
docker inspect cyrus-test
```

### Reset Cyrus
```bash
# Stop and remove container with volumes (WARNING: deletes all data)
docker-compose down -v

# Start fresh
./start.sh
```

## Docker Compose Commands

```bash
# Start Cyrus in background
docker-compose up -d

# View logs
docker-compose logs -f cyrus

# Stop Cyrus
docker-compose stop

# Stop and remove (keeps volumes)
docker-compose down

# Stop and remove everything including data
docker-compose down -v

# Restart Cyrus
docker-compose restart cyrus
```

## Architecture

The Cyrus testing framework consists of:

1. **docker-compose.yml** - Defines the Cyrus container using the official test image
2. **setup_cyrus.sh** - Creates test user via management API
3. **start.sh** / **stop.sh** - Manual start/stop scripts
4. **tests/conf.py** - Auto-detects Cyrus and manages container lifecycle

## Ports

The Cyrus container exposes:
- **8802**: HTTP (CalDAV, CardDAV, JMAP)
- **8143**: IMAP
- **8001**: Management API (for creating users)

## Notes

- First startup takes ~10-15 seconds as Cyrus initializes
- Uses official Cyrus IMAP Docker test server image
- Data is persisted in Docker volumes between restarts
- Container runs on port 8802 (to avoid conflicts with other test servers)
- All test users use password `x` by default

## Version

This setup uses the `ghcr.io/cyrusimap/cyrus-docker-test-server:latest` Docker image from the official Cyrus IMAP project.

## More Information

- [Cyrus IMAP](https://www.cyrusimap.org/)
- [Cyrus Docker Test Server](https://github.com/cyrusimap/cyrus-docker-test-server)
- [Cyrus CalDAV Documentation](https://www.cyrusimap.org/imap/download/installation/http/caldav.html)
