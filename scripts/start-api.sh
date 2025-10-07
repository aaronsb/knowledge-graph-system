#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Knowledge Graph API Server${NC}"
echo "=============================="

# Check venv
if [ ! -d "venv" ]; then
    echo -e "${RED}✗ Virtual environment not found${NC}"
    echo -e "${YELLOW}  Run: ./scripts/setup.sh${NC}"
    exit 1
fi

# Check Neo4j
if ! docker ps --format '{{.Names}}' | grep -q knowledge-graph-neo4j; then
    echo -e "${YELLOW}⚠ Neo4j is not running${NC}"
    echo -e "${YELLOW}  Starting Neo4j...${NC}"
    docker-compose up -d
    sleep 3
fi

source venv/bin/activate

# Parse arguments
PORT=${1:-8000}
RELOAD=""

if [ "$2" = "--reload" ]; then
    RELOAD="--reload"
    echo -e "${YELLOW}Hot reload enabled (development mode)${NC}"
fi

echo -e "\n${GREEN}Starting API server...${NC}"
echo -e "${BLUE}API docs:${NC}     http://localhost:$PORT/docs"
echo -e "${BLUE}Health:${NC}       http://localhost:$PORT/health"
echo -e "${BLUE}Root info:${NC}    http://localhost:$PORT/"

echo -e "\n${YELLOW}Press Ctrl+C to stop${NC}\n"

python -m uvicorn src.api.main:app --host 0.0.0.0 --port $PORT $RELOAD
