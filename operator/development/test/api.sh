#!/usr/bin/env bash
#
# Run Python API server tests
#
# Tests the API server codebase (api/app) including unit tests and integration tests.
# Unit tests are fast and don't require external dependencies.
# Integration tests require database to be running.
#
# Usage:
#   ./scripts/development/test/api.sh              # Run all API tests
#   ./scripts/development/test/api.sh -v           # Verbose output
#   ./scripts/development/test/api.sh -k datetime  # Run tests matching 'datetime'
#   ./scripts/development/test/api.sh --quick      # Skip coverage report
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
        --quick|-q)
            QUICK_MODE=true
            shift
            ;;
        *)
            PYTEST_ARGS+=("$1")
            shift
            ;;
    esac
done

echo -e "${BLUE}🐍 Running Python API tests${NC}"
echo ""

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Run: python3 -m venv venv${NC}"
    exit 1
fi

source venv/bin/activate

# Currently we don't have pytest markers set up yet, so we'll exclude
# integration test directories that require database
EXCLUDE_PATTERNS=(
    "--ignore=tests/api/"
    "--ignore=tests/test_synonym_detector.py"
    "--ignore=tests/test_vocabulary_manager_integration.py"
    "--ignore=tests/test_phase3_vocabulary_graph.py"
    "--ignore=tests/test_query_linter.py"
    "--ignore=tests/manual/"
)

# Run tests
if [ "$QUICK_MODE" = true ]; then
    # Quick mode: no coverage
    echo -e "${BLUE}Running unit tests (quick mode)...${NC}"
    python -m pytest tests/ \
        "${EXCLUDE_PATTERNS[@]}" \
        -v --tb=short \
        "${PYTEST_ARGS[@]}"
else
    # Full mode: with coverage
    echo -e "${BLUE}Running unit tests with coverage...${NC}"
    python -m pytest tests/ \
        "${EXCLUDE_PATTERNS[@]}" \
        --cov=api/app \
        --cov-report=term-missing \
        --cov-report=html:htmlcov/unit \
        -v --tb=short \
        "${PYTEST_ARGS[@]}"

    echo ""
    echo -e "${GREEN}✅ Tests complete${NC}"
    echo -e "${BLUE}📊 Coverage report: htmlcov/unit/index.html${NC}"
fi

echo ""
echo -e "${GREEN}✅ Python API tests passed${NC}"
