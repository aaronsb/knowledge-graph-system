#!/usr/bin/env bash
#
# build-cli.sh - Build CLI tool
#
# Status: FUNCTIONAL - Uses existing client build
#

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT/client"

echo "Building CLI tool..."

# Install dependencies
if [ ! -d "node_modules" ]; then
  echo "  Installing npm dependencies..."
  npm install > /dev/null 2>&1
fi

# Build TypeScript
echo "  Compiling TypeScript..."
npm run build > /dev/null 2>&1

echo "✓ CLI tool built successfully"
echo "  Artifacts: client/dist/index.js"
echo "  Install globally: cd client && ./install.sh"

exit 0
