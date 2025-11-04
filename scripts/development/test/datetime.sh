#!/usr/bin/env bash
#
# Run datetime utilities tests
#
# This script runs the ADR-056 datetime_utils test suite with coverage reporting.
# These are pure unit tests with no external dependencies.
#
# Usage:
#   ./scripts/development/test/datetime.sh           # Run tests with coverage
#   ./scripts/development/test/datetime.sh -v        # Verbose output
#   ./scripts/development/test/datetime.sh --quick   # Skip coverage report
#
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
QUICK_MODE=false
PYTEST_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        *)
            PYTEST_ARGS+=("$1")
            shift
            ;;
    esac
done

echo -e "${BLUE}🧪 Running datetime utilities tests (ADR-056)${NC}"
echo ""

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Run: python3 -m venv venv${NC}"
    exit 1
fi

source venv/bin/activate

# Run tests
if [ "$QUICK_MODE" = true ]; then
    # Quick mode: no coverage
    echo -e "${BLUE}Running tests (quick mode)...${NC}"
    python -m pytest tests/test_datetime_utils.py -v --tb=short "${PYTEST_ARGS[@]}"
else
    # Full mode: with coverage
    echo -e "${BLUE}Running tests with coverage...${NC}"
    python -m pytest tests/test_datetime_utils.py \
        --cov=src/api/lib/datetime_utils \
        --cov-report=term-missing \
        --cov-report=html:htmlcov/datetime_utils \
        -v --tb=short \
        "${PYTEST_ARGS[@]}"

    echo ""
    echo -e "${GREEN}✅ Tests complete${NC}"
    echo -e "${BLUE}📊 Coverage report: htmlcov/datetime_utils/index.html${NC}"
fi

echo ""
echo -e "${GREEN}✅ All datetime_utils tests passed${NC}"
