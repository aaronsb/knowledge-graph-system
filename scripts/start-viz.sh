#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🎨 Knowledge Graph Visualization Explorer${NC}"
echo "=========================================="

# Check if API server is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ API server not detected on port 8000${NC}"
    echo -e "${YELLOW}  The visualization app requires the API server to be running${NC}"
    echo -e "${YELLOW}  Start it with: ./scripts/start-api.sh${NC}"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
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
