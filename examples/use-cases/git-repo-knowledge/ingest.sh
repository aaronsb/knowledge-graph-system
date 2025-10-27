#!/bin/bash
#
# Ingest git commits and PRs into knowledge graph using directory ingestion.
#
# This script uses 'kg ingest directory' for efficient batch processing.
# The extraction scripts (extract_commits.py, extract_prs.py) handle idempotency
# via config.json pointers, so we simply ingest whatever is in output/.
#
# Usage:
#   ./ingest.sh                 # Ingest all documents in output/
#   ./ingest.sh --no-auto-approve  # Require manual approval
#   ./ingest.sh --clean         # Remove output/ after ingestion
#

set -e  # Exit on error

# Configuration
OUTPUT_DIR="output"
AUTO_APPROVE=""  # Default to auto-approve (no flag = auto-approve)

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Parse arguments
CLEAN=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --no-auto-approve)
      AUTO_APPROVE="--no-approve"
      shift
      ;;
    --clean)
      CLEAN=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--no-auto-approve] [--clean]"
      exit 1
      ;;
  esac
done

echo "======================================================================"
echo "GIT REPOSITORY KNOWLEDGE GRAPH INGESTION"
echo "======================================================================"
echo ""

# Check if output directory exists
if [ ! -d "$OUTPUT_DIR" ]; then
    echo -e "${YELLOW}No output directory found${NC}"
    echo "Run extract_commits.py and/or extract_prs.py first"
    exit 0
fi

total_ingested=0

# Ingest commits
if [ -d "$OUTPUT_DIR/commits" ]; then
    echo "Processing commits..."

    for repo in "$OUTPUT_DIR/commits"/*/ ; do
        if [ -d "$repo" ]; then
            repo_name=$(basename "$repo")
            ontology=$(jq -r ".repositories[] | select(.name == \"$repo_name\") | .ontology" config.json)

            # Count files
            file_count=$(find "$repo" -name "*.md" -type f | wc -l)

            if [ "$file_count" -eq 0 ]; then
                echo ""
                echo "Repository: $repo_name"
                echo "  No commit files to ingest"
                continue
            fi

            echo ""
            echo "Repository: $repo_name"
            echo "Ontology: $ontology"
            echo "  Found $file_count commit files"

            # Ingest entire directory
            echo "  Ingesting commits..."
            if kg ingest directory -o "$ontology" $AUTO_APPROVE "$repo"; then
                echo -e "${GREEN}  ✓ Ingested $file_count commits${NC}"
                ((total_ingested += file_count))
            else
                echo -e "${RED}  ✗ Ingestion failed${NC}"
            fi
        fi
    done
fi

# Ingest PRs
if [ -d "$OUTPUT_DIR/prs" ]; then
    echo ""
    echo "Processing pull requests..."

    for repo in "$OUTPUT_DIR/prs"/*/ ; do
        if [ -d "$repo" ]; then
            repo_name=$(basename "$repo")
            ontology=$(jq -r ".repositories[] | select(.name == \"$repo_name\") | .ontology" config.json)

            # Count files
            file_count=$(find "$repo" -name "*.md" -type f | wc -l)

            if [ "$file_count" -eq 0 ]; then
                echo ""
                echo "Repository: $repo_name"
                echo "  No PR files to ingest"
                continue
            fi

            echo ""
            echo "Repository: $repo_name"
            echo "Ontology: $ontology"
            echo "  Found $file_count PR files"

            # Ingest entire directory
            echo "  Ingesting PRs..."
            if kg ingest directory -o "$ontology" $AUTO_APPROVE "$repo"; then
                echo -e "${GREEN}  ✓ Ingested $file_count PRs${NC}"
                ((total_ingested += file_count))
            else
                echo -e "${RED}  ✗ Ingestion failed${NC}"
            fi
        fi
    done
fi

# Cleanup if requested
if [ "$CLEAN" = true ]; then
    echo ""
    echo "======================================================================"
    echo "CLEANUP"
    echo "======================================================================"
    echo ""
    echo -e "${YELLOW}Removing output files...${NC}"
    rm -rf "$OUTPUT_DIR"
    echo -e "${GREEN}✓ Output files removed${NC}"
    echo ""
    echo "State pointers preserved in config.json. Next extraction will only process new items."
fi

echo ""
echo "======================================================================"
echo -e "${GREEN}INGESTION COMPLETE${NC}"
echo "======================================================================"
echo ""
echo "Total documents ingested: $total_ingested"
echo ""
echo "Next steps:"
echo "  kg database stats                    # View ontology statistics"
echo "  kg search query \"your search term\"  # Semantic search"
echo ""
echo "Run extract scripts again to process new commits/PRs incrementally."
if [ "$CLEAN" != true ]; then
    echo "Use --clean flag to remove output files after ingestion."
fi
