#!/bin/bash
# Quick start script for Nextcloud test server
#
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting Nextcloud CalDAV server..."
docker-compose up -d

echo ""
echo "Waiting for Nextcloud to initialize (this may take a minute)..."
./setup_nextcloud.sh

echo "To stop Nextcloud: ./stop.sh"
echo "To view logs: docker-compose logs -f nextcloud"
