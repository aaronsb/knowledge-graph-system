#!/usr/bin/env bash
# ============================================================================
# Garage Status - Show node status, buckets, and storage statistics
# ============================================================================
# Quick overview of Garage cluster health and storage usage
#
# Usage:
#   ./scripts/diagnostics/garage-status.sh
# ============================================================================

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Garage Status & Statistics${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if Garage is running
if ! docker ps | grep -q knowledge-graph-garage; then
    echo -e "${RED}✗ Garage container not running${NC}"
    echo ""
    echo "Start Garage:"
    echo "  ./scripts/services/start-garage.sh"
    exit 1
fi

echo -e "${GREEN}✓ Garage container running${NC}"
echo ""

# Node Status
echo -e "${CYAN}Node Status:${NC}"
docker exec knowledge-graph-garage /garage status 2>&1 | grep -v "INFO\|Connected" || true
echo ""

# Buckets
echo -e "${CYAN}Buckets:${NC}"
docker exec knowledge-graph-garage /garage bucket list 2>&1 | grep -v "INFO\|Connected" || true
echo ""

# Storage Statistics (via Python client)
echo -e "${CYAN}Storage Statistics:${NC}"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

if [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

python3 << 'EOF'
try:
    from src.api.lib.garage_client import get_garage_client

    client = get_garage_client()

    # List all images
    images = client.list_images()

    total_size = sum(img['size'] for img in images)
    total_size_mb = total_size / (1024 * 1024)

    print(f"  Total Images: {len(images)}")
    print(f"  Total Size:   {total_size_mb:.2f} MB ({total_size:,} bytes)")

    if images:
        print(f"\n  Recent Images:")
        for img in sorted(images, key=lambda x: x['last_modified'], reverse=True)[:5]:
            size_kb = img['size'] / 1024
            print(f"    • {img['object_name']}")
            print(f"      Size: {size_kb:.1f} KB, Modified: {img['last_modified'].strftime('%Y-%m-%d %H:%M:%S')}")

except Exception as e:
    print(f"  Error: {e}")
EOF

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
