#!/bin/bash
# Setup script for DAViCal test server
# Creates a test user with CalDAV access via PostgreSQL.
#
# DAViCal stores users in the 'usr' table with passwords prefixed by '**'.
# Each user needs a corresponding entry in the 'principal' table.

set -e

DB_CONTAINER="davical-db"
DAVICAL_CONTAINER="davical-test"
DB_USER="davical_dba"
DB_NAME="davical"
TEST_USER="testuser"
TEST_PASSWORD="testpass"

run_sql() {
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" "$DB_NAME" -tAc "$1" 2>&1
}

echo "Waiting for DAViCal to be accessible..."
max_attempts=60
for i in $(seq 1 $max_attempts); do
    if curl -s -w "%{http_code}" "http://localhost:8805/caldav.php/" 2>/dev/null | grep -q "401"; then
        echo "DAViCal HTTP server is ready"
        break
    fi
    if [ $i -eq $max_attempts ]; then
        echo "DAViCal did not become ready in time"
        echo "Check logs with: docker-compose logs davical"
        exit 1
    fi
    echo -n "."
    sleep 3
done

create_user() {
    local username="$1"
    local password="$2"
    local fullname="$3"
    EXISTING=$(run_sql "SELECT username FROM usr WHERE username='${username}'")
    if [ -n "$EXISTING" ]; then
        echo "User '${username}' already exists, skipping creation"
    else
        run_sql "INSERT INTO usr (username, password, fullname, email) VALUES ('${username}', '**${password}', '${fullname}', '${username}@example.com')"
        echo "User '${username}' created"
    fi
    EXISTING_PRINCIPAL=$(run_sql "SELECT principal_id FROM principal p JOIN usr u ON p.user_no = u.user_no WHERE u.username='${username}'")
    if [ -n "$EXISTING_PRINCIPAL" ]; then
        echo "Principal for '${username}' already exists, skipping"
    else
        run_sql "INSERT INTO principal (type_id, user_no, displayname) SELECT 1, user_no, fullname FROM usr WHERE username='${username}'"
        echo "Principal for '${username}' created"
    fi
}

echo ""
echo "Creating test users..."
create_user "${TEST_USER}" "${TEST_PASSWORD}" "Test User"
create_user "user1" "testpass1" "User One"
create_user "user2" "testpass2" "User Two"
create_user "user3" "testpass3" "User Three"

echo ""
echo "Verifying CalDAV access..."
max_caldav_attempts=10
for i in $(seq 1 $max_caldav_attempts); do
    RESPONSE=$(curl -s -X PROPFIND -H "Depth: 0" -u "${TEST_USER}:${TEST_PASSWORD}" "http://localhost:8805/caldav.php/${TEST_USER}/" 2>/dev/null)
    if echo "$RESPONSE" | grep -qi "multistatus\|collection"; then
        echo "CalDAV is accessible"
        break
    fi
    if [ $i -eq $max_caldav_attempts ]; then
        echo "Warning: CalDAV access test failed after ${max_caldav_attempts} attempts"
        echo "Response: $RESPONSE"
        echo "Continuing anyway..."
        break
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "DAViCal setup complete!"
echo ""
echo "Credentials:"
echo "  Admin: admin / testpass"
echo "  Test user: ${TEST_USER} / ${TEST_PASSWORD}"
echo "  Scheduling users: user1/testpass1, user2/testpass2, user3/testpass3"
echo "  CalDAV URL: http://localhost:8805/caldav.php/${TEST_USER}/"
