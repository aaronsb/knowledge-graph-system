#!/bin/bash
# ============================================================================
# migrate-api-structure.sh - Rename api/api/ to api/app/
# ============================================================================
#
# This is a throwaway script for restructuring the API module.
# Run, test, revert if needed, iterate until clean.
#
# Usage:
#   ./scripts/migrate-api-structure.sh          # Dry run (show what would change)
#   ./scripts/migrate-api-structure.sh --apply  # Actually make changes
#   ./scripts/migrate-api-structure.sh --revert # Undo changes (git checkout)
#
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

OLD_NAME="api.api"
NEW_NAME="api.app"
OLD_DIR="api/api"
NEW_DIR="api/app"

# ============================================================================
# Functions
# ============================================================================

count_occurrences() {
    local pattern="$1"
    grep -r --include="*.py" --include="Dockerfile*" --include="*.yml" --include="*.yaml" \
        -l "$pattern" "$PROJECT_ROOT" 2>/dev/null | wc -l
}

list_files_with_pattern() {
    local pattern="$1"
    grep -r --include="*.py" --include="Dockerfile*" --include="*.yml" --include="*.yaml" \
        -l "$pattern" "$PROJECT_ROOT" 2>/dev/null || true
}

dry_run() {
    echo -e "${BLUE}=== DRY RUN: api/api → api/app migration ===${NC}"
    echo ""

    # Check if already migrated
    if [ -d "$PROJECT_ROOT/$NEW_DIR" ]; then
        echo -e "${YELLOW}⚠ $NEW_DIR already exists - migration may have been applied${NC}"
        return
    fi

    if [ ! -d "$PROJECT_ROOT/$OLD_DIR" ]; then
        echo -e "${RED}✗ $OLD_DIR not found - nothing to migrate${NC}"
        return
    fi

    echo -e "${GREEN}✓ $OLD_DIR exists${NC}"
    echo ""

    # Count files to update
    local py_count=$(grep -r --include="*.py" -l "$OLD_NAME" "$PROJECT_ROOT" 2>/dev/null | wc -l)
    local docker_count=$(grep -r --include="Dockerfile*" -l "$OLD_NAME" "$PROJECT_ROOT" 2>/dev/null | wc -l)
    local compose_count=$(grep -r --include="*.yml" --include="*.yaml" -l "$OLD_NAME" "$PROJECT_ROOT" 2>/dev/null | wc -l)

    echo -e "${BLUE}Files to update:${NC}"
    echo "  Python files:    $py_count"
    echo "  Dockerfiles:     $docker_count"
    echo "  Compose files:   $compose_count"
    echo ""

    echo -e "${BLUE}Python files with '$OLD_NAME':${NC}"
    list_files_with_pattern "$OLD_NAME" | grep "\.py$" | head -20
    local total=$(list_files_with_pattern "$OLD_NAME" | grep "\.py$" | wc -l)
    [ "$total" -gt 20 ] && echo "  ... and $((total - 20)) more"
    echo ""

    echo -e "${BLUE}Docker/Compose files:${NC}"
    list_files_with_pattern "$OLD_NAME" | grep -E "(Dockerfile|\.ya?ml)$"
    echo ""

    echo -e "${YELLOW}Run with --apply to make changes${NC}"
}

apply_migration() {
    echo -e "${BLUE}=== APPLYING: api/api → api/app migration ===${NC}"
    echo ""

    # Safety checks
    if [ -d "$PROJECT_ROOT/$NEW_DIR" ]; then
        echo -e "${RED}✗ $NEW_DIR already exists - aborting${NC}"
        exit 1
    fi

    if [ ! -d "$PROJECT_ROOT/$OLD_DIR" ]; then
        echo -e "${RED}✗ $OLD_DIR not found - nothing to migrate${NC}"
        exit 1
    fi

    # Step 1: Rename directory
    echo -e "${BLUE}→ Renaming $OLD_DIR to $NEW_DIR...${NC}"
    mv "$PROJECT_ROOT/$OLD_DIR" "$PROJECT_ROOT/$NEW_DIR"
    echo -e "${GREEN}✓ Directory renamed${NC}"

    # Step 2: Update Python imports
    echo -e "${BLUE}→ Updating Python imports...${NC}"
    find "$PROJECT_ROOT" -name "*.py" -type f | while read file; do
        if grep -q "$OLD_NAME" "$file" 2>/dev/null; then
            sed -i "s/$OLD_NAME/$NEW_NAME/g" "$file"
            echo "  Updated: ${file#$PROJECT_ROOT/}"
        fi
    done
    echo -e "${GREEN}✓ Python imports updated${NC}"

    # Step 3: Update Dockerfiles
    echo -e "${BLUE}→ Updating Dockerfiles...${NC}"
    find "$PROJECT_ROOT" -name "Dockerfile*" -type f | while read file; do
        if grep -q "$OLD_NAME" "$file" 2>/dev/null; then
            sed -i "s/$OLD_NAME/$NEW_NAME/g" "$file"
            echo "  Updated: ${file#$PROJECT_ROOT/}"
        fi
    done
    echo -e "${GREEN}✓ Dockerfiles updated${NC}"

    # Step 4: Update compose files
    echo -e "${BLUE}→ Updating compose files...${NC}"
    find "$PROJECT_ROOT" -name "*.yml" -o -name "*.yaml" -type f 2>/dev/null | while read file; do
        if grep -q "$OLD_NAME" "$file" 2>/dev/null; then
            sed -i "s/$OLD_NAME/$NEW_NAME/g" "$file"
            echo "  Updated: ${file#$PROJECT_ROOT/}"
        fi
    done
    echo -e "${GREEN}✓ Compose files updated${NC}"

    echo ""
    echo -e "${GREEN}=== Migration complete ===${NC}"
    echo ""
    echo -e "${BLUE}Validation steps:${NC}"
    echo "  1. python -c 'from api.app.main import app'"
    echo "  2. ./operator.sh start"
    echo "  3. curl localhost:8000/health"
    echo ""
    echo -e "${YELLOW}If something broke, run: ./scripts/migrate-api-structure.sh --revert${NC}"
}

revert_migration() {
    echo -e "${BLUE}=== REVERTING: api/app → api/api ===${NC}"
    echo ""

    echo -e "${YELLOW}This will discard all changes to api/ and docker/ directories${NC}"
    echo ""

    # Git checkout to revert
    echo -e "${BLUE}→ Reverting with git checkout...${NC}"
    cd "$PROJECT_ROOT"
    git checkout -- api/ docker/ 2>/dev/null || true

    # Check if new dir exists and old doesn't (partial migration)
    if [ -d "$PROJECT_ROOT/$NEW_DIR" ] && [ ! -d "$PROJECT_ROOT/$OLD_DIR" ]; then
        echo -e "${BLUE}→ Renaming $NEW_DIR back to $OLD_DIR...${NC}"
        mv "$PROJECT_ROOT/$NEW_DIR" "$PROJECT_ROOT/$OLD_DIR"
    fi

    echo -e "${GREEN}✓ Reverted${NC}"
}

# ============================================================================
# Main
# ============================================================================

case "${1:-}" in
    --apply)
        apply_migration
        ;;
    --revert)
        revert_migration
        ;;
    *)
        dry_run
        ;;
esac
