#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'
DIM='\033[2m'

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

POSTGRES_USER="${POSTGRES_USER:-admin}"
POSTGRES_DB="${POSTGRES_DB:-knowledge_graph}"
CONTAINER_NAME="knowledge-graph-postgres"

echo -e "${BLUE}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║      Knowledge Graph System - Database Table Report       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if PostgreSQL is running
echo -e "${BLUE}→${NC} Checking PostgreSQL connection..."
if ! docker exec $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${RED}✗ PostgreSQL is not running${NC}"
    echo -e "${YELLOW}  Run: docker-compose up -d${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} PostgreSQL is running"
echo ""

# Get PostgreSQL version
PG_VERSION=$(docker exec $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT version();" | head -1 | xargs)
echo -e "${DIM}Database: ${POSTGRES_DB}${NC}"
echo -e "${DIM}Version:  ${PG_VERSION}${NC}"
echo ""

# ============================================================================
# Apache AGE Graph Schema
# ============================================================================
echo -e "${BLUE}${BOLD}═══ Apache AGE Graph (ag_catalog) ═══${NC}"
echo ""

# Check if AGE graph exists
GRAPH_EXISTS=$(docker exec $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c \
    "SELECT COUNT(*) FROM ag_catalog.ag_graph WHERE name = 'knowledge_graph';" | xargs)

if [ "$GRAPH_EXISTS" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Graph: ${BOLD}knowledge_graph${NC}"

    # Get node counts by label
    echo -e "\n${BOLD}Graph Nodes:${NC}"
    NODE_COUNTS=$(docker exec $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "
        SELECT
            COALESCE(SUM(CASE WHEN label_name = 'Concept' THEN 1 ELSE 0 END), 0) as concepts,
            COALESCE(SUM(CASE WHEN label_name = 'Source' THEN 1 ELSE 0 END), 0) as sources,
            COALESCE(SUM(CASE WHEN label_name = 'Instance' THEN 1 ELSE 0 END), 0) as instances,
            COUNT(*) as total
        FROM (
            SELECT tablename as label_name
            FROM pg_tables
            WHERE schemaname = 'knowledge_graph'
            AND tablename LIKE '%_vertex'
        ) t;
    " 2>/dev/null || echo "0|0|0|0")

    # Get total node count via Cypher (more accurate)
    TOTAL_NODES=$(docker exec $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "
        LOAD 'age';
        SET search_path = ag_catalog, \"\$user\", public;
        SELECT count FROM cypher('knowledge_graph', \$\$
            MATCH (n)
            RETURN count(n) as count
        \$\$) as (count agtype);
    " 2>/dev/null | grep -E '^[[:space:]]*[0-9]+' | xargs || echo "0")

    # Get edge count
    TOTAL_EDGES=$(docker exec $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "
        LOAD 'age';
        SET search_path = ag_catalog, \"\$user\", public;
        SELECT count FROM cypher('knowledge_graph', \$\$
            MATCH ()-[r]->()
            RETURN count(r) as count
        \$\$) as (count agtype);
    " 2>/dev/null | grep -E '^[[:space:]]*[0-9]+' | xargs || echo "0")

    echo -e "  Total Nodes: ${YELLOW}${TOTAL_NODES}${NC}"
    echo -e "  Total Edges: ${YELLOW}${TOTAL_EDGES}${NC}"
else
    echo -e "${RED}✗${NC} No AGE graph found"
fi

echo ""

# ============================================================================
# Application Schemas (kg_api, kg_auth, kg_logs)
# ============================================================================

for SCHEMA in kg_api kg_auth kg_logs; do
    echo -e "${BLUE}${BOLD}═══ Schema: ${SCHEMA} ═══${NC}"
    echo ""

    # Get table list with row counts
    TABLES=$(docker exec $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "
        SELECT
            schemaname || '.' || relname as full_name,
            relname,
            n_live_tup as row_count
        FROM pg_stat_user_tables
        WHERE schemaname = '$SCHEMA'
        ORDER BY relname;
    ")

    if [ -z "$TABLES" ]; then
        echo -e "${DIM}  (no tables)${NC}"
    else
        printf "${BOLD}%-40s %12s${NC}\n" "Table" "Rows"
        echo "────────────────────────────────────────────────────────"

        while IFS='|' read -r full_name table_name row_count; do
            # Trim whitespace
            full_name=$(echo "$full_name" | xargs)
            table_name=$(echo "$table_name" | xargs)
            row_count=$(echo "$row_count" | xargs)

            # Color code based on row count
            if [ "$row_count" -eq 0 ]; then
                COLOR=$DIM
            elif [ "$row_count" -lt 10 ]; then
                COLOR=$YELLOW
            else
                COLOR=$GREEN
            fi

            printf "%-40s ${COLOR}%12s${NC}\n" "$table_name" "$row_count"
        done <<< "$TABLES"
    fi

    echo ""
done

# ============================================================================
# Summary Statistics
# ============================================================================
echo -e "${BLUE}${BOLD}═══ Summary ═══${NC}"
echo ""

# Total tables
TOTAL_TABLES=$(docker exec $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "
    SELECT COUNT(*)
    FROM information_schema.tables
    WHERE table_schema IN ('kg_api', 'kg_auth', 'kg_logs')
    AND table_type = 'BASE TABLE';
" | xargs)

# Total rows across all tables
TOTAL_ROWS=$(docker exec $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "
    SELECT COALESCE(SUM(n_live_tup), 0)
    FROM pg_stat_user_tables
    WHERE schemaname IN ('kg_api', 'kg_auth', 'kg_logs');
" | xargs)

# Database size
DB_SIZE=$(docker exec $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "
    SELECT pg_size_pretty(pg_database_size('$POSTGRES_DB'));
" | xargs)

echo -e "  Application Tables: ${YELLOW}${TOTAL_TABLES}${NC}"
echo -e "  Total Rows:         ${YELLOW}${TOTAL_ROWS}${NC}"
echo -e "  Graph Nodes:        ${YELLOW}${TOTAL_NODES}${NC}"
echo -e "  Graph Edges:        ${YELLOW}${TOTAL_EDGES}${NC}"
echo -e "  Database Size:      ${YELLOW}${DB_SIZE}${NC}"
echo ""

# ============================================================================
# Health Checks
# ============================================================================
echo -e "${BLUE}${BOLD}═══ Health Status ═══${NC}"
echo ""

# Check if critical tables exist
CRITICAL_TABLES="kg_auth.users kg_auth.api_keys kg_auth.roles kg_api.ingestion_jobs kg_api.sessions"
MISSING_TABLES=""

for TABLE in $CRITICAL_TABLES; do
    SCHEMA=$(echo $TABLE | cut -d. -f1)
    TABLE_NAME=$(echo $TABLE | cut -d. -f2)

    EXISTS=$(docker exec $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = '$SCHEMA'
        AND table_name = '$TABLE_NAME';
    " | xargs)

    if [ "$EXISTS" -eq 0 ]; then
        MISSING_TABLES="$MISSING_TABLES $TABLE"
    fi
done

if [ -z "$MISSING_TABLES" ]; then
    echo -e "${GREEN}✓${NC} All critical tables exist"
else
    echo -e "${RED}✗${NC} Missing tables:${MISSING_TABLES}"
fi

# Check if AGE graph is operational
AGE_TEST=$(docker exec $CONTAINER_NAME psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "
    LOAD 'age';
    SET search_path = ag_catalog, \"\$user\", public;
    SELECT result FROM cypher('knowledge_graph', \$\$ RETURN 1 \$\$) as (result agtype);
" 2>/dev/null | grep -E '^[[:space:]]*1' | xargs || echo "0")

if [ "$AGE_TEST" = "1" ]; then
    echo -e "${GREEN}✓${NC} AGE graph is operational"
else
    echo -e "${RED}✗${NC} AGE graph is not operational"
fi

echo ""
echo -e "${DIM}Report generated at: $(date)${NC}"
echo ""
