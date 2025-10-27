#!/bin/bash
#
# Git Data Collector: Complete extraction and ingestion workflow
#
# This script:
# 1. Sets up a Python virtual environment
# 2. Installs required dependencies
# 3. Extracts commits from git repository
# 4. Extracts GitHub PRs (if gh CLI authenticated)
# 5. Ingests everything into knowledge graph
# 6. Shows query examples
#
# Completely self-contained - handles all dependencies automatically.
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

VENV_DIR="venv"
PYTHON="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"

echo "======================================================================"
echo "GIT REPOSITORY KNOWLEDGE GRAPH"
echo "======================================================================"
echo ""

# Step 0: Setup Python virtual environment
echo -e "${BLUE}Step 0: Setting up Python environment...${NC}"

if [ ! -d "$VENV_DIR" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}  ✓ Virtual environment created${NC}"
else
    echo "  ✓ Virtual environment already exists"
fi

# Install/upgrade dependencies
echo "  Installing dependencies..."
"$PIP" install -q --upgrade pip
"$PIP" install -q -r requirements.txt
echo -e "${GREEN}  ✓ Dependencies installed${NC}"
echo ""

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

if ! command -v kg &> /dev/null; then
    echo -e "${RED}✗ kg CLI not found${NC}"
    echo "  Install from: cd ../../../client && ./install.sh"
    exit 1
fi
echo "  ✓ kg CLI found"

if ! command -v jq &> /dev/null; then
    echo -e "${RED}✗ jq not found${NC}"
    echo "  Install with: sudo apt install jq  # or brew install jq"
    exit 1
fi
echo "  ✓ jq found"

# Check gh CLI for PR extraction
if command -v gh &> /dev/null; then
    if gh auth status &>/dev/null; then
        echo "  ✓ gh CLI authenticated"
        GH_AVAILABLE=true
    else
        echo -e "${YELLOW}  ⚠ gh CLI found but not authenticated${NC}"
        echo "    Run: gh auth login"
        GH_AVAILABLE=false
    fi
else
    echo -e "${YELLOW}  ⚠ gh CLI not found (PRs will be skipped)${NC}"
    echo "    Install: https://cli.github.com/"
    GH_AVAILABLE=false
fi

echo -e "${GREEN}✓ Prerequisites checked${NC}"
echo ""

# Step 1: Extract commits (from the beginning)
echo -e "${BLUE}Step 1: Extracting commits from the beginning...${NC}"
"$PYTHON" extract_commits.py --limit 30

commit_count=$(find output/commits -name "*.md" 2>/dev/null | wc -l || echo "0")
echo ""
echo -e "${GREEN}✓ Extracted $commit_count commits${NC}"
echo ""

# Step 2: Extract PRs
if [ "$GH_AVAILABLE" = true ]; then
    echo -e "${BLUE}Step 2: Extracting pull requests...${NC}"
    "$PYTHON" extract_prs.py --limit 10

    pr_count=$(find output/prs -name "*.md" 2>/dev/null | wc -l || echo "0")
    echo ""
    echo -e "${GREEN}✓ Extracted $pr_count PRs${NC}"
    echo ""
else
    echo -e "${YELLOW}Step 2: Skipping PRs (gh not available/authenticated)${NC}"
    echo ""
    pr_count=0
fi

# Step 3: Show summary
echo -e "${BLUE}Step 3: Summary of extracted documents${NC}"
echo ""
echo "  Commits: $commit_count"
echo "  PRs: $pr_count"
echo "  Total: $((commit_count + pr_count))"
echo ""

if [ $commit_count -eq 0 ] && [ $pr_count -eq 0 ]; then
    echo -e "${YELLOW}No new documents to ingest. All caught up!${NC}"
    echo ""
    echo "To re-extract all items, run: ./clean.sh --reset"
    exit 0
fi

if [ $commit_count -gt 0 ]; then
    echo "Sample commit:"
    echo "---"
    head -n 20 "$(find output/commits -name "*.md" | head -1)"
    echo "..."
    echo "---"
    echo ""
fi

read -p "Ingest these documents into the knowledge graph? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Ingestion skipped.${NC}"
    echo ""
    echo "Documents are ready in output/ directory."
    echo "Run './ingest.sh' when ready to ingest."
    exit 0
fi

# Step 4: Ingest
echo ""
echo -e "${BLUE}Step 4: Ingesting into knowledge graph...${NC}"
echo ""
./ingest.sh

echo ""
echo -e "${GREEN}✓ Ingestion complete${NC}"
echo ""

# Step 5: Cleanup prompt
echo ""
read -p "Clean up output files? (keeps state pointers) (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Removing output files...${NC}"
    rm -rf output
    echo -e "${GREEN}✓ Output files removed${NC}"
    echo "  State pointers preserved. Next run will only process new items."
else
    echo "Output files kept in output/ directory."
fi
echo ""

# Step 6: Show statistics
echo -e "${BLUE}Knowledge Graph Statistics${NC}"
echo ""

# Get ontology name from config
ontology=$(jq -r '.repositories[0].ontology' config.json)
echo "Ontology: $ontology"
echo ""

kg database stats

echo ""
echo "======================================================================"
echo -e "${GREEN}COMPLETE!${NC}"
echo "======================================================================"
echo ""
echo "Your git history is now in the knowledge graph!"
echo ""
echo "Try these queries:"
echo "  kg search query \"Apache AGE migration\""
echo "  kg search query \"grounding system\""
echo "  kg search query \"authentication\""
echo "  kg search connect \"commit message concept\" \"ADR document\""
echo ""
echo "Run ./run.sh again anytime - it's idempotent!"
echo "Only new commits/PRs will be processed."
echo ""
