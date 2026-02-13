#!/bin/bash
# Setup script for Davis test server
# Creates a test user with CalDAV access.
#
# Davis uses sabre/dav which requires entries in both the 'users' and
# 'principals' tables. The digesta1 field is md5(username:realm:password).
#
# Since the container has no sqlite3 CLI, we use Symfony's dbal:run-sql
# and doctrine:migrations:migrate console commands instead.

set -e

CONTAINER_NAME="davis-test"
TEST_USER="testuser"
TEST_PASSWORD="testpass"
AUTH_REALM="SabreDAV"
CONSOLE="php /var/www/davis/bin/console"

run_sql() {
    docker exec "$CONTAINER_NAME" $CONSOLE dbal:run-sql "$1" 2>&1
}

echo "Waiting for Davis container to be running..."
max_attempts=30
for i in $(seq 1 $max_attempts); do
    if docker exec "$CONTAINER_NAME" true 2>/dev/null; then
        echo "Container is running"
        break
    fi
    if [ $i -eq $max_attempts ]; then
        echo "Container did not start in time"
        exit 1
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "Initializing SQLite database..."
# Create the DB file and ensure it's writable by all processes in the container
docker exec "$CONTAINER_NAME" touch /data/davis-database.db
docker exec "$CONTAINER_NAME" chmod 666 /data/davis-database.db
docker exec "$CONTAINER_NAME" chmod 777 /data/

echo "Running database migrations..."
docker exec "$CONTAINER_NAME" $CONSOLE doctrine:migrations:migrate --no-interaction 2>&1

echo ""
echo "Computing digest hash..."
DIGEST=$(echo -n "${TEST_USER}:${AUTH_REALM}:${TEST_PASSWORD}" | md5sum | awk '{print $1}')
echo "Digest: ${DIGEST}"

echo ""
echo "Creating test user in database..."
run_sql "INSERT INTO users (username, digesta1) VALUES ('${TEST_USER}', '${DIGEST}')"

echo "Creating principal entries..."
# sabre/dav requires principal entries for CalDAV to work
# The principals table has is_main and is_admin boolean columns
run_sql "INSERT INTO principals (uri, email, displayname, is_main, is_admin) VALUES ('principals/${TEST_USER}', '${TEST_USER}@example.com', 'Test User', 1, 0)"

# Calendar-proxy principals that sabre/dav expects for delegation
run_sql "INSERT INTO principals (uri, email, displayname, is_main, is_admin) VALUES ('principals/${TEST_USER}/calendar-proxy-read', NULL, NULL, 0, 0)"
run_sql "INSERT INTO principals (uri, email, displayname, is_main, is_admin) VALUES ('principals/${TEST_USER}/calendar-proxy-write', NULL, NULL, 0, 0)"

echo ""
echo "Verifying CalDAV access..."
max_caldav_attempts=15
for i in $(seq 1 $max_caldav_attempts); do
    RESPONSE=$(curl -s -X PROPFIND -H "Depth: 0" -u "${TEST_USER}:${TEST_PASSWORD}" http://localhost:8806/dav/ 2>/dev/null)
    if echo "$RESPONSE" | grep -qi "multistatus\|collection"; then
        echo "CalDAV is accessible"
        break
    fi
    if [ $i -eq $max_caldav_attempts ]; then
        echo "Warning: CalDAV access test failed after ${max_caldav_attempts} attempts"
        echo "Response: $RESPONSE"
        echo "Continuing anyway - the user may need to debug..."
        break
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "Davis setup complete!"
echo ""
echo "Credentials:"
echo "  Admin: admin / admin"
echo "  Test user: ${TEST_USER} / ${TEST_PASSWORD}"
echo "  CalDAV URL: http://localhost:8806/dav/"
