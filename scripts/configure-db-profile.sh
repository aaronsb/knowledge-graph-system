#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m'

PROFILE=$1

show_usage() {
    echo -e "${BLUE}PostgreSQL Resource Profile Configuration${NC}"
    echo "==========================================="
    echo ""
    echo "Usage: $0 <profile>"
    echo ""
    echo -e "${CYAN}Available Profiles:${NC}"
    echo ""
    echo -e "${YELLOW}small${NC}  - Development laptop/workstation"
    echo "  • 8GB RAM, 8 CPU cores"
    echo "  • shared_buffers: 2GB (25% of 8GB)"
    echo "  • work_mem: 32MB"
    echo "  • maintenance_work_mem: 512MB"
    echo "  • effective_cache_size: 6GB (75% of 8GB)"
    echo "  • max_worker_processes: 8"
    echo "  • max_parallel_workers: 4"
    echo "  • max_parallel_workers_per_gather: 2"
    echo ""
    echo -e "${YELLOW}medium${NC} - Production workstation/small server"
    echo "  • 16GB RAM, 16 CPU cores"
    echo "  • shared_buffers: 4GB (25% of 16GB)"
    echo "  • work_mem: 64MB"
    echo "  • maintenance_work_mem: 1GB"
    echo "  • effective_cache_size: 12GB (75% of 16GB)"
    echo "  • max_worker_processes: 16"
    echo "  • max_parallel_workers: 8"
    echo "  • max_parallel_workers_per_gather: 4"
    echo ""
    echo -e "${YELLOW}large${NC}  - Production server/high-performance system"
    echo "  • 32GB+ RAM, 32 CPU cores"
    echo "  • shared_buffers: 8GB (25% of 32GB)"
    echo "  • work_mem: 128MB"
    echo "  • maintenance_work_mem: 2GB"
    echo "  • effective_cache_size: 24GB (75% of 32GB)"
    echo "  • max_worker_processes: 32"
    echo "  • max_parallel_workers: 16"
    echo "  • max_parallel_workers_per_gather: 8"
    echo ""
    echo -e "${GRAY}Note: Container will be restarted to apply changes${NC}"
    echo ""
}

if [ -z "$PROFILE" ]; then
    show_usage
    exit 1
fi

# Check if database container exists
if ! docker ps -a --format '{{.Names}}' | grep -q knowledge-graph-postgres; then
    echo -e "${RED}✗ Database container not found${NC}"
    echo -e "${YELLOW}  Run: ./scripts/start-db.sh${NC}"
    exit 1
fi

# Check if database is running
if ! docker ps --format '{{.Names}}' | grep -q knowledge-graph-postgres; then
    echo -e "${YELLOW}⚠ Database is not running, starting...${NC}"
    docker start knowledge-graph-postgres
    sleep 3
fi

# Define profile settings
case "$PROFILE" in
    small)
        echo -e "${BLUE}Applying SMALL profile (8GB RAM, 8 cores)${NC}"
        SHARED_BUFFERS="2GB"
        WORK_MEM="32MB"
        MAINTENANCE_WORK_MEM="512MB"
        EFFECTIVE_CACHE="6GB"
        MAX_WORKERS=8
        MAX_PARALLEL=4
        MAX_PARALLEL_PER_GATHER=2
        ;;
    medium)
        echo -e "${BLUE}Applying MEDIUM profile (16GB RAM, 16 cores)${NC}"
        SHARED_BUFFERS="4GB"
        WORK_MEM="64MB"
        MAINTENANCE_WORK_MEM="1GB"
        EFFECTIVE_CACHE="12GB"
        MAX_WORKERS=16
        MAX_PARALLEL=8
        MAX_PARALLEL_PER_GATHER=4
        ;;
    large)
        echo -e "${BLUE}Applying LARGE profile (32GB RAM, 32 cores)${NC}"
        SHARED_BUFFERS="8GB"
        WORK_MEM="128MB"
        MAINTENANCE_WORK_MEM="2GB"
        EFFECTIVE_CACHE="24GB"
        MAX_WORKERS=32
        MAX_PARALLEL=16
        MAX_PARALLEL_PER_GATHER=8
        ;;
    *)
        echo -e "${RED}✗ Invalid profile: $PROFILE${NC}"
        echo ""
        show_usage
        exit 1
        ;;
esac

echo ""
echo -e "${YELLOW}Configuring PostgreSQL settings...${NC}"

# Apply settings via ALTER SYSTEM
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph <<EOSQL
-- Core parallelism settings
ALTER SYSTEM SET max_worker_processes = $MAX_WORKERS;
ALTER SYSTEM SET max_parallel_workers = $MAX_PARALLEL;
ALTER SYSTEM SET max_parallel_workers_per_gather = $MAX_PARALLEL_PER_GATHER;
ALTER SYSTEM SET max_parallel_maintenance_workers = $((MAX_PARALLEL_PER_GATHER > 4 ? 4 : MAX_PARALLEL_PER_GATHER));

-- Memory settings
ALTER SYSTEM SET shared_buffers = '$SHARED_BUFFERS';
ALTER SYSTEM SET work_mem = '$WORK_MEM';
ALTER SYSTEM SET maintenance_work_mem = '$MAINTENANCE_WORK_MEM';
ALTER SYSTEM SET effective_cache_size = '$EFFECTIVE_CACHE';

-- Parallel query cost optimization
ALTER SYSTEM SET parallel_tuple_cost = 0.01;
ALTER SYSTEM SET parallel_setup_cost = 100;

-- WAL settings (same for all profiles)
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET checkpoint_timeout = '15min';
ALTER SYSTEM SET max_wal_size = '4GB';
ALTER SYSTEM SET min_wal_size = '1GB';

-- Monitoring
ALTER SYSTEM SET track_io_timing = on;
ALTER SYSTEM SET log_min_duration_statement = 1000;
EOSQL

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to apply settings${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Settings applied to configuration${NC}"
echo ""
echo -e "${YELLOW}Restarting database container...${NC}"

# Restart container to apply settings
docker restart knowledge-graph-postgres

# Wait for database to be ready
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

echo ""
echo -e "${BLUE}Verifying applied settings:${NC}"
echo ""

docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT
  name,
  setting,
  CASE
    WHEN unit = '8kB' THEN pg_size_pretty((setting::bigint * 8192)::bigint)
    WHEN unit = 'kB' THEN pg_size_pretty((setting::bigint * 1024)::bigint)
    WHEN unit = 'MB' THEN setting || ' MB'
    WHEN unit IS NULL THEN setting
    ELSE setting || ' ' || unit
  END as value,
  CASE
    WHEN source = 'configuration file' THEN '✓'
    WHEN source = 'default' THEN '✗ (default)'
    ELSE source
  END as applied
FROM pg_settings
WHERE name IN (
  'max_worker_processes',
  'max_parallel_workers',
  'max_parallel_workers_per_gather',
  'max_parallel_maintenance_workers',
  'shared_buffers',
  'work_mem',
  'maintenance_work_mem',
  'effective_cache_size'
)
ORDER BY name;
"

echo ""
echo -e "${GREEN}✓ Profile '$PROFILE' applied successfully${NC}"
echo ""
echo -e "${CYAN}System Resources:${NC}"
echo -e "  CPU Cores:      $(nproc)"
echo -e "  Total RAM:      $(free -h | awk '/^Mem:/ {print $2}')"
echo ""
echo -e "${YELLOW}Monitor performance with:${NC} ./scripts/monitor-db.sh"
echo -e "${YELLOW}Change profile with:${NC}      ./scripts/configure-db-profile.sh <small|medium|large>"
echo ""
