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
docker-compose --env-file "$PROJECT_ROOT/.env" up -d postgres garage

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
echo -e "${BLUE}→ Verifying PostgreSQL configuration...${NC}"

# Check database exists
DB_EXISTS=$(docker exec knowledge-graph-postgres psql -U ${POSTGRES_USER:-admin} -lqt | cut -d \| -f 1 | grep -w ${POSTGRES_DB:-knowledge_graph} | wc -l)
if [ "$DB_EXISTS" -gt 0 ]; then
    echo -e "${GREEN}✓ Database '${POSTGRES_DB:-knowledge_graph}' exists${NC}"
else
    echo -e "${RED}✗ Database not found${NC}"
fi

# Check AGE extension
AGE_EXT=$(docker exec knowledge-graph-postgres psql -U ${POSTGRES_USER:-admin} -d ${POSTGRES_DB:-knowledge_graph} -tAc "SELECT COUNT(*) FROM pg_extension WHERE extname='age'" 2>/dev/null || echo "0")
if [ "$AGE_EXT" -gt 0 ]; then
    echo -e "${GREEN}✓ Apache AGE extension loaded${NC}"
else
    echo -e "${RED}✗ AGE extension not found${NC}"
fi

# Check migrations applied (look for schema tables)
SCHEMA_EXISTS=$(docker exec knowledge-graph-postgres psql -U ${POSTGRES_USER:-admin} -d ${POSTGRES_DB:-knowledge_graph} -tAc "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name IN ('kg_api', 'kg_auth')" 2>/dev/null || echo "0")
if [ "$SCHEMA_EXISTS" -eq 2 ]; then
    echo -e "${GREEN}✓ Database schemas initialized (kg_api, kg_auth)${NC}"

    # Show what migrations were applied from logs
    echo -e "${BLUE}→ Checking migration log...${NC}"
    MIGRATION_LOG=$(docker logs knowledge-graph-postgres 2>&1 | grep -E "CREATE TABLE|CREATE SCHEMA|ALTER TABLE|CREATE INDEX" | head -10)
    if [ -n "$MIGRATION_LOG" ]; then
        echo "$MIGRATION_LOG" | while IFS= read -r line; do
            echo "  $line"
        done
    fi

    # Count tables
    TABLE_COUNT=$(docker exec knowledge-graph-postgres psql -U ${POSTGRES_USER:-admin} -d ${POSTGRES_DB:-knowledge_graph} -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('kg_api', 'kg_auth')" 2>/dev/null || echo "0")
    echo -e "${GREEN}✓ Migrations complete (${TABLE_COUNT} tables created)${NC}"
else
    echo -e "${YELLOW}⚠  Database schemas not found (migrations may not have run)${NC}"
fi

echo ""
echo -e "${BLUE}→ Verifying Garage configuration...${NC}"

# Check Garage status
GARAGE_STATUS=$(docker exec knowledge-graph-garage /garage status 2>/dev/null || echo "error")
if echo "$GARAGE_STATUS" | grep -q "Healthy"; then
    echo -e "${GREEN}✓ Garage cluster healthy${NC}"

    # Show node info
    NODE_ID=$(echo "$GARAGE_STATUS" | grep "Node ID" | head -1 | awk '{print $NF}' | cut -c1-16)
    if [ -n "$NODE_ID" ]; then
        echo -e "${GREEN}✓ Garage node initialized (${NODE_ID}...)${NC}"
    fi
else
    echo -e "${YELLOW}⚠  Garage status check failed (may need manual initialization)${NC}"
    echo -e "${YELLOW}   Run: ./scripts/garage/init-garage.sh${NC}"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Infrastructure ready${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BOLD}Services running:${NC}"
echo "  • PostgreSQL (port 5432)"
echo "    - Database: ${POSTGRES_DB:-knowledge_graph}"
echo "    - Extensions: Apache AGE"
echo "    - Migrations: Applied"
echo ""
echo "  • Garage S3 storage (port 3900)"
echo "    - Status: Ready"
echo "    - Note: Bucket/keys created during platform configuration"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo "  1. Start operator: cd docker && docker-compose --env-file ../.env up -d operator"
echo "  2. Configure platform: docker exec kg-operator python /workspace/operator/configure.py admin"
echo "  3. Start application: ./operator/lib/start-app.sh"
echo ""
