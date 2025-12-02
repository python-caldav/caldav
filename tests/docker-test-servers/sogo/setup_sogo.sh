#!/bin/bash
# Setup script for SOGo groupware test server

set -e

CONTAINER_NAME="sogo-test"
TEST_USER="testuser"
TEST_PASSWORD="testpass"

echo "Waiting for SOGo server to be ready..."
max_attempts=30
for i in $(seq 1 $max_attempts); do
    if curl -s http://localhost:8803/SOGo/ 2>/dev/null | grep -q .; then
        echo "✓ SOGo HTTP server is ready"
        break
    fi
    if [ $i -eq $max_attempts ]; then
        echo "✗ SOGo server did not become ready in time"
        exit 1
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "Verifying CalDAV access..."
# Test CalDAV access with pre-created user using PROPFIND with Depth header
max_caldav_attempts=60  # 2 minutes at 2s intervals
for i in $(seq 1 $max_caldav_attempts); do
    if curl -s -X PROPFIND -H "Depth: 0" -u ${TEST_USER}:${TEST_PASSWORD} http://localhost:8803/SOGo/dav/${TEST_USER}/Calendar/ 2>/dev/null | grep -qi "multistatus\|collection"; then
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
echo "✓ SOGo setup complete!"
echo ""
echo "Credentials:"
echo "  Test user: ${TEST_USER} / ${TEST_PASSWORD}"
echo "  CalDAV URL: http://localhost:8803/SOGo/dav/${TEST_USER}/Calendar/"
echo "  CardDAV URL: http://localhost:8803/SOGo/dav/${TEST_USER}/Contacts/"
echo "  Web interface: http://localhost:8803/SOGo/"
echo ""
