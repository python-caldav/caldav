# Testing with Nextcloud CalDAV Server

This directory contains the Docker setup for running automated tests against a Nextcloud CalDAV/CardDAV server. The setup works seamlessly in both local development and CI/CD environments.

## Requirements

- **Docker** and **docker-compose** must be installed
- If Docker is not available, Nextcloud tests will be automatically skipped

## Automatic Setup

**Tests automatically start Nextcloud if Docker is available!** Just run:

```bash
pytest tests/
# or
tox -e py
```

The test framework will:
1. Detect if docker-compose is available
2. Automatically start the Nextcloud container if needed
3. Configure Nextcloud and create a test user
4. Run tests against it
5. Clean up after tests complete

## Manual Setup (Optional)

If you prefer to start Nextcloud manually:

```bash
cd tests/docker-test-servers/nextcloud
./start.sh
```

This will:
1. Start the Nextcloud container with SQLite backend
2. Wait for Nextcloud to initialize (first startup takes ~1 minute)
3. Create admin user and test user
4. Enable calendar and contacts apps
5. Nextcloud will be available on `http://localhost:8801`

## Configuration

This Nextcloud instance comes **pre-configured** with:
- Admin user: `admin` / `admin`
- Test user: `testuser` / `TestPassword123!`
- Calendar and Contacts apps enabled
- CalDAV URL: `http://localhost:8801/remote.php/dav`

**No manual configuration needed!** The container will start ready to use.

**Note:** The test framework automatically appends `/remote.php/dav` to the base URL, so you can set `NEXTCLOUD_URL=http://localhost:8801` and it will work correctly.

## Environment Variables

- `NEXTCLOUD_URL`: URL of the Nextcloud server (default: `http://localhost:8801`)
- `NEXTCLOUD_USERNAME`: Test user username (default: `testuser`)
- `NEXTCLOUD_PASSWORD`: Test user password (default: `TestPassword123!`)

## Disabling Nextcloud Tests

If you want to skip Nextcloud tests, create `tests/conf_private.py`:

```python
test_nextcloud = False
```

Or simply don't install Docker - the tests will automatically skip Nextcloud if Docker is not available.

## Troubleshooting

### Container won't start
```bash
# Check container logs
docker-compose logs nextcloud

# Restart container
docker-compose restart nextcloud
```

### Tests can't connect to Nextcloud
```bash
# Check if Nextcloud is accessible
curl -v http://localhost:8801/

# Check if container is running
docker-compose ps

# Check container health
docker inspect nextcloud-test
```

### Reset Nextcloud
```bash
# Stop and remove container with volumes (WARNING: deletes all data)
docker-compose down -v

# Start fresh
./start.sh
```

## Known Issues

### Repeated Compatibility Tests Against Same Container

**Issue:** Running the `testCheckCompatibility` test repeatedly against the same Nextcloud container will eventually fail with 500 errors due to database unique constraint violations.

**Root Cause:** The compatibility tests create test objects with fixed UIDs (e.g., `csc_simple_event1`, `csc_alarm_test_event`). On the first run, these are created successfully. On subsequent runs against the same container, the test tries to create these objects again, violating SQLite unique constraints.

**Workaround:** Restart the container between test runs to get a fresh database:
```bash
cd tests/docker-test-servers/nextcloud
./stop.sh && ./start.sh
```

**Note:** The tmpfs storage is ephemeral between container restarts (data is lost on stop/start), but persists during a single container's lifetime. This is the expected behavior for efficient testing - most tests work fine with a persistent container, and only the compatibility tests require a fresh container.

**TODO:** This should be fixed in the caldav-server-tester project by having the PrepareCalendar check properly handle existing test objects or by cleaning up test data before creating new objects.

## Docker Compose Commands

```bash
# Start Nextcloud in background
docker-compose up -d

# View logs
docker-compose logs -f nextcloud

# Stop Nextcloud
docker-compose stop

# Stop and remove (keeps volumes)
docker-compose down

# Stop and remove everything including data
docker-compose down -v

# Restart Nextcloud
docker-compose restart nextcloud
```

## Architecture

The Nextcloud testing framework consists of:

1. **docker-compose.yml** - Defines the Nextcloud container with SQLite backend
2. **setup_nextcloud.sh** - Configures Nextcloud and creates test user
3. **start.sh** / **stop.sh** - Manual start/stop scripts
4. **tests/conf.py** - Auto-detects Nextcloud and manages container lifecycle

## Notes

- First startup takes longer (~1 minute) as Nextcloud initializes
- Uses SQLite for simplicity (production should use MySQL/PostgreSQL)
- Data is stored in tmpfs (ephemeral storage) - lost on container restart but persists during container lifetime
- Container runs on port 8801 (to avoid conflicts with Baikal on 8800)

## Version

This setup uses the `nextcloud:latest` Docker image, which currently tracks the latest stable Nextcloud release.
