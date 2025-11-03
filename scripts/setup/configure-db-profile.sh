#!/bin/bash
set -e

# ============================================================================
# configure-db-profile.sh
# PostgreSQL Resource Profile Configuration Tool
# ============================================================================
#
# PURPOSE:
# Interactive tool to configure PostgreSQL resource profiles and manage
# database container restarts. Provides safe, controlled performance tuning.
#
# FEATURES:
# - View current database settings
# - Apply resource profiles (small/medium/large) without forced restarts
# - Explicit restart option (no surprises!)
# - Verify applied settings
# - Menu loop for easy exploration
#
# PROFILES:
# - small:  8GB RAM, 8 cores  (development laptops)
# - medium: 16GB RAM, 16 cores (workstations)
# - large:  32GB+ RAM, 32 cores (production servers)
# ============================================================================

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m'
BOLD='\033[1m'

# Track if changes are pending
CHANGES_PENDING=false

# Show banner
echo -e "${BLUE}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║     PostgreSQL Resource Profile Configuration Tool        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if database container exists
if ! docker ps -a --format '{{.Names}}' | grep -q knowledge-graph-postgres; then
    echo -e "${RED}✗ Database container not found${NC}"
    echo -e "${YELLOW}  Run: ./scripts/database/start-database.sh${NC}"
    exit 1
fi

# Check if database is running, start if needed
if ! docker ps --format '{{.Names}}' | grep -q knowledge-graph-postgres; then
    echo -e "${YELLOW}⚠ Database is not running, starting...${NC}"
    docker start knowledge-graph-postgres
    sleep 3
fi

echo -e "${GREEN}✓${NC} Database container is running"

# Function to get current database settings
get_current_settings() {
    docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -t -A -c "
SELECT
  COALESCE(
    (SELECT setting FROM pg_settings WHERE name = 'shared_buffers'),
    'unknown'
  )
" 2>/dev/null | head -n 1
}

# Function to detect current profile based on settings
detect_current_profile() {
    local shared_buffers=$(docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -t -A -c "SELECT setting FROM pg_settings WHERE name = 'shared_buffers'" 2>/dev/null | xargs)

    if [ -z "$shared_buffers" ] || [ "$shared_buffers" = "0" ]; then
        echo "unknown"
        return
    fi

    # Convert 8kB blocks to GB (shared_buffers is stored in 8kB blocks)
    # shared_buffers is stored as number of 8KB blocks
    # To convert to GB: blocks * 8KB / 1024KB/MB / 1024MB/GB
    local shared_gb=$(echo "scale=1; $shared_buffers * 8 / 1024 / 1024" | bc 2>/dev/null)

    if [ -z "$shared_gb" ]; then
        echo "unknown"
        return
    fi

    # Use bc for floating point comparison
    if [ $(echo "$shared_gb >= 7.0" | bc) -eq 1 ]; then
        echo "large"
    elif [ $(echo "$shared_gb >= 3.0" | bc) -eq 1 ]; then
        echo "medium"
    elif [ $(echo "$shared_gb >= 1.5" | bc) -eq 1 ]; then
        echo "small"
    else
        echo "custom"
    fi
}

# Function to show current settings
show_current_settings() {
    echo -e "\n${BOLD}${CYAN}Current PostgreSQL Settings${NC}"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT
  name,
  CASE
    WHEN unit = '8kB' THEN pg_size_pretty((setting::bigint * 8192)::bigint)
    WHEN unit = 'kB' THEN pg_size_pretty((setting::bigint * 1024)::bigint)
    WHEN unit = 'MB' THEN setting || ' MB'
    WHEN unit IS NULL THEN setting
    ELSE setting || ' ' || unit
  END as value,
  CASE
    WHEN source = 'configuration file' THEN '✓ configured'
    WHEN source = 'default' THEN '○ default'
    ELSE source
  END as status
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
" 2>/dev/null

    echo -e "\n${CYAN}System Resources:${NC}"
    echo -e "  CPU Cores:      $(nproc)"
    echo -e "  Total RAM:      $(free -h | awk '/^Mem:/ {print $2}')"

    local profile=$(detect_current_profile)
    echo -e "\n${CYAN}Detected Profile:${NC} ${YELLOW}${profile}${NC}"
}

# Function to show profile details
show_profile_details() {
    local profile=$1

    case "$profile" in
        small)
            echo -e "${YELLOW}SMALL${NC} Profile - Development laptop/workstation"
            echo "  • 8GB RAM, 8 CPU cores"
            echo "  • shared_buffers: 2GB (25% of 8GB)"
            echo "  • work_mem: 32MB"
            echo "  • maintenance_work_mem: 512MB"
            echo "  • effective_cache_size: 6GB (75% of 8GB)"
            echo "  • max_worker_processes: 8"
            echo "  • max_parallel_workers: 4"
            echo "  • max_parallel_workers_per_gather: 2"
            ;;
        medium)
            echo -e "${YELLOW}MEDIUM${NC} Profile - Production workstation/small server"
            echo "  • 16GB RAM, 16 CPU cores"
            echo "  • shared_buffers: 4GB (25% of 16GB)"
            echo "  • work_mem: 64MB"
            echo "  • maintenance_work_mem: 1GB"
            echo "  • effective_cache_size: 12GB (75% of 16GB)"
            echo "  • max_worker_processes: 16"
            echo "  • max_parallel_workers: 8"
            echo "  • max_parallel_workers_per_gather: 4"
            ;;
        large)
            echo -e "${YELLOW}LARGE${NC} Profile - Production server/high-performance system"
            echo "  • 32GB+ RAM, 32 CPU cores"
            echo "  • shared_buffers: 8GB (25% of 32GB)"
            echo "  • work_mem: 128MB"
            echo "  • maintenance_work_mem: 2GB"
            echo "  • effective_cache_size: 24GB (75% of 32GB)"
            echo "  • max_worker_processes: 32"
            echo "  • max_parallel_workers: 16"
            echo "  • max_parallel_workers_per_gather: 8"
            ;;
    esac
}

# Function to apply a profile (without restarting)
apply_profile() {
    local profile=$1

    # Define profile settings
    case "$profile" in
        small)
            SHARED_BUFFERS="2GB"
            WORK_MEM="32MB"
            MAINTENANCE_WORK_MEM="512MB"
            EFFECTIVE_CACHE="6GB"
            MAX_WORKERS=8
            MAX_PARALLEL=4
            MAX_PARALLEL_PER_GATHER=2
            ;;
        medium)
            SHARED_BUFFERS="4GB"
            WORK_MEM="64MB"
            MAINTENANCE_WORK_MEM="1GB"
            EFFECTIVE_CACHE="12GB"
            MAX_WORKERS=16
            MAX_PARALLEL=8
            MAX_PARALLEL_PER_GATHER=4
            ;;
        large)
            SHARED_BUFFERS="8GB"
            WORK_MEM="128MB"
            MAINTENANCE_WORK_MEM="2GB"
            EFFECTIVE_CACHE="24GB"
            MAX_WORKERS=32
            MAX_PARALLEL=16
            MAX_PARALLEL_PER_GATHER=8
            ;;
        *)
            echo -e "${RED}✗ Invalid profile: $profile${NC}"
            return 1
            ;;
    esac

    echo -e "\n${BLUE}→${NC} Applying ${YELLOW}${profile^^}${NC} profile settings..."

    # Apply settings via ALTER SYSTEM
    docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph <<EOSQL 2>/dev/null
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
        return 1
    fi

    echo -e "${GREEN}✓${NC} Settings written to configuration"
    echo -e "${YELLOW}⚠${NC}  ${BOLD}Database restart required to apply changes${NC}"
    echo -e "   Use option 5 to restart database"
    CHANGES_PENDING=true
}

# Function to check if API server is running
check_api_server() {
    curl -s http://localhost:8000/health > /dev/null 2>&1
    return $?
}

# Function to restart database
restart_database() {
    local api_was_running=false

    # Check if API server is running
    if check_api_server; then
        api_was_running=true
        echo -e "\n${YELLOW}⚠${NC}  API server is running and will need to be restarted"
        echo -e "   (Database connections will be stale after restart)"
    fi

    echo -e "\n${YELLOW}→${NC} Restarting database container..."

    docker restart knowledge-graph-postgres > /dev/null 2>&1

    # Wait for database to be ready
    echo -e "${YELLOW}→${NC} Waiting for database to be ready..."
    for i in {1..30}; do
        if docker exec knowledge-graph-postgres pg_isready -U admin -d knowledge_graph > /dev/null 2>&1; then
            # Additional check - try to actually query the database
            if docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "SELECT 1" > /dev/null 2>&1; then
                echo -e "${GREEN}✓${NC} Database is ready"
                CHANGES_PENDING=false

                if [ "$api_was_running" = true ]; then
                    echo ""
                    echo -e "${YELLOW}${BOLD}⚠  IMPORTANT: API server must be restarted${NC}"
                    echo -e "   ${CYAN}./scripts/stop-api.sh && ./scripts/start-api.sh${NC}"
                    echo -e "   Or use option 6 to restart API automatically"
                fi
                return 0
            fi
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}✗ Database failed to become ready${NC}"
            return 1
        fi
        sleep 1
    done
}

# Function to restart API server
restart_api_server() {
    echo -e "\n${YELLOW}→${NC} Checking API server status..."

    if ! check_api_server; then
        echo -e "${YELLOW}○${NC} API server is not running"
        echo -e "   Start it with: ${CYAN}./scripts/start-api.sh${NC}"
        return 0
    fi

    echo -e "${GREEN}✓${NC} API server is running"
    echo -e "\n${YELLOW}→${NC} Restarting API server..."

    # Stop API
    ./scripts/stop-api.sh > /dev/null 2>&1
    sleep 2

    # Start API
    ./scripts/start-api.sh -y > /dev/null 2>&1

    # Wait for API to be ready
    echo -e "${YELLOW}→${NC} Waiting for API to be ready..."
    for i in {1..30}; do
        if check_api_server; then
            echo -e "${GREEN}✓${NC} API server is ready"
            return 0
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}✗ API server failed to become ready${NC}"
            echo -e "   Check logs: ${CYAN}tail -f logs/api_*.log${NC}"
            return 1
        fi
        sleep 1
    done
}

# Main menu loop
while true; do
    echo -e "\n${BOLD}Database Configuration${NC}"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Show pending changes warning
    if [ "$CHANGES_PENDING" = true ]; then
        echo -e "${YELLOW}${BOLD}⚠  CHANGES PENDING - Database restart required to apply${NC}"
        echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    fi

    echo -e "\n${BOLD}${YELLOW}Options:${NC}"
    echo -e "  ${GREEN}1)${NC} View current settings"
    echo -e "  ${GREEN}2)${NC} Apply SMALL profile (8GB RAM, 8 cores)"
    echo -e "  ${GREEN}3)${NC} Apply MEDIUM profile (16GB RAM, 16 cores)"
    echo -e "  ${GREEN}4)${NC} Apply LARGE profile (32GB+ RAM, 32 cores)"
    echo -e "  ${GREEN}5)${NC} Restart database (apply pending changes)"
    echo -e "  ${GREEN}6)${NC} Restart API server (fix stale connections)"
    echo -e "  ${GREEN}7)${NC} View profile details"
    echo -e "  ${RED}8)${NC} Exit"
    echo ""

    read -p "Select option [1-8]: " option

    case $option in
        1)
            # Always refresh settings from database
            show_current_settings
            ;;
        2)
            echo -e "\n${CYAN}Applying SMALL profile...${NC}"
            show_profile_details "small"
            echo ""
            read -p "Apply this profile? [y/N]: " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                apply_profile "small"
            else
                echo -e "${YELLOW}Cancelled${NC}"
            fi
            ;;
        3)
            echo -e "\n${CYAN}Applying MEDIUM profile...${NC}"
            show_profile_details "medium"
            echo ""
            read -p "Apply this profile? [y/N]: " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                apply_profile "medium"
            else
                echo -e "${YELLOW}Cancelled${NC}"
            fi
            ;;
        4)
            echo -e "\n${CYAN}Applying LARGE profile...${NC}"
            show_profile_details "large"
            echo ""
            read -p "Apply this profile? [y/N]: " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                apply_profile "large"
            else
                echo -e "${YELLOW}Cancelled${NC}"
            fi
            ;;
        5)
            if [ "$CHANGES_PENDING" = false ]; then
                echo ""
                echo -e "${YELLOW}⚠${NC}  No pending changes to apply"
                echo -e "   Current settings are already active"
                echo ""
                read -p "Restart database anyway? [y/N]: " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    continue
                fi
            fi
            restart_database
            ;;
        6)
            restart_api_server
            ;;
        7)
            echo -e "\n${BOLD}${CYAN}Available Profiles${NC}"
            echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            show_profile_details "small"
            echo ""
            show_profile_details "medium"
            echo ""
            show_profile_details "large"
            ;;
        8)
            if [ "$CHANGES_PENDING" = true ]; then
                echo ""
                echo -e "${YELLOW}⚠${NC}  ${BOLD}You have pending changes that have not been applied${NC}"
                echo -e "   Settings will not take effect until database is restarted"
                echo ""
                read -p "Exit anyway? [y/N]: " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    continue
                fi
            fi
            echo ""
            echo -e "${GREEN}✓${NC} Configuration tool closed"
            exit 0
            ;;
        *)
            echo ""
            echo -e "${RED}Invalid option${NC}"
            ;;
    esac

    echo ""
    echo -e "${BLUE}Press Enter to continue...${NC}"
    read
done
