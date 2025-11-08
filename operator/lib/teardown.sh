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
REMOVE_IMAGES=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-env)
            KEEP_ENV=true
            shift
            ;;
        --remove-images)
            REMOVE_IMAGES=true
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
            echo "  --keep-env       Keep .env file (don't delete secrets)"
            echo "  --remove-images  Also remove Docker images (forces clean rebuild)"
            echo "  -y, --yes        Skip confirmation prompt"
            echo "  -h, --help       Show this help"
            echo ""
            echo "What this does:"
            echo "  1. Stop all containers"
            echo "  2. Remove all containers"
            echo "  3. Remove all volumes (database data, garage storage)"
            echo "  4. Remove Docker networks"
            echo "  5. Optionally remove .env file"
            echo "  6. Optionally remove Docker images (requires clean rebuild)"
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
if [ "$REMOVE_IMAGES" = true ]; then
    echo "  • Remove Docker images (forces clean rebuild)"
fi
echo ""
echo -e "${RED}⚠️  All database data and uploaded files will be LOST!${NC}"
if [ "$REMOVE_IMAGES" = false ]; then
    echo -e "${YELLOW}Note: Docker images will be kept (you'll be prompted if you want to remove them)${NC}"
fi
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

# List running services before stopping
RUNNING_SERVICES=$(docker ps --format '{{.Names}}' | grep -E "knowledge-graph|kg-" || true)
if [ -n "$RUNNING_SERVICES" ]; then
    echo -e "${BLUE}→ Stopping services:${NC}"
    echo "$RUNNING_SERVICES" | sed 's/^/  • /'
    echo ""
fi

# Stop and remove everything
echo -e "${BLUE}→ Running docker-compose down...${NC}"
if [ -f "$PROJECT_ROOT/.env" ]; then
    docker-compose --env-file "$PROJECT_ROOT/.env" down -v 2>/dev/null || true
else
    docker-compose down -v 2>/dev/null || true
fi
echo -e "${GREEN}✓ Docker Compose services stopped and removed${NC}"

# Force remove any remaining containers
echo -e "${BLUE}→ Cleaning up any remaining containers...${NC}"
REMAINING=$(docker ps -a --format '{{.Names}}' | grep -E "knowledge-graph|kg-" || true)
if [ -n "$REMAINING" ]; then
    while IFS= read -r container; do
        echo -e "  ${YELLOW}Removing:${NC} $container"
        docker rm -f "$container" 2>/dev/null || true
    done <<< "$REMAINING"
    echo -e "${GREEN}✓ Removed remaining containers${NC}"
else
    echo -e "${GREEN}✓ No remaining containers${NC}"
fi

# Force remove volumes
echo -e "${BLUE}→ Cleaning up volumes...${NC}"
VOLUMES=$(docker volume ls -q | grep -E "knowledge-graph|docker_postgres|docker_garage|docker_api|docker_viz" || true)
if [ -n "$VOLUMES" ]; then
    while IFS= read -r volume; do
        echo -e "  ${YELLOW}Removing:${NC} $volume"
        docker volume rm "$volume" 2>/dev/null || true
    done <<< "$VOLUMES"
    echo -e "${GREEN}✓ Removed volumes${NC}"
else
    echo -e "${GREEN}✓ No volumes to remove${NC}"
fi

# Remove networks
echo -e "${BLUE}→ Cleaning up networks...${NC}"
NETWORKS=$(docker network ls --format '{{.Name}}' | grep -E "knowledge-graph|docker_default|knowledge-graph-system" || true)
if [ -n "$NETWORKS" ]; then
    while IFS= read -r network; do
        echo -e "  ${YELLOW}Removing:${NC} $network"
        docker network rm "$network" 2>/dev/null || true
    done <<< "$NETWORKS"
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

# Check for Docker images
IMAGES=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E "knowledge-graph|kg-|docker-" | grep -v "<none>" || true)

# Prompt to remove images if not specified via flag
if [ -n "$IMAGES" ] && [ "$REMOVE_IMAGES" = false ]; then
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Docker Images Found${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "The following Docker images are still present:"
    echo ""
    echo "$IMAGES" | sed 's/^/  • /'
    echo ""
    echo -e "${YELLOW}Removing images forces a clean rebuild (takes 2-3 minutes on next start)${NC}"
    echo ""
    read -p "Remove Docker images? [y/N]: " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        REMOVE_IMAGES=true
    fi
fi

# Remove images if requested
if [ "$REMOVE_IMAGES" = true ]; then
    if [ -n "$IMAGES" ]; then
        echo ""
        echo -e "${BLUE}→ Removing Docker images...${NC}"
        while IFS= read -r image; do
            echo -e "  ${YELLOW}Removing:${NC} $image"
            docker rmi -f "$image" 2>/dev/null || true
        done <<< "$IMAGES"
        echo -e "${GREEN}✓ Docker images removed${NC}"
    else
        echo ""
        echo -e "${GREEN}✓ No Docker images to remove${NC}"
    fi
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
    if [ "$REMOVE_IMAGES" = true ]; then
        echo "     (Images will be rebuilt automatically)"
    fi
    echo ""
else
    echo -e "${BOLD}Next steps:${NC}"
    echo "  1. Start fresh: ./operator/lib/start-infra.sh"
    if [ "$REMOVE_IMAGES" = true ]; then
        echo "     (Images will be rebuilt automatically)"
    fi
    echo "  2. Reconfigure if needed: docker exec kg-operator python /workspace/operator/configure.py status"
    echo ""
fi
