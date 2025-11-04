#!/usr/bin/env bash
#
# Run code quality linters
#
# Runs all linters across the codebase to detect code quality issues.
# Currently includes:
#   - Datetime linter (ADR-056): Unsafe datetime patterns
#   - (Future: Query safety linter, ADR-048)
#   - (Future: General code quality linters)
#
# Usage:
#   ./scripts/development/test/lint.sh              # Run all linters
#   ./scripts/development/test/lint.sh --verbose    # Show violations
#   ./scripts/development/test/lint.sh --strict     # Exit 1 on violations
#
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Running code quality linters${NC}"
echo ""

# Track overall pass/fail
OVERALL_EXIT_CODE=0

# Run datetime linter
echo -e "${BLUE}Datetime linter (ADR-056)...${NC}"
if [ -f "src/testing/linters/datetime_linter.py" ]; then
    python3 -m src.testing.linters.datetime_linter "$@"
    DATETIME_EXIT=$?
    if [ $DATETIME_EXIT -ne 0 ]; then
        OVERALL_EXIT_CODE=1
    fi
    echo ""
else
    echo -e "${YELLOW}⚠️  Datetime linter not found, skipping${NC}"
    echo ""
fi

# Future: Add more linters here
# echo -e "${BLUE}Query safety linter (ADR-048)...${NC}"
# python3 -m src.testing.linters.query_linter "$@"

# Summary
if [ $OVERALL_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All linters passed${NC}"
else
    echo -e "${YELLOW}⚠️  Some linters found issues${NC}"
fi

exit $OVERALL_EXIT_CODE
