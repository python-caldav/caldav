#!/bin/bash
# Setup script for Cyrus IMAP test server with CalDAV support

set -e

CONTAINER_NAME="cyrus-test"
TEST_USER="user1"  # Use pre-created user (user1-user5 are created automatically)
TEST_PASSWORD="x"  # Cyrus test server uses 'x' as default password

echo "Waiting for Cyrus server to be ready..."
max_attempts=30
for i in $(seq 1 $max_attempts); do
    # Accept any HTTP response (including 404) as a sign that the server is up
    if curl -s http://localhost:8802/ 2>/dev/null | grep -q .; then
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
echo "Verifying CalDAV access..."
# Test CalDAV access with pre-created user using PROPFIND
# Cyrus CalDAV can take additional time to initialize after HTTP is ready
max_caldav_attempts=60  # 2 minutes at 2s intervals
for i in $(seq 1 $max_caldav_attempts); do
    if curl -s -X PROPFIND -u ${TEST_USER}:${TEST_PASSWORD} http://localhost:8802/dav/calendars/user/${TEST_USER}/ 2>/dev/null | grep -q "multistatus"; then
        echo "✓ CalDAV is accessible"
        break
    fi
    if [ $i -eq $max_caldav_attempts ]; then
        echo "Warning: CalDAV access test failed after ${max_caldav_attempts} attempts, but continuing..."
        break
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "✓ Cyrus setup complete!"
echo ""
echo "Credentials:"
echo "  Test user: ${TEST_USER} / ${TEST_PASSWORD}"
echo "  CalDAV URL: http://localhost:8802/dav/calendars/user/${TEST_USER}"
echo "  CardDAV URL: http://localhost:8802/dav/addressbooks/user/${TEST_USER}"
echo ""
