#!/bin/bash
# Stop script for Apple CalendarServer (CCS) test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping CCS and removing volumes..."
docker-compose down -v

echo "CCS stopped and volumes removed"
