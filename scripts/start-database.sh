#!/bin/bash
# ============================================================================
# Start Knowledge Graph Database
# ============================================================================
# Starts PostgreSQL + Apache AGE in Docker container
# On first startup: applies baseline schema + all migrations automatically
# ============================================================================

set -e

# Colors for output
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

# Project root (parent of scripts directory)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo ""
echo -e "${BOLD}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Knowledge Graph System - Database Startup          ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗${NC} docker-compose not found"
    echo -e "  Install: ${BLUE}https://docs.docker.com/compose/install/${NC}"
    exit 1
fi

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}⚠${NC}  No .env file found"
    echo -e "  Copying from .env.example..."
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    echo -e "${GREEN}✓${NC} Created .env file"
    echo ""
fi

# Check if database is already running
if docker ps --format '{{.Names}}' | grep -q "knowledge-graph-postgres"; then
    echo -e "${BLUE}→${NC} Database is already running"
    echo -e "  Container: ${GREEN}knowledge-graph-postgres${NC}"
    echo ""

    # Show status
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' knowledge-graph-postgres 2>/dev/null || echo "unknown")
    if [ "$HEALTH" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Status: ${GREEN}healthy${NC}"
    else
        echo -e "${YELLOW}⚠${NC}  Status: ${YELLOW}$HEALTH${NC}"
        echo -e "  The database may still be initializing..."
    fi
    echo ""
    exit 0
fi

# Start database
echo -e "${BLUE}→${NC} Starting PostgreSQL + Apache AGE..."
cd "$PROJECT_ROOT"
docker-compose up -d

# Wait for container to start
echo -e "${BLUE}→${NC} Waiting for container to start..."
sleep 2

# Wait for database to be healthy
echo -e "${BLUE}→${NC} Waiting for database to initialize..."
echo -e "  ${YELLOW}Note: First startup runs schema + migrations (may take 10-20 seconds)${NC}"

RETRY_COUNT=0
MAX_RETRIES=30  # 30 seconds max wait

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' knowledge-graph-postgres 2>/dev/null || echo "starting")

    if [ "$HEALTH" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} Database is ready!"
        break
    fi

    # Show progress indicator
    echo -ne "  Waiting... ($((RETRY_COUNT + 1))s)\r"
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

echo "" # Clear progress line

if [ "$HEALTH" != "healthy" ]; then
    echo -e "${YELLOW}⚠${NC}  Database health check timeout"
    echo -e "  The database may still be initializing."
    echo -e "  Check logs: ${BLUE}docker logs knowledge-graph-postgres${NC}"
    echo ""
    exit 1
fi

# Check if this was first initialization
FIRST_INIT=$(docker logs knowledge-graph-postgres 2>&1 | grep -c "Baseline Schema Initialization Complete" 2>/dev/null || echo "0")
# Ensure it's a single number (grep -c might return multiple lines in some edge cases)
FIRST_INIT=$(echo "$FIRST_INIT" | head -1 | tr -d ' \n')

# Apply migrations using standard migrate-db.sh script
echo ""
echo -e "${BLUE}→${NC} Applying database migrations..."
if "$PROJECT_ROOT/scripts/migrate-db.sh" -y > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Migrations applied"
else
    echo -e "${YELLOW}⚠${NC}  Migration check completed (may be already applied)"
fi

echo ""
echo -e "${BOLD}Database Status:${NC}"
echo -e "  Container: ${GREEN}knowledge-graph-postgres${NC}"
echo -e "  Status: ${GREEN}healthy${NC}"
echo -e "  Port: ${BLUE}5432${NC}"

if [ "$FIRST_INIT" -gt 0 ]; then
    echo -e "  Schema: ${GREEN}initialized${NC} (baseline + migrations applied)"
else
    echo -e "  Schema: ${BLUE}existing${NC} (using persisted data)"
fi

echo ""
echo -e "${BOLD}Next Steps:${NC}"
echo -e "  1. Start API server: ${BLUE}./scripts/start-api.sh${NC}"
echo -e "  2. Initialize auth: ${BLUE}./scripts/initialize-auth.sh${NC}"
echo -e "  3. Use kg CLI: ${BLUE}kg database stats${NC}"
echo ""
echo -e "${BOLD}Logs:${NC} ${BLUE}docker logs -f knowledge-graph-postgres${NC}"
echo -e "${BOLD}Stop:${NC} ${BLUE}docker-compose down${NC}"
echo ""
