#!/bin/bash
# Setup script for Nextcloud test server
# This script configures Nextcloud and creates a test user

set -e

CONTAINER_NAME="nextcloud-test"
TEST_USER="testuser"
TEST_PASSWORD="testpass"

echo "Waiting for Nextcloud to be ready..."
max_attempts=60
for i in $(seq 1 $max_attempts); do
    if docker exec $CONTAINER_NAME php occ status 2>/dev/null | grep -q "installed: true"; then
        echo "✓ Nextcloud is ready"
        break
    fi
    if [ $i -eq $max_attempts ]; then
        echo "✗ Nextcloud did not become ready in time"
        exit 1
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "Creating test user..."
# Create test user (ignore error if already exists)
docker exec $CONTAINER_NAME php occ user:add --password-from-env --display-name="Test User" $TEST_USER <<< "$TEST_PASSWORD" 2>/dev/null || echo "User may already exist"

echo "Enabling calendar app..."
docker exec $CONTAINER_NAME php occ app:enable calendar || true

echo "Enabling contacts app..."
docker exec $CONTAINER_NAME php occ app:enable contacts || true

echo ""
echo "✓ Nextcloud setup complete!"
echo ""
echo "Credentials:"
echo "  Admin: admin / admin"
echo "  Test user: $TEST_USER / $TEST_PASSWORD"
echo "  CalDAV URL: http://localhost:8801/remote.php/dav"
echo ""
