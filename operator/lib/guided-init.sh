#!/bin/bash
set -e

# Get project root (this script is in operator/lib/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Track if services were started for cleanup
INFRA_STARTED=false
APP_STARTED=false

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Setup interrupted or failed${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    if [ "$INFRA_STARTED" = true ] || [ "$APP_STARTED" = true ]; then
        echo -e "${BOLD}Would you like to clean up and remove all created services and data?${NC}"
        echo ""
        echo -e "  ${RED}⚠ WARNING:${NC} This will delete:"
        echo "    • All running containers"
        echo "    • All stored data (database, concepts, documents)"
        echo "    • Docker volumes"
        echo "    • The .env secrets file"
        echo ""
        read -p "Run cleanup? (yes/no): " -r
        echo ""

        if [[ $REPLY =~ ^[Yy]es$ ]]; then
            echo -e "${BLUE}→${NC} Running teardown..."
            ./operator/lib/teardown.sh
            echo ""
            echo -e "${GREEN}✓${NC} Cleanup complete"
        else
            echo -e "${YELLOW}→${NC} Leaving services running. To clean up later, run:"
            echo "    ./operator/lib/teardown.sh"
        fi
    fi

    exit 1
}

# Set trap for cleanup on error or interrupt
trap cleanup ERR INT TERM

# Banner
clear
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}  ${BOLD}Knowledge Graph System - Platform Setup${NC}               ${BLUE}    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}This script will get you started in minutes.${NC}"
echo ""
echo -e "${YELLOW}What this does:${NC}"
echo "  • Generates infrastructure secrets (.env file)"
echo "  • Starts Docker services (PostgreSQL, Garage S3, API, Web)"
echo "  • Configures system with development defaults"
echo "  • Installs kg CLI tool globally"
echo ""
echo -e "${YELLOW}Development defaults (for quick evaluation):${NC}"
echo -e "  • Admin password: ${RED}Password1!${NC}"
echo -e "  • Database password: ${RED}password${NC}"
echo "  • AI extraction: Choose from OpenAI, Anthropic, or OpenRouter"
echo "  • Embeddings: Local (nomic-ai/nomic-embed-text-v1.5)"
echo ""
echo -e "${YELLOW}Prerequisites:${NC}"
echo "  • Docker with permissions (docker ps should work)"
echo "  • API key for your AI provider (will prompt during setup)"
echo "  • Node.js + npm (for kg CLI installation)"
echo ""
echo -e "${YELLOW}Supported Platforms:${NC}"
echo "  • Mac (Intel/Apple Silicon) - Auto-detects and configures"
echo "  • Linux (with/without NVIDIA GPU) - Auto-detects GPU"
echo "  • Windows WSL2 - Works like Linux"
echo ""
echo -e "${YELLOW}Time required:${NC} ~5 minutes"
echo ""
echo -e "${RED}⚠ WARNING:${NC} This will:"
echo "  • Start multiple Docker containers on your machine"
echo "  • Use disk space for databases and volumes"
echo "  • Install the 'kg' CLI command globally"
echo ""
echo -e "${BOLD}Ready to proceed?${NC}"
echo ""
read -p "Continue with setup? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

# Password configuration choice
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Password Configuration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Choose password security level:"
echo ""
echo -e "  ${GREEN}[1] Randomized passwords${NC} (recommended for security)"
echo "      • Strong random passwords generated automatically"
echo "      • You'll need to save them (displayed after generation)"
echo "      • Database password is harder to change later"
echo ""
echo -e "  ${YELLOW}[2] Simple defaults${NC} (quick evaluation)"
echo "      • Admin: Password1!"
echo "      • Database: password"
echo "      • Easy to remember, but insecure"
echo ""
read -p "Choose option (1 or 2): " -r
echo ""

USE_RANDOM_PASSWORDS=false
if [[ $REPLY == "1" ]]; then
    USE_RANDOM_PASSWORDS=true
    # Generate random admin password (16 chars, alphanumeric)
    ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d '/+=' | cut -c1-16)
    echo -e "${GREEN}→${NC} Will generate randomized passwords"
    echo ""
else
    ADMIN_PASSWORD="Password1!"
    echo -e "${YELLOW}→${NC} Using simple default passwords"
    echo ""
fi

# Development mode choice
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Container Mode${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Choose how to run the application:"
echo ""
echo -e "  ${GREEN}[1] Regular mode${NC} (recommended for usage)"
echo -e "      • Production-ready static builds"
echo -e "      • Fast and stable performance"
echo -e "      • ${BOLD}Choose this if you just want to use the system${NC}"
echo ""
echo -e "  ${YELLOW}[2] Hot reload mode${NC} (for development)"
echo -e "      • Live code editing with automatic reload"
echo -e "      • API and web restart after every file save"
echo -e "      • ${BOLD}Choose this only if you plan to edit the source code${NC}"
echo ""
read -p "Choose option (1 or 2): " -r
echo ""

USE_HOT_RELOAD=false
START_APP_FLAGS=""
if [[ $REPLY == "2" ]]; then
    USE_HOT_RELOAD=true
    START_APP_FLAGS="--dev"
    echo -e "${YELLOW}→${NC} Will use development mode with hot reload"
    echo ""
else
    echo -e "${GREEN}→${NC} Will use regular mode"
    echo ""
fi

# Platform detection choice
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Platform Configuration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Choose your platform (this configures GPU acceleration for LOCAL embeddings):"
echo ""
echo -e "  ${GREEN}[1] Mac (macOS)${NC}"
echo "      • Intel Mac: CPU-based local embeddings"
echo "      • Apple Silicon (M1/M2/M3/M4): MPS GPU acceleration"
echo ""
echo -e "  ${GREEN}[2] Linux / Windows WSL2 with NVIDIA GPU${NC}"
echo "      • Auto-detects NVIDIA GPU (CUDA acceleration if available)"
echo "      • Falls back to CPU if no NVIDIA GPU found"
echo ""
echo -e "  ${GREEN}[3] Linux with AMD GPU (ROCm wheels)${NC}"
echo "      • Downloads PyTorch ROCm 6.x wheels"
echo "      • For systems with ROCm 6.x installed"
echo ""
echo -e "  ${GREEN}[4] Linux with AMD GPU (host ROCm)${NC}"
echo "      • Uses host's ROCm and PyTorch installation"
echo "      • For Arch/distros with newer ROCm (7.x+)"
echo "      • Requires: python-pytorch with ROCm support"
echo ""
echo -e "  ${GREEN}[5] CPU only${NC}"
echo "      • No GPU acceleration"
echo "      • Works on any platform"
echo ""
echo -e "${YELLOW}ℹ️  What this affects:${NC}"
echo "  • WHERE local embeddings are computed (MPS/CUDA/ROCm/CPU)"
echo "  • Does NOT affect WHICH models are used (local vs API)"
echo "  • AI extraction uses remote API (OpenAI/Anthropic/OpenRouter)"
echo ""
read -p "Choose option (1-5): " -r
echo ""

# Set GPU_MODE based on selection
case "$REPLY" in
    1)
        GPU_MODE="mac"
        echo -e "${YELLOW}→${NC} Will configure for Mac platform"
        ;;
    2)
        GPU_MODE="auto"  # Will be detected as nvidia or cpu
        echo -e "${GREEN}→${NC} Will auto-detect NVIDIA GPU"
        ;;
    3)
        GPU_MODE="amd"
        echo -e "${GREEN}→${NC} Will configure for AMD GPU (ROCm wheels)"
        ;;
    4)
        GPU_MODE="amd-host"
        echo -e "${GREEN}→${NC} Will configure for AMD GPU (host ROCm)"
        ;;
    5)
        GPU_MODE="cpu"
        echo -e "${GREEN}→${NC} Will use CPU only (no GPU acceleration)"
        ;;
    *)
        GPU_MODE="auto"
        echo -e "${GREEN}→${NC} Invalid option, defaulting to auto-detect"
        ;;
esac
echo ""

# Check Docker is running
echo -e "${BLUE}→${NC} Checking Docker..."
if ! docker ps >/dev/null 2>&1; then
    echo -e "${RED}✗${NC} Docker is not running or you don't have permission."
    echo "  Please start Docker and ensure you can run: docker ps"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker is running"
echo ""

# Step 1: Generate secrets
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 1/9: Generating infrastructure secrets${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ "$USE_RANDOM_PASSWORDS" = true ]; then
    # Production mode - generates random database password
    # Check if .env exists (upgrade vs fresh install)
    if [ -f ".env" ]; then
        # Existing .env: Use --upgrade to transition dev→prod (upgrades weak "password" to strong random)
        ./operator/lib/init-secrets.sh --upgrade -y
    else
        # Fresh install: Use production mode (no --dev flag, generates strong passwords)
        ./operator/lib/init-secrets.sh -y
    fi
    # Read the generated database password from .env
    POSTGRES_PASSWORD=$(grep '^POSTGRES_PASSWORD=' .env | cut -d'=' -f2)

    # Display passwords for user to save
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  ${BOLD}🔐 SAVE THESE PASSWORDS${NC}                               ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BOLD}Admin Password:${NC}     ${GREEN}$ADMIN_PASSWORD${NC}"
    echo -e "${BOLD}Database Password:${NC}  ${GREEN}$POSTGRES_PASSWORD${NC}"
    echo ""
    echo -e "${YELLOW}⚠  Write these down now - you'll need them to access the system!${NC}"
    echo ""
    read -p "Press Enter after saving these passwords..." -r
    echo ""
else
    # Development mode - uses simple default passwords
    ./operator/lib/init-secrets.sh --dev -y
    POSTGRES_PASSWORD="password"
fi

echo ""

# Step 2: Start infrastructure
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 2/9: Starting infrastructure (Postgres + Garage + Operator)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
./operator/lib/start-infra.sh
INFRA_STARTED=true
echo ""

# Step 3: Configure admin
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 3/9: Creating admin user${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ "$USE_RANDOM_PASSWORDS" = true ]; then
    echo "Creating admin user with randomized password (shown earlier)..."
else
    echo -e "Creating admin user with password: ${RED}Password1!${NC}"
fi

docker exec kg-operator python /workspace/operator/configure.py admin --password "$ADMIN_PASSWORD"
echo ""

# Step 4: Configure AI provider (interactive selection)
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 4/9: Choosing AI extraction provider${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Choose your AI extraction provider:"
echo ""
echo -e "  ${GREEN}[1] OpenAI${NC} (GPT-4o, GPT-4o-mini)"
echo "      Direct access to OpenAI models"
echo ""
echo -e "  ${GREEN}[2] Anthropic${NC} (Claude Sonnet 4, Claude 3.5 Sonnet)"
echo "      Direct access to Anthropic Claude models"
echo ""
echo -e "  ${GREEN}[3] OpenRouter${NC} (200+ models from all providers)"
echo "      Unified API — access OpenAI, Anthropic, Google, Meta, Mistral, etc."
echo "      Single API key for all models"
echo ""
# Ollama requires separate setup (local inference, no API key)
# Configure via: ./operator.sh shell → configure ai-provider ollama
echo -e "  ${YELLOW}Note:${NC} Ollama (local inference) can be configured after setup"
echo "        via: ./operator.sh shell → configure ai-provider ollama"
echo ""
read -p "Choose option (1-3): " -r
echo ""

case "$REPLY" in
    1)
        AI_PROVIDER="openai"
        AI_KEY_PROMPT="OpenAI API key (sk-...)"
        echo -e "${GREEN}→${NC} Selected OpenAI"
        ;;
    2)
        AI_PROVIDER="anthropic"
        AI_KEY_PROMPT="Anthropic API key (sk-ant-...)"
        echo -e "${GREEN}→${NC} Selected Anthropic"
        ;;
    3)
        AI_PROVIDER="openrouter"
        AI_KEY_PROMPT="OpenRouter API key (sk-or-...)"
        echo -e "${GREEN}→${NC} Selected OpenRouter"
        ;;
    *)
        AI_PROVIDER="openai"
        AI_KEY_PROMPT="OpenAI API key (sk-...)"
        echo -e "${YELLOW}→${NC} Invalid option, defaulting to OpenAI"
        ;;
esac
echo ""

# Step 5: Store API key (skip for Ollama)
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 5/9: Validating API key${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo "Please enter your ${AI_PROVIDER} API key."
echo "The key will be validated and stored encrypted in the database."
echo ""
echo -e "${YELLOW}Press Ctrl+C to cancel${NC}"
echo ""

API_KEY_STORED=false
while [ "$API_KEY_STORED" = false ]; do
    read -p "${AI_KEY_PROMPT}: " AI_KEY
    echo ""

    if [ -z "$AI_KEY" ]; then
        echo -e "${RED}✗${NC} API key cannot be empty. Please try again."
        echo ""
        continue
    fi

    echo -e "${BLUE}→${NC} Validating and storing API key..."

    if docker exec kg-operator python /workspace/operator/configure.py api-key "$AI_PROVIDER" --key "$AI_KEY" 2>&1; then
        API_KEY_STORED=true
        echo ""
    else
        echo ""
        echo -e "${RED}✗${NC} API key validation failed. Please check your key and try again."
        echo ""
    fi
done

# Step 6: Refresh model catalog and select model
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 6/9: Selecting extraction model${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Set initial provider config with default model so catalog refresh can work
docker exec kg-operator python /workspace/operator/configure.py ai-provider "$AI_PROVIDER" 2>/dev/null

# Refresh model catalog from provider API
echo -e "${BLUE}→${NC} Fetching available models from ${AI_PROVIDER}..."
docker exec kg-operator python /workspace/operator/configure.py models refresh "$AI_PROVIDER" 2>&1
echo ""

# Get model list in TSV format for parsing
# Get full model list in TSV format
FULL_MODEL_LIST=$(docker exec kg-operator python /workspace/operator/configure.py models list "$AI_PROVIDER" --tsv --category extraction 2>/dev/null)

if [ -z "$FULL_MODEL_LIST" ]; then
    echo -e "${YELLOW}⚠${NC} Could not fetch models from catalog. Using provider default."
    echo ""
else
    # For OpenRouter (200+ models), filter to well-known reasoning models first.
    # For OpenAI/Anthropic, the seed data is already a curated list.
    if [ "$AI_PROVIDER" = "openrouter" ]; then
        # Pattern match popular/capable reasoning models
        MODEL_LIST=$(echo "$FULL_MODEL_LIST" | grep -iE '(gpt-4o|gpt-4\.5|gpt-5|claude.*sonnet|claude.*opus|claude.*haiku|gemini.*pro|gemini.*flash|llama.*70|llama.*405|qwen.*72|mistral.*large|deepseek.*chat|deepseek.*r1|command-r)')
    else
        MODEL_LIST="$FULL_MODEL_LIST"
    fi

    # Sort a TSV model list by prompt price (column 4)
    # Args: $1=model_list, $2=sort mode ("asc", "desc", or "none")
    sort_model_list() {
        local list="$1" mode="$2"
        case "$mode" in
            asc)  echo "$list" | sort -t$'\t' -k4 -n ;;
            desc) echo "$list" | sort -t$'\t' -k4 -rn ;;
            *)    echo "$list" ;;
        esac
    }

    # Build numbered menu from filtered list
    display_model_menu() {
        local model_list="$1"
        MENU_INDEX=0
        declare -g -a MODEL_IDS MODEL_NAMES MODEL_CATALOG_IDS MODEL_PRICES
        MODEL_IDS=()
        MODEL_NAMES=()
        MODEL_CATALOG_IDS=()
        MODEL_PRICES=()

        while IFS=$'\t' read -r cat_id model_id display_name prompt_price comp_price; do
            MENU_INDEX=$((MENU_INDEX + 1))
            MODEL_CATALOG_IDS[$MENU_INDEX]="$cat_id"
            MODEL_IDS[$MENU_INDEX]="$model_id"
            MODEL_NAMES[$MENU_INDEX]="$display_name"

            if [ -n "$prompt_price" ] && [ "$prompt_price" != "0.0000" ]; then
                MODEL_PRICES[$MENU_INDEX]="\$${prompt_price}/\$${comp_price} per 1M tokens"
            else
                MODEL_PRICES[$MENU_INDEX]="free (local)"
            fi

            printf "  ${GREEN}[%2d]${NC} %-45s %s\n" "$MENU_INDEX" "$display_name" "${MODEL_PRICES[$MENU_INDEX]}"
        done <<< "$model_list"
    }

    # State for the selection loop
    SHOW_ALL=false
    SORT_MODE="none"  # none → asc → desc → none
    CURRENT_LIST="$MODEL_LIST"

    redisplay_menu() {
        # Pick base list
        if [ "$SHOW_ALL" = true ]; then
            local base="$FULL_MODEL_LIST"
        else
            local base="$MODEL_LIST"
        fi
        CURRENT_LIST=$(sort_model_list "$base" "$SORT_MODE")

        echo ""
        if [ "$SHOW_ALL" = true ]; then
            echo "All available models:"
        else
            echo "Available extraction models:"
        fi
        # Show sort indicator
        case "$SORT_MODE" in
            asc)  echo -e "  ${YELLOW}(sorted: cheapest first)${NC}" ;;
            desc) echo -e "  ${YELLOW}(sorted: most expensive first)${NC}" ;;
        esac
        echo ""
        display_model_menu "$CURRENT_LIST"

        # Show options footer
        echo ""
        if [ "$AI_PROVIDER" = "openrouter" ]; then
            TOTAL_COUNT=$(echo "$FULL_MODEL_LIST" | wc -l)
            if [ "$SHOW_ALL" = true ]; then
                echo -e "  ${YELLOW}[ 0]${NC} Show curated models only"
            else
                echo -e "  ${YELLOW}[ 0]${NC} Show all ${TOTAL_COUNT} available models"
            fi
        fi
        case "$SORT_MODE" in
            none) echo -e "  ${YELLOW}[ \$]${NC} Sort by price (cheapest first)" ;;
            asc)  echo -e "  ${YELLOW}[ \$]${NC} Sort by price (most expensive first)" ;;
            desc) echo -e "  ${YELLOW}[ \$]${NC} Clear price sort" ;;
        esac
        echo ""
    }

    # Initial display
    redisplay_menu

    SELECTING=true
    while [ "$SELECTING" = true ]; do
        read -p "Choose model (1-${MENU_INDEX}) [1]: " -r MODEL_CHOICE
        if [ -z "$MODEL_CHOICE" ]; then
            MODEL_CHOICE=1
        fi

        # Handle "show all / show curated" toggle
        if [ "$MODEL_CHOICE" = "0" ] && [ "$AI_PROVIDER" = "openrouter" ]; then
            if [ "$SHOW_ALL" = true ]; then
                SHOW_ALL=false
            else
                SHOW_ALL=true
            fi
            redisplay_menu
            continue
        fi

        # Handle price sort toggle
        if [ "$MODEL_CHOICE" = '$' ]; then
            case "$SORT_MODE" in
                none) SORT_MODE="asc" ;;
                asc)  SORT_MODE="desc" ;;
                desc) SORT_MODE="none" ;;
            esac
            redisplay_menu
            continue
        fi

        # Validate and apply choice
        if [ "$MODEL_CHOICE" -ge 1 ] 2>/dev/null && [ "$MODEL_CHOICE" -le "$MENU_INDEX" ] 2>/dev/null; then
            CHOSEN_MODEL_ID="${MODEL_IDS[$MODEL_CHOICE]}"
            CHOSEN_CATALOG_ID="${MODEL_CATALOG_IDS[$MODEL_CHOICE]}"
            CHOSEN_NAME="${MODEL_NAMES[$MODEL_CHOICE]}"

            echo ""
            echo -e "${GREEN}→${NC} Selected: ${BOLD}${CHOSEN_NAME}${NC} (${CHOSEN_MODEL_ID})"

            # Prompt for max completion tokens with sensible default
            echo ""
            read -p "Max completion tokens [16384]: " -r MAX_TOKENS_INPUT
            MAX_TOKENS="${MAX_TOKENS_INPUT:-16384}"
            echo -e "${GREEN}→${NC} Max tokens: ${MAX_TOKENS}"

            # Enable and set as default in catalog
            docker exec kg-operator python /workspace/operator/configure.py models enable "$CHOSEN_CATALOG_ID" 2>/dev/null
            docker exec kg-operator python /workspace/operator/configure.py models default "$CHOSEN_CATALOG_ID" 2>/dev/null

            # Update active extraction config with chosen model and max tokens
            docker exec kg-operator python /workspace/operator/configure.py ai-provider "$AI_PROVIDER" --model "$CHOSEN_MODEL_ID" --max-tokens "$MAX_TOKENS"
            SELECTING=false
        else
            echo -e "${YELLOW}→${NC} Invalid choice, please try again."
        fi
    done
fi
echo ""

# Step 7: Configure embeddings
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 7/9: Configuring embedding provider${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Activating local embeddings (nomic-ai/nomic-embed-text-v1.5)..."
docker exec kg-operator python /workspace/operator/configure.py embedding --provider local
echo ""

# Step 8: Configure Garage credentials
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 8/9: Configuring Garage object storage${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Configuring S3-compatible object storage for images..."
echo ""

# Recreate Garage API key to capture credentials
echo -e "${BLUE}→${NC} Creating Garage API key..."

# Delete existing key if it exists (silently)
docker exec knowledge-graph-garage /garage key delete kg-api-key --yes >/dev/null 2>&1 || true

# Create new key and capture output
KEY_OUTPUT=$(docker exec knowledge-graph-garage /garage key create kg-api-key 2>&1)

# Extract credentials from output
GARAGE_KEY_ID=$(echo "$KEY_OUTPUT" | grep "Key ID:" | awk '{print $3}')
GARAGE_SECRET=$(echo "$KEY_OUTPUT" | grep "Secret key:" | awk '{print $3}')

if [ -z "$GARAGE_KEY_ID" ] || [ -z "$GARAGE_SECRET" ]; then
    echo -e "${RED}✗${NC} Failed to create Garage API key"
    echo ""
    echo "Debug output:"
    echo "$KEY_OUTPUT"
    exit 1
fi

echo -e "${GREEN}✓${NC} Garage API key created"

# Grant bucket permissions
GARAGE_BUCKET="${GARAGE_BUCKET:-kg-storage}"
docker exec knowledge-graph-garage /garage bucket allow --read --write --key kg-api-key "$GARAGE_BUCKET" >/dev/null 2>&1
echo -e "${GREEN}✓${NC} Bucket permissions configured"

# Store credentials in encrypted database
echo -e "${BLUE}→${NC} Storing credentials in encrypted database..."
GARAGE_CREDENTIALS="${GARAGE_KEY_ID}:${GARAGE_SECRET}"

if docker exec kg-operator python /workspace/operator/configure.py api-key garage --key "$GARAGE_CREDENTIALS" 2>&1 | grep -qi "stored"; then
    echo -e "${GREEN}✓${NC} Garage credentials stored securely"
    echo ""
else
    echo -e "${RED}✗${NC} Failed to store Garage credentials"
    echo ""
    echo "You can store them manually later with:"
    echo "  docker exec kg-operator python /workspace/operator/configure.py api-key garage --key \"${GARAGE_KEY_ID}:${GARAGE_SECRET}\""
    echo ""
fi

# Step 8: Save configuration and start application
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 9/9: Starting application (API + Web)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Detect NVIDIA GPU on host (only called when GPU_MODE is "auto")
detect_nvidia_gpu() {
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

# Determine configuration
DEV_MODE="false"
if [ "$USE_HOT_RELOAD" = true ]; then
    DEV_MODE="true"
fi

# GPU_MODE was set earlier in platform selection
# If "auto", detect NVIDIA GPU now
if [ "$GPU_MODE" = "auto" ]; then
    GPU_MODE=$(detect_nvidia_gpu)
fi

echo -e "${BLUE}→${NC} Saving platform configuration..."
cat > "$PROJECT_ROOT/.operator.conf" << EOF
# Operator configuration (auto-generated by guided-init)
# Edit with: ./operator.sh config --dev true --gpu nvidia|amd|mac|cpu
DEV_MODE=$DEV_MODE
GPU_MODE=$GPU_MODE
INITIALIZED_AT=$(date -Iseconds)
EOF
echo -e "${GREEN}✓${NC} Configuration saved (dev=$DEV_MODE, gpu=$GPU_MODE)"
echo ""

# Start the platform using operator.sh
echo -e "${BLUE}→${NC} Starting platform..."
"$PROJECT_ROOT/operator.sh" start
APP_STARTED=true
echo ""

# Show configuration status
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Platform Configuration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
docker exec kg-operator python /workspace/operator/configure.py status
echo ""

# Install CLI
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Installing kg CLI${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ -d "cli" ]; then
    echo -e "${BLUE}→${NC} Installing kg CLI globally..."
    cd cli && ./install.sh && cd ..
    echo ""
else
    echo -e "${YELLOW}⚠${NC} CLI directory not found. Skipping CLI installation."
    echo "  You can install it later by running: cd cli && ./install.sh"
    echo ""
fi

# Success banner
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}  ${BOLD}Setup Complete!${NC}                                        ${GREEN}║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Your Knowledge Graph system is ready!${NC}"
echo ""
echo -e "${YELLOW}Services running:${NC}"
echo "  • API:      http://localhost:8000"
echo "  • Web UI:   http://localhost:3000"
echo "  • Postgres: localhost:5432"
echo ""
if [ "$USE_RANDOM_PASSWORDS" = true ]; then
    echo -e "${YELLOW}Your Credentials (randomized - from earlier):${NC}"
    echo "  • Admin username: admin"
    echo -e "  • Admin password: ${GREEN}$ADMIN_PASSWORD${NC}"
    echo -e "  • Database password: ${GREEN}$POSTGRES_PASSWORD${NC}"
else
    echo -e "${YELLOW}Development Credentials (for evaluation/testing):${NC}"
    echo "  • Admin username: admin"
    echo -e "  • Admin password: ${RED}$ADMIN_PASSWORD${NC}"
    echo -e "  • Database password: ${RED}$POSTGRES_PASSWORD${NC}"
fi

echo ""
echo -e "${BOLD}Next steps:${NC}"
echo ""
echo -e "  ${GREEN}1.${NC} Login with kg CLI:"
echo "       kg login"
echo "       (Use username: admin, password: $ADMIN_PASSWORD)"
echo ""
echo -e "  ${GREEN}2.${NC} Test the system:"
echo "       kg health"
echo "       kg database stats"
echo ""
echo -e "  ${GREEN}3.${NC} Ingest your first document:"
echo "       kg ingest file -o \"Test\" path/to/document.txt"
echo ""
echo -e "  ${GREEN}4.${NC} Access the web UI:"
echo "       Open http://localhost:3000 in your browser"
echo ""
echo -e "  ${GREEN}5.${NC} Install MCP server for Claude Desktop:"
echo "       See: docs/guides/MCP_SERVER.md"
echo ""

if [ "$USE_RANDOM_PASSWORDS" = false ]; then
    echo -e "${YELLOW}💡 Production Use:${NC}"
    echo "  If you plan to keep this system, consider changing the default passwords:"
    echo "    • Admin password:    kg admin update-password"
    echo "    • Database password: Update POSTGRES_PASSWORD in .env and restart"
    echo ""
fi

echo -e "${YELLOW}To manage the platform:${NC}"
echo "  ./operator.sh start             # Start platform"
echo "  ./operator.sh stop              # Stop platform"
echo "  ./operator.sh stop --keep-infra # Stop but keep database"
echo "  ./operator.sh status            # Show status"
echo "  ./operator.sh logs api          # View API logs"
echo ""
echo -e "${YELLOW}To remove all data and containers:${NC}"
echo "  ./operator/lib/teardown.sh"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
