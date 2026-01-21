#!/bin/bash
# Publish @aaronsb/kg-cli to npm
#
# Usage:
#   ./scripts/publish-cli.sh           # Publish current version
#   ./scripts/publish-cli.sh --dry-run # Test without publishing
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_DIR="$SCRIPT_DIR/../cli"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo -e "${YELLOW}Dry run mode - no actual publish${NC}"
    echo
fi

cd "$CLI_DIR"

# Check npm login
echo -e "${BLUE}Checking npm authentication...${NC}"
if ! npm whoami &>/dev/null; then
    echo -e "${RED}Not logged in to npm${NC}"
    echo "Run: npm login"
    exit 1
fi
NPM_USER=$(npm whoami)
echo -e "${GREEN}✓ Logged in as: $NPM_USER${NC}"

# Get version from package.json
VERSION=$(node -p "require('./package.json').version")
PACKAGE_NAME=$(node -p "require('./package.json').name")

echo -e "${BLUE}Package: ${PACKAGE_NAME}@${VERSION}${NC}"
echo

# Check if version already exists
echo -e "${BLUE}Checking if version exists on npm...${NC}"
if npm view "${PACKAGE_NAME}@${VERSION}" version &>/dev/null; then
    echo -e "${RED}Version ${VERSION} already published${NC}"
    echo "Bump version in cli/package.json first"
    exit 1
fi
echo -e "${GREEN}✓ Version ${VERSION} is available${NC}"
echo

# Sync version with main VERSION file
MAIN_VERSION=$(cat "$SCRIPT_DIR/../VERSION" 2>/dev/null || echo "")
if [[ -n "$MAIN_VERSION" && "$MAIN_VERSION" != "$VERSION" ]]; then
    echo -e "${YELLOW}Note: CLI version ($VERSION) differs from main VERSION ($MAIN_VERSION)${NC}"
    echo
fi

# Clean and build
echo -e "${BLUE}Building...${NC}"
npm run clean
npm run build
echo -e "${GREEN}✓ Build complete${NC}"
echo

# Show what will be published
echo -e "${BLUE}Files to publish:${NC}"
npm pack --dry-run 2>&1 | grep -E "^npm notice [0-9]" | head -20
echo

# Publish
if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}Dry run - skipping actual publish${NC}"
    echo "Would run: npm publish --access public"
else
    echo -e "${BLUE}Publishing to npm...${NC}"
    npm publish --access public
    echo
    echo -e "${GREEN}✅ Published ${PACKAGE_NAME}@${VERSION}${NC}"
    echo
    echo "Install with:"
    echo -e "  ${BLUE}npm install -g ${PACKAGE_NAME}${NC}"
fi
