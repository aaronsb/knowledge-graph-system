#!/bin/bash
set -e

# ============================================================================
# init-secrets.sh
# Knowledge Graph System - Infrastructure Secret Initialization
# ============================================================================
#
# PURPOSE:
# Generate/verify infrastructure secrets BEFORE docker-compose starts.
# This script ONLY handles infrastructure secrets (encryption, auth, database).
# Application configuration (AI providers, API keys) is handled by the operator.
#
# WHAT IT MANAGES:
# - ENCRYPTION_KEY: Master key for encrypting API keys at rest (Fernet)
# - OAUTH_SIGNING_KEY: Secret for signing JWT access tokens
# - POSTGRES_PASSWORD: PostgreSQL admin password
# - GARAGE_RPC_SECRET: Garage cluster coordination secret
# - INTERNAL_KEY_SERVICE_SECRET: Internal service authorization token (ADR-031)
#
# WHAT IT DOES NOT TOUCH:
# - Application config (AI providers, embedding settings)
# - API keys (OpenAI, Anthropic - those go in database via operator)
# - User passwords (admin user - configured via operator)
#
# USAGE:
# ./scripts/setup/init-secrets.sh              # Check/generate secrets
# ./scripts/setup/init-secrets.sh --dev        # Dev mode (weak passwords OK)
# ./scripts/setup/init-secrets.sh --reset      # Reset all secrets (DANGEROUS)
# ./scripts/setup/init-secrets.sh --reset-key ENCRYPTION_KEY  # Reset specific key
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

# Parse arguments
DEV_MODE=false
RESET_ALL=false
RESET_KEYS=()
AUTO_YES=false
UPGRADE_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            DEV_MODE=true
            shift
            ;;
        --upgrade)
            UPGRADE_MODE=true
            shift
            ;;
        --reset)
            RESET_ALL=true
            shift
            ;;
        --reset-key)
            RESET_KEYS+=("$2")
            shift 2
            ;;
        -y|--yes)
            AUTO_YES=true
            shift
            ;;
        --help|-h)
            echo "Infrastructure Secret Initialization"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dev              Development mode (weak passwords acceptable)"
            echo "  --upgrade          Upgrade dev to prod (regenerates weak passwords)"
            echo "  --reset            Reset ALL secrets (DANGEROUS - will break encryption)"
            echo "  --reset-key KEY    Reset specific secret (e.g., OAUTH_SIGNING_KEY)"
            echo "  -y, --yes          Skip prompts (for automated scripts)"
            echo "  --help             Show this help"
            echo ""
            echo "Managed Secrets:"
            echo "  ENCRYPTION_KEY              Master key for encrypting API keys at rest"
            echo "  OAUTH_SIGNING_KEY           Secret for signing JWT tokens"
            echo "  POSTGRES_PASSWORD           PostgreSQL admin password"
            echo "  GARAGE_RPC_SECRET           Garage cluster coordination secret"
            echo "  INTERNAL_KEY_SERVICE_SECRET Internal service authorization token"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Banner
echo -e "${BLUE}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║       Infrastructure Secret Initialization                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

if [ "$DEV_MODE" = true ]; then
    echo -e "${YELLOW}Mode: Development (weak passwords allowed)${NC}"
elif [ "$RESET_ALL" = true ]; then
    echo -e "${RED}Mode: RESET ALL SECRETS${NC}"
    echo -e "${RED}⚠️  This will break existing encrypted API keys!${NC}"
    echo ""
    read -p "Are you sure? Type 'yes' to confirm: " -r
    if [ "$REPLY" != "yes" ]; then
        echo -e "${YELLOW}Cancelled${NC}"
        exit 0
    fi
    echo ""
else
    echo -e "${GREEN}Mode: Production (strong secrets required)${NC}"
fi
echo ""

# Helper: Check if key exists and is not a placeholder
is_secret_valid() {
    local key=$1
    if ! grep -q "^${key}=" "$PROJECT_ROOT/.env" 2>/dev/null; then
        return 1  # Key doesn't exist
    fi
    local value=$(grep "^${key}=" "$PROJECT_ROOT/.env" | cut -d'=' -f2-)
    if [[ "$value" == *"CHANGE_THIS"* ]] || [[ "$value" == *"changeme"* ]] || [ -z "$value" ]; then
        return 1  # Placeholder value
    fi
    return 0  # Valid secret
}

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    if [ ! -f "$PROJECT_ROOT/.env.example" ]; then
        echo -e "${RED}✗ .env.example not found${NC}"
        exit 1
    fi
    echo -e "${YELLOW}→ Creating .env from .env.example...${NC}"
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    echo -e "${GREEN}✓ .env created${NC}"
    echo ""
else
    # .env exists - check if secrets are already configured
    if [ "$RESET_ALL" = false ] && [ ${#RESET_KEYS[@]} -eq 0 ]; then
        # Check if any secrets are already valid
        SECRETS_EXIST=false
        for key in ENCRYPTION_KEY OAUTH_SIGNING_KEY POSTGRES_PASSWORD GARAGE_RPC_SECRET INTERNAL_KEY_SERVICE_SECRET; do
            if is_secret_valid "$key"; then
                SECRETS_EXIST=true
                break
            fi
        done

        if [ "$SECRETS_EXIST" = true ]; then
            echo -e "${YELLOW}⚠️  .env file already contains configured secrets${NC}"
            echo ""
            if [ "$AUTO_YES" = false ]; then
                echo "Options:"
                echo "  1) Keep existing secrets (recommended)"
                echo "  2) Regenerate ALL secrets (will break encrypted data!)"
                echo "  3) Exit"
                echo ""
                read -p "Choice [1/2/3]: " -n 1 -r
                echo ""
                echo ""

                case $REPLY in
                    1)
                        echo -e "${GREEN}→ Keeping existing secrets${NC}"
                        echo ""
                        ;;
                    2)
                        echo -e "${RED}→ Regenerating ALL secrets${NC}"
                        echo -e "${RED}⚠️  This will break existing encrypted API keys!${NC}"
                        echo ""
                        read -p "Type 'yes' to confirm: " -r
                        if [ "$REPLY" = "yes" ]; then
                            RESET_ALL=true
                        else
                            echo -e "${YELLOW}Cancelled${NC}"
                            exit 0
                        fi
                        ;;
                    3)
                        echo -e "${YELLOW}Exiting${NC}"
                        exit 0
                        ;;
                    *)
                        echo -e "${YELLOW}Invalid choice, keeping existing secrets${NC}"
                        echo ""
                        ;;
                esac
            else
                echo -e "${GREEN}→ Keeping existing secrets (--yes flag)${NC}"
                echo ""
            fi
        fi
    fi
fi

# Helper: Check if key should be reset
should_reset() {
    local key=$1
    if [ "$RESET_ALL" = true ]; then
        return 0
    fi
    for reset_key in "${RESET_KEYS[@]}"; do
        if [ "$key" = "$reset_key" ]; then
            return 0
        fi
    done
    return 1
}

# Helper: Update secret in .env file
update_env_file() {
    local key=$1
    local value=$2
    local description=$3

    # Update .env file
    if grep -q "^${key}=" "$PROJECT_ROOT/.env"; then
        # Key exists, replace it
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^${key}=.*|${key}=${value}|" "$PROJECT_ROOT/.env"
        else
            sed -i "s|^${key}=.*|${key}=${value}|" "$PROJECT_ROOT/.env"
        fi
    else
        # Key doesn't exist, append it
        echo "" >> "$PROJECT_ROOT/.env"
        echo "# ${description}" >> "$PROJECT_ROOT/.env"
        echo "${key}=${value}" >> "$PROJECT_ROOT/.env"
    fi
}

# Check for required tools
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ python3 not found (required for secret generation)${NC}"
    exit 1
fi

# 1. ENCRYPTION_KEY (Fernet key for encrypting API keys at rest)
# Fernet keys are 32 random bytes, URL-safe base64 encoded
# Using stdlib only (no cryptography package needed)
if should_reset "ENCRYPTION_KEY" || ! is_secret_valid "ENCRYPTION_KEY"; then
    echo -e "${YELLOW}→ Generating ENCRYPTION_KEY...${NC}"
    VALUE=$(python3 -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())")
    update_env_file "ENCRYPTION_KEY" "$VALUE" "Master encryption key for API keys (ADR-031)"
    echo -e "${GREEN}✓ ENCRYPTION_KEY${NC} - generated and saved"
else
    echo -e "${GREEN}✓ ENCRYPTION_KEY${NC} - already configured"
fi

# 2. OAUTH_SIGNING_KEY (for signing JWT tokens)
if should_reset "OAUTH_SIGNING_KEY" || ! is_secret_valid "OAUTH_SIGNING_KEY"; then
    echo -e "${YELLOW}→ Generating OAUTH_SIGNING_KEY...${NC}"
    VALUE=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    update_env_file "OAUTH_SIGNING_KEY" "$VALUE" "OAuth 2.0 access token signing key (ADR-054)"
    echo -e "${GREEN}✓ OAUTH_SIGNING_KEY${NC} - generated and saved"
else
    echo -e "${GREEN}✓ OAUTH_SIGNING_KEY${NC} - already configured"
fi

# 3. POSTGRES_PASSWORD (database admin password)
if [ "$DEV_MODE" = true ]; then
    # Dev mode: use simple password
    if should_reset "POSTGRES_PASSWORD" || ! is_secret_valid "POSTGRES_PASSWORD"; then
        echo -e "${YELLOW}→ Setting POSTGRES_PASSWORD (dev mode - using simple password)...${NC}"
        update_env_file "POSTGRES_PASSWORD" "password" "PostgreSQL admin password"
        echo -e "${GREEN}✓ POSTGRES_PASSWORD${NC} - set to \"password\" for easy local development"
    else
        echo -e "${GREEN}✓ POSTGRES_PASSWORD${NC} - already configured"
    fi
else
    # Prod mode: generate strong password
    # Check if we're upgrading from dev (password == "password")
    CURRENT_PASSWORD=$(grep '^POSTGRES_PASSWORD=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2)
    NEEDS_UPGRADE=false
    if [ "$UPGRADE_MODE" = true ] && [ "$CURRENT_PASSWORD" = "password" ]; then
        NEEDS_UPGRADE=true
        echo -e "${YELLOW}→ Upgrading POSTGRES_PASSWORD from dev to prod...${NC}"
    fi

    if should_reset "POSTGRES_PASSWORD" || ! is_secret_valid "POSTGRES_PASSWORD" || [ "$NEEDS_UPGRADE" = true ]; then
        if [ "$NEEDS_UPGRADE" = true ]; then
            echo -e "${YELLOW}   Detected weak dev password, generating strong replacement...${NC}"
        else
            echo -e "${YELLOW}→ Generating POSTGRES_PASSWORD (production mode - strong cryptographic token)...${NC}"
        fi
        VALUE=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        update_env_file "POSTGRES_PASSWORD" "$VALUE" "PostgreSQL admin password"
        echo -e "${GREEN}✓ POSTGRES_PASSWORD${NC} - generated and saved"
    else
        echo -e "${GREEN}✓ POSTGRES_PASSWORD${NC} - already configured"
    fi
fi

# 4. GARAGE_RPC_SECRET (for Garage cluster coordination)
if should_reset "GARAGE_RPC_SECRET" || ! is_secret_valid "GARAGE_RPC_SECRET"; then
    echo -e "${YELLOW}→ Generating GARAGE_RPC_SECRET...${NC}"
    VALUE=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    update_env_file "GARAGE_RPC_SECRET" "$VALUE" "Garage cluster RPC secret"
    echo -e "${GREEN}✓ GARAGE_RPC_SECRET${NC} - generated and saved"
else
    echo -e "${GREEN}✓ GARAGE_RPC_SECRET${NC} - already configured"
fi

# 5. INTERNAL_KEY_SERVICE_SECRET (for internal service authorization)
# This token authorizes services to access encrypted API keys (ADR-031)
if should_reset "INTERNAL_KEY_SERVICE_SECRET" || ! is_secret_valid "INTERNAL_KEY_SERVICE_SECRET"; then
    echo -e "${YELLOW}→ Generating INTERNAL_KEY_SERVICE_SECRET...${NC}"
    VALUE=$(python3 -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())")
    update_env_file "INTERNAL_KEY_SERVICE_SECRET" "$VALUE" "Internal service authorization token (ADR-031)"
    echo -e "${GREEN}✓ INTERNAL_KEY_SERVICE_SECRET${NC} - generated and saved"
else
    echo -e "${GREEN}✓ INTERNAL_KEY_SERVICE_SECRET${NC} - already configured"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Infrastructure secrets ready${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BOLD}Next Steps:${NC}"
echo "  1. Start infrastructure: ./operator/lib/start-infra.sh"
echo "  2. Start operator: cd docker && docker-compose --env-file ../.env up -d operator"
echo "  3. Configure platform: docker exec kg-operator python /workspace/operator/configure.py admin"
echo "  4. Start application: ./operator/lib/start-app.sh"
echo ""
echo -e "${YELLOW}Note: .env file contains secrets - never commit to git${NC}"
echo ""
