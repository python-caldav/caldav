#!/bin/bash
# Stop script for Cyrus IMAP test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping Cyrus (data will be preserved in volumes)..."
docker-compose stop

echo "✓ Cyrus stopped"
echo ""
echo "To remove all data: docker-compose down -v"
