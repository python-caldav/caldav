#!/bin/bash
# Stop script for Baikal test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping Baikal and removing volumes..."
docker-compose down -v

echo "✓ Baikal stopped and volumes removed"
