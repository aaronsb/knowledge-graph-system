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

while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            DEV_MODE=true
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
            echo "  --reset            Reset ALL secrets (DANGEROUS - will break encryption)"
            echo "  --reset-key KEY    Reset specific secret (e.g., OAUTH_SIGNING_KEY)"
            echo "  -y, --yes          Skip prompts (for automated scripts)"
            echo "  --help             Show this help"
            echo ""
            echo "Managed Secrets:"
            echo "  ENCRYPTION_KEY     Master key for encrypting API keys at rest"
            echo "  OAUTH_SIGNING_KEY  Secret for signing JWT tokens"
            echo "  POSTGRES_PASSWORD  PostgreSQL admin password"
            echo "  GARAGE_RPC_SECRET  Garage cluster coordination secret"
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
        for key in ENCRYPTION_KEY OAUTH_SIGNING_KEY POSTGRES_PASSWORD GARAGE_RPC_SECRET; do
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

# Helper: Generate and update secret
generate_secret() {
    local key=$1
    local generator=$2
    local description=$3

    # Check if we should skip this key
    if should_reset "$key"; then
        echo -e "${YELLOW}→ Resetting ${key}...${NC}"
    elif is_secret_valid "$key"; then
        echo -e "${GREEN}✓ ${key}${NC} - already configured"
        return 0
    else
        echo -e "${YELLOW}→ Generating ${key}...${NC}"
    fi

    # Generate the secret
    local value=$($generator)

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

    echo -e "${GREEN}✓ ${key}${NC} - generated and saved"
}

# Check for required tools
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ python3 not found (required for generating Fernet key)${NC}"
    exit 1
fi

# 1. ENCRYPTION_KEY (Fernet key for encrypting API keys at rest)
generate_secret "ENCRYPTION_KEY" \
    'python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"' \
    "Master encryption key for API keys (ADR-031)"

# 2. OAUTH_SIGNING_KEY (for signing JWT tokens)
if command -v openssl &> /dev/null; then
    generate_secret "OAUTH_SIGNING_KEY" \
        "openssl rand -hex 32" \
        "OAuth 2.0 access token signing key (ADR-054)"
else
    generate_secret "OAUTH_SIGNING_KEY" \
        'python3 -c "import secrets; print(secrets.token_hex(32))"' \
        "OAuth 2.0 access token signing key (ADR-054)"
fi

# 3. POSTGRES_PASSWORD (database admin password)
if [ "$DEV_MODE" = true ]; then
    # Dev mode: use simple password
    if ! is_secret_valid "POSTGRES_PASSWORD" || should_reset "POSTGRES_PASSWORD"; then
        echo -e "${YELLOW}→ Setting POSTGRES_PASSWORD (dev mode)...${NC}"
        if grep -q "^POSTGRES_PASSWORD=" "$PROJECT_ROOT/.env"; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=password|" "$PROJECT_ROOT/.env"
            else
                sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=password|" "$PROJECT_ROOT/.env"
            fi
        else
            echo "POSTGRES_PASSWORD=password" >> "$PROJECT_ROOT/.env"
        fi
        echo -e "${GREEN}✓ POSTGRES_PASSWORD${NC} - set to 'password' (dev mode)"
    else
        echo -e "${GREEN}✓ POSTGRES_PASSWORD${NC} - already configured"
    fi
else
    # Prod mode: generate strong password
    if command -v openssl &> /dev/null; then
        generate_secret "POSTGRES_PASSWORD" \
            "openssl rand -base64 32" \
            "PostgreSQL admin password"
    else
        generate_secret "POSTGRES_PASSWORD" \
            'python3 -c "import secrets; print(secrets.token_urlsafe(32))"' \
            "PostgreSQL admin password"
    fi
fi

# 4. GARAGE_RPC_SECRET (for Garage cluster coordination)
if command -v openssl &> /dev/null; then
    generate_secret "GARAGE_RPC_SECRET" \
        "openssl rand -hex 32" \
        "Garage cluster RPC secret"
else
    generate_secret "GARAGE_RPC_SECRET" \
        'python3 -c "import secrets; print(secrets.token_hex(32))"' \
        "Garage cluster RPC secret"
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
