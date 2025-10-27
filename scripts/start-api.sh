#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m'

# Parse all arguments
AUTO_CONFIRM=false
PORT=8000
RELOAD=""

for arg in "$@"; do
    case $arg in
        -y|--yes)
            AUTO_CONFIRM=true
            ;;
        --reload)
            RELOAD="--reload"
            ;;
        [0-9]*)
            PORT=$arg
            ;;
    esac
done

# Show usage and require confirmation
if [ "$AUTO_CONFIRM" = false ]; then
    echo -e "${BLUE}🚀 Start Knowledge Graph API Server${NC}"
    echo "======================================"
    echo ""
    echo -e "${YELLOW}What this does:${NC}"
    echo "  • Starts FastAPI server in foreground"
    echo "  • Automatically starts PostgreSQL if needed"
    echo "  • Listens on http://localhost:$PORT"
    echo "  • Press Ctrl+C to stop"
    echo ""
    echo -e "${GRAY}Usage:${NC}"
    echo "  $0 -y                   # Start on port 8000 (skip confirmation)"
    echo "  $0 -y 8080              # Start on custom port"
    echo "  $0 -y --reload          # Start with hot reload (dev mode)"
    echo "  $0 -y --reload 8080     # All options (any order works)"
    echo ""
    echo -e "${GRAY}API Endpoints:${NC}"
    echo "  http://localhost:$PORT/docs   # Interactive API docs"
    echo "  http://localhost:$PORT/redoc  # ReDoc API documentation"
    echo "  http://localhost:$PORT/health # Health check"
    echo ""
    read -p "$(echo -e ${YELLOW}Start API server now? [y/N]:${NC} )" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Cancelled${NC}"
        exit 0
    fi
fi

echo -e "${BLUE}🚀 Knowledge Graph API Server${NC}"
echo "=============================="

# Check venv
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠ Virtual environment not found${NC}"
    echo -e "${YELLOW}  Creating venv and installing dependencies...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    source venv/bin/activate
fi

# Check PostgreSQL
if ! docker ps --format '{{.Names}}' | grep -q knowledge-graph-postgres; then
    echo -e "${YELLOW}⚠ PostgreSQL is not running${NC}"
    echo -e "${YELLOW}  Starting PostgreSQL...${NC}"
    docker-compose up -d
    sleep 5
fi

# Show reload status if enabled
if [ "$RELOAD" = "--reload" ]; then
    echo -e "${YELLOW}Hot reload enabled (development mode)${NC}"
    RELOAD="--reload --reload-exclude 'docs/*' --reload-exclude 'site/*' --reload-exclude '.cache/*'"
fi

echo -e "\n${GREEN}Starting API server...${NC}"
echo -e "${BLUE}API docs:${NC}     http://localhost:$PORT/docs"
echo -e "${BLUE}Health:${NC}       http://localhost:$PORT/health"
echo -e "${BLUE}Root info:${NC}    http://localhost:$PORT/"

echo -e "\n${YELLOW}Press Ctrl+C to stop${NC}\n"

python -m uvicorn src.api.main:app --host 0.0.0.0 --port $PORT $RELOAD
