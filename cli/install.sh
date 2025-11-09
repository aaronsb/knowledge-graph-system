#!/bin/bash
#
# Install kg CLI to user-local bin directory (~/.local/bin/)
# No sudo required - user-scope installation
#

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

INSTALL_DIR="${HOME}/.local"
BIN_DIR="${INSTALL_DIR}/bin"

echo -e "${BLUE}📦 Installing Knowledge Graph CLI (kg) to user-local directory...${NC}"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ node not found${NC}"
    echo "  Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo -e "${RED}✗ npm not found${NC}"
    echo "  Please install npm (usually comes with Node.js)"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo -e "${YELLOW}⚠️  Warning: Node.js version $NODE_VERSION detected${NC}"
    echo "  Node.js 18+ is recommended"
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo ""

# Check if ~/.local/bin exists, create if not
if [ ! -d "$BIN_DIR" ]; then
    echo "Creating ${BIN_DIR}..."
    mkdir -p "$BIN_DIR"
fi

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":${BIN_DIR}:"* ]]; then
    echo -e "${YELLOW}⚠️  Warning: ${BIN_DIR} is not in your PATH${NC}"
    echo ""
    echo "Add this to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
    echo "  export PATH=\"\${HOME}/.local/bin:\${PATH}\""
    echo ""
fi

# Install npm dependencies if needed
if [ ! -d "node_modules" ] || [ ! -f "node_modules/.package-lock.json" ]; then
    echo -e "${BLUE}📥 Installing npm dependencies...${NC}"
    npm install
    echo -e "${GREEN}✓ Dependencies installed${NC}"
    echo ""
else
    echo -e "${GREEN}✓ Dependencies already installed${NC}"
    echo ""
fi

# Clean previous build
if [ -d "dist" ]; then
    echo "Cleaning previous build..."
    npm run clean
fi

# Build TypeScript
echo -e "${BLUE}🔨 Building TypeScript client...${NC}"
if ! npm run build; then
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
fi

# Verify build artifacts exist
if [ ! -f "dist/index.js" ] || [ ! -f "dist/mcp-server.js" ]; then
    echo -e "${RED}✗ Build artifacts missing${NC}"
    echo "  Expected dist/index.js and dist/mcp-server.js"
    exit 1
fi

echo -e "${GREEN}✓ Build successful${NC}"
echo ""

# Install to user-local prefix
echo -e "${BLUE}📦 Installing to ${INSTALL_DIR}...${NC}"
npm install -g --prefix "$INSTALL_DIR"

# Verify installation
if [ ! -f "${BIN_DIR}/kg" ]; then
    echo -e "${RED}✗ Installation failed${NC}"
    echo "  Expected ${BIN_DIR}/kg but not found"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Installation complete!${NC}"
echo ""
echo -e "The 'kg' command is now available at: ${GREEN}${BIN_DIR}/kg${NC}"
echo -e "The 'kg-mcp-server' command is also available for MCP integration"
echo ""
echo "Test with:"
echo -e "  ${BLUE}kg --version${NC}"
echo -e "  ${BLUE}kg health${NC}"
echo ""
echo -e "${YELLOW}📝 Note for AI coding agents:${NC}"
echo "If you modified the MCP server (mcp-server.ts or formatters), the user needs to"
echo "restart Claude Desktop (or the MCP client) to pick up the changes."
echo ""
