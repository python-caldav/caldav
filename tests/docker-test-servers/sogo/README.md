# Testing with SOGo Groupware Server

This directory contains the Docker setup for running automated tests against SOGo, an enterprise groupware server with CalDAV/CardDAV support.

## Requirements

- **Docker** and **docker-compose** must be installed
- If Docker is not available, SOGo tests will be automatically skipped

## Automatic Setup

**Tests automatically start SOGo if Docker is available!** Just run:

```bash
pytest tests/
# or
tox -e py
```

The test framework will:
1. Detect if docker-compose is available
2. Automatically start the SOGo container and PostgreSQL database
3. Initialize the database with test tables and user
4. Run tests against it
5. Clean up after tests complete

## Manual Setup (Optional)

If you prefer to start SOGo manually:

```bash
cd tests/docker-test-servers/sogo
./start.sh
```

This will:
1. Start SOGo and PostgreSQL containers
2. Wait for SOGo to initialize (~15-20 seconds)
3. Verify CalDAV access
4. SOGo will be available on `http://localhost:8803`

## Configuration

This SOGo instance comes **pre-configured** with:
- Test user: `testuser` / `testpass`
- CalDAV URL: `http://localhost:8803/SOGo/dav/testuser/Calendar/`
- CardDAV URL: `http://localhost:8803/SOGo/dav/testuser/Contacts/`
- Web interface: `http://localhost:8803/SOGo/`
- PostgreSQL database for user and folder storage

**No manual configuration needed!** The container starts with a pre-created test user and initialized database.

## Environment Variables

- `SOGO_URL`: URL of the SOGo server (default: `http://localhost:8803`)
- `SOGO_USERNAME`: Test user username (default: `testuser`)
- `SOGO_PASSWORD`: Test user password (default: `testpass`)

## Disabling SOGo Tests

If you want to skip SOGo tests, create `tests/conf_private.py`:

```python
test_sogo = False
```

Or simply don't install Docker - the tests will automatically skip SOGo if Docker is not available.

## Troubleshooting

### Container won't start
```bash
# Check container logs
docker-compose logs sogo
docker-compose logs sogo-db

# Restart containers
docker-compose restart
```

### Tests can't connect to SOGo
```bash
# Check if SOGo is accessible
curl -v http://localhost:8803/SOGo/

# Check CalDAV endpoint
curl -X PROPFIND -H "Depth: 0" -u testuser:testpass \
  http://localhost:8803/SOGo/dav/testuser/Calendar/

# Check container status
docker-compose ps

# Check database
docker exec sogo-db psql -U sogo -d sogo -c "SELECT * FROM sogo_users;"
```

### Reset SOGo
```bash
# Stop and remove containers with volumes (WARNING: deletes all data)
docker-compose down -v

# Start fresh
./start.sh
```

## Docker Compose Commands

```bash
# Start SOGo in background
docker-compose up -d

# View logs
docker-compose logs -f sogo

# Stop SOGo
docker-compose stop

# Stop and remove (keeps volumes)
docker-compose down

# Stop and remove everything including data
docker-compose down -v

# Restart SOGo
docker-compose restart sogo
```

## Architecture

The SOGo testing framework consists of:

1. **docker-compose.yml** - Defines SOGo and PostgreSQL containers
2. **sogo.conf** - SOGo configuration with SQL-based authentication
3. **init-sogo.sql** - Database initialization script for tables and test user
4. **setup_sogo.sh** - Waits for SOGo to be ready and verifies access
5. **start.sh** / **stop.sh** - Manual start/stop scripts
6. **tests/conf.py** - Auto-detects SOGo and manages container lifecycle

## Ports

The SOGo container exposes:
- **8803**: HTTP (Web UI, CalDAV, CardDAV)

The PostgreSQL container is internal (not exposed to host).

## Notes

- First startup takes ~15-20 seconds as SOGo and PostgreSQL initialize
- Uses PostgreSQL 16 for user/folder storage (more realistic than SQLite)
- SOGo is an enterprise-grade groupware with advanced CalDAV features
- Container data is persisted in Docker volumes between restarts
- Container runs on port 8803 (to avoid conflicts with other test servers)
- Test user password is MD5-hashed in the database

## Differences from Other Servers

SOGo provides unique testing value compared to other servers:
- **Enterprise groupware** (vs. simple file sync like Nextcloud)
- **PostgreSQL backend** (vs. SQLite in Baikal/Nextcloud)
- **SQL-based authentication** (vs. file-based)
- **Multiple principals** per database
- **Advanced CalDAV features** like scheduling and freebusy

## Version

This setup uses the `pmietlicki/sogo:latest` Docker image. There is no official public Docker image from Alinto/SOGo, so we use this well-maintained community alternative.

## More Information

- [SOGo Website](https://www.sogo.nu/)
- [SOGo Documentation](https://www.sogo.nu/support/documentation.html)
- [Docker Image Used](https://hub.docker.com/r/pmietlicki/sogo)
- [Docker Image Source](https://github.com/pmietlicki/docker-sogo)
- [SOGo GitHub (Official)](https://github.com/Alinto/sogo)
