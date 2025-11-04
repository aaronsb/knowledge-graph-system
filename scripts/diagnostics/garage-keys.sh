#!/usr/bin/env bash
# ============================================================================
# Garage Keys - Show API keys and bucket permissions
# ============================================================================
# Display all API keys configured in Garage and their bucket permissions.
# Useful for debugging access issues and verifying configuration.
#
# Usage:
#   ./scripts/diagnostics/garage-keys.sh
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
echo -e "${BLUE}Garage API Keys & Permissions${NC}"
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

# List all keys
echo -e "${CYAN}API Keys:${NC}"
KEY_LIST=$(docker exec knowledge-graph-garage /garage key list 2>&1 | grep -v "INFO\|Connected" || true)
echo "$KEY_LIST"
echo ""

# Get details for each key
echo -e "${CYAN}Key Details & Permissions:${NC}"
echo ""

# Extract key names from the list
KEY_NAMES=$(echo "$KEY_LIST" | awk '{print $1}' | grep -v "^$")

for KEY_NAME in $KEY_NAMES; do
    if [ -n "$KEY_NAME" ] && [ "$KEY_NAME" != "Key" ]; then
        echo -e "${YELLOW}Key: ${KEY_NAME}${NC}"
        docker exec knowledge-graph-garage /garage key info "$KEY_NAME" 2>&1 | grep -v "INFO\|Connected" || true
        echo ""
    fi
done

# Show buckets and their permissions
echo -e "${CYAN}Bucket Permissions:${NC}"
docker exec knowledge-graph-garage /garage bucket list 2>&1 | grep -v "INFO\|Connected" || true
echo ""

# Get detailed bucket info
BUCKET_LIST=$(docker exec knowledge-graph-garage /garage bucket list 2>&1 | grep -v "INFO\|Connected\|^$" || true)

for BUCKET in $BUCKET_LIST; do
    if [ -n "$BUCKET" ]; then
        echo -e "${YELLOW}Bucket: ${BUCKET}${NC}"
        docker exec knowledge-graph-garage /garage bucket info "$BUCKET" 2>&1 | grep -v "INFO\|Connected" || true
        echo ""
    fi
done

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}Note:${NC} Secret keys are only shown once during creation."
echo "To retrieve credentials from encrypted database:"
echo "  ./scripts/setup/initialize-platform.sh"
echo "  Select option 6 (API Keys)"
echo ""
