#!/usr/bin/env bash
# ============================================================================
# build-in-container.sh — Build graph_accel inside the official apache/age
# container for guaranteed ABI compatibility.
#
# Produces:
#   graph-accel/dist/pg17/graph_accel.so
#   graph-accel/dist/pg17/graph_accel.control
#   graph-accel/dist/pg17/graph_accel--<version>.sql
#
# These artifacts can be:
#   1. Baked into kg-postgres Docker image (docker/Dockerfile.postgres)
#   2. Volume-mounted in dev mode (docker-compose.dev.yml)
#   3. Distributed independently for any apache/age installation
#
# Usage:
#   ./graph-accel/build-in-container.sh          # full build
#   ./graph-accel/build-in-container.sh --no-cache  # force rebuild
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"
DOCKERFILE="$SCRIPT_DIR/Dockerfile.build"

# Parse args
EXTRA_ARGS=""
for arg in "$@"; do
    case "$arg" in
        --no-cache) EXTRA_ARGS="--no-cache" ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

echo "=== Building graph_accel in apache/age container ==="
echo ""

# Clean previous artifacts
rm -rf "$DIST_DIR/pg17"
mkdir -p "$DIST_DIR/pg17"

# Build using Docker BuildKit --output to extract just the artifacts
# The 'artifacts' stage in Dockerfile.build contains only the three files
DOCKER_BUILDKIT=1 docker build \
    -f "$DOCKERFILE" \
    --target artifacts \
    --output "type=local,dest=$DIST_DIR" \
    $EXTRA_ARGS \
    "$PROJECT_ROOT"

# Verify artifacts
echo ""
echo "=== Build artifacts ==="
ls -lh "$DIST_DIR/pg17/"

# Extract version from control file
VERSION=$(grep 'default_version' "$DIST_DIR/pg17/graph_accel.control" | grep -oP "'\K[^']+")
echo ""
echo "  Extension version: $VERSION"
echo "  Target: PostgreSQL 17 (apache/age)"
echo ""

# Verify all three files exist
MISSING=0
for f in graph_accel.so graph_accel.control "graph_accel--${VERSION}.sql"; do
    if [ ! -f "$DIST_DIR/pg17/$f" ]; then
        echo "ERROR: Missing artifact: $f"
        MISSING=1
    fi
done

if [ "$MISSING" -eq 0 ]; then
    echo "BUILD: OK — artifacts ready in graph-accel/dist/pg17/"
else
    echo "BUILD: FAILED — missing artifacts"
    exit 1
fi
