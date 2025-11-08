#!/bin/bash
set -e

# ============================================================================
# teardown.sh
# Complete teardown: stop containers, remove volumes, clean state
# For testing clean installations
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
KEEP_ENV=false
AUTO_YES=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-env)
            KEEP_ENV=true
            shift
            ;;
        -y|--yes)
            AUTO_YES=true
            shift
            ;;
        -h|--help)
            echo "Complete Teardown Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --keep-env     Keep .env file (don't delete secrets)"
            echo "  -y, --yes      Skip confirmation prompt"
            echo "  -h, --help     Show this help"
            echo ""
            echo "What this does:"
            echo "  1. Stop all containers"
            echo "  2. Remove all containers"
            echo "  3. Remove all volumes (database data, garage storage)"
            echo "  4. Remove Docker networks"
            echo "  5. Optionally remove .env file"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}✗ Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${RED}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                COMPLETE TEARDOWN                           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

echo -e "${YELLOW}This will:${NC}"
echo "  • Stop all containers"
echo "  • Remove all containers"
echo "  • Delete all volumes (PostgreSQL data, Garage storage)"
echo "  • Remove Docker networks"
if [ "$KEEP_ENV" = false ]; then
    echo "  • Delete .env file (regenerate with init-secrets.sh)"
else
    echo "  • Keep .env file"
fi
echo ""
echo -e "${RED}⚠️  All database data and uploaded files will be LOST!${NC}"
echo ""

if [ "$AUTO_YES" = false ]; then
    read -p "Are you sure? Type 'yes' to confirm: " -r
    if [ "$REPLY" != "yes" ]; then
        echo -e "${YELLOW}Cancelled${NC}"
        exit 0
    fi
    echo ""
fi

cd "$DOCKER_DIR"

# Stop and remove everything
echo -e "${BLUE}→ Stopping all services...${NC}"
if [ -f "$PROJECT_ROOT/.env" ]; then
    docker-compose --env-file "$PROJECT_ROOT/.env" down -v 2>/dev/null || true
else
    docker-compose down -v 2>/dev/null || true
fi
echo -e "${GREEN}✓ Services stopped and removed${NC}"

# Force remove any remaining containers
echo -e "${BLUE}→ Cleaning up any remaining containers...${NC}"
REMAINING=$(docker ps -a --format '{{.Names}}' | grep -E "knowledge-graph|kg-" || true)
if [ -n "$REMAINING" ]; then
    echo "$REMAINING" | xargs docker rm -f 2>/dev/null || true
    echo -e "${GREEN}✓ Removed remaining containers${NC}"
else
    echo -e "${GREEN}✓ No remaining containers${NC}"
fi

# Force remove volumes
echo -e "${BLUE}→ Cleaning up volumes...${NC}"
VOLUMES=$(docker volume ls -q | grep -E "knowledge-graph|docker_postgres|docker_garage" || true)
if [ -n "$VOLUMES" ]; then
    echo "$VOLUMES" | xargs docker volume rm 2>/dev/null || true
    echo -e "${GREEN}✓ Removed volumes${NC}"
else
    echo -e "${GREEN}✓ No volumes to remove${NC}"
fi

# Remove networks
echo -e "${BLUE}→ Cleaning up networks...${NC}"
NETWORKS=$(docker network ls --format '{{.Name}}' | grep -E "knowledge-graph|docker_default" || true)
if [ -n "$NETWORKS" ]; then
    echo "$NETWORKS" | xargs docker network rm 2>/dev/null || true
    echo -e "${GREEN}✓ Removed networks${NC}"
else
    echo -e "${GREEN}✓ No networks to remove${NC}"
fi

# Remove .env if requested
if [ "$KEEP_ENV" = false ]; then
    if [ -f "$PROJECT_ROOT/.env" ]; then
        echo -e "${BLUE}→ Removing .env file...${NC}"
        rm "$PROJECT_ROOT/.env"
        echo -e "${GREEN}✓ .env removed${NC}"
    else
        echo -e "${GREEN}✓ No .env file to remove${NC}"
    fi
else
    echo -e "${YELLOW}→ Keeping .env file${NC}"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Teardown complete - clean slate ready${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ "$KEEP_ENV" = false ]; then
    echo -e "${BOLD}Next steps:${NC}"
    echo "  1. Generate new secrets: ./operator/lib/init-secrets.sh --dev"
    echo "  2. Start fresh: ./operator/lib/start-infra.sh"
    echo ""
else
    echo -e "${BOLD}Next steps:${NC}"
    echo "  1. Start fresh: ./operator/lib/start-infra.sh"
    echo "  2. Reconfigure if needed: docker exec kg-operator python /workspace/operator/configure.py status"
    echo ""
fi
