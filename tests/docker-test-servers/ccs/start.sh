#!/bin/bash
# Quick start script for Apple CalendarServer (CCS) test server
#
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Creating and starting Apple CalendarServer container..."
docker-compose up -d

echo "Waiting for CCS to be healthy..."
for i in $(seq 1 60); do
    if docker inspect --format='{{.State.Health.Status}}' ccs-test 2>/dev/null | grep -q healthy; then
        echo "CCS is healthy!"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "Timeout waiting for CCS to become healthy"
        echo "Container logs:"
        docker-compose logs ccs
        exit 1
    fi
    sleep 2
done

# Verify CalDAV is responding
echo "Verifying CalDAV endpoint..."
if curl -s -o /dev/null -w "%{http_code}" -u user01:user01 -X PROPFIND -H "Depth: 0" http://localhost:8807/ | grep -q "207"; then
    echo "CalDAV is responding correctly"
else
    echo "Warning: CalDAV endpoint not responding as expected"
    echo "Container logs:"
    docker-compose logs ccs
fi

echo ""
echo "CCS is running on http://localhost:8807/"
echo "  Users: user01/user01, user02/user02, admin/admin"
echo ""
echo "Run tests from project root:"
echo "  cd ../../.."
echo "  TEST_CCS=true pytest"
echo ""
echo "To stop CCS: ./stop.sh"
echo "To view logs: docker-compose logs -f ccs"
