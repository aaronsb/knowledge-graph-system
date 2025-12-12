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
echo -e "${BLUE}║${NC}  ${BOLD}Knowledge Graph System - TL;DR Quickstart${NC}             ${BLUE}    ║${NC}"
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
echo "  • AI extraction: OpenAI GPT-4o"
echo "  • Embeddings: Local (nomic-ai/nomic-embed-text-v1.5)"
echo ""
echo -e "${YELLOW}Prerequisites:${NC}"
echo "  • Docker with permissions (docker ps should work)"
echo "  • OpenAI API key (will prompt during setup)"
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
read -p "Continue with quickstart? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "Quickstart cancelled."
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
echo "      • Note: This only affects local embedding compute, not AI extraction"
echo ""
echo -e "  ${GREEN}[2] Linux / Windows WSL2${NC}"
echo "      • Auto-detects NVIDIA GPU (CUDA acceleration if available)"
echo "      • Falls back to CPU if no NVIDIA GPU found"
echo "      • Note: This only affects local embedding compute, not AI extraction"
echo ""
echo -e "${YELLOW}ℹ️  What this affects:${NC}"
echo "  • WHERE local embeddings are computed (MPS/CUDA/CPU)"
echo "  • Does NOT affect WHICH models are used (local vs API)"
echo "  • AI extraction always uses remote API (OpenAI/Anthropic)"
echo ""
read -p "Choose option (1 or 2): " -r
echo ""

USE_MAC_MODE=false
if [[ $REPLY == "1" ]]; then
    USE_MAC_MODE=true
    echo -e "${YELLOW}→${NC} Will configure for Mac platform"
    echo ""
else
    echo -e "${GREEN}→${NC} Will auto-detect GPU availability"
    echo ""
fi

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
echo -e "${BOLD}Step 1/7: Generating infrastructure secrets${NC}"
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
echo -e "${BOLD}Step 2/7: Starting infrastructure (Postgres + Garage + Operator)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
./operator/lib/start-infra.sh
INFRA_STARTED=true
echo ""

# Step 3: Configure admin
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 3/7: Creating admin user${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ "$USE_RANDOM_PASSWORDS" = true ]; then
    echo "Creating admin user with randomized password (shown earlier)..."
else
    echo -e "Creating admin user with password: ${RED}Password1!${NC}"
fi

docker exec kg-operator python /workspace/operator/configure.py admin --password "$ADMIN_PASSWORD"
echo ""

# Step 4: Configure AI provider
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 4/7: Configuring AI extraction provider${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Setting OpenAI GPT-4o as extraction provider..."
docker exec kg-operator python /workspace/operator/configure.py ai-provider openai --model gpt-4o
echo ""

# Step 5: Configure embeddings
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 5/7: Configuring embedding provider${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Activating local embeddings (nomic-ai/nomic-embed-text-v1.5)..."
docker exec kg-operator python /workspace/operator/configure.py embedding 2
echo ""

# Step 6: Store OpenAI API key with validation loop
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 6/8: Storing OpenAI API key${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Please enter your OpenAI API key."
echo "The key will be validated and stored encrypted in the database."
echo ""
echo -e "${YELLOW}Press Ctrl+C to cancel${NC}"
echo ""

API_KEY_STORED=false
while [ "$API_KEY_STORED" = false ]; do
    read -sp "OpenAI API key (sk-...): " OPENAI_KEY
    echo ""

    if [ -z "$OPENAI_KEY" ]; then
        echo -e "${RED}✗${NC} API key cannot be empty. Please try again."
        echo ""
        continue
    fi

    echo -e "${BLUE}→${NC} Validating and storing API key..."

    # Try to store the key (will validate automatically)
    if docker exec kg-operator python /workspace/operator/configure.py api-key openai --key "$OPENAI_KEY" 2>&1; then
        API_KEY_STORED=true
        echo ""
    else
        echo ""
        echo -e "${RED}✗${NC} API key validation failed. Please check your key and try again."
        echo ""
    fi
done

# Step 7: Configure Garage credentials
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 7/8: Configuring Garage object storage${NC}"
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
GARAGE_BUCKET="${GARAGE_BUCKET:-knowledge-graph-images}"
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
echo -e "${BOLD}Step 8/8: Starting application (API + Web)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Detect GPU on host
detect_gpu() {
    if [[ "$(uname)" == "Darwin" ]]; then
        echo "mac"
        return
    fi
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

if [ "$USE_MAC_MODE" = true ]; then
    GPU_MODE="mac"
else
    GPU_MODE=$(detect_gpu)
fi

echo -e "${BLUE}→${NC} Saving platform configuration..."
cat > "$PROJECT_ROOT/.operator.conf" << EOF
# Operator configuration (auto-generated by guided-init)
# Edit with: ./operator.sh config --dev true --gpu nvidia
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
echo -e "${GREEN}║${NC}  ${BOLD}🎉 Quickstart Complete!${NC}                                ${GREEN}║${NC}"
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
