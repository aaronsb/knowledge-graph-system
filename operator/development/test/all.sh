#!/usr/bin/env bash
#
# Run all tests across entire stack
#
# Orchestrates test execution across all components:
#   - Python API server tests
#   - TypeScript CLI + MCP client tests (future)
#   - React webapp tests (future)
#   - Code quality linters
#
# Usage:
#   ./scripts/development/test/all.sh              # Run everything
#   ./scripts/development/test/all.sh --quick      # Skip coverage
#

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🌍 Running all tests across entire stack${NC}"
echo ""

# Track overall results
OVERALL_EXIT_CODE=0

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run Python API tests
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📦 Component: Python API Server${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
"$SCRIPT_DIR/api.sh" "$@"
if [ $? -ne 0 ]; then
    OVERALL_EXIT_CODE=1
fi
echo ""

# Run TypeScript client tests (future)
# echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
# echo -e "${BLUE}📦 Component: TypeScript CLI + MCP${NC}"
# echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
# "$SCRIPT_DIR/client.sh" "$@"
# if [ $? -ne 0 ]; then
#     OVERALL_EXIT_CODE=1
# fi
# echo ""

# Run React webapp tests (future)
# echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
# echo -e "${BLUE}📦 Component: React Webapp${NC}"
# echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
# "$SCRIPT_DIR/webapp.sh" "$@"
# if [ $? -ne 0 ]; then
#     OVERALL_EXIT_CODE=1
# fi
# echo ""

# Run linters
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔍 Code Quality Linters${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
"$SCRIPT_DIR/lint.sh" "$@"
if [ $? -ne 0 ]; then
    OVERALL_EXIT_CODE=1
fi
echo ""

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ $OVERALL_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed across entire stack${NC}"
else
    echo -e "${RED}❌ Some tests failed${NC}"
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

exit $OVERALL_EXIT_CODE
