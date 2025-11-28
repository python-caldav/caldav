#!/bin/bash
# Stop script for Baikal test server
#
# Usage: ./stop.sh [--clean]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ "$1" = "--clean" ] || [ "$1" = "-c" ]; then
    echo "Stopping Baikal and removing all data..."
    docker-compose down -v
    echo "✓ Baikal stopped and all data removed"
else
    echo "Stopping Baikal (data will be preserved)..."
    docker-compose down
    echo "✓ Baikal stopped"
    echo ""
    echo "To remove all data: ./stop.sh --clean"
fi
