#!/bin/bash
# ============================================================================
# start-platform.sh - Complete platform startup (runs IN operator container)
#
# Called by operator.sh after infrastructure (postgres, garage, operator) is up.
# Handles: migrations, garage initialization, api/web startup
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Paths (inside container - project mounted at /workspace)
WORKSPACE="${WORKSPACE:-/workspace}"
OPERATOR_DIR="$WORKSPACE/operator"
DOCKER_DIR="$WORKSPACE/docker"
ENV_FILE="$WORKSPACE/.env"

# ============================================================================
# Wait for services
# ============================================================================

wait_for_postgres() {
    echo -e "${BLUE}→ Waiting for PostgreSQL...${NC}"
    # Try multiple hostnames (kg-postgres for standalone, knowledge-graph-postgres for dev)
    local pg_host="${POSTGRES_HOST:-postgres}"
    for i in {1..30}; do
        if pg_isready -h "$pg_host" -U "${POSTGRES_USER:-admin}" -d "${POSTGRES_DB:-knowledge_graph}" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ PostgreSQL ready${NC}"
            return 0
        fi
        sleep 2
    done
    echo -e "${RED}✗ PostgreSQL timeout${NC}"
    return 1
}

wait_for_garage() {
    echo -e "${BLUE}→ Waiting for Garage...${NC}"
    # Try multiple hostnames (garage for docker network, knowledge-graph-garage for container name)
    for i in {1..15}; do
        for host in "garage" "knowledge-graph-garage" "kg-garage"; do
            if curl -sf "http://${host}:3900/health" > /dev/null 2>&1; then
                echo -e "${GREEN}✓ Garage ready${NC}"
                return 0
            fi
        done
        sleep 2
    done
    echo -e "${YELLOW}⚠ Garage timeout (continuing)${NC}"
    return 0
}

# ============================================================================
# Database migrations
# ============================================================================

run_migrations() {
    echo -e "${BLUE}→ Running database migrations...${NC}"

    if [ -f "$OPERATOR_DIR/database/migrate-db.sh" ]; then
        "$OPERATOR_DIR/database/migrate-db.sh" -y 2>&1 | grep -E "✓|✅|→|⚠|✗" || true
        echo -e "${GREEN}✓ Migrations complete${NC}"
    else
        echo -e "${YELLOW}⚠ Migration script not found${NC}"
    fi
}

# ============================================================================
# Garage initialization
# ============================================================================

init_garage() {
    local bucket="${GARAGE_BUCKET:-kg-storage}"
    local key_name="kg-api-key"
    local garage_host="${GARAGE_HOST:-garage}"
    local garage_container="${GARAGE_CONTAINER:-knowledge-graph-garage}"

    echo -e "${BLUE}→ Initializing Garage...${NC}"

    # Use docker exec to run garage commands in the garage container
    # (more reliable than garage CLI in operator container)

    # Check for unassigned node
    local node_id=$(docker exec "$garage_container" /garage status 2>&1 | grep "NO ROLE ASSIGNED" | awk '{print $1}' || true)

    if [ -n "$node_id" ]; then
        docker exec "$garage_container" /garage layout assign "$node_id" -z dc1 -c 10G > /dev/null 2>&1 || true
        docker exec "$garage_container" /garage layout apply --version 1 > /dev/null 2>&1 || true
        echo -e "${GREEN}✓ Garage node configured${NC}"
    fi

    # Create bucket
    if ! docker exec "$garage_container" /garage bucket info "$bucket" > /dev/null 2>&1; then
        docker exec "$garage_container" /garage bucket create "$bucket" > /dev/null 2>&1 || true
        echo -e "${GREEN}✓ Bucket '$bucket' created${NC}"
    fi

    # Create key
    if ! docker exec "$garage_container" /garage key info "$key_name" > /dev/null 2>&1; then
        docker exec "$garage_container" /garage key create "$key_name" > /dev/null 2>&1 || true
        echo -e "${GREEN}✓ Garage API key created${NC}"
    fi

    # Grant permissions
    docker exec "$garage_container" /garage bucket allow --read --write --key "$key_name" "$bucket" > /dev/null 2>&1 || true
}

# ============================================================================
# Start application containers (via docker socket)
# ============================================================================

start_application() {
    echo -e "${BLUE}→ Starting application (api, web)...${NC}"

    cd "$DOCKER_DIR"

    if [ -f docker-compose.yml ]; then
        # Build compose command with available overlays
        # Check DEV_MODE from config or environment
        local dev_mode="${DEV_MODE:-false}"
        [ -f "$WORKSPACE/.operator.conf" ] && source "$WORKSPACE/.operator.conf"

        local compose_cmd="docker compose -f docker-compose.yml"

        # Dev mode OR prod mode, not both
        if [ "$dev_mode" = "true" ] || [ "$DEV_MODE" = "true" ]; then
            [ -f docker-compose.dev.yml ] && compose_cmd="$compose_cmd -f docker-compose.dev.yml"
        else
            [ -f docker-compose.prod.yml ] && compose_cmd="$compose_cmd -f docker-compose.prod.yml"
            [ -f docker-compose.ghcr.yml ] && compose_cmd="$compose_cmd -f docker-compose.ghcr.yml"
        fi

        # SSL overlay (can apply to either mode)
        [ -f docker-compose.ssl.yml ] && compose_cmd="$compose_cmd -f docker-compose.ssl.yml"

        compose_cmd="$compose_cmd --env-file $ENV_FILE"

        # Use --no-recreate to avoid recreating already-running containers
        $compose_cmd up -d --no-recreate api web

        # Wait for API health
        echo -e "${BLUE}→ Waiting for API...${NC}"
        local api_host="${API_HOST:-api}"
        for i in {1..30}; do
            if curl -sf "http://${api_host}:8000/health" > /dev/null 2>&1; then
                echo -e "${GREEN}✓ API is healthy${NC}"
                return 0
            fi
            sleep 2
        done
        echo -e "${YELLOW}⚠ API health timeout (may still be starting)${NC}"
    else
        echo -e "${YELLOW}⚠ No docker-compose.yml found at $DOCKER_DIR${NC}"
    fi
}

# ============================================================================
# Main
# ============================================================================

main() {
    echo -e "\n${BOLD}Platform Startup${NC}"
    echo ""

    wait_for_postgres || exit 1
    wait_for_garage
    run_migrations
    init_garage
    start_application

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ Platform started${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Show URL if available
    if [ -n "$PUBLIC_HOSTNAME" ]; then
        echo -e "\n  URL: ${BLUE}https://${PUBLIC_HOSTNAME}${NC}"
    fi
    echo ""
}

main "$@"
