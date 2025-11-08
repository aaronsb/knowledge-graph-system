#!/bin/bash
set -e

# ============================================================================
# stop.sh
# Clean shutdown of all containers or specific layers
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

# Parse arguments
STOP_APP=true
STOP_INFRA=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --app-only)
            STOP_INFRA=false
            shift
            ;;
        --infra-only)
            STOP_APP=false
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --app-only      Stop only application containers (api, web)"
            echo "  --infra-only    Stop only infrastructure containers (postgres, garage)"
            echo "  -h, --help      Show this help message"
            echo ""
            echo "Default: Stop all containers"
            exit 0
            ;;
        *)
            echo -e "${RED}✗ Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

cd "$DOCKER_DIR"

# Stop application containers
if [ "$STOP_APP" = true ]; then
    echo -e "${BLUE}Stopping application containers...${NC}"
    echo ""

    # Check if containers are running
    API_RUNNING=$(docker ps --format '{{.Names}}' | grep -E "^(kg-api-dev|knowledge-graph-api)$" || true)
    WEB_RUNNING=$(docker ps --format '{{.Names}}' | grep -E "^(kg-viz-dev|kg-web-dev|knowledge-graph-web)$" || true)

    if [ -n "$API_RUNNING" ] || [ -n "$WEB_RUNNING" ]; then
        # Stop web first
        if docker-compose --env-file "$PROJECT_ROOT/.env" ps | grep -qE "web.*Up|viz.*Up"; then
            echo -e "${BLUE}→ Stopping web visualization...${NC}"
            docker-compose --env-file "$PROJECT_ROOT/.env" stop web 2>/dev/null || docker-compose --env-file "$PROJECT_ROOT/.env" stop viz 2>/dev/null || true
            echo -e "${GREEN}✓ Web stopped${NC}"
        fi

        # Stop API
        if docker-compose --env-file "$PROJECT_ROOT/.env" ps | grep -qE "api.*Up"; then
            echo -e "${BLUE}→ Stopping API server...${NC}"
            docker-compose --env-file "$PROJECT_ROOT/.env" stop api
            echo -e "${GREEN}✓ API stopped${NC}"
        fi

        echo ""
    else
        echo -e "${YELLOW}⚠  No application containers running${NC}"
        echo ""
    fi
fi

# Stop infrastructure containers
if [ "$STOP_INFRA" = true ]; then
    echo -e "${BLUE}Stopping infrastructure containers...${NC}"
    echo ""

    # Check if containers are running
    POSTGRES_RUNNING=$(docker ps --format '{{.Names}}' | grep -E "^(kg-postgres-dev|knowledge-graph-postgres)$" || true)
    GARAGE_RUNNING=$(docker ps --format '{{.Names}}' | grep -E "^(kg-garage-dev|knowledge-graph-garage)$" || true)

    if [ -n "$POSTGRES_RUNNING" ] || [ -n "$GARAGE_RUNNING" ]; then
        # Stop garage
        if docker-compose --env-file "$PROJECT_ROOT/.env" ps | grep -qE "garage.*Up"; then
            echo -e "${BLUE}→ Stopping Garage storage...${NC}"
            docker-compose --env-file "$PROJECT_ROOT/.env" stop garage
            echo -e "${GREEN}✓ Garage stopped${NC}"
        fi

        # Stop postgres last (might have open connections)
        if docker-compose --env-file "$PROJECT_ROOT/.env" ps | grep -qE "postgres.*Up"; then
            echo -e "${BLUE}→ Stopping PostgreSQL...${NC}"
            docker-compose --env-file "$PROJECT_ROOT/.env" stop postgres
            echo -e "${GREEN}✓ PostgreSQL stopped${NC}"
        fi

        echo ""
    else
        echo -e "${YELLOW}⚠  No infrastructure containers running${NC}"
        echo ""
    fi
fi

echo -e "${GREEN}✅ Shutdown complete${NC}"
echo ""
echo "To remove containers and volumes:"
echo "  cd docker/ && docker-compose down -v"
echo ""
echo "To restart:"
echo "  ./operator/lib/start-infra.sh"
echo "  ./operator/lib/start-app.sh"
echo ""
