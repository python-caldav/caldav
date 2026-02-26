#!/bin/bash
# Stop script for Stalwart test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping Stalwart and removing volumes..."
docker-compose down -v

echo "Stalwart stopped and volumes removed"
