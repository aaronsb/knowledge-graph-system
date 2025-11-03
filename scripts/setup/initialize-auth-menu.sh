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
    local provider=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c \
        "SELECT provider FROM kg_config.extraction_config WHERE is_active = true LIMIT 1" 2>/dev/null | xargs)
    if [ -n "$provider" ]; then
        echo -e "${GREEN}✓${NC} ${provider}"
    else
        echo -e "○ unconfigured"
    fi
}

get_embedding_provider_status() {
    local provider=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c \
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

    # Implementation here - call to original script section
    echo -e "${YELLOW}⚠${NC}  This feature is being implemented..."
    echo ""
    read -p "Press Enter to continue..."
}

configure_encryption_key() {
    echo ""
    echo -e "${BOLD}Configure Encryption Key${NC}"
    echo -e "${YELLOW}Used for encrypting API keys at rest (ADR-031)${NC}"
    echo ""

    # Implementation here - call to original script section
    echo -e "${YELLOW}⚠${NC}  This feature is being implemented..."
    echo ""
    read -p "Press Enter to continue..."
}

configure_ai_provider() {
    echo ""
    echo -e "${BOLD}Configure AI Extraction Provider${NC}"
    echo -e "${YELLOW}For concept extraction (ADR-041)${NC}"
    echo ""

    # Implementation here - call to original script section
    echo -e "${YELLOW}⚠${NC}  This feature is being implemented..."
    echo ""
    read -p "Press Enter to continue..."
}

configure_embedding_provider() {
    echo ""
    echo -e "${BOLD}Configure Embedding Provider${NC}"
    echo -e "${YELLOW}For concept similarity (ADR-039)${NC}"
    echo ""

    # Implementation here - call to original script section
    echo -e "${YELLOW}⚠${NC}  This feature is being implemented..."
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
