#!/bin/bash

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

if [ $# -eq 0 ]; then
    echo -e "${BLUE}Query Explain Tool${NC}"
    echo "Usage: $0 \"<your cypher query>\""
    echo ""
    echo "Examples:"
    echo "  $0 \"MATCH (c:Concept) RETURN c LIMIT 100\""
    echo "  $0 \"MATCH (c:Concept)-[r]->(c2:Concept) RETURN c, r, c2 LIMIT 50\""
    echo ""
    exit 1
fi

QUERY="$1"

echo -e "${BLUE}🔍 Query Analysis${NC}"
echo -e "${CYAN}================================${NC}"
echo ""

# Check if database is running
if ! docker ps --format '{{.Names}}' | grep -q knowledge-graph-postgres; then
    echo -e "${RED}✗ Database is not running${NC}"
    exit 1
fi

echo -e "${YELLOW}Query:${NC} $QUERY"
echo ""
echo -e "${BLUE}Execution Plan (with parallelism info):${NC}"
echo ""

# Execute EXPLAIN for the cypher query
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT * FROM cypher('knowledge_graph', \$\$
${QUERY}
\$\$) as (result agtype);
" 2>&1

echo ""
echo -e "${BLUE}Checking for parallel execution:${NC}"
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
EXPLAIN SELECT * FROM cypher('knowledge_graph', \$\$
${QUERY}
\$\$) as (result agtype);
" 2>&1 | grep -iE "(parallel|workers|gather)" && echo -e "${GREEN}✓ Parallel execution available${NC}" || echo -e "${YELLOW}✗ No parallel execution (see reasons below)${NC}"

echo ""
echo -e "${BLUE}Current parallel settings:${NC}"
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT name, setting, unit
FROM pg_settings
WHERE name IN (
  'max_parallel_workers_per_gather',
  'parallel_setup_cost',
  'parallel_tuple_cost',
  'min_parallel_table_scan_size',
  'min_parallel_index_scan_size'
)
ORDER BY name;
"

echo ""
echo -e "${BLUE}Graph statistics:${NC}"
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT
  schemaname,
  relname as tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname)) as total_size,
  n_live_tup as rows,
  n_dead_tup as dead_rows
FROM pg_stat_user_tables
WHERE relname LIKE '%concept%' OR relname LIKE '%_vertex%' OR relname LIKE '%_edge%'
ORDER BY pg_total_relation_size(schemaname||'.'||relname) DESC
LIMIT 10;
"

echo ""
echo -e "${CYAN}================================${NC}"
echo -e "${BLUE}Why might parallelism NOT be used?${NC}"
echo ""
echo -e "  1. ${YELLOW}LIMIT clause${NC} - Small limits disable parallelism"
echo -e "  2. ${YELLOW}Table too small${NC} - Must be >8MB (see total_size above)"
echo -e "  3. ${YELLOW}Query too simple${NC} - Overhead exceeds benefit"
echo -e "  4. ${YELLOW}Apache AGE specifics${NC} - Cypher queries may use custom execution paths"
echo -e "  5. ${YELLOW}Cost threshold${NC} - Query cost must exceed parallel_setup_cost (100)"
echo ""
echo -e "${BLUE}Try queries without LIMIT or with complex joins/aggregations${NC}"
echo ""
