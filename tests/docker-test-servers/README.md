# Docker Test Servers

This directory contains Docker-based test server configurations for running integration tests against various CalDAV server implementations.

## Available Test Servers

### Baikal

A lightweight CalDAV and CardDAV server.

- **Location**: `baikal/`
- **Documentation**: [baikal/README.md](baikal/README.md)
- **Quick Start**:
  ```bash
  cd baikal
  docker-compose up -d
  ```

## Adding New Test Servers

To add a new CalDAV server for testing:

1. Create a new directory under `tests/docker-test-servers/`
2. Add a `docker-compose.yml` file
3. Create a `README.md` with setup instructions
4. Add configuration to `tests/conf_<servername>.py`
5. Update `.github/workflows/tests.yaml` to include the new service

## General Usage

### Local Testing

1. Navigate to the specific server directory
2. Start the container: `docker-compose up -d`
3. Configure the server (see server-specific README)
4. Run tests from project root with appropriate environment variables

### CI/CD Testing

Test servers are automatically started as GitHub Actions services. See `.github/workflows/tests.yaml` for configuration.

## Environment Variables

Each server may use different environment variables. Common ones include:

- `<SERVER>_URL`: URL of the test server
- `<SERVER>_USERNAME`: Test user username
- `<SERVER>_PASSWORD`: Test user password

See individual server READMEs for specific variables.
