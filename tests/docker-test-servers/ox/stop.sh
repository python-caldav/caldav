#!/bin/bash
# Stop OX App Suite CalDAV test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping OX App Suite and removing volumes..."
docker-compose down -v

echo "OX App Suite stopped."
