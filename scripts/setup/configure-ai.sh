#!/bin/bash
set -e

# ============================================================================
# configure-ai.sh
# AI Provider Testing and Model Configuration Tool
# ============================================================================
#
# PURPOSE:
# Test database-configured AI providers and validate API keys work correctly.
# Allows quick model switching for different cost/performance tradeoffs.
#
# USAGE:
# This script complements initialize-platform.sh:
# - initialize-platform.sh → Initial database setup
# - configure-ai.sh → Testing, validation, and model tuning
#
# REQUIREMENTS:
# - Database must be running (./scripts/database/start-database.sh)
# - API server must be running (./scripts/start-api.sh)
# - Providers configured via initialize-platform.sh or kg CLI
# ============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${BLUE}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║     AI Provider Testing and Model Configuration Tool      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${RED}✗ Python virtual environment not found${NC}"
    echo -e "${YELLOW}  Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt${NC}"
    exit 1
fi

source venv/bin/activate

# Load .env file if exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs) 2>/dev/null || true
fi

# Check if API server is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${RED}✗ API server is not running${NC}"
    echo -e "${YELLOW}  Start it with: ./scripts/start-api.sh${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} API server is running"

# Function to get database configuration
get_db_config() {
    echo -e "\n${BLUE}→${NC} Querying database configuration..."

    # Get extraction provider from database
    EXTRACTION_JSON=$(curl -s http://localhost:8000/admin/extraction/config 2>/dev/null)
    if [ -z "$EXTRACTION_JSON" ] || [ "$EXTRACTION_JSON" = "null" ]; then
        EXTRACTION_PROVIDER="not configured"
        EXTRACTION_MODEL=""
    else
        EXTRACTION_PROVIDER=$(echo "$EXTRACTION_JSON" | python -c "import sys, json; data=json.load(sys.stdin); print(data.get('provider', 'unknown'))" 2>/dev/null || echo "unknown")
        EXTRACTION_MODEL=$(echo "$EXTRACTION_JSON" | python -c "import sys, json; data=json.load(sys.stdin); print(data.get('model_name', ''))" 2>/dev/null || echo "")
    fi

    # Get embedding provider from database
    EMBEDDING_JSON=$(curl -s http://localhost:8000/admin/embedding/configs 2>/dev/null)
    if [ -z "$EMBEDDING_JSON" ] || [ "$EMBEDDING_JSON" = "[]" ]; then
        EMBEDDING_PROVIDER="not configured"
        EMBEDDING_MODEL=""
    else
        # Get active config
        ACTIVE_EMBEDDING=$(echo "$EMBEDDING_JSON" | python -c "import sys, json; data=json.load(sys.stdin); active=[c for c in data if c.get('active')]; print(json.dumps(active[0]) if active else 'null')" 2>/dev/null)
        if [ "$ACTIVE_EMBEDDING" = "null" ]; then
            EMBEDDING_PROVIDER="not configured"
            EMBEDDING_MODEL=""
        else
            EMBEDDING_PROVIDER=$(echo "$ACTIVE_EMBEDDING" | python -c "import sys, json; data=json.load(sys.stdin); print(data.get('provider', 'unknown'))" 2>/dev/null || echo "unknown")
            EMBEDDING_MODEL=$(echo "$ACTIVE_EMBEDDING" | python -c "import sys, json; data=json.load(sys.stdin); print(data.get('model_name', ''))" 2>/dev/null || echo "")
        fi
    fi

    # Get API key status
    KEYS_JSON=$(curl -s http://localhost:8000/admin/keys 2>/dev/null)
    OPENAI_KEY_STATUS=$(echo "$KEYS_JSON" | python -c "import sys, json; data=json.load(sys.stdin); print('valid' if any(k.get('provider')=='openai' and k.get('validation_status')=='valid' for k in data) else 'invalid')" 2>/dev/null || echo "unknown")
    ANTHROPIC_KEY_STATUS=$(echo "$KEYS_JSON" | python -c "import sys, json; data=json.load(sys.stdin); print('valid' if any(k.get('provider')=='anthropic' and k.get('validation_status')=='valid' for k in data) else 'invalid')" 2>/dev/null || echo "unknown")
}

# Function to test provider
test_provider() {
    local provider=$1
    echo -e "\n${BLUE}Testing ${provider} provider via database config...${NC}"

    python -c "
import sys
sys.path.insert(0, '.')
from src.api.lib.llm_extractor import validate_provider_config

result = validate_provider_config('$provider')
if 'error' in result:
    print(f\"${RED}✗ Error: {result['error']}${NC}\")
    sys.exit(1)

print(f\"${CYAN}Provider: {result['provider']}${NC}\")
print(f\"${CYAN}Extraction Model: {result['extraction_model']}${NC}\")
print(f\"${CYAN}Embedding Model: {result['embedding_model']}${NC}\")
print(f\"${CYAN}API Key Valid: {'${GREEN}✓${NC}' if result['api_key_valid'] else '${RED}✗${NC}'}${NC}\")

if result['api_key_valid']:
    print(f\"\n${GREEN}✓ ${provider} provider is working!${NC}\")
    if 'available_models' in result:
        print(f\"\n${YELLOW}Available Models:${NC}\")
        for model_type, models in result['available_models'].items():
            print(f\"  {model_type}:\")
            for model in models[:5]:  # Show first 5
                print(f\"    - {model}\")
            if len(models) > 5:
                print(f\"    ... and {len(models) - 5} more\")
else:
    print(f\"${RED}✗ ${provider} provider API key is invalid${NC}\")
    sys.exit(1)
"
}

# Get current database configuration
get_db_config

# Show current configuration from database
echo -e "\n${BOLD}Database Configuration:${NC}"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo -e "${CYAN}Extraction Provider:${NC}"
if [ "$EXTRACTION_PROVIDER" = "not configured" ]; then
    echo -e "  ${YELLOW}○ Not configured${NC}"
else
    echo -e "  ${GREEN}✓ ${EXTRACTION_PROVIDER}${NC}"
    [ -n "$EXTRACTION_MODEL" ] && echo -e "  Model: ${EXTRACTION_MODEL}"
fi

echo -e "\n${CYAN}Embedding Provider:${NC}"
if [ "$EMBEDDING_PROVIDER" = "not configured" ]; then
    echo -e "  ${YELLOW}○ Not configured${NC}"
else
    echo -e "  ${GREEN}✓ ${EMBEDDING_PROVIDER}${NC}"
    [ -n "$EMBEDDING_MODEL" ] && echo -e "  Model: ${EMBEDDING_MODEL}"
fi

echo -e "\n${CYAN}API Keys:${NC}"
if [ "$OPENAI_KEY_STATUS" = "valid" ]; then
    echo -e "  OpenAI:     ${GREEN}✓ Valid${NC}"
else
    echo -e "  OpenAI:     ${RED}✗ Not configured${NC}"
fi

if [ "$ANTHROPIC_KEY_STATUS" = "valid" ]; then
    echo -e "  Anthropic:  ${GREEN}✓ Valid${NC}"
else
    echo -e "  Anthropic:  ${YELLOW}○ Not configured${NC}"
fi

echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Menu
echo -e "\n${BOLD}${YELLOW}Options:${NC}"
echo -e "  ${GREEN}1)${NC} Test current extraction provider"
echo -e "  ${GREEN}2)${NC} Test OpenAI provider"
echo -e "  ${GREEN}3)${NC} Test Anthropic provider"
echo -e "  ${GREEN}4)${NC} Configure extraction provider and model"
echo -e "  ${GREEN}5)${NC} Configure embedding provider"
echo -e "  ${GREEN}6)${NC} Manage API keys"
echo -e "  ${GREEN}7)${NC} Refresh configuration (re-query database)"
echo -e "  ${RED}8)${NC} Exit"
echo ""

read -p "Select option [1-8]: " option

case $option in
    1)
        # Test current extraction provider
        if [ "$EXTRACTION_PROVIDER" = "not configured" ]; then
            echo ""
            echo -e "${RED}✗ No extraction provider configured${NC}"
            echo -e "${YELLOW}  Run: ./scripts/setup/initialize-platform.sh (option 3)${NC}"
            echo ""
            echo -e "${BLUE}Press Enter to return to menu...${NC}"
            read
            exec "$0"  # Return to menu
        fi
        test_provider "$EXTRACTION_PROVIDER"
        ;;
    2)
        # Test OpenAI
        if [ "$OPENAI_KEY_STATUS" != "valid" ]; then
            echo ""
            echo -e "${YELLOW}⚠ OpenAI API key not configured or invalid${NC}"
            echo -e "  Configure API key with option 6 first"
            echo ""
            echo -e "${BLUE}Press Enter to return to menu...${NC}"
            read
            exec "$0"  # Return to menu
        fi
        test_provider "openai"
        ;;
    3)
        # Test Anthropic
        if [ "$ANTHROPIC_KEY_STATUS" != "valid" ]; then
            echo ""
            echo -e "${YELLOW}⚠ Anthropic API key not configured or invalid${NC}"
            echo -e "  Configure API key with option 6 first"
            echo ""
            echo -e "${BLUE}Press Enter to return to menu...${NC}"
            read
            exec "$0"  # Return to menu
        fi
        test_provider "anthropic"
        ;;
    4)
        # Configure extraction provider and model
        echo -e "\n${BOLD}${CYAN}Configure Extraction Provider${NC}"
        echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo -e "\n${YELLOW}Select provider:${NC}"
        echo "  1) OpenAI"
        echo "  2) Anthropic"
        echo "  3) Cancel (return to menu)"
        echo ""
        read -p "Choice [1-3]: " provider_choice

        case $provider_choice in
            1)
                PROVIDER="openai"
                echo -e "\n${YELLOW}OpenAI Extraction Models:${NC}"
                echo "  1) gpt-4o - Latest GPT-4o (~$6.25/1M tokens, balanced)"
                echo "  2) gpt-4o-mini - Faster, cheaper (~$0.38/1M tokens)"
                echo "  3) o1-preview - Reasoning model (~$30/1M tokens)"
                echo "  4) o1-mini - Smaller reasoning (~$5.50/1M tokens)"
                echo "  5) Cancel (return to menu)"
                echo ""
                read -p "Model [1-5]: " model_choice

                case $model_choice in
                    1) MODEL="gpt-4o" ;;
                    2) MODEL="gpt-4o-mini" ;;
                    3) MODEL="o1-preview" ;;
                    4) MODEL="o1-mini" ;;
                    5)
                        echo -e "${YELLOW}Cancelled${NC}"
                        echo -e "${BLUE}Press Enter to return to menu...${NC}"
                        read
                        exec "$0"
                        ;;
                    *)
                        echo ""
                        echo -e "${RED}Invalid choice${NC}"
                        echo -e "${BLUE}Press Enter to return to menu...${NC}"
                        read
                        exec "$0"
                        ;;
                esac
                ;;
            2)
                PROVIDER="anthropic"
                echo -e "\n${YELLOW}Anthropic Extraction Models:${NC}"
                echo "  1) claude-sonnet-4-20250514 - Latest Sonnet 4.5 (~$9/1M tokens, SOTA)"
                echo "  2) claude-3-5-sonnet-20241022 - Claude 3.5 Sonnet"
                echo "  3) claude-3-opus-20240229 - Claude 3 Opus"
                echo "  4) Cancel (return to menu)"
                echo ""
                read -p "Model [1-4]: " model_choice

                case $model_choice in
                    1) MODEL="claude-sonnet-4-20250514" ;;
                    2) MODEL="claude-3-5-sonnet-20241022" ;;
                    3) MODEL="claude-3-opus-20240229" ;;
                    4)
                        echo -e "${YELLOW}Cancelled${NC}"
                        echo -e "${BLUE}Press Enter to return to menu...${NC}"
                        read
                        exec "$0"
                        ;;
                    *)
                        echo ""
                        echo -e "${RED}Invalid choice${NC}"
                        echo -e "${BLUE}Press Enter to return to menu...${NC}"
                        read
                        exec "$0"
                        ;;
                esac
                ;;
            3)
                # Cancel - return to menu
                echo -e "${YELLOW}Cancelled${NC}"
                echo -e "${BLUE}Press Enter to return to menu...${NC}"
                read
                exec "$0"
                ;;
            *)
                echo ""
                echo -e "${RED}Invalid provider choice${NC}"
                echo -e "${BLUE}Press Enter to return to menu...${NC}"
                read
                exec "$0"
                ;;
        esac

        echo -e "\n${BLUE}→${NC} Updating extraction config: ${CYAN}${PROVIDER} / ${MODEL}${NC}"

        # Call API to update config
        RESPONSE=$(curl -s -X POST http://localhost:8000/admin/extraction/config \
            -H "Content-Type: application/json" \
            -d "{\"provider\": \"${PROVIDER}\", \"model_name\": \"${MODEL}\", \"updated_by\": \"configure-ai.sh\"}")

        SUCCESS=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null)

        if [ "$SUCCESS" = "True" ]; then
            echo -e "${GREEN}✓${NC} Extraction config updated successfully"
            echo -e "\n${BLUE}Testing new provider...${NC}"
            test_provider "$PROVIDER"
        else
            ERROR=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('detail', 'Unknown error'))" 2>/dev/null)
            echo ""
            echo -e "${RED}✗ Failed to update config: ${ERROR}${NC}"
            echo ""
            echo -e "${BLUE}Press Enter to return to menu...${NC}"
            read
            exec "$0"
        fi
        ;;
    5)
        # Configure embedding provider
        echo -e "\n${BOLD}${CYAN}Configure Embedding Provider${NC}"
        echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo -e "\n${YELLOW}Available providers:${NC}"
        echo "  1) OpenAI (text-embedding-3-small) - 1536 dims, cloud-based"
        echo "  2) Nomic (nomic-embed-text-v1.5) - 768 dims, local inference"
        echo "  3) Cancel (return to menu)"
        echo ""
        read -p "Choice [1-3]: " emb_choice

        case $emb_choice in
            1)
                echo -e "\n${BLUE}→${NC} Configuring OpenAI embeddings..."
                echo -e "${YELLOW}Use kg CLI for embedding configuration:${NC}"
                echo -e "  ${CYAN}kg admin embedding create --provider openai --model text-embedding-3-small${NC}"
                echo -e "  ${CYAN}kg admin embedding activate <config-id>${NC}"
                ;;
            2)
                echo -e "\n${BLUE}→${NC} Configuring Nomic embeddings..."
                echo -e "${YELLOW}Use kg CLI for embedding configuration:${NC}"
                echo -e "  ${CYAN}kg admin embedding create --provider nomic --model nomic-embed-text-v1.5${NC}"
                echo -e "  ${CYAN}kg admin embedding activate <config-id>${NC}"
                ;;
            3)
                # Cancel - return to menu
                echo -e "${YELLOW}Cancelled${NC}"
                echo -e "${BLUE}Press Enter to return to menu...${NC}"
                read
                exec "$0"
                ;;
            *)
                echo ""
                echo -e "${RED}Invalid choice${NC}"
                echo -e "${BLUE}Press Enter to return to menu...${NC}"
                read
                exec "$0"
                ;;
        esac
        ;;
    6)
        # Manage API keys
        echo -e "\n${BOLD}${CYAN}Manage API Keys${NC}"
        echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo -e "\n${YELLOW}Options:${NC}"
        echo "  1) View API key status"
        echo "  2) Set/Update OpenAI key"
        echo "  3) Set/Update Anthropic key"
        echo "  4) Delete OpenAI key"
        echo "  5) Delete Anthropic key"
        echo "  6) Cancel (return to menu)"
        echo ""
        read -p "Choice [1-6]: " key_choice

        case $key_choice in
            1)
                echo -e "\n${BLUE}→${NC} Current API key status:"
                curl -s http://localhost:8000/admin/keys | python -m json.tool
                ;;
            2)
                echo -e "\n${BLUE}→${NC} Use kg CLI to set OpenAI key:"
                echo -e "  ${CYAN}kg admin keys set openai${NC}"
                echo -e "  (Validates key before storing)"
                ;;
            3)
                echo -e "\n${BLUE}→${NC} Use kg CLI to set Anthropic key:"
                echo -e "  ${CYAN}kg admin keys set anthropic${NC}"
                echo -e "  (Validates key before storing)"
                ;;
            4)
                echo -e "\n${BLUE}→${NC} Use kg CLI to delete OpenAI key:"
                echo -e "  ${CYAN}kg admin keys delete openai${NC}"
                ;;
            5)
                echo -e "\n${BLUE}→${NC} Use kg CLI to delete Anthropic key:"
                echo -e "  ${CYAN}kg admin keys delete anthropic${NC}"
                ;;
            6)
                # Cancel - return to menu
                echo -e "${YELLOW}Cancelled${NC}"
                echo -e "${BLUE}Press Enter to return to menu...${NC}"
                read
                exec "$0"
                ;;
            *)
                echo ""
                echo -e "${RED}Invalid choice${NC}"
                echo -e "${BLUE}Press Enter to return to menu...${NC}"
                read
                exec "$0"
                ;;
        esac
        ;;
    7)
        # Refresh configuration
        echo -e "\n${BLUE}→${NC} Refreshing configuration..."
        exec "$0"  # Re-execute script
        ;;
    8)
        # Exit
        echo ""
        echo -e "${GREEN}✓${NC} Configuration tool closed"
        exit 0
        ;;
    *)
        echo ""
        echo -e "${RED}Invalid option${NC}"
        echo -e "${BLUE}Press Enter to return to menu...${NC}"
        read
        exec "$0"
        ;;
esac

echo ""
echo -e "${BLUE}Press Enter to return to menu...${NC}"
read
exec "$0"  # Re-run script to show menu again
