#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Stopping Visualization Explorer...${NC}"

# Find and kill Vite dev server processes
PIDS=$(ps aux | grep 'vite.*viz-app' | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo -e "${YELLOW}No Visualization Explorer processes found${NC}"
else
    echo "$PIDS" | xargs kill 2>/dev/null || true
    echo -e "${GREEN}✓ Visualization Explorer stopped${NC}"
fi
