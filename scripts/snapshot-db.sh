#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m'

# Configuration
CONTAINER="knowledge-graph-postgres"
DB_NAME="${POSTGRES_DB:-knowledge_graph}"
DB_USER="${POSTGRES_USER:-admin}"
BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SNAPSHOT_FILE="$BACKUP_DIR/snapshot_${DB_NAME}_${TIMESTAMP}.sql"

# Parse arguments
QUIET=false
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -q|--quiet)
            QUIET=true
            shift
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Create a complete snapshot of the PostgreSQL database"
            echo ""
            echo "Options:"
            echo "  -q, --quiet       Quiet mode (minimal output)"
            echo "  -o, --output FILE Output file path (default: backups/snapshot_YYYYMMDD_HHMMSS.sql)"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Create timestamped snapshot"
            echo "  $0 -o my-backup.sql          # Custom output file"
            echo "  $0 -q                        # Quiet mode"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Use custom output file if specified
if [ -n "$OUTPUT_FILE" ]; then
    SNAPSHOT_FILE="$OUTPUT_FILE"
fi

if [ "$QUIET" = false ]; then
    echo -e "${BLUE}📸 Database Snapshot${NC}"
    echo "========================================"
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo -e "${RED}✗ Database container '$CONTAINER' is not running${NC}"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$(dirname "$SNAPSHOT_FILE")"

if [ "$QUIET" = false ]; then
    echo -e "${YELLOW}Creating snapshot...${NC}"
    echo -e "${GRAY}  Database: $DB_NAME${NC}"
    echo -e "${GRAY}  Container: $CONTAINER${NC}"
    echo -e "${GRAY}  Output: $SNAPSHOT_FILE${NC}"
    echo ""
fi

# Create snapshot using pg_dump (includes all data, schema, AGE graph)
# Use plain SQL format for maximum compatibility and human readability
if docker exec $CONTAINER pg_dump -U $DB_USER -d $DB_NAME \
    --format=plain \
    --no-owner \
    --no-privileges \
    --clean \
    --if-exists \
    > "$SNAPSHOT_FILE" 2>/dev/null; then

    # Get snapshot size
    SNAPSHOT_SIZE=$(du -h "$SNAPSHOT_FILE" | cut -f1)

    if [ "$QUIET" = false ]; then
        echo -e "${GREEN}✓ Snapshot created successfully${NC}"
        echo ""
        echo -e "${BLUE}Snapshot Details:${NC}"
        echo -e "  File: $SNAPSHOT_FILE"
        echo -e "  Size: $SNAPSHOT_SIZE"
        echo ""
        echo -e "${YELLOW}Restore with:${NC}"
        echo -e "  ./scripts/restore-db.sh $SNAPSHOT_FILE"
    else
        echo "$SNAPSHOT_FILE"
    fi

    exit 0
else
    echo -e "${RED}✗ Snapshot failed${NC}"
    echo -e "${YELLOW}Check that the database container is running and healthy${NC}"
    exit 1
fi
