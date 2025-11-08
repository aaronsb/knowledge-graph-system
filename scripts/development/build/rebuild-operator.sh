#!/bin/bash
# ============================================================================
# rebuild-operator.sh
# Rebuild operator image and restart container to pick up changes
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

echo -e "${BLUE}→ Rebuilding operator image...${NC}"

# Set build metadata (same as start-infra.sh)
export GIT_COMMIT=$(cd "$PROJECT_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")
export BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cd "$DOCKER_DIR"

# Rebuild operator image
docker-compose --env-file "$PROJECT_ROOT/.env" build operator

echo -e "${GREEN}✓ Operator image rebuilt${NC}"
echo ""

# Check if container is running
if docker ps --format '{{.Names}}' | grep -q "^kg-operator$"; then
    echo -e "${YELLOW}→ Restarting operator container to pick up new image...${NC}"
    docker-compose --env-file "$PROJECT_ROOT/.env" up -d --force-recreate --no-deps operator
    echo -e "${GREEN}✓ Operator container restarted${NC}"
else
    echo -e "${YELLOW}⚠  Operator container not running${NC}"
    echo "   Start it with: ./operator/lib/start-infra.sh"
fi

echo ""
echo -e "${GREEN}✅ Done${NC}"
echo ""
echo "Image metadata:"
echo "  Commit: ${GIT_COMMIT}"
echo "  Built:  ${BUILD_DATE}"
echo ""
