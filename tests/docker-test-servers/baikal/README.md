# Testing with Baikal CalDAV Server

This project includes a framework for running tests against a Baikal CalDAV server in a Docker container. This setup works both locally and in CI/CD pipelines (GitHub Actions).

## Quick Start (Local Testing)

### 1. Start Baikal Container

```bash
cd tests/docker-test-servers/baikal
./start.sh
```

This will:
1. Start the Baikal CalDAV server container
2. Copy the pre-configured database and config files
3. Restart the container to apply the configuration
4. Wait for Baikal to be ready on `http://localhost:8800`

### 2. Pre-configured and Ready!

This Baikal instance comes **pre-configured** with:
- Admin user: `admin` / `admin`
- Test user: `testuser` / `testpass`
- Default calendar and addressbook already created
- Digest authentication enabled

**No manual configuration needed!** The container will start ready to use.

### 3. Run Tests

```bash
# From project root directory
# Export Baikal URL (optional, defaults to http://localhost:8800)
export BAIKAL_URL=http://localhost:8800
export BAIKAL_USERNAME=testuser
export BAIKAL_PASSWORD=testpass

# Run tests
pytest tests/
```

Or with tox:

```bash
tox -e py
```

## GitHub Actions (CI/CD)

The GitHub Actions workflow in `.github/workflows/tests.yaml` automatically:

1. Spins up a Baikal container as a service
2. Waits for Baikal to be healthy
3. Runs the test suite

**Note:** For CI to work properly, you need to either:
- Pre-configure Baikal and commit the config (if appropriate for your project)
- Modify tests to skip Baikal-specific tests if not configured
- Use automated configuration scripts

### Configuring CI

The workflow sets these environment variables:
- `BAIKAL_URL=http://localhost:8800`

You can add more secrets in GitHub Actions settings for credentials.

## Configuration

### Environment Variables

- `BAIKAL_URL`: URL of the Baikal server (default: `http://localhost:8800`)
- `BAIKAL_USERNAME`: Test user username (default: `testuser`)
- `BAIKAL_PASSWORD`: Test user password (default: `testpass`)
- `BAIKAL_ADMIN_PASSWORD`: Admin password for initial setup (default: `admin`)

### Test Configuration

The test suite will automatically detect and use Baikal if configured. Configuration is in:
- `tests/conf_baikal.py` - Baikal-specific configuration
- `tests/conf.py` - Main test configuration (add Baikal to `caldav_servers` list)

To enable Baikal testing, add to `tests/conf_private.py`:

```python
from tests.conf_baikal import get_baikal_config

# Add Baikal to test servers if available
baikal_conf = get_baikal_config()
if baikal_conf:
    caldav_servers.append(baikal_conf)
```

## Troubleshooting

### Container won't start
```bash
# Check container logs
docker-compose logs baikal

# Restart container
docker-compose restart baikal
```

### Tests can't connect to Baikal
```bash
# Check if Baikal is accessible
curl -v http://localhost:8800/

# Check if container is running
docker-compose ps

# Check container health
docker inspect baikal-test | grep -A 10 Health
```

### Reset Baikal
```bash
# Stop and remove container with volumes
docker-compose down -v

# Start fresh
docker-compose up -d
```

## Docker Compose Commands

```bash
# Start Baikal in background
docker-compose up -d

# View logs
docker-compose logs -f baikal

# Stop Baikal
docker-compose stop

# Stop and remove (keeps volumes)
docker-compose down

# Stop and remove everything including data
docker-compose down -v

# Restart Baikal
docker-compose restart baikal
```

## Architecture

The Baikal testing framework consists of:

1. **tests/docker-test-servers/baikal/docker-compose.yml** - Defines the Baikal container service
2. **tests/docker-test-servers/baikal/Specific/** - Pre-configured database and config files
3. **tests/docker-test-servers/baikal/create_baikal_db.py** - Script to regenerate config (if needed)
4. **.github/workflows/tests.yaml** - GitHub Actions workflow with Baikal service
5. **tests/conf.py** - Auto-detects Baikal when BAIKAL_URL is set

## Regenerating Configuration

If you need to recreate the pre-configured database:

```bash
cd tests/docker-test-servers/baikal
python3 create_baikal_db.py
```

This will regenerate:
- `Specific/db/db.sqlite` - Database with testuser
- `Specific/config.php` - Main configuration
- `Specific/config.system.php` - System configuration

## Contributing

When adding Baikal-specific tests:
- Check if Baikal is available before running tests
- Use `tests/conf_baikal.is_baikal_available()` to check availability
- Mark Baikal-specific tests with appropriate markers or skips

## References

- Baikal Docker Image: https://hub.docker.com/r/ckulka/baikal
- Baikal Project: https://sabre.io/baikal/
- CalDAV Protocol: RFC 4791
