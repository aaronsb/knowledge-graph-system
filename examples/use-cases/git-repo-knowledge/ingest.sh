#!/bin/bash
#
# Ingest git commits and PRs into knowledge graph.
#
# This script batches small documents together for efficient ingestion.
# It's idempotent - tracking what's been ingested in .ingest_state.json
#
# Usage:
#   ./ingest.sh                    # Ingest all new documents
#   ./ingest.sh --batch-size 20    # Custom batch size (commits per batch)
#   ./ingest.sh --reset            # Reset state and re-ingest all
#

set -e  # Exit on error

# Configuration
OUTPUT_DIR="output"
STATE_FILE=".ingest_state.json"
BATCH_SIZE=20  # Number of commits per batch document
AUTO_APPROVE="-y"  # Auto-approve ingestion jobs

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Parse arguments
RESET=false
CLEAN=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --batch-size)
      BATCH_SIZE="$2"
      shift 2
      ;;
    --reset)
      RESET=true
      shift
      ;;
    --clean)
      CLEAN=true
      shift
      ;;
    --no-auto-approve)
      AUTO_APPROVE=""
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--batch-size N] [--reset] [--clean] [--no-auto-approve]"
      exit 1
      ;;
  esac
done

# Initialize or load state
if [ "$RESET" = true ] || [ ! -f "$STATE_FILE" ]; then
    echo "{\"ingested_commits\": [], \"ingested_prs\": [], \"last_run\": null}" > "$STATE_FILE"
    echo -e "${YELLOW}State reset${NC}"
fi

# Load state
INGESTED_COMMITS=$(jq -r '.ingested_commits[]' "$STATE_FILE" 2>/dev/null || echo "")
INGESTED_PRS=$(jq -r '.ingested_prs[]' "$STATE_FILE" 2>/dev/null || echo "")

echo "======================================================================"
echo "GIT REPOSITORY KNOWLEDGE GRAPH INGESTION"
echo "======================================================================"
echo "Batch size: $BATCH_SIZE commits per document"
echo ""

# Function to check if file is already ingested
is_ingested() {
    local file=$1
    local list=$2
    echo "$list" | grep -q "^$file$"
}

# Function to create batched commit document
create_commit_batch() {
    local ontology=$1
    local repo=$2
    local batch_num=$3
    shift 3
    local files=("$@")

    local batch_file="output/batches/${repo}_commits_batch_${batch_num}.md"
    mkdir -p "output/batches"

    # Create batch document header
    cat > "$batch_file" <<EOF
# Git Commits Batch #$batch_num - $repo

This document contains a batch of ${#files[@]} commit messages from the $repo repository.
Each commit is preserved with its full metadata and message.

---

EOF

    # Append each commit
    for file in "${files[@]}"; do
        echo "## Commit: $(basename "$file" .md)" >> "$batch_file"
        echo "" >> "$batch_file"
        # Skip frontmatter (between ---) and append the rest
        awk '/^---$/,/^---$/{if(!/^---$/)next} !/^---$/' "$file" >> "$batch_file"
        echo "" >> "$batch_file"
        echo "---" >> "$batch_file"
        echo "" >> "$batch_file"
    done

    echo "$batch_file"
}

# Ingest commits
echo "Processing commits..."
cd "$OUTPUT_DIR/commits" 2>/dev/null || { echo "No commits directory found"; cd ../..; }

for repo in */ ; do
    if [ -d "$repo" ]; then
        repo_name=$(basename "$repo")
        ontology=$(jq -r ".repositories[] | select(.name == \"$repo_name\") | .ontology" ../../config.json)

        echo ""
        echo "Repository: $repo_name"
        echo "Ontology: $ontology"

        cd "$repo"

        # Get new commits
        new_commits=()
        for commit_file in *.md 2>/dev/null; do
            [ -f "$commit_file" ] || continue

            if ! is_ingested "$commit_file" "$INGESTED_COMMITS"; then
                new_commits+=("$commit_file")
            fi
        done

        if [ ${#new_commits[@]} -eq 0 ]; then
            echo "  No new commits to ingest"
            cd ..
            continue
        fi

        echo "  Found ${#new_commits[@]} new commits"

        # Batch commits
        batch_num=1
        batch=()

        for commit_file in "${new_commits[@]}"; do
            batch+=("$commit_file")

            if [ ${#batch[@]} -ge $BATCH_SIZE ]; then
                # Create batch document
                cd ../../..
                batch_doc=$(create_commit_batch "$ontology" "$repo_name" "$batch_num" "${batch[@]/#/$OUTPUT_DIR/commits/$repo}")

                # Ingest batch
                echo "  Ingesting batch $batch_num (${#batch[@]} commits)..."
                kg ingest file -o "$ontology" $AUTO_APPROVE "$batch_doc" || {
                    echo -e "${RED}  ✗ Ingestion failed${NC}"
                    cd "$OUTPUT_DIR/commits/$repo"
                    continue
                }

                # Mark as ingested
                for f in "${batch[@]}"; do
                    jq ".ingested_commits += [\"$f\"]" "$STATE_FILE" > "${STATE_FILE}.tmp"
                    mv "${STATE_FILE}.tmp" "$STATE_FILE"
                done

                batch=()
                ((batch_num++))
                cd "$OUTPUT_DIR/commits/$repo"
            fi
        done

        # Ingest remaining batch if any
        if [ ${#batch[@]} -gt 0 ]; then
            cd ../../..
            batch_doc=$(create_commit_batch "$ontology" "$repo_name" "$batch_num" "${batch[@]/#/$OUTPUT_DIR/commits/$repo}")

            echo "  Ingesting batch $batch_num (${#batch[@]} commits)..."
            kg ingest file -o "$ontology" $AUTO_APPROVE "$batch_doc" || {
                echo -e "${RED}  ✗ Ingestion failed${NC}"
                cd "$OUTPUT_DIR/commits/$repo"
                continue
            }

            for f in "${batch[@]}"; do
                jq ".ingested_commits += [\"$f\"]" "$STATE_FILE" > "${STATE_FILE}.tmp"
                mv "${STATE_FILE}.tmp" "$STATE_FILE"
            done

            cd "$OUTPUT_DIR/commits/$repo"
        fi

        echo -e "${GREEN}  ✓ Ingested ${#new_commits[@]} commits in $((batch_num)) batches${NC}"
        cd ..
    fi
done

cd ../..

# Ingest PRs (individually, as they're typically longer)
echo ""
echo "Processing pull requests..."
cd "$OUTPUT_DIR/prs" 2>/dev/null || { echo "No prs directory found"; cd ../..; }

for repo in */ ; do
    if [ -d "$repo" ]; then
        repo_name=$(basename "$repo")
        ontology=$(jq -r ".repositories[] | select(.name == \"$repo_name\") | .ontology" ../../config.json)

        echo ""
        echo "Repository: $repo_name"
        echo "Ontology: $ontology"

        cd "$repo"

        new_prs=0
        for pr_file in pr-*.md 2>/dev/null; do
            [ -f "$pr_file" ] || continue

            if ! is_ingested "$pr_file" "$INGESTED_PRS"; then
                # Ingest PR individually
                echo "  Ingesting $pr_file..."
                kg ingest file -o "$ontology" $AUTO_APPROVE "$pr_file" || {
                    echo -e "${RED}  ✗ Ingestion failed${NC}"
                    continue
                }

                # Mark as ingested
                cd ../../..
                jq ".ingested_prs += [\"$pr_file\"]" "$STATE_FILE" > "${STATE_FILE}.tmp"
                mv "${STATE_FILE}.tmp" "$STATE_FILE"
                cd "$OUTPUT_DIR/prs/$repo"

                ((new_prs++))
            fi
        done

        if [ $new_prs -eq 0 ]; then
            echo "  No new PRs to ingest"
        else
            echo -e "${GREEN}  ✓ Ingested $new_prs PRs${NC}"
        fi

        cd ..
    fi
done

cd ../..

# Update last run timestamp
jq ".last_run = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$STATE_FILE" > "${STATE_FILE}.tmp"
mv "${STATE_FILE}.tmp" "$STATE_FILE"

# Cleanup if requested
if [ "$CLEAN" = true ]; then
    echo ""
    echo "======================================================================"
    echo "CLEANUP"
    echo "======================================================================"
    echo ""
    echo -e "${YELLOW}Removing output files (keeping state pointers)...${NC}"
    rm -rf "$OUTPUT_DIR"
    echo -e "${GREEN}✓ Output files removed${NC}"
    echo ""
    echo "State pointers preserved. Next extraction will only process new items."
fi

echo ""
echo "======================================================================"
echo -e "${GREEN}INGESTION COMPLETE${NC}"
echo "======================================================================"
echo ""
echo "Next steps:"
echo "  kg database stats                    # View ontology statistics"
echo "  kg search query \"your search term\"  # Semantic search"
echo ""
echo "Run this script again anytime to ingest new commits/PRs incrementally."
if [ "$CLEAN" != true ]; then
    echo "Use --clean flag to remove output files after ingestion."
fi
