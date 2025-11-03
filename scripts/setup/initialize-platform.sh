#!/bin/bash
set -e

# initialize-auth-menu.sh
# Interactive menu-driven configuration for Knowledge Graph System
# Refactored version with menu loop for selective configuration

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

# Parse command line arguments
DEV_MODE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            DEV_MODE=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: $0 [--dev]"
            echo "  --dev    Development mode (sets password to 'Password1!')"
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

# Banner
clear
echo -e "${BLUE}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Knowledge Graph System - Configuration Manager          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check PostgreSQL
echo -e "${BLUE}→${NC} Checking PostgreSQL connection..."
if ! docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${RED}✗ PostgreSQL is not running${NC}"
    echo -e "${YELLOW}  Run: docker-compose up -d${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} PostgreSQL is running"
echo ""

# PostgreSQL connection details
POSTGRES_HOST=${POSTGRES_HOST:-localhost}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_DB=${POSTGRES_DB:-knowledge_graph}
POSTGRES_USER=${POSTGRES_USER:-admin}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-password}

# Check current configuration status with indicators
# ✓ = configured, ⚠ = needs attention, ○ = not configured

get_admin_status() {
    local exists=$(docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -t -c \
        "SELECT COUNT(*) FROM kg_auth.users WHERE username = 'admin'" 2>/dev/null | xargs)
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
    local provider=$(docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -t -A -c \
        "SELECT provider FROM kg_config.extraction_config WHERE is_active = true LIMIT 1" 2>/dev/null | xargs)
    if [ -n "$provider" ]; then
        echo -e "${GREEN}✓${NC} ${provider}"
    else
        echo -e "○ unconfigured"
    fi
}

get_embedding_provider_status() {
    local provider=$(docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -t -A -c \
        "SELECT provider FROM kg_config.embedding_config WHERE is_active = true LIMIT 1" 2>/dev/null | xargs)
    if [ -n "$provider" ]; then
        echo -e "${GREEN}✓${NC} ${provider}"
    else
        echo -e "○ unconfigured"
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
    echo -e "  6) Exit"
    echo ""
}

configure_admin() {
    echo ""
    echo -e "${BOLD}Configure Admin Password${NC}"
    echo ""

    export PROJECT_ROOT
    export PYTHON

    local admin_exists=$(docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -t -c \
        "SELECT COUNT(*) FROM kg_auth.users WHERE username = 'admin'" 2>/dev/null | xargs)

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
    local CURRENT_PROVIDER=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c \
        "SELECT provider FROM kg_config.extraction_config WHERE is_active = true LIMIT 1" 2>/dev/null | xargs)

    if [ -n "$CURRENT_PROVIDER" ]; then
        echo -e "${BLUE}→${NC} Current provider: ${BOLD}${CURRENT_PROVIDER}${NC}"
    else
        echo -e "${BLUE}→${NC} Current provider: ${YELLOW}unconfigured${NC}"
    fi
    echo ""

    echo "Select AI provider:"
    echo "  1) OpenAI (GPT-4o) - Recommended"
    echo "  2) Anthropic (Claude Sonnet 4)"
    echo "  3) Skip (configure later via API)"
    echo ""
    read -p "Choice [1-3]: " -n 1 -r
    echo ""
    echo ""

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

        echo -e "${BOLD}${PROVIDER_DISPLAY} API Key${NC}"
        echo -e "${YELLOW}Note: Keys are encrypted at rest (Fernet AES-128)${NC}"
        echo ""
        read -s -p "Enter ${PROVIDER_DISPLAY} API key: " API_KEY
        echo ""

        if [ -z "$API_KEY" ]; then
            echo -e "${YELLOW}⚠${NC}  No API key provided, skipping AI configuration"
        else
            echo -e "${BLUE}→${NC} Validating and storing ${PROVIDER_DISPLAY} API key..."

            set +e
            local STORE_RESULT=$(PROJECT_ROOT="$PROJECT_ROOT" API_KEY_TO_STORE="$API_KEY" PROVIDER_NAME_TO_STORE="$PROVIDER_NAME" $PYTHON << 'EOF' 2>&1
import sys
import os
sys.path.insert(0, os.getenv("PROJECT_ROOT", "."))
from src.api.lib.age_client import AGEClient
from src.api.lib.encrypted_keys import EncryptedKeyStore
try:
    provider = os.getenv("PROVIDER_NAME_TO_STORE")
    api_key = os.getenv("API_KEY_TO_STORE")
    if not provider or not api_key:
        print("ERROR:Missing provider or API key")
        sys.exit(1)
    client = AGEClient()
    conn = client.pool.getconn()
    try:
        key_store = EncryptedKeyStore(conn)
        key_store.store_key(provider, api_key)
        key_store.update_validation_status(provider, "valid")
        print("SUCCESS")
    finally:
        client.pool.putconn(conn)
except Exception as e:
    print(f"ERROR:{e}")
    sys.exit(1)
EOF
)
            set -e

            if echo "$STORE_RESULT" | grep -q "^SUCCESS"; then
                echo -e "${GREEN}✓${NC} ${PROVIDER_DISPLAY} API key stored and validated"

                # Initialize AI extraction configuration
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
                local ERROR_MSG=$(echo "$STORE_RESULT" | grep "^ERROR:" | cut -d: -f2-)
                echo -e "${RED}✗${NC} Failed to store API key: $ERROR_MSG"
                echo -e "${YELLOW}   You can configure this later via: POST /admin/keys/$PROVIDER_NAME${NC}"
            fi
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
    local CURRENT_EMBEDDING=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c \
        "SELECT provider FROM kg_config.embedding_config WHERE is_active = true LIMIT 1" 2>/dev/null | xargs)

    if [ -n "$CURRENT_EMBEDDING" ]; then
        echo -e "${BLUE}→${NC} Current embedding provider: ${BOLD}${CURRENT_EMBEDDING}${NC}"
    else
        echo -e "${BLUE}→${NC} Current embedding provider: ${YELLOW}unconfigured${NC}"
    fi
    echo ""

    echo "Available providers:"
    echo "  1) OpenAI (text-embedding-3-small) - 1536 dimensions, cloud-based"
    echo "  2) Nomic (nomic-embed-text-v1.5) - 768 dimensions, local inference"
    echo "  3) Skip (use OpenAI default)"
    echo ""
    read -p "Choice [1-3]: " -n 1 -r
    echo ""
    echo ""

    if [[ $REPLY =~ ^[12]$ ]]; then
        local EMBEDDING_PROVIDER EMBEDDING_MODEL EMBEDDING_DISPLAY EMBEDDING_DIMS

        if [ "$REPLY" = "1" ]; then
            EMBEDDING_PROVIDER="openai"
            EMBEDDING_MODEL="text-embedding-3-small"
            EMBEDDING_DISPLAY="OpenAI (text-embedding-3-small)"
            EMBEDDING_DIMS=1536
        else
            EMBEDDING_PROVIDER="local"
            EMBEDDING_MODEL="nomic-ai/nomic-embed-text-v1.5"
            EMBEDDING_DISPLAY="Nomic (nomic-embed-text-v1.5)"
            EMBEDDING_DIMS=768
        fi

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
    config_id = save_embedding_config(config, created_by="initialize-platform.sh")
    if config_id:
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

# Main menu loop
while true; do
    show_menu
    read -p "Select option [1-6]: " choice

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
        6|q|Q)
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
