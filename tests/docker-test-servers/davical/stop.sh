#!/bin/bash
# Stop script for DAViCal test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping DAViCal and removing volumes..."
docker-compose down -v

echo "DAViCal stopped and volumes removed"
