#!/bin/bash
# Setup script for Baikal CalDAV server for testing
#
# This script helps configure a fresh Baikal installation for testing.
# It can be used both locally and in CI environments.

set -e

BAIKAL_URL="${BAIKAL_URL:-http://localhost:8800}"
BAIKAL_ADMIN_PASSWORD="${BAIKAL_ADMIN_PASSWORD:-admin}"
BAIKAL_USERNAME="${BAIKAL_USERNAME:-testuser}"
BAIKAL_PASSWORD="${BAIKAL_PASSWORD:-testpass}"

echo "Setting up Baikal CalDAV server at $BAIKAL_URL"

# Wait for Baikal to be ready
echo "Waiting for Baikal to be ready..."
timeout 60 bash -c "until curl -f $BAIKAL_URL/ 2>/dev/null; do echo 'Waiting...'; sleep 2; done" || {
    echo "Error: Baikal did not become ready in time"
    exit 1
}

echo "Baikal is ready!"

# Note: Baikal requires initial configuration through web interface or config files
# For automated testing, you may need to:
# 1. Pre-configure Baikal by mounting a pre-configured config directory
# 2. Use the Baikal API if available
# 3. Manually configure once and export the config

echo ""
echo "================================================================"
echo "IMPORTANT: Baikal Initial Configuration Required"
echo "================================================================"
echo ""
echo "Baikal requires initial setup through the web interface or"
echo "by providing pre-configured files."
echo ""
echo "For automated testing, you have several options:"
echo ""
echo "1. Access $BAIKAL_URL in your browser and complete the setup"
echo "   - Set admin password to: $BAIKAL_ADMIN_PASSWORD"
echo "   - Create a test user: $BAIKAL_USERNAME / $BAIKAL_PASSWORD"
echo ""
echo "2. Mount a pre-configured Baikal config directory:"
echo "   - Configure Baikal once"
echo "   - Export the config directory"
echo "   - Mount it in docker-compose.yml or CI"
echo ""
echo "3. For CI/CD: See tests/baikal-config/ for sample configs"
echo ""
echo "================================================================"
