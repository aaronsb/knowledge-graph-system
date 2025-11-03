#!/bin/bash
# ============================================================================
# Stop Knowledge Graph Database
# ============================================================================
# Stops PostgreSQL + Apache AGE Docker container
# Data is persisted in Docker volume (use docker-compose down -v to wipe)
# ============================================================================

set -e

# Colors for output
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

# Project root (two levels up from scripts/database/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo ""
echo -e "${BOLD}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Knowledge Graph System - Database Shutdown         ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗${NC} docker-compose not found"
    exit 1
fi

# Check if database is running
if ! docker ps --format '{{.Names}}' | grep -q "knowledge-graph-postgres"; then
    echo -e "${YELLOW}⚠${NC}  Database is not running"
    echo ""
    exit 0
fi

echo -e "${BLUE}→${NC} Stopping database container..."
cd "$PROJECT_ROOT"
docker-compose down

echo ""
echo -e "${GREEN}✓${NC} Database stopped"
echo ""
echo -e "${BOLD}Note:${NC} Data is persisted in Docker volume"
echo -e "  Restart: ${BLUE}./scripts/database/start-database.sh${NC}"
echo -e "  Wipe data: ${BLUE}docker-compose down -v${NC}"
echo ""
