#!/bin/bash
# ============================================================================
# operator.sh - Knowledge Graph Platform Manager
#
# Single entry point for platform lifecycle and configuration.
# Runs on HOST - handles docker-compose directly (no docker-in-docker).
#
# Usage:
#   ./operator.sh init               Guided first-time setup
#   ./operator.sh start              Start the platform
#   ./operator.sh stop               Stop the platform
#   ./operator.sh status             Show platform status
#   ./operator.sh restart <service>  Restart a service
#   ./operator.sh rebuild <service>  Rebuild and restart a service
#   ./operator.sh logs [service]     Tail logs
#   ./operator.sh shell              Open shell in operator container
#   ./operator.sh teardown           Remove containers and optionally data
#
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Get script directory (project root)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOCKER_DIR="$SCRIPT_DIR/docker"
CONFIG_FILE="$SCRIPT_DIR/.operator.conf"
ENV_FILE="$SCRIPT_DIR/.env"

# ============================================================================
# Configuration Management
# ============================================================================

# Load saved configuration
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
    else
        # Defaults
        DEV_MODE=false
        GPU_MODE=cpu
    fi
}

# Save configuration
save_config() {
    cat > "$CONFIG_FILE" << EOF
# Operator configuration (auto-generated)
# Edit with: ./operator.sh config --dev true --gpu nvidia
DEV_MODE=$DEV_MODE
GPU_MODE=$GPU_MODE
INITIALIZED_AT=${INITIALIZED_AT:-$(date -Iseconds)}
EOF
    echo -e "${GREEN}✓ Configuration saved to .operator.conf${NC}"
}

# Detect GPU on host
detect_gpu() {
    # Check for Mac
    if [[ "$(uname)" == "Darwin" ]]; then
        echo "mac"
        return
    fi

    # Check for NVIDIA GPU
    if command -v nvidia-smi &> /dev/null; then
        if nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | grep -q .; then
            local gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
            echo -e "${GREEN}Detected NVIDIA GPU: $gpu_name${NC}" >&2
            echo "nvidia"
            return
        fi
    fi

    echo "cpu"
}

# Build docker-compose command with appropriate files
get_compose_cmd() {
    load_config

    local cmd="docker-compose -f $DOCKER_DIR/docker-compose.yml"

    if [ "$DEV_MODE" = "true" ]; then
        cmd="$cmd -f $DOCKER_DIR/docker-compose.dev.yml"
    fi

    case "$GPU_MODE" in
        nvidia)
            cmd="$cmd -f $DOCKER_DIR/docker-compose.gpu-nvidia.yml"
            ;;
        mac)
            cmd="$cmd -f $DOCKER_DIR/docker-compose.override.mac.yml"
            ;;
    esac

    cmd="$cmd --env-file $ENV_FILE"
    echo "$cmd"
}

# ============================================================================
# Prerequisites Check
# ============================================================================

check_env() {
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${RED}✗ .env file not found${NC}"
        echo ""
        echo "Run init first to generate secrets:"
        echo "  ./operator.sh init"
        exit 1
    fi
}

check_operator() {
    if ! docker ps --format '{{.Names}}' | grep -q "^kg-operator$"; then
        echo -e "${YELLOW}Operator container not running.${NC}"
        echo ""
        echo "Start infrastructure first:"
        echo "  ./operator.sh start"
        exit 1
    fi
}

# ============================================================================
# Lifecycle Commands
# ============================================================================

cmd_start() {
    check_env
    load_config

    echo -e "\n${BOLD}Starting Knowledge Graph Platform${NC}"
    echo -e "  Mode: ${BLUE}$([ "$DEV_MODE" = "true" ] && echo "development" || echo "production")${NC}"
    echo -e "  GPU:  ${BLUE}$GPU_MODE${NC}"
    echo ""

    # Export config for child scripts
    export DEV_MODE GPU_MODE

    # Start infrastructure (postgres, garage, operator) with migrations
    "$SCRIPT_DIR/operator/lib/start-infra.sh"

    # Start application (api, web)
    "$SCRIPT_DIR/operator/lib/start-app.sh"

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ Platform started${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  API: ${BLUE}http://localhost:8000${NC}"
    echo -e "  Web: ${BLUE}http://localhost:3000${NC}"
    echo ""
}

cmd_stop() {
    check_env

    # Pass through arguments to stop script
    "$SCRIPT_DIR/operator/lib/stop.sh" "$@"
}

cmd_restart() {
    local service="${1:-}"
    if [ -z "$service" ]; then
        echo -e "${RED}Usage: $0 restart <service>${NC}"
        echo "Services: api, web, postgres, garage, operator"
        exit 1
    fi

    echo -e "${BLUE}→ Restarting $service...${NC}"

    case "$service" in
        api)
            docker restart kg-api-dev 2>/dev/null || docker restart knowledge-graph-api
            ;;
        web)
            docker restart kg-web-dev 2>/dev/null || docker restart knowledge-graph-web
            ;;
        postgres)
            docker restart knowledge-graph-postgres
            ;;
        garage)
            docker restart knowledge-graph-garage
            ;;
        operator)
            docker restart kg-operator
            ;;
        *)
            echo -e "${RED}Unknown service: $service${NC}"
            exit 1
            ;;
    esac

    echo -e "${GREEN}✓ $service restarted${NC}"
}

cmd_rebuild() {
    local service="${1:-}"
    if [ -z "$service" ]; then
        echo -e "${RED}Usage: $0 rebuild <service>${NC}"
        echo "Services: api, web"
        echo ""
        echo -e "${YELLOW}Note: postgres/garage use stock images, use teardown + init to recreate${NC}"
        exit 1
    fi

    check_env
    load_config

    case "$service" in
        api|web)
            echo -e "${BLUE}→ Rebuilding $service...${NC}"
            local compose_cmd=$(get_compose_cmd)
            $compose_cmd stop $service
            $compose_cmd rm -f $service
            $compose_cmd up -d --build $service
            echo -e "${GREEN}✓ $service rebuilt and started${NC}"
            ;;
        postgres|garage)
            echo -e "${RED}Cannot rebuild $service - uses stock image${NC}"
            echo "Use: ./operator.sh teardown --full && ./operator.sh init"
            exit 1
            ;;
        *)
            echo -e "${RED}Unknown service: $service${NC}"
            exit 1
            ;;
    esac
}

cmd_status() {
    echo -e "\n${BOLD}Platform Configuration:${NC}"
    if [ -f "$CONFIG_FILE" ]; then
        load_config
        echo -e "  Dev mode: ${BLUE}$DEV_MODE${NC}"
        echo -e "  GPU mode: ${BLUE}$GPU_MODE${NC}"
        echo -e "  Initialized: ${BLUE}${INITIALIZED_AT:-never}${NC}"
    else
        echo -e "  ${YELLOW}Not configured (run ./operator.sh init)${NC}"
    fi

    echo -e "\n${BOLD}Container Status:${NC}"
    docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' \
        --filter 'name=kg-' --filter 'name=knowledge-graph' 2>/dev/null || \
        echo "  No containers running"
    echo ""
}

cmd_config() {
    load_config

    while [[ $# -gt 0 ]]; do
        case $1 in
            --dev)
                DEV_MODE="$2"
                shift 2
                ;;
            --gpu)
                if [ "$2" = "auto" ]; then
                    GPU_MODE=$(detect_gpu)
                else
                    GPU_MODE="$2"
                fi
                shift 2
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                exit 1
                ;;
        esac
    done

    save_config
    echo -e "\n${BOLD}Current configuration:${NC}"
    echo -e "  Dev mode: $DEV_MODE"
    echo -e "  GPU mode: $GPU_MODE"
    echo -e "\n${YELLOW}Restart platform to apply changes: ./operator.sh stop && ./operator.sh start${NC}"
}

cmd_logs() {
    local service="${1:-api}"
    case "$service" in
        api)
            docker logs -f kg-api-dev 2>/dev/null || docker logs -f knowledge-graph-api
            ;;
        web)
            docker logs -f kg-web-dev 2>/dev/null || docker logs -f knowledge-graph-web
            ;;
        postgres)
            docker logs -f knowledge-graph-postgres
            ;;
        garage)
            docker logs -f knowledge-graph-garage
            ;;
        operator)
            docker logs -f kg-operator
            ;;
        *)
            echo -e "${RED}Unknown service: $service${NC}"
            echo "Available: api, web, postgres, garage, operator"
            exit 1
            ;;
    esac
}

# ============================================================================
# Help
# ============================================================================

show_help() {
    echo -e "${BOLD}Knowledge Graph Platform Manager${NC}"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo -e "${BOLD}Lifecycle Commands:${NC}"
    echo "  init               Guided first-time setup"
    echo "  start              Start the platform"
    echo "  stop               Stop the platform"
    echo "  teardown           Remove containers (keeps data by default)"
    echo ""
    echo -e "${BOLD}Service Commands:${NC}"
    echo "  restart <service>  Restart a service (api, web, postgres, garage)"
    echo "  rebuild <service>  Rebuild and restart (api, web only)"
    echo ""
    echo -e "${BOLD}Management Commands:${NC}"
    echo "  status             Show platform and container status"
    echo "  config [options]   Update platform configuration"
    echo "  logs [service]     Tail logs (default: api)"
    echo "  shell              Open shell in operator container"
    echo "  help               Show this help"
    echo ""
    echo -e "${BOLD}Stop Options:${NC}"
    echo "  --keep-infra       Keep infrastructure running (postgres, garage)"
    echo ""
    echo -e "${BOLD}Teardown Options:${NC}"
    echo "  --keep-env         Keep .env secrets file"
    echo "  --include-operator Also remove operator container"
    echo "  --full             Remove everything (volumes, images, operator)"
    echo ""
    echo -e "${BOLD}Config Options:${NC}"
    echo "  --dev true|false   Set development mode"
    echo "  --gpu <mode>       Set GPU mode (nvidia, mac, cpu, auto)"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo "  $0 init                    # First-time setup"
    echo "  $0 start                   # Start with saved config"
    echo "  $0 stop --keep-infra       # Stop app, keep database"
    echo "  $0 config --gpu nvidia     # Change GPU mode"
    echo "  $0 rebuild api             # Rebuild API after code changes"
    echo "  $0 logs api                # Tail API logs"
    echo ""
}

# ============================================================================
# Main Command Dispatch
# ============================================================================

case "${1:-help}" in
    init)
        shift
        "$SCRIPT_DIR/operator/lib/guided-init.sh" "$@"
        ;;
    start)
        shift
        cmd_start "$@"
        ;;
    stop)
        shift
        cmd_stop "$@"
        ;;
    restart)
        shift
        cmd_restart "$@"
        ;;
    rebuild)
        shift
        cmd_rebuild "$@"
        ;;
    status)
        cmd_status
        ;;
    config)
        shift
        cmd_config "$@"
        ;;
    logs)
        shift
        cmd_logs "$@"
        ;;
    shell)
        check_operator
        docker exec -it kg-operator /bin/bash
        ;;
    teardown)
        shift
        "$SCRIPT_DIR/operator/lib/teardown.sh" "$@"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
