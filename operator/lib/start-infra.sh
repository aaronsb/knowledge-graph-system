#!/bin/bash
set -e

# ============================================================================
# start-infra.sh
# Start infrastructure containers (postgres + garage)
# ============================================================================

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get project root (operator/lib -> ../..)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
DOCKER_DIR="$PROJECT_ROOT/docker"

echo -e "${BLUE}Starting infrastructure containers...${NC}"
echo ""

# Check if docker-compose file exists
if [ ! -f "$DOCKER_DIR/docker-compose.yml" ]; then
    echo -e "${RED}✗ docker-compose.yml not found at $DOCKER_DIR${NC}"
    exit 1
fi

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}⚠  .env file not found${NC}"
    echo ""
    echo "Run this first to generate infrastructure secrets:"
    echo "  ./operator/lib/init-secrets.sh --dev"
    echo ""
    exit 1
fi

cd "$DOCKER_DIR"

# Start postgres and garage
echo -e "${BLUE}→ Starting postgres and garage...${NC}"
docker-compose up -d postgres garage

echo ""
echo -e "${BLUE}→ Waiting for PostgreSQL to be healthy...${NC}"

# Wait for postgres (up to 60 seconds)
for i in {1..30}; do
    if docker ps --format '{{.Names}} {{.Status}}' | grep -q "kg-postgres-dev.*healthy\|knowledge-graph-postgres.*healthy"; then
        echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ PostgreSQL health check timeout${NC}"
        echo ""
        echo "Check logs with: docker logs kg-postgres-dev"
        exit 1
    fi
    sleep 2
done

echo -e "${BLUE}→ Waiting for Garage to be healthy...${NC}"

# Wait for garage (up to 30 seconds)
for i in {1..15}; do
    if docker ps --format '{{.Names}} {{.Status}}' | grep -q "kg-garage-dev.*healthy\|knowledge-graph-garage.*healthy"; then
        echo -e "${GREEN}✓ Garage is ready${NC}"
        break
    fi
    if [ $i -eq 15 ]; then
        echo -e "${YELLOW}⚠  Garage health check timeout (continuing anyway)${NC}"
        break
    fi
    sleep 2
done

echo ""
echo -e "${GREEN}✅ Infrastructure ready${NC}"
echo ""
echo "Services running:"
echo "  • PostgreSQL (port 5432)"
echo "  • Garage S3 storage (port 3900)"
echo ""
echo "Next steps:"
echo "  1. Configure platform: ./operator/kg-operator config admin"
echo "  2. Start application: ./operator/lib/start-app.sh"
echo ""
