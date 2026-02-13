#!/bin/bash
# Quick start script for DAViCal test server
#
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Creating and starting DAViCal containers (PostgreSQL + DAViCal)..."
docker-compose up -d

echo "Waiting for DAViCal to be healthy (DB init takes ~60s)..."
timeout 180 bash -c 'until docker inspect --format="{{.State.Health.Status}}" davical-test 2>/dev/null | grep -q "healthy"; do echo -n "."; sleep 5; done' || {
    echo ""
    echo "Error: DAViCal did not become healthy in time"
    echo "Check logs with: docker-compose logs"
    exit 1
}
echo ""

echo "Running setup..."
bash "$SCRIPT_DIR/setup_davical.sh"

echo ""
echo "Run tests from project root:"
echo "  cd ../../.."
echo "  TEST_DAVICAL=true pytest"
echo ""
echo "To stop DAViCal: ./stop.sh"
echo "To view logs: docker-compose logs -f"
