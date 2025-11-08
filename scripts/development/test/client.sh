#!/usr/bin/env bash
#
# Run TypeScript CLI + MCP client tests
#
# Tests the TypeScript client codebase (client/) including:
#   - CLI command tests
#   - MCP server tool tests
#   - API client integration tests
#
# Usage:
#   ./scripts/development/test/client.sh              # Run all client tests
#   ./scripts/development/test/client.sh --watch      # Watch mode
#
# TODO: Implement once client has test suite
# Currently: Placeholder for future implementation
#

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}📘 Running TypeScript client tests${NC}"
echo ""

# Check if client directory exists
if [ ! -d "client" ]; then
    echo -e "${YELLOW}⚠️  Client directory not found${NC}"
    exit 1
fi

# Check if tests exist
if [ ! -f "client/package.json" ]; then
    echo -e "${YELLOW}⚠️  Client package.json not found${NC}"
    exit 1
fi

# Navigate to client directory
cd client

# Check if test script exists
if ! npm run | grep -q "test"; then
    echo -e "${YELLOW}⚠️  No test script configured in package.json${NC}"
    echo -e "${YELLOW}   Add test script to client/package.json:${NC}"
    echo -e "${YELLOW}   \"scripts\": { \"test\": \"jest\" or \"vitest\" }${NC}"
    cd ..
    exit 0
fi

# Run tests
echo -e "${BLUE}Running client tests...${NC}"
npm test -- "$@"

# Return to repo root
cd ..

echo ""
echo -e "${GREEN}✅ TypeScript client tests passed${NC}"
