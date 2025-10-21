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

# Parse arguments
AUTO_CONFIRM=false
SNAPSHOT_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -y|--yes)
            AUTO_CONFIRM=true
            shift
            ;;
        -l|--list)
            echo -e "${BLUE}📦 Available Snapshots${NC}"
            echo "========================================"
            if [ -d "$BACKUP_DIR" ] && [ "$(ls -A $BACKUP_DIR/*.sql 2>/dev/null)" ]; then
                ls -lht $BACKUP_DIR/*.sql | awk '{print "  " $9 "  (" $5 ")"}'
            else
                echo -e "${GRAY}  No snapshots found in $BACKUP_DIR/${NC}"
            fi
            echo ""
            exit 0
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS] <snapshot-file>"
            echo ""
            echo "Restore database from a snapshot file"
            echo ""
            echo "Options:"
            echo "  -y, --yes         Auto-confirm (skip confirmation prompt)"
            echo "  -l, --list        List available snapshots"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "Arguments:"
            echo "  snapshot-file     Path to snapshot file to restore"
            echo ""
            echo "Examples:"
            echo "  $0 -l                                    # List snapshots"
            echo "  $0 backups/snapshot_20251021_120000.sql # Restore specific snapshot"
            echo "  $0 -y my-backup.sql                      # Auto-confirm restore"
            exit 0
            ;;
        -*)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
        *)
            SNAPSHOT_FILE="$1"
            shift
            ;;
    esac
done

# Require snapshot file
if [ -z "$SNAPSHOT_FILE" ]; then
    echo -e "${RED}Error: Snapshot file required${NC}"
    echo ""
    echo "Usage: $0 <snapshot-file>"
    echo ""
    echo -e "${YELLOW}List available snapshots:${NC}"
    echo "  $0 --list"
    echo ""
    exit 1
fi

# Check if snapshot file exists
if [ ! -f "$SNAPSHOT_FILE" ]; then
    echo -e "${RED}✗ Snapshot file not found: $SNAPSHOT_FILE${NC}"
    echo ""
    echo -e "${YELLOW}List available snapshots:${NC}"
    echo "  $0 --list"
    exit 1
fi

echo -e "${BLUE}🔄 Database Restore${NC}"
echo "========================================"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo -e "${RED}✗ Database container '$CONTAINER' is not running${NC}"
    echo -e "${YELLOW}Start it with: ./scripts/start-db.sh${NC}"
    exit 1
fi

# Show restore details
SNAPSHOT_SIZE=$(du -h "$SNAPSHOT_FILE" | cut -f1)
echo -e "${YELLOW}Restore Details:${NC}"
echo -e "  Source: $SNAPSHOT_FILE"
echo -e "  Size: $SNAPSHOT_SIZE"
echo -e "  Target database: $DB_NAME"
echo ""

# Warning about data loss
echo -e "${RED}⚠️  WARNING: This will REPLACE all data in $DB_NAME${NC}"
echo -e "${GRAY}   All existing concepts, relationships, and data will be lost${NC}"
echo ""

# Confirmation prompt (unless -y flag)
if [ "$AUTO_CONFIRM" = false ]; then
    read -p "$(echo -e ${YELLOW}Continue with restore? [y/N]:${NC} )" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Restore cancelled${NC}"
        exit 0
    fi
    echo ""
fi

echo -e "${YELLOW}Restoring database...${NC}"

# Restore snapshot (snapshot includes DROP/CREATE commands with --clean --if-exists)
if docker exec -i $CONTAINER psql -U $DB_USER -d $DB_NAME < "$SNAPSHOT_FILE" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Database restored successfully${NC}"
    echo ""

    # Show schema version
    SCHEMA_VERSION=$(docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c \
      "SELECT MAX(version) FROM public.schema_migrations" 2>/dev/null || echo "unknown")

    echo -e "${BLUE}Restored Database:${NC}"
    echo -e "  Schema version: $SCHEMA_VERSION"

    # Show concept count if available
    CONCEPT_COUNT=$(docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c \
      "SELECT COUNT(*) FROM ag_catalog.ag_label WHERE name='Concept'" 2>/dev/null || echo "0")

    if [ "$CONCEPT_COUNT" != "0" ]; then
        echo -e "  Concepts: $CONCEPT_COUNT"
    fi

    echo ""
    echo -e "${GREEN}✓ Restore complete${NC}"
else
    echo -e "${RED}✗ Restore failed${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "  1. Check snapshot file is valid SQL"
    echo "  2. Verify database container is healthy"
    echo "  3. Check Docker logs: docker logs $CONTAINER"
    exit 1
fi
