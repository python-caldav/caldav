#!/bin/bash
# Quick start script for Stalwart test server
#
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Creating and starting Stalwart container..."
docker-compose up -d

echo "Running setup (waits for HTTP readiness, creates domain and test user)..."
bash "$SCRIPT_DIR/setup_stalwart.sh"

echo ""
echo "Run tests from project root:"
echo "  cd ../../.."
echo "  TEST_STALWART=true pytest"
echo ""
echo "To stop Stalwart: ./stop.sh"
echo "To view logs: docker-compose logs -f stalwart"
