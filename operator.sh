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
#   ./operator.sh logs [service] [-f] Show logs (last 100 lines, -f to follow)
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

# Source common functions for container name resolution
if [ -f "$SCRIPT_DIR/operator/lib/common.sh" ]; then
    source "$SCRIPT_DIR/operator/lib/common.sh"
fi

# Load saved configuration
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
    fi
    # Defaults if not set
    DEV_MODE="${DEV_MODE:-false}"
    GPU_MODE="${GPU_MODE:-cpu}"
    CONTAINER_PREFIX="${CONTAINER_PREFIX:-knowledge-graph}"
    CONTAINER_SUFFIX="${CONTAINER_SUFFIX:-}"
    COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
    IMAGE_SOURCE="${IMAGE_SOURCE:-local}"
}

# Save configuration
save_config() {
    cat > "$CONFIG_FILE" << EOF
# Operator configuration (auto-generated)
# Edit with: ./operator.sh config --dev true --gpu nvidia
DEV_MODE=$DEV_MODE
GPU_MODE=$GPU_MODE
CONTAINER_PREFIX=${CONTAINER_PREFIX:-knowledge-graph}
CONTAINER_SUFFIX=${CONTAINER_SUFFIX:-}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.yml}
IMAGE_SOURCE=${IMAGE_SOURCE:-local}
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
    load_config
    local operator_container=$(get_container_name operator)
    if ! docker ps --format '{{.Names}}' | grep -q "^${operator_container}$"; then
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

    load_config

    echo -e "${BLUE}→ Restarting $service...${NC}"

    local container=""
    case "$service" in
        api|web|postgres|garage|operator)
            container=$(get_container_name "$service")
            ;;
        *)
            echo -e "${RED}Unknown service: $service${NC}"
            exit 1
            ;;
    esac

    if docker restart "$container" 2>/dev/null; then
        echo -e "${GREEN}✓ $service restarted (container: $container)${NC}"
    else
        echo -e "${RED}✗ Failed to restart $container${NC}"
        exit 1
    fi
}

cmd_rebuild() {
    local service="${1:-}"
    if [ -z "$service" ]; then
        echo -e "${RED}Usage: $0 rebuild <service>${NC}"
        echo "Services: api, web, operator"
        echo ""
        echo -e "${YELLOW}Note: postgres/garage use stock images, use teardown + init to recreate${NC}"
        exit 1
    fi

    check_env
    load_config

    case "$service" in
        api|web|operator)
            echo -e "${BLUE}→ Rebuilding $service...${NC}"
            local compose_cmd=$(get_compose_cmd)
            $compose_cmd stop $service 2>/dev/null || true
            $compose_cmd rm -f $service 2>/dev/null || true
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
    local follow=""
    local lines="100"
    local service=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -f|--follow)
                follow="-f"
                shift
                ;;
            -n|--lines)
                lines="$2"
                shift 2
                ;;
            -*)
                echo -e "${RED}Unknown option: $1${NC}"
                echo "Usage: ./operator.sh logs [service] [-f|--follow] [-n|--lines N]"
                exit 1
                ;;
            *)
                service="$1"
                shift
                ;;
        esac
    done

    # Default to api if no service specified
    service="${service:-api}"

    load_config

    local container=""
    case "$service" in
        api|web|postgres|garage|operator)
            container=$(get_container_name "$service")
            ;;
        *)
            echo -e "${RED}Unknown service: $service${NC}"
            echo "Available: api, web, postgres, garage, operator"
            exit 1
            ;;
    esac

    # Check if container exists
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        echo -e "${RED}Container '$container' not found${NC}"
        exit 1
    fi

    docker logs --tail "$lines" $follow "$container"
}

cmd_query() {
    check_env

    # Load credentials from .env
    source "$ENV_FILE"
    load_config

    local query="$1"

    if [ -z "$query" ]; then
        echo -e "${RED}Usage: $0 query 'SQL query here'${NC}"
        echo ""
        echo "Examples:"
        echo "  $0 query 'SELECT count(*) FROM pg_stat_activity'"
        echo "  $0 query 'SHOW max_connections'"
        echo ""
        echo "For multi-line queries, use single quotes:"
        echo "  $0 query '"
        echo "    SELECT state, count(*)"
        echo "    FROM pg_stat_activity"
        echo "    GROUP BY state"
        echo "  '"
        exit 1
    fi

    # Get postgres container name
    local postgres_container=$(get_container_name postgres)

    # Run query against postgres container
    docker exec "$postgres_container" \
        psql -U "${POSTGRES_USER:-admin}" \
             -d "${POSTGRES_DB:-knowledge_graph}" \
             -c "$query"
}

cmd_update() {
    check_env
    load_config

    local service="${1:-}"

    echo -e "\n${BOLD}Pulling latest images${NC}"
    echo -e "  Source: ${BLUE}${IMAGE_SOURCE:-ghcr}${NC}"
    echo ""

    # Detect standalone vs repo install for DOCKER_DIR
    local docker_dir="$SCRIPT_DIR/docker"
    if [ ! -d "$docker_dir" ]; then
        docker_dir="$SCRIPT_DIR"
    fi

    cd "$docker_dir"

    # Build compose command with appropriate overlays
    local compose_cmd="docker compose -f docker-compose.yml"
    if [ "$IMAGE_SOURCE" = "ghcr" ] && [ -f "docker-compose.ghcr.yml" ]; then
        compose_cmd="$compose_cmd -f docker-compose.ghcr.yml"
    fi
    compose_cmd="$compose_cmd --env-file $ENV_FILE"

    if [ -n "$service" ]; then
        # Update specific service
        case "$service" in
            api|web|operator)
                echo -e "${BLUE}→ Pulling $service...${NC}"
                if [ "$IMAGE_SOURCE" = "ghcr" ] || [ "$IMAGE_SOURCE" = "" ]; then
                    $compose_cmd pull "$service"
                else
                    echo -e "${YELLOW}  Local build - use 'rebuild $service' instead${NC}"
                    return 1
                fi
                echo ""
                echo -e "${GREEN}✓ $service image updated${NC}"
                echo ""
                echo "To apply the update:"
                echo "  $0 restart $service"
                ;;
            postgres|garage)
                echo -e "${YELLOW}$service version is pinned in docker-compose.yml${NC}"
                echo ""
                echo "To update $service:"
                echo "  1. Edit docker-compose.yml and update the image tag"
                echo "  2. $0 update $service  # Pull new version"
                echo "  3. $0 restart $service # Apply (caution: may need migration)"
                echo ""
                if [ "$service" = "postgres" ]; then
                    echo -e "${RED}Warning: PostgreSQL upgrades may require data migration${NC}"
                    echo "Back up your data before upgrading: operator/database/backup-database.sh"
                fi
                ;;
            *)
                echo -e "${RED}Unknown service: $service${NC}"
                echo "Services: api, web, operator"
                return 1
                ;;
        esac
    else
        # Update all services
        echo -e "${BLUE}→ Pulling all images...${NC}"
        if [ "$IMAGE_SOURCE" = "ghcr" ] || [ "$IMAGE_SOURCE" = "" ]; then
            $compose_cmd pull
        else
            echo -e "${YELLOW}  Local build - use 'rebuild' instead${NC}"
            return 1
        fi
        echo ""
        echo -e "${GREEN}✓ Images updated${NC}"
        echo ""
        echo "To apply updates:"
        echo "  $0 upgrade           # Full upgrade with migrations"
        echo "  $0 restart <service> # Restart specific service"
    fi
}

cmd_admin() {
    check_operator
    load_config

    local operator_container=$(get_container_name operator)
    local password=""
    local action="status"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --password)
                password="$2"
                action="set-password"
                shift 2
                ;;
            status|--status)
                action="status"
                shift
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                echo "Usage: $0 admin [--password PASSWORD]"
                exit 1
                ;;
        esac
    done

    case "$action" in
        set-password)
            if [ -z "$password" ]; then
                echo -e "${RED}Password is required${NC}"
                exit 1
            fi
            docker exec "$operator_container" python /workspace/operator/configure.py admin --password "$password"
            ;;
        status)
            docker exec "$operator_container" python /workspace/operator/configure.py status
            ;;
    esac
}

cmd_recert() {
    local force=false
    local dns_provider=""
    local dns_key=""
    local dns_secret=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force)
                force=true
                shift
                ;;
            --dns)
                dns_provider="$2"
                shift 2
                ;;
            --dns-key)
                dns_key="$2"
                shift 2
                ;;
            --dns-secret)
                dns_secret="$2"
                shift 2
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                echo "Usage: $0 recert [--force] [--dns PROVIDER --dns-key KEY [--dns-secret SECRET]]"
                exit 1
                ;;
        esac
    done

    local install_dir="$SCRIPT_DIR"
    local certs_dir="$install_dir/certs"
    local acme_home="$HOME/.acme.sh"

    # Load hostname from .env
    if [ -f "$ENV_FILE" ]; then
        source "$ENV_FILE"
    fi

    local hostname="${PUBLIC_HOSTNAME:-}"
    if [ -z "$hostname" ]; then
        echo -e "${RED}Could not determine hostname from .env${NC}"
        echo "Set PUBLIC_HOSTNAME in .env or use install.sh to configure SSL"
        exit 1
    fi

    echo -e "\n${BOLD}SSL Certificate Management${NC}"
    echo -e "  Hostname: ${BLUE}$hostname${NC}"

    # Check for existing acme.sh certificate
    if [ -d "$acme_home/${hostname}_ecc" ] || [ -d "$acme_home/$hostname" ]; then
        echo -e "  acme.sh cert: ${GREEN}found${NC}"

        if [ "$force" = "true" ]; then
            echo -e "\n${BLUE}→ Force renewing certificate...${NC}"
            "$acme_home/acme.sh" --renew -d "$hostname" --force
        else
            echo -e "\n${BLUE}→ Renewing certificate (if due)...${NC}"
            "$acme_home/acme.sh" --renew -d "$hostname"
        fi

        # Install to certs directory
        mkdir -p "$certs_dir"
        "$acme_home/acme.sh" --install-cert -d "$hostname" \
            --key-file "$certs_dir/${hostname}.key" \
            --fullchain-file "$certs_dir/${hostname}.fullchain.cer" \
            --reloadcmd "docker restart kg-web 2>/dev/null || true"

        echo -e "${GREEN}✓ Certificate renewed${NC}"

    elif [ -n "$dns_provider" ]; then
        # Issue new certificate with DNS-01 challenge
        echo -e "  DNS provider: ${BLUE}$dns_provider${NC}"
        echo -e "\n${BLUE}→ Issuing new certificate via DNS-01...${NC}"

        # Install acme.sh if needed
        if [ ! -f "$acme_home/acme.sh" ]; then
            echo -e "${BLUE}→ Installing acme.sh...${NC}"
            curl -fsSL https://get.acme.sh | sh -s email="${SSL_EMAIL:-admin@$hostname}"
        fi

        # Set DNS credentials
        case "$dns_provider" in
            dns_porkbun)
                export PORKBUN_API_KEY="$dns_key"
                export PORKBUN_SECRET_API_KEY="$dns_secret"
                ;;
            dns_cloudflare)
                export CF_Key="$dns_key"
                export CF_Email="${SSL_EMAIL:-}"
                ;;
            dns_digitalocean)
                export DO_API_KEY="$dns_key"
                ;;
            *)
                export DNS_API_KEY="$dns_key"
                export DNS_API_SECRET="$dns_secret"
                ;;
        esac

        if ! "$acme_home/acme.sh" --issue --dns "$dns_provider" -d "$hostname" --server letsencrypt; then
            echo -e "${RED}Failed to obtain certificate${NC}"
            exit 1
        fi

        mkdir -p "$certs_dir"
        "$acme_home/acme.sh" --install-cert -d "$hostname" \
            --key-file "$certs_dir/${hostname}.key" \
            --fullchain-file "$certs_dir/${hostname}.fullchain.cer" \
            --reloadcmd "docker restart kg-web 2>/dev/null || true"

        echo -e "${GREEN}✓ Certificate issued and installed${NC}"

    else
        echo -e "  acme.sh cert: ${YELLOW}not found${NC}"
        echo ""
        echo "To issue a new certificate with DNS-01 challenge:"
        echo "  $0 recert --dns dns_porkbun --dns-key YOUR_API_KEY --dns-secret YOUR_SECRET"
        echo ""
        echo "Supported DNS providers: dns_porkbun, dns_cloudflare, dns_digitalocean, dns_gandi, dns_namecheap"
        echo "See: https://github.com/acmesh-official/acme.sh/wiki/dnsapi"
        exit 1
    fi

    # Restart web to pick up new certs
    load_config
    local web_container=$(get_container_name web)
    if docker ps --format '{{.Names}}' | grep -q "^${web_container}$"; then
        echo -e "${BLUE}→ Restarting web server...${NC}"
        docker restart "$web_container"
        echo -e "${GREEN}✓ Web server restarted${NC}"
    fi
}

# ============================================================================
# Help System
# ============================================================================

show_help_overview() {
    echo -e "${BOLD}Knowledge Graph Platform Manager${NC}"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo -e "${BOLD}Lifecycle Commands:${NC}"
    echo "  init               Guided first-time setup"
    echo "  init --headless    Non-interactive setup (for automation)"
    echo "  update [service]   Pull latest images (no restart)"
    echo "  upgrade            Pull images, migrate, restart (no data loss)"
    echo "  start              Start the platform"
    echo "  stop               Stop the platform"
    echo "  teardown           Remove containers (keeps data by default)"
    echo ""
    echo -e "${BOLD}Service Commands:${NC}"
    echo "  restart <service>  Restart a service (api, web, postgres, garage)"
    echo "  rebuild <service>  Rebuild and restart (api, web only)"
    echo "  recert             Renew/reissue SSL certificates"
    echo ""
    echo -e "${BOLD}Management Commands:${NC}"
    echo "  status             Show platform and container status"
    echo "  admin [options]    Manage admin user (--password to set)"
    echo "  config [options]   Update platform configuration"
    echo "  logs [service] [-f] Show logs (default: api, -f to follow)"
    echo "  shell              Open shell in operator container"
    echo "  query 'SQL'        Run SQL query against database (alias: pg)"
    echo ""
    echo -e "${BOLD}Help Topics:${NC}"
    echo "  help               Show this overview"
    echo "  help lifecycle     Detailed lifecycle command help"
    echo "  help services      Service management details"
    echo "  help config        Configuration options"
    echo ""
    echo -e "${BOLD}Quick Examples:${NC}"
    echo "  $0 init                    # First-time setup (interactive)"
    echo "  $0 init --headless --skip-ai-config  # Automated setup"
    echo "  $0 upgrade --dry-run       # Preview upgrade"
    echo "  $0 start                   # Start with saved config"
    echo "  $0 stop --keep-infra       # Stop app, keep database"
    echo "  $0 shell                   # Enter operator shell for configuration"
    echo ""
}

show_help_lifecycle() {
    echo -e "${BOLD}Lifecycle Commands${NC}"
    echo ""
    echo "These commands manage the platform lifecycle on your host machine."
    echo ""
    echo -e "${BLUE}init${NC}"
    echo "  Guided first-time setup wizard."
    echo "  - Generates secrets (.env file)"
    echo "  - Detects GPU (NVIDIA, Mac, or CPU-only)"
    echo "  - Creates .operator.conf with your settings"
    echo "  - Starts all services"
    echo "  - Prompts for admin password and API keys"
    echo ""
    echo -e "${BLUE}init --headless [OPTIONS]${NC}"
    echo "  Non-interactive setup for automation."
    echo "  Options:"
    echo "    --password-mode random|simple   Password generation (default: random)"
    echo "    --container-mode regular|dev    Container naming (default: regular)"
    echo "    --container-prefix STR          Name prefix (default: knowledge-graph)"
    echo "    --gpu auto|nvidia|amd|mac|cpu   GPU mode (default: auto)"
    echo "    --image-source local|ghcr       Image source (default: local)"
    echo "    --ai-provider openai|anthropic  AI extraction provider"
    echo "    --ai-model MODEL                Model name (e.g., gpt-4o)"
    echo "    --ai-key KEY                    API key for provider"
    echo "    --skip-ai-config                Skip AI configuration"
    echo "    --skip-cli                      Skip CLI installation"
    echo ""
    echo "  Example:"
    echo "    $0 init --headless --container-prefix=kg --image-source=ghcr --skip-ai-config"
    echo ""
    echo -e "${BLUE}update [service]${NC}"
    echo "  Pull latest images without restarting (like apt update)."
    echo "  - Fetches new images from GHCR"
    echo "  - Shows what was downloaded"
    echo "  - Does NOT restart services"
    echo ""
    echo "  Examples:"
    echo "    $0 update              # Pull all images"
    echo "    $0 update api          # Pull only API image"
    echo "    $0 update operator     # Pull only operator image"
    echo ""
    echo "  After updating, apply changes with:"
    echo "    $0 upgrade             # Full upgrade (recommended)"
    echo "    $0 restart <service>   # Quick restart of one service"
    echo ""
    echo -e "${BLUE}upgrade [OPTIONS]${NC}"
    echo "  Graceful upgrade without data loss (like apt upgrade)."
    echo "  - Pulls new images (GHCR) or rebuilds (local)"
    echo "  - Creates pre-upgrade backup (optional)"
    echo "  - Runs database migrations"
    echo "  - Restarts with new images"
    echo ""
    echo "  Options:"
    echo "    --dry-run       Show what would change"
    echo "    --no-backup     Skip pre-upgrade backup"
    echo ""
    echo -e "${BLUE}start${NC}"
    echo "  Start the platform using saved configuration."
    echo "  - Reads .operator.conf for dev mode and GPU settings"
    echo "  - Starts infrastructure (postgres, garage, operator)"
    echo "  - Applies database migrations"
    echo "  - Starts application (api, web)"
    echo ""
    echo -e "${BLUE}stop [options]${NC}"
    echo "  Stop all containers gracefully."
    echo "  Options:"
    echo "    --keep-infra    Stop only app containers (api, web)"
    echo "                    Keep infrastructure running (postgres, garage, operator)"
    echo ""
    echo -e "${BLUE}teardown [options]${NC}"
    echo "  Remove containers and optionally all data."
    echo "  Options:"
    echo "    (default)           Remove containers, keep volumes and .env"
    echo "    --keep-env          Remove containers and volumes, keep .env"
    echo "    --include-operator  Also remove operator container"
    echo "    --full              Remove everything (volumes, images, .env)"
    echo ""
    echo -e "${BOLD}Typical Workflow:${NC}"
    echo "  $0 init              # First time only"
    echo "  $0 start             # Daily startup"
    echo "  $0 stop              # End of session"
    echo "  $0 teardown --full   # Complete reset"
    echo ""
}

show_help_services() {
    echo -e "${BOLD}Service Management${NC}"
    echo ""
    echo "Manage individual services without full restart."
    echo ""
    echo -e "${BLUE}restart <service>${NC}"
    echo "  Restart a running service container."
    echo "  Services: api, web, postgres, garage, operator"
    echo ""
    echo "  Examples:"
    echo "    $0 restart api        # Restart API server"
    echo "    $0 restart postgres   # Restart database"
    echo ""
    echo -e "${BLUE}rebuild <service>${NC}"
    echo "  Rebuild image and restart (for code changes)."
    echo "  Services: api, web (custom images only)"
    echo ""
    echo "  Examples:"
    echo "    $0 rebuild api        # After Python code changes"
    echo "    $0 rebuild web        # After React code changes"
    echo ""
    echo -e "${YELLOW}Note:${NC} In dev mode, code is mounted as volumes, so most changes"
    echo "auto-reload without rebuild. Use rebuild for:"
    echo "  - requirements.txt / package.json changes"
    echo "  - Dockerfile changes"
    echo "  - Schema changes requiring rebuild"
    echo ""
    echo -e "${BLUE}recert [options]${NC}"
    echo "  Renew or reissue SSL certificates."
    echo "  Uses acme.sh for DNS-01 challenge, certbot for HTTP-01."
    echo ""
    echo "  Options:"
    echo "    --force             Force renewal even if not due"
    echo "    --dns <provider>    DNS provider for new cert (e.g., dns_porkbun)"
    echo "    --dns-key <key>     DNS API key"
    echo "    --dns-secret <sec>  DNS API secret"
    echo ""
    echo "  Examples:"
    echo "    $0 recert                  # Renew existing certificate"
    echo "    $0 recert --force          # Force renewal"
    echo "    $0 recert --dns dns_porkbun --dns-key KEY --dns-secret SECRET"
    echo ""
    echo -e "${BLUE}logs [service] [-f|--follow] [-n|--lines N]${NC}"
    echo "  Show logs from a service (default: api)."
    echo "  By default shows last 100 lines and exits."
    echo "  Use -f to follow (like tail -f), Ctrl+C to stop."
    echo ""
    echo "  Options:"
    echo "    -f, --follow     Follow log output (stream continuously)"
    echo "    -n, --lines N    Show last N lines (default: 100)"
    echo ""
    echo "  Examples:"
    echo "    $0 logs              # Last 100 API logs"
    echo "    $0 logs -f           # Follow API logs"
    echo "    $0 logs web          # Last 100 web server logs"
    echo "    $0 logs postgres -n 50  # Last 50 database logs"
    echo "    $0 logs api -f       # Follow API logs"
    echo ""
}

show_help_config() {
    echo -e "${BOLD}Configuration${NC}"
    echo ""
    echo -e "${BLUE}status${NC}"
    echo "  Show platform configuration and container status."
    echo "  Displays: dev mode, GPU mode, container health"
    echo ""
    echo -e "${BLUE}config [options]${NC}"
    echo "  Update platform configuration (saved to .operator.conf)."
    echo ""
    echo "  Options:"
    echo "    --dev true|false    Enable/disable development mode"
    echo "                        Dev mode: hot reload, source mounts, Vite HMR"
    echo "    --gpu <mode>        Set GPU acceleration mode"
    echo "                        Modes: nvidia, mac, cpu, auto"
    echo ""
    echo "  Examples:"
    echo "    $0 config --dev true           # Enable dev mode"
    echo "    $0 config --gpu nvidia         # Use NVIDIA GPU"
    echo "    $0 config --dev true --gpu auto # Dev mode, auto-detect GPU"
    echo ""
    echo -e "${YELLOW}Note:${NC} After changing config, restart to apply:"
    echo "    $0 stop && $0 start"
    echo ""
    echo -e "${BLUE}shell${NC}"
    echo "  Open interactive shell in operator container."
    echo "  Use for detailed platform configuration:"
    echo "    - Admin user management"
    echo "    - AI provider setup"
    echo "    - Embedding configuration"
    echo "    - API key management"
    echo ""
    echo "  Inside shell, run: operator-help"
    echo ""
    echo -e "${BLUE}query 'SQL'${NC} (alias: pg)"
    echo "  Run SQL queries directly against the database."
    echo "  No TTY required - works in scripts and automation."
    echo ""
    echo "  Examples:"
    echo "    $0 query 'SELECT count(*) FROM pg_stat_activity'"
    echo "    $0 query 'SHOW max_connections'"
    echo "    $0 pg 'SELECT state, count(*) FROM pg_stat_activity GROUP BY state'"
    echo ""
    echo "  Multi-line queries (use single quotes):"
    echo "    $0 query '"
    echo "      SELECT ontology, count(*)"
    echo "      FROM kg_api.sources"
    echo "      GROUP BY ontology"
    echo "    '"
    echo ""
}

cmd_help() {
    local topic="${1:-}"

    case "$topic" in
        lifecycle)
            show_help_lifecycle
            ;;
        services|service)
            show_help_services
            ;;
        config|configuration)
            show_help_config
            ;;
        *)
            show_help_overview
            ;;
    esac
}

# ============================================================================
# Main Command Dispatch
# ============================================================================

case "${1:-help}" in
    init)
        shift
        # Check if --headless flag is present
        if [[ " $* " =~ " --headless " ]] || [[ "$1" == "--headless" ]]; then
            "$SCRIPT_DIR/operator/lib/headless-init.sh" "$@"
        else
            "$SCRIPT_DIR/operator/lib/guided-init.sh" "$@"
        fi
        ;;
    update)
        shift
        cmd_update "$@"
        ;;
    upgrade)
        shift
        "$SCRIPT_DIR/operator/lib/upgrade.sh" "$@"
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
        load_config
        docker exec -it $(get_container_name operator) /bin/bash
        ;;
    query|pg)
        shift
        cmd_query "$*"
        ;;
    teardown)
        shift
        "$SCRIPT_DIR/operator/lib/teardown.sh" "$@"
        ;;
    recert)
        shift
        cmd_recert "$@"
        ;;
    admin)
        shift
        cmd_admin "$@"
        ;;
    help|--help|-h)
        shift 2>/dev/null || true
        cmd_help "$@"
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        show_help_overview
        exit 1
        ;;
esac
