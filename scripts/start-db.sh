#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🐘 PostgreSQL + Apache AGE Database${NC}"
echo "===================================="

# Check if container exists
if docker ps -a --format '{{.Names}}' | grep -q knowledge-graph-postgres; then
    # Check if it's running
    if docker ps --format '{{.Names}}' | grep -q knowledge-graph-postgres; then
        echo -e "${GREEN}✓ Database is already running${NC}"
    else
        echo -e "${YELLOW}Starting existing database container...${NC}"
        docker start knowledge-graph-postgres
        sleep 3
    fi
else
    echo -e "${YELLOW}Creating and starting database container...${NC}"
    docker-compose up -d postgres
    sleep 5
fi

# Wait for healthy status
echo -e "${YELLOW}Waiting for database to be ready...${NC}"
for i in {1..30}; do
    if docker exec knowledge-graph-postgres pg_isready -U admin -d knowledge_graph > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Database is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ Database failed to become ready${NC}"
        exit 1
    fi
    sleep 1
done

# Show database info
echo ""
echo -e "${BLUE}Database Connection:${NC}"
echo -e "  Host:     localhost"
echo -e "  Port:     5432"
echo -e "  Database: knowledge_graph"
echo -e "  User:     admin"

echo ""
echo -e "${BLUE}Performance Settings:${NC}"
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT
  'max_parallel_workers_per_gather' as setting,
  setting as value
FROM pg_settings WHERE name = 'max_parallel_workers_per_gather'
UNION ALL
SELECT 'max_parallel_workers', setting FROM pg_settings WHERE name = 'max_parallel_workers'
UNION ALL
SELECT 'shared_buffers', pg_size_pretty((setting::bigint * 8192)::bigint) FROM pg_settings WHERE name = 'shared_buffers'
UNION ALL
SELECT 'work_mem', pg_size_pretty((setting::bigint * 1024)::bigint) FROM pg_settings WHERE name = 'work_mem'
" -t

echo ""
echo -e "${GREEN}✓ Database started successfully${NC}"
echo -e "${YELLOW}Monitor with:${NC}     ./scripts/monitor-db.sh"
echo -e "${YELLOW}Stop with:${NC}        ./scripts/stop-db.sh"
