#!/bin/bash
# Quick start script for Baikal test server with pre-configuration
#
# Usage: ./start.sh

## This logic is also sort of duplicated in the .github/workflows/test.yaml file

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Creating and starting container..."
docker-compose up -d

echo "Waiting for container to be fully started..."
sleep 2

echo "Copying pre-configured files into container (after tmpfs mounts are active)..."
# Use tar to preserve directory structure and permissions when copying to tmpfs
tar -C Specific -c . | docker exec -i baikal-test tar -C /var/www/baikal/Specific -x
tar -C config -c . | docker exec -i baikal-test tar -C /var/www/baikal/config -x

echo "Fixing permissions..."
docker exec baikal-test chown -R nginx:nginx /var/www/baikal/Specific /var/www/baikal/config
docker exec baikal-test chmod -R 770 /var/www/baikal/Specific

echo ""
echo "Waiting for Baikal to be ready..."
sleep 5
timeout 60 bash -c 'until curl -s -o /dev/null -w "%{http_code}" http://localhost:8800/dav.php/ | grep -q "^[234]"; do echo -n "."; sleep 2; done' || {
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
