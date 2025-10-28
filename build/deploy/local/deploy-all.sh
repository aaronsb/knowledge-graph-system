#!/usr/bin/env bash
#
# deploy-all.sh - Deploy all components locally
#
# Status: PARTIAL - Uses existing deployment scripts
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
CLEAN=false
NO_API=false
NO_DATABASE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --clean) CLEAN=true; shift ;;
    --no-api) NO_API=true; shift ;;
    --no-database) NO_DATABASE=true; shift ;;
    --help)
      echo "Usage: $0 [--clean] [--no-api] [--no-database]"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Knowledge Graph - Local Deployment${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Deploy database
if [ "$NO_DATABASE" = false ]; then
  echo -e "${BLUE}━━━ Deploying: Database ━━━${NC}"
  "$SCRIPT_DIR/deploy-database.sh"
  echo -e "${GREEN}✓ Database deployed${NC}"
  echo ""
fi

# Deploy API
if [ "$NO_API" = false ]; then
  echo -e "${BLUE}━━━ Deploying: API Server ━━━${NC}"
  "$SCRIPT_DIR/deploy-api.sh"
  echo -e "${GREEN}✓ API Server deployed${NC}"
  echo ""
fi

# Deploy visualization (future)
echo -e "${BLUE}━━━ Deploying: Visualization ━━━${NC}"
"$SCRIPT_DIR/deploy-viz.sh" || true
echo ""

echo -e "${GREEN}✓ Deployment complete!${NC}"
echo ""
echo -e "${BLUE}Services:${NC}"
echo -e "  Database:  ${GREEN}http://localhost:5432${NC}"
echo -e "  API:       ${GREEN}http://localhost:8000${NC}"
echo ""
echo -e "${BLUE}Verify:${NC}"
echo -e "  ${GREEN}kg health${NC}"
echo ""
