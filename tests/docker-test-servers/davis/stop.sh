#!/bin/bash
# Stop script for Davis test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping Davis and removing volumes..."
docker-compose down -v

echo "Davis stopped and volumes removed"
