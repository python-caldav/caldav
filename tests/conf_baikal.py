"""
Configuration for running tests against Baikal CalDAV server in Docker.

This module provides configuration for testing against the Baikal CalDAV
server running in a Docker container. It can be used both locally (via
docker-compose) and in CI/CD pipelines (GitHub Actions).

Usage:
    Local testing:
        docker-compose up -d
        export BAIKAL_URL=http://localhost:8800
        pytest

    CI testing:
        The GitHub Actions workflow automatically sets up the Baikal service
        and exports the BAIKAL_URL environment variable.
"""
import os

from caldav import compatibility_hints

# Get Baikal URL from environment, default to local docker-compose setup
BAIKAL_URL = os.environ.get("BAIKAL_URL", "http://localhost:8800")

# Baikal default credentials (these need to be configured after first start)
# Note: Baikal requires initial setup through the web interface
# For CI, you may need to pre-configure or use API/config file approach
BAIKAL_USERNAME = os.environ.get("BAIKAL_USERNAME", "testuser")
BAIKAL_PASSWORD = os.environ.get("BAIKAL_PASSWORD", "testpass")

# Configuration for Baikal server
baikal_config = {
    "name": "BaikalDocker",
    "url": BAIKAL_URL,
    "username": BAIKAL_USERNAME,
    "password": BAIKAL_PASSWORD,
    "features": compatibility_hints.baikal
    if hasattr(compatibility_hints, "baikal")
    else {},
}


def is_baikal_available() -> bool:
    """
    Check if Baikal server is available and configured.

    Returns:
        bool: True if Baikal is running and accessible, False otherwise.
    """
    try:
        import requests

        response = requests.get(BAIKAL_URL, timeout=5)
        return response.status_code in (200, 401, 403)  # Server is responding
    except Exception:
        return False


def get_baikal_config():
    """
    Get Baikal configuration if the server is available.

    Returns:
        dict or None: Configuration dict if available, None otherwise.
    """
    if is_baikal_available():
        return baikal_config
    return None
