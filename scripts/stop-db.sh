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
fi

# Show usage and require confirmation
if [ "$AUTO_CONFIRM" = false ]; then
    echo -e "${BLUE}🐘 Stop PostgreSQL Database${NC}"
    echo "============================"
    echo ""
    echo -e "${YELLOW}What this does:${NC}"
    echo "  • Performs graceful shutdown of PostgreSQL container"
    echo "  • All data is preserved in Docker volume"
    echo "  • Can be restarted with ./scripts/start-db.sh"
    echo ""
    echo -e "${GRAY}Usage:${NC}"
    echo "  $0 -y          # Stop database (skip confirmation)"
    echo "  $0 --yes       # Stop database (skip confirmation)"
    echo ""

    # Check if database is even running
    if ! docker ps --format '{{.Names}}' | grep -q knowledge-graph-postgres; then
        echo -e "${YELLOW}Database is not running${NC}"
        exit 0
    fi

    read -p "$(echo -e ${YELLOW}Stop database now? [y/N]:${NC} )" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Cancelled${NC}"
        exit 0
    fi
fi

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
