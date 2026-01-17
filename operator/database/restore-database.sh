#!/bin/bash
# ============================================================================
# Restore Knowledge Graph Database
# ============================================================================
# Restores full database from binary backup (created by backup-database.sh)
# Uses pg_restore for custom format dumps
# ============================================================================

set -e

# Colors for output
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

# Project root (two levels up from operator/database/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Source common functions for container name resolution
if [ -f "$PROJECT_ROOT/operator/lib/common.sh" ]; then
    source "$PROJECT_ROOT/operator/lib/common.sh"
    CONTAINER=$(get_container_name postgres)
else
    CONTAINER="knowledge-graph-postgres"
fi

# Configuration
DB_NAME="${POSTGRES_DB:-knowledge_graph}"
DB_USER="${POSTGRES_USER:-admin}"
BACKUP_DIR="$PROJECT_ROOT/backups"

# Parse arguments
AUTO_CONFIRM=false
BACKUP_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -y|--yes)
            AUTO_CONFIRM=true
            shift
            ;;
        -l|--list)
            echo ""
            echo -e "${BOLD}Available Backups${NC}"
            echo "================="
            echo ""
            if [ -d "$BACKUP_DIR" ] && ls -1 "$BACKUP_DIR"/*.dump >/dev/null 2>&1; then
                ls -lht "$BACKUP_DIR"/*.dump | while read -r line; do
                    size=$(echo "$line" | awk '{print $5}')
                    file=$(echo "$line" | awk '{print $9}')
                    basename=$(basename "$file")
                    echo -e "  ${BLUE}$basename${NC} (${GREEN}$size${NC})"
                done
            else
                echo -e "  ${YELLOW}No backups found in $BACKUP_DIR/${NC}"
                echo -e "  Create backup with: ${BLUE}./scripts/database/backup-database.sh${NC}"
            fi
            echo ""
            exit 0
            ;;
        -h|--help)
            echo ""
            echo -e "${BOLD}Restore Knowledge Graph Database${NC}"
            echo "=================================="
            echo ""
            echo "Restores database from binary backup created by backup-database.sh"
            echo ""
            echo -e "${BLUE}Usage:${NC}"
            echo "  $0 [OPTIONS] <backup-file>"
            echo ""
            echo -e "${BLUE}Options:${NC}"
            echo "  -y, --yes         Skip confirmation prompt"
            echo "  -l, --list        List available backups"
            echo "  -h, --help        Show this help message"
            echo ""
            echo -e "${BLUE}Examples:${NC}"
            echo "  $0 -l                                     # List backups"
            echo "  $0 backups/backup_20251102_120000.dump   # Restore specific backup"
            echo "  $0 -y my-backup.dump                      # Auto-confirm restore"
            echo ""
            exit 0
            ;;
        -*)
            echo -e "${RED}✗${NC} Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
        *)
            BACKUP_FILE="$1"
            shift
            ;;
    esac
done

# Require backup file
if [ -z "$BACKUP_FILE" ]; then
    echo ""
    echo -e "${RED}✗${NC} Error: Backup file required"
    echo ""
    echo "Usage: $0 <backup-file>"
    echo ""
    echo -e "${YELLOW}List available backups:${NC}"
    echo "  $0 --list"
    echo ""
    exit 1
fi

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo ""
    echo -e "${RED}✗${NC} Backup file not found: ${BLUE}$BACKUP_FILE${NC}"
    echo ""
    echo -e "${YELLOW}List available backups:${NC}"
    echo "  $0 --list"
    echo ""
    exit 1
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo ""
    echo -e "${RED}✗${NC} Database container is not running"
    echo -e "  Start it with: ${BLUE}./scripts/services/start-database.sh${NC}"
    echo ""
    exit 1
fi

# Show confirmation prompt unless -y flag used
if [ "$AUTO_CONFIRM" = false ]; then
    echo ""
    echo -e "${BOLD}Restore Knowledge Graph Database${NC}"
    echo "=================================="
    echo ""

    # Get backup size
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

    echo -e "${YELLOW}Restore Details:${NC}"
    echo -e "  Source: ${BLUE}$BACKUP_FILE${NC}"
    echo -e "  Size: ${GREEN}$BACKUP_SIZE${NC}"
    echo -e "  Target database: ${BLUE}$DB_NAME${NC}"
    echo ""
    echo -e "${RED}⚠️  WARNING: This will REPLACE ALL DATA in $DB_NAME${NC}"
    echo -e "  ${YELLOW}All existing concepts, relationships, sources, and users will be lost${NC}"
    echo ""
    echo -e "${BLUE}What this does:${NC}"
    echo "  • Drops all existing tables and data"
    echo "  • Restores complete database from backup"
    echo "  • Includes all graphs, users, and configuration"
    echo ""
    echo -e "${BLUE}Usage:${NC}"
    echo "  $0 -y <backup-file>    # Restore (skip confirmation)"
    echo "  $0 --yes <backup-file> # Restore (skip confirmation)"
    echo ""
    read -p "$(echo -e ${YELLOW}Continue with restore? [y/N]:${NC} )" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Cancelled${NC}"
        exit 0
    fi
    echo ""
fi

echo ""
echo -e "${BOLD}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Knowledge Graph System - Database Restore          ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}→${NC} Preparing restore..."
echo -e "  Source: ${BLUE}$(basename "$BACKUP_FILE")${NC}"
echo -e "  Target: ${BLUE}$DB_NAME${NC}"
echo ""

# Detect backup format (custom binary or plain SQL)
if file "$BACKUP_FILE" | grep -q "PostgreSQL custom database dump"; then
    # Binary custom format - use pg_restore
    echo -e "${BLUE}→${NC} Restoring from binary backup (pg_restore)..."

    # pg_restore options:
    # --clean: Drop objects before recreating
    # --if-exists: Use IF EXISTS when dropping
    # --no-owner: Don't restore ownership
    # --no-privileges: Don't restore privileges
    # -1: Run restore in single transaction (all or nothing)
    if docker exec -i $CONTAINER pg_restore \
        -U $DB_USER \
        -d $DB_NAME \
        --clean \
        --if-exists \
        --no-owner \
        --no-privileges \
        -1 \
        < "$BACKUP_FILE" 2>&1 | grep -v "^WARNING:" | grep -v "already exists"; then

        RESTORE_METHOD="pg_restore (binary)"
    else
        echo -e "${RED}✗${NC} Restore failed"
        echo ""
        echo -e "${YELLOW}Troubleshooting:${NC}"
        echo "  1. Verify backup file is valid: ${BLUE}file $BACKUP_FILE${NC}"
        echo "  2. Check database container is healthy: ${BLUE}docker ps${NC}"
        echo "  3. View Docker logs: ${BLUE}docker logs $CONTAINER${NC}"
        echo ""
        exit 1
    fi
else
    # Plain SQL format - use psql
    echo -e "${BLUE}→${NC} Restoring from SQL backup (psql)..."

    if docker exec -i $CONTAINER psql -U $DB_USER -d $DB_NAME \
        < "$BACKUP_FILE" > /dev/null 2>&1; then

        RESTORE_METHOD="psql (SQL)"
    else
        echo -e "${RED}✗${NC} Restore failed"
        echo ""
        echo -e "${YELLOW}Troubleshooting:${NC}"
        echo "  1. Verify backup file is valid SQL"
        echo "  2. Check database container is healthy: ${BLUE}docker ps${NC}"
        echo "  3. View Docker logs: ${BLUE}docker logs $CONTAINER${NC}"
        echo ""
        exit 1
    fi
fi

echo -e "${GREEN}✓${NC} Database restored successfully!"
echo ""

# Show restored database stats
SCHEMA_VERSION=$(docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c \
    "SELECT MAX(version) FROM public.schema_migrations" 2>/dev/null || echo "unknown")

CONCEPT_COUNT=$(docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c \
    "SELECT COUNT(*) FROM cypher('knowledge_graph', \$\$ MATCH (c:Concept) RETURN c \$\$) as (c agtype)" 2>/dev/null || echo "0")

SOURCE_COUNT=$(docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c \
    "SELECT COUNT(*) FROM cypher('knowledge_graph', \$\$ MATCH (s:Source) RETURN s \$\$) as (s agtype)" 2>/dev/null || echo "0")

USER_COUNT=$(docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c \
    "SELECT COUNT(*) FROM kg_auth.users" 2>/dev/null || echo "0")

echo -e "${BOLD}Restored Database:${NC}"
echo -e "  Method: ${BLUE}$RESTORE_METHOD${NC}"
echo -e "  Schema version: ${GREEN}$SCHEMA_VERSION${NC}"
echo -e "  Concepts: ${GREEN}$CONCEPT_COUNT${NC}"
echo -e "  Sources: ${GREEN}$SOURCE_COUNT${NC}"
echo -e "  Users: ${GREEN}$USER_COUNT${NC}"
echo ""
echo -e "${BOLD}Next Steps:${NC}"
echo -e "  1. Restart API server: ${BLUE}./scripts/services/stop-api.sh && ./scripts/services/start-api.sh${NC}"
echo -e "  2. Test login: ${BLUE}kg login${NC}"
echo -e "  3. Verify data: ${BLUE}kg database stats${NC}"
echo ""
