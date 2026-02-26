#!/bin/bash
# Setup script for Stalwart test server.
# Creates the test domain and user via the management REST API.
#
# Stalwart requires:
#   1. A domain principal before a user can be created with that email.
#   2. A user principal with a plain-text secret (Stalwart hashes it internally).
#
# CalDAV is served at /dav/cal/<username>/ over plain HTTP on port 8080.

set -e

CONTAINER_NAME="stalwart-test"
HOST_PORT="${STALWART_PORT:-8809}"
ADMIN_USER="admin"
ADMIN_PASSWORD="adminpass"
DOMAIN="example.org"
TEST_USER="${STALWART_USERNAME:-testuser}"
TEST_PASSWORD="${STALWART_PASSWORD:-testpass}"
API_BASE="http://localhost:${HOST_PORT}/api"

api_post() {
    local endpoint="$1"
    local body="$2"
    curl -s -X POST "${API_BASE}${endpoint}" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -u "${ADMIN_USER}:${ADMIN_PASSWORD}" \
        -d "${body}"
}

echo "Waiting for Stalwart HTTP endpoint to be ready..."
max_attempts=60
for i in $(seq 1 $max_attempts); do
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${HOST_PORT}/" 2>/dev/null | grep -q "200"; then
        echo "Stalwart is ready"
        break
    fi
    if [ $i -eq $max_attempts ]; then
        echo "Stalwart did not start in time"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
        exit 1
    fi
    echo -n "."
    sleep 1
done

echo ""
echo "Creating domain '${DOMAIN}'..."
RESULT=$(api_post "/principal" "{\"type\": \"domain\", \"name\": \"${DOMAIN}\"}")
if echo "$RESULT" | grep -q '"error"'; then
    if echo "$RESULT" | grep -q '"fieldAlreadyExists"'; then
        echo "Domain already exists (OK)"
    else
        echo "Warning: domain creation returned: $RESULT"
    fi
fi

echo "Creating test user '${TEST_USER}'..."
RESULT=$(api_post "/principal" "{
    \"type\": \"individual\",
    \"name\": \"${TEST_USER}\",
    \"secrets\": [\"${TEST_PASSWORD}\"],
    \"emails\": [\"${TEST_USER}@${DOMAIN}\"],
    \"roles\": [\"user\"]
}")
if echo "$RESULT" | grep -q '"error"'; then
    if echo "$RESULT" | grep -q '"fieldAlreadyExists"'; then
        echo "User already exists (OK)"
    else
        echo "Error creating user: $RESULT"
        exit 1
    fi
else
    echo "User created: $RESULT"
fi

echo ""
echo "Verifying CalDAV access..."
max_caldav_attempts=15
for i in $(seq 1 $max_caldav_attempts); do
    RESPONSE=$(curl -s -X PROPFIND \
        -H "Depth: 0" \
        -u "${TEST_USER}:${TEST_PASSWORD}" \
        "http://localhost:${HOST_PORT}/dav/cal/${TEST_USER}/" 2>/dev/null)
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
echo "Stalwart setup complete!"
echo ""
echo "Credentials:"
echo "  Admin:     ${ADMIN_USER} / ${ADMIN_PASSWORD}  (web UI: http://localhost:${HOST_PORT})"
echo "  Test user: ${TEST_USER} / ${TEST_PASSWORD}"
echo "  CalDAV URL: http://localhost:${HOST_PORT}/dav/cal/${TEST_USER}/"
