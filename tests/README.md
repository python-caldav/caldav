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
```

## Test Configuration

Test configuration is managed through several files:

- `conf.py` - Main test configuration, includes setup for Xandikos and Radicale servers
- `conf_private.py.EXAMPLE` - Example private configuration for custom CalDAV servers
- `conf_private.py` - Your personal test server configuration (gitignored)
- `conf_baikal.py` - Configuration for Baikal Docker test server

### Testing Against Your Own Server

1. Copy the example configuration:
   ```bash
   cp tests/conf_private.py.EXAMPLE tests/conf_private.py
   ```

2. Edit `conf_private.py` and add your server details:
   ```python
   caldav_servers = [
       {
           'name': 'MyServer',
           'url': 'https://caldav.example.com',
           'username': 'testuser',
           'password': 'password',
           'features': [],
       }
   ]
   ```

3. Run tests:
   ```bash
   pytest
   ```

## Docker Test Servers

The `docker-test-servers/` directory contains Docker configurations for running tests against various CalDAV server implementations:

- **Baikal** - Lightweight CalDAV/CardDAV server

See [docker-test-servers/README.md](docker-test-servers/README.md) for details.

### Quick Start with Baikal

```bash
cd tests/docker-test-servers/baikal
docker-compose up -d
# Configure Baikal through web interface at http://localhost:8800
# Then run tests from project root
cd ../../..
pytest
```

## Test Structure

- `test_cdav.py` - Tests for CalDAV elements
- `test_vcal.py` - Tests for calendar/event handling
- `test_utils.py` - Utility function tests
- `test_docs.py` - Documentation tests
- `test_caldav.py` - Main CalDAV client tests
- `test_caldav_unit.py` - Unit tests for CalDAV client
- `test_search.py` - Search functionality tests

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
1. Either set up `conf_private.py` with your server details
2. Or use the Docker test servers (recommended)
3. Tests will still run against embedded servers (Xandikos, Radicale) if available

### Docker test server won't start

```bash
cd tests/docker-test-servers/baikal
docker-compose logs
docker-compose down -v  # Reset everything
docker-compose up -d
```

### Tests timing out

Some CalDAV servers may be slow to respond. You can increase timeouts in your test configuration or skip slow tests:

```bash
pytest -m "not slow"
```
