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
echo "Disabling password policy for testing..."
docker exec $CONTAINER_NAME php occ app:disable password_policy || true

echo "Creating test user..."
# Create test user (ignore error if already exists)
docker exec -e OC_PASS="$TEST_PASSWORD" $CONTAINER_NAME php occ user:add --password-from-env --display-name="Test User" $TEST_USER 2>/dev/null || echo "User may already exist"

echo "Enabling calendar app..."
docker exec $CONTAINER_NAME php occ app:enable calendar || true

echo "Enabling contacts app..."
docker exec $CONTAINER_NAME php occ app:enable contacts || true

echo "Disabling rate limiting for testing..."
docker exec $CONTAINER_NAME php occ config:system:set ratelimit.enabled --value=false --type=boolean || true
docker exec $CONTAINER_NAME php occ app:disable bruteforcesettings || true
docker exec $CONTAINER_NAME php occ config:system:set auth.bruteforce.protection.enabled --value=false --type=boolean || true

echo "Configuring CalDAV rate limits..."
docker exec $CONTAINER_NAME php occ config:app:set dav rateLimitCalendarCreation --value=99999 || true
docker exec $CONTAINER_NAME php occ config:app:set dav maximumCalendarsSubscriptions --value=-1 || true

echo "Adding IP whitelist for rate limiting..."
docker exec $CONTAINER_NAME php occ config:system:set ratelimit.whitelist.0 --value='172.19.0.0/16' || true
docker exec $CONTAINER_NAME php occ config:system:set ratelimit.whitelist.1 --value='127.0.0.1' || true

echo "Clearing rate limit cache..."
docker exec $CONTAINER_NAME php -r "
\$db = new PDO('sqlite:/var/www/html/data/nextcloud.db');
\$db->exec('DELETE FROM oc_ratelimit_entries');
\$db->exec('DELETE FROM oc_bruteforce_attempts');
echo 'Cleared rate limit and bruteforce caches\n';
" || true

echo ""
echo "✓ Nextcloud setup complete!"
echo ""
echo "Credentials:"
echo "  Admin: admin / admin"
echo "  Test user: $TEST_USER / $TEST_PASSWORD"
echo "  CalDAV URL: http://localhost:8801/remote.php/dav"
echo ""
