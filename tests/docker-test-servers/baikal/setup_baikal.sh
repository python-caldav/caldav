#!/bin/bash
# Setup script for Baikal CalDAV server for testing.
#
# Baikal is pre-configured via the committed Specific/ directory which contains
# a pre-seeded db.sqlite with testuser and user1-user3 for scheduling tests.
# This script verifies connectivity and re-seeds users if needed (e.g. if the
# DB was replaced or users were deleted).

set -e

CONTAINER_NAME="baikal-test"
BAIKAL_URL="${BAIKAL_URL:-http://localhost:8800}"
DB_PATH="/var/www/baikal/Specific/db/db.sqlite"
REALM="BaikalDAV"

echo "Waiting for Baikal to be ready..."
max_attempts=30
for i in $(seq 1 $max_attempts); do
    if curl -sf "$BAIKAL_URL/" -o /dev/null 2>/dev/null; then
        echo "✓ Baikal is ready"
        break
    fi
    if [ $i -eq $max_attempts ]; then
        echo "✗ Baikal did not become ready in time"
        exit 1
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "Seeding test users (idempotent)..."

add_user() {
    local username="$1"
    local password="$2"
    local email="$3"
    local displayname="$4"
    local ha1
    ha1=$(python3 -c "import hashlib; print(hashlib.md5('${username}:${REALM}:${password}'.encode()).hexdigest())")
    docker exec "$CONTAINER_NAME" sqlite3 "$DB_PATH" \
        "INSERT OR IGNORE INTO users (username, digesta1) VALUES ('${username}', '${ha1}');
         INSERT OR IGNORE INTO principals (uri, email, displayname) VALUES ('principals/${username}', '${email}', '${displayname}');"
    echo "  ${username}: OK"
}

add_user "testuser"  "testpass"  "testuser@example.com"  "Test User"
add_user "user1"     "testpass1" "user1@example.com"     "User 1"
add_user "user2"     "testpass2" "user2@example.com"     "User 2"
add_user "user3"     "testpass3" "user3@example.com"     "User 3"

echo ""
echo "✓ Baikal setup complete!"
echo ""
echo "Credentials:"
echo "  Test user: testuser / testpass"
echo "  Scheduling users: user1/testpass1, user2/testpass2, user3/testpass3"
echo "  CalDAV URL: $BAIKAL_URL/dav.php"
echo "  Auth type: Digest (realm: $REALM)"
echo ""
