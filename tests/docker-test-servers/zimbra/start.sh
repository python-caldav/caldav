#!/bin/bash
# Quick start script for Zimbra CalDAV test server
#
# WARNING: First run takes ~5-10 minutes (Zimbra configuration).
# The container requires ~6GB of RAM and runs in privileged mode.
#
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ZIMBRA_FQDN="zimbra-docker.zimbra.io"
ZIMBRA_DOMAIN="zimbra.io"

# Ensure hostname resolves to localhost (Zimbra nginx requires matching Host header)
if ! grep -q "$ZIMBRA_FQDN" /etc/hosts 2>/dev/null; then
    echo "Adding $ZIMBRA_FQDN to /etc/hosts (requires sudo)..."
    echo "127.0.0.1 $ZIMBRA_FQDN" | sudo tee -a /etc/hosts > /dev/null
fi

echo "Creating and starting Zimbra container..."
docker-compose up -d

echo "Waiting for Zimbra setup to complete (this may take up to 15 minutes on first run)..."
for i in $(seq 1 180); do
    if docker logs zimbra-test 2>&1 | grep -q "SETUP COMPLETE"; then
        echo "Zimbra setup is complete!"
        break
    fi
    if ! docker ps -q -f name=zimbra-test | grep -q .; then
        echo "ERROR: Zimbra container stopped unexpectedly"
        echo "Container logs (last 30 lines):"
        docker-compose logs --tail=30 zimbra
        exit 1
    fi
    if [ "$i" -eq 180 ]; then
        echo "Timeout waiting for Zimbra setup"
        echo "Container logs (last 50 lines):"
        docker-compose logs --tail=50 zimbra
        exit 1
    fi
    sleep 5
done

# Wait a bit for all services to stabilize
sleep 10

# Create test users (ignore errors if they already exist)
echo "Creating test users..."
docker exec zimbra-test su - zimbra -c "zmprov ca testuser@$ZIMBRA_DOMAIN testpass" 2>/dev/null || \
    echo "  testuser already exists (or creation failed)"
docker exec zimbra-test su - zimbra -c "zmprov ca testuser2@$ZIMBRA_DOMAIN testpass" 2>/dev/null || \
    echo "  testuser2 already exists (or creation failed)"

# Verify CalDAV is responding
echo "Verifying CalDAV endpoint..."
if curl -sk -o /dev/null -w "%{http_code}" -u "testuser@$ZIMBRA_DOMAIN:testpass" "https://$ZIMBRA_FQDN:8808/dav/" | grep -qE "200|207|301|302|401"; then
    echo "CalDAV is responding"
else
    echo "Warning: CalDAV endpoint not responding as expected"
    echo "Container logs (last 20 lines):"
    docker-compose logs --tail=20 zimbra
fi

echo ""
echo "Zimbra is running on https://$ZIMBRA_FQDN:8808/"
echo "  Users: testuser@$ZIMBRA_DOMAIN / testpass"
echo "         testuser2@$ZIMBRA_DOMAIN / testpass"
echo ""
echo "Run tests from project root:"
echo "  cd ../../.."
echo "  TEST_ZIMBRA=true pytest tests/test_caldav.py -k Zimbra -v"
echo ""
echo "To stop Zimbra: ./stop.sh"
echo "To view logs: docker-compose logs -f zimbra"
