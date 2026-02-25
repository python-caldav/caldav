#!/bin/bash
# Quick start script for Davis test server
#
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Creating and starting Davis container..."
docker-compose up -d

# The DB doesn't exist yet on a fresh tmpfs, so the healthcheck will fail
# until setup_davis.sh creates and migrates it. We just wait for the
# container processes to be running, then run setup.
echo "Waiting for container to be running..."
sleep 3

echo "Running setup (creates DB, runs migrations, creates test user)..."
bash "$SCRIPT_DIR/setup_davis.sh"

echo ""
echo "Run tests from project root:"
echo "  cd ../../.."
echo "  TEST_DAVIS=true pytest"
echo ""
echo "To stop Davis: ./stop.sh"
echo "To view logs: docker-compose logs -f davis"
