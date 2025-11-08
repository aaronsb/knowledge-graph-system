#!/bin/bash
# ============================================================================
# rebuild-all.sh
# Rebuild all application images (operator, api, web) and restart containers
# ============================================================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

# Get project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../../.." && pwd )"
DOCKER_DIR="$PROJECT_ROOT/docker"

echo -e "${BLUE}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║       Rebuild All Application Images                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Set build metadata
export GIT_COMMIT=$(cd "$PROJECT_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")
export BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo -e "${BLUE}Build metadata:${NC}"
echo "  Commit: ${GIT_COMMIT}"
echo "  Date:   ${BUILD_DATE}"
echo ""

cd "$DOCKER_DIR"

# Rebuild all images
echo -e "${BLUE}→ Rebuilding all images...${NC}"
docker-compose --env-file "$PROJECT_ROOT/.env" build operator api web

echo -e "${GREEN}✓ All images rebuilt${NC}"
echo ""

# Restart running containers
echo -e "${BLUE}→ Restarting containers to pick up new images...${NC}"

RESTARTED=0

if docker ps --format '{{.Names}}' | grep -q "^kg-operator$"; then
    echo -e "${YELLOW}  Restarting operator...${NC}"
    docker-compose --env-file "$PROJECT_ROOT/.env" up -d --force-recreate --no-deps operator
    RESTARTED=$((RESTARTED + 1))
fi

if docker ps --format '{{.Names}}' | grep -q "^kg-api-dev$"; then
    echo -e "${YELLOW}  Restarting API...${NC}"
    docker-compose --env-file "$PROJECT_ROOT/.env" up -d --force-recreate --no-deps api
    RESTARTED=$((RESTARTED + 1))
fi

if docker ps --format '{{.Names}}' | grep -q "^kg-web-dev$"; then
    echo -e "${YELLOW}  Restarting web UI...${NC}"
    docker-compose --env-file "$PROJECT_ROOT/.env" up -d --force-recreate --no-deps web
    RESTARTED=$((RESTARTED + 1))
fi

if [ $RESTARTED -eq 0 ]; then
    echo -e "${YELLOW}⚠  No containers were running${NC}"
    echo "   Start with: ./operator/lib/start-infra.sh && ./operator/lib/start-app.sh"
else
    echo -e "${GREEN}✓ Restarted $RESTARTED container(s)${NC}"
fi

echo ""
echo -e "${GREEN}✅ Done${NC}"
echo ""
