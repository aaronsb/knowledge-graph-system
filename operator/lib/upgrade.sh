#!/bin/bash
# ============================================================================
# upgrade.sh - Graceful platform upgrade
# ============================================================================
# Pulls new images (GHCR) or rebuilds (local), runs migrations, and restarts
# without data loss.
# ============================================================================

set -e

# Get project root
# In standalone mode, host directory is mounted at /project
# In repo/dev mode, everything is at /workspace
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ -d "/project" ] && [ -f "/project/.env" ]; then
    # Standalone mode: host directory mounted at /project
    PROJECT_ROOT="/project"
    DOCKER_DIR="/project"
else
    # Repo/dev mode: full workspace mounted
    PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
    if [ -d "$PROJECT_ROOT/docker" ]; then
        DOCKER_DIR="$PROJECT_ROOT/docker"
    else
        DOCKER_DIR="$PROJECT_ROOT"
    fi
fi

# Source common functions
source "$SCRIPT_DIR/common.sh"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# ============================================================================
# Options
# ============================================================================
DRY_RUN=false
BACKUP_BEFORE=true
TARGET_VERSION=""
SHOW_HELP=false

# ============================================================================
# Help
# ============================================================================
show_help() {
    cat << EOF
${BOLD}Platform Upgrade${NC}

Gracefully upgrade the Knowledge Graph platform without data loss.

${BOLD}Usage:${NC}
  ./operator.sh upgrade [OPTIONS]

${BOLD}Options:${NC}
  --dry-run           Show what would be done without making changes
  --no-backup         Skip pre-upgrade database backup
  --version VERSION   Upgrade to specific version tag (GHCR only)
  --help              Show this help message

${BOLD}What This Does:${NC}
  1. Pre-flight: Verify .env exists, check current state
  2. Backup database (optional, recommended)
  3. Pull new images (GHCR) or rebuild (local)
  4. Stop application containers (keep postgres/garage running)
  5. Apply database migrations
  6. Start application with new images
  7. Health check

${BOLD}Examples:${NC}
  ./operator.sh upgrade              # Pull latest, migrate, restart
  ./operator.sh upgrade --dry-run    # Show what would change
  ./operator.sh upgrade --no-backup  # Skip backup (faster)

EOF
}

# ============================================================================
# Parse Arguments
# ============================================================================
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                SHOW_HELP=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --no-backup)
                BACKUP_BEFORE=false
                shift
                ;;
            --version=*)
                TARGET_VERSION="${1#*=}"
                shift
                ;;
            --version)
                TARGET_VERSION="$2"
                shift 2
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

# ============================================================================
# Pre-flight Checks
# ============================================================================
preflight_check() {
    echo -e "${BLUE}→ Pre-flight checks...${NC}"
    local errors=0

    # Check .env exists
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        echo -e "${RED}  ✗ .env file not found${NC}"
        echo "    Run ./operator.sh init first"
        errors=$((errors + 1))
    else
        echo -e "${GREEN}  ✓ .env file exists${NC}"
    fi

    # Check .operator.conf exists
    if [ ! -f "$PROJECT_ROOT/.operator.conf" ]; then
        echo -e "${RED}  ✗ .operator.conf not found${NC}"
        echo "    Run ./operator.sh init first"
        errors=$((errors + 1))
    else
        echo -e "${GREEN}  ✓ .operator.conf exists${NC}"
        load_operator_config
    fi

    # Check Docker is running
    if ! docker ps >/dev/null 2>&1; then
        echo -e "${RED}  ✗ Docker is not running${NC}"
        errors=$((errors + 1))
    else
        echo -e "${GREEN}  ✓ Docker is available${NC}"
    fi

    # Get container names
    POSTGRES_CONTAINER=$(get_container_name postgres)
    GARAGE_CONTAINER=$(get_container_name garage)
    API_CONTAINER=$(get_container_name api)
    WEB_CONTAINER=$(get_container_name web)
    OPERATOR_CONTAINER=$(get_container_name operator)

    # Check if postgres is running
    if docker ps --format '{{.Names}}' | grep -qE "$(get_container_pattern postgres)"; then
        echo -e "${GREEN}  ✓ PostgreSQL is running${NC}"
    else
        echo -e "${YELLOW}  ⚠ PostgreSQL is not running (will be started)${NC}"
    fi

    echo ""

    if [ $errors -gt 0 ]; then
        echo -e "${RED}Pre-flight check failed with $errors error(s)${NC}"
        exit 1
    fi
}

# ============================================================================
# Show Current State
# ============================================================================
show_current_state() {
    echo -e "${BOLD}Current Configuration:${NC}"
    echo -e "  Dev mode:         ${BLUE}$DEV_MODE${NC}"
    echo -e "  GPU mode:         ${BLUE}$GPU_MODE${NC}"
    echo -e "  Container prefix: ${BLUE}$CONTAINER_PREFIX${NC}"
    echo -e "  Image source:     ${BLUE}$IMAGE_SOURCE${NC}"
    echo -e "  Compose file:     ${BLUE}$COMPOSE_FILE${NC}"
    echo ""

    # Show current image versions
    echo -e "${BOLD}Current Images:${NC}"
    for service in api web operator; do
        local container=$(get_container_name "$service")
        local image=$(docker inspect --format '{{.Config.Image}}' "$container" 2>/dev/null || echo "not running")
        echo -e "  $service: ${BLUE}$image${NC}"
    done
    echo ""
}

# ============================================================================
# Backup Database
# ============================================================================
backup_database() {
    if [ "$BACKUP_BEFORE" = false ]; then
        echo -e "${YELLOW}→ Skipping backup (--no-backup)${NC}"
        echo ""
        return
    fi

    echo -e "${BLUE}→ Creating pre-upgrade backup...${NC}"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}  [DRY RUN] Would run: operator/database/backup-database.sh -y${NC}"
    else
        if [ -f "$PROJECT_ROOT/operator/database/backup-database.sh" ]; then
            "$PROJECT_ROOT/operator/database/backup-database.sh" -y
        else
            echo -e "${YELLOW}  ⚠ Backup script not found, skipping${NC}"
        fi
    fi
    echo ""
}

# ============================================================================
# Pull/Rebuild Images
# ============================================================================
update_images() {
    echo -e "${BLUE}→ Updating images...${NC}"

    cd "$DOCKER_DIR"

    if [ "$IMAGE_SOURCE" = "ghcr" ]; then
        echo -e "  Source: ${BLUE}GitHub Container Registry${NC}"

        if [ "$DRY_RUN" = true ]; then
            echo -e "${YELLOW}  [DRY RUN] Would run: docker-compose pull${NC}"
        else
            run_compose pull
        fi
    else
        echo -e "  Source: ${BLUE}Local build${NC}"

        if [ "$DRY_RUN" = true ]; then
            echo -e "${YELLOW}  [DRY RUN] Would run: docker-compose build${NC}"
        else
            run_compose build
        fi
    fi
    echo ""
}

# ============================================================================
# Stop Application
# ============================================================================
stop_application() {
    echo -e "${BLUE}→ Stopping application containers...${NC}"
    echo -e "  ${YELLOW}(keeping postgres and garage running)${NC}"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}  [DRY RUN] Would stop: api, web${NC}"
    else
        cd "$DOCKER_DIR"
        run_compose stop api web 2>/dev/null || true
    fi
    echo ""
}

# ============================================================================
# Run Migrations
# ============================================================================
run_migrations() {
    echo -e "${BLUE}→ Running database migrations...${NC}"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}  [DRY RUN] Would run: operator/database/migrate-db.sh -y${NC}"
        # Show pending migrations even in dry run
        if [ -f "$PROJECT_ROOT/operator/database/migrate-db.sh" ]; then
            "$PROJECT_ROOT/operator/database/migrate-db.sh" --dry-run 2>/dev/null || true
        fi
    else
        if [ -f "$PROJECT_ROOT/operator/database/migrate-db.sh" ]; then
            "$PROJECT_ROOT/operator/database/migrate-db.sh" -y
        else
            echo -e "${YELLOW}  ⚠ Migration script not found${NC}"
        fi
    fi
    echo ""
}

# ============================================================================
# Start Application
# ============================================================================
start_application() {
    echo -e "${BLUE}→ Starting application with new images...${NC}"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}  [DRY RUN] Would start: api, web${NC}"
    else
        cd "$DOCKER_DIR"
        run_compose up -d api web

        # Wait for health check
        echo -e "${BLUE}  Waiting for API health check...${NC}"
        local api_pattern=$(get_container_pattern api)
        for i in {1..30}; do
            if docker ps --format '{{.Names}} {{.Status}}' | grep -qE "$api_pattern.*healthy"; then
                echo -e "${GREEN}  ✓ API is healthy${NC}"
                break
            fi
            if [ $i -eq 30 ]; then
                echo -e "${YELLOW}  ⚠ API health check timeout (may still be starting)${NC}"
            fi
            sleep 2
        done
    fi
    echo ""
}

# ============================================================================
# Main
# ============================================================================
main() {
    parse_args "$@"

    if [ "$SHOW_HELP" = true ]; then
        show_help
        exit 0
    fi

    echo ""
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${YELLOW}║${NC}  ${BOLD}Platform Upgrade - DRY RUN${NC}                           ${YELLOW}    ║${NC}"
        echo -e "${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
    else
        echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${BLUE}║${NC}  ${BOLD}Platform Upgrade${NC}                                     ${BLUE}    ║${NC}"
        echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    fi
    echo ""

    preflight_check
    show_current_state
    backup_database
    update_images
    stop_application
    run_migrations
    start_application

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}DRY RUN complete - no changes were made${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo "Run without --dry-run to apply these changes:"
        echo "  ./operator.sh upgrade"
    else
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}✅ Upgrade complete${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo "Verify with:"
        echo "  ./operator.sh status"
        echo "  kg health"
    fi
    echo ""
}

# Run main
main "$@"
