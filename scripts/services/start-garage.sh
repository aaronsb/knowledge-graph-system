#!/usr/bin/env bash
# ============================================================================
# Start Garage Service
# ============================================================================
# Starts the Garage container and initializes the images bucket
#
# Usage:
#   ./scripts/services/start-garage.sh
# ============================================================================

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Starting Garage Object Storage Service${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    echo "Install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Navigate to project root
cd "$PROJECT_ROOT"

# Auto-generate GARAGE_RPC_SECRET if missing or placeholder (cold-start requirement)
if [ -f "$PROJECT_ROOT/.env" ]; then
    if ! grep -q "^GARAGE_RPC_SECRET=" "$PROJECT_ROOT/.env" 2>/dev/null || \
       grep -q "^GARAGE_RPC_SECRET=CHANGE_THIS" "$PROJECT_ROOT/.env" 2>/dev/null; then
        echo -e "${YELLOW}→ Generating Garage RPC secret...${NC}"
        RPC_SECRET=$(openssl rand -hex 32)

        if grep -q "^GARAGE_RPC_SECRET=" "$PROJECT_ROOT/.env" 2>/dev/null; then
            # Replace existing placeholder
            if command -v sed &> /dev/null; then
                sed -i.bak "s|^GARAGE_RPC_SECRET=.*|GARAGE_RPC_SECRET=$RPC_SECRET|" "$PROJECT_ROOT/.env"
                rm -f "$PROJECT_ROOT/.env.bak"
            fi
        else
            # Add if missing
            echo "GARAGE_RPC_SECRET=$RPC_SECRET" >> "$PROJECT_ROOT/.env"
        fi
        echo -e "${GREEN}✓ Generated RPC secret${NC}"
        echo ""
    fi
else
    echo -e "${RED}✗ .env file not found${NC}"
    echo "Create .env from .env.example first"
    exit 1
fi

# Check if Garage is already running
if docker ps | grep -q knowledge-graph-garage; then
    echo -e "${GREEN}✓ Garage already running${NC}"
    echo ""
    echo -e "${BLUE}Garage Status:${NC}"
    docker ps --filter "name=knowledge-graph-garage" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo -e "${BLUE}Access Garage S3 API:${NC}   http://localhost:3900"
    echo -e "${BLUE}Access Garage Admin API:${NC} http://localhost:3903"
    exit 0
fi

# Start Garage container
echo -e "${YELLOW}→ Starting Garage container...${NC}"
docker-compose up -d garage

# Wait for Garage to be healthy
echo -e "${YELLOW}→ Waiting for Garage to be ready...${NC}"
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec knowledge-graph-garage /garage status > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Garage is ready${NC}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo -e "${RED}✗ Garage failed to become ready after ${MAX_RETRIES} attempts${NC}"
        echo ""
        echo "Check logs:"
        echo "  docker logs knowledge-graph-garage"
        exit 1
    fi
    sleep 1
done

echo ""

# Run initialization script if it exists
if [ -x "$PROJECT_ROOT/scripts/garage/init-garage.sh" ]; then
    echo -e "${YELLOW}→ Initializing Garage bucket...${NC}"
    "$PROJECT_ROOT/scripts/garage/init-garage.sh"
else
    echo -e "${YELLOW}⚠ Garage init script not found, skipping bucket initialization${NC}"
    echo "Expected: $PROJECT_ROOT/scripts/garage/init-garage.sh"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Garage started successfully${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Garage S3 API:${NC}   http://localhost:3900"
echo -e "${BLUE}Garage Admin API:${NC} http://localhost:3903"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "  • Run initialize-platform.sh to configure encrypted credentials"
echo "  • Restart API server to pick up Garage credentials"
echo "  • Test image ingestion: kg ingest image <image-path> -o <ontology-name>"
echo ""
