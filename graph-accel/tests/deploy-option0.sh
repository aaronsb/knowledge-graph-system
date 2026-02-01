#!/usr/bin/env bash
# deploy-option0.sh — Build and deploy graph_accel into running container
#
# Option 0 deployment for development: builds the extension, copies artifacts
# into the knowledge-graph-postgres container, and reinstalls the extension.
#
# Requirements:
#   - cargo-pgrx 0.16.1 installed
#   - pgrx initialized for pg17 (~/.pgrx/17.*/pgrx-install/bin/pg_config)
#   - knowledge-graph-postgres container running
#
# Usage:
#   ./graph-accel/tests/deploy-option0.sh          # build + deploy
#   ./graph-accel/tests/deploy-option0.sh --skip-build   # deploy only (reuse last build)

set -euo pipefail

CONTAINER="knowledge-graph-postgres"
DB="knowledge_graph"
USER="admin"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ACCEL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKIP_BUILD=false

if [[ "${1:-}" == "--skip-build" ]]; then
    SKIP_BUILD=true
fi

# Find pg_config
PG_CONFIG=$(find ~/.pgrx -name pg_config -path "*/17.*/bin/*" 2>/dev/null | head -1)
if [ -z "$PG_CONFIG" ]; then
    echo "ERROR: pg_config for PG 17 not found in ~/.pgrx/"
    echo "Run: cargo pgrx init --pg17=download"
    exit 1
fi

# Build
if ! $SKIP_BUILD; then
    echo "--- Building extension ---"
    cd "$ACCEL_DIR"
    cargo pgrx package --package graph-accel-ext --pg-config "$PG_CONFIG" 2>&1 | tail -5
    echo ""
fi

# Find package directory (pgrx nests it under the full pgrx-install path)
PKGDIR=$(find "$ACCEL_DIR/target/release/graph_accel-pg17" -name "graph_accel.control" -printf '%h' -quit 2>/dev/null)
PKGDIR="${PKGDIR%/share/postgresql/extension}"
if [ -z "$PKGDIR" ] || [ ! -d "$PKGDIR" ]; then
    echo "ERROR: Package directory not found. Run without --skip-build first."
    exit 1
fi

# Resolve version from control file
VERSION=$(grep 'default_version' "$PKGDIR/share/postgresql/extension/graph_accel.control" | grep -oP "'\K[^']+")
SQL_FILE="$PKGDIR/share/postgresql/extension/graph_accel--${VERSION}.sql"

if [ ! -f "$SQL_FILE" ]; then
    echo "ERROR: SQL file not found: $SQL_FILE"
    exit 1
fi

echo "--- Deploying v${VERSION} into ${CONTAINER} ---"

# Copy artifacts
docker cp "$PKGDIR/lib/postgresql/graph_accel.so" \
    "$CONTAINER:/usr/lib/postgresql/17/lib/"
docker cp "$PKGDIR/share/postgresql/extension/graph_accel.control" \
    "$CONTAINER:/usr/share/postgresql/17/extension/"
docker cp "$SQL_FILE" \
    "$CONTAINER:/usr/share/postgresql/17/extension/"

echo "  Copied .so, .control, SQL"

# Reinstall extension
docker exec "$CONTAINER" psql -U "$USER" -d "$DB" \
    -c "DROP EXTENSION IF EXISTS graph_accel CASCADE;" \
    -c "CREATE EXTENSION graph_accel;" \
    2>&1

echo ""

# Verify
installed=$(docker exec "$CONTAINER" psql -U "$USER" -d "$DB" -t -A \
    -c "SELECT extversion FROM pg_extension WHERE extname = 'graph_accel';")
echo "  Installed: graph_accel v${installed}"

# Quick smoke test
docker exec "$CONTAINER" psql -U "$USER" -d "$DB" -t -A \
    -c "SELECT status FROM graph_accel_status();" | \
    xargs -I{} echo "  Status: {}"

echo ""
echo "DEPLOY: OK"
