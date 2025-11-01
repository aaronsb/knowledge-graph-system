#!/bin/bash
set -e

# ============================================================================
# Database Migration Runner
# ============================================================================
# Applies pending schema migrations to PostgreSQL database
# ADR-040: Database Schema Migration Management
# ============================================================================

# Colors (matching existing script style)
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
CONTAINER="knowledge-graph-postgres"
DB_USER="admin"
DB_NAME="knowledge_graph"
MIGRATIONS_DIR="schema/migrations"

# Parse arguments
DRY_RUN=false
AUTO_CONFIRM=false
VERBOSE=false

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
        -y|--yes)
            AUTO_CONFIRM=true
            ;;
        -v|--verbose)
            VERBOSE=true
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run       Show what would be applied without making changes"
            echo "  -y, --yes       Skip confirmation prompt"
            echo "  -v, --verbose   Show detailed migration SQL"
            echo "  -h, --help      Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Interactive mode with confirmation"
            echo "  $0 --dry-run          # Preview pending migrations"
            echo "  $0 -y                 # Apply migrations without confirmation"
            echo "  $0 -y --verbose       # Apply with detailed output"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Header
if [ "$DRY_RUN" = true ]; then
    echo -e "${CYAN}📦 Database Migration Runner (DRY RUN)${NC}"
else
    echo -e "${BLUE}📦 Database Migration Runner${NC}"
fi
echo "========================================"
echo ""

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q $CONTAINER; then
    echo -e "${RED}✗ Database container not running${NC}"
    echo -e "${YELLOW}Start it with:${NC} ./scripts/start-db.sh"
    exit 1
fi

# Ensure schema_migrations table exists
if [ "$VERBOSE" = true ]; then
    echo -e "${GRAY}Ensuring schema_migrations table exists...${NC}"
fi

docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -c \
  "CREATE TABLE IF NOT EXISTS public.schema_migrations (
      version INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      applied_at TIMESTAMP NOT NULL DEFAULT NOW()
  );" > /dev/null 2>&1

# Get applied migrations
APPLIED=$(docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c \
  "SELECT version FROM public.schema_migrations ORDER BY version" 2>/dev/null || echo "")

if [ -z "$APPLIED" ]; then
    echo -e "${YELLOW}⚠️  No migrations applied yet${NC}"
    APPLIED_LIST="(none)"
else
    APPLIED_LIST=$(echo "$APPLIED" | tr '\n' ', ' | sed 's/,$//')
    echo -e "${GREEN}✓ Applied migrations:${NC} $APPLIED_LIST"
fi
echo ""

# Find pending migrations
PENDING_MIGRATIONS=()
PENDING_COUNT=0

if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo -e "${YELLOW}⚠️  Migrations directory not found: $MIGRATIONS_DIR${NC}"
    echo -e "${GRAY}No migrations to apply${NC}"
    exit 0
fi

# Scan for migration files
for migration_file in "$MIGRATIONS_DIR"/*.sql; do
    [ -f "$migration_file" ] || continue

    # Extract version from filename (001_baseline.sql → 001)
    FILENAME=$(basename "$migration_file")
    VERSION=$(echo "$FILENAME" | cut -d_ -f1)
    NAME=$(echo "$FILENAME" | sed 's/^[0-9]*_//' | sed 's/\.sql$//')

    # Strip leading zeros for comparison with INTEGER database column
    VERSION_NUM=$((10#$VERSION))

    # Check if already applied
    if echo "$APPLIED" | grep -q "^$VERSION_NUM$"; then
        if [ "$VERBOSE" = true ]; then
            echo -e "${GRAY}✓ Migration $VERSION ($NAME) - already applied${NC}"
        fi
        continue
    fi

    # Pending migration found
    PENDING_MIGRATIONS+=("$VERSION|$NAME|$migration_file")
    PENDING_COUNT=$((PENDING_COUNT + 1))
done

# Show summary
echo -e "${BLUE}Migration Status:${NC}"
echo -e "  Applied:  ${GREEN}$(echo "$APPLIED" | wc -l)${NC} migration(s)"
echo -e "  Pending:  ${YELLOW}$PENDING_COUNT${NC} migration(s)"
echo ""

if [ $PENDING_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ Database is up to date - no pending migrations${NC}"
    exit 0
fi

# Show pending migrations
echo -e "${YELLOW}Pending Migrations:${NC}"
for pending in "${PENDING_MIGRATIONS[@]}"; do
    IFS='|' read -r VERSION NAME FILE <<< "$pending"
    echo -e "  ${CYAN}→ Migration $VERSION${NC} - $NAME"
    if [ "$VERBOSE" = true ]; then
        echo -e "${GRAY}    File: $FILE${NC}"
    fi
done
echo ""

# Dry run mode - exit after showing what would be applied
if [ "$DRY_RUN" = true ]; then
    echo -e "${CYAN}Dry run mode - no changes will be made${NC}"
    echo -e "${GRAY}Run without --dry-run to apply these migrations${NC}"
    exit 0
fi

# Check if database has data and offer snapshot
if [ "$AUTO_CONFIRM" = false ]; then
    # Count tables in kg_api schema (simple proxy for "has data")
    TABLE_COUNT=$(docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c \
      "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'kg_api'" 2>/dev/null || echo "0")

    if [ "$TABLE_COUNT" -gt 0 ]; then
        echo -e "${BLUE}💾 Database Snapshot${NC}"
        echo -e "${GRAY}Your database contains data ($TABLE_COUNT tables in kg_api schema)${NC}"
        echo -e "${GRAY}It's recommended to create a snapshot before applying migrations${NC}"
        echo ""
        read -p "$(echo -e ${YELLOW}Create snapshot before migrating? [Y/n]:${NC} )" -n 1 -r
        echo

        # Default to Yes if Enter is pressed (empty response)
        if [[ -z $REPLY ]] || [[ $REPLY =~ ^[Yy]$ ]]; then
            echo ""
            if [ -f "./scripts/snapshot-db.sh" ]; then
                ./scripts/snapshot-db.sh
                echo ""
            else
                echo -e "${RED}✗ Snapshot script not found at ./scripts/snapshot-db.sh${NC}"
                echo -e "${YELLOW}Continuing without snapshot...${NC}"
                echo ""
            fi
        fi
        echo ""
    fi
fi

# Confirmation prompt (unless -y flag)
if [ "$AUTO_CONFIRM" = false ]; then
    echo -e "${YELLOW}Apply $PENDING_COUNT migration(s)?${NC}"
    read -p "$(echo -e ${YELLOW}Continue? [y/N]:${NC} )" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Cancelled${NC}"
        exit 0
    fi
    echo ""
fi

# Apply migrations
APPLIED_COUNT=0
FAILED_COUNT=0

for pending in "${PENDING_MIGRATIONS[@]}"; do
    IFS='|' read -r VERSION NAME FILE <<< "$pending"

    # Strip leading zeros for database operations
    VERSION_NUM=$((10#$VERSION))

    echo -e "${YELLOW}→ Applying migration $VERSION${NC} ($NAME)..."

    # Show SQL if verbose
    if [ "$VERBOSE" = true ]; then
        echo -e "${GRAY}----------------------------------------${NC}"
        cat "$FILE" | grep -v "^--" | grep -v "^$" | head -20 | sed 's/^/  /'
        echo -e "${GRAY}----------------------------------------${NC}"
    fi

    # Apply migration (capture output to detect errors)
    MIGRATION_OUTPUT=$(docker exec -i $CONTAINER psql -U $DB_USER -d $DB_NAME < "$FILE" 2>&1)
    MIGRATION_EXIT_CODE=$?

    # Show output in verbose mode
    if [ "$VERBOSE" = true ]; then
        echo -e "${GRAY}$MIGRATION_OUTPUT${NC}"
    fi

    # Check for errors (either non-zero exit or ERROR/ROLLBACK in output)
    if [ $MIGRATION_EXIT_CODE -ne 0 ] || echo "$MIGRATION_OUTPUT" | grep -qi "ERROR:\|ROLLBACK"; then
        echo -e "${RED}  ✗ Migration $VERSION failed${NC}"
        FAILED_COUNT=$((FAILED_COUNT + 1))

        # Show error details
        echo -e "${RED}Error details:${NC}"
        echo "$MIGRATION_OUTPUT" | grep -i "ERROR:\|ROLLBACK\|LINE" | sed 's/^/  /'

        echo ""
        echo -e "${RED}✗ Migration $VERSION failed - stopping${NC}"
        echo -e "${YELLOW}Fix the migration and try again${NC}"
        exit 1
    fi

    echo -e "${GREEN}  ✅ Migration $VERSION applied successfully${NC}"
    APPLIED_COUNT=$((APPLIED_COUNT + 1))

    # Verify it was recorded in schema_migrations (use VERSION_NUM for INTEGER comparison)
    RECORDED=$(docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c \
      "SELECT version FROM public.schema_migrations WHERE version = $VERSION_NUM" 2>/dev/null || echo "")

    if [ -z "$RECORDED" ]; then
        echo -e "${YELLOW}  ⚠️  Warning: Migration $VERSION not recorded in schema_migrations table${NC}"
        echo -e "${GRAY}     Migration may not have included INSERT statement${NC}"
    fi

    echo ""
done

# Final summary
echo "========================================"
if [ $FAILED_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ Migration complete!${NC}"
    echo -e "   Applied: ${GREEN}$APPLIED_COUNT${NC} migration(s)"

    # Show current migration state
    CURRENT=$(docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c \
      "SELECT MAX(version) FROM public.schema_migrations" 2>/dev/null || echo "?")
    echo -e "   Current schema version: ${CYAN}$CURRENT${NC}"
else
    echo -e "${RED}✗ Migration failed${NC}"
    echo -e "   Applied: $APPLIED_COUNT"
    echo -e "   Failed:  $FAILED_COUNT"
    exit 1
fi
