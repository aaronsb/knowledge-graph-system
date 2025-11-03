#!/bin/bash
set -e

# Trap errors for debugging
trap 'echo "ERROR at line $LINENO: Command exited with status $?" >&2' ERR

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Parse arguments
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

# Use venv Python if available, otherwise system python3
if [ -f "$PROJECT_ROOT/venv/bin/python" ]; then
    PYTHON="$PROJECT_ROOT/venv/bin/python"
    PIP="$PROJECT_ROOT/venv/bin/pip"
elif [ -f "$PROJECT_ROOT/venv/bin/python3" ]; then
    PYTHON="$PROJECT_ROOT/venv/bin/python3"
    PIP="$PROJECT_ROOT/venv/bin/pip"
else
    PYTHON="python3"
    PIP="pip3"
    echo -e "${YELLOW}⚠${NC}  Virtual environment not found, using system Python"
fi

# Check and install required Python packages
echo -e "${BLUE}→${NC} Checking Python dependencies..."
MISSING_PACKAGES=()

# Check for required packages
for package in passlib psycopg2 cryptography; do
    if ! $PYTHON -c "import ${package/psycopg2/psycopg2}" &>/dev/null; then
        MISSING_PACKAGES+=("$package")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠${NC}  Missing required packages: ${MISSING_PACKAGES[*]}"
    echo -e "${BLUE}→${NC} Installing missing packages..."

    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        $PIP install -r "$PROJECT_ROOT/requirements.txt" -q
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓${NC} Dependencies installed successfully"
        else
            echo -e "${RED}✗${NC} Failed to install dependencies"
            echo -e "${YELLOW}   Please run: pip install -r requirements.txt${NC}"
            exit 1
        fi
    else
        echo -e "${RED}✗${NC} requirements.txt not found"
        echo -e "${YELLOW}   Please install required packages manually${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} All required dependencies installed"
fi

echo -e "${BLUE}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Knowledge Graph System - Authentication Initialization   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

if [ "$DEV_MODE" = true ]; then
    echo -e "${YELLOW}⚠${NC}  ${BOLD}DEVELOPMENT MODE${NC} - Using default password"
    echo ""
fi

echo "This script will configure:"
echo "  • Admin user credentials (create or reset)"
echo "  • OAuth signing key (for access tokens)"
echo "  • Encryption key (for API key storage)"
echo "  • AI provider (OpenAI or Anthropic)"
echo "  • Embedding provider (OpenAI or Nomic local)"
echo ""
echo -e "${YELLOW}Note: Existing configuration can be kept or updated${NC}"
echo ""

# Check if PostgreSQL is running
echo -e "${BLUE}→${NC} Checking PostgreSQL connection..."
if ! docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${RED}✗ PostgreSQL is not running${NC}"
    echo -e "${YELLOW}  Run: docker-compose up -d${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} PostgreSQL is running"

# Check if admin user already exists
echo -e "${BLUE}→${NC} Checking if admin user exists..."
ADMIN_EXISTS=$(docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -t -c \
    "SELECT COUNT(*) FROM kg_auth.users WHERE username = 'admin'" 2>/dev/null | xargs)

if [ "$ADMIN_EXISTS" -gt "0" ]; then
    echo -e "${YELLOW}⚠${NC}  Admin user already exists"
    echo ""
    echo "What would you like to do?"
    echo "  1) Reset admin password"
    echo "  2) Skip password setup (keep existing)"
    echo "  3) Cancel initialization"
    echo ""
    read -p "Choice [1-3]: " -n 1 -r ADMIN_CHOICE
    echo ""
    echo ""

    if [ "$ADMIN_CHOICE" = "1" ]; then
        RESET_MODE=true
    elif [ "$ADMIN_CHOICE" = "2" ]; then
        echo -e "${YELLOW}→${NC} Keeping existing admin password"
        RESET_MODE=false
        SKIP_PASSWORD_SETUP=true
    else
        echo -e "${YELLOW}Initialization cancelled${NC}"
        exit 0
    fi
else
    echo -e "${GREEN}✓${NC} No admin user found (fresh installation)"
    RESET_MODE=false
    SKIP_PASSWORD_SETUP=false
fi

# Set admin password using dedicated script
if [ "${SKIP_PASSWORD_SETUP:-false}" = false ]; then
    echo ""
    echo -e "${BOLD}Admin Password Setup${NC}"

    # Call set-admin-password.sh to handle password setup
    SET_ADMIN_PASSWORD_SCRIPT="$PROJECT_ROOT/scripts/admin/set-admin-password.sh"

    if [ "$DEV_MODE" = true ]; then
        # Development mode: Use known password Password1!
        export ADMIN_PASSWORD="Password1!"
        if [ "$RESET_MODE" = true ]; then
            "$SET_ADMIN_PASSWORD_SCRIPT" --quiet --non-interactive
        else
            "$SET_ADMIN_PASSWORD_SCRIPT" --quiet --create --non-interactive
        fi
        echo -e "${GREEN}✓${NC} Admin password set to: ${BOLD}Password1!${NC} (dev mode)"
    else
        # Production mode: Interactive password prompt
        if [ "$RESET_MODE" = true ]; then
            "$SET_ADMIN_PASSWORD_SCRIPT" --quiet
        else
            "$SET_ADMIN_PASSWORD_SCRIPT" --quiet --create
        fi
    fi

    # Check if password was set successfully
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Failed to set admin password${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓${NC} Admin password configured"
else
    echo -e "${GREEN}✓${NC} Skipped admin password setup (keeping existing)"
fi

# Generate or check OAUTH_SIGNING_KEY
echo ""
echo -e "${BOLD}OAuth Token Signing Key Setup${NC}"
echo -e "${YELLOW}Used to sign OAuth 2.0 access tokens (ADR-054)${NC}"

if [ -f "$PROJECT_ROOT/.env" ] && grep -q "^OAUTH_SIGNING_KEY=" "$PROJECT_ROOT/.env"; then
    EXISTING_SECRET=$(grep "^OAUTH_SIGNING_KEY=" "$PROJECT_ROOT/.env" | cut -d'=' -f2)
    if [[ "$EXISTING_SECRET" == *"CHANGE_THIS"* ]]; then
        echo -e "${YELLOW}⚠${NC}  Insecure signing key found in .env"
        GENERATE_SECRET=true
    else
        echo -e "${GREEN}✓${NC} OAuth signing key already configured in .env"
        read -p "Generate new signing key? [y/N]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            GENERATE_SECRET=true
        else
            GENERATE_SECRET=false
        fi
    fi
else
    echo -e "${BLUE}→${NC} No OAuth signing key found in .env"
    GENERATE_SECRET=true
fi

if [ "$GENERATE_SECRET" = true ]; then
    # Try openssl first, fall back to Python
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
            # Update existing (cross-platform sed)
            sed "s/^OAUTH_SIGNING_KEY=.*/OAUTH_SIGNING_KEY=$OAUTH_SIGNING_KEY/" "$PROJECT_ROOT/.env" > "$PROJECT_ROOT/.env.tmp" && mv "$PROJECT_ROOT/.env.tmp" "$PROJECT_ROOT/.env"
        else
            # Append new
            echo "OAUTH_SIGNING_KEY=$OAUTH_SIGNING_KEY" >> "$PROJECT_ROOT/.env"
        fi
    else
        # Create new .env
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env" 2>/dev/null || true
        echo "OAUTH_SIGNING_KEY=$OAUTH_SIGNING_KEY" >> "$PROJECT_ROOT/.env"
    fi
    echo -e "${GREEN}✓${NC} OAuth signing key saved to .env"
fi

# Generate or check ENCRYPTION_KEY (ADR-031)
echo ""
echo -e "${BOLD}Encryption Key Setup (ADR-031)${NC}"
echo -e "${YELLOW}Used for encrypting API keys at rest${NC}"

if [ -f "$PROJECT_ROOT/.env" ] && grep -q "^ENCRYPTION_KEY=" "$PROJECT_ROOT/.env"; then
    echo -e "${GREEN}✓${NC} Encryption key already configured in .env"
    read -p "Generate new encryption key? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        GENERATE_ENCRYPTION_KEY=true
        echo -e "${RED}⚠${NC}  Warning: Existing encrypted API keys will become unreadable!"
        read -p "Continue? [y/N]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            GENERATE_ENCRYPTION_KEY=false
        fi
    else
        GENERATE_ENCRYPTION_KEY=false
    fi
else
    echo -e "${BLUE}→${NC} No encryption key found in .env"
    GENERATE_ENCRYPTION_KEY=true
fi

if [ "$GENERATE_ENCRYPTION_KEY" = true ]; then
    # Generate Fernet-compatible key (32 bytes, base64-encoded)
    ENCRYPTION_KEY=$($PYTHON -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    echo -e "${GREEN}✓${NC} Generated encryption key using Fernet"

    # Update or create .env file
    if [ -f "$PROJECT_ROOT/.env" ]; then
        if grep -q "^ENCRYPTION_KEY=" "$PROJECT_ROOT/.env"; then
            # Update existing (cross-platform sed)
            sed "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENCRYPTION_KEY|" "$PROJECT_ROOT/.env" > "$PROJECT_ROOT/.env.tmp" && mv "$PROJECT_ROOT/.env.tmp" "$PROJECT_ROOT/.env"
        else
            # Append new
            echo "" >> "$PROJECT_ROOT/.env"
            echo "# Master encryption key for API keys (ADR-031)" >> "$PROJECT_ROOT/.env"
            echo "ENCRYPTION_KEY=$ENCRYPTION_KEY" >> "$PROJECT_ROOT/.env"
        fi
    else
        # Create new .env
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env" 2>/dev/null || true
        echo "" >> "$PROJECT_ROOT/.env"
        echo "# Master encryption key for API keys (ADR-031)" >> "$PROJECT_ROOT/.env"
        echo "ENCRYPTION_KEY=$ENCRYPTION_KEY" >> "$PROJECT_ROOT/.env"
    fi
    echo -e "${GREEN}✓${NC} Encryption key saved to .env"
fi

# Admin password and database user are now handled by set-admin-password.sh (see above)

# AI Provider and API Key Setup (ADR-041)
echo ""
echo -e "${BOLD}AI Provider Configuration${NC}"
echo -e "${YELLOW}Configure AI provider for concept extraction (ADR-041)${NC}"
echo ""
echo "Select AI provider:"
echo "  1) OpenAI (GPT-4o) - Recommended"
echo "  2) Anthropic (Claude Sonnet 4)"
echo "  3) Skip (configure later via API)"
echo ""
read -p "Choice [1-3]: " -n 1 -r PROVIDER_CHOICE
echo ""
echo ""

if [[ $PROVIDER_CHOICE =~ ^[12]$ ]]; then
    if [ "$PROVIDER_CHOICE" = "1" ]; then
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

    # Debug: Confirm we got the key
    echo -e "${YELLOW}[DEBUG] API key length: ${#API_KEY}${NC}" >&2
    echo -e "${YELLOW}[DEBUG] Provider: $PROVIDER_NAME${NC}" >&2

    if [ -z "$API_KEY" ]; then
        echo -e "${YELLOW}⚠${NC}  No API key provided, skipping AI configuration"
    else
        echo -e "${BLUE}→${NC} Validating and storing ${PROVIDER_DISPLAY} API key..."
        echo -e "${YELLOW}[DEBUG] About to run Python script...${NC}" >&2

        # Store API key via Python script (pass key via environment to avoid heredoc escaping issues)
        # Temporarily disable 'set -e' so Python errors don't kill the script
        set +e
        STORE_RESULT=$(PROJECT_ROOT="$PROJECT_ROOT" API_KEY_TO_STORE="$API_KEY" PROVIDER_NAME_TO_STORE="$PROVIDER_NAME" $PYTHON << 'EOF' 2>&1
import sys
import os
sys.path.insert(0, os.getenv("PROJECT_ROOT", "."))

from src.api.lib.age_client import AGEClient
from src.api.lib.encrypted_keys import EncryptedKeyStore

try:
    # Get values from environment (to avoid bash heredoc escaping issues)
    provider = os.getenv("PROVIDER_NAME_TO_STORE")
    api_key = os.getenv("API_KEY_TO_STORE")

    if not provider or not api_key:
        print("ERROR:Missing provider or API key")
        sys.exit(1)

    # Connect to database
    client = AGEClient()
    conn = client.pool.getconn()

    try:
        # Initialize key store
        key_store = EncryptedKeyStore(conn)

        # Store the key (this also validates it)
        key_store.store_key(provider, api_key)

        # Mark as valid
        key_store.update_validation_status(provider, "valid")

        print("SUCCESS")
    finally:
        client.pool.putconn(conn)
except Exception as e:
    print(f"ERROR:{e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF
)
        # Re-enable 'set -e'
        set -e

        echo -e "${YELLOW}[DEBUG] Python script completed${NC}" >&2

        # Debug: Show what we got back
        if [ -z "$STORE_RESULT" ]; then
            echo -e "${RED}✗${NC} Python script produced no output (possible crash)"
            echo -e "${YELLOW}   Check that venv is activated and dependencies are installed${NC}"
        else
            echo -e "${YELLOW}[DEBUG] Store result:${NC}" >&2
            echo "$STORE_RESULT" >&2
        fi

        if echo "$STORE_RESULT" | grep -q "^SUCCESS"; then
            echo -e "${GREEN}✓${NC} ${PROVIDER_DISPLAY} API key stored and validated"

            # Initialize AI extraction configuration
            echo -e "${BLUE}→${NC} Initializing AI extraction configuration..."

            set +e
            CONFIG_RESULT=$(PROJECT_ROOT="$PROJECT_ROOT" PROVIDER_NAME_CONFIG="$PROVIDER_NAME" DEFAULT_MODEL_CONFIG="$DEFAULT_MODEL" $PYTHON << 'EOF' 2>&1
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
    success = save_extraction_config(config, updated_by="initialize-auth.sh")
    if success:
        print("SUCCESS")
    else:
        print("ERROR:Failed to save configuration")
        sys.exit(1)
except Exception as e:
    print(f"ERROR:{e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF
)
            set -e

            if echo "$CONFIG_RESULT" | grep -q "^SUCCESS"; then
                echo -e "${GREEN}✓${NC} AI extraction configured: $PROVIDER_DISPLAY / $DEFAULT_MODEL"
            else
                ERROR_MSG=$(echo "$CONFIG_RESULT" | grep "^ERROR:" | cut -d: -f2-)
                echo -e "${YELLOW}⚠${NC}  Failed to configure AI extraction: $ERROR_MSG"
            fi

        else
            ERROR_MSG=$(echo "$STORE_RESULT" | grep "^ERROR:" | cut -d: -f2-)
            echo -e "${RED}✗${NC} Failed to store API key: $ERROR_MSG"
            echo -e "${YELLOW}   You can configure this later via: POST /admin/keys/$PROVIDER_NAME${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠${NC}  Skipping AI provider configuration"
    echo -e "${YELLOW}   Configure later via:${NC}"
    echo -e "${YELLOW}   - POST /admin/keys/{provider}${NC}"
    echo -e "${YELLOW}   - POST /admin/extraction/config${NC}"
fi

# Embedding Provider Selection (ADR-039)
echo ""
echo -e "${BOLD}Embedding Provider Configuration${NC}"
echo -e "${YELLOW}Select embedding provider for concept similarity (ADR-039)${NC}"
echo -e "${YELLOW}This configures cold-start before first API startup${NC}"
echo ""
echo "Available providers:"
echo "  1) OpenAI (text-embedding-3-small) - 1536 dimensions, cloud-based"
echo "  2) Nomic (nomic-embed-text-v1.5) - 768 dimensions, local inference"
echo "  3) Skip (use OpenAI default)"
echo ""
read -p "Choice [1-3]: " -n 1 -r EMBEDDING_CHOICE
echo ""
echo ""

if [[ $EMBEDDING_CHOICE =~ ^[12]$ ]]; then
    if [ "$EMBEDDING_CHOICE" = "1" ]; then
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
    EMBEDDING_RESULT=$(PROJECT_ROOT="$PROJECT_ROOT" EMBEDDING_PROVIDER_CONFIG="$EMBEDDING_PROVIDER" EMBEDDING_MODEL_CONFIG="$EMBEDDING_MODEL" EMBEDDING_DIMS_CONFIG="$EMBEDDING_DIMS" $PYTHON << 'EOF' 2>&1
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
    config_id = save_embedding_config(config, created_by="initialize-auth.sh")
    if config_id:
        # Activate the config
        from src.api.lib.embedding_config import activate_embedding_config
        activate_embedding_config(config_id)
        print("SUCCESS")
    else:
        print("ERROR:Failed to save configuration")
        sys.exit(1)
except Exception as e:
    print(f"ERROR:{e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF
)
    set -e

    if echo "$EMBEDDING_RESULT" | grep -q "^SUCCESS"; then
        echo -e "${GREEN}✓${NC} ${EMBEDDING_DISPLAY} configured"
        echo -e "${YELLOW}   Cold-start will use ${EMBEDDING_DISPLAY} for builtin vocabulary${NC}"
        EMBEDDING_CONFIGURED=true
    else
        ERROR_MSG=$(echo "$EMBEDDING_RESULT" | grep "^ERROR:" | cut -d: -f2-)
        echo -e "${YELLOW}⚠${NC}  Failed to configure embedding provider: $ERROR_MSG"
        echo -e "${YELLOW}   Configure after startup via: kg admin embedding activate $EMBEDDING_CHOICE --force${NC}"
        EMBEDDING_CONFIGURED=false
    fi
else
    echo -e "${YELLOW}⚠${NC}  Using OpenAI default embedding provider"
    echo -e "${YELLOW}   Configure later via: kg admin embedding activate 2 --force${NC}"
    EMBEDDING_CONFIGURED=false
fi

# Success message
echo ""
echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║              Authentication Initialized!                   ║${NC}"
echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Admin Credentials:${NC}"
echo -e "  Username: ${GREEN}admin${NC}"
if [ "$DEV_MODE" = true ]; then
    echo -e "  Password: ${GREEN}Password1!${NC} ${YELLOW}(DEV MODE - change in production!)${NC}"
else
    echo -e "  Password: ${GREEN}(the password you just set)${NC}"
fi
echo ""
echo -e "${BOLD}Next Steps:${NC}"
echo -e "  1. ${BLUE}Start API server:${NC} ./scripts/services/start-api.sh"
echo -e "  2. ${BLUE}Login (kg CLI):${NC} kg login"
echo -e "     ${BLUE}Or test OAuth:${NC} curl -X POST http://localhost:8000/auth/oauth/clients/personal \\"
echo -e "                      -F username=admin -F password=YOUR_PASSWORD"
echo -e "  3. ${BLUE}View docs:${NC} http://localhost:8000/docs"
echo -e "  4. ${BLUE}Ingest data:${NC} kg ingest file -o 'My Ontology' document.txt"
echo ""
echo -e "${YELLOW}Security Notes:${NC}"
echo -e "  • ${BOLD}OAuth tokens${NC} are used for all authentication (ADR-054)"
echo -e "  • Client secrets are hashed with bcrypt (rounds=12)"
echo -e "  • OAuth access tokens expire after 1 hour"
echo -e "  • Encryption key stored in ${BOLD}.env${NC}"
echo -e "  • Never commit .env to git (it's in .gitignore)"
if [ "$DEV_MODE" = true ]; then
    echo -e "  • ${YELLOW}${BOLD}WARNING:${NC} ${YELLOW}Development mode password is NOT secure!${NC}"
    echo -e "    ${YELLOW}For production, run: ./scripts/setup/initialize-auth.sh (without --dev)${NC}"
fi
echo ""
echo -e "${YELLOW}Configuration:${NC}"
if [ "${EMBEDDING_CONFIGURED:-false}" = true ]; then
    echo -e "  • Embedding provider: ${GREEN}${EMBEDDING_DISPLAY}${NC}"
else
    echo -e "  • Embedding provider: ${GREEN}OpenAI (default)${NC}"
    echo -e "    Change via: ${BOLD}kg admin embedding activate 2 --force${NC} (for Nomic local)"
fi
echo ""
echo -e "${YELLOW}Management Commands:${NC}"
echo -e "  • Switch embeddings: ${BOLD}kg admin embedding activate <config_id> --force${NC}"
echo -e "  • Reload after switch: ${BOLD}kg admin embedding reload${NC}"
echo -e "  • AI extraction config: ${BOLD}kg admin extraction set --provider <provider> --model <model>${NC}"
echo -e "  • API key management: ${BOLD}kg admin keys list${NC}"
echo ""
