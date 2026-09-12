#!/bin/bash
# Start the Bedework 5 CalDAV test server.
#
# The Docker image must be built first:
#   ./build.sh
#
# The container starts four processes (apacheds, h2, opensearch, wildfly) and
# builds its opensearch indexes on every start, which takes a few minutes.
#
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! docker image inspect bedework-caldav-test >/dev/null 2>&1; then
    echo "ERROR: Docker image 'bedework-caldav-test' not found."
    echo "Please build it first with:  ./build.sh"
    exit 1
fi

echo "Starting Bedework 5 container (startup takes a few minutes)..."
docker-compose up -d

echo "Waiting for Bedework to finish deploying..."
for i in $(seq 1 90); do
    if curl -sf -o /dev/null -X PROPFIND -H "Depth: 0" \
            -u vbede:bedework "http://localhost:8811/ucaldav/user/vbede/"; then
        echo ""
        echo "Bedework is ready."
        break
    fi
    if ! docker ps -q -f name=bedework5-test | grep -q .; then
        echo "ERROR: Bedework container stopped unexpectedly."
        docker-compose logs --tail=40 bedework
        exit 1
    fi
    if [ "$i" -eq 90 ]; then
        echo ""
        echo "Timeout waiting for Bedework to deploy."
        docker-compose logs --tail=40 bedework
        exit 1
    fi
    echo -n "."
    sleep 5
done

echo ""
echo "Bedework 5 is running on http://localhost:8811/"
echo "  CalDAV: http://localhost:8811/ucaldav/user/vbede/"
echo "  User:   vbede / bedework"
echo ""
echo "Run tests from project root:"
echo "  cd ../../.."
echo "  pytest tests/test_caldav.py -k Bedework -v"
echo ""
echo "To stop: ./stop.sh"
echo "To view logs: docker-compose logs -f bedework"
