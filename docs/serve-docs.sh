#!/bin/bash
# Serve MkDocs documentation locally with automatic venv management
#
# This script:
# 1. Creates a Python virtual environment in docs/.venv (if needed)
# 2. Installs MkDocs and dependencies from docs/requirements.txt
# 3. Starts a local web server at http://127.0.0.1:8000
# 4. Auto-reloads when you edit documentation files
# 5. Cleans up the venv when you stop (Ctrl+C)
#
# The venv is isolated from your system Python and the main project venv.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$SCRIPT_DIR/.venv"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  MkDocs Documentation Server${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}This will:${NC}"
echo -e "  • Create a Python virtual environment (if needed)"
echo -e "  • Install MkDocs and Material theme"
echo -e "  • Start a local server at ${YELLOW}http://127.0.0.1:8001${NC}"
echo -e "  • Auto-reload when you save changes"
echo ""
echo -e "${CYAN}Location:${NC} $PROJECT_ROOT"
echo -e "${CYAN}Venv:${NC} $VENV_DIR"
echo ""

# Prompt to continue
read -p "$(echo -e ${YELLOW}"Continue? [y/N]: "${NC})" -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Aborted.${NC}"
    exit 0
fi

echo ""

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate venv
echo -e "${YELLOW}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

# Install/upgrade dependencies
echo -e "${YELLOW}Installing MkDocs dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r "$SCRIPT_DIR/requirements.txt"
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping server...${NC}"
    deactivate 2>/dev/null || true
    echo -e "${GREEN}✓ Server stopped${NC}"
}

# Register cleanup on exit
trap cleanup EXIT INT TERM

# Serve docs
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Server starting...${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}➜ Local:${NC}    ${CYAN}http://127.0.0.1:8001${NC}"
echo -e "${YELLOW}➜ Press Ctrl+C to stop${NC}"
echo ""

cd "$PROJECT_ROOT"
mkdocs serve --dev-addr 127.0.0.1:8001 \
  --watch docs/ \
  --watch mkdocs.yml \
  --livereload
