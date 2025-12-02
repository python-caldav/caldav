#!/bin/bash
# Stop script for Cyrus IMAP test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping Cyrus and removing volumes..."
docker-compose down -v

echo "✓ Cyrus stopped and volumes removed"
