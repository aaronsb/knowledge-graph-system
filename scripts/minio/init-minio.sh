#!/usr/bin/env bash
# ============================================================================
# MinIO Initialization Script
# ============================================================================
# Creates buckets and sets policies for image storage (ADR-057)
#
# Usage:
#   ./scripts/minio/init-minio.sh
#
# Environment Variables (optional, from .env):
#   MINIO_ROOT_USER     - MinIO admin username (default: minioadmin)
#   MINIO_ROOT_PASSWORD - MinIO admin password (default: minioadmin)
#   MINIO_HOST          - MinIO host (default: localhost)
#   MINIO_PORT          - MinIO port (default: 9000)
#   MINIO_BUCKET        - Bucket name (default: images)
#
# Note: Application retrieves credentials from encrypted key store (ADR-031)
#       Configure via: ./scripts/setup/initialize-platform.sh (option 7)
# ============================================================================

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f .env ]; then
    source .env
fi

MINIO_HOST="${MINIO_HOST:-localhost:9000}"
MINIO_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"
MINIO_BUCKET="${MINIO_BUCKET:-images}"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}MinIO Initialization${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if MinIO container is running
echo -e "${YELLOW}→ Checking MinIO container...${NC}"
if ! docker ps | grep -q knowledge-graph-minio; then
    echo -e "${RED}✗ MinIO container not running${NC}"
    echo -e "${YELLOW}  Run: ./scripts/services/start-minio.sh${NC}"
    echo -e "${YELLOW}  Or start all services: docker-compose up -d${NC}"
    exit 1
fi
echo -e "${GREEN}✓ MinIO container running${NC}"
echo ""

# Wait for MinIO to be ready
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
        exit 1
    fi
    sleep 1
done
echo ""

# Configure MinIO client (mc) inside the container
echo -e "${YELLOW}→ Configuring MinIO client...${NC}"
docker exec knowledge-graph-minio mc alias set local http://localhost:9000 "$MINIO_USER" "$MINIO_PASSWORD" > /dev/null 2>&1
echo -e "${GREEN}✓ MinIO client configured${NC}"
echo ""

# Create images bucket if it doesn't exist
echo -e "${YELLOW}→ Creating '${MINIO_BUCKET}' bucket...${NC}"
if docker exec knowledge-graph-minio mc ls local/${MINIO_BUCKET} > /dev/null 2>&1; then
    echo -e "${BLUE}  Bucket '${MINIO_BUCKET}' already exists${NC}"
else
    docker exec knowledge-graph-minio mc mb local/${MINIO_BUCKET}
    echo -e "${GREEN}✓ Bucket '${MINIO_BUCKET}' created${NC}"
fi
echo ""

# Set bucket policy (private by default - require authentication)
echo -e "${YELLOW}→ Setting bucket policy...${NC}"
docker exec knowledge-graph-minio mc anonymous set none local/${MINIO_BUCKET} > /dev/null 2>&1
echo -e "${GREEN}✓ Bucket policy set to private (authentication required)${NC}"
echo ""

# Enable versioning (optional - allows keeping multiple versions of same image)
echo -e "${YELLOW}→ Enabling versioning...${NC}"
docker exec knowledge-graph-minio mc version enable local/${MINIO_BUCKET} > /dev/null 2>&1
echo -e "${GREEN}✓ Versioning enabled${NC}"
echo ""

# Display bucket info
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ MinIO initialization complete${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Bucket Information:${NC}"
echo -e "  Name:       ${MINIO_BUCKET}"
echo -e "  Policy:     Private (authentication required)"
echo -e "  Versioning: Enabled"
echo -e "  Endpoint:   http://${MINIO_HOST}"
echo ""
echo -e "${BLUE}MinIO Console (Web UI):${NC}"
echo -e "  URL:      http://localhost:9001"
echo -e "  Username: ${MINIO_USER}"
echo -e "  Password: ${MINIO_PASSWORD}"
echo ""
