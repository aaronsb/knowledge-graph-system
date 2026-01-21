#!/bin/bash
# ============================================================================
# operator.sh - Knowledge Graph Platform Manager (Thin Shim)
#
# Minimal host-side script that delegates to operator container.
# Only host-critical operations run directly; everything else via docker exec.
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
    IMAGE_SOURCE="${IMAGE_SOURCE:-ghcr}"
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

    # Delegate: migrations, garage init, app start → container
    echo -e "${BLUE}→ Running platform startup...${NC}"
    docker exec "$OPERATOR_CONTAINER" /workspace/operator/lib/start-platform.sh
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
    check_operator

    # Delegate upgrade to container (it can pull, migrate, restart)
    docker exec "$OPERATOR_CONTAINER" /workspace/operator/lib/upgrade.sh "$@"
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

    echo -e "${BLUE}→ Pulling images...${NC}"
    run_compose pull "$@"
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
cmd_query()       { run_in_operator python /workspace/operator/configure.py query "$@"; }

# ============================================================================
# Help
# ============================================================================

show_help() {
    cat << EOF
${BOLD}Knowledge Graph Platform Manager${NC}

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
  logs <service> [-f] View logs (default: api)
  shell              Open shell in operator container

${BOLD}Configuration:${NC}
  admin              Manage admin user
  ai-provider        Configure AI extraction
  embedding          Configure embeddings
  api-key            Store API keys

${BOLD}Maintenance:${NC}
  self-update        Update operator.sh from container

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
    status) cmd_status ;;
    logs)   shift; cmd_logs "$@" ;;
    shell)  check_operator; docker exec -it "$OPERATOR_CONTAINER" /bin/bash ;;

    # Config (delegated)
    admin)       shift; cmd_admin "$@" ;;
    ai-provider) shift; cmd_ai_provider "$@" ;;
    embedding)   shift; cmd_embedding "$@" ;;
    api-key)     shift; cmd_api_key "$@" ;;
    query|pg)    shift; cmd_query "$@" ;;

    # SSL
    recert)
        check_operator
        docker exec "$OPERATOR_CONTAINER" /workspace/operator/lib/recert.sh "$@"
        ;;

    # Self-update: extract operator.sh from container
    self-update)
        check_operator
        echo -e "${BLUE}→ Extracting operator.sh from container...${NC}"
        # Preserve original ownership
        ORIG_OWNER=$(stat -c '%u:%g' "$SCRIPT_DIR/operator.sh" 2>/dev/null || echo "")
        if docker cp "$OPERATOR_CONTAINER":/etc/kg/operator.sh "$SCRIPT_DIR/operator.sh.new"; then
            chmod +x "$SCRIPT_DIR/operator.sh.new"
            if [ -n "$ORIG_OWNER" ]; then
                chown "$ORIG_OWNER" "$SCRIPT_DIR/operator.sh.new" 2>/dev/null || true
            fi
            mv "$SCRIPT_DIR/operator.sh.new" "$SCRIPT_DIR/operator.sh"
            echo -e "${GREEN}✓ operator.sh updated from container${NC}"
        else
            echo -e "${RED}✗ Failed to extract operator.sh${NC}"
            echo "  Make sure the operator container has /etc/kg/operator.sh"
            exit 1
        fi
        ;;

    # Help
    help|--help|-h) show_help ;;

    *) echo -e "${RED}Unknown: $1${NC}"; show_help; exit 1 ;;
esac
