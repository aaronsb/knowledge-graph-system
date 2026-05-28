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
    echo -e "  • ${GREEN}Preserve${NC} operator container"
fi
echo "  • Remove Docker networks"

if [ "$REMOVE_VOLUMES" = true ]; then
    echo "  • Delete ALL volumes (PostgreSQL, Garage, HF cache ~1GB)"
else
    echo -e "  • ${GREEN}Preserve${NC} volumes (database data, Garage storage, HF cache)"
fi

if [ "$KEEP_ENV" = false ]; then
    echo "  • Delete .env file (regenerate with init-secrets.sh)"
else
    echo "  • Keep .env file"
fi

if [ "$REMOVE_IMAGES" = true ]; then
    echo "  • Remove Docker images (forces 2-3 min rebuild)"
else
    echo -e "  • ${GREEN}Preserve${NC} Docker images"
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
echo -e "${BLUE}→ Running docker compose down...${NC}"

# Determine docker compose down flags
DOWN_FLAGS="--remove-orphans"  # always catch services no longer in the active overlay set
if [ "$REMOVE_VOLUMES" = true ]; then
    DOWN_FLAGS="$DOWN_FLAGS -v"  # also remove (named + anonymous) volumes attached to containers
    echo -e "  ${YELLOW}Including volumes (--remove-volumes specified)${NC}"
else
    echo -e "  ${GREEN}Preserving volumes (default)${NC}"
fi

# Run compose down using the SAME overlay stack the platform was started with
# (sources common.sh -> get_compose_cmd, which honors GPU_MODE / DEV_MODE /
# IMAGE_SOURCE from .operator.conf). Doing this with the wrong overlay set
# left services unreferenced from compose's perspective — and their
# anonymous volumes orphaned as SHA-named leftovers that the manual sweep
# below can't grep for.
if [ -f "$SCRIPT_DIR/common.sh" ]; then
    # shellcheck source=operator/lib/common.sh
    source "$SCRIPT_DIR/common.sh"
    load_operator_config
    COMPOSE_CMD=$(get_compose_cmd)
    $COMPOSE_CMD down $DOWN_FLAGS 2>/dev/null || true
else
    # Fallback: best-effort base + dev overlay, no env file
    docker compose -f docker-compose.yml down $DOWN_FLAGS 2>/dev/null || true
    if [ -f "$DOCKER_DIR/docker-compose.dev.yml" ]; then
        docker compose -f docker-compose.yml -f docker-compose.dev.yml down $DOWN_FLAGS 2>/dev/null || true
    fi
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

# Only manually remove volumes if --remove-volumes specified and docker compose down didn't catch them
if [ "$REMOVE_VOLUMES" = true ]; then
    echo -e "${BLUE}→ Cleaning up volumes...${NC}"

    # Pass 1: named volumes matching our project's naming patterns.
    # The kg- prefix catches the standalone/prod layout (kg_postgres_data
    # etc.); knowledge-graph and docker_ catch dev-mode and curl-installer
    # layouts. This pass never touches SHA-named anonymous volumes — those
    # are handled in pass 2.
    VOLUMES=$(docker volume ls -q | grep -E "knowledge-graph|docker_postgres|docker_garage|docker_hf|^kg_" || true)
    if [ -n "$VOLUMES" ]; then
        while IFS= read -r volume; do
            echo -e "  ${YELLOW}Removing:${NC} $volume"
            docker volume rm "$volume" 2>/dev/null || true
        done <<< "$VOLUMES"
        echo -e "${GREEN}✓ Removed named volumes${NC}"
    else
        echo -e "${GREEN}✓ No named volumes to remove${NC}"
    fi

    # Pass 2: detect dangling (no container references) volumes and prompt.
    # Past compose versions / partial teardowns left anonymous volumes with
    # SHA names containing the PG18 cluster (/_data/18/docker/) — those
    # don't match pass 1's grep, and `compose down --remove-orphans` only
    # reaches volumes attached to containers compose still knows about.
    # Listing rather than auto-deleting because dangling volumes on a
    # shared host may belong to other projects (this developer's box had
    # sable_sable-pgdata and whisper-service_whisper-temp sitting alongside
    # ours).
    DANGLING_VOLS=$(docker volume ls -qf dangling=true 2>/dev/null || true)
    if [ -n "$DANGLING_VOLS" ]; then
        echo ""
        echo -e "${BLUE}→ Dangling volumes detected (not referenced by any container):${NC}"
        # Show each with a peek at what's inside (Docker compose project label
        # if present, otherwise first-level contents). This is how the user
        # decides whether it's a kg leftover or an unrelated project.
        while IFS= read -r vol; do
            label=$(docker volume inspect "$vol" --format '{{index .Labels "com.docker.compose.project"}}' 2>/dev/null)
            mount=$(docker volume inspect "$vol" --format '{{.Mountpoint}}' 2>/dev/null)
            if [ -n "$label" ] && [ "$label" != "<no value>" ]; then
                echo -e "  • ${YELLOW}$vol${NC}  (compose project: $label)"
            else
                echo -e "  • ${YELLOW}$vol${NC}  (anonymous; mount: $mount)"
            fi
        done <<< "$DANGLING_VOLS"
        echo ""

        if [ "$AUTO_YES" = true ]; then
            echo -e "${YELLOW}→ --yes specified, removing all dangling volumes${NC}"
            REMOVE_DANGLING=true
        else
            read -p "Remove all dangling volumes listed above? Type 'yes' to confirm (or anything else to skip): " -r
            if [ "$REPLY" = "yes" ]; then
                REMOVE_DANGLING=true
            else
                REMOVE_DANGLING=false
                echo -e "${YELLOW}→ Skipped dangling-volume cleanup${NC}"
                echo -e "${YELLOW}  Remove manually with: docker volume rm <volume-id>${NC}"
            fi
        fi

        if [ "$REMOVE_DANGLING" = true ]; then
            while IFS= read -r vol; do
                echo -e "  ${YELLOW}Removing:${NC} $vol"
                docker volume rm "$vol" 2>/dev/null || true
            done <<< "$DANGLING_VOLS"
            echo -e "${GREEN}✓ Removed dangling volumes${NC}"
        fi
    else
        echo -e "${GREEN}✓ No dangling volumes${NC}"
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
