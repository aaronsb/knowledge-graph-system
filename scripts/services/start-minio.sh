#!/usr/bin/env bash
# ============================================================================
# Start MinIO Service
# ============================================================================
# Starts the MinIO container and initializes the images bucket
#
# Usage:
#   ./scripts/services/start-minio.sh
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
echo -e "${BLUE}Starting MinIO Object Storage Service${NC}"
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

# Check if MinIO is already running
if docker ps | grep -q knowledge-graph-minio; then
    echo -e "${GREEN}✓ MinIO already running${NC}"
    echo ""
    echo -e "${BLUE}MinIO Status:${NC}"
    docker ps --filter "name=knowledge-graph-minio" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo -e "${BLUE}Access MinIO Console:${NC} http://localhost:9001"
    exit 0
fi

# Start MinIO container
echo -e "${YELLOW}→ Starting MinIO container...${NC}"
docker-compose up -d minio

# Wait for MinIO to be healthy
echo -e "${YELLOW}→ Waiting for MinIO to be ready...${NC}"
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec knowledge-graph-minio curl -sf http://localhost:9000/minio/health/live > /dev/null 2>&1; then
        echo -e "${GREEN}✓ MinIO is ready${NC}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo -e "${RED}✗ MinIO failed to become ready after ${MAX_RETRIES} attempts${NC}"
        echo ""
        echo "Check logs:"
        echo "  docker logs knowledge-graph-minio"
        exit 1
    fi
    sleep 1
done

echo ""

# Run initialization script if it exists
if [ -x "$PROJECT_ROOT/scripts/minio/init-minio.sh" ]; then
    echo -e "${YELLOW}→ Initializing MinIO bucket...${NC}"
    "$PROJECT_ROOT/scripts/minio/init-minio.sh"
else
    echo -e "${YELLOW}⚠ MinIO init script not found, skipping bucket initialization${NC}"
    echo "Expected: $PROJECT_ROOT/scripts/minio/init-minio.sh"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ MinIO started successfully${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}MinIO API:${NC}     http://localhost:9000"
echo -e "${BLUE}MinIO Console:${NC} http://localhost:9001"
echo -e "${BLUE}Username:${NC}      minioadmin"
echo -e "${BLUE}Password:${NC}      minioadmin"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "  • Run initialize-platform.sh to configure encrypted credentials"
echo "  • Restart API server to pick up MinIO credentials"
echo "  • Test image ingestion: kg ingest image <image-path> -o <ontology-name>"
echo ""
