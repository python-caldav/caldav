#!/bin/bash
# Setup script for Stalwart test server.
# Creates the test domain and user via the JMAP management API.
#
# Stalwart v0.16+ architecture:
#   - REST /api/ endpoints are gone; management is done via JMAP (POST /jmap).
#   - x:Domain/set creates a domain principal.
#   - x:Account/set creates a user account (name = local part, domainId = domain id).
#   - Authentication uses full email: testuser@example.org.
#   - CalDAV URL encodes the @ as %40: /dav/cal/testuser%40example.org/
#   - config.json (mounted read-only) points Stalwart at the SQLite database,
#     preventing bootstrap mode from activating.
#   - STALWART_RECOVERY_ADMIN pins the admin credential during bootstrap.
#
# Default passwords avoid zxcvbn's common-password blacklist ("testpass" is rejected).

set -e

CONTAINER_NAME="stalwart-test"
HOST_PORT="${STALWART_PORT:-8809}"
ADMIN_USER="admin"
ADMIN_PASSWORD="adminpass"
DOMAIN="example.org"
TEST_USER="${STALWART_USERNAME:-testuser}"
TEST_PASSWORD="${STALWART_PASSWORD:-testcaldav}"
JMAP_URL="http://localhost:${HOST_PORT}/jmap"

jmap_call() {
    local body="$1"
    curl -s -u "${ADMIN_USER}:${ADMIN_PASSWORD}" \
        -X POST "${JMAP_URL}" \
        -H "Content-Type: application/json" \
        -d "${body}"
}

echo "Waiting for Stalwart HTTP endpoint to be ready..."
max_attempts=60
for i in $(seq 1 $max_attempts); do
    # /dav/cal/ returns 401 once the database is initialised — no GitHub download needed.
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${HOST_PORT}/dav/cal/" 2>/dev/null | grep -q "401"; then
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
echo "Disabling password strength check for test environment..."
# Allow simple test passwords; zxcvbn by default rejects common words like "testpass".
RESULT=$(jmap_call '{
    "using": ["urn:ietf:params:jmap:core"],
    "methodCalls": [["x:Authentication/set", {
        "accountId": "d333333",
        "update": {"singleton": {"passwordMinStrength": "zero"}}
    }, "0"]]
}')
if echo "$RESULT" | grep -q '"updated"'; then
    echo "Password strength check disabled"
else
    echo "Warning: could not disable password strength check: $RESULT"
fi

echo ""
echo "Disabling rate limiting for test environment..."
# Stalwart applies HTTP rate limits by default; disable them to avoid 429s during tests.
# The Http object is a singleton with id "singleton". period is milliseconds (integer).
# max count per Stalwart validation is 1,000,000.  Try create first; if it already
# exists (primaryKeyViolation), update the singleton instead.
RATE_BODY='{"rateLimitAnonymous":{"count":1000000,"period":60000},"rateLimitAuthenticated":{"count":1000000,"period":60000}}'
RESULT=$(jmap_call "{
    \"using\": [\"urn:ietf:params:jmap:core\"],
    \"methodCalls\": [[\"x:Http/set\", {
        \"accountId\": \"d333333\",
        \"create\": {\"h1\": ${RATE_BODY}}
    }, \"0\"]]
}")
if echo "$RESULT" | grep -q '"primaryKeyViolation"'; then
    RESULT=$(jmap_call "{
        \"using\": [\"urn:ietf:params:jmap:core\"],
        \"methodCalls\": [[\"x:Http/set\", {
            \"accountId\": \"d333333\",
            \"update\": {\"singleton\": ${RATE_BODY}}
        }, \"0\"]]
    }")
fi
if echo "$RESULT" | grep -q '"notCreated"\|"notUpdated"\|"error"'; then
    echo "Warning: rate limit update returned: $RESULT"
else
    echo "Rate limiting disabled"
fi

echo ""
echo "Creating domain '${DOMAIN}'..."
RESULT=$(jmap_call "{
    \"using\": [\"urn:ietf:params:jmap:core\"],
    \"methodCalls\": [[\"x:Domain/set\", {
        \"accountId\": \"d333333\",
        \"create\": {\"d1\": {\"name\": \"${DOMAIN}\"}}
    }, \"0\"]]
}")
if echo "$RESULT" | grep -q '"created"'; then
    DOMAIN_ID=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['methodResponses'][0][1]['created']['d1']['id'])" 2>/dev/null)
    echo "Domain created (id=${DOMAIN_ID})"
elif echo "$RESULT" | grep -q '"alreadyExists"\|"primaryKeyViolation"'; then
    echo "Domain already exists, fetching id..."
    DOMAIN_ID=$(jmap_call '{"using":["urn:ietf:params:jmap:core"],"methodCalls":[["x:Domain/get",{"accountId":"d333333","ids":null},"0"]]}' | \
        python3 -c "import json,sys; l=json.load(sys.stdin)['methodResponses'][0][1]['list']; d=[x for x in l if x['name']=='${DOMAIN}']; print(d[0]['id'] if d else '')" 2>/dev/null)
    echo "Existing domain id=${DOMAIN_ID}"
else
    echo "Warning: domain creation returned: $RESULT"
    DOMAIN_ID=$(jmap_call '{"using":["urn:ietf:params:jmap:core"],"methodCalls":[["x:Domain/get",{"accountId":"d333333","ids":null},"0"]]}' | \
        python3 -c "import json,sys; l=json.load(sys.stdin)['methodResponses'][0][1]['list']; d=[x for x in l if x['name']=='${DOMAIN}']; print(d[0]['id'] if d else '')" 2>/dev/null)
fi

if [ -z "$DOMAIN_ID" ]; then
    echo "Error: could not determine domain id"
    exit 1
fi

create_user() {
    local username="$1"
    local password="$2"
    local result
    result=$(jmap_call "{
        \"using\": [\"urn:ietf:params:jmap:core\"],
        \"methodCalls\": [[\"x:Account/set\", {
            \"accountId\": \"d333333\",
            \"create\": {\"u1\": {
                \"@type\": \"User\",
                \"name\": \"${username}\",
                \"domainId\": \"${DOMAIN_ID}\",
                \"credentials\": {\"0\": {\"@type\": \"Password\", \"secret\": \"${password}\"}}
            }}
        }, \"0\"]]
    }")
    if echo "$result" | grep -q '"created"'; then
        echo "User '${username}@${DOMAIN}' created"
    elif echo "$result" | grep -q '"primaryKeyViolation"'; then
        echo "User '${username}@${DOMAIN}' already exists (OK)"
    else
        echo "Warning: user '${username}' creation returned: $result"
    fi
}

echo ""
echo "Creating test user '${TEST_USER}'..."
create_user "${TEST_USER}" "${TEST_PASSWORD}"

echo ""
echo "Creating additional users for RFC6638 scheduling tests..."
# Passwords avoid the common-word blacklist: "caldavtest{N}" passes, "testpass{N}" does not.
create_user "user1" "caldavtest1"
create_user "user2" "caldavtest2"
create_user "user3" "caldavtest3"

echo ""
echo "Verifying CalDAV access..."
# v0.16+: CalDAV path encodes the @ in the email address as %40.
CALDAV_PATH="/dav/cal/${TEST_USER}%40${DOMAIN}/"
max_caldav_attempts=15
for i in $(seq 1 $max_caldav_attempts); do
    RESPONSE=$(curl -s -X PROPFIND \
        -H "Depth: 0" \
        -u "${TEST_USER}@${DOMAIN}:${TEST_PASSWORD}" \
        "http://localhost:${HOST_PORT}${CALDAV_PATH}" 2>/dev/null)
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
echo "  Admin:     ${ADMIN_USER} / ${ADMIN_PASSWORD}  (web UI: http://localhost:${HOST_PORT}/admin/)"
echo "  Test user: ${TEST_USER}@${DOMAIN} / ${TEST_PASSWORD}"
echo "  CalDAV URL: http://localhost:${HOST_PORT}${CALDAV_PATH}"
