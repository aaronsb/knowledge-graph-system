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

# Source common functions (provides run_compose, load_operator_config)
source "$SCRIPT_DIR/common.sh"

# Load config from .operator.conf (can be overridden by args)
load_operator_config

# Parse arguments (override config file settings)
while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            DEV_MODE=true
            shift
            ;;
        --mac)
            GPU_MODE=mac
            shift
            ;;
        --help|-h)
            echo "Start application containers (API + web)"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dev    Enable development mode with volume mounts"
            echo "           • API: source mounted, restart to pick up changes"
            echo "           • Web: Vite dev server with hot module replacement"
            echo "           • Source code mounted as volumes"
            echo "  --mac    Force Mac/CPU-only mode (disable NVIDIA GPU)"
            echo "           • Use this on Mac or systems without NVIDIA GPU"
            echo "           • Skips GPU detection and uses CPU for embeddings"
            echo "  --help   Show this help"
            echo ""
            echo "Config is loaded from .operator.conf if it exists."
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
    echo -e "${YELLOW}Development mode:${NC}"
    echo "  • Operator: Scripts mounted at /workspace (live edits)"
    echo "  • API: Source mounted at /app/api (restart to pick up changes)"
    echo "  • Web: Source mounted at /app/src (Vite HMR)"
    echo "  • Web changes auto-reload; API changes require: ./operator.sh restart api"
    echo ""
else
    echo -e "${BLUE}Starting application containers (production mode)...${NC}"
    echo ""
fi

# Get container patterns from config
POSTGRES_PATTERN=$(get_container_pattern postgres)
GARAGE_PATTERN=$(get_container_pattern garage)
API_PATTERN=$(get_container_pattern api)

# Check if infrastructure is running
echo -e "${BLUE}→ Checking infrastructure...${NC}"

POSTGRES_RUNNING=$(docker ps --format '{{.Names}}' | grep -E "$POSTGRES_PATTERN" || true)
GARAGE_RUNNING=$(docker ps --format '{{.Names}}' | grep -E "$GARAGE_PATTERN" || true)

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
# Returns: "mac" | "nvidia" | "cpu"
detect_platform() {
    # Detect OS using uname (more reliable than $OSTYPE)
    local OS_TYPE=$(uname -s)

    # Check if running on Mac
    if [[ "$OS_TYPE" == "Darwin" ]]; then
        echo -e "${YELLOW}🍎 Mac platform detected${NC}"
        echo "mac"
        return
    fi

    # Check if NVIDIA GPU available on Linux/Windows
    if [[ "$OS_TYPE" == "Linux" ]] || [[ "$OS_TYPE" =~ ^MINGW|^MSYS|^CYGWIN ]]; then
        if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
            # Get GPU info
            GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
            echo -e "${GREEN}✓ NVIDIA GPU detected: ${GPU_NAME}${NC}"
            echo "nvidia"
            return
        else
            echo -e "${YELLOW}⚠  No NVIDIA GPU detected${NC}"
            echo "cpu"
            return
        fi
    fi

    # Unknown OS or no GPU
    echo -e "${YELLOW}⚠  Unknown platform, using CPU-only mode${NC}"
    echo "cpu"
}

# Show configuration from .operator.conf (loaded by common.sh)
echo -e "${BLUE}→ Configuration: dev=$DEV_MODE, gpu=$GPU_MODE${NC}"

case "$GPU_MODE" in
    mac)
        echo -e "${BLUE}→ Using Mac configuration (MPS GPU acceleration via Metal)${NC}"
        ;;
    nvidia)
        echo -e "${BLUE}→ Using NVIDIA GPU configuration (CUDA acceleration)${NC}"
        ;;
    amd)
        echo -e "${BLUE}→ Using AMD GPU configuration (ROCm wheels)${NC}"
        ;;
    amd-host)
        echo -e "${BLUE}→ Using AMD GPU configuration (host ROCm libraries)${NC}"
        ;;
    cpu|*)
        echo -e "${BLUE}→ Using CPU-only mode (no GPU acceleration)${NC}"
        ;;
esac
echo ""

# Start API
echo -e "${BLUE}→ Starting API server...${NC}"

# Set build metadata
export GIT_COMMIT=$(cd "$PROJECT_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")
export BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

run_compose up -d --build api

# Get API container name
API_CONTAINER=$(get_container_name api)

echo -e "${BLUE}→ Waiting for API to be healthy...${NC}"

# Wait for API (up to 60 seconds)
for i in {1..30}; do
    if docker ps --format '{{.Names}} {{.Status}}' | grep -qE "$API_PATTERN.*healthy"; then
        echo -e "${GREEN}✓ API server is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}⚠  API health check timeout (may still be starting)${NC}"
        echo ""
        echo "Check logs with: docker logs $API_CONTAINER"
        break
    fi
    sleep 2
done

# Start web viz app (if defined in docker-compose)
if run_compose config --services 2>/dev/null | grep -q "^web$\|^viz$"; then
    echo ""
    echo -e "${BLUE}→ Starting web visualization...${NC}"
    # Build metadata already exported above
    run_compose up -d --build web 2>/dev/null || run_compose up -d --build viz 2>/dev/null || true

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
    echo "    - Restart to pick up changes: ./operator.sh restart api"
    echo "  • Web app: http://localhost:3000"
    echo "    - Source: $PROJECT_ROOT/web/src → /app/src"
    echo "    - Hot Module Replacement (Vite HMR)"
    echo ""
    echo "Workflow:"
    echo "  1. Edit files in $PROJECT_ROOT (operator/*, api/*, web/*)"
    echo "  2. Web changes auto-reload; API changes need: ./operator.sh restart api"
    echo "  3. No rebuild required (unless deps change)!"
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
