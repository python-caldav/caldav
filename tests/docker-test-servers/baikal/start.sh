#!/bin/bash
# Quick start script for Baikal test server with pre-configuration
#
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting Baikal CalDAV server..."
docker-compose up -d

echo "Waiting for container to start..."
sleep 3

echo "Copying pre-configured files into container..."
docker cp Specific/. baikal-test:/var/www/baikal/Specific/

echo "Restarting Baikal to apply configuration..."
docker restart baikal-test

echo ""
echo "Waiting for Baikal to be ready..."
sleep 5
timeout 60 bash -c 'until curl -f http://localhost:8800/dav.php/ 2>/dev/null; do echo -n "."; sleep 2; done' || {
    echo ""
    echo "Error: Baikal did not become ready in time"
    echo "Check logs with: docker-compose logs baikal"
    exit 1
}

echo ""
echo "✓ Baikal is ready and pre-configured!"
echo ""
echo "Pre-configured credentials:"
echo "  Admin: admin / admin"
echo "  Test user: testuser / testpass"
echo "  CalDAV URL: http://localhost:8800/dav.php/"
echo ""
echo "Run tests from project root:"
echo "  cd ../../.."
echo "  export BAIKAL_URL=http://localhost:8800"
echo "  export BAIKAL_USERNAME=testuser"
echo "  export BAIKAL_PASSWORD=testpass"
echo "  pytest"
echo ""
echo "To stop Baikal: ./stop.sh"
echo "To view logs: docker-compose logs -f baikal"
