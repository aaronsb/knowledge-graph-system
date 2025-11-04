#!/usr/bin/env bash
#
# Run React webapp tests
#
# Tests the React webapp codebase (viz-app/) including:
#   - Component tests
#   - Integration tests
#   - E2E tests (future)
#
# Usage:
#   ./scripts/development/test/webapp.sh              # Run all webapp tests
#   ./scripts/development/test/webapp.sh --watch      # Watch mode
#
# TODO: Implement once webapp has test suite
# Currently: Placeholder for future implementation
#

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}⚛️  Running React webapp tests${NC}"
echo ""

# Check if webapp directory exists
if [ ! -d "viz-app" ]; then
    echo -e "${YELLOW}⚠️  Webapp directory (viz-app/) not found${NC}"
    exit 1
fi

# Check if tests exist
if [ ! -f "viz-app/package.json" ]; then
    echo -e "${YELLOW}⚠️  Webapp package.json not found${NC}"
    exit 1
fi

# Navigate to webapp directory
cd viz-app

# Check if test script exists
if ! npm run | grep -q "test"; then
    echo -e "${YELLOW}⚠️  No test script configured in package.json${NC}"
    echo -e "${YELLOW}   Add test script to viz-app/package.json:${NC}"
    echo -e "${YELLOW}   \"scripts\": { \"test\": \"jest\" or \"vitest\" }${NC}"
    cd ..
    exit 0
fi

# Run tests
echo -e "${BLUE}Running webapp tests...${NC}"
npm test -- "$@"

# Return to repo root
cd ..

echo ""
echo -e "${GREEN}✅ React webapp tests passed${NC}"
