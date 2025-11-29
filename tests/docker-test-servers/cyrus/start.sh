#!/bin/bash
# Quick start script for Cyrus IMAP test server
#
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting Cyrus IMAP CalDAV server..."
docker-compose up -d

echo ""
echo "Waiting for Cyrus to initialize..."
./setup_cyrus.sh

echo "To stop Cyrus: ./stop.sh"
echo "To view logs: docker-compose logs -f cyrus"
