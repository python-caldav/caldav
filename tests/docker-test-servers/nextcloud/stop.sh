#!/bin/bash
# Stop script for Nextcloud test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping Nextcloud and removing volumes..."
docker-compose down -v

echo "✓ Nextcloud stopped and volumes removed"
