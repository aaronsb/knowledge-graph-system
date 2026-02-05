#!/bin/bash
# ============================================================================
# operator.sh - Knowledge Graph Platform Manager (Thin Shim)
# ============================================================================
OPERATOR_VERSION="0.9.0"
# ============================================================================
#
# Minimal host-side script that delegates to operator container.
# Only host-critical operations run directly; everything else via docker exec.
#
# GitHub repository for self-update
KG_REPO="aaronsb/knowledge-graph-system"
KG_REPO_RAW="https://raw.githubusercontent.com/${KG_REPO}/main"
KG_GHCR="ghcr.io/${KG_REPO}"
#
# ============================================================================

set -e

# Colors (disabled if not a terminal)
if [ -t 1 ]; then
    RED=$'\033[0;31m'
    GREEN=$'\033[0;32m'
    YELLOW=$'\033[1;33m'
    BLUE=$'\033[0;34m'
    BOLD=$'\033[1m'
    NC=$'\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    BOLD=''
    NC=''
fi

# Script location
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Detect standalone vs repo install
if [ -d "$SCRIPT_DIR/docker" ]; then
    DOCKER_DIR="$SCRIPT_DIR/docker"
else
    DOCKER_DIR="$SCRIPT_DIR"
fi

CONFIG_FILE="$SCRIPT_DIR/.operator.conf"
ENV_FILE="$SCRIPT_DIR/.env"
OPERATOR_CONTAINER="kg-operator"
POSTGRES_CONTAINER="knowledge-graph-postgres"

# ============================================================================
# Configuration
# ============================================================================

load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
    fi
    DEV_MODE="${DEV_MODE:-false}"
    GPU_MODE="${GPU_MODE:-cpu}"
    CONTAINER_PREFIX="${CONTAINER_PREFIX:-kg}"
    # Dev mode uses local builds by default, standalone uses GHCR
    if [ "$DEV_MODE" = "true" ]; then
        IMAGE_SOURCE="${IMAGE_SOURCE:-local}"
    else
        IMAGE_SOURCE="${IMAGE_SOURCE:-ghcr}"
    fi
}

# Build compose command with overlays
get_compose_cmd() {
    load_config
    local cmd="docker compose -f $DOCKER_DIR/docker-compose.yml"

    # GHCR images overlay (must come before standalone)
    [ "$IMAGE_SOURCE" = "ghcr" ] && [ -f "$DOCKER_DIR/docker-compose.ghcr.yml" ] && cmd="$cmd -f $DOCKER_DIR/docker-compose.ghcr.yml"

    # Standalone mode (curl installer) - removes dev mounts, fixes container names
    [ -f "$DOCKER_DIR/docker-compose.standalone.yml" ] && cmd="$cmd -f $DOCKER_DIR/docker-compose.standalone.yml"

    # SSL overlay (if configured)
    [ -f "$DOCKER_DIR/docker-compose.ssl.yml" ] && cmd="$cmd -f $DOCKER_DIR/docker-compose.ssl.yml"

    # Dev mode overlay (adds hot reload, source mounts)
    [ "$DEV_MODE" = "true" ] && [ -f "$DOCKER_DIR/docker-compose.dev.yml" ] && cmd="$cmd -f $DOCKER_DIR/docker-compose.dev.yml"

    # GPU overlays
    case "$GPU_MODE" in
        nvidia) [ -f "$DOCKER_DIR/docker-compose.gpu-nvidia.yml" ] && cmd="$cmd -f $DOCKER_DIR/docker-compose.gpu-nvidia.yml" ;;
        amd)    [ -f "$DOCKER_DIR/docker-compose.gpu-amd.yml" ] && cmd="$cmd -f $DOCKER_DIR/docker-compose.gpu-amd.yml" ;;
        mac)    [ -f "$DOCKER_DIR/docker-compose.override.mac.yml" ] && cmd="$cmd -f $DOCKER_DIR/docker-compose.override.mac.yml" ;;
    esac

    echo "$cmd --env-file $ENV_FILE"
}

run_compose() {
    $(get_compose_cmd) "$@"
}

# ============================================================================
# Checks
# ============================================================================

check_env() {
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${RED}✗ .env not found. Run ./operator.sh init${NC}"
        exit 1
    fi
}

check_operator() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${OPERATOR_CONTAINER}$"; then
        echo -e "${YELLOW}Operator not running. Starting infrastructure...${NC}"
        cmd_start_infra
    fi
}

wait_for_container() {
    local container=$1
    local max_wait=${2:-30}
    for i in $(seq 1 $max_wait); do
        docker ps --format '{{.Names}} {{.Status}}' | grep -qE "^${container}.*healthy" && return 0
        docker ps --format '{{.Names}}' | grep -q "^${container}$" && [ $i -gt 5 ] && return 0
        sleep 2
    done
    return 1
}

# ============================================================================
# HOST-ONLY: Bootstrap infrastructure (can't run in container - chicken/egg)
# ============================================================================

cmd_start_infra() {
    check_env
    load_config
    cd "$DOCKER_DIR"

    # Start postgres and garage
    echo -e "${BLUE}→ Starting infrastructure (postgres, garage)...${NC}"
    run_compose up -d postgres garage

    # Only start operator if not already running (don't recreate - it's the brain!)
    if docker ps --format '{{.Names}}' | grep -q "^${OPERATOR_CONTAINER}$"; then
        echo -e "${GREEN}✓ Operator already running${NC}"
    else
        echo -e "${BLUE}→ Starting operator...${NC}"
        run_compose up -d operator

        echo -e "${BLUE}→ Waiting for operator...${NC}"
        if wait_for_container "$OPERATOR_CONTAINER" 30; then
            echo -e "${GREEN}✓ Operator ready${NC}"
        else
            echo -e "${RED}✗ Operator failed to start${NC}"
            exit 1
        fi
    fi
}

# ============================================================================
# DELEGATED TO CONTAINER: Complex operations
# ============================================================================

cmd_start() {
    check_env
    load_config

    # Bootstrap: start infra from host
    cmd_start_infra

    # Run migrations via container
    echo -e "${BLUE}→ Running migrations...${NC}"
    docker exec "$OPERATOR_CONTAINER" /workspace/operator/database/migrate-db.sh -y 2>/dev/null || true

    # Start api/web - must run on HOST for dev mode volume mounts to resolve correctly
    # (running compose inside container causes paths like ../api to resolve to /workspace/api)
    echo -e "${BLUE}→ Starting application (api, web)...${NC}"
    cd "$DOCKER_DIR"
    run_compose up -d api web

    # Wait for API health
    echo -e "${BLUE}→ Waiting for API...${NC}"
    for i in {1..30}; do
        if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
            echo -e "${GREEN}✓ API healthy${NC}"
            echo -e "${GREEN}✓ Platform started${NC}"
            return 0
        fi
        sleep 2
    done
    echo -e "${YELLOW}⚠ API may still be starting${NC}"
}

cmd_stop() {
    check_env
    load_config
    cd "$DOCKER_DIR"

    # Simple stop can run on host
    local stop_all=true
    [[ "$1" == "--keep-infra" ]] && stop_all=false

    echo -e "${BLUE}→ Stopping containers...${NC}"
    if [ "$stop_all" = true ]; then
        run_compose stop
    else
        run_compose stop api web
    fi
    echo -e "${GREEN}✓ Stopped${NC}"
}

cmd_upgrade() {
    check_env
    load_config
    cd "$DOCKER_DIR"

    local dry_run=false
    local no_backup=false
    local auto_yes=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run|--whatif) dry_run=true; shift ;;
            --no-backup) no_backup=true; shift ;;
            -y|--yes) auto_yes=true; shift ;;
            --help|-h)
                echo "Usage: ./operator.sh upgrade [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --dry-run     Show what would be done (also: --whatif)"
                echo "  -y, --yes     Skip confirmation prompt"
                echo "  --no-backup   Skip pre-upgrade backup"
                exit 0
                ;;
            *) shift ;;
        esac
    done

    echo -e "${BLUE}${BOLD}Platform Upgrade${NC}"
    echo ""

    # Pre-flight checks
    echo -e "${BLUE}→ Pre-flight checks...${NC}"
    [ -f "$ENV_FILE" ] && echo -e "${GREEN}  ✓ .env exists${NC}" || { echo -e "${RED}  ✗ .env missing${NC}"; exit 1; }
    [ -f "$CONFIG_FILE" ] && echo -e "${GREEN}  ✓ .operator.conf exists${NC}" || { echo -e "${RED}  ✗ .operator.conf missing${NC}"; exit 1; }
    docker ps >/dev/null 2>&1 && echo -e "${GREEN}  ✓ Docker available${NC}" || { echo -e "${RED}  ✗ Docker not running${NC}"; exit 1; }
    echo ""

    # Show config and versions
    echo -e "${BOLD}Configuration:${NC}"
    echo -e "  Image source: ${BLUE}$IMAGE_SOURCE${NC}"
    echo ""
    echo -e "${BOLD}Running versions:${NC}"
    show_versions_table false
    echo ""

    if [ "$dry_run" = true ]; then
        if [ "$IMAGE_SOURCE" = "local" ]; then
            echo -e "${YELLOW}[DRY RUN] Would build images, update infra, run migrations, restart application${NC}"
        else
            echo -e "${YELLOW}[DRY RUN] Would pull images, update infra, run migrations, restart application${NC}"
        fi
        return
    fi

    # Confirmation
    if [ "$auto_yes" = false ]; then
        read -p "Proceed with upgrade? [y/N] " -r
        echo ""
        [[ ! "$REPLY" =~ ^[Yy]$ ]] && echo "Cancelled." && return
    fi

    # Build or pull images
    if [ "$IMAGE_SOURCE" = "local" ]; then
        echo -e "${BLUE}→ Building local images...${NC}"
        run_compose build
    else
        echo -e "${BLUE}→ Pulling images...${NC}"
        run_compose pull
    fi
    echo ""

    # Stop app containers
    echo -e "${BLUE}→ Stopping application containers...${NC}"
    run_compose stop api web 2>/dev/null || true
    echo ""

    # Update infra containers (recreates if image changed, no-op otherwise)
    echo -e "${BLUE}→ Updating infrastructure...${NC}"
    run_compose up -d postgres garage
    echo -e "${BLUE}→ Waiting for postgres...${NC}"
    if wait_for_container "$POSTGRES_CONTAINER" 30; then
        echo -e "${GREEN}  ✓ Postgres ready${NC}"
    else
        echo -e "${RED}  ✗ Postgres failed to start${NC}"
        exit 1
    fi
    echo ""

    # Run migrations via operator container (uses psql)
    echo -e "${BLUE}→ Running migrations...${NC}"
    if docker ps --format '{{.Names}}' | grep -q "^${OPERATOR_CONTAINER}$"; then
        docker exec "$OPERATOR_CONTAINER" /workspace/operator/database/migrate-db.sh -y 2>/dev/null || echo -e "${YELLOW}  ⚠ Migration script not found or failed${NC}"
    else
        echo -e "${YELLOW}  ⚠ Operator container not running, skipping migrations${NC}"
    fi
    echo ""

    # Start application
    echo -e "${BLUE}→ Starting application...${NC}"
    run_compose up -d api web

    # Health check
    echo -e "${BLUE}→ Waiting for API health...${NC}"
    for i in {1..30}; do
        if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
            echo -e "${GREEN}  ✓ API healthy${NC}"
            break
        fi
        [ $i -eq 30 ] && echo -e "${YELLOW}  ⚠ API may still be starting${NC}"
        sleep 2
    done
    echo ""

    echo -e "${BOLD}Current versions:${NC}"
    show_versions_table false
    echo ""

    echo -e "${GREEN}${BOLD}✅ Upgrade complete${NC}"
}

cmd_teardown() {
    check_env
    load_config
    cd "$DOCKER_DIR"

    # Teardown is simple enough for host
    local remove_volumes=false
    local auto_yes=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --full) remove_volumes=true; shift ;;
            -y|--yes) auto_yes=true; shift ;;
            *) shift ;;
        esac
    done

    echo -e "${RED}${BOLD}TEARDOWN${NC}"
    if [ "$auto_yes" = false ]; then
        read -p "Type 'yes' to confirm: " -r
        [[ "$REPLY" != "yes" ]] && echo "Cancelled" && exit 0
    fi

    local flags=""
    [ "$remove_volumes" = true ] && flags="-v"

    run_compose down $flags
    echo -e "${GREEN}✓ Teardown complete${NC}"
}

# ============================================================================
# SIMPLE HOST OPERATIONS
# ============================================================================

cmd_status() {
    echo -e "\n${BOLD}Container Status:${NC}"
    docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' \
        --filter 'name=kg-' --filter 'name=knowledge-graph' 2>/dev/null || \
        echo "  No containers running"
}

# Get container name based on service and mode
get_container_name() {
    local service=$1
    load_config

    case "$service" in
        postgres) echo "${CONTAINER_PREFIX:-knowledge-graph}-postgres" ;;
        garage)   echo "${CONTAINER_PREFIX:-knowledge-graph}-garage" ;;
        operator) echo "kg-operator" ;;
        api|web)
            # Dev mode uses kg-*-dev, standalone uses kg-*
            if [ "$DEV_MODE" = "true" ]; then
                echo "kg-${service}-dev"
            else
                echo "kg-${service}"
            fi
            ;;
        *) echo "kg-$service" ;;
    esac
}

# Read an OCI label from a running container
inspect_label() {
    local container=$1 label=$2
    docker inspect --format "{{index .Config.Labels \"$label\"}}" "$container" 2>/dev/null
}

# Get the target image name for a service (respects IMAGE_SOURCE)
get_image_ref() {
    local service=$1
    if [ "$IMAGE_SOURCE" = "ghcr" ]; then
        echo "${KG_GHCR}/kg-${service}:latest"
    else
        echo "kg-${service}:latest"
    fi
}

# Display version table for platform services
show_versions_table() {
    local show_stale=${1:-false}

    printf "  %-14s %-10s %-10s %-12s %s\n" "Service" "Version" "Commit" "Built" "Image"
    printf "  %-14s %-10s %-10s %-12s %s\n" "-------" "-------" "------" "-----" "-----"

    local any_stale=false
    for service in postgres api web operator; do
        local container=$(get_container_name "$service")

        # Check if running
        if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            printf "  %-14s ${YELLOW}%-10s${NC}\n" "$service" "(stopped)"
            continue
        fi

        local ver=$(inspect_label "$container" "org.opencontainers.image.version")
        local rev=$(inspect_label "$container" "org.opencontainers.image.revision")
        local blt=$(inspect_label "$container" "org.opencontainers.image.created")

        # Normalize "unknown" to empty
        [ "$ver" = "unknown" ] && ver=""
        [ "$rev" = "unknown" ] && rev=""
        [ "$blt" = "unknown" ] && blt=""

        # Truncate built date to date-only
        [ -n "$blt" ] && blt="${blt%%T*}"

        # Short image SHA for display
        local img_sha=$(docker inspect --format '{{.Image}}' "$container" 2>/dev/null)
        local short_sha=""
        [ -n "$img_sha" ] && short_sha="${img_sha:7:12}"

        # Stale detection: compare running image vs locally available image
        local stale_flag=""
        if [ "$show_stale" = "true" ]; then
            local image_ref
            # Dev-mode postgres uses stock apache/age, not kg-postgres
            if [ "$service" = "postgres" ] && [ "$DEV_MODE" = "true" ]; then
                image_ref="apache/age"
            else
                image_ref=$(get_image_ref "$service")
            fi
            local local_sha=$(docker image inspect --format '{{.Id}}' "$image_ref" 2>/dev/null)
            if [ -n "$local_sha" ] && [ -n "$img_sha" ] && [ "$img_sha" != "$local_sha" ]; then
                stale_flag=" ${YELLOW}↑${NC}"
                any_stale=true
            fi
        fi

        printf "  %-14s %-10s %-10s %-12s %s%b\n" \
            "$service" "${ver:--}" "${rev:--}" "${blt:--}" "${short_sha:--}" "$stale_flag"
    done

    # operator.sh script version
    printf "  %-14s %-10s %s\n" "operator.sh" "$OPERATOR_VERSION" "(host script)"

    if [ "$show_stale" = "true" ] && [ "$any_stale" = "true" ]; then
        echo ""
        echo -e "  ${YELLOW}↑ = newer image available, run './operator.sh upgrade' to apply${NC}"
    fi
}

cmd_versions() {
    load_config
    echo ""
    echo -e "${BOLD}Platform Versions${NC} (operator.sh v${OPERATOR_VERSION})"
    echo ""
    show_versions_table true
}

cmd_logs() {
    local service="${1:-api}"
    shift 2>/dev/null || true

    local container=$(get_container_name "$service")
    docker logs "$@" "$container"
}

cmd_restart() {
    local service="${1:-}"
    [ -z "$service" ] && echo "Usage: $0 restart <service>" && exit 1

    local container=$(get_container_name "$service")
    docker restart "$container"
    echo -e "${GREEN}✓ $service restarted${NC}"
}

cmd_update() {
    check_env
    load_config
    cd "$DOCKER_DIR"

    local dry_run=false
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run|--whatif) dry_run=true; shift ;;
            *) break ;;
        esac
    done

    echo -e "\n${BOLD}Current versions:${NC}"
    show_versions_table false
    echo ""

    if [ "$dry_run" = true ]; then
        if [ "$IMAGE_SOURCE" = "local" ]; then
            echo -e "${YELLOW}[WHATIF] Would rebuild local images${NC}"
        else
            echo -e "${YELLOW}[WHATIF] Would pull latest images from GHCR${NC}"
        fi
        return
    fi

    if [ "$IMAGE_SOURCE" = "local" ]; then
        echo -e "${BLUE}→ Building local images...${NC}"
        run_compose build "$@"
    else
        echo -e "${BLUE}→ Pulling images...${NC}"
        run_compose pull "$@"
    fi

    echo ""
    echo -e "${BOLD}Updated images:${NC}"
    show_versions_table true
    echo ""
    echo -e "${GREEN}✓ Images updated. Run './operator.sh upgrade' to apply.${NC}"
}

# ============================================================================
# CONTAINER DELEGATION: Config commands
# ============================================================================

# Run command in operator container
run_in_operator() {
    check_operator
    # -t for TTY (colors/formatting)
    # -i only if stdin is a real TTY (needed for interactive prompts)
    local docker_flags=""
    if [ -t 0 ] && [ -t 1 ]; then
        docker_flags="-it"
    elif [ -t 1 ]; then
        docker_flags="-t"
    fi
    docker exec $docker_flags "$OPERATOR_CONTAINER" "$@"
}

cmd_admin()       { run_in_operator python /workspace/operator/configure.py admin "$@"; }
cmd_ai_provider() { run_in_operator python /workspace/operator/configure.py ai-provider "$@"; }
cmd_embedding()   { run_in_operator python /workspace/operator/configure.py embedding "$@"; }
cmd_api_key()     { run_in_operator python /workspace/operator/configure.py api-key "$@"; }
cmd_query() {
    # Run SQL query against PostgreSQL (host-side, uses docker compose)
    local query="$1"
    if [ -z "$query" ]; then
        echo -e "${RED}Usage: $0 query 'SQL query'${NC}"
        echo ""
        echo "Examples:"
        echo "  $0 query 'SELECT count(*) FROM kg_auth.users'"
        echo "  $0 query 'SELECT username, primary_role FROM kg_auth.users'"
        exit 1
    fi
    $(get_compose_cmd) exec -T postgres psql -U admin -d knowledge_graph -c "$query"
}
cmd_garage()      { run_in_operator /workspace/operator/lib/garage-manager.sh "$@"; }

# ============================================================================
# Help
# ============================================================================

show_help() {
    cat << EOF
${BOLD}Knowledge Graph Platform Manager${NC} v${OPERATOR_VERSION}

Usage: $0 <command> [options]

${BOLD}Lifecycle:${NC}
  start              Start platform (infra + app)
  stop [--keep-infra] Stop platform
  restart <service>  Restart a service
  upgrade            Pull, migrate, restart
  update             Pull images only
  teardown [--full]  Remove containers (--full: +volumes)

${BOLD}Management:${NC}
  status             Show container status
  versions           Show version info for all containers
  logs <service> [-f] View logs (default: api)
  shell              Open shell in operator container

${BOLD}Configuration:${NC}
  admin              Manage admin user
  ai-provider        Configure AI extraction
  embedding          Configure embeddings
  api-key            Store API keys

${BOLD}Database:${NC}
  query 'SQL'        Run SQL query (also: pg)

${BOLD}Infrastructure:${NC}
  garage             Manage Garage storage (status, init, repair)

${BOLD}Maintenance:${NC}
  self-update        Update operator.sh and operator container

${BOLD}Development (repo only):${NC}
  init               Guided setup
  init --headless    Automated setup

EOF
}

# ============================================================================
# Main
# ============================================================================

case "${1:-help}" in
    # Init: only in repo mode
    init)
        shift
        if [ -f "$SCRIPT_DIR/operator/lib/guided-init.sh" ]; then
            [[ "$1" == "--headless" ]] && "$SCRIPT_DIR/operator/lib/headless-init.sh" "$@" || "$SCRIPT_DIR/operator/lib/guided-init.sh" "$@"
        else
            echo -e "${RED}Init only available in repo mode${NC}"
            exit 1
        fi
        ;;

    # Lifecycle
    start)    shift; cmd_start "$@" ;;
    stop)     shift; cmd_stop "$@" ;;
    restart)  shift; cmd_restart "$@" ;;
    upgrade)  shift; cmd_upgrade "$@" ;;
    update)   shift; cmd_update "$@" ;;
    teardown) shift; cmd_teardown "$@" ;;

    # Management
    status)   cmd_status ;;
    versions) cmd_versions ;;
    logs)     shift; cmd_logs "$@" ;;
    shell)  check_operator; docker exec -it "$OPERATOR_CONTAINER" /bin/bash ;;

    # Config (delegated)
    admin)       shift; cmd_admin "$@" ;;
    ai-provider) shift; cmd_ai_provider "$@" ;;
    embedding)   shift; cmd_embedding "$@" ;;
    api-key)     shift; cmd_api_key "$@" ;;
    query|pg)    shift; cmd_query "$@" ;;

    # Infrastructure
    garage)      shift; cmd_garage "$@" ;;

    # SSL
    recert)
        check_operator
        docker exec "$OPERATOR_CONTAINER" /workspace/operator/lib/recert.sh "$@"
        ;;

    # Self-update: update operator.sh and operator container
    self-update)
        echo -e "${BLUE}${BOLD}Self-Update${NC}"
        echo ""

        # Check docker permissions
        if ! docker ps >/dev/null 2>&1; then
            echo -e "${RED}✗ Cannot access Docker. Try: sudo ./operator.sh self-update${NC}"
            exit 1
        fi

        # Check write permissions to script directory
        if [ ! -w "$SCRIPT_DIR" ]; then
            echo -e "${RED}✗ Cannot write to $SCRIPT_DIR. Try: sudo ./operator.sh self-update${NC}"
            exit 1
        fi

        local_version="$OPERATOR_VERSION"
        container_version=""

        echo -e "${BLUE}→ Checking versions...${NC}"
        echo -e "  Local:     ${BOLD}$local_version${NC}"

        # Get version from container (if running)
        if docker ps --format '{{.Names}}' | grep -q "^${OPERATOR_CONTAINER}$"; then
            container_version=$(docker exec "$OPERATOR_CONTAINER" grep '^OPERATOR_VERSION=' /etc/kg/operator.sh 2>/dev/null | cut -d'"' -f2 || echo "")
            if [ -n "$container_version" ]; then
                echo -e "  Container: ${BOLD}$container_version${NC}"
            else
                echo -e "  Container: ${YELLOW}unknown${NC}"
            fi
        else
            echo -e "  Container: ${YELLOW}not running${NC}"
        fi
        echo ""

        # Compare versions (simple string comparison - newer versions should sort higher)
        update_script=false
        if [ -n "$container_version" ] && [ "$container_version" != "$local_version" ]; then
            # Use sort -V for version comparison
            newer=$(printf '%s\n%s\n' "$local_version" "$container_version" | sort -V | tail -1)
            if [ "$newer" = "$container_version" ] && [ "$newer" != "$local_version" ]; then
                echo -e "${BLUE}→ Container has newer operator.sh ($container_version)${NC}"
                update_script=true
            fi
        fi

        # Update operator.sh from container if newer
        if [ "$update_script" = true ]; then
            echo -e "${BLUE}→ Extracting operator.sh from container...${NC}"
            ORIG_OWNER=$(stat -c '%u:%g' "$SCRIPT_DIR/operator.sh" 2>/dev/null || echo "")
            if docker cp "$OPERATOR_CONTAINER":/etc/kg/operator.sh "$SCRIPT_DIR/operator.sh.new"; then
                chmod +x "$SCRIPT_DIR/operator.sh.new"
                if [ -n "$ORIG_OWNER" ]; then
                    chown "$ORIG_OWNER" "$SCRIPT_DIR/operator.sh.new" 2>/dev/null || true
                fi
                mv "$SCRIPT_DIR/operator.sh.new" "$SCRIPT_DIR/operator.sh"
                echo -e "${GREEN}  ✓ operator.sh updated to $container_version${NC}"
            else
                echo -e "${RED}  ✗ Failed to extract operator.sh${NC}"
            fi
        else
            echo -e "${GREEN}  ✓ operator.sh is current${NC}"
        fi

        # Always pull and recreate operator container
        echo ""
        echo -e "${BLUE}→ Updating operator container...${NC}"

        # Pull latest operator image
        echo -e "  Pulling ${KG_GHCR}/kg-operator:latest..."
        if docker pull "${KG_GHCR}/kg-operator:latest" >/dev/null 2>&1; then
            echo -e "${GREEN}  ✓ Image pulled${NC}"
        else
            echo -e "${RED}  ✗ Failed to pull operator image${NC}"
            exit 1
        fi

        # Get current container config for recreation
        load_config
        install_dir="$SCRIPT_DIR"

        # Stop and remove old container
        echo -e "  Recreating container..."
        docker rm -f "$OPERATOR_CONTAINER" >/dev/null 2>&1 || true

        # Start new container with same mounts as install.sh creates
        docker run -d \
            --name "$OPERATOR_CONTAINER" \
            --network knowledge-graph-network \
            --env-file "$ENV_FILE" \
            -e COMPOSE_PROJECT_NAME=knowledge-graph \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$install_dir:/project" \
            "${KG_GHCR}/kg-operator:latest" >/dev/null

        echo -e "${GREEN}  ✓ Operator container updated${NC}"

        # Check if new container has newer script
        echo ""
        new_container_version=$(docker exec "$OPERATOR_CONTAINER" grep '^OPERATOR_VERSION=' /etc/kg/operator.sh 2>/dev/null | cut -d'"' -f2 || echo "")
        if [ -n "$new_container_version" ] && [ "$new_container_version" != "$local_version" ] && [ "$update_script" = false ]; then
            newer=$(printf '%s\n%s\n' "$local_version" "$new_container_version" | sort -V | tail -1)
            if [ "$newer" = "$new_container_version" ]; then
                echo -e "${YELLOW}Note: New container has operator.sh $new_container_version${NC}"
                echo -e "${YELLOW}Run './operator.sh self-update' again to update the script${NC}"
            fi
        fi

        echo ""
        echo -e "${GREEN}${BOLD}✅ Self-update complete${NC}"
        ;;

    # Help
    help|--help|-h) show_help ;;

    *) echo -e "${RED}Unknown: $1${NC}"; show_help; exit 1 ;;
esac
