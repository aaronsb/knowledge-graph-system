#!/bin/bash
#
# Clean up generated files after ingestion
#
# Removes output/ directory and optionally resets state.
# Use after successful ingestion when you no longer need the markdown files.
#
# Usage:
#   ./clean.sh             # Remove output files, keep state
#   ./clean.sh --reset     # Remove output files AND reset state
#   ./clean.sh --reset-state-only  # Only reset state, keep files
#

set -e

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

RESET_STATE=false
RESET_STATE_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --reset)
      RESET_STATE=true
      shift
      ;;
    --reset-state-only)
      RESET_STATE_ONLY=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--reset] [--reset-state-only]"
      exit 1
      ;;
  esac
done

echo "======================================================================"
echo "CLEANUP"
echo "======================================================================"
echo ""

if [ "$RESET_STATE_ONLY" = true ]; then
    echo -e "${YELLOW}Resetting state only (keeping output files)${NC}"
    if [ -f ".ingest_state.json" ]; then
        rm .ingest_state.json
        echo -e "${GREEN}✓ Removed .ingest_state.json${NC}"
    fi
    if [ -f "config.json" ]; then
        jq '.repositories[].last_commit = null | .repositories[].last_pr = null' config.json > config.json.tmp
        mv config.json.tmp config.json
        echo -e "${GREEN}✓ Reset config.json pointers${NC}"
    fi
    echo ""
    echo "State reset. Output files preserved."
    exit 0
fi

# Remove output directory
if [ -d "output" ]; then
    file_count=$(find output -type f | wc -l)
    echo "Output directory contains $file_count files"
    echo -e "${YELLOW}Removing output/ directory...${NC}"
    rm -rf output
    echo -e "${GREEN}✓ Removed output/  ${NC}"
else
    echo "No output/ directory found"
fi

# Remove state file if --reset
if [ "$RESET_STATE" = true ]; then
    echo ""
    echo -e "${YELLOW}Resetting ingestion state...${NC}"

    if [ -f ".ingest_state.json" ]; then
        rm .ingest_state.json
        echo -e "${GREEN}✓ Removed .ingest_state.json${NC}"
    fi

    if [ -f "config.json" ]; then
        jq '.repositories[].last_commit = null | .repositories[].last_pr = null' config.json > config.json.tmp
        mv config.json.tmp config.json
        echo -e "${GREEN}✓ Reset config.json pointers${NC}"
    fi
fi

echo ""
echo "======================================================================"
echo -e "${GREEN}CLEANUP COMPLETE${NC}"
echo "======================================================================"
echo ""

if [ "$RESET_STATE" = true ]; then
    echo "All state reset. Next extraction will start from the beginning."
else
    echo "Output files removed. State preserved for incremental updates."
    echo "Run with --reset to also reset extraction pointers."
fi
echo ""
