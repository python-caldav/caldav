#!/bin/bash
# Quick start script for Baikal test server
#
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting Baikal CalDAV server..."
docker-compose up -d

echo ""
echo "Waiting for Baikal to be ready..."
timeout 60 bash -c 'until curl -f http://localhost:8800/ 2>/dev/null; do echo -n "."; sleep 2; done' || {
    echo ""
    echo "Error: Baikal did not become ready in time"
    echo "Check logs with: docker-compose logs baikal"
    exit 1
}

echo ""
echo "✓ Baikal is ready!"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:8800 in your browser"
echo "2. Complete the initial setup wizard"
echo "3. Create a test user (recommended: testuser/testpass)"
echo "4. Run tests from project root:"
echo "   cd ../../.."
echo "   export BAIKAL_URL=http://localhost:8800"
echo "   export BAIKAL_USERNAME=testuser"
echo "   export BAIKAL_PASSWORD=testpass"
echo "   pytest"
echo ""
echo "To stop Baikal: ./stop.sh"
echo "To view logs: docker-compose logs -f baikal"
