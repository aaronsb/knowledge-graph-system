#!/usr/bin/env bash
# ============================================================================
# Stop MinIO Service
# ============================================================================
# Stops the MinIO container (data persists in Docker volume)
#
# Usage:
#   ./scripts/services/stop-minio.sh
#
# Options:
#   -v, --volumes    Also remove data volumes (DESTRUCTIVE!)
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

# Parse arguments
REMOVE_VOLUMES=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--volumes)
            REMOVE_VOLUMES=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Stopping MinIO Object Storage Service${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Navigate to project root
cd "$PROJECT_ROOT"

# Check if MinIO is running
if ! docker ps | grep -q knowledge-graph-minio; then
    echo -e "${YELLOW}⚠ MinIO is not running${NC}"
    exit 0
fi

# Stop MinIO container
echo -e "${YELLOW}→ Stopping MinIO container...${NC}"
docker-compose stop minio

if [ "$REMOVE_VOLUMES" = true ]; then
    echo -e "${RED}⚠ WARNING: Removing MinIO data volumes (DESTRUCTIVE!)${NC}"
    echo -e "${RED}   All stored images will be permanently deleted${NC}"
    echo ""
    read -p "Are you sure? Type 'yes' to confirm: " confirm
    if [ "$confirm" = "yes" ]; then
        echo -e "${YELLOW}→ Removing MinIO volumes...${NC}"
        docker-compose down minio -v
        echo -e "${GREEN}✓ MinIO volumes removed${NC}"
    else
        echo -e "${YELLOW}⚠ Cancelled - volumes preserved${NC}"
    fi
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ MinIO stopped${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ "$REMOVE_VOLUMES" = false ]; then
    echo -e "${BLUE}Note:${NC} Image data persists in Docker volume 'minio_data'"
    echo "      To permanently delete images, run: $0 --volumes"
fi

echo ""
