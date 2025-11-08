#!/bin/bash
set -e

# ============================================================================
# start-app.sh
# Start application containers (api + web)
# Assumes infrastructure (postgres + garage) is already running
# ============================================================================

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
DOCKER_DIR="$PROJECT_ROOT/docker"

echo -e "${BLUE}Starting application containers...${NC}"
echo ""

# Check if infrastructure is running
echo -e "${BLUE}→ Checking infrastructure...${NC}"

POSTGRES_RUNNING=$(docker ps --format '{{.Names}}' | grep -E "^(kg-postgres-dev|knowledge-graph-postgres)$" || true)
GARAGE_RUNNING=$(docker ps --format '{{.Names}}' | grep -E "^(kg-garage-dev|knowledge-graph-garage)$" || true)

if [ -z "$POSTGRES_RUNNING" ]; then
    echo -e "${RED}✗ PostgreSQL not running${NC}"
    echo ""
    echo "Start infrastructure first:"
    echo "  ./operator/lib/start-infra.sh"
    echo ""
    exit 1
fi

if [ -z "$GARAGE_RUNNING" ]; then
    echo -e "${YELLOW}⚠  Garage not running (optional for basic operation)${NC}"
fi

echo -e "${GREEN}✓ Infrastructure ready${NC}"
echo ""

cd "$DOCKER_DIR"

# Start API
echo -e "${BLUE}→ Starting API server...${NC}"
docker-compose --env-file "$PROJECT_ROOT/.env" up -d api

echo -e "${BLUE}→ Waiting for API to be healthy...${NC}"

# Wait for API (up to 60 seconds)
for i in {1..30}; do
    if docker ps --format '{{.Names}} {{.Status}}' | grep -q "kg-api.*healthy\|knowledge-graph-api.*healthy"; then
        echo -e "${GREEN}✓ API server is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}⚠  API health check timeout (may still be starting)${NC}"
        echo ""
        echo "Check logs with: docker logs kg-api-dev"
        break
    fi
    sleep 2
done

# Start web viz app (if defined in docker-compose)
if docker-compose --env-file "$PROJECT_ROOT/.env" config --services 2>/dev/null | grep -q "^web$\|^viz$"; then
    echo ""
    echo -e "${BLUE}→ Starting web visualization...${NC}"
    docker-compose --env-file "$PROJECT_ROOT/.env" up -d web 2>/dev/null || docker-compose --env-file "$PROJECT_ROOT/.env" up -d viz 2>/dev/null || true
    echo -e "${GREEN}✓ Web app starting${NC}"
fi

echo ""
echo -e "${GREEN}✅ Application started${NC}"
echo ""
echo "Services:"
echo "  • API server: http://localhost:8000"
echo "  • Web app: http://localhost:3000"
echo ""
echo "Check status:"
echo "  docker-compose ps"
echo ""
echo "View logs:"
echo "  docker-compose logs -f api"
echo ""
