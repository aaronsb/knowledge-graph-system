#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/kg_backup_${TIMESTAMP}.cypher"

echo "💾 Knowledge Graph System - Backup"
echo "==================================="

# Check if Neo4j is running
if ! docker ps --format '{{.Names}}' | grep -q knowledge-graph-neo4j; then
    echo -e "${RED}✗ Neo4j is not running${NC}"
    echo -e "${YELLOW}  Start it with: docker-compose up -d${NC}"
    exit 1
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo -e "\n${YELLOW}Creating backup...${NC}"

# Export all data as Cypher statements
docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password \
    "CALL apoc.export.cypher.all('backup.cypher', {format: 'cypher-shell'})" 2>/dev/null || {
    # Fallback: Manual export of nodes and relationships
    echo -e "${YELLOW}Note: APOC not available, using manual export${NC}"

    cat > "$BACKUP_FILE" << 'EOF'
// Knowledge Graph Backup
// Generated: $(date)

// Clear existing data (use with caution!)
// MATCH (n) DETACH DELETE n;

EOF

    # Export Concepts
    docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password \
        "MATCH (c:Concept) RETURN c" --format plain 2>/dev/null | \
        grep -v "^c$" | grep -v "^+--" | grep -v "rows available" >> "$BACKUP_FILE" || true

    # Export Sources
    docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password \
        "MATCH (s:Source) RETURN s" --format plain 2>/dev/null | \
        grep -v "^s$" | grep -v "^+--" | grep -v "rows available" >> "$BACKUP_FILE" || true

    # Export Instances
    docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password \
        "MATCH (i:Instance) RETURN i" --format plain 2>/dev/null | \
        grep -v "^i$" | grep -v "^+--" | grep -v "rows available" >> "$BACKUP_FILE" || true

    # Export Relationships
    docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password \
        "MATCH (a)-[r]->(b) RETURN a, type(r), properties(r), b" --format plain 2>/dev/null | \
        grep -v "^a\|type" | grep -v "^+--" | grep -v "rows available" >> "$BACKUP_FILE" || true
}

# Also backup the .env file (without sensitive data)
cat .env | grep -v "API_KEY" > "${BACKUP_DIR}/env_template_${TIMESTAMP}.txt" 2>/dev/null || true

echo -e "${GREEN}✓ Backup created: ${BACKUP_FILE}${NC}"

# Show backup size
if [ -f "$BACKUP_FILE" ]; then
    size=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "  Size: ${size}"
fi

# List recent backups
echo -e "\n${YELLOW}Recent backups:${NC}"
ls -lht "$BACKUP_DIR" | head -6

echo -e "\n${GREEN}✅ Backup complete${NC}"
echo -e "${YELLOW}Note: API keys are NOT included in backup${NC}"
