#!/bin/bash
# Start script for Bedework CalDAV test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting Bedework CalDAV server..."
docker-compose up -d

echo ""
echo "Waiting for Bedework to initialize (this may take up to 2 minutes)..."
timeout=120
elapsed=0
while [ $elapsed -lt $timeout ]; do
    if curl -f http://localhost:8804/bedework/ >/dev/null 2>&1; then
        echo "✓ Bedework is ready!"
        echo ""
        echo "CalDAV endpoint: http://localhost:8804/ucaldav/user/vbede/"
        echo "Username: vbede"
        echo "Password: bedework"
        echo ""
        echo "To stop Bedework: ./stop.sh"
        echo "To view logs: docker-compose logs -f bedework"
        exit 0
    fi
    sleep 5
    elapsed=$((elapsed + 5))
    echo -n "."
done

echo ""
echo "✗ Bedework did not start within ${timeout}s"
echo "Check logs with: docker-compose logs bedework"
exit 1
