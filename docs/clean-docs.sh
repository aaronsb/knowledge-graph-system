#!/bin/bash
# Clean up MkDocs artifacts and virtual environment
#
# This script removes:
# - docs/.venv/       (Python virtual environment)
# - site/             (Built documentation)
# - .cache/           (MkDocs cache)
#
# Run this to start fresh or free up disk space.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  MkDocs Cleanup${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}This will remove:${NC}"

# Check what exists and calculate size
TOTAL_SIZE=0
FOUND_ITEMS=0

if [ -d "$SCRIPT_DIR/.venv" ]; then
    VENV_SIZE=$(du -sh "$SCRIPT_DIR/.venv" 2>/dev/null | cut -f1)
    echo -e "  ${RED}✗${NC} docs/.venv/         (${VENV_SIZE})"
    FOUND_ITEMS=$((FOUND_ITEMS + 1))
fi

if [ -d "$PROJECT_ROOT/site" ]; then
    SITE_SIZE=$(du -sh "$PROJECT_ROOT/site" 2>/dev/null | cut -f1)
    echo -e "  ${RED}✗${NC} site/               (${SITE_SIZE})"
    FOUND_ITEMS=$((FOUND_ITEMS + 1))
fi

if [ -d "$PROJECT_ROOT/.cache" ]; then
    CACHE_SIZE=$(du -sh "$PROJECT_ROOT/.cache" 2>/dev/null | cut -f1)
    echo -e "  ${RED}✗${NC} .cache/             (${CACHE_SIZE})"
    FOUND_ITEMS=$((FOUND_ITEMS + 1))
fi

echo ""

# If nothing to clean
if [ $FOUND_ITEMS -eq 0 ]; then
    echo -e "${GREEN}✓ Already clean - nothing to remove${NC}"
    exit 0
fi

# Prompt to continue
read -p "$(echo -e ${YELLOW}"Remove these artifacts? [y/N]: "${NC})" -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Aborted.${NC}"
    exit 0
fi

echo ""

# Remove artifacts
if [ -d "$SCRIPT_DIR/.venv" ]; then
    echo -e "${YELLOW}Removing docs/.venv/...${NC}"
    rm -rf "$SCRIPT_DIR/.venv"
    echo -e "${GREEN}✓ Removed virtual environment${NC}"
fi

if [ -d "$PROJECT_ROOT/site" ]; then
    echo -e "${YELLOW}Removing site/...${NC}"
    rm -rf "$PROJECT_ROOT/site"
    echo -e "${GREEN}✓ Removed built site${NC}"
fi

if [ -d "$PROJECT_ROOT/.cache" ]; then
    echo -e "${YELLOW}Removing .cache/...${NC}"
    rm -rf "$PROJECT_ROOT/.cache"
    echo -e "${GREEN}✓ Removed cache${NC}"
fi

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Cleanup complete${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
