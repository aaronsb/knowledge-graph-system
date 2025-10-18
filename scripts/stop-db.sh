#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🐘 Stopping PostgreSQL Database...${NC}"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q knowledge-graph-postgres; then
    echo -e "${YELLOW}Database is not running${NC}"
    exit 0
fi

# Graceful shutdown
echo -e "${YELLOW}Performing graceful shutdown...${NC}"
docker stop knowledge-graph-postgres

echo -e "${GREEN}✓ Database stopped${NC}"
echo -e "${YELLOW}Start again with:${NC} ./scripts/start-db.sh"
