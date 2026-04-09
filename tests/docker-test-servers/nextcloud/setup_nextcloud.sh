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

echo "Creating test users..."
# Create test user (ignore error if already exists)
docker exec -e OC_PASS="$TEST_PASSWORD" $CONTAINER_NAME php occ user:add --password-from-env --display-name="Test User" $TEST_USER 2>/dev/null || echo "User may already exist"
# Create scheduling test users
for i in 1 2 3; do
    docker exec -e OC_PASS="testpass${i}" $CONTAINER_NAME php occ user:add --password-from-env --display-name="User ${i}" "user${i}" 2>/dev/null || echo "user${i} may already exist"
    # Set email address — required for CalDAV scheduling (calendar-user-address-set)
    docker exec $CONTAINER_NAME php occ user:setting "user${i}" settings email "user${i}@localhost" || true
done

echo "Enabling calendar app..."
docker exec $CONTAINER_NAME php occ app:enable calendar || true

echo "Enabling contacts app..."
docker exec $CONTAINER_NAME php occ app:enable contacts || true

echo "Configuring bruteforce protection..."
# Temporarily enable bruteforce protection so we can reset accumulated failed
# auth attempts (which pile up while the server is starting before users exist).
docker exec $CONTAINER_NAME php occ config:system:set auth.bruteforce.protection.enabled --value=true --type=boolean || true
for ip in 127.0.0.1 ::1; do
    docker exec $CONTAINER_NAME php occ security:bruteforce:reset "$ip" 2>/dev/null || true
done
# Detect the Docker gateway IP and reset it too
GATEWAY_IP=$(docker exec $CONTAINER_NAME sh -c "ip route | awk '/default/{print \$3}'" 2>/dev/null || true)
if [ -n "$GATEWAY_IP" ]; then
    docker exec $CONTAINER_NAME php occ security:bruteforce:reset "$GATEWAY_IP" 2>/dev/null || true
fi
# Now disable bruteforce protection — the caldav library handles 429 via
# rate_limit_handle, but Nextcloud's bruteforce gives no Retry-After header
# and would make tests slow.
docker exec $CONTAINER_NAME php occ app:disable bruteforcesettings || true
docker exec $CONTAINER_NAME php occ config:system:set auth.bruteforce.protection.enabled --value=false --type=boolean || true

echo "Disabling CalDAV trashbin (calendar retention)..."
# Setting calendarRetentionObligation to '0' (the string) disables the trashbin in
# CalDavBackend::deleteCalendar and deleteCalendarObject, making deletes permanent.
# Without this, deleted calendars/objects are soft-deleted and accumulate in the DB,
# causing UNIQUE constraint violations when tests recreate a calendar with the same slug
# (Nextcloud 33+ reuses the calendarid, keeping old soft-deleted objects, so adding
# an event with the same UID fails).
docker exec $CONTAINER_NAME php occ config:app:set dav calendarRetentionObligation --value=0 || true
# Purge any leftover soft-deleted calendars/objects from previous runs
docker exec $CONTAINER_NAME php occ dav:retention:clean-up || true

echo "Configuring CalDAV rate limits..."
docker exec $CONTAINER_NAME php occ config:app:set dav rateLimitCalendarCreation --value=99999 || true
docker exec $CONTAINER_NAME php occ config:app:set dav maximumCalendarsSubscriptions --value=-1 || true

echo "Adding IP whitelist for rate limiting..."
# Service is test-only and never exposed externally, so whitelist everything
docker exec $CONTAINER_NAME php occ config:system:set ratelimit.whitelist.0 --value='0.0.0.0/0' || true
docker exec $CONTAINER_NAME php occ config:system:set ratelimit.whitelist.1 --value='::/0' || true

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
echo "  Scheduling users: user1/testpass1, user2/testpass2, user3/testpass3"
echo "  CalDAV URL: http://localhost:8801/remote.php/dav"
echo ""
