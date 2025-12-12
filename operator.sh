#!/bin/bash
# ============================================================================
# operator.sh - Knowledge Graph Platform Lifecycle Manager
#
# Single entry point for platform management. Dispatches to scripts in
# operator/lib/ or executes commands inside the kg-operator container.
#
# Usage:
#   ./operator.sh init               First-time interactive setup
#   ./operator.sh start              Start the platform
#   ./operator.sh stop               Stop the platform
#   ./operator.sh teardown           Remove all containers and data
#   ./operator.sh status             Show platform status
#   ./operator.sh logs [service]     Tail logs
#   ./operator.sh shell              Open shell in operator container
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

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if operator container is running
check_operator() {
    if ! docker ps --format '{{.Names}}' | grep -q "^kg-operator$"; then
        echo -e "${YELLOW}Operator container not running.${NC}"
        echo ""
        echo "Run init first:"
        echo "  ./operator.sh init"
        exit 1
    fi
}

# Show help
show_help() {
    echo -e "${BOLD}Knowledge Graph Platform Manager${NC}"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo -e "${BOLD}Lifecycle Commands:${NC}"
    echo "  init               First-time interactive setup"
    echo "  start              Start the platform (API + web)"
    echo "  stop               Stop the platform"
    echo "  teardown           Remove all containers and data"
    echo ""
    echo -e "${BOLD}Management Commands:${NC}"
    echo "  status             Show platform and container status"
    echo "  config             Update platform configuration"
    echo "  logs [service]     Tail logs (api, web, postgres, garage)"
    echo "  shell              Open interactive shell in operator"
    echo "  help               Show this help"
    echo ""
    echo -e "${BOLD}Stop options:${NC}"
    echo "  --keep-infra       Keep infrastructure running (postgres, garage)"
    echo ""
    echo -e "${BOLD}Teardown options:${NC}"
    echo "  --keep-env         Keep .env secrets file"
    echo ""
    echo -e "${BOLD}Config options:${NC}"
    echo "  --dev true|false   Set development mode"
    echo "  --gpu MODE         Set GPU mode (nvidia, mac, cpu, auto)"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo "  $0 init                     # First-time setup"
    echo "  $0 start                    # Start with saved configuration"
    echo "  $0 stop --keep-infra        # Stop app but keep database"
    echo "  $0 teardown --keep-env      # Full reset, keep secrets"
    echo "  $0 config --gpu nvidia      # Change GPU mode"
    echo "  $0 logs api                 # Tail API logs"
    echo ""
}

# Main command dispatch
case "${1:-help}" in
    init)
        shift
        "$SCRIPT_DIR/quickstart.sh" "$@"
        ;;

    start)
        check_operator
        shift
        docker exec kg-operator python /workspace/operator/platform.py start "$@"
        ;;

    stop)
        check_operator
        shift
        docker exec kg-operator python /workspace/operator/platform.py stop "$@"
        ;;

    teardown)
        shift
        "$SCRIPT_DIR/operator/lib/teardown.sh" "$@"
        ;;

    status)
        check_operator
        docker exec kg-operator python /workspace/operator/platform.py status
        ;;

    config)
        check_operator
        shift
        docker exec kg-operator python /workspace/operator/platform.py config "$@"
        ;;

    logs)
        SERVICE="${2:-api}"
        case "$SERVICE" in
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
                echo "Unknown service: $SERVICE"
                echo "Available: api, web, postgres, garage, operator"
                exit 1
                ;;
        esac
        ;;

    shell)
        check_operator
        docker exec -it kg-operator /bin/bash
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
