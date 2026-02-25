#!/bin/bash
# Stop script for Zimbra CalDAV test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping Zimbra and removing volumes..."
docker-compose down -v

echo "Zimbra stopped and volumes removed"
