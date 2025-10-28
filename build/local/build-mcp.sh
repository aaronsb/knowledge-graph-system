#!/usr/bin/env bash
#
# build-mcp.sh - Build MCP server
#
# Status: FUNCTIONAL - Shares build with CLI
#

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT/client"

echo "Building MCP server..."

# MCP shares build process with CLI
if [ ! -f "dist/mcp-server.js" ]; then
  echo "  Running CLI build (includes MCP)..."
  npm run build > /dev/null 2>&1
fi

echo "✓ MCP server built successfully"
echo "  Artifacts: client/dist/mcp-server.js"

exit 0
