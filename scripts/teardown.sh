#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🛑 Knowledge Graph System - Teardown"
echo "===================================="

# Check if containers are running
if ! docker ps --format '{{.Names}}' | grep -q neo4j-kg; then
    echo -e "${YELLOW}⚠ No running containers found${NC}"
else
    echo -e "\n${YELLOW}Stopping Docker containers...${NC}"
    docker-compose down
    echo -e "${GREEN}✓ Containers stopped${NC}"
fi

# Ask about data preservation
echo -e "\n${YELLOW}What would you like to do with the data?${NC}"
echo "1. Keep data (preserve Neo4j database volume)"
echo "2. Delete data (remove all graph data)"
read -p "Enter choice [1/2]: " choice

case $choice in
    2)
        echo -e "\n${YELLOW}Removing Docker volumes...${NC}"
        docker volume rm knowledge-graph-system_neo4j_data 2>/dev/null || true
        docker volume rm knowledge-graph-system_neo4j_logs 2>/dev/null || true
        echo -e "${GREEN}✓ Data volumes removed${NC}"
        ;;
    *)
        echo -e "${GREEN}✓ Data preserved${NC}"
        ;;
esac

# Ask about Python environment
echo -e "\n${YELLOW}Remove Python virtual environment?${NC}"
read -p "Enter choice [y/N]: " remove_venv

if [[ $remove_venv =~ ^[Yy]$ ]]; then
    if [ -d "venv" ]; then
        rm -rf venv
        echo -e "${GREEN}✓ Python virtual environment removed${NC}"
    fi
fi

# Ask about node_modules
echo -e "\n${YELLOW}Remove Node.js dependencies (node_modules)?${NC}"
read -p "Enter choice [y/N]: " remove_node

if [[ $remove_node =~ ^[Yy]$ ]]; then
    if [ -d "mcp-server/node_modules" ]; then
        rm -rf mcp-server/node_modules
        echo -e "${GREEN}✓ Node modules removed${NC}"
    fi
    if [ -d "mcp-server/build" ]; then
        rm -rf mcp-server/build
        echo -e "${GREEN}✓ Build artifacts removed${NC}"
    fi
fi

echo -e "\n${GREEN}✅ Teardown complete${NC}"
echo -e "${YELLOW}Note: Your .env file and source code remain intact${NC}"
