#!/bin/bash

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m'

# Check if database is running
if ! docker ps --format '{{.Names}}' | grep -q knowledge-graph-postgres; then
    echo -e "${RED}✗ Database is not running${NC}"
    echo -e "${YELLOW}  Start with: ./scripts/start-db.sh${NC}"
    exit 1
fi

echo -e "${BLUE}🔍 PostgreSQL Performance Monitor${NC}"
echo -e "${GRAY}=================================${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Track last active count to detect activity changes
LAST_ACTIVE=0
IDLE_COUNT=0

# Cleanup on exit
trap 'echo -e "\n${YELLOW}Monitoring stopped${NC}"; exit 0' INT TERM

while true; do
    # Get current stats
    STATS=$(docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -t -A -F'|' -c "
    SELECT
        (SELECT count(*) FROM pg_stat_activity WHERE state = 'active' AND pid != pg_backend_pid()) as active_queries,
        (SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction') as idle_txn,
        (SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock') as waiting_locks,
        (SELECT sum(numbackends) FROM pg_stat_database) as total_connections,
        (SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'parallel worker') as parallel_workers
    " 2>/dev/null)

    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Failed to query database${NC}"
        sleep 3
        continue
    fi

    # Parse stats
    IFS='|' read -r ACTIVE IDLE_TXN LOCKS CONNECTIONS WORKERS <<< "$STATS"

    # Get Docker stats
    DOCKER_STATS=$(docker stats knowledge-graph-postgres --no-stream --format "{{.CPUPerc}}|{{.MemUsage}}" 2>/dev/null)
    IFS='|' read -r CPU_PERC MEM_USAGE <<< "$DOCKER_STATS"

    # Check if there's activity (active queries or parallel workers)
    CURRENT_ACTIVITY=$((ACTIVE + WORKERS))

    if [ "$CURRENT_ACTIVITY" -gt 0 ]; then
        # Activity detected - show detailed stats
        IDLE_COUNT=0

        # Clear screen if this is first activity after idle
        if [ "$LAST_ACTIVE" -eq 0 ]; then
            clear
            echo -e "${BLUE}🔍 PostgreSQL Performance Monitor${NC}"
            echo -e "${GRAY}=================================${NC}"
            echo ""
        fi

        TIMESTAMP=$(date '+%H:%M:%S')
        echo -e "${CYAN}[$TIMESTAMP]${NC} ${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

        # System resources
        echo -e "${BLUE}System:${NC}"
        echo -e "  CPU:    ${YELLOW}$CPU_PERC${NC}  (max 3200% with 32 cores, 800% with 8 parallel workers)"
        echo -e "  Memory: ${YELLOW}$MEM_USAGE${NC}"

        # Query activity
        echo -e "\n${BLUE}Query Activity:${NC}"
        echo -e "  Active Queries:    ${GREEN}$ACTIVE${NC}"
        echo -e "  Parallel Workers:  ${GREEN}$WORKERS${NC}"
        echo -e "  Total Connections: $CONNECTIONS"

        if [ "$LOCKS" -gt 0 ]; then
            echo -e "  ${RED}⚠ Waiting on Locks: $LOCKS${NC}"
        fi

        if [ "$IDLE_TXN" -gt 0 ]; then
            echo -e "  ${YELLOW}⚠ Idle in Transaction: $IDLE_TXN${NC}"
        fi

        # Show active queries
        if [ "$ACTIVE" -gt 0 ]; then
            echo -e "\n${BLUE}Active Queries:${NC}"
            docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
            SELECT
                pid,
                left(query, 80) as query,
                state,
                wait_event_type,
                EXTRACT(EPOCH FROM (now() - query_start))::int as duration_sec
            FROM pg_stat_activity
            WHERE state = 'active'
              AND pid != pg_backend_pid()
            ORDER BY query_start
            " 2>/dev/null | sed 's/^/  /'
        fi

        # Show parallel workers if any
        if [ "$WORKERS" -gt 0 ]; then
            echo -e "\n${BLUE}Parallel Workers:${NC}"
            docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
            SELECT
                pid,
                backend_type,
                wait_event_type,
                wait_event
            FROM pg_stat_activity
            WHERE backend_type = 'parallel worker'
            " 2>/dev/null | sed 's/^/  /'
        fi

        # Show recent slow queries (> 1 second, from logs)
        SLOW_QUERIES=$(docker logs knowledge-graph-postgres --since 5s 2>&1 | grep "duration:" | tail -3)
        if [ ! -z "$SLOW_QUERIES" ]; then
            echo -e "\n${YELLOW}Recent Slow Queries (>1s):${NC}"
            echo "$SLOW_QUERIES" | sed 's/^/  /' | sed "s/duration:/$(echo -e ${RED})duration:$(echo -e ${NC})/g"
        fi

        LAST_ACTIVE=$CURRENT_ACTIVITY

    else
        # No activity
        LAST_ACTIVE=0
        IDLE_COUNT=$((IDLE_COUNT + 1))

        # Only show idle message every 10 iterations (20 seconds)
        if [ $((IDLE_COUNT % 10)) -eq 1 ]; then
            TIMESTAMP=$(date '+%H:%M:%S')
            echo -e "${GRAY}[$TIMESTAMP] Idle - waiting for query activity...${NC}"
        fi
    fi

    sleep 2
done
