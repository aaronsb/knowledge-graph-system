#!/bin/bash
set -e

# Colors for output
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}📂 Knowledge Graph System - Restore${NC}"
echo "======================================="
echo ""
echo "Launching Python restore tool..."
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "✗ Python virtual environment not found"
    echo "  Run: ./scripts/setup.sh"
    exit 1
fi

# Activate venv and run Python restore tool
source venv/bin/activate

# Pass all arguments to Python tool
python -m src.admin.restore "$@"
