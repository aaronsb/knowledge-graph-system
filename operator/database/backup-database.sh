#!/bin/bash
# ============================================================================
# Backup Knowledge Graph Database
# ============================================================================
# Creates full binary backup of PostgreSQL database including Apache AGE graph
# Uses pg_dump custom format (compressed binary, includes all data)
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
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_${DB_NAME}_${TIMESTAMP}.dump"

# Check for -y/--yes flag for non-interactive mode
AUTO_CONFIRM=false
CUSTOM_OUTPUT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -y|--yes)
            AUTO_CONFIRM=true
            shift
            ;;
        -o|--output)
            CUSTOM_OUTPUT="$2"
            shift 2
            ;;
        -h|--help)
            echo ""
            echo -e "${BOLD}Backup Knowledge Graph Database${NC}"
            echo "================================="
            echo ""
            echo "Creates full binary backup of PostgreSQL database including Apache AGE graph data."
            echo ""
            echo -e "${BLUE}Usage:${NC}"
            echo "  $0 [OPTIONS]"
            echo ""
            echo -e "${BLUE}Options:${NC}"
            echo "  -y, --yes         Skip confirmation prompt"
            echo "  -o, --output FILE Custom output file path"
            echo "  -h, --help        Show this help message"
            echo ""
            echo -e "${BLUE}Examples:${NC}"
            echo "  $0                          # Interactive backup with timestamp"
            echo "  $0 -y                       # Auto-confirm backup"
            echo "  $0 -o my-backup.dump        # Custom output file"
            echo "  $0 -y -o my-backup.dump     # Auto-confirm with custom output"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}✗${NC} Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Use custom output file if specified
if [ -n "$CUSTOM_OUTPUT" ]; then
    BACKUP_FILE="$CUSTOM_OUTPUT"
fi

# Show confirmation prompt unless -y flag used
if [ "$AUTO_CONFIRM" = false ]; then
    echo ""
    echo -e "${BOLD}Backup Knowledge Graph Database${NC}"
    echo "================================="
    echo ""
    echo -e "${YELLOW}What this does:${NC}"
    echo "  • Creates full binary backup using pg_dump custom format"
    echo "  • Includes all data: concepts, relationships, sources, users"
    echo "  • Includes Apache AGE graph data"
    echo "  • Output file: ${BLUE}$BACKUP_FILE${NC}"
    echo ""
    echo -e "${BLUE}Backup Format:${NC}"
    echo "  • Binary custom format (compressed)"
    echo "  • Restore with: ${BLUE}./scripts/database/restore-database.sh <file>${NC}"
    echo ""
    echo -e "${BLUE}Usage:${NC}"
    echo "  $0 -y          # Backup database (skip confirmation)"
    echo "  $0 --yes       # Backup database (skip confirmation)"
    echo ""
    read -p "$(echo -e ${YELLOW}Create backup now? [y/N]:${NC} )" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Cancelled${NC}"
        exit 0
    fi
    echo ""
fi

echo ""
echo -e "${BOLD}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Knowledge Graph System - Database Backup           ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo -e "${RED}✗${NC} Database container is not running"
    echo -e "  Start it with: ${BLUE}./scripts/services/start-database.sh${NC}"
    echo ""
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$(dirname "$BACKUP_FILE")"

echo -e "${BLUE}→${NC} Creating backup..."
echo -e "  Database: ${GREEN}$DB_NAME${NC}"
echo -e "  Container: ${GREEN}$CONTAINER${NC}"
echo -e "  Output: ${BLUE}$BACKUP_FILE${NC}"
echo ""

# Create backup using pg_dump custom format (binary, compressed)
# --format=custom: Binary format, compressed, best for restore
# --no-owner: Don't output ownership commands
# --no-privileges: Don't output privilege commands
# --clean: Include commands to drop objects before recreating
# --if-exists: Use IF EXISTS when dropping objects
# This includes ALL data: tables, sequences, Apache AGE graph data, everything
if docker exec $CONTAINER pg_dump \
    -U $DB_USER \
    -d $DB_NAME \
    --format=custom \
    --compress=9 \
    --no-owner \
    --no-privileges \
    --clean \
    --if-exists \
    > "$BACKUP_FILE" 2>&1; then

    # Get backup size
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

    # Get database stats
    CONCEPT_COUNT=$(docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c \
        "SELECT COUNT(*) FROM cypher('knowledge_graph', \$\$ MATCH (c:Concept) RETURN c \$\$) as (c agtype)" 2>/dev/null || echo "0")

    SOURCE_COUNT=$(docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c \
        "SELECT COUNT(*) FROM cypher('knowledge_graph', \$\$ MATCH (s:Source) RETURN s \$\$) as (s agtype)" 2>/dev/null || echo "0")

    echo -e "${GREEN}✓${NC} Backup created successfully!"
    echo ""
    echo -e "${BOLD}Backup Details:${NC}"
    echo -e "  File: ${BLUE}$BACKUP_FILE${NC}"
    echo -e "  Size: ${GREEN}$BACKUP_SIZE${NC}"
    echo -e "  Format: ${BLUE}PostgreSQL custom (binary, compressed)${NC}"
    echo ""
    echo -e "${BOLD}Database Contents:${NC}"
    echo -e "  Concepts: ${GREEN}$CONCEPT_COUNT${NC}"
    echo -e "  Sources: ${GREEN}$SOURCE_COUNT${NC}"
    echo ""
    echo -e "${BOLD}Restore with:${NC}"
    echo -e "  ${BLUE}./scripts/database/restore-database.sh $BACKUP_FILE${NC}"
    echo ""

    exit 0
else
    echo -e "${RED}✗${NC} Backup failed"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "  1. Check database container is healthy: ${BLUE}docker ps${NC}"
    echo "  2. Check Docker logs: ${BLUE}docker logs $CONTAINER${NC}"
    echo "  3. Verify database is accessible: ${BLUE}docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -c '\\dt'${NC}"
    echo ""
    exit 1
fi
