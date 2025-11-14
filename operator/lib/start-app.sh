#!/bin/bash
set -e

# ============================================================================
# start-app.sh
# Start application containers (api + web)
# Assumes infrastructure (postgres + garage) is already running
# ============================================================================

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
DOCKER_DIR="$PROJECT_ROOT/docker"

# Parse arguments
DEV_MODE=false
FORCE_MAC_MODE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            DEV_MODE=true
            shift
            ;;
        --mac)
            FORCE_MAC_MODE=true
            shift
            ;;
        --help|-h)
            echo "Start application containers (API + web)"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dev    Enable development mode with hot reload"
            echo "           • API: uvicorn --reload (already enabled)"
            echo "           • Web: Vite dev server with hot module replacement"
            echo "           • Source code mounted as volumes"
            echo "  --mac    Force Mac/CPU-only mode (disable NVIDIA GPU)"
            echo "           • Use this on Mac or systems without NVIDIA GPU"
            echo "           • Skips GPU detection and uses CPU for embeddings"
            echo "  --help   Show this help"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

if [ "$DEV_MODE" = true ]; then
    echo -e "${BLUE}Starting application containers (${YELLOW}development mode${BLUE})...${NC}"
    echo ""
    echo -e "${YELLOW}Hot reload enabled:${NC}"
    echo "  • Operator: Scripts mounted at /workspace (live edits)"
    echo "  • API: Source mounted at /app/api (uvicorn --reload)"
    echo "  • Web: Source mounted at /app/src (Vite HMR)"
    echo "  • Edit files in your local repo, changes auto-reload in containers"
    echo ""
else
    echo -e "${BLUE}Starting application containers (production mode)...${NC}"
    echo ""
fi

# Check if infrastructure is running
echo -e "${BLUE}→ Checking infrastructure...${NC}"

POSTGRES_RUNNING=$(docker ps --format '{{.Names}}' | grep -E "^(kg-postgres-dev|knowledge-graph-postgres)$" || true)
GARAGE_RUNNING=$(docker ps --format '{{.Names}}' | grep -E "^(kg-garage-dev|knowledge-graph-garage)$" || true)

if [ -z "$POSTGRES_RUNNING" ]; then
    echo -e "${RED}✗ PostgreSQL not running${NC}"
    echo ""
    echo "Start infrastructure first:"
    echo "  ./operator/lib/start-infra.sh"
    echo ""
    exit 1
fi

if [ -z "$GARAGE_RUNNING" ]; then
    echo -e "${YELLOW}⚠  Garage not running (optional for basic operation)${NC}"
fi

echo -e "${GREEN}✓ Infrastructure ready${NC}"
echo ""

cd "$DOCKER_DIR"

# Detect platform and GPU availability
detect_platform() {
    local USE_MAC_OVERRIDE=false

    # Detect OS using uname (more reliable than $OSTYPE)
    local OS_TYPE=$(uname -s)

    # Check if running on Mac
    if [[ "$OS_TYPE" == "Darwin" ]]; then
        echo -e "${YELLOW}⚠  Mac platform detected (no NVIDIA GPU support)${NC}"
        USE_MAC_OVERRIDE=true
    # Check if NVIDIA GPU available on Linux
    elif [[ "$OS_TYPE" == "Linux" ]]; then
        if ! command -v nvidia-smi &> /dev/null; then
            echo -e "${YELLOW}⚠  NVIDIA GPU not detected (nvidia-smi not available)${NC}"
            USE_MAC_OVERRIDE=true
        elif ! nvidia-smi &> /dev/null; then
            echo -e "${YELLOW}⚠  NVIDIA GPU not available${NC}"
            USE_MAC_OVERRIDE=true
        else
            echo -e "${GREEN}✓ NVIDIA GPU detected${NC}"
        fi
    fi

    echo "$USE_MAC_OVERRIDE"
}

# Prepare docker-compose command with optional dev and platform overrides
COMPOSE_FILES="-f docker-compose.yml"

# Add dev mode override if requested
if [ "$DEV_MODE" = true ]; then
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.dev.yml"
fi

# Add Mac/non-GPU override if needed
if [ "$FORCE_MAC_MODE" = true ]; then
    # Mac mode forced via --mac flag (from quickstart or manual)
    USE_MAC_OVERRIDE=true
    echo -e "${YELLOW}→ Mac mode forced via --mac flag${NC}"
else
    # Auto-detect platform
    USE_MAC_OVERRIDE=$(detect_platform)
fi

if [ "$USE_MAC_OVERRIDE" = true ]; then
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.override.mac.yml"
    echo -e "${BLUE}→ Using CPU-only mode for embeddings${NC}"
fi
echo ""

# Start API
echo -e "${BLUE}→ Starting API server...${NC}"

# Set build metadata
export GIT_COMMIT=$(cd "$PROJECT_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")
export BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

docker-compose $COMPOSE_FILES --env-file "$PROJECT_ROOT/.env" up -d --build api

echo -e "${BLUE}→ Waiting for API to be healthy...${NC}"

# Wait for API (up to 60 seconds)
for i in {1..30}; do
    if docker ps --format '{{.Names}} {{.Status}}' | grep -q "kg-api.*healthy\|knowledge-graph-api.*healthy"; then
        echo -e "${GREEN}✓ API server is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}⚠  API health check timeout (may still be starting)${NC}"
        echo ""
        echo "Check logs with: docker logs kg-api-dev"
        break
    fi
    sleep 2
done

# Start web viz app (if defined in docker-compose)
if docker-compose $COMPOSE_FILES --env-file "$PROJECT_ROOT/.env" config --services 2>/dev/null | grep -q "^web$\|^viz$"; then
    echo ""
    echo -e "${BLUE}→ Starting web visualization...${NC}"
    # Build metadata already exported above
    docker-compose $COMPOSE_FILES --env-file "$PROJECT_ROOT/.env" up -d --build web 2>/dev/null || docker-compose $COMPOSE_FILES --env-file "$PROJECT_ROOT/.env" up -d --build viz 2>/dev/null || true

    if [ "$DEV_MODE" = true ]; then
        echo -e "${GREEN}✓ Web dev server starting (Vite HMR enabled)${NC}"
        echo -e "${YELLOW}  Note: Web dev server runs on port 3000 (mapped from internal 5173)${NC}"
    else
        echo -e "${GREEN}✓ Web app starting${NC}"
    fi
fi

echo ""
echo -e "${GREEN}✅ Application started${NC}"
echo ""

if [ "$DEV_MODE" = true ]; then
    echo -e "${YELLOW}Development Mode (Hot Reload Active)${NC}"
    echo ""
    echo "Services:"
    echo "  • Operator: Configuration & management"
    echo "    - Source: $PROJECT_ROOT → /workspace"
    echo "    - Live script edits (operator/*, schema/*)"
    echo "  • API server: http://localhost:8000"
    echo "    - Source: $PROJECT_ROOT/api → /app/api"
    echo "    - Changes auto-reload (uvicorn --reload)"
    echo "  • Web app: http://localhost:3000"
    echo "    - Source: $PROJECT_ROOT/web/src → /app/src"
    echo "    - Hot Module Replacement (Vite HMR)"
    echo ""
    echo "Workflow:"
    echo "  1. Edit files in $PROJECT_ROOT (operator/*, api/*, web/*)"
    echo "  2. Changes automatically reflect in running containers"
    echo "  3. No rebuild required!"
    echo ""
else
    echo "Services:"
    echo "  • API server: http://localhost:8000"
    echo "  • Web app: http://localhost:3000"
    echo ""
fi

echo "Check status:"
echo "  docker-compose ps"
echo ""
echo "View logs:"
echo "  docker-compose $COMPOSE_FILES logs -f api"
echo "  docker-compose $COMPOSE_FILES logs -f web"
echo ""
