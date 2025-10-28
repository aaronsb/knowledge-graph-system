#!/usr/bin/env bash
#
# build-api.sh - Build API server
#
# Status: PARTIAL - Uses existing setup
#

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "Building API server..."

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
  echo "  Creating Python venv..."
  python3 -m venv venv
fi

# Activate and install dependencies
source venv/bin/activate
pip install -q -r requirements.txt

echo "✓ API server built (Python dependencies installed)"
echo "  Note: Docker image build not yet implemented"

# Future: Build Docker image
# docker build -f build/docker/api.Dockerfile -t kg-api:local .

exit 0
