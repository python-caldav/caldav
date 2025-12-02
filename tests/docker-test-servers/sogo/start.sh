#!/bin/bash
# Start script for SOGo groupware test server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting SOGo groupware server..."
docker-compose up -d

echo ""
echo "Waiting for SOGo to initialize..."
./setup_sogo.sh

echo "To stop SOGo: ./stop.sh"
echo "To view logs: docker-compose logs -f sogo"
