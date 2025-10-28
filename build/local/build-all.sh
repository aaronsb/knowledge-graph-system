#!/usr/bin/env bash
#
# build-all.sh - Build all components of the Knowledge Graph system
#
# Usage: ./build-all.sh [--clean] [--verbose]
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
CLEAN=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --clean)
      CLEAN=true
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    --help)
      echo "Usage: $0 [--clean] [--verbose]"
      echo ""
      echo "Options:"
      echo "  --clean    Clean build artifacts before building"
      echo "  --verbose  Show detailed build output"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Knowledge Graph - Build All Components${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Clean if requested
if [ "$CLEAN" = true ]; then
  echo -e "${YELLOW}🧹 Cleaning build artifacts...${NC}"
  rm -rf "$PROJECT_ROOT/client/dist"
  rm -rf "$PROJECT_ROOT/venv"
  rm -rf "$PROJECT_ROOT/.pytest_cache"
  rm -rf "$PROJECT_ROOT/client/node_modules"
  echo -e "${GREEN}✓ Clean complete${NC}"
  echo ""
fi

# Build order (respects dependencies)
COMPONENTS=(
  "build-database.sh:Database"
  "build-api.sh:API Server"
  "build-cli.sh:CLI Tool"
  "build-mcp.sh:MCP Server"
  "build-viz.sh:Visualization"
)

FAILED=()
SUCCEEDED=()

for component in "${COMPONENTS[@]}"; do
  SCRIPT="${component%%:*}"
  NAME="${component##*:}"

  echo -e "${BLUE}━━━ Building: $NAME ━━━${NC}"

  if [ "$VERBOSE" = true ]; then
    if "$SCRIPT_DIR/$SCRIPT"; then
      SUCCEEDED+=("$NAME")
      echo -e "${GREEN}✓ $NAME built successfully${NC}"
    else
      FAILED+=("$NAME")
      echo -e "${RED}✗ $NAME build failed${NC}"
    fi
  else
    if "$SCRIPT_DIR/$SCRIPT" > /dev/null 2>&1; then
      SUCCEEDED+=("$NAME")
      echo -e "${GREEN}✓ $NAME built successfully${NC}"
    else
      FAILED+=("$NAME")
      echo -e "${RED}✗ $NAME build failed${NC}"
    fi
  fi

  echo ""
done

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Build Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}Succeeded: ${#SUCCEEDED[@]}${NC}"
for name in "${SUCCEEDED[@]}"; do
  echo -e "  ${GREEN}✓${NC} $name"
done

if [ ${#FAILED[@]} -gt 0 ]; then
  echo ""
  echo -e "${RED}Failed: ${#FAILED[@]}${NC}"
  for name in "${FAILED[@]}"; do
    echo -e "  ${RED}✗${NC} $name"
  done
  echo ""
  echo -e "${RED}Build failed. Check logs for details.${NC}"
  exit 1
fi

echo ""
echo -e "${GREEN}✓ All components built successfully!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "  Deploy locally: ${YELLOW}./build/deploy/local/deploy-all.sh${NC}"
echo -e "  Install system: ${YELLOW}./build/install/install-local.sh${NC}"
echo ""
