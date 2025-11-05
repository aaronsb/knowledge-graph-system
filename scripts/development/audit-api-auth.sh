#!/usr/bin/env bash
################################################################################
# API Authentication Audit Tool
#
# Wrapper script that handles venv activation and runs the audit tool.
# Scans all FastAPI routes and identifies auth requirements.
#
# Usage:
#   ./scripts/development/audit-api-auth.sh [options]
#
# Options:
#   --verbose, -v           Show detailed breakdown of all endpoints
#   --format json|markdown  Export to file format (optional)
#   --output, -o PATH       Output file path
#   --help                  Show help message
#
# Examples:
#   ./scripts/development/audit-api-auth.sh
#   ./scripts/development/audit-api-auth.sh --verbose
#   ./scripts/development/audit-api-auth.sh --format=markdown --output=docs/testing/AUTH_AUDIT.md
################################################################################

set -e

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

# Show help if requested
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo -e "${BLUE}API Authentication Audit Tool${NC}"
    echo ""
    echo "Scans all FastAPI routes and identifies authentication requirements."
    echo ""
    echo -e "${GREEN}Usage:${NC}"
    echo "  ./scripts/development/audit-api-auth.sh [options]"
    echo ""
    echo -e "${GREEN}Options:${NC}"
    echo "  --verbose, -v           Show detailed breakdown of all endpoints"
    echo "  --format json|markdown  Export to file format (optional)"
    echo "  --output, -o PATH       Output file path"
    echo "  --help, -h              Show this help message"
    echo ""
    echo -e "${GREEN}Examples:${NC}"
    echo "  ./scripts/development/audit-api-auth.sh"
    echo "  ./scripts/development/audit-api-auth.sh --verbose"
    echo "  ./scripts/development/audit-api-auth.sh --format=json"
    echo "  ./scripts/development/audit-api-auth.sh --format=markdown --output=auth_audit.md"
    echo ""
    exit 0
fi

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Run: python3 -m venv venv${NC}"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check for required dependencies
if ! python3 -c "import tabulate" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Missing required package: tabulate${NC}"
    echo -e "${BLUE}Installing tabulate...${NC}"
    pip install tabulate
    echo ""
fi

# Run the Python audit script with all arguments passed through
python3 scripts/development/audit-api-auth.py "$@"
