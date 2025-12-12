#!/bin/bash
set -e

# ============================================================================
# teardown.sh
# Multi-level teardown: three levels of cleanup granularity
# ============================================================================
#
# Level 1 (default): Stop containers, preserve volumes & images
# Level 2 (--remove-images): Level 1 + remove images
# Level 3 (--full): Level 1 + Level 2 + remove ALL volumes including caches
#
# ============================================================================

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

# Get project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
DOCKER_DIR="$PROJECT_ROOT/docker"

# Parse arguments
KEEP_ENV=false
AUTO_YES=false
REMOVE_IMAGES=false
REMOVE_VOLUMES=false
INCLUDE_OPERATOR=false

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
        --remove-volumes)
            REMOVE_VOLUMES=true
            shift
            ;;
        --include-operator)
            INCLUDE_OPERATOR=true
            shift
            ;;
        --full)
            REMOVE_IMAGES=true
            REMOVE_VOLUMES=true
            INCLUDE_OPERATOR=true
            shift
            ;;
        -y|--yes)
            AUTO_YES=true
            shift
            ;;
        -h|--help)
            echo "Multi-Level Teardown Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --keep-env          Keep .env file (don't delete secrets)"
            echo "  --remove-images     Also remove Docker images"
            echo "  --remove-volumes    Also remove ALL volumes including caches"
            echo "  --include-operator  Also teardown the operator container (default: preserve)"
            echo "  --full              Complete teardown: images + volumes + operator"
            echo "  -y, --yes           Skip confirmation prompt"
            echo "  -h, --help          Show this help"
            echo ""
            echo "Default Behavior:"
            echo "  • Stops app containers (api, web) and infra (postgres, garage)"
            echo "  • Preserves operator container (for quick restart)"
            echo "  • Preserves volumes (database data, Garage storage, HF cache)"
            echo "  • Preserves Docker images"
            echo ""
            echo "Examples:"
            echo "  $0                      # Stop platform, keep operator + data"
            echo "  $0 --include-operator   # Stop everything including operator"
            echo "  $0 --remove-images      # Force image rebuild on next start"
            echo "  $0 --full               # Nuclear option: remove everything"
            echo "  $0 --keep-env --full    # Full reset but keep secrets"
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
echo "║                    TEARDOWN                                ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Determine teardown level description
LEVEL_PARTS=()
if [ "$INCLUDE_OPERATOR" = true ]; then
    LEVEL_PARTS+=("operator")
fi
if [ "$REMOVE_IMAGES" = true ]; then
    LEVEL_PARTS+=("images")
fi
if [ "$REMOVE_VOLUMES" = true ]; then
    LEVEL_PARTS+=("volumes")
fi

if [ ${#LEVEL_PARTS[@]} -eq 0 ]; then
    LEVEL="Platform only (operator preserved)"
    LEVEL_COLOR="${GREEN}"
elif [ "$REMOVE_VOLUMES" = true ] && [ "$REMOVE_IMAGES" = true ] && [ "$INCLUDE_OPERATOR" = true ]; then
    LEVEL="Full (everything)"
    LEVEL_COLOR="${RED}"
else
    LEVEL="Platform + ${LEVEL_PARTS[*]}"
    LEVEL_COLOR="${YELLOW}"
fi

echo -e "${BOLD}Teardown: ${LEVEL_COLOR}${LEVEL}${NC}"
echo ""

echo -e "${YELLOW}This will:${NC}"
if [ "$INCLUDE_OPERATOR" = true ]; then
    echo "  • Stop ALL containers (including operator)"
else
    echo "  • Stop platform containers (api, web, postgres, garage)"
    echo "  • ${GREEN}Preserve${NC} operator container"
fi
echo "  • Remove Docker networks"

if [ "$REMOVE_VOLUMES" = true ]; then
    echo "  • Delete ALL volumes (PostgreSQL, Garage, HF cache ~1GB)"
else
    echo "  • ${GREEN}Preserve${NC} volumes (database data, Garage storage, HF cache)"
fi

if [ "$KEEP_ENV" = false ]; then
    echo "  • Delete .env file (regenerate with init-secrets.sh)"
else
    echo "  • Keep .env file"
fi

if [ "$REMOVE_IMAGES" = true ]; then
    echo "  • Remove Docker images (forces 2-3 min rebuild)"
else
    echo "  • ${GREEN}Preserve${NC} Docker images"
fi

echo ""

if [ "$REMOVE_VOLUMES" = true ]; then
    echo -e "${RED}⚠️  All database data and uploaded files will be LOST!${NC}"
    echo -e "${RED}⚠️  HuggingFace model cache (~1GB) will be deleted and re-downloaded!${NC}"
else
    echo -e "${GREEN}✓ Database data and caches will be preserved${NC}"
fi

if [ "$REMOVE_IMAGES" = true ]; then
    echo -e "${YELLOW}⚠️  Next startup will require 2-3 minute image rebuild${NC}"
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

# Stop and remove containers (but NOT volumes by default)
echo -e "${BLUE}→ Running docker-compose down...${NC}"

# Determine docker-compose down flags
DOWN_FLAGS=""
if [ "$REMOVE_VOLUMES" = true ]; then
    DOWN_FLAGS="-v"  # Remove volumes
    echo -e "  ${YELLOW}Including volumes (--remove-volumes specified)${NC}"
else
    echo -e "  ${GREEN}Preserving volumes (default)${NC}"
fi

# Try with dev override first (in case services were started with --dev)
if [ -f "$PROJECT_ROOT/.env" ]; then
    if [ -f "$DOCKER_DIR/docker-compose.dev.yml" ]; then
        echo -e "  ${YELLOW}Checking dev mode containers...${NC}"
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml --env-file "$PROJECT_ROOT/.env" down $DOWN_FLAGS 2>/dev/null || true
    fi
    # Then run regular teardown (catches any remaining)
    docker-compose --env-file "$PROJECT_ROOT/.env" down $DOWN_FLAGS 2>/dev/null || true
else
    if [ -f "$DOCKER_DIR/docker-compose.dev.yml" ]; then
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml down $DOWN_FLAGS 2>/dev/null || true
    fi
    docker-compose down $DOWN_FLAGS 2>/dev/null || true
fi
echo -e "${GREEN}✓ Docker Compose services stopped and removed${NC}"

# Force remove any remaining containers
echo -e "${BLUE}→ Cleaning up any remaining containers...${NC}"
if [ "$INCLUDE_OPERATOR" = true ]; then
    REMAINING=$(docker ps -a --format '{{.Names}}' | grep -E "knowledge-graph|kg-" || true)
else
    # Exclude operator container
    REMAINING=$(docker ps -a --format '{{.Names}}' | grep -E "knowledge-graph|kg-" | grep -v "^kg-operator$" || true)
fi
if [ -n "$REMAINING" ]; then
    while IFS= read -r container; do
        echo -e "  ${YELLOW}Removing:${NC} $container"
        docker rm -f "$container" 2>/dev/null || true
    done <<< "$REMAINING"
    echo -e "${GREEN}✓ Removed remaining containers${NC}"
else
    echo -e "${GREEN}✓ No remaining containers${NC}"
fi

if [ "$INCLUDE_OPERATOR" = false ]; then
    # Check if operator is still running
    if docker ps --format '{{.Names}}' | grep -q "^kg-operator$"; then
        echo -e "${GREEN}✓ Operator container preserved${NC}"
    fi
fi

# Only manually remove volumes if --remove-volumes specified and docker-compose down didn't catch them
if [ "$REMOVE_VOLUMES" = true ]; then
    echo -e "${BLUE}→ Cleaning up volumes...${NC}"
    VOLUMES=$(docker volume ls -q | grep -E "knowledge-graph|docker_postgres|docker_garage|docker_hf" || true)
    if [ -n "$VOLUMES" ]; then
        while IFS= read -r volume; do
            echo -e "  ${YELLOW}Removing:${NC} $volume"
            docker volume rm "$volume" 2>/dev/null || true
        done <<< "$VOLUMES"
        echo -e "${GREEN}✓ Removed volumes${NC}"
    else
        echo -e "${GREEN}✓ No volumes to remove${NC}"
    fi
else
    echo -e "${GREEN}✓ Preserved volumes (use --remove-volumes to delete)${NC}"
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

# Remove images if requested
if [ "$REMOVE_IMAGES" = true ]; then
    IMAGES=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E "knowledge-graph|^kg-" | grep -v "<none>" || true)
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

    # Also remove dangling images (untagged build layers)
    echo -e "${BLUE}→ Removing dangling images...${NC}"
    DANGLING=$(docker images -f "dangling=true" -q)
    if [ -n "$DANGLING" ]; then
        docker rmi -f $DANGLING 2>/dev/null || true
        echo -e "${GREEN}✓ Dangling images removed${NC}"
    else
        echo -e "${GREEN}✓ No dangling images${NC}"
    fi
else
    # Show images but don't remove
    IMAGES=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E "knowledge-graph|^kg-" | grep -v "<none>" || true)
    if [ -n "$IMAGES" ]; then
        echo ""
        echo -e "${GREEN}✓ Preserved Docker images (use --remove-images to delete)${NC}"
    fi
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Teardown complete - ${LEVEL}${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ "$REMOVE_VOLUMES" = false ]; then
    echo -e "${BOLD}Data Preserved:${NC}"
    echo "  • PostgreSQL database (all concepts and relationships)"
    echo "  • Garage storage (all uploaded images)"
    echo "  • HuggingFace model cache (~500MB-1GB, prevents re-download)"
    echo ""
fi

echo -e "${BOLD}Next steps:${NC}"
if [ "$KEEP_ENV" = false ]; then
    echo "  1. Generate new secrets: ./operator/lib/init-secrets.sh --dev"
    echo "  2. Start fresh: ./operator/lib/start-infra.sh"
else
    echo "  1. Start fresh: ./operator/lib/start-infra.sh"
    if [ "$REMOVE_VOLUMES" = false ]; then
        echo "     (Your data will be restored from preserved volumes)"
    fi
fi

if [ "$REMOVE_IMAGES" = true ]; then
    echo "     (Images will be rebuilt automatically - takes 2-3 minutes)"
fi

if [ "$REMOVE_VOLUMES" = false ]; then
    echo ""
    echo -e "${YELLOW}Tip: Use --full for complete fresh start (deletes all data)${NC}"
fi

echo ""
