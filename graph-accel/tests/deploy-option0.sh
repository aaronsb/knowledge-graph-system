#!/usr/bin/env bash
# deploy-option0.sh — Build and deploy graph_accel into running container
#
# Deployment for development: builds the extension (or uses pre-built artifacts),
# copies into the knowledge-graph-postgres container, and reinstalls the extension.
#
# Artifact sources (checked in order):
#   1. graph-accel/dist/pg17/  (from build-in-container.sh — ABI-compatible)
#   2. cargo pgrx package output (from host Rust toolchain)
#
# Usage:
#   ./graph-accel/tests/deploy-option0.sh              # use dist/ or build + deploy
#   ./graph-accel/tests/deploy-option0.sh --skip-build  # deploy only (reuse last build)
#   ./graph-accel/tests/deploy-option0.sh --host-build   # force host cargo pgrx build

set -euo pipefail

CONTAINER="knowledge-graph-postgres"
DB="knowledge_graph"
USER="admin"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ACCEL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKIP_BUILD=false
FORCE_HOST_BUILD=false

for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=true ;;
        --host-build) FORCE_HOST_BUILD=true ;;
    esac
done

# Resolve artifact source
DIST_DIR="$ACCEL_DIR/dist/pg17"
if [ -f "$DIST_DIR/graph_accel.so" ] && [ -f "$DIST_DIR/graph_accel.control" ] && ! $FORCE_HOST_BUILD; then
    # Use pre-built artifacts from build-in-container.sh
    VERSION=$(grep 'default_version' "$DIST_DIR/graph_accel.control" | grep -oP "'\K[^']+")
    SO_FILE="$DIST_DIR/graph_accel.so"
    CONTROL_FILE="$DIST_DIR/graph_accel.control"
    SQL_FILE="$DIST_DIR/graph_accel--${VERSION}.sql"
    echo "--- Using pre-built artifacts from dist/pg17/ (v${VERSION}) ---"
else
    # Fall back to host cargo pgrx build
    PG_CONFIG=$(find ~/.pgrx -name pg_config -path "*/17.*/pgrx-install/bin/*" 2>/dev/null | head -1)
    if [ -z "$PG_CONFIG" ]; then
        echo "ERROR: No dist/ artifacts and pg_config for PG 17 not found in ~/.pgrx/"
        echo "Run: ./graph-accel/build-in-container.sh  (or: cargo pgrx init --pg17=download)"
        exit 1
    fi

    if ! $SKIP_BUILD; then
        echo "--- Building extension (host) ---"
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

    VERSION=$(grep 'default_version' "$PKGDIR/share/postgresql/extension/graph_accel.control" | grep -oP "'\K[^']+")
    SO_FILE="$PKGDIR/lib/postgresql/graph_accel.so"
    CONTROL_FILE="$PKGDIR/share/postgresql/extension/graph_accel.control"
    SQL_FILE="$PKGDIR/share/postgresql/extension/graph_accel--${VERSION}.sql"
fi

if [ ! -f "$SQL_FILE" ]; then
    echo "ERROR: SQL file not found: $SQL_FILE"
    exit 1
fi

echo "--- Deploying v${VERSION} into ${CONTAINER} ---"

# Copy artifacts
docker cp "$SO_FILE" "$CONTAINER:/usr/lib/postgresql/17/lib/"
docker cp "$CONTROL_FILE" "$CONTAINER:/usr/share/postgresql/17/extension/"
docker cp "$SQL_FILE" "$CONTAINER:/usr/share/postgresql/17/extension/"

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
