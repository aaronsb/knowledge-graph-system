#!/bin/bash
# ============================================================================
# rebuild-api.sh
# Rebuild API image and restart container to pick up changes
# ============================================================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../../.." && pwd )"
DOCKER_DIR="$PROJECT_ROOT/docker"

echo -e "${BLUE}→ Rebuilding API image...${NC}"

# Set build metadata (same as start-app.sh)
export GIT_COMMIT=$(cd "$PROJECT_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")
export BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cd "$DOCKER_DIR"

# Rebuild API image
docker-compose --env-file "$PROJECT_ROOT/.env" build api

echo -e "${GREEN}✓ API image rebuilt${NC}"
echo ""

# Check if container is running
if docker ps --format '{{.Names}}' | grep -q "^kg-api-dev$"; then
    echo -e "${YELLOW}→ Restarting API container to pick up new image...${NC}"
    docker-compose --env-file "$PROJECT_ROOT/.env" up -d --force-recreate --no-deps api

    # Wait for health check
    echo -e "${BLUE}  Waiting for API to be healthy...${NC}"
    for i in {1..30}; do
        if docker ps --format '{{.Names}} {{.Status}}' | grep -q "kg-api.*healthy"; then
            echo -e "${GREEN}✓ API container restarted and healthy${NC}"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${YELLOW}⚠  API health check timeout (may still be starting)${NC}"
            break
        fi
        sleep 2
    done
else
    echo -e "${YELLOW}⚠  API container not running${NC}"
    echo "   Start it with: ./operator/lib/start-app.sh"
fi

echo ""
echo -e "${GREEN}✅ Done${NC}"
echo ""
echo "Image metadata:"
echo "  Commit: ${GIT_COMMIT}"
echo "  Built:  ${BUILD_DATE}"
echo ""
