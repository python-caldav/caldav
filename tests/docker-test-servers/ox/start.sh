#!/bin/bash
# Start OX App Suite CalDAV test server.
#
# The Docker image must be built first:
#   ./build.sh
#
# OX initialises its database and registers all services on first start,
# which takes 2-3 minutes. Subsequent starts of the same container are faster,
# but since we use tmpfs volumes the container always starts fresh.
#
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! docker image inspect ox-caldav-test >/dev/null 2>&1; then
    echo "ERROR: Docker image 'ox-caldav-test' not found."
    echo "Please build it first with:  ./build.sh"
    exit 1
fi

echo "Starting OX App Suite container (first-run initialisation takes ~3 minutes)..."
docker-compose up -d

echo "Waiting for OX to finish initialising..."
for i in $(seq 1 60); do
    if docker logs ox-test 2>&1 | grep -q "OX App Suite is ready"; then
        echo "OX App Suite is ready."
        break
    fi
    if ! docker ps -q -f name=ox-test | grep -q .; then
        echo "ERROR: OX container stopped unexpectedly."
        docker-compose logs --tail=40 ox
        exit 1
    fi
    if [ "$i" -eq 60 ]; then
        echo "Timeout waiting for OX App Suite to initialise."
        docker-compose logs --tail=40 ox
        exit 1
    fi
    echo -n "."
    sleep 5
done
echo ""

echo "Verifying CalDAV endpoint..."
if curl -sf -o /dev/null -w "%{http_code}" -X PROPFIND \
        -u oxadmin:oxadmin "http://localhost:8810/caldav/" | grep -qE "207"; then
    echo "CalDAV is responding (207 Multi-Status)."
else
    echo "Warning: CalDAV endpoint did not respond as expected."
fi

echo ""
echo "OX App Suite is running on http://localhost:8810/"
echo "  CalDAV: http://localhost:8810/caldav/"
echo "  User:   oxadmin / oxadmin"
echo ""
echo "Run tests from project root:"
echo "  cd ../../.."
echo "  TEST_OX=true pytest tests/test_caldav.py -k OX -v"
echo ""
echo "To stop: ./stop.sh"
echo "To view logs: docker-compose logs -f ox"
