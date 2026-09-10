#!/bin/bash
# Build the Bedework 5 Docker image for CalDAV testing.
#
# This must be run manually before starting the test server.  Galleon pulls
# roughly a gigabyte of Maven artifacts, so the build takes a while.
#
# Usage: ./build.sh [--build-arg BW_VERSION=5.0.0] ...

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Building bedework-caldav-test image (this will take several minutes)..."
docker build -t bedework-caldav-test "$@" .

echo ""
echo "Build complete. You can now run ./start.sh"
