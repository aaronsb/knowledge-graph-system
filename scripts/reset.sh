#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔄 Knowledge Graph System - Reset"
echo "================================="

echo -e "${RED}WARNING: This will delete ALL graph data!${NC}"
echo "This operation will:"
echo "  - Stop all containers"
echo "  - Delete the Neo4j database"
echo "  - Restart with a clean database"
echo ""
read -p "Are you sure you want to continue? [y/N]: " confirm

if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Reset cancelled${NC}"
    exit 0
fi

# Stop containers
echo -e "\n${YELLOW}Stopping containers...${NC}"
docker-compose down
echo -e "${GREEN}✓ Containers stopped${NC}"

# Remove volumes
echo -e "\n${YELLOW}Removing database volumes...${NC}"
docker volume rm knowledge-graph-system_neo4j_data 2>/dev/null || true
docker volume rm knowledge-graph-system_neo4j_logs 2>/dev/null || true
echo -e "${GREEN}✓ Database volumes removed${NC}"

# Restart containers
echo -e "\n${YELLOW}Starting fresh database...${NC}"
docker-compose up -d

# Wait for Neo4j to be ready
echo -e "${YELLOW}Waiting for Neo4j to be ready...${NC}"
max_attempts=30
attempt=0
until docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password "RETURN 1" &> /dev/null || [ $attempt -eq $max_attempts ]; do
    echo -n "."
    sleep 2
    ((attempt++))
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "\n${RED}✗ Neo4j failed to start${NC}"
    exit 1
fi
echo -e "\n${GREEN}✓ Neo4j is ready${NC}"

# Initialize schema
echo -e "\n${YELLOW}Initializing fresh schema...${NC}"
docker exec -i knowledge-graph-neo4j cypher-shell -u neo4j -p password < schema/init.cypher
echo -e "${GREEN}✓ Schema initialized${NC}"

echo -e "\n${GREEN}✅ Reset complete!${NC}"
echo -e "${YELLOW}Database is now empty and ready for fresh data${NC}"
echo ""
echo "To ingest documents:"
echo "  source venv/bin/activate"
echo "  python ingest/ingest.py docs/watts_lecture_1.txt --document-name \"Watts Doc 1\""
