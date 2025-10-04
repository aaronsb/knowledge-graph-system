#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BACKUP_DIR="backups"

echo "📥 Knowledge Graph System - Restore"
echo "==================================="

# Check if Neo4j is running
if ! docker ps --format '{{.Names}}' | grep -q knowledge-graph-neo4j; then
    echo -e "${RED}✗ Neo4j is not running${NC}"
    echo -e "${YELLOW}  Start it with: docker-compose up -d${NC}"
    exit 1
fi

# List available backups
if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A $BACKUP_DIR/*.cypher 2>/dev/null)" ]; then
    echo -e "${RED}✗ No backups found in $BACKUP_DIR${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Available backups:${NC}"
select backup_file in "$BACKUP_DIR"/*.cypher; do
    if [ -n "$backup_file" ]; then
        break
    fi
done

echo -e "\n${YELLOW}Selected: ${backup_file}${NC}"
echo -e "${RED}WARNING: This will DELETE all current data!${NC}"
read -p "Continue with restore? [y/N]: " confirm

if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Restore cancelled${NC}"
    exit 0
fi

# Clear existing data
echo -e "\n${YELLOW}Clearing existing data...${NC}"
docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password \
    "MATCH (n) DETACH DELETE n" 2>/dev/null
echo -e "${GREEN}✓ Existing data cleared${NC}"

# Restore from backup
echo -e "\n${YELLOW}Restoring data...${NC}"
docker exec -i knowledge-graph-neo4j cypher-shell -u neo4j -p password < "$backup_file"
echo -e "${GREEN}✓ Data restored${NC}"

# Verify restoration
echo -e "\n${YELLOW}Verifying restoration...${NC}"
node_count=$(docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password \
    "MATCH (n) RETURN count(n)" --format plain 2>/dev/null | tail -1)
echo -e "  Nodes restored: ${GREEN}${node_count}${NC}"

rel_count=$(docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password \
    "MATCH ()-[r]->() RETURN count(r)" --format plain 2>/dev/null | tail -1)
echo -e "  Relationships restored: ${GREEN}${rel_count}${NC}"

echo -e "\n${GREEN}✅ Restore complete${NC}"
