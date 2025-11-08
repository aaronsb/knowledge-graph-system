#!/bin/bash
set -e

# ============================================================================
# bootstrap.sh
# Knowledge Graph System - Complete Cold Start Orchestration
# ============================================================================
#
# PURPOSE:
# Automate the complete cold start sequence from zero to operational system.
# This script chains together all the individual start scripts and handles
# prerequisite checks, service startup, configuration, and verification.
#
# WHAT IT DOES:
# 1. Checks prerequisites (Docker, Python, Node.js)
# 2. Creates .env from .env.example if needed
# 3. Starts PostgreSQL + Apache AGE database
# 4. Starts Garage object storage
# 5. Starts FastAPI server
# 6. Runs initialize-platform.sh for auth/secrets/AI config
# 7. Installs kg CLI globally
# 8. Verifies system health
#
# USAGE:
# ./scripts/setup/bootstrap.sh             # Production mode (interactive)
# ./scripts/setup/bootstrap.sh --dev       # Development mode (quick start)
# ./scripts/setup/bootstrap.sh --help      # Show this help
#
# FLAGS:
# --dev       Development mode (uses Password1!, no prompts)
# --skip-cli  Skip kg CLI installation
# --help      Show this help message
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

# Parse command line arguments
DEV_MODE=false
SKIP_CLI=false

show_help() {
    echo "Knowledge Graph System - Complete Cold Start Bootstrap"
    echo ""
    echo "Automate the complete cold start sequence from zero to operational system."
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --dev       Development mode (uses Password1!, fastest cold start)"
    echo "  --skip-cli  Skip kg CLI installation"
    echo "  --help      Show this help message and exit"
    echo ""
    echo "What this script does:"
    echo "  1. Checks prerequisites (Docker, Python 3.11+, Node.js 18+)"
    echo "  2. Creates .env from .env.example if needed"
    echo "  3. Starts PostgreSQL + Apache AGE database"
    echo "  4. Starts Garage object storage"
    echo "  5. Starts FastAPI server"
    echo "  6. Configures authentication, secrets, and AI providers"
    echo "  7. Installs kg CLI globally"
    echo "  8. Verifies system health"
    echo ""
    echo "Expected time: ~3-4 minutes for fresh system"
    echo ""
    echo "Examples:"
    echo "  ./scripts/setup/bootstrap.sh           # Production mode"
    echo "  ./scripts/setup/bootstrap.sh --dev     # Development mode (quick)"
    echo ""
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            DEV_MODE=true
            shift
            ;;
        --skip-cli)
            SKIP_CLI=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Run '$0 --help' for usage information"
            exit 1
            ;;
    esac
done

# Banner
clear
echo -e "${BLUE}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Knowledge Graph System - Cold Start Bootstrap           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
if [ "$DEV_MODE" = true ]; then
    echo -e "${YELLOW}Mode: Development (--dev)${NC}"
    echo -e "${YELLOW}Admin password will be set to: Password1!${NC}"
else
    echo -e "${GREEN}Mode: Production${NC}"
    echo -e "${GREEN}You will be prompted for admin password${NC}"
fi
echo ""
echo -e "${BOLD}This will:${NC}"
echo "  1. Check prerequisites"
echo "  2. Start PostgreSQL + Apache AGE database"
echo "  3. Start Garage object storage"
echo "  4. Start FastAPI server"
echo "  5. Configure authentication and secrets"
if [ "$SKIP_CLI" = true ]; then
    echo "  6. ${YELLOW}[SKIP]${NC} kg CLI installation"
else
    echo "  6. Install kg CLI globally"
fi
echo "  7. Verify system health"
echo ""
echo -e "${BOLD}Expected time: ~3-4 minutes${NC}"
echo ""
read -p "Continue? [Y/n]: " -r
echo ""
if [[ -z "$REPLY" || "$REPLY" =~ ^[Yy]$ ]]; then
    # Empty (Enter) or Y/y - continue
    :
elif [[ "$REPLY" =~ ^[Nn]$ ]]; then
    # N/n - abort
    echo -e "${YELLOW}Bootstrap cancelled${NC}"
    exit 0
else
    # Invalid input - warn and default to Yes
    echo -e "${YELLOW}Invalid input '$REPLY', defaulting to Yes${NC}"
fi
echo ""

# ============================================================================
# Step 1: Check Prerequisites
# ============================================================================
echo -e "${BLUE}${BOLD}[1/7]${NC} ${BOLD}Checking prerequisites...${NC}"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗${NC} Docker not found"
    echo -e "${YELLOW}  Install Docker: https://docs.docker.com/get-docker/${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker found: $(docker --version | cut -d' ' -f3 | cut -d',' -f1)"

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}✗${NC} Docker Compose not found"
    echo -e "${YELLOW}  Install Docker Compose: https://docs.docker.com/compose/install/${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker Compose found"

# Check Docker daemon
if ! docker ps &> /dev/null; then
    echo -e "${RED}✗${NC} Docker daemon not running"
    echo -e "${YELLOW}  Start Docker daemon and try again${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker daemon running"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗${NC} python3 not found"
    echo -e "${YELLOW}  Install Python 3.11+: https://www.python.org/downloads/${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✓${NC} Python found: $PYTHON_VERSION"

# Check Node.js (only if not skipping CLI)
if [ "$SKIP_CLI" = false ]; then
    if ! command -v node &> /dev/null; then
        echo -e "${RED}✗${NC} node not found"
        echo -e "${YELLOW}  Install Node.js 18+: https://nodejs.org/${NC}"
        exit 1
    fi
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓${NC} Node.js found: $NODE_VERSION"

    if ! command -v npm &> /dev/null; then
        echo -e "${RED}✗${NC} npm not found"
        echo -e "${YELLOW}  Install npm (usually bundled with Node.js)${NC}"
        exit 1
    fi
    NPM_VERSION=$(npm --version)
    echo -e "${GREEN}✓${NC} npm found: $NPM_VERSION"
fi

echo ""
echo -e "${GREEN}✓${NC} All prerequisites satisfied"
echo ""

# ============================================================================
# Step 2: Create .env if needed
# ============================================================================
echo -e "${BLUE}${BOLD}[2/7]${NC} ${BOLD}Checking environment configuration...${NC}"
echo ""

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    if [ ! -f "$PROJECT_ROOT/.env.example" ]; then
        echo -e "${RED}✗${NC} .env.example not found"
        exit 1
    fi
    echo -e "${YELLOW}→${NC} Creating .env from .env.example..."
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    echo -e "${GREEN}✓${NC} .env created (will be configured by initialize-platform.sh)"
else
    echo -e "${GREEN}✓${NC} .env already exists"
fi
echo ""

# ============================================================================
# Step 3: Start Database
# ============================================================================
echo -e "${BLUE}${BOLD}[3/7]${NC} ${BOLD}Starting PostgreSQL + Apache AGE database...${NC}"
echo ""

if [ ! -x "$PROJECT_ROOT/scripts/services/start-database.sh" ]; then
    echo -e "${RED}✗${NC} start-database.sh not found or not executable"
    exit 1
fi

# Auto-confirm database startup
"$PROJECT_ROOT/scripts/services/start-database.sh" -y

echo ""
echo -e "${GREEN}✓${NC} Database started and migrations applied"
echo ""

# ============================================================================
# Step 4: Start Garage
# ============================================================================
echo -e "${BLUE}${BOLD}[4/7]${NC} ${BOLD}Starting Garage object storage...${NC}"
echo ""

if [ ! -x "$PROJECT_ROOT/scripts/services/start-garage.sh" ]; then
    echo -e "${YELLOW}⚠${NC}  start-garage.sh not found - skipping Garage"
    echo -e "${YELLOW}  (Garage is optional - system will work without it)${NC}"
else
    # Auto-confirm Garage startup
    "$PROJECT_ROOT/scripts/services/start-garage.sh" -y || {
        echo -e "${YELLOW}⚠${NC}  Garage startup failed - continuing without it"
        echo -e "${YELLOW}  (Garage is optional - system will work without it)${NC}"
    }
    echo ""
    echo -e "${GREEN}✓${NC} Garage started (or skipped if not needed)"
fi
echo ""

# ============================================================================
# Step 5: Install API Dependencies
# ============================================================================
# TODO: Once API server is containerized, replace this with:
#       ./scripts/services/start-api.sh -y
#       (following the same pattern as start-database.sh and start-garage.sh)
echo -e "${BLUE}${BOLD}[5/7]${NC} ${BOLD}Installing API dependencies...${NC}"
echo ""
echo -e "${YELLOW}NOTE:${NC} API server will start after platform initialization"
echo -e "${YELLOW}      (temporary - waiting for API containerization)${NC}"
echo ""

# Create venv if needed
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${BLUE}→${NC} Creating Python virtual environment..."
    cd "$PROJECT_ROOT"
    python3 -m venv venv
    source venv/bin/activate
    pip install --quiet --upgrade pip
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${GREEN}✓${NC} Virtual environment exists"
    cd "$PROJECT_ROOT"
    source venv/bin/activate
fi

# Install dependencies
echo -e "${BLUE}→${NC} Installing Python dependencies..."
pip install --quiet -r "$PROJECT_ROOT/requirements.txt"
echo -e "${GREEN}✓${NC} Dependencies installed"
echo ""

# ============================================================================
# Step 6: Initialize Platform
# ============================================================================
echo -e "${BLUE}${BOLD}[6/7]${NC} ${BOLD}Configuring authentication, secrets, and AI providers...${NC}"
echo ""

if [ ! -x "$PROJECT_ROOT/scripts/setup/initialize-platform.sh" ]; then
    echo -e "${RED}✗${NC} initialize-platform.sh not found or not executable"
    exit 1
fi

if [ "$DEV_MODE" = true ]; then
    echo -e "${YELLOW}Running in development mode (--dev)${NC}"
    echo -e "${YELLOW}Admin password will be: Password1!${NC}"
    echo ""
    "$PROJECT_ROOT/scripts/setup/initialize-platform.sh" --dev
else
    echo -e "${BLUE}Running in production mode${NC}"
    echo -e "${BLUE}You will be prompted for configuration...${NC}"
    echo ""
    "$PROJECT_ROOT/scripts/setup/initialize-platform.sh"
fi

echo ""
echo -e "${GREEN}✓${NC} Platform configured"
echo ""

# ============================================================================
# Step 6.5: Start API Server
# ============================================================================
# TODO: Once API server is containerized, this step will be merged into Step 5
#       and use docker-compose like database/garage instead of nohup
echo -e "${BLUE}${BOLD}[6.5/7]${NC} ${BOLD}Starting FastAPI server...${NC}"
echo ""

# Start API in background using nohup
cd "$PROJECT_ROOT"
source venv/bin/activate

# Ensure logs directory exists
mkdir -p logs

nohup python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 > logs/api_bootstrap_$(date +%Y%m%d_%H%M%S).log 2>&1 &
API_PID=$!

echo -e "${GREEN}✓${NC} API server started (PID: $API_PID)"
echo -e "${BLUE}→${NC} Logs: logs/api_bootstrap_*.log"
echo ""

# Give API a moment to fully initialize
echo -e "${BLUE}→${NC} Waiting for API to initialize..."
sleep 3
echo ""

# ============================================================================
# Step 7: Install kg CLI
# ============================================================================
if [ "$SKIP_CLI" = true ]; then
    echo -e "${BLUE}${BOLD}[7/7]${NC} ${BOLD}Skipping kg CLI installation (--skip-cli)${NC}"
    echo ""
else
    echo -e "${BLUE}${BOLD}[7/7]${NC} ${BOLD}Installing kg CLI globally...${NC}"
    echo ""

    if [ ! -f "$PROJECT_ROOT/client/install.sh" ]; then
        echo -e "${YELLOW}⚠${NC}  client/install.sh not found - skipping CLI installation"
        echo -e "${YELLOW}  (You can install manually later: cd client && ./install.sh)${NC}"
    else
        cd "$PROJECT_ROOT/client"
        if [ -x "./install.sh" ]; then
            ./install.sh
            cd "$PROJECT_ROOT"
            echo ""
            echo -e "${GREEN}✓${NC} kg CLI installed to ~/.local/bin/kg"
        else
            echo -e "${YELLOW}⚠${NC}  install.sh not executable - skipping"
            cd "$PROJECT_ROOT"
        fi
    fi
    echo ""
fi

# ============================================================================
# Step 8: Verify System Health
# ============================================================================
echo -e "${BLUE}${BOLD}[8/8]${NC} ${BOLD}Verifying system health...${NC}"
echo ""

# Check if kg command is available (if we installed it)
if [ "$SKIP_CLI" = false ] && command -v kg &> /dev/null; then
    echo -e "${BLUE}→${NC} Running health checks via kg CLI..."
    echo ""

    # Test kg health
    if kg health &> /dev/null; then
        echo -e "${GREEN}✓${NC} kg health: API responding"
    else
        echo -e "${YELLOW}⚠${NC}  kg health: API not responding yet (may need a moment)"
    fi

    # Test kg database stats
    if kg database stats &> /dev/null; then
        echo -e "${GREEN}✓${NC} kg database stats: Database accessible"
    else
        echo -e "${YELLOW}⚠${NC}  kg database stats: Database not accessible yet"
    fi
else
    echo -e "${BLUE}→${NC} Testing API endpoint directly..."
    echo ""

    # Test API health endpoint with curl
    if command -v curl &> /dev/null; then
        if curl -s http://localhost:8000/health &> /dev/null; then
            echo -e "${GREEN}✓${NC} API health endpoint: Responding"
        else
            echo -e "${YELLOW}⚠${NC}  API health endpoint: Not responding yet (may need a moment)"
        fi
    else
        echo -e "${YELLOW}⚠${NC}  curl not found - skipping API health check"
    fi
fi

echo ""

# ============================================================================
# Success Summary
# ============================================================================
echo -e "${GREEN}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              🎉 Bootstrap Complete! 🎉                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${BOLD}Services Running:${NC}"
echo "  • PostgreSQL + Apache AGE (knowledge-graph-postgres)"
echo "  • Garage object storage (knowledge-graph-garage)"
echo "  • FastAPI server (background, logs: logs/api_*.log)"
if [ "$SKIP_CLI" = false ]; then
    echo "  • kg CLI installed to ~/.local/bin/kg"
fi
echo ""
echo -e "${BOLD}Next Steps:${NC}"
echo ""

if [ "$SKIP_CLI" = false ] && command -v kg &> /dev/null; then
    echo "  1. Verify system health:"
    echo -e "     ${BLUE}kg health${NC}"
    echo -e "     ${BLUE}kg database stats${NC}"
    echo ""
    echo "  2. Ingest your first document:"
    echo -e "     ${BLUE}kg ingest file -o \"My Ontology\" document.txt${NC}"
    echo ""
    echo "  3. Search the graph:"
    echo -e "     ${BLUE}kg search query \"your search term\"${NC}"
    echo ""
    echo "  4. Create a backup:"
    echo -e "     ${BLUE}kg admin backup${NC}"
else
    echo "  1. Verify API is running:"
    echo -e "     ${BLUE}curl http://localhost:8000/health${NC}"
    echo ""
    echo "  2. Install kg CLI (if skipped):"
    echo -e "     ${BLUE}cd client && ./install.sh${NC}"
fi
echo ""
echo -e "${BOLD}Documentation:${NC}"
echo "  • Quickstart: docs/guides/COLD-START.md"
echo "  • User Manual: docs/manual/"
echo "  • Architecture: docs/architecture/"
echo ""
echo -e "${BOLD}Logs:${NC}"
echo "  • API: logs/api_*.log"
echo -e "  • Database: ${BLUE}docker logs knowledge-graph-postgres${NC}"
echo -e "  • Garage: ${BLUE}docker logs knowledge-graph-garage${NC}"
echo ""

if [ "$DEV_MODE" = true ]; then
    echo -e "${YELLOW}${BOLD}Development Mode Active:${NC}"
    echo -e "${YELLOW}  Admin credentials: admin / Password1!${NC}"
    echo -e "${YELLOW}  ⚠️  NEVER use in production!${NC}"
    echo ""
fi

echo -e "${GREEN}Happy graphing! 🚀${NC}"
echo ""
