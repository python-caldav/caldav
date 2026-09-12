#!/bin/bash
# Stop script for the Bedework 3.10.3 test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping Bedework 3.10.3 and removing volumes..."
docker-compose down -v

echo "✓ Bedework 3.10.3 stopped and volumes removed"
