#!/bin/bash
# Stop script for Nextcloud test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping Nextcloud (data will be preserved in volume)..."
docker-compose stop

echo "✓ Nextcloud stopped"
echo ""
echo "To remove all data: docker-compose down -v"
