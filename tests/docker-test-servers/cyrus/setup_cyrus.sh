#!/bin/bash
# Setup script for Cyrus IMAP test server with CalDAV support

set -e

CONTAINER_NAME="cyrus-test"
TEST_USER="testuser"
TEST_PASSWORD="x"  # Cyrus test server uses 'x' as default password
MANAGEMENT_URL="http://localhost:8001"

echo "Waiting for Cyrus server to be ready..."
max_attempts=30
for i in $(seq 1 $max_attempts); do
    if curl -f http://localhost:8802/ 2>/dev/null >/dev/null; then
        echo "✓ Cyrus HTTP server is ready"
        break
    fi
    if [ $i -eq $max_attempts ]; then
        echo "✗ Cyrus server did not become ready in time"
        exit 1
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "Creating test user via management API..."
# Create user using the management API
# The API expects a PUT request with user data
curl -X PUT "${MANAGEMENT_URL}/user/${TEST_USER}" \
    -H "Content-Type: application/json" \
    -d '{"password": "'${TEST_PASSWORD}'"}' \
    2>/dev/null || echo "User may already exist"

echo ""
echo "✓ Cyrus setup complete!"
echo ""
echo "Credentials:"
echo "  Test user: ${TEST_USER} / ${TEST_PASSWORD}"
echo "  CalDAV URL: http://localhost:8802/dav/calendars/user/${TEST_USER}"
echo "  CardDAV URL: http://localhost:8802/dav/addressbooks/user/${TEST_USER}"
echo ""
