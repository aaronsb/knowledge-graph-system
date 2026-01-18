#!/bin/bash
# ============================================================================
# headless-init.sh - Non-interactive platform initialization
# ============================================================================
# Use for automated deployments, CI/CD, and multi-machine setups
# Run ./operator.sh init --headless --help for usage
# ============================================================================

set -e

# Get project root (this script is in operator/lib/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Source common functions
source "$SCRIPT_DIR/common.sh"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# ============================================================================
# Default Configuration
# ============================================================================
PASSWORD_MODE="random"
CONTAINER_MODE="regular"
GPU_MODE="auto"
CONTAINER_PREFIX="knowledge-graph"
CONTAINER_SUFFIX=""
COMPOSE_FILE="docker-compose.yml"
IMAGE_SOURCE="local"
AI_PROVIDER=""
AI_MODEL=""
AI_KEY=""
WEB_HOSTNAME=""
SKIP_AI_CONFIG=false
SKIP_CLI=false
SHOW_HELP=false

# ============================================================================
# Help
# ============================================================================
show_help() {
    cat << EOF
${BOLD}Headless Platform Initialization${NC}

Non-interactive setup for automated deployments.

${BOLD}Usage:${NC}
  ./operator.sh init --headless [OPTIONS]

${BOLD}Required:${NC}
  --headless              Enable non-interactive mode

${BOLD}Password Options:${NC}
  --password-mode MODE    Password generation mode
                          • random (default): Strong random passwords
                          • simple: Use Password1!/password defaults

${BOLD}Container Options:${NC}
  --container-mode MODE   Container naming mode
                          • regular (default): Production naming
                          • dev: Development mode with hot reload
  --container-prefix STR  Container name prefix (default: knowledge-graph)
  --container-suffix STR  Container name suffix (e.g., -dev)

${BOLD}Infrastructure Options:${NC}
  --gpu MODE              GPU acceleration mode
                          • auto (default): Detect NVIDIA or use CPU
                          • nvidia: Force NVIDIA GPU mode
                          • amd: AMD GPU (ROCm wheels)
                          • amd-host: AMD GPU (host ROCm)
                          • mac: macOS (MPS acceleration)
                          • cpu: CPU only
  --image-source SOURCE   Image source
                          • local (default): Build images locally
                          • ghcr: Pull from GitHub Container Registry
  --compose-file FILE     Base compose file (default: docker-compose.yml)

${BOLD}Web Configuration:${NC}
  --web-hostname HOST     Public hostname for web access (e.g., kg.example.com)
                          Used for OAuth redirect URIs and API URL
                          Default: localhost (for local dev) or localhost:3000

${BOLD}AI Configuration:${NC}
  --ai-provider PROVIDER  AI extraction provider (openai, anthropic, openrouter)
  --ai-model MODEL        Model name (e.g., gpt-4o, claude-sonnet-4)
  --ai-key KEY            API key for the provider
  --skip-ai-config        Skip AI provider configuration

${BOLD}Other Options:${NC}
  --skip-cli              Skip CLI installation
  --help                  Show this help message

${BOLD}Examples:${NC}

  # Production deployment with DNS hostname
  ./operator.sh init --headless \\
    --container-prefix=kg \\
    --image-source=ghcr \\
    --gpu=nvidia \\
    --web-hostname=kg.example.com \\
    --ai-provider=openai \\
    --ai-model=gpt-4o \\
    --ai-key="\$OPENAI_API_KEY"

  # Minimal deployment (configure AI later)
  ./operator.sh init --headless \\
    --container-prefix=kg \\
    --image-source=ghcr \\
    --web-hostname=192.168.1.82 \\
    --skip-ai-config

  # Local development with simple passwords
  ./operator.sh init --headless \\
    --password-mode=simple \\
    --container-mode=dev \\
    --gpu=auto

EOF
}

# ============================================================================
# Argument Parsing
# ============================================================================
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                SHOW_HELP=true
                shift
                ;;
            --headless)
                # Already in headless mode
                shift
                ;;
            --password-mode=*)
                PASSWORD_MODE="${1#*=}"
                shift
                ;;
            --password-mode)
                PASSWORD_MODE="$2"
                shift 2
                ;;
            --container-mode=*)
                CONTAINER_MODE="${1#*=}"
                shift
                ;;
            --container-mode)
                CONTAINER_MODE="$2"
                shift 2
                ;;
            --gpu=*)
                GPU_MODE="${1#*=}"
                shift
                ;;
            --gpu)
                GPU_MODE="$2"
                shift 2
                ;;
            --container-prefix=*)
                CONTAINER_PREFIX="${1#*=}"
                shift
                ;;
            --container-prefix)
                CONTAINER_PREFIX="$2"
                shift 2
                ;;
            --container-suffix=*)
                CONTAINER_SUFFIX="${1#*=}"
                shift
                ;;
            --container-suffix)
                CONTAINER_SUFFIX="$2"
                shift 2
                ;;
            --compose-file=*)
                COMPOSE_FILE="${1#*=}"
                shift
                ;;
            --compose-file)
                COMPOSE_FILE="$2"
                shift 2
                ;;
            --image-source=*)
                IMAGE_SOURCE="${1#*=}"
                shift
                ;;
            --image-source)
                IMAGE_SOURCE="$2"
                shift 2
                ;;
            --ai-provider=*)
                AI_PROVIDER="${1#*=}"
                shift
                ;;
            --ai-provider)
                AI_PROVIDER="$2"
                shift 2
                ;;
            --ai-model=*)
                AI_MODEL="${1#*=}"
                shift
                ;;
            --ai-model)
                AI_MODEL="$2"
                shift 2
                ;;
            --ai-key=*)
                AI_KEY="${1#*=}"
                shift
                ;;
            --ai-key)
                AI_KEY="$2"
                shift 2
                ;;
            --skip-ai-config)
                SKIP_AI_CONFIG=true
                shift
                ;;
            --skip-cli)
                SKIP_CLI=true
                shift
                ;;
            --web-hostname=*)
                WEB_HOSTNAME="${1#*=}"
                shift
                ;;
            --web-hostname)
                WEB_HOSTNAME="$2"
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
# Validation
# ============================================================================
validate_config() {
    local errors=0

    # Validate password mode
    if [[ "$PASSWORD_MODE" != "random" && "$PASSWORD_MODE" != "simple" ]]; then
        echo -e "${RED}✗ Invalid --password-mode: $PASSWORD_MODE (must be 'random' or 'simple')${NC}"
        errors=$((errors + 1))
    fi

    # Validate container mode
    if [[ "$CONTAINER_MODE" != "regular" && "$CONTAINER_MODE" != "dev" ]]; then
        echo -e "${RED}✗ Invalid --container-mode: $CONTAINER_MODE (must be 'regular' or 'dev')${NC}"
        errors=$((errors + 1))
    fi

    # Validate GPU mode
    case "$GPU_MODE" in
        auto|nvidia|amd|amd-host|mac|cpu) ;;
        *)
            echo -e "${RED}✗ Invalid --gpu: $GPU_MODE (must be auto|nvidia|amd|amd-host|mac|cpu)${NC}"
            errors=$((errors + 1))
            ;;
    esac

    # Validate image source
    if [[ "$IMAGE_SOURCE" != "local" && "$IMAGE_SOURCE" != "ghcr" ]]; then
        echo -e "${RED}✗ Invalid --image-source: $IMAGE_SOURCE (must be 'local' or 'ghcr')${NC}"
        errors=$((errors + 1))
    fi

    # Validate AI provider if specified
    if [[ -n "$AI_PROVIDER" ]]; then
        case "$AI_PROVIDER" in
            openai|anthropic|openrouter) ;;
            *)
                echo -e "${RED}✗ Invalid --ai-provider: $AI_PROVIDER (must be openai|anthropic|openrouter)${NC}"
                errors=$((errors + 1))
                ;;
        esac

        # If provider is set, model should also be set
        if [[ -z "$AI_MODEL" ]]; then
            echo -e "${YELLOW}⚠ --ai-provider set but --ai-model not specified, will use provider default${NC}"
        fi
    fi

    if [ $errors -gt 0 ]; then
        echo ""
        echo -e "${RED}Validation failed with $errors error(s)${NC}"
        exit 1
    fi
}

# ============================================================================
# GPU Detection
# ============================================================================
detect_gpu_mode() {
    if [[ "$GPU_MODE" != "auto" ]]; then
        return
    fi

    # Check for Mac
    if [[ "$(uname)" == "Darwin" ]]; then
        GPU_MODE="mac"
        echo -e "${GREEN}→ Detected macOS, using MPS acceleration${NC}"
        return
    fi

    # Check for NVIDIA GPU
    if command -v nvidia-smi &> /dev/null; then
        if nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | grep -q .; then
            local gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
            GPU_MODE="nvidia"
            echo -e "${GREEN}→ Detected NVIDIA GPU: $gpu_name${NC}"
            return
        fi
    fi

    GPU_MODE="cpu"
    echo -e "${YELLOW}→ No GPU detected, using CPU mode${NC}"
}

# ============================================================================
# Main Initialization
# ============================================================================
main() {
    parse_args "$@"

    if [ "$SHOW_HELP" = true ]; then
        show_help
        exit 0
    fi

    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  ${BOLD}Knowledge Graph System - Headless Setup${NC}               ${BLUE}    ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    validate_config
    detect_gpu_mode

    # Set DEV_MODE based on container mode
    local DEV_MODE="false"
    if [ "$CONTAINER_MODE" = "dev" ]; then
        DEV_MODE="true"
        if [ -z "$CONTAINER_SUFFIX" ]; then
            CONTAINER_SUFFIX="-dev"
        fi
    fi

    # Auto-select compose file based on container prefix and image source
    # docker-compose.prod.yml uses kg-* names, docker-compose.yml uses knowledge-graph-*
    if [ "$COMPOSE_FILE" = "docker-compose.yml" ]; then
        if [ "$CONTAINER_PREFIX" = "kg" ] || [ "$IMAGE_SOURCE" = "ghcr" ]; then
            COMPOSE_FILE="docker-compose.prod.yml"
        fi
    fi

    echo -e "${BOLD}Configuration:${NC}"
    echo -e "  Password mode:     ${BLUE}$PASSWORD_MODE${NC}"
    echo -e "  Container mode:    ${BLUE}$CONTAINER_MODE${NC}"
    echo -e "  Container prefix:  ${BLUE}$CONTAINER_PREFIX${NC}"
    echo -e "  Container suffix:  ${BLUE}${CONTAINER_SUFFIX:-none}${NC}"
    echo -e "  GPU mode:          ${BLUE}$GPU_MODE${NC}"
    echo -e "  Image source:      ${BLUE}$IMAGE_SOURCE${NC}"
    echo -e "  Compose file:      ${BLUE}$COMPOSE_FILE${NC}"
    if [ -n "$WEB_HOSTNAME" ]; then
        echo -e "  Web hostname:      ${BLUE}$WEB_HOSTNAME${NC}"
    fi
    if [ "$SKIP_AI_CONFIG" = true ]; then
        echo -e "  AI config:         ${YELLOW}skipped${NC}"
    elif [ -n "$AI_PROVIDER" ]; then
        echo -e "  AI provider:       ${BLUE}$AI_PROVIDER${NC}"
        echo -e "  AI model:          ${BLUE}${AI_MODEL:-default}${NC}"
    fi
    echo ""

    # -------------------------------------------------------------------------
    # Step 1: Check Docker
    # -------------------------------------------------------------------------
    echo -e "${BLUE}→ Step 1: Checking Docker...${NC}"
    if ! docker ps >/dev/null 2>&1; then
        echo -e "${RED}✗ Docker is not running or you don't have permission${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker is available${NC}"
    echo ""

    # -------------------------------------------------------------------------
    # Step 2: Generate secrets
    # -------------------------------------------------------------------------
    echo -e "${BLUE}→ Step 2: Generating infrastructure secrets...${NC}"

    local ADMIN_PASSWORD
    local POSTGRES_PASSWORD

    if [ "$PASSWORD_MODE" = "random" ]; then
        ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d '/+=' | cut -c1-16)
        # Check if upgrading or fresh install
        if [ -f "$PROJECT_ROOT/.env" ]; then
            "$PROJECT_ROOT/operator/lib/init-secrets.sh" --upgrade -y
        else
            "$PROJECT_ROOT/operator/lib/init-secrets.sh" -y
        fi
        POSTGRES_PASSWORD=$(grep '^POSTGRES_PASSWORD=' "$PROJECT_ROOT/.env" | cut -d'=' -f2)
    else
        ADMIN_PASSWORD="Password1!"
        POSTGRES_PASSWORD="password"
        "$PROJECT_ROOT/operator/lib/init-secrets.sh" --dev -y
    fi

    # Set default WEB_HOSTNAME if not specified
    if [ -z "$WEB_HOSTNAME" ]; then
        if [ "$CONTAINER_PREFIX" = "kg" ]; then
            WEB_HOSTNAME="localhost"
        else
            WEB_HOSTNAME="localhost:3000"
        fi
    fi

    # Add WEB_HOSTNAME to .env
    if ! grep -q '^WEB_HOSTNAME=' "$PROJECT_ROOT/.env" 2>/dev/null; then
        echo "" >> "$PROJECT_ROOT/.env"
        echo "# Web hostname for OAuth and API URLs" >> "$PROJECT_ROOT/.env"
        echo "WEB_HOSTNAME=$WEB_HOSTNAME" >> "$PROJECT_ROOT/.env"
    else
        sed -i "s|^WEB_HOSTNAME=.*|WEB_HOSTNAME=$WEB_HOSTNAME|" "$PROJECT_ROOT/.env"
    fi

    echo -e "${GREEN}✓ Secrets generated${NC}"
    echo -e "${GREEN}✓ Web hostname: $WEB_HOSTNAME${NC}"
    echo ""

    # -------------------------------------------------------------------------
    # Step 3: Save configuration
    # -------------------------------------------------------------------------
    echo -e "${BLUE}→ Step 3: Saving configuration...${NC}"

    cat > "$PROJECT_ROOT/.operator.conf" << EOF
# Operator configuration (auto-generated by headless-init)
DEV_MODE=$DEV_MODE
GPU_MODE=$GPU_MODE
CONTAINER_PREFIX=$CONTAINER_PREFIX
CONTAINER_SUFFIX=$CONTAINER_SUFFIX
COMPOSE_FILE=$COMPOSE_FILE
IMAGE_SOURCE=$IMAGE_SOURCE
INITIALIZED_AT=$(date -Iseconds)
EOF

    echo -e "${GREEN}✓ Configuration saved to .operator.conf${NC}"
    echo ""

    # -------------------------------------------------------------------------
    # Step 4: Start infrastructure
    # -------------------------------------------------------------------------
    echo -e "${BLUE}→ Step 4: Starting infrastructure...${NC}"
    export DEV_MODE GPU_MODE
    "$PROJECT_ROOT/operator/lib/start-infra.sh"
    echo ""

    # Get operator container name
    local OPERATOR_CONTAINER=$(get_container_name operator)
    local GARAGE_CONTAINER=$(get_container_name garage)

    # -------------------------------------------------------------------------
    # Step 5: Create admin user and register OAuth client
    # -------------------------------------------------------------------------
    echo -e "${BLUE}→ Step 5: Creating admin user...${NC}"
    docker exec "$OPERATOR_CONTAINER" python /workspace/operator/configure.py admin --password "$ADMIN_PASSWORD"
    echo -e "${GREEN}✓ Admin user created${NC}"

    # Register OAuth client for web app with configured hostname
    local POSTGRES_CONTAINER=$(get_container_name postgres)
    local REDIRECT_URI="http://${WEB_HOSTNAME}/callback"
    echo -e "${BLUE}  Registering OAuth client (kg-web)...${NC}"
    docker exec "$POSTGRES_CONTAINER" psql -U ${POSTGRES_USER:-admin} -d ${POSTGRES_DB:-knowledge_graph} -c \
        "INSERT INTO kg_auth.oauth_clients (client_id, client_name, client_type, redirect_uris, grant_types, scopes)
         VALUES ('kg-web', 'Knowledge Graph Web', 'public',
                 ARRAY['${REDIRECT_URI}', 'http://localhost:3000/callback'],
                 ARRAY['authorization_code', 'refresh_token'],
                 ARRAY['*'])
         ON CONFLICT (client_id) DO UPDATE SET
             redirect_uris = EXCLUDED.redirect_uris,
             scopes = EXCLUDED.scopes;" >/dev/null 2>&1
    echo -e "${GREEN}✓ OAuth client registered (redirect: ${REDIRECT_URI})${NC}"
    echo ""

    # -------------------------------------------------------------------------
    # Step 6: Configure AI provider (if requested)
    # -------------------------------------------------------------------------
    if [ "$SKIP_AI_CONFIG" = false ]; then
        if [ -n "$AI_PROVIDER" ]; then
            echo -e "${BLUE}→ Step 6: Configuring AI provider...${NC}"

            local model_arg=""
            if [ -n "$AI_MODEL" ]; then
                model_arg="--model $AI_MODEL"
            fi

            docker exec "$OPERATOR_CONTAINER" python /workspace/operator/configure.py ai-provider "$AI_PROVIDER" $model_arg

            if [ -n "$AI_KEY" ]; then
                echo -e "${BLUE}  Storing API key...${NC}"
                docker exec "$OPERATOR_CONTAINER" python /workspace/operator/configure.py api-key "$AI_PROVIDER" --key "$AI_KEY"
                echo -e "${GREEN}✓ API key stored${NC}"
            fi
            echo ""
        else
            echo -e "${BLUE}→ Step 6: Setting default AI provider (OpenAI)...${NC}"
            docker exec "$OPERATOR_CONTAINER" python /workspace/operator/configure.py ai-provider openai --model gpt-4o
            echo -e "${YELLOW}⚠ AI provider set but no API key provided${NC}"
            echo -e "${YELLOW}  Add key later: docker exec $OPERATOR_CONTAINER python /workspace/operator/configure.py api-key openai --key <KEY>${NC}"
            echo ""
        fi

        # Configure embeddings
        echo -e "${BLUE}→ Configuring embeddings...${NC}"
        docker exec "$OPERATOR_CONTAINER" python /workspace/operator/configure.py embedding 2
        echo -e "${GREEN}✓ Embeddings configured (local nomic-embed)${NC}"
        echo ""
    else
        echo -e "${YELLOW}→ Step 6: Skipping AI configuration (--skip-ai-config)${NC}"
        echo ""
    fi

    # -------------------------------------------------------------------------
    # Step 7: Configure Garage credentials
    # -------------------------------------------------------------------------
    echo -e "${BLUE}→ Step 7: Configuring Garage storage...${NC}"

    # Delete existing key if it exists (silently)
    docker exec "$GARAGE_CONTAINER" /garage key delete kg-api-key --yes >/dev/null 2>&1 || true

    # Create new key and capture output
    KEY_OUTPUT=$(docker exec "$GARAGE_CONTAINER" /garage key create kg-api-key 2>&1)

    GARAGE_KEY_ID=$(echo "$KEY_OUTPUT" | grep "Key ID:" | awk '{print $3}')
    GARAGE_SECRET=$(echo "$KEY_OUTPUT" | grep "Secret key:" | awk '{print $3}')

    if [ -n "$GARAGE_KEY_ID" ] && [ -n "$GARAGE_SECRET" ]; then
        GARAGE_BUCKET="${GARAGE_BUCKET:-kg-storage}"
        docker exec "$GARAGE_CONTAINER" /garage bucket allow --read --write --key kg-api-key "$GARAGE_BUCKET" >/dev/null 2>&1

        GARAGE_CREDENTIALS="${GARAGE_KEY_ID}:${GARAGE_SECRET}"
        docker exec "$OPERATOR_CONTAINER" python /workspace/operator/configure.py api-key garage --key "$GARAGE_CREDENTIALS" 2>&1 | grep -qi "stored" && \
            echo -e "${GREEN}✓ Garage credentials stored${NC}" || \
            echo -e "${YELLOW}⚠ Garage credentials may need manual configuration${NC}"
    else
        echo -e "${YELLOW}⚠ Failed to create Garage API key${NC}"
    fi
    echo ""

    # -------------------------------------------------------------------------
    # Step 8: Start application
    # -------------------------------------------------------------------------
    echo -e "${BLUE}→ Step 8: Starting application...${NC}"
    "$PROJECT_ROOT/operator.sh" start
    echo ""

    # -------------------------------------------------------------------------
    # Step 9: Install CLI (optional)
    # -------------------------------------------------------------------------
    if [ "$SKIP_CLI" = false ]; then
        if [ -d "$PROJECT_ROOT/cli" ]; then
            echo -e "${BLUE}→ Step 9: Installing kg CLI...${NC}"
            cd "$PROJECT_ROOT/cli" && ./install.sh && cd "$PROJECT_ROOT"
            echo ""
        fi
    else
        echo -e "${YELLOW}→ Step 9: Skipping CLI installation (--skip-cli)${NC}"
        echo ""
    fi

    # -------------------------------------------------------------------------
    # Success
    # -------------------------------------------------------------------------
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  ${BOLD}Headless Setup Complete!${NC}                              ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BOLD}Services running:${NC}"
    echo "  • API:      http://localhost:8000"
    echo "  • Web UI:   http://localhost:3000"
    echo "  • Postgres: localhost:5432"
    echo ""

    if [ "$PASSWORD_MODE" = "random" ]; then
        echo -e "${BOLD}Credentials (randomized):${NC}"
        echo -e "  Admin username: admin"
        echo -e "  Admin password: ${GREEN}$ADMIN_PASSWORD${NC}"
        echo -e "  Database password: ${GREEN}$POSTGRES_PASSWORD${NC}"
    else
        echo -e "${BOLD}Credentials (simple defaults):${NC}"
        echo -e "  Admin username: admin"
        echo -e "  Admin password: ${RED}$ADMIN_PASSWORD${NC}"
        echo -e "  Database password: ${RED}$POSTGRES_PASSWORD${NC}"
    fi
    echo ""

    if [ "$SKIP_AI_CONFIG" = true ]; then
        echo -e "${YELLOW}Note: AI provider not configured. Configure manually:${NC}"
        echo "  docker exec $OPERATOR_CONTAINER python /workspace/operator/configure.py ai-provider openai --model gpt-4o"
        echo "  docker exec $OPERATOR_CONTAINER python /workspace/operator/configure.py api-key openai --key <KEY>"
        echo ""
    fi

    echo -e "${BOLD}Management commands:${NC}"
    echo "  ./operator.sh status             # Show status"
    echo "  ./operator.sh logs api           # View API logs"
    echo "  ./operator.sh stop               # Stop platform"
    echo "  ./operator.sh shell              # Enter operator shell"
    echo ""
}

# Run main function
main "$@"
