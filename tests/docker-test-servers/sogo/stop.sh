#!/bin/bash
# Stop script for SOGo test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping SOGo and removing volumes..."
docker-compose down -v

echo "✓ SOGo stopped and volumes removed"
