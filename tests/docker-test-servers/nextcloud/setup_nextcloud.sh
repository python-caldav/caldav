#!/bin/bash
# Setup script for Nextcloud test server
# This script configures Nextcloud and creates a test user

set -e

CONTAINER_NAME="${NEXTCLOUD_CONTAINER:-nextcloud-test}"
NEXTCLOUD_PORT="${NEXTCLOUD_PORT:-8801}"
TEST_USER="testuser"
TEST_PASSWORD="testpass"

# Nextcloud requires occ to be run as the web server user.  `docker exec` runs as
# root by default, and any file occ creates then ends up root-owned inside
# /var/www/html — which the server itself (running as www-data) cannot write
# afterwards, leaving an install that answers HTTP 500 on every request.
# Usage: occ [-e VAR=value]... <occ arguments>
occ() {
    local envs=()
    while [ "$1" = "-e" ]; do
        envs+=(-e "$2")
        shift 2
    done
    docker exec "${envs[@]}" -u www-data "$CONTAINER_NAME" php occ "$@"
}

echo "Waiting for Nextcloud to be ready..."
max_attempts=60
for i in $(seq 1 $max_attempts); do
    if occ status 2>/dev/null | grep -q "installed: true"; then
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
occ app:disable password_policy || true

echo "Creating test users..."
# Create test user (ignore error if already exists)
occ -e OC_PASS="$TEST_PASSWORD" user:add --password-from-env --display-name="Test User" $TEST_USER 2>/dev/null || echo "User may already exist"
# Create scheduling test users
for i in 1 2 3; do
    occ -e OC_PASS="testpass${i}" user:add --password-from-env --display-name="User ${i}" "user${i}" 2>/dev/null || echo "user${i} may already exist"
    # Set email address — required for CalDAV scheduling (calendar-user-address-set)
    occ user:setting "user${i}" settings email "user${i}@localhost" || true
done

echo "Enabling calendar app..."
occ app:enable calendar || true

echo "Enabling contacts app..."
occ app:enable contacts || true

echo "Configuring bruteforce protection..."
# Temporarily enable bruteforce protection so we can reset accumulated failed
# auth attempts (which pile up while the server is starting before users exist).
occ config:system:set auth.bruteforce.protection.enabled --value=true --type=boolean || true
for ip in 127.0.0.1 ::1; do
    occ security:bruteforce:reset "$ip" 2>/dev/null || true
done
# Detect the Docker gateway IP and reset it too
GATEWAY_IP=$(docker exec "$CONTAINER_NAME" sh -c "ip route | awk '/default/{print \$3}'" 2>/dev/null || true)
if [ -n "$GATEWAY_IP" ]; then
    occ security:bruteforce:reset "$GATEWAY_IP" 2>/dev/null || true
fi
# Now disable bruteforce protection — the caldav library handles 429 via
# rate_limit_handle, but Nextcloud's bruteforce gives no Retry-After header
# and would make tests slow.
occ app:disable bruteforcesettings || true
occ config:system:set auth.bruteforce.protection.enabled --value=false --type=boolean || true

echo "Disabling CalDAV trashbin (calendar retention)..."
# Setting calendarRetentionObligation to '0' (the string) disables the trashbin in
# CalDavBackend::deleteCalendar and deleteCalendarObject, making deletes permanent.
# Without this, deleted calendars/objects are soft-deleted and accumulate in the DB,
# causing UNIQUE constraint violations when tests recreate a calendar with the same slug
# (Nextcloud 33+ reuses the calendarid, keeping old soft-deleted objects, so adding
# an event with the same UID fails).
occ config:app:set dav calendarRetentionObligation --value=0 || true
# Purge any leftover soft-deleted calendars/objects from previous runs
occ dav:retention:clean-up || true

echo "Configuring CalDAV rate limits..."
occ config:app:set dav rateLimitCalendarCreation --value=99999 || true
occ config:app:set dav maximumCalendarsSubscriptions --value=-1 || true

echo "Adding IP whitelist for rate limiting..."
# Service is test-only and never exposed externally, so whitelist everything
occ config:system:set ratelimit.whitelist.0 --value='0.0.0.0/0' || true
occ config:system:set ratelimit.whitelist.1 --value='::/0' || true

echo "Clearing rate limit cache..."
# The SQLite file is named after the `dbname` config value, and Nextcloud's
# default is `owncloud`, not `nextcloud` — look it up instead of guessing.  Guard
# on the file existing as well: PDO happily *creates* a missing SQLite file, so a
# wrong path leaves a bogus empty database behind and every DELETE below fails
# with "no such table".
DB_NAME=$(occ config:system:get dbname 2>/dev/null | tr -d '\r\n')
DB_PATH="/var/www/html/data/${DB_NAME:-owncloud}.db"
if docker exec -u www-data "$CONTAINER_NAME" test -f "$DB_PATH"; then
    docker exec -u www-data "$CONTAINER_NAME" php -r "
    \$db = new PDO('sqlite:$DB_PATH');
    foreach (['oc_ratelimit_entries', 'oc_bruteforce_attempts'] as \$table) {
        try {
            \$db->exec(\"DELETE FROM \$table\");
        } catch (PDOException \$e) {
            fwrite(STDERR, \"skipping \$table: \" . \$e->getMessage() . \"\n\");
        }
    }
    echo \"Cleared rate limit and bruteforce caches\n\";
    " || true
else
    echo "✗ No database found at $DB_PATH — skipping cache cleanup"
fi

echo "Verifying the CalDAV endpoint..."
# The configuration above is worthless if the server itself is broken (a
# root-owned config.php or data file will make every request 500).  Fail loudly
# here rather than leaving it for the test suite to discover.
for i in $(seq 1 30); do
    HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' -u "$TEST_USER:$TEST_PASSWORD" \
        "http://localhost:${NEXTCLOUD_PORT}/remote.php/dav/" || echo 000)
    case "$HTTP_CODE" in
        2*|3*)
            echo "✓ CalDAV endpoint answers HTTP $HTTP_CODE"
            break
            ;;
    esac
    if [ "$i" -eq 30 ]; then
        echo "✗ CalDAV endpoint answers HTTP $HTTP_CODE — this Nextcloud is broken"
        exit 1
    fi
    sleep 1
done

echo ""
echo "✓ Nextcloud setup complete!"
echo ""
echo "Credentials:"
echo "  Admin: admin / admin"
echo "  Test user: $TEST_USER / $TEST_PASSWORD"
echo "  Scheduling users: user1/testpass1, user2/testpass2, user3/testpass3"
echo "  CalDAV URL: http://localhost:${NEXTCLOUD_PORT}/remote.php/dav"
echo ""
