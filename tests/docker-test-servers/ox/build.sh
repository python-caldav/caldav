#!/bin/bash
# Build the OX App Suite Docker image for CalDAV testing.
#
# This must be run manually before starting the test server.
# Building takes several minutes and downloads ~1.5GB of packages.
#
# Usage: ./build.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Building ox-caldav-test image (this will take several minutes)..."
docker build -t ox-caldav-test .

echo ""
echo "Build complete. You can now run ./start.sh"
