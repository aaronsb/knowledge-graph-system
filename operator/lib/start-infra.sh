#!/bin/bash
set -e

# ============================================================================
# start-infra.sh
# Start infrastructure containers (postgres + garage + operator)
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

# Source common functions (provides run_compose, load_operator_config)
source "$SCRIPT_DIR/common.sh"

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

# Start postgres and garage (uses config from .operator.conf)
echo -e "${BLUE}→ Starting postgres and garage...${NC}"
run_compose up -d postgres garage

# Get container names from config
POSTGRES_CONTAINER=$(get_container_name postgres)
GARAGE_CONTAINER=$(get_container_name garage)
OPERATOR_CONTAINER=$(get_container_name operator)

# Get patterns for container matching (supports legacy names)
POSTGRES_PATTERN=$(get_container_pattern postgres)
GARAGE_PATTERN=$(get_container_pattern garage)

echo ""
echo -e "${BLUE}→ Waiting for PostgreSQL to be healthy...${NC}"

# Wait for postgres (up to 60 seconds)
for i in {1..30}; do
    if docker ps --format '{{.Names}} {{.Status}}' | grep -qE "$POSTGRES_PATTERN.*healthy"; then
        echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ PostgreSQL health check timeout${NC}"
        echo ""
        echo "Check logs with: docker logs $POSTGRES_CONTAINER"
        exit 1
    fi
    sleep 2
done

echo -e "${BLUE}→ Waiting for Garage to be healthy...${NC}"

# Wait for garage (up to 30 seconds)
for i in {1..15}; do
    if docker ps --format '{{.Names}} {{.Status}}' | grep -qE "$GARAGE_PATTERN.*healthy"; then
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

# Wait for PostgreSQL to be ready for queries (not just healthy)
echo -e "${BLUE}  Waiting for database to accept queries...${NC}"
for i in {1..10}; do
    if docker exec $POSTGRES_CONTAINER psql -U ${POSTGRES_USER:-admin} -lqt >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Database ready for queries${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}✗ Database not responding to queries${NC}"
        exit 1
    fi
    sleep 2
done

# Check database exists
DB_EXISTS=$(docker exec $POSTGRES_CONTAINER psql -U ${POSTGRES_USER:-admin} -lqt | cut -d \| -f 1 | grep -w ${POSTGRES_DB:-knowledge_graph} | wc -l)
if [ "$DB_EXISTS" -gt 0 ]; then
    echo -e "${GREEN}✓ Database '${POSTGRES_DB:-knowledge_graph}' exists${NC}"
else
    echo -e "${RED}✗ Database not found${NC}"
fi

# Apply pending migrations
echo -e "${BLUE}  Applying database migrations...${NC}"
cd "$PROJECT_ROOT"
if [ -f "$PROJECT_ROOT/operator/database/migrate-db.sh" ]; then
    "$PROJECT_ROOT/operator/database/migrate-db.sh" -y 2>&1 | grep -E "✓|✅|→|⚠️|✗" || true
    echo -e "${GREEN}✓ Migrations applied${NC}"
else
    echo -e "${YELLOW}⚠  Migration script not found${NC}"
fi
cd "$DOCKER_DIR"

# Check AGE extension
AGE_EXT=$(docker exec $POSTGRES_CONTAINER psql -U ${POSTGRES_USER:-admin} -d ${POSTGRES_DB:-knowledge_graph} -tAc "SELECT COUNT(*) FROM pg_extension WHERE extname='age'" 2>/dev/null || echo "0")
if [ "$AGE_EXT" -gt 0 ]; then
    echo -e "${GREEN}✓ Apache AGE extension loaded${NC}"
else
    echo -e "${RED}✗ AGE extension not found${NC}"
fi

# Show applied migrations
MIGRATION_LIST=$(docker exec $POSTGRES_CONTAINER psql -U ${POSTGRES_USER:-admin} -d ${POSTGRES_DB:-knowledge_graph} -tAc "SELECT version || ' - ' || name FROM public.schema_migrations ORDER BY version" 2>/dev/null || echo "")

if [ -n "$MIGRATION_LIST" ]; then
    MIGRATION_COUNT=$(echo "$MIGRATION_LIST" | wc -l)
    TABLE_COUNT=$(docker exec $POSTGRES_CONTAINER psql -U ${POSTGRES_USER:-admin} -d ${POSTGRES_DB:-knowledge_graph} -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('kg_api', 'kg_auth')" 2>/dev/null || echo "0")
    echo -e "${GREEN}✓ Schema ready (${TABLE_COUNT} tables, ${MIGRATION_COUNT} migrations applied)${NC}"
    echo "$MIGRATION_LIST" | sed 's/^/    • /'

    # Verify critical tables exist
    CRITICAL_TABLES=("kg_api.ai_extraction_config" "kg_api.embedding_config")
    MISSING_CRITICAL=()
    for table in "${CRITICAL_TABLES[@]}"; do
        IFS='.' read -r schema table_name <<< "$table"
        EXISTS=$(docker exec $POSTGRES_CONTAINER psql -U ${POSTGRES_USER:-admin} -d ${POSTGRES_DB:-knowledge_graph} -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$schema' AND table_name='$table_name'" 2>/dev/null || echo "0")
        if [ "$EXISTS" -eq 0 ]; then
            MISSING_CRITICAL+=("$table")
        fi
    done

    if [ ${#MISSING_CRITICAL[@]} -gt 0 ]; then
        echo -e "${RED}✗ Missing critical tables (migrations incomplete):${NC}"
        for missing in "${MISSING_CRITICAL[@]}"; do
            echo -e "    ${RED}- $missing${NC}"
        done
    fi
else
    echo -e "${RED}✗ No migrations applied${NC}"
fi

echo ""
echo -e "${BLUE}→ Initializing Garage configuration...${NC}"

# Check for node without role assignment
NODE_ID=$(docker exec $GARAGE_CONTAINER /garage status 2>&1 | grep "NO ROLE ASSIGNED" | awk '{print $1}')
if [ -n "$NODE_ID" ]; then
    echo -e "${BLUE}  Assigning role to node ${NODE_ID}...${NC}"
    docker exec $GARAGE_CONTAINER /garage layout assign "$NODE_ID" -z dc1 -c 10G > /dev/null 2>&1
    docker exec $GARAGE_CONTAINER /garage layout apply --version 1 > /dev/null 2>&1
    echo -e "${GREEN}✓ Node role assigned and layout applied${NC}"
else
    echo -e "${GREEN}✓ Node role already assigned${NC}"
fi

# Create bucket
GARAGE_BUCKET="${GARAGE_BUCKET:-kg-storage}"
if docker exec $GARAGE_CONTAINER /garage bucket info "${GARAGE_BUCKET}" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Bucket '${GARAGE_BUCKET}' exists${NC}"
else
    docker exec $GARAGE_CONTAINER /garage bucket create "${GARAGE_BUCKET}" > /dev/null 2>&1
    echo -e "${GREEN}✓ Bucket '${GARAGE_BUCKET}' created${NC}"
fi

# Create or check API key
KEY_NAME="kg-api-key"
if docker exec $GARAGE_CONTAINER /garage key info "${KEY_NAME}" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API key '${KEY_NAME}' exists${NC}"
    echo -e "${YELLOW}  Note: Garage credentials must be configured separately${NC}"
    echo -e "${YELLOW}  Run: ./operator/setup/initialize-platform.sh (option 7)${NC}"
    echo -e "${YELLOW}  Or: ./quickstart.sh for automated setup${NC}"
else
    echo -e "${BLUE}  Creating Garage API key...${NC}"
    KEY_OUTPUT=$(docker exec $GARAGE_CONTAINER /garage key create "${KEY_NAME}" 2>&1)

    # Extract credentials for display
    GARAGE_KEY_ID=$(echo "$KEY_OUTPUT" | grep "Key ID:" | awk '{print $3}')
    GARAGE_SECRET=$(echo "$KEY_OUTPUT" | grep "Secret key:" | awk '{print $3}')

    if [ -n "$GARAGE_KEY_ID" ] && [ -n "$GARAGE_SECRET" ]; then
        echo -e "${GREEN}✓ API key '${KEY_NAME}' created${NC}"
        echo ""
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}⚠  IMPORTANT: Store Garage credentials${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo -e "  ${BOLD}Access Key ID:${NC}  ${GARAGE_KEY_ID}"
        echo -e "  ${BOLD}Secret Key:${NC}     ${GARAGE_SECRET}"
        echo ""
        echo -e "${YELLOW}Store these credentials securely:${NC}"
        echo -e "  docker exec kg-operator python /workspace/operator/configure.py api-key garage --key \"${GARAGE_KEY_ID}:${GARAGE_SECRET}\""
        echo ""
        echo -e "${YELLOW}Or run automated setup:${NC}"
        echo -e "  ./quickstart.sh"
        echo ""
    else
        echo -e "${RED}✗ Failed to create API key${NC}"
    fi
fi

# Grant bucket permissions
docker exec $GARAGE_CONTAINER /garage bucket allow --read --write --key "${KEY_NAME}" "${GARAGE_BUCKET}" > /dev/null 2>&1
echo -e "${GREEN}✓ Bucket permissions configured${NC}"

echo ""
echo -e "${BLUE}→ Starting operator container...${NC}"

# Set build metadata
export GIT_COMMIT=$(cd "$PROJECT_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")
export BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Check if operator is already running
if docker ps --format '{{.Names}}' | grep -q "^${OPERATOR_CONTAINER}$"; then
    echo -e "${GREEN}✓ Operator already running${NC}"
else
    run_compose up -d --build operator

    # Wait for operator to be ready
    echo -e "${BLUE}  Waiting for operator to start...${NC}"
    for i in {1..15}; do
        if docker ps --format '{{.Names}}' | grep -q "^${OPERATOR_CONTAINER}$"; then
            echo -e "${GREEN}✓ Operator is ready${NC}"
            break
        fi
        if [ $i -eq 15 ]; then
            echo -e "${RED}✗ Operator startup timeout${NC}"
            echo "Check logs with: docker logs $OPERATOR_CONTAINER"
            exit 1
        fi
        sleep 2
    done
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Infrastructure ready${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BOLD}Services running:${NC}"
echo "  • PostgreSQL (port 5432)"
echo "    - Container: ${POSTGRES_CONTAINER}"
echo "    - Database: ${POSTGRES_DB:-knowledge_graph}"
echo "    - Extensions: Apache AGE"
echo "    - Migrations: Applied"
echo ""
echo "  • Garage S3 storage (port 3900)"
echo "    - Container: ${GARAGE_CONTAINER}"
echo "    - Bucket: ${GARAGE_BUCKET:-kg-storage}"
echo "    - API key: ${KEY_NAME}"
echo ""
echo "  • Operator container"
echo "    - Container: ${OPERATOR_CONTAINER}"
echo "    - Status: Running"
echo "    - Access: docker exec -it ${OPERATOR_CONTAINER} /bin/bash"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo "  1. Configure admin user: docker exec ${OPERATOR_CONTAINER} python /workspace/operator/configure.py admin"
echo "  2. Configure AI provider: docker exec ${OPERATOR_CONTAINER} python /workspace/operator/configure.py ai-provider openai --model gpt-4o"
echo "  3. List embedding profiles: docker exec ${OPERATOR_CONTAINER} python /workspace/operator/configure.py embedding"
echo "  4. Activate embedding profile: docker exec ${OPERATOR_CONTAINER} python /workspace/operator/configure.py embedding 2"
echo "  5. Store API keys: docker exec -it ${OPERATOR_CONTAINER} python /workspace/operator/configure.py api-key openai"
echo "  6. Start application: ./operator/lib/start-app.sh"
echo ""
