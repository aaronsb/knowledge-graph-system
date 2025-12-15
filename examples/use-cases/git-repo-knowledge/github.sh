#!/bin/bash
#
# GitHub Repository Knowledge Graph Extractor
#
# Extracts commits and PRs from a GitHub repository and ingests them
# into the knowledge graph. Tracks progress to enable incremental updates.
#
# Usage:
#   ./github.sh                     # Show help
#   ./github.sh preview             # Preview what would be extracted
#   ./github.sh run                 # Extract + ingest next batch
#   ./github.sh run --all           # YOLO: Extract + ingest EVERYTHING
#   ./github.sh run --prs           # Only PRs
#   ./github.sh run --commits       # Only commits
#   ./github.sh status              # Show current progress
#   ./github.sh reset               # Reset to start from beginning
#   ./github.sh clean               # Remove output files
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

VENV_DIR="venv"
PYTHON="${VENV_DIR}/bin/python"

# ============================================================================
# Helper Functions
# ============================================================================

setup_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${BLUE}Setting up Python environment...${NC}"
        python3 -m venv "$VENV_DIR"
        "${VENV_DIR}/bin/pip" install -q --upgrade pip
        "${VENV_DIR}/bin/pip" install -q -r requirements.txt
        echo -e "${GREEN}✓ Environment ready${NC}"
        echo ""
    fi
}

check_prereqs() {
    local missing=false

    if ! command -v kg &> /dev/null; then
        echo -e "${YELLOW}⚠ kg CLI not found - ingestion will fail${NC}"
        echo "  Install: cd ../../../client && ./install.sh"
        missing=true
    fi

    if ! command -v jq &> /dev/null; then
        echo -e "${RED}✗ jq required but not found${NC}"
        echo "  Install: sudo apt install jq  # or brew install jq"
        exit 1
    fi

    if ! command -v gh &> /dev/null; then
        echo -e "${YELLOW}⚠ gh CLI not found - PR extraction will be skipped${NC}"
        echo "  Install: https://cli.github.com/"
    elif ! gh auth status &>/dev/null; then
        echo -e "${YELLOW}⚠ gh CLI not authenticated - PR extraction will be skipped${NC}"
        echo "  Run: gh auth login"
    fi

    if [ "$missing" = true ]; then
        echo ""
    fi
}

show_status() {
    echo "======================================================================"
    echo -e "${CYAN}STATUS${NC}"
    echo "======================================================================"
    echo ""

    # Show config pointers
    if [ -f "config.json" ]; then
        local last_commit=$(jq -r '.repositories[0].last_commit // "none"' config.json)
        local last_pr=$(jq -r '.repositories[0].last_pr // 0' config.json)
        local repo=$(jq -r '.repositories[0].github_repo // "unknown"' config.json)
        local ontology=$(jq -r '.repositories[0].ontology // "unknown"' config.json)

        echo "Repository: $repo"
        echo "Ontology: $ontology"
        echo ""
        echo "Progress:"
        if [ "$last_commit" = "none" ] || [ "$last_commit" = "null" ]; then
            echo "  Commits: Starting from beginning"
        else
            echo "  Commits: Up to ${last_commit:0:8}"
        fi
        echo "  PRs: Up to #$last_pr"
    else
        echo -e "${RED}No config.json found${NC}"
    fi

    echo ""

    # Show output counts
    local commit_count=$(find output/commits -name "*.md" 2>/dev/null | wc -l || echo "0")
    local pr_count=$(find output/prs -name "*.md" 2>/dev/null | wc -l || echo "0")

    if [ "$commit_count" -gt 0 ] || [ "$pr_count" -gt 0 ]; then
        echo "Pending ingestion:"
        echo "  Commits: $commit_count"
        echo "  PRs: $pr_count"
    else
        echo "No pending documents in output/"
    fi
    echo ""
}

do_reset() {
    echo -e "${YELLOW}Resetting extraction pointers...${NC}"
    if [ -f "config.json" ]; then
        jq '.repositories[0].last_commit = null | .repositories[0].last_pr = 0' config.json > config.json.tmp
        mv config.json.tmp config.json
        echo -e "${GREEN}✓ Pointers reset to beginning${NC}"
    else
        echo -e "${RED}No config.json found${NC}"
        exit 1
    fi
}

do_clean() {
    if [ -d "output" ]; then
        local file_count=$(find output -type f | wc -l)
        echo "Removing $file_count files from output/..."
        rm -rf output
        echo -e "${GREEN}✓ Output cleaned${NC}"
    else
        echo "No output/ directory to clean"
    fi
}

do_ingest() {
    local output_dir="output"
    local total_ingested=0

    # Check if output directory exists
    if [ ! -d "$output_dir" ]; then
        echo -e "${YELLOW}No output directory found${NC}"
        return 0
    fi

    # Ingest commits
    if [ -d "$output_dir/commits" ]; then
        echo "Ingesting commits..."

        for repo in "$output_dir/commits"/*/ ; do
            if [ -d "$repo" ]; then
                local repo_name=$(basename "$repo")
                local base_ontology=$(jq -r ".repositories[] | select(.name == \"$repo_name\") | .ontology" config.json)
                local ontology="${base_ontology}-Commits"
                local file_count=$(find "$repo" -name "*.md" -type f | wc -l)

                if [ "$file_count" -gt 0 ]; then
                    echo "  $ontology: $file_count files"
                    if kg ingest directory -o "$ontology" "$repo"; then
                        echo -e "${GREEN}  ✓ Ingested${NC}"
                        ((total_ingested += file_count))
                    else
                        echo -e "${RED}  ✗ Failed${NC}"
                    fi
                fi
            fi
        done
    fi

    # Ingest PRs
    if [ -d "$output_dir/prs" ]; then
        echo "Ingesting PRs..."

        for repo in "$output_dir/prs"/*/ ; do
            if [ -d "$repo" ]; then
                local repo_name=$(basename "$repo")
                local base_ontology=$(jq -r ".repositories[] | select(.name == \"$repo_name\") | .ontology" config.json)
                local ontology="${base_ontology}-PRs"
                local file_count=$(find "$repo" -name "*.md" -type f | wc -l)

                if [ "$file_count" -gt 0 ]; then
                    echo "  $ontology: $file_count files"
                    if kg ingest directory -o "$ontology" "$repo"; then
                        echo -e "${GREEN}  ✓ Ingested${NC}"
                        ((total_ingested += file_count))
                    else
                        echo -e "${RED}  ✗ Failed${NC}"
                    fi
                fi
            fi
        done
    fi

    echo ""
    echo "Total ingested: $total_ingested documents"
}

do_preview() {
    local limit_arg="$1"
    local do_commits="$2"
    local do_prs="$3"

    echo "======================================================================"
    echo -e "${YELLOW}PREVIEW${NC} - What would be extracted"
    echo "======================================================================"
    echo ""

    setup_venv

    # Preview commits
    if [ "$do_commits" = "true" ]; then
        echo -e "${BLUE}Commits:${NC}"
        "$PYTHON" extract_commits.py $limit_arg
        echo ""
    fi

    # Preview PRs
    if [ "$do_prs" = "true" ]; then
        if command -v gh &> /dev/null && gh auth status &>/dev/null; then
            echo -e "${BLUE}Pull Requests:${NC}"
            "$PYTHON" extract_prs.py $limit_arg
        fi
        echo ""
    fi

    echo "======================================================================"
    echo "To extract: ./github.sh run"
    echo "======================================================================"
}

do_run() {
    local limit_arg="$1"
    local yolo="$2"
    local do_commits="$3"
    local do_prs="$4"

    echo "======================================================================"
    if [ -n "$yolo" ]; then
        echo -e "${RED}YOLO MODE${NC} - Extracting ALL remaining items"
    else
        echo -e "${GREEN}BATCH MODE${NC} - Extracting next batch"
    fi
    echo "======================================================================"
    echo ""

    setup_venv

    # Extract commits
    if [ "$do_commits" = "true" ]; then
        echo -e "${BLUE}Extracting commits...${NC}"
        "$PYTHON" extract_commits.py $limit_arg $yolo --confirm
        echo ""
    fi

    # Extract PRs
    if [ "$do_prs" = "true" ]; then
        if command -v gh &> /dev/null && gh auth status &>/dev/null; then
            echo -e "${BLUE}Extracting PRs...${NC}"
            "$PYTHON" extract_prs.py $limit_arg --confirm
        else
            echo -e "${YELLOW}Skipping PRs (gh CLI not available/authenticated)${NC}"
        fi
        echo ""
    fi

    # Check what was extracted
    local commit_count=$(find output/commits -name "*.md" 2>/dev/null | wc -l || echo "0")
    local pr_count=$(find output/prs -name "*.md" 2>/dev/null | wc -l || echo "0")
    local total=$((commit_count + pr_count))

    if [ "$total" -eq 0 ]; then
        echo -e "${GREEN}All caught up! No new items to process.${NC}"
        exit 0
    fi

    echo "Extracted: $commit_count commits, $pr_count PRs"
    echo ""

    # Ingest
    echo -e "${BLUE}Ingesting into knowledge graph...${NC}"
    do_ingest
    echo ""

    # Clean up output directory after successful ingestion
    # Files are either queued (being processed) or duplicates (already in system)
    # Either way, we don't need the local copies anymore
    if [ -d "output" ]; then
        echo -e "${BLUE}Cleaning up output files...${NC}"
        rm -rf output
        echo -e "${GREEN}✓ Output cleaned${NC}"
        echo ""
    fi

    # Show results
    echo -e "${BLUE}Results:${NC}"
    kg database stats 2>/dev/null || echo "(kg CLI not available for stats)"
    echo ""

    # Done
    echo "======================================================================"
    echo -e "${GREEN}DONE!${NC}"
    echo "======================================================================"
    echo ""
    echo "Run again to process more items incrementally."
}

show_help() {
    echo "GitHub Repository Knowledge Graph Extractor"
    echo ""
    echo "Extracts commits and PRs from a GitHub repo, ingests into knowledge graph."
    echo "Progress is tracked - each run continues where the last left off."
    echo ""
    echo "Usage: ./github.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  preview   Show what would be extracted (dry run)"
    echo "  run       Extract and ingest into knowledge graph"
    echo "  ingest    Ingest already-extracted files in output/"
    echo "  status    Show current progress and pointers"
    echo "  reset     Reset pointers to start from beginning"
    echo "  clean     Remove output files"
    echo ""
    echo "Options for 'preview' and 'run':"
    echo "  --all       YOLO mode: process ALL remaining items"
    echo "  --commits   Only commits (skip PRs)"
    echo "  --prs       Only PRs (skip commits)"
    echo "  --limit N   Batch size per type (default: 50)"
    echo ""
    echo "Examples:"
    echo "  ./github.sh preview             # See what would be extracted"
    echo "  ./github.sh run                 # Extract + ingest next batch"
    echo "  ./github.sh run --all           # YOLO: process everything"
    echo "  ./github.sh run --prs --limit 20"
    echo "  ./github.sh status              # Check progress"
    echo "  ./github.sh reset               # Start over from beginning"
}

# ============================================================================
# Main
# ============================================================================

COMMAND=""
LIMIT_ARG=""
YOLO=""
DO_COMMITS="true"
DO_PRS="true"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        run)
            COMMAND="run"
            shift
            ;;
        preview)
            COMMAND="preview"
            shift
            ;;
        ingest)
            COMMAND="ingest"
            shift
            ;;
        status)
            COMMAND="status"
            shift
            ;;
        reset)
            COMMAND="reset"
            shift
            ;;
        clean)
            COMMAND="clean"
            shift
            ;;
        --all)
            YOLO="--all"
            shift
            ;;
        --commits)
            DO_COMMITS="true"
            DO_PRS="false"
            shift
            ;;
        --prs)
            DO_COMMITS="false"
            DO_PRS="true"
            shift
            ;;
        --limit)
            LIMIT_ARG="--limit $2"
            shift 2
            ;;
        --help|-h|help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage"
            exit 1
            ;;
    esac
done

# Execute command
case "$COMMAND" in
    "")
        show_help
        ;;
    preview)
        check_prereqs
        do_preview "$LIMIT_ARG" "$DO_COMMITS" "$DO_PRS"
        ;;
    run)
        check_prereqs
        do_run "$LIMIT_ARG" "$YOLO" "$DO_COMMITS" "$DO_PRS"
        ;;
    ingest)
        check_prereqs
        do_ingest
        ;;
    status)
        show_status
        ;;
    reset)
        do_reset
        ;;
    clean)
        do_clean
        ;;
esac
