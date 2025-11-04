#!/usr/bin/env bash
#
# Run datetime linter (ADR-056)
#
# This script checks for unsafe datetime patterns across the API codebase.
# Detects: datetime.utcnow(), datetime.now(), datetime.fromtimestamp() without tz
#
# Usage:
#   ./scripts/development/test/lint-datetime.sh              # Lint entire src/api
#   ./scripts/development/test/lint-datetime.sh --verbose    # Show violations
#   ./scripts/development/test/lint-datetime.sh --strict     # Exit 1 on violations
#   ./scripts/development/test/lint-datetime.sh --path src/api/lib/auth.py  # Specific file
#
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Linting datetime usage (ADR-056)${NC}"
echo ""

# Check if linter exists
if [ ! -f "scripts/lint_datetimes.py" ]; then
    echo -e "${RED}❌ Linter not found: scripts/lint_datetimes.py${NC}"
    exit 1
fi

# Run linter with all arguments passed through
python3 scripts/lint_datetimes.py "$@"

# Capture exit code
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Datetime linting passed${NC}"
else
    echo ""
    echo -e "${YELLOW}⚠️  Datetime violations found (see ADR-056 for migration guide)${NC}"
fi

exit $EXIT_CODE
