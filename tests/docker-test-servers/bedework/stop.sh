#!/bin/bash
# Stop script for Bedework test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping Bedework and removing volumes..."
docker-compose down -v

echo "✓ Bedework stopped and volumes removed"
