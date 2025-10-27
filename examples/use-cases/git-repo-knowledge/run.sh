#!/bin/bash
#
# Demo: Extract and ingest git history to knowledge graph
#
# This demo shows the complete workflow:
# 1. Extract recent commits
# 2. Extract recent PRs (if GITHUB_TOKEN is set)
# 3. Ingest into knowledge graph
# 4. Query the results
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "======================================================================"
echo "GIT REPOSITORY KNOWLEDGE GRAPH - DEMO"
echo "======================================================================"
echo ""

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

if ! command -v kg &> /dev/null; then
    echo "✗ kg CLI not found. Install from client/ directory"
    exit 1
fi

if ! python3 -c "import git" 2>/dev/null; then
    echo "✗ gitpython not installed"
    echo "  Install with: pip install gitpython"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites met${NC}"
echo ""

# Step 1: Extract commits
echo -e "${BLUE}Step 1: Extracting last 30 commits...${NC}"
python3 extract_commits.py --limit 30

echo ""
echo -e "${GREEN}✓ Commits extracted${NC}"
echo ""

# Step 2: Extract PRs (if token available)
if [ -n "$GITHUB_TOKEN" ]; then
    echo -e "${BLUE}Step 2: Extracting pull requests...${NC}"

    if python3 -c "import github" 2>/dev/null; then
        python3 extract_prs.py --limit 10
        echo ""
        echo -e "${GREEN}✓ PRs extracted${NC}"
    else
        echo -e "${YELLOW}PyGithub not installed. Skipping PRs.${NC}"
        echo "  Install with: pip install PyGithub"
    fi
else
    echo -e "${YELLOW}Step 2: Skipping PRs (no GITHUB_TOKEN set)${NC}"
    echo "  Set token with: export GITHUB_TOKEN='ghp_...'"
fi

echo ""

# Step 3: Show what was extracted
echo -e "${BLUE}Step 3: Review extracted files${NC}"
echo ""

commit_count=$(find output/commits -name "*.md" 2>/dev/null | wc -l)
pr_count=$(find output/prs -name "*.md" 2>/dev/null | wc -l)

echo "Extracted documents:"
echo "  Commits: $commit_count"
echo "  PRs: $pr_count"
echo ""

if [ $commit_count -gt 0 ]; then
    echo "Sample commit:"
    echo "---"
    head -n 20 "$(find output/commits -name "*.md" | head -1)"
    echo "..."
    echo "---"
fi

echo ""
read -p "Press Enter to continue with ingestion..."
echo ""

# Step 4: Ingest
echo -e "${BLUE}Step 4: Ingesting into knowledge graph...${NC}"
echo ""
./ingest.sh

echo ""
echo -e "${GREEN}✓ Ingestion complete${NC}"
echo ""

# Step 5: Query
echo -e "${BLUE}Step 5: Query the knowledge graph${NC}"
echo ""

# Get ontology name from config
ontology=$(jq -r '.repositories[0].ontology' config.json)

echo "Ontology: $ontology"
echo ""

echo "Database statistics:"
kg database stats

echo ""
echo "======================================================================"
echo -e "${GREEN}DEMO COMPLETE${NC}"
echo "======================================================================"
echo ""
echo "Your git history is now in the knowledge graph!"
echo ""
echo "Try these queries:"
echo "  kg search query \"Apache AGE migration\""
echo "  kg search query \"grounding system\""
echo "  kg search query \"authentication\""
echo ""
echo "Run this demo again anytime - it's idempotent!"
echo "Only new commits/PRs will be processed."
echo ""
