#!/bin/bash
set -e

# ============================================================================
# initialize-platform.sh
# Knowledge Graph System - Platform Configuration Manager
# ============================================================================
#
# PURPOSE:
# Pre-configure database settings BEFORE the API server starts for clean
# first-time initialization. This script sets up all critical configuration
# so the API server can start with known-good settings and avoid common
# cold-start issues.
#
# WHAT IT CONFIGURES:
# 1. Admin User - Known username/password for first login
# 2. OAuth Signing Key - JWT token signing for authentication (ADR-054)
# 3. Encryption Key - Master key for encrypting API keys at rest (ADR-031)
# 4. AI Extraction Provider - Which LLM to use (OpenAI/Anthropic/Ollama)
# 5. Embedding Provider - Which embeddings to use (OpenAI/Local)
# 6. API Keys - Store encrypted keys for configured providers
#
# WHY PRE-CONFIGURE?
# The API server loads configuration from the database on startup. If critical
# settings (especially embedding provider) are not configured before first
# startup, the system may:
# - Apply wrong embeddings to vocabulary metadata (requires regeneration)
# - Fail to start due to missing API keys
# - Force manual configuration via kg CLI after the fact
#
# COLD-START EXAMPLE:
# Without this script:
# 1. API starts → no embedding config → defaults to OpenAI embeddings
# 2. Vocabulary metadata gets OpenAI embeddings
# 3. You configure local embeddings → now have mixed embedding types
# 4. Must regenerate all embeddings to fix inconsistency
#
# With this script:
# 1. Configure local embeddings BEFORE API starts
# 2. API starts → sees local embedding config → uses it from the start
# 3. All embeddings consistent, no regeneration needed
#
# DOCKER vs NON-DOCKER:
# This script works with both deployment modes:
# - Docker: Connects to PostgreSQL container via POSTGRES_HOST=localhost
# - Non-Docker: Connects to PostgreSQL server via POSTGRES_HOST=<server>
# All database operations use Python + psycopg2, not docker exec commands.
#
# USAGE:
# ./scripts/setup/initialize-platform.sh        # Interactive menu
# ./scripts/setup/initialize-platform.sh --dev  # Dev mode (weak password)
# ./scripts/setup/initialize-platform.sh --help # Show this help
#
# ============================================================================

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Show help message
show_help() {
    echo "Knowledge Graph System - Platform Configuration Manager"
    echo ""
    echo "Pre-configure database settings BEFORE the API server starts for clean"
    echo "first-time initialization. Prevents cold-start issues like wrong embedding"
    echo "types being applied to vocabulary metadata."
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --dev     Development mode (uses weak password 'Password1!')"
    echo "  --help    Show this help message and exit"
    echo ""
    echo "Configuration Steps:"
    echo "  1. Admin User       - Set username/password for first login"
    echo "  2. OAuth Key        - Generate signing key for authentication (ADR-054)"
    echo "  3. Encryption Key   - Generate master key for API key encryption (ADR-031)"
    echo "  4. AI Extraction    - Configure LLM provider (OpenAI/Anthropic/Ollama)"
    echo "  5. Embedding        - Configure embedding provider (OpenAI/Local)"
    echo "  6. API Keys         - Store encrypted keys for configured providers"
    echo ""
    echo "Example:"
    echo "  ./scripts/setup/initialize-platform.sh"
    echo "  # Follow interactive prompts to configure each component"
    echo ""
    echo "Docker vs Non-Docker:"
    echo "  This script works with both deployment modes by connecting to PostgreSQL"
    echo "  via environment variables (POSTGRES_HOST from .env file)."
    echo ""
}

# Parse command line arguments
DEV_MODE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            DEV_MODE=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: $0 [--dev] [--help]"
            echo "Run '$0 --help' for more information"
            exit 1
            ;;
    esac
done

# Check for Python venv, create if missing
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${BLUE}→${NC} Virtual environment not found, creating..."
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}✗${NC} python3 not found. Please install Python 3.11+"
        exit 1
    fi
    python3 -m venv "$PROJECT_ROOT/venv"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Virtual environment created"
    else
        echo -e "${RED}✗${NC} Failed to create virtual environment"
        exit 1
    fi
fi

# Use venv Python
if [ -f "$PROJECT_ROOT/venv/bin/python" ]; then
    PYTHON="$PROJECT_ROOT/venv/bin/python"
    PIP="$PROJECT_ROOT/venv/bin/pip"
elif [ -f "$PROJECT_ROOT/venv/bin/python3" ]; then
    PYTHON="$PROJECT_ROOT/venv/bin/python3"
    PIP="$PROJECT_ROOT/venv/bin/pip"
else
    echo -e "${RED}✗${NC} Virtual environment exists but Python not found"
    exit 1
fi

# Check and install required Python packages
check_packages() {
    local missing=()
    for import_name in passlib psycopg2 cryptography dotenv; do
        if ! $PYTHON -c "import $import_name" &>/dev/null 2>&1; then
            missing+=("$import_name")
        fi
    done
    echo "${missing[@]}"
}

MISSING_PACKAGES=($(check_packages))
if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠${NC}  Missing required packages: ${MISSING_PACKAGES[*]}"
    if [ ! -f "$PROJECT_ROOT/requirements.txt" ]; then
        echo -e "${RED}✗${NC} requirements.txt not found"
        exit 1
    fi
    echo -e "${BLUE}→${NC} Upgrading pip..."
    $PIP install --upgrade pip -q 2>&1 | grep -v "Requirement already satisfied" || true
    echo -e "${BLUE}→${NC} Installing dependencies from requirements.txt..."
    $PIP install -r "$PROJECT_ROOT/requirements.txt" 2>&1 | grep -E "(Successfully installed|Requirement already satisfied|ERROR)" || true
    echo -e "${BLUE}→${NC} Verifying installation..."
    STILL_MISSING=($(check_packages))
    if [ ${#STILL_MISSING[@]} -gt 0 ]; then
        echo -e "${RED}✗${NC} Failed to install: ${STILL_MISSING[*]}"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} Dependencies installed and verified"
fi

# PostgreSQL connection details (load from .env if exists)
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi
POSTGRES_HOST=${POSTGRES_HOST:-localhost}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_DB=${POSTGRES_DB:-knowledge_graph}
POSTGRES_USER=${POSTGRES_USER:-admin}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-password}

# Detect environment: Docker vs Local PostgreSQL
DEPLOYMENT_MODE="unknown"
if command -v docker &> /dev/null; then
    # Docker is installed - check if container exists and is running
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^knowledge-graph-postgres$"; then
        DEPLOYMENT_MODE="docker"
        DEPLOYMENT_DESC="Docker Container (knowledge-graph-postgres)"
    elif [ "$POSTGRES_HOST" = "localhost" ] || [ "$POSTGRES_HOST" = "127.0.0.1" ]; then
        # Docker not running but localhost - could be local PostgreSQL
        DEPLOYMENT_MODE="local"
        DEPLOYMENT_DESC="Local PostgreSQL ($POSTGRES_HOST:$POSTGRES_PORT)"
    else
        # Remote PostgreSQL server
        DEPLOYMENT_MODE="remote"
        DEPLOYMENT_DESC="Remote PostgreSQL ($POSTGRES_HOST:$POSTGRES_PORT)"
    fi
else
    # Docker not installed
    DEPLOYMENT_MODE="local"
    DEPLOYMENT_DESC="Local PostgreSQL ($POSTGRES_HOST:$POSTGRES_PORT)"
fi

# Banner
clear
echo -e "${BLUE}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║       Knowledge Graph System - Configuration Manager       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${BOLD}Environment:${NC} $DEPLOYMENT_DESC"
echo ""

# Check PostgreSQL connection
echo -e "${BLUE}→${NC} Checking PostgreSQL connection..."

if [ "$DEPLOYMENT_MODE" = "docker" ]; then
    # Docker deployment - use docker exec
    if ! docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "SELECT 1" > /dev/null 2>&1; then
        echo -e "${RED}✗ PostgreSQL container is not responding${NC}"
        echo -e "${YELLOW}  Run: docker-compose up -d${NC}"
        exit 1
    fi
else
    # Local/remote deployment - use psql with host/port
    if ! PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1" > /dev/null 2>&1; then
        echo -e "${RED}✗ PostgreSQL is not responding at $POSTGRES_HOST:$POSTGRES_PORT${NC}"
        echo -e "${YELLOW}  Check that PostgreSQL is running and accessible${NC}"
        echo -e "${YELLOW}  Verify POSTGRES_HOST, POSTGRES_PORT in .env${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓${NC} PostgreSQL is running"
echo ""

# Helper function: Execute PostgreSQL query (works with both Docker and local)
pg_query() {
    local query="$1"
    if [ "$DEPLOYMENT_MODE" = "docker" ]; then
        docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -t -A -c "$query" 2>/dev/null
    else
        PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c "$query" 2>/dev/null
    fi
}

# Check current configuration status with indicators
# ✓ = configured, ⚠ = needs attention, ○ = not configured

get_admin_status() {
    local exists=$(pg_query "SELECT COUNT(*) FROM kg_auth.users WHERE username = 'admin'" | xargs)
    if [ "$exists" -gt "0" ]; then
        echo -e "${GREEN}✓${NC} configured"
    else
        echo -e "○ not configured"
    fi
}

get_oauth_key_status() {
    if [ -f "$PROJECT_ROOT/.env" ] && grep -q "^OAUTH_SIGNING_KEY=" "$PROJECT_ROOT/.env"; then
        local key=$(grep "^OAUTH_SIGNING_KEY=" "$PROJECT_ROOT/.env" | cut -d'=' -f2)
        if [[ "$key" == *"CHANGE_THIS"* ]]; then
            echo -e "${YELLOW}⚠${NC} insecure default"
        else
            echo -e "${GREEN}✓${NC} configured"
        fi
    else
        echo -e "○ not configured"
    fi
}

get_encryption_key_status() {
    if [ -f "$PROJECT_ROOT/.env" ] && grep -q "^ENCRYPTION_KEY=" "$PROJECT_ROOT/.env"; then
        echo -e "${GREEN}✓${NC} configured"
    else
        echo -e "○ not configured"
    fi
}

get_ai_provider_status() {
    local provider=$(pg_query "SELECT provider FROM kg_api.ai_extraction_config WHERE active = true LIMIT 1" | xargs)
    if [ -n "$provider" ]; then
        echo -e "${GREEN}✓${NC} ${provider}"
    else
        echo -e "○ unconfigured"
    fi
}

get_embedding_provider_status() {
    local provider=$(pg_query "SELECT provider FROM kg_api.embedding_config WHERE active = true LIMIT 1" | xargs)
    if [ -n "$provider" ]; then
        echo -e "${GREEN}✓${NC} ${provider}"
    else
        echo -e "○ unconfigured"
    fi
}

get_api_keys_status() {
    # Query which providers have API keys configured
    local keys=$(pg_query "SELECT provider FROM kg_api.system_api_keys ORDER BY provider" | tr '\n' ' ' | xargs)
    if [ -n "$keys" ]; then
        echo -e "${GREEN}✓${NC} ${keys}"
    else
        echo -e "○ none"
    fi
}

get_minio_status() {
    # Check if MinIO credentials are in encrypted key store (ADR-031)
    local key_exists=$(pg_query "SELECT COUNT(*) FROM kg_api.system_api_keys WHERE provider = 'minio'" | xargs)

    if [ "$key_exists" -gt "0" ]; then
        # Credentials encrypted in database (recommended)
        if [ "$DEPLOYMENT_MODE" = "docker" ]; then
            if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^knowledge-graph-minio$"; then
                echo -e "${GREEN}✓${NC} configured, running"
            else
                echo -e "${GREEN}✓${NC} configured, stopped"
            fi
        else
            # Non-Docker - try health check
            local minio_host=$(grep "^MINIO_HOST=" "$PROJECT_ROOT/.env" 2>/dev/null | cut -d'=' -f2 || echo "localhost")
            local minio_port=$(grep "^MINIO_PORT=" "$PROJECT_ROOT/.env" 2>/dev/null | cut -d'=' -f2 || echo "9000")
            if command -v curl &> /dev/null && curl -sf "http://${minio_host}:${minio_port}/minio/health/live" > /dev/null 2>&1; then
                echo -e "${GREEN}✓${NC} configured, reachable"
            else
                echo -e "${GREEN}✓${NC} configured, unreachable"
            fi
        fi
    else
        # Check if using .env fallback (works but not recommended)
        if grep -q "^MINIO_ROOT_USER=" "$PROJECT_ROOT/.env" 2>/dev/null; then
            echo -e "${YELLOW}⚠${NC} .env fallback"
        else
            echo -e "○ not configured"
        fi
    fi
}

# Main menu loop
show_menu() {
    echo ""
    echo -e "${BOLD}Configuration Menu:${NC}"
    echo ""
    echo -e "  1) Admin Password          [$(get_admin_status)]"
    echo -e "  2) OAuth Signing Key       [$(get_oauth_key_status)]"
    echo -e "  3) Encryption Key          [$(get_encryption_key_status)]"
    echo -e "  4) AI Extraction Provider  [$(get_ai_provider_status)]"
    echo -e "  5) Embedding Provider      [$(get_embedding_provider_status)]"
    echo -e "  6) API Keys                [$(get_api_keys_status)]"
    echo -e "  7) MinIO Storage           [$(get_minio_status)]"
    echo -e "  8) Image Embedding Model   [nomic-ai/nomic-embed-vision-v1.5]"
    echo ""
    echo -e "  ${BOLD}h)${NC} Help     ${BOLD}q)${NC} Quit"
    echo ""
}

configure_single_api_key() {
    local provider=$1
    local provider_display=$2

    echo ""
    echo -e "${BOLD}${provider_display} API Key Configuration${NC}"
    echo -e "${YELLOW}Keys are encrypted at rest (ADR-031)${NC}"
    echo ""

    # Check if key already exists and if it can be decrypted
    local key_exists=$(pg_query "SELECT COUNT(*) FROM kg_api.system_api_keys WHERE provider = '$provider'" | xargs)

    if [ "$key_exists" -gt "0" ]; then
        # Key exists - check if it's valid
        local validation_status=$(pg_query "SELECT validation_status FROM kg_api.system_api_keys WHERE provider = '$provider'" | xargs)

        if [ "$validation_status" = "valid" ]; then
            echo -e "${GREEN}✓${NC} ${provider_display} API key already configured and validated"
        elif [ "$validation_status" = "invalid" ]; then
            echo -e "${RED}✗${NC} ${provider_display} API key is invalid (failed validation)"
        else
            echo -e "${YELLOW}⚠${NC}  ${provider_display} API key exists but validation status unknown"
        fi

        echo ""
        read -p "Update ${provider_display} API key? [y/N]: " -n 1 -r
        echo ""

        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 0
        fi
    else
        # Key doesn't exist - prompt to configure it
        echo -e "${YELLOW}→${NC} No ${provider_display} API key found"
        echo ""
        read -p "Configure ${provider_display} API key now? [Y/n]: " -n 1 -r
        echo ""

        if [[ $REPLY =~ ^[Nn]$ ]]; then
            echo -e "${YELLOW}⚠${NC}  Skipping API key configuration"
            echo -e "${YELLOW}   Provider will be configured but may fail without API key${NC}"
            return 1
        fi
    fi

    # Call Python helper to configure just this provider
    echo ""
    echo -e "${BLUE}→${NC} Configuring ${provider_display} API key..."
    echo ""

    # Create temporary script that configures only this provider
    local temp_script=$(mktemp)
    cat > "$temp_script" << EOF
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, "$PROJECT_ROOT")
from scripts.admin.manage_api_keys import add_key_interactive, EncryptedKeyStore
from src.api.lib.age_client import AGEClient

try:
    client = AGEClient()
    conn = client.pool.getconn()
    try:
        key_store = EncryptedKeyStore(conn)
        success = add_key_interactive(key_store, "$provider")
        sys.exit(0 if success else 1)
    finally:
        client.pool.putconn(conn)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
EOF

    $PYTHON "$temp_script"
    local result=$?
    rm -f "$temp_script"

    if [ $result -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓${NC} ${provider_display} API key configured successfully"
        return 0
    else
        echo ""
        echo -e "${RED}✗${NC} Failed to configure ${provider_display} API key"
        return 1
    fi
}

configure_admin() {
    echo ""
    echo -e "${BOLD}Configure Admin Password${NC}"
    echo ""

    export PROJECT_ROOT
    export PYTHON

    local admin_exists=$(pg_query "SELECT COUNT(*) FROM kg_auth.users WHERE username = 'admin'" | xargs)

    if [ "$admin_exists" -gt "0" ]; then
        echo -e "${YELLOW}⚠${NC}  Admin user already exists"
        read -p "Reset admin password? [y/N]: " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            "$PROJECT_ROOT/scripts/admin/set-admin-password.sh"
        fi
    else
        "$PROJECT_ROOT/scripts/admin/set-admin-password.sh" --create
    fi

    echo ""
    read -p "Press Enter to continue..."
}

configure_oauth_key() {
    echo ""
    echo -e "${BOLD}Configure OAuth Signing Key${NC}"
    echo -e "${YELLOW}Used to sign OAuth 2.0 access tokens (ADR-054)${NC}"
    echo ""

    local GENERATE_SECRET=false

    if [ -f "$PROJECT_ROOT/.env" ] && grep -q "^OAUTH_SIGNING_KEY=" "$PROJECT_ROOT/.env"; then
        local EXISTING_SECRET=$(grep "^OAUTH_SIGNING_KEY=" "$PROJECT_ROOT/.env" | cut -d'=' -f2)
        if [[ "$EXISTING_SECRET" == *"CHANGE_THIS"* ]]; then
            echo -e "${YELLOW}⚠${NC}  Insecure signing key found in .env"
            GENERATE_SECRET=true
        else
            echo -e "${GREEN}✓${NC} OAuth signing key already configured in .env"
            read -p "Generate new signing key? [y/N]: " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                GENERATE_SECRET=true
            fi
        fi
    else
        echo -e "${BLUE}→${NC} No OAuth signing key found in .env"
        GENERATE_SECRET=true
    fi

    if [ "$GENERATE_SECRET" = true ]; then
        # Try openssl first, fall back to Python
        local OAUTH_SIGNING_KEY
        if command -v openssl &> /dev/null; then
            OAUTH_SIGNING_KEY=$(openssl rand -hex 32)
            echo -e "${GREEN}✓${NC} Generated OAuth signing key using openssl"
        else
            OAUTH_SIGNING_KEY=$($PYTHON -c "import secrets; print(secrets.token_hex(32))")
            echo -e "${GREEN}✓${NC} Generated OAuth signing key using Python"
        fi

        # Update or create .env file
        if [ -f "$PROJECT_ROOT/.env" ]; then
            if grep -q "^OAUTH_SIGNING_KEY=" "$PROJECT_ROOT/.env"; then
                sed "s/^OAUTH_SIGNING_KEY=.*/OAUTH_SIGNING_KEY=$OAUTH_SIGNING_KEY/" "$PROJECT_ROOT/.env" > "$PROJECT_ROOT/.env.tmp" && mv "$PROJECT_ROOT/.env.tmp" "$PROJECT_ROOT/.env"
            else
                echo "OAUTH_SIGNING_KEY=$OAUTH_SIGNING_KEY" >> "$PROJECT_ROOT/.env"
            fi
        else
            cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env" 2>/dev/null || true
            echo "OAUTH_SIGNING_KEY=$OAUTH_SIGNING_KEY" >> "$PROJECT_ROOT/.env"
        fi
        echo -e "${GREEN}✓${NC} OAuth signing key saved to .env"
    fi

    echo ""
    read -p "Press Enter to continue..."
}

configure_encryption_key() {
    echo ""
    echo -e "${BOLD}Configure Encryption Key${NC}"
    echo -e "${YELLOW}Used for encrypting API keys at rest (ADR-031)${NC}"
    echo ""

    local GENERATE_ENCRYPTION_KEY=false

    if [ -f "$PROJECT_ROOT/.env" ] && grep -q "^ENCRYPTION_KEY=" "$PROJECT_ROOT/.env"; then
        echo -e "${GREEN}✓${NC} Encryption key already configured in .env"
        read -p "Generate new encryption key? [y/N]: " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${RED}⚠${NC}  Warning: Existing encrypted API keys will become unreadable!"
            read -p "Continue? [y/N]: " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                GENERATE_ENCRYPTION_KEY=true
            fi
        fi
    else
        echo -e "${BLUE}→${NC} No encryption key found in .env"
        GENERATE_ENCRYPTION_KEY=true
    fi

    if [ "$GENERATE_ENCRYPTION_KEY" = true ]; then
        # Generate Fernet-compatible key (32 bytes, base64-encoded)
        local ENCRYPTION_KEY=$($PYTHON -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
        echo -e "${GREEN}✓${NC} Generated encryption key using Fernet"

        # Update or create .env file
        if [ -f "$PROJECT_ROOT/.env" ]; then
            if grep -q "^ENCRYPTION_KEY=" "$PROJECT_ROOT/.env"; then
                sed "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENCRYPTION_KEY|" "$PROJECT_ROOT/.env" > "$PROJECT_ROOT/.env.tmp" && mv "$PROJECT_ROOT/.env.tmp" "$PROJECT_ROOT/.env"
            else
                echo "" >> "$PROJECT_ROOT/.env"
                echo "# Master encryption key for API keys (ADR-031)" >> "$PROJECT_ROOT/.env"
                echo "ENCRYPTION_KEY=$ENCRYPTION_KEY" >> "$PROJECT_ROOT/.env"
            fi
        else
            cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env" 2>/dev/null || true
            echo "" >> "$PROJECT_ROOT/.env"
            echo "# Master encryption key for API keys (ADR-031)" >> "$PROJECT_ROOT/.env"
            echo "ENCRYPTION_KEY=$ENCRYPTION_KEY" >> "$PROJECT_ROOT/.env"
        fi
        echo -e "${GREEN}✓${NC} Encryption key saved to .env"

        # Check if there are any existing encrypted keys that are now unreadable
        local encrypted_keys=$(pg_query "SELECT COUNT(*) FROM kg_api.system_api_keys" | xargs)
        if [ "$encrypted_keys" -gt "0" ]; then
            echo ""
            echo -e "${RED}⚠${NC}  ${BOLD}IMPORTANT:${NC} You must reconfigure all API keys!"
            echo -e "${RED}   All existing encrypted keys are now unreadable.${NC}"
            echo ""
            echo "   Next steps:"
            echo "   1. Restart API server: ./scripts/services/stop-api.sh && ./scripts/services/start-api.sh"
            echo "   2. Run option 6 (API Keys) to reconfigure each provider"
        fi
    fi

    echo ""
    read -p "Press Enter to continue..."
}

configure_ai_provider() {
    echo ""
    echo -e "${BOLD}Configure AI Extraction Provider${NC}"
    echo -e "${YELLOW}For concept extraction (ADR-041)${NC}"
    echo ""

    # Check current provider
    local CURRENT_PROVIDER=$(pg_query "SELECT provider FROM kg_api.ai_extraction_config WHERE active = true LIMIT 1" | xargs)

    if [ -n "$CURRENT_PROVIDER" ]; then
        echo -e "${BLUE}→${NC} Current provider: ${BOLD}${CURRENT_PROVIDER}${NC}"
    else
        echo -e "${BLUE}→${NC} Current provider: ${YELLOW}unconfigured${NC}"
    fi
    echo ""

    echo "Select AI provider:"
    echo "  1) OpenAI (GPT-4o) - Recommended"
    echo "  2) Anthropic (Claude Sonnet 4)"
    if [ -n "$CURRENT_PROVIDER" ]; then
        echo "  3) Keep current ($CURRENT_PROVIDER)"
    else
        echo "  3) Skip (configure later)"
    fi
    echo ""
    read -p "Choice [1-3]: " -n 1 -r
    echo ""
    echo ""

    # If user chose option 3 (keep current or skip)
    if [ "$REPLY" = "3" ]; then
        if [ -n "$CURRENT_PROVIDER" ]; then
            echo -e "${GREEN}✓${NC} Keeping current AI extraction provider: $CURRENT_PROVIDER"
        else
            echo -e "${YELLOW}⚠${NC}  Skipping AI provider configuration"
        fi
        echo ""
        read -p "Press Enter to continue..."
        return
    fi

    if [[ $REPLY =~ ^[12]$ ]]; then
        local PROVIDER_NAME PROVIDER_DISPLAY DEFAULT_MODEL

        if [ "$REPLY" = "1" ]; then
            PROVIDER_NAME="openai"
            PROVIDER_DISPLAY="OpenAI"
            DEFAULT_MODEL="gpt-4o"
        else
            PROVIDER_NAME="anthropic"
            PROVIDER_DISPLAY="Anthropic"
            DEFAULT_MODEL="claude-sonnet-4-20250514"
        fi

        # Check if API key exists, configure if needed
        configure_single_api_key "$PROVIDER_NAME" "$PROVIDER_DISPLAY"
        local key_result=$?

        if [ $key_result -eq 0 ]; then
            # Key is configured (either pre-existing or just added) - proceed with provider setup
            echo ""
            echo -e "${BLUE}→${NC} Initializing AI extraction configuration..."

            set +e
            local CONFIG_RESULT=$(PROJECT_ROOT="$PROJECT_ROOT" PROVIDER_NAME_CONFIG="$PROVIDER_NAME" DEFAULT_MODEL_CONFIG="$DEFAULT_MODEL" $PYTHON << 'EOF' 2>&1
import sys
import os
sys.path.insert(0, os.getenv("PROJECT_ROOT", "."))
from src.api.lib.ai_extraction_config import save_extraction_config
provider = os.getenv("PROVIDER_NAME_CONFIG")
model = os.getenv("DEFAULT_MODEL_CONFIG")
config = {
    "provider": provider,
    "model_name": model,
    "supports_vision": True,
    "supports_json_mode": True,
    "max_tokens": 16384 if provider == "openai" else 8192
}
try:
    success = save_extraction_config(config, updated_by="initialize-platform.sh")
    if success:
        print("SUCCESS")
    else:
        print("ERROR:Failed to save configuration")
        sys.exit(1)
except Exception as e:
    print(f"ERROR:{e}")
    sys.exit(1)
EOF
)
                set -e

            if echo "$CONFIG_RESULT" | grep -q "^SUCCESS"; then
                echo -e "${GREEN}✓${NC} AI extraction configured: $PROVIDER_DISPLAY / $DEFAULT_MODEL"
            else
                local ERROR_MSG=$(echo "$CONFIG_RESULT" | grep "^ERROR:" | cut -d: -f2-)
                echo -e "${YELLOW}⚠${NC}  Failed to configure AI extraction: $ERROR_MSG"
            fi
        else
            # Key configuration was skipped
            echo -e "${YELLOW}⚠${NC}  Skipping AI provider configuration (no API key)"
        fi
    else
        echo -e "${YELLOW}⚠${NC}  Skipping AI provider configuration"
    fi

    echo ""
    read -p "Press Enter to continue..."
}

configure_embedding_provider() {
    echo ""
    echo -e "${BOLD}Configure Embedding Provider${NC}"
    echo -e "${YELLOW}For concept similarity (ADR-039)${NC}"
    echo -e "${YELLOW}This configures cold-start before first API startup${NC}"
    echo ""

    # Check current embedding provider
    local CURRENT_EMBEDDING=$(pg_query "SELECT provider FROM kg_api.embedding_config WHERE active = true LIMIT 1" | xargs)

    if [ -n "$CURRENT_EMBEDDING" ]; then
        echo -e "${BLUE}→${NC} Current embedding provider: ${BOLD}${CURRENT_EMBEDDING}${NC}"
    else
        echo -e "${BLUE}→${NC} Current embedding provider: ${YELLOW}unconfigured${NC}"
    fi
    echo ""

    echo "Available providers:"
    echo "  1) OpenAI (text-embedding-3-small) - 1536 dimensions, cloud-based"
    echo "  2) Nomic (nomic-embed-text-v1.5) - 768 dimensions, local inference"
    if [ -n "$CURRENT_EMBEDDING" ]; then
        echo "  3) Keep current ($CURRENT_EMBEDDING)"
        echo "  4) Skip (use OpenAI default)"
        echo ""
        read -p "Choice [1-4]: " -n 1 -r
    else
        echo "  3) Skip (use OpenAI default)"
        echo ""
        read -p "Choice [1-3]: " -n 1 -r
    fi
    echo ""
    echo ""

    # If user chose "keep current" option
    if [ -n "$CURRENT_EMBEDDING" ] && [ "$REPLY" = "3" ]; then
        echo -e "${GREEN}✓${NC} Keeping current embedding provider: $CURRENT_EMBEDDING"
        echo ""
        read -p "Press Enter to continue..."
        return
    fi

    if [[ $REPLY =~ ^[12]$ ]]; then
        local EMBEDDING_PROVIDER EMBEDDING_MODEL EMBEDDING_DISPLAY EMBEDDING_DIMS

        if [ "$REPLY" = "1" ]; then
            EMBEDDING_PROVIDER="openai"
            EMBEDDING_MODEL="text-embedding-3-small"
            EMBEDDING_DISPLAY="OpenAI (text-embedding-3-small)"
            EMBEDDING_DIMS=1536

            # OpenAI embeddings require API key - check and configure if needed
            configure_single_api_key "openai" "OpenAI"
            local key_result=$?

            if [ $key_result -ne 0 ]; then
                echo -e "${YELLOW}⚠${NC}  Cannot configure OpenAI embeddings without API key"
                echo ""
                read -p "Press Enter to continue..."
                return
            fi
        else
            EMBEDDING_PROVIDER="local"
            EMBEDDING_MODEL="nomic-ai/nomic-embed-text-v1.5"
            EMBEDDING_DISPLAY="Nomic (nomic-embed-text-v1.5)"
            EMBEDDING_DIMS=768
            # Local embeddings don't need API keys
        fi

        echo ""
        echo -e "${BLUE}→${NC} Configuring ${EMBEDDING_DISPLAY}..."

        set +e
        local EMBEDDING_RESULT=$(PROJECT_ROOT="$PROJECT_ROOT" EMBEDDING_PROVIDER_CONFIG="$EMBEDDING_PROVIDER" EMBEDDING_MODEL_CONFIG="$EMBEDDING_MODEL" EMBEDDING_DIMS_CONFIG="$EMBEDDING_DIMS" $PYTHON << 'EOF' 2>&1
import sys
import os
sys.path.insert(0, os.getenv("PROJECT_ROOT", "."))
from src.api.lib.embedding_config import save_embedding_config
provider = os.getenv("EMBEDDING_PROVIDER_CONFIG")
model = os.getenv("EMBEDDING_MODEL_CONFIG")
dims = int(os.getenv("EMBEDDING_DIMS_CONFIG"))
config = {
    "provider": provider,
    "model_name": model,
    "embedding_dimensions": dims,
    "precision": "float16" if provider == "local" else None,
    "supports_batch": True
}
try:
    success, message, config_id = save_embedding_config(config, updated_by="initialize-platform.sh", force_change=True)
    if success:
        from src.api.lib.embedding_config import activate_embedding_config
        activate_embedding_config(config_id)
        print("SUCCESS")
    else:
        print("ERROR:Failed to save configuration")
        sys.exit(1)
except Exception as e:
    print(f"ERROR:{e}")
    sys.exit(1)
EOF
)
        set -e

        if echo "$EMBEDDING_RESULT" | grep -q "^SUCCESS"; then
            echo -e "${GREEN}✓${NC} ${EMBEDDING_DISPLAY} configured"
            echo -e "${YELLOW}   Cold-start will use ${EMBEDDING_DISPLAY} for builtin vocabulary${NC}"
        else
            local ERROR_MSG=$(echo "$EMBEDDING_RESULT" | grep "^ERROR:" | cut -d: -f2-)
            echo -e "${YELLOW}⚠${NC}  Failed to configure embedding provider: $ERROR_MSG"
            echo -e "${YELLOW}   Configure after startup via: kg admin embedding activate ${REPLY} --force${NC}"
        fi
    else
        echo -e "${YELLOW}⚠${NC}  Using OpenAI default embedding provider"
    fi

    echo ""
    read -p "Press Enter to continue..."
}

configure_api_keys() {
    echo ""
    echo -e "${BOLD}Manage API Keys${NC}"
    echo -e "${YELLOW}View, add, or replace encrypted API keys (ADR-031)${NC}"
    echo ""

    # Query existing API keys
    echo -e "${BLUE}→${NC} Checking configured API keys..."
    local openai_exists=$(pg_query "SELECT COUNT(*) FROM kg_api.system_api_keys WHERE provider = 'openai'" | xargs)
    local anthropic_exists=$(pg_query "SELECT COUNT(*) FROM kg_api.system_api_keys WHERE provider = 'anthropic'" | xargs)

    # Query provider configuration for context
    local extraction_provider=$(pg_query "SELECT provider FROM kg_api.ai_extraction_config WHERE active = true LIMIT 1" | xargs)
    local embedding_provider=$(pg_query "SELECT provider FROM kg_api.embedding_config WHERE active = true LIMIT 1" | xargs)

    echo ""
    echo -e "${BOLD}Current Configuration:${NC}"
    echo ""

    # Show provider config
    echo -e "${BOLD}Providers:${NC}"
    if [ -n "$extraction_provider" ] || [ -n "$embedding_provider" ]; then
        echo -e "  AI Extraction:  ${extraction_provider:-${YELLOW}not configured${NC}}"
        echo -e "  Embedding:      ${embedding_provider:-${YELLOW}not configured${NC}}"
    else
        echo -e "  ${YELLOW}No providers configured yet${NC}"
    fi
    echo ""

    # Show API key status
    echo -e "${BOLD}API Keys:${NC}"
    if [ "$openai_exists" -gt "0" ]; then
        echo -e "  OpenAI:     ${GREEN}✓ configured${NC}"
    else
        echo -e "  OpenAI:     ${YELLOW}○ not configured${NC}"
    fi

    if [ "$anthropic_exists" -gt "0" ]; then
        echo -e "  Anthropic:  ${GREEN}✓ configured${NC}"
    else
        echo -e "  Anthropic:  ${YELLOW}○ not configured${NC}"
    fi
    echo ""

    # Show which keys are needed (if providers configured)
    local needs_openai=false
    local needs_anthropic=false
    if [ "$extraction_provider" = "openai" ] || [ "$embedding_provider" = "openai" ]; then
        needs_openai=true
    fi
    if [ "$extraction_provider" = "anthropic" ]; then
        needs_anthropic=true
    fi

    if [ "$needs_openai" = true ] || [ "$needs_anthropic" = true ]; then
        echo -e "${BOLD}Keys Needed for Current Providers:${NC}"
        [ "$needs_openai" = true ] && echo -e "  • OpenAI (for ${extraction_provider:-}${embedding_provider:+ / }${embedding_provider:-})"
        [ "$needs_anthropic" = true ] && echo -e "  • Anthropic (for extraction)"
        echo ""
    fi

    # Always offer key management options
    echo -e "${BOLD}What would you like to do?${NC}"
    echo "  1) View detailed key status (masked values, validation)"
    echo "  2) Add/Replace OpenAI API key"
    echo "  3) Add/Replace Anthropic API key"
    echo "  4) Configure all needed keys (based on providers)"
    echo "  5) Return to main menu"
    echo ""
    read -p "Choice [1-5]: " -n 1 -r
    echo ""
    echo ""

    export PROJECT_ROOT
    export PYTHON

    case $REPLY in
        1)
            # List keys with details
            echo -e "${BLUE}→${NC} Fetching key details..."
            echo ""
            "$PYTHON" "$PROJECT_ROOT/scripts/admin/manage_api_keys.py" --list
            ;;
        2)
            # Configure OpenAI key
            configure_single_api_key "openai" "OpenAI"
            ;;
        3)
            # Configure Anthropic key
            configure_single_api_key "anthropic" "Anthropic"
            ;;
        4)
            # Configure all needed keys
            if [ "$needs_openai" = false ] && [ "$needs_anthropic" = false ]; then
                echo -e "${YELLOW}⚠${NC}  No API keys required for current provider configuration"
                echo -e "${YELLOW}   (Configure providers first, or use options 2-3 to add keys anyway)${NC}"
            else
                echo -e "${BLUE}→${NC} Configuring keys for current providers..."
                echo ""
                if [ "$needs_openai" = true ]; then
                    configure_single_api_key "openai" "OpenAI"
                    echo ""
                fi
                if [ "$needs_anthropic" = true ]; then
                    configure_single_api_key "anthropic" "Anthropic"
                fi
            fi
            ;;
        5)
            # Return to main menu
            return
            ;;
        *)
            echo -e "${YELLOW}Invalid choice${NC}"
            ;;
    esac

    echo ""
    read -p "Press Enter to continue..."
}

# Configure MinIO storage (ADR-057)
configure_minio() {
    echo ""
    echo -e "${BOLD}MinIO Object Storage Configuration (ADR-057)${NC}"
    echo -e "${YELLOW}Credentials are encrypted at rest (ADR-031)${NC}"
    echo ""

    # Check encryption key exists (required for storing credentials)
    if ! grep -q "^ENCRYPTION_KEY=" "$PROJECT_ROOT/.env" 2>/dev/null; then
        echo -e "${RED}✗${NC} Encryption key not configured"
        echo ""
        echo "Run option 3 (Configure Encryption Key) first"
        echo ""
        read -p "Press Enter to continue..."
        return
    fi

    # Check if MinIO is running (optional - can configure credentials without it)
    local minio_running=false
    echo -e "${BLUE}→${NC} Checking MinIO availability..."

    if [ "$DEPLOYMENT_MODE" = "docker" ]; then
        # Docker deployment - check for container
        if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^knowledge-graph-minio$"; then
            echo -e "${GREEN}✓${NC} MinIO container detected (knowledge-graph-minio)"
            minio_running=true
        else
            echo -e "${YELLOW}⚠${NC}  MinIO container not running (can still configure credentials)"
        fi
    else
        # Non-Docker - try to reach MinIO endpoint
        local minio_host=$(grep "^MINIO_HOST=" "$PROJECT_ROOT/.env" 2>/dev/null | cut -d'=' -f2 || echo "localhost")
        local minio_port=$(grep "^MINIO_PORT=" "$PROJECT_ROOT/.env" 2>/dev/null | cut -d'=' -f2 || echo "9000")

        if command -v curl &> /dev/null && curl -sf "http://${minio_host}:${minio_port}/minio/health/live" > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} MinIO service reachable (${minio_host}:${minio_port})"
            minio_running=true
        else
            echo -e "${YELLOW}⚠${NC}  MinIO not reachable at ${minio_host}:${minio_port} (can still configure credentials)"
        fi
    fi
    echo ""

    # Check if credentials already configured in database
    local key_exists=$(pg_query "SELECT COUNT(*) FROM kg_api.system_api_keys WHERE provider = 'minio'" | xargs)

    if [ "$key_exists" -gt "0" ]; then
        echo -e "${GREEN}✓${NC} MinIO credentials already configured in encrypted key store"
        echo ""
        read -p "Reconfigure? (y/N): " reconfigure
        if [ "$reconfigure" != "y" ] && [ "$reconfigure" != "Y" ]; then
            return
        fi
    fi

    # Configure endpoint settings in .env (not credentials!)
    echo -e "${BLUE}→${NC} Configuring MinIO endpoint settings..."
    if ! grep -q "# MinIO Object Storage Configuration" "$PROJECT_ROOT/.env" 2>/dev/null; then
        cat >> "$PROJECT_ROOT/.env" << 'EOF'

# ----------------------------------------------------------------------------
# MinIO Object Storage Configuration (ADR-057)
# ----------------------------------------------------------------------------
# Credentials stored encrypted in database (ADR-031)
# Only endpoint configuration in .env
MINIO_HOST=localhost
MINIO_PORT=9000
MINIO_BUCKET=images
MINIO_SECURE=false
EOF
        echo -e "${GREEN}✓${NC} MinIO endpoint settings added to .env"
    else
        echo -e "${YELLOW}⚠${NC}  MinIO section already exists in .env"
    fi
    echo ""

    # Store credentials in encrypted key store
    echo -e "${BLUE}→${NC} Configuring MinIO credentials..."
    echo ""

    # Prompt for credentials
    echo "Enter MinIO credentials (from docker-compose.yml or MinIO console):"
    echo ""
    read -p "Access Key [minioadmin]: " access_key
    access_key=${access_key:-minioadmin}

    read -sp "Secret Key [minioadmin]: " secret_key
    echo ""
    secret_key=${secret_key:-minioadmin}

    # Store in encrypted key store
    local temp_script=$(mktemp)
    cat > "$temp_script" << EOF
#!/usr/bin/env python3
import sys
sys.path.insert(0, "$PROJECT_ROOT")
from src.api.lib.encrypted_keys import EncryptedKeyStore
from src.api.lib.age_client import AGEClient

try:
    client = AGEClient()
    conn = client.pool.getconn()
    try:
        key_store = EncryptedKeyStore(conn)
        # Store as "access_key:secret_key" format
        credentials = "${access_key}:${secret_key}"
        key_store.store_key("minio", credentials)
        print("✓ MinIO credentials stored in encrypted key store")
        sys.exit(0)
    finally:
        client.pool.putconn(conn)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
EOF

    $PYTHON "$temp_script"
    local result=$?
    rm -f "$temp_script"

    if [ $result -ne 0 ]; then
        echo ""
        echo -e "${RED}✗${NC} Failed to store MinIO credentials"
        read -p "Press Enter to continue..."
        return
    fi

    echo ""

    # Run initialization script (only if MinIO is running)
    if [ "$minio_running" = true ]; then
        echo -e "${BLUE}→${NC} Initializing MinIO bucket..."
        if [ -x "$PROJECT_ROOT/scripts/minio/init-minio.sh" ]; then
            "$PROJECT_ROOT/scripts/minio/init-minio.sh"
            echo ""
            echo -e "${GREEN}✓${NC} MinIO bucket initialized"
        else
            echo -e "${YELLOW}⚠${NC}  MinIO init script not found or not executable"
            echo "    Expected location: $PROJECT_ROOT/scripts/minio/init-minio.sh"
            echo "    You can run it manually later: ./scripts/minio/init-minio.sh"
        fi
    else
        echo -e "${YELLOW}⚠${NC}  Skipping bucket initialization (MinIO not running)"
        echo "    Start MinIO and run: ./scripts/minio/init-minio.sh"
    fi
    echo ""

    # Success message
    echo -e "${GREEN}✓${NC} MinIO credentials configured successfully"
    echo ""
    echo -e "${BOLD}Next Steps:${NC}"

    if [ "$minio_running" = false ]; then
        echo "1. Start MinIO:"
        if [ "$DEPLOYMENT_MODE" = "docker" ]; then
            echo "   ./scripts/services/start-minio.sh"
        else
            echo "   Start your MinIO service (configuration in .env)"
        fi
        echo ""
        echo "2. Initialize bucket:"
        echo "   ./scripts/minio/init-minio.sh"
        echo ""
        echo "3. Restart API server to pick up MinIO credentials:"
    else
        echo "1. Restart API server to pick up MinIO credentials:"
    fi
    echo "   ./scripts/services/stop-api.sh && ./scripts/services/start-api.sh"
    echo ""

    read -p "Press Enter to continue..."
}

# View image embedding configuration (read-only for now)
configure_image_embedding() {
    echo ""
    echo -e "${BOLD}Image Embedding Configuration (Read-Only)${NC}"
    echo -e "${YELLOW}View current visual embedding model for image similarity${NC}"
    echo ""

    # Image embeddings are currently hardcoded to Nomic Vision v1.5
    # This is a placeholder for future configurability
    echo -e "${BLUE}→${NC} Current configuration:"
    echo ""
    echo -e "  ${BOLD}Model:${NC}        nomic-ai/nomic-embed-vision-v1.5"
    echo -e "  ${BOLD}Dimensions:${NC}   768 (same space as Nomic Text embeddings)"
    echo -e "  ${BOLD}Inference:${NC}    Local (transformers library, not Ollama)"
    echo -e "  ${BOLD}Performance:${NC}  ~1-2ms per image (GPU), ~5-10ms (CPU fallback)"
    echo ""
    echo -e "${GREEN}✓${NC} Research validated (ADR-057):"
    echo "    • 0.847 average top-3 similarity"
    echo "    • 27% better than OpenAI CLIP"
    echo "    • Excellent clustering for similar images"
    echo ""
    echo -e "${YELLOW}Note:${NC} Image embedding provider is not configurable yet."
    echo "      Nomic Vision v1.5 is the default and recommended model."
    echo ""
    echo -e "${YELLOW}Future:${NC} If you need to add another provider (e.g., OpenAI CLIP):"
    echo "      1. Implement provider in src/api/lib/visual_embeddings.py"
    echo "      2. Add database config table (similar to embedding_config)"
    echo "      3. Update this configuration option to support selection"
    echo ""

    read -p "Press Enter to continue..."
}

# Display help in menu context
show_menu_help() {
    clear
    echo -e "${BLUE}${BOLD}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║             Configuration Manager - Help                   ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "${BOLD}Purpose:${NC}"
    echo "Pre-configure database settings BEFORE the API server starts to ensure"
    echo "clean first-time initialization and avoid cold-start configuration issues."
    echo ""
    echo -e "${BOLD}What This Script Configures:${NC}"
    echo ""
    echo -e "${BLUE}1. Admin Password${NC}"
    echo "   Set known username/password for first login (kg login -u admin)"
    echo ""
    echo -e "${BLUE}2. OAuth Signing Key${NC}"
    echo "   Generate secret key for signing OAuth 2.0 access tokens (ADR-054)"
    echo "   Stored in .env file as OAUTH_SIGNING_KEY"
    echo ""
    echo -e "${BLUE}3. Encryption Key${NC}"
    echo "   Generate master key for encrypting API keys at rest (ADR-031)"
    echo "   Stored in .env file as ENCRYPTION_KEY"
    echo ""
    echo -e "${BLUE}4. AI Extraction Provider${NC}"
    echo "   Configure which LLM to use for concept extraction"
    echo "   Options: OpenAI (GPT-4), Anthropic (Claude), Ollama (Local)"
    echo ""
    echo -e "${BLUE}5. Embedding Provider (Text)${NC}"
    echo "   Configure which embedding model to use for text/concepts"
    echo "   Options:"
    echo "     • OpenAI (text-embedding-3-small) - Cloud API, fast, costs ~$0.02/1M tokens"
    echo "     • Local (nomic-embed-text-v1.5) - Free, local inference via Ollama"
    echo "       768-dim embeddings, same space as Nomic Vision for images"
    echo ""
    echo -e "${BLUE}6. API Keys${NC}"
    echo "   Store encrypted API keys for configured providers"
    echo "   Keys are independent: OpenAI extraction + local embedding = only needs OpenAI key"
    echo ""
    echo -e "${BLUE}7. MinIO Storage${NC}"
    echo "   Configure S3-compatible object storage for image assets (ADR-057)"
    echo "   Credentials stored encrypted in database (same as OpenAI/Anthropic keys)"
    echo ""
    echo -e "${BLUE}8. Image Embedding Model${NC}"
    echo "   View current image embedding configuration (read-only)"
    echo "   Default: Nomic Vision v1.5 (768-dim, local inference)"
    echo "   Research: 27% better than CLIP for visual similarity"
    echo ""
    echo -e "${BOLD}Why Pre-Configure?${NC}"
    echo ""
    echo -e "${YELLOW}Cold-Start Problem:${NC}"
    echo "If you don't configure embedding provider before first API startup:"
    echo "  • API defaults to OpenAI embeddings"
    echo "  • Vocabulary metadata gets OpenAI embeddings"
    echo "  • Later switching to local requires regenerating ALL embeddings"
    echo ""
    echo "Pre-configuring avoids this by setting the correct provider from the start."
    echo ""
    echo -e "${BOLD}Docker vs Non-Docker:${NC}"
    echo "This script works with both deployment modes. All database operations use"
    echo "Python + psycopg2 (reads POSTGRES_HOST from .env), not docker exec commands."
    echo ""
    read -p "Press Enter to return to menu..."
}

# Main menu loop
while true; do
    show_menu
    read -p "Select option [1-8, h, q]: " choice

    case $choice in
        1)
            configure_admin
            ;;
        2)
            configure_oauth_key
            ;;
        3)
            configure_encryption_key
            ;;
        4)
            configure_ai_provider
            ;;
        5)
            configure_embedding_provider
            ;;
        6)
            configure_api_keys
            ;;
        7)
            configure_minio
            ;;
        8)
            configure_image_embedding
            ;;
        h|H)
            show_menu_help
            ;;
        q|Q)
            echo ""
            echo -e "${GREEN}Configuration complete!${NC}"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            sleep 1
            ;;
    esac
done
