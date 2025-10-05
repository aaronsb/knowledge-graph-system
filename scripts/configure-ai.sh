#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo "🤖 AI Provider Configuration"
echo "============================="

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${RED}✗ Python virtual environment not found${NC}"
    echo -e "${YELLOW}  Run: ./scripts/setup.sh${NC}"
    exit 1
fi

source venv/bin/activate

# Load .env file
export $(grep -v '^#' .env | xargs)

# Function to test provider
test_provider() {
    local provider=$1
    echo -e "\n${BLUE}Testing ${provider} provider...${NC}"

    python -c "
import sys
sys.path.insert(0, '.')
from ingest.llm_extractor import validate_provider_config

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

# Show current configuration
echo -e "\n${BLUE}Current Configuration:${NC}"
if [ -f .env ]; then
    AI_PROVIDER=$(grep "^AI_PROVIDER=" .env | cut -d= -f2 || echo "openai")
    echo -e "  Provider: ${GREEN}${AI_PROVIDER:-openai}${NC}"

    # Check which keys are set
    if grep -q "^OPENAI_API_KEY=" .env && ! grep -q "^OPENAI_API_KEY=$" .env; then
        echo -e "  OpenAI Key: ${GREEN}✓ Set${NC}"
    else
        echo -e "  OpenAI Key: ${RED}✗ Not set${NC}"
    fi

    if grep -q "^ANTHROPIC_API_KEY=" .env && ! grep -q "^ANTHROPIC_API_KEY=$" .env; then
        echo -e "  Anthropic Key: ${GREEN}✓ Set${NC}"
    else
        echo -e "  Anthropic Key: ${YELLOW}⚠ Not set${NC}"
    fi
else
    echo -e "${RED}✗ .env file not found${NC}"
    exit 1
fi

# Menu
echo -e "\n${YELLOW}Options:${NC}"
echo "1. Test current provider"
echo "2. Test OpenAI"
echo "3. Test Anthropic"
echo "4. Switch to OpenAI"
echo "5. Switch to Anthropic"
echo "6. Configure OpenAI models"
echo "7. Configure Anthropic models"
echo "8. Exit"

read -p "Select option [1-8]: " option

case $option in
    1)
        AI_PROVIDER=$(grep "^AI_PROVIDER=" .env | cut -d= -f2 || echo "openai")
        test_provider "${AI_PROVIDER:-openai}"
        ;;
    2)
        test_provider "openai"
        ;;
    3)
        test_provider "anthropic"
        ;;
    4)
        sed -i 's/^AI_PROVIDER=.*/AI_PROVIDER=openai/' .env 2>/dev/null || echo "AI_PROVIDER=openai" >> .env
        echo -e "${GREEN}✓ Switched to OpenAI${NC}"
        test_provider "openai"
        ;;
    5)
        if ! grep -q "^ANTHROPIC_API_KEY=" .env || grep -q "^ANTHROPIC_API_KEY=$" .env; then
            echo -e "${RED}✗ ANTHROPIC_API_KEY not set in .env${NC}"
            echo -e "${YELLOW}Please add your Anthropic API key to .env first${NC}"
            exit 1
        fi
        sed -i 's/^AI_PROVIDER=.*/AI_PROVIDER=anthropic/' .env 2>/dev/null || echo "AI_PROVIDER=anthropic" >> .env
        echo -e "${GREEN}✓ Switched to Anthropic${NC}"
        test_provider "anthropic"
        ;;
    6)
        echo -e "\n${YELLOW}OpenAI Model Configuration:${NC}"
        echo "Available extraction models:"
        echo "  1. gpt-4o (latest, recommended)"
        echo "  2. gpt-4o-mini (faster, cheaper)"
        echo "  3. o1-preview (reasoning model)"
        echo "  4. o1-mini (smaller reasoning)"
        read -p "Select model [1-4]: " model_choice

        case $model_choice in
            1) MODEL="gpt-4o" ;;
            2) MODEL="gpt-4o-mini" ;;
            3) MODEL="o1-preview" ;;
            4) MODEL="o1-mini" ;;
            *) echo -e "${RED}Invalid choice${NC}"; exit 1 ;;
        esac

        sed -i '/^OPENAI_EXTRACTION_MODEL=/d' .env
        echo "OPENAI_EXTRACTION_MODEL=$MODEL" >> .env
        echo -e "${GREEN}✓ Set OpenAI extraction model to: $MODEL${NC}"
        ;;
    7)
        echo -e "\n${YELLOW}Anthropic Model Configuration:${NC}"
        echo "Available extraction models:"
        echo "  1. claude-sonnet-4-20250514 (latest Sonnet 4.5, SOTA)"
        echo "  2. claude-3-5-sonnet-20241022 (Claude 3.5 Sonnet)"
        echo "  3. claude-3-opus-20240229 (Claude 3 Opus)"
        read -p "Select model [1-3]: " model_choice

        case $model_choice in
            1) MODEL="claude-sonnet-4-20250514" ;;
            2) MODEL="claude-3-5-sonnet-20241022" ;;
            3) MODEL="claude-3-opus-20240229" ;;
            *) echo -e "${RED}Invalid choice${NC}"; exit 1 ;;
        esac

        sed -i '/^ANTHROPIC_EXTRACTION_MODEL=/d' .env
        echo "ANTHROPIC_EXTRACTION_MODEL=$MODEL" >> .env
        echo -e "${GREEN}✓ Set Anthropic extraction model to: $MODEL${NC}"
        ;;
    8)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

echo ""
