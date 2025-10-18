#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m'

# Check for -y/--yes flag
AUTO_CONFIRM=false
if [ "$1" = "-y" ] || [ "$1" = "--yes" ]; then
    AUTO_CONFIRM=true
    shift
fi

# Parse port argument
PORT=${1:-3000}

# Show usage and require confirmation
if [ "$AUTO_CONFIRM" = false ]; then
    echo -e "${BLUE}🎨 Start Knowledge Graph Visualization Explorer${NC}"
    echo "=================================================="
    echo ""
    echo -e "${YELLOW}What this does:${NC}"
    echo "  • Starts React/Vite dev server in foreground"
    echo "  • Requires API server on port 8000 (checks automatically)"
    echo "  • Listens on http://localhost:$PORT"
    echo "  • Press Ctrl+C to stop"
    echo ""
    echo -e "${GRAY}Usage:${NC}"
    echo "  $0 -y              # Start on port 3000 (skip confirmation)"
    echo "  $0 -y 3001         # Start on custom port"
    echo ""
    echo -e "${GRAY}What you get:${NC}"
    echo "  • Interactive graph visualization (2D/3D/VR)"
    echo "  • Smart search with semantic similarity"
    echo "  • Visual query builder (drag-and-drop blocks)"
    echo "  • Direct openCypher editor"
    echo ""
    read -p "$(echo -e ${YELLOW}Start visualization explorer now? [y/N]:${NC} )" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Cancelled${NC}"
        exit 0
    fi
fi

echo -e "${BLUE}🎨 Knowledge Graph Visualization Explorer${NC}"
echo "=========================================="

# Check if API server is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ API server not detected on port 8000${NC}"
    echo -e "${YELLOW}  The visualization app requires the API server to be running${NC}"
    echo -e "${YELLOW}  Start it with: ./scripts/start-api.sh -y${NC}"
    echo ""

    # If -y flag was used, just warn and continue
    if [ "$AUTO_CONFIRM" = true ]; then
        echo -e "${YELLOW}  Continuing anyway (--yes flag used)${NC}"
        echo ""
    else
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Generate log file name with date
LOG_FILE="logs/viz_$(date +%Y%m%d).log"

# Check node_modules
cd viz-app
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠ Dependencies not installed${NC}"
    echo -e "${YELLOW}  Installing dependencies...${NC}"
    npm install
fi

# Parse arguments
PORT=${1:-3000}

echo -e "\n${GREEN}Starting Visualization Explorer...${NC}"
echo -e "${BLUE}Viz App:${NC}      http://localhost:$PORT"
echo -e "${BLUE}API Server:${NC}   http://localhost:8000"
echo -e "${BLUE}Logs:${NC}         ../$LOG_FILE"

echo -e "\n${YELLOW}Press Ctrl+C to stop${NC}\n"

# Log startup
{
    echo "================================================================================"
    echo "Visualization Explorer Started - $(date)"
    echo "Port: $PORT"
    echo "================================================================================"
} >> "../$LOG_FILE"

# Run with output to both console and log file
npm run dev -- --port $PORT --host 0.0.0.0 2>&1 | tee -a "../$LOG_FILE"
