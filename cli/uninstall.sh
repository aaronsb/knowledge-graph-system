#!/bin/bash
#
# Uninstall kg CLI from user-local bin directory (~/.local/bin/)
# Reverses what install.sh does
#

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

INSTALL_DIR="${HOME}/.local"
BIN_DIR="${INSTALL_DIR}/bin"
LIB_DIR="${INSTALL_DIR}/lib/node_modules"
CONFIG_DIR="${HOME}/.config/kg"

# Package name (matches package.json)
PACKAGE_NAME="@aaronsb/kg-cli"

echo -e "${BLUE}🗑️  Uninstalling Knowledge Graph CLI (kg)...${NC}"
echo ""

# Check what's installed
FOUND_SOMETHING=false

if [ -f "${BIN_DIR}/kg" ] || [ -L "${BIN_DIR}/kg" ]; then
    echo -e "  Found: ${BIN_DIR}/kg"
    FOUND_SOMETHING=true
fi

if [ -f "${BIN_DIR}/kg-mcp-server" ] || [ -L "${BIN_DIR}/kg-mcp-server" ]; then
    echo -e "  Found: ${BIN_DIR}/kg-mcp-server"
    FOUND_SOMETHING=true
fi

if [ -d "${LIB_DIR}/${PACKAGE_NAME}" ]; then
    echo -e "  Found: ${LIB_DIR}/${PACKAGE_NAME}"
    FOUND_SOMETHING=true
fi

# Also check for old package name
if [ -d "${LIB_DIR}/@kg" ]; then
    echo -e "  Found: ${LIB_DIR}/@kg (old package)"
    FOUND_SOMETHING=true
fi

if [ -d "$CONFIG_DIR" ]; then
    echo -e "  Found: ${CONFIG_DIR} (config directory)"
fi

if [ "$FOUND_SOMETHING" = false ]; then
    echo -e "${YELLOW}Nothing to uninstall - kg CLI not found in ${INSTALL_DIR}${NC}"
    exit 0
fi

echo ""

# Confirm unless --force flag
if [[ "$1" != "--force" && "$1" != "-f" ]]; then
    echo -ne "${YELLOW}Remove these files? [y/N]: ${NC}"
    read -r CONFIRM
    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
    echo ""
fi

# Remove binaries
if [ -f "${BIN_DIR}/kg" ] || [ -L "${BIN_DIR}/kg" ]; then
    rm -f "${BIN_DIR}/kg"
    echo -e "${GREEN}✓${NC} Removed ${BIN_DIR}/kg"
fi

if [ -f "${BIN_DIR}/kg-mcp-server" ] || [ -L "${BIN_DIR}/kg-mcp-server" ]; then
    rm -f "${BIN_DIR}/kg-mcp-server"
    echo -e "${GREEN}✓${NC} Removed ${BIN_DIR}/kg-mcp-server"
fi

# Remove package from lib
if [ -d "${LIB_DIR}/${PACKAGE_NAME}" ]; then
    rm -rf "${LIB_DIR}/${PACKAGE_NAME}"
    echo -e "${GREEN}✓${NC} Removed ${LIB_DIR}/${PACKAGE_NAME}"
fi

# Remove old package name if present
if [ -d "${LIB_DIR}/@kg" ]; then
    rm -rf "${LIB_DIR}/@kg"
    echo -e "${GREEN}✓${NC} Removed ${LIB_DIR}/@kg"
fi

# Clean up empty @aaronsb scope directory
if [ -d "${LIB_DIR}/@aaronsb" ] && [ -z "$(ls -A "${LIB_DIR}/@aaronsb")" ]; then
    rmdir "${LIB_DIR}/@aaronsb"
    echo -e "${GREEN}✓${NC} Removed empty ${LIB_DIR}/@aaronsb"
fi

echo ""

# Ask about config
if [ -d "$CONFIG_DIR" ]; then
    echo -e "${YELLOW}Config directory exists: ${CONFIG_DIR}${NC}"
    echo "  This contains your saved API URL, tokens, and preferences."
    echo ""
    if [[ "$1" == "--all" ]]; then
        rm -rf "$CONFIG_DIR"
        echo -e "${GREEN}✓${NC} Removed ${CONFIG_DIR}"
    else
        echo "  Keep it to preserve settings for future installs."
        echo "  To remove: rm -rf ${CONFIG_DIR}"
        echo "  Or run: ./uninstall.sh --all"
    fi
fi

echo ""
echo -e "${GREEN}✅ Uninstall complete!${NC}"
echo ""
