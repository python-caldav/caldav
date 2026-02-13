# CalDAV Library Tests

This directory contains the test suite for the caldav Python library.

## Running Tests

### Quick Start

Run all tests using pytest:

```bash
pytest
```

Or using tox (recommended):

```bash
tox -e py
```

### Running Specific Tests

```bash
# Run a specific test file
pytest tests/test_cdav.py

# Run a specific test function
pytest tests/test_cdav.py::test_element

# Run tests matching a pattern
pytest -k "test_to_utc"

# Run only unit tests (no server required)
pytest tests/test_caldav_unit.py
```

## Test Configuration

Test configuration uses YAML or JSON files. The configuration loader searches
these locations in order:

1. `tests/caldav_test_servers.yaml`
2. `tests/caldav_test_servers.json`
3. `~/.config/caldav/test_servers.yaml`
4. `~/.config/caldav/test_servers.json`

### Setting Up Test Configuration

1. Copy the example configuration:
   ```bash
   cp tests/caldav_test_servers.yaml.example tests/caldav_test_servers.yaml
   ```

2. If you want to populate it with private passwords, remember to protect it:
   ```sh
   chmod og-r tests/caldav_test_servers.yaml
   ```

3. Edit `caldav_test_servers.yaml` to enable/configure servers:
   ```yaml
   test-servers:
     radicale:
       type: embedded
       enabled: true

     baikal:
       type: docker
       enabled: true
       username: testuser
       password: testpass

     # Your own server
     my-server:
       type: external
       enabled: true
       url: https://caldav.example.com
       username: testuser
       password: secret
   ```

3. Run tests:
   ```bash
   pytest
   ```

### Environment Variables

Configuration values support environment variable expansion:

```yaml
my-server:
  url: ${CALDAV_URL}
  username: ${CALDAV_USERNAME}
  password: ${CALDAV_PASSWORD}
```

You can also use defaults: `${VAR:-default_value}`

### Migration from conf_private.py

If you have an existing `conf_private.py`, a migration script is provided:

```bash
python tests/tools/convert_conf_private.py
```

This generates a `caldav_test_servers.yaml` from your existing configuration.
The old `conf_private.py` format is deprecated and will be removed in v3.0.

## Test Server Types

### Embedded Servers

These run in-process and require no setup:

- **Radicale** - Requires `radicale` package (`pip install radicale`)
- **Xandikos** - Requires `xandikos` package (`pip install xandikos`)

### Docker Servers

The `docker-test-servers/` directory contains Docker configurations for:

- **Baikal** - Lightweight CalDAV/CardDAV server
- **Nextcloud** - Full-featured cloud platform
- **Cyrus** - Enterprise mail/calendaring server
- **SOGo** - Groupware server
- **Bedework** - Enterprise calendar server
- **DAViCal** - CalDAV server

See [docker-test-servers/README.md](docker-test-servers/README.md) for details.

#### Quick Start with Docker

```bash
# Start Baikal
cd tests/docker-test-servers/baikal
docker-compose up -d

# Run tests (from project root)
cd ../../..
pytest

# Stop when done
cd tests/docker-test-servers/baikal
docker-compose down
```

### External Servers

For testing against your own CalDAV server:

```yaml
test-servers:
  my-server:
    type: external
    enabled: true
    url: https://caldav.example.com/dav/
    username: testuser
    password: secret
    # Optional: specify known limitations
    features:
      - no-expand
      - no-sync-token
```

## Test Structure

### Unit Tests (no server required)
- `test_caldav_unit.py` - CalDAV client unit tests
- `test_cdav.py` - CalDAV elements tests
- `test_vcal.py` - Calendar/event handling tests
- `test_utils.py` - Utility function tests
- `test_protocol.py` - Protocol layer tests
- `test_search.py` - Search functionality tests
- `test_operations_*.py` - Operation module tests

### Integration Tests (require server)
- `test_caldav.py` - Main CalDAV client integration tests
- `test_async_integration.py` - Async client integration tests

### Other Tests
- `test_docs.py` - Documentation tests
- `test_examples.py` - Example code tests
- `test_compatibility_hints.py` - Server compatibility tests

## Test Server Framework

The `test_servers/` directory contains the unified test server framework:

- `base.py` - Base classes for test servers
- `config_loader.py` - Configuration file loading
- `registry.py` - Server discovery and registration
- `embedded.py` - Embedded server implementations (Radicale, Xandikos)
- `docker.py` - Docker server implementations
- `helpers.py` - Test helper utilities

## Continuous Integration

Tests run automatically on GitHub Actions for:
- Python versions: 3.9, 3.10, 3.11, 3.12, 3.13, 3.14
- With Baikal CalDAV server as a service container

See `.github/workflows/tests.yaml` for the full CI configuration.

## Coverage

Generate a coverage report:

```bash
coverage run -m pytest
coverage report
coverage html  # Generate HTML report
```

## Troubleshooting

### No test servers configured

If you see warnings about no test servers being configured:

1. Set up `caldav_test_servers.yaml` with your server details, or
2. Install embedded servers: `pip install radicale xandikos`, or
3. Use the Docker test servers

### Embedded server won't start

Check that the required packages are installed:
```bash
pip install radicale xandikos
```

### Docker test server won't start

```bash
cd tests/docker-test-servers/baikal
docker-compose logs
docker-compose down -v  # Reset everything
docker-compose up -d
```

### Tests timing out

Some CalDAV servers may be slow to respond. You can skip slow tests:

```bash
pytest -m "not slow"
```

Or increase the timeout in your test configuration.

### Permission errors

Some tests require write access to calendars. Ensure your test user has
appropriate permissions on the server.
