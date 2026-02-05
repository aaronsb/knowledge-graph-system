#!/usr/bin/env bash
# ============================================================================
# build-in-container.sh — Build graph_accel inside the official apache/age
# container for guaranteed ABI compatibility.
#
# Produces per-architecture artifacts:
#   graph-accel/dist/pg17/<arch>/graph_accel.so
#   graph-accel/dist/pg17/<arch>/graph_accel.control
#   graph-accel/dist/pg17/<arch>/graph_accel--<version>.sql
#
# These artifacts can be:
#   1. Baked into kg-postgres Docker image (docker/Dockerfile.postgres)
#   2. Deployed via deploy-option0.sh in dev mode
#   3. Distributed independently for any apache/age installation
#
# Usage:
#   ./graph-accel/build-in-container.sh              # host arch only
#   ./graph-accel/build-in-container.sh --all         # amd64 + arm64
#   ./graph-accel/build-in-container.sh --platform linux/arm64
#   ./graph-accel/build-in-container.sh --no-cache    # force rebuild
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"
DOCKERFILE="$SCRIPT_DIR/Dockerfile.build"

# Parse args
EXTRA_ARGS=""
PLATFORMS=()
BUILD_ALL=false
for arg in "$@"; do
    case "$arg" in
        --no-cache) EXTRA_ARGS="--no-cache" ;;
        --all) BUILD_ALL=true ;;
        --platform)
            # Next arg is the platform — handled below
            ;;
        linux/amd64|linux/arm64)
            PLATFORMS+=("$arg")
            ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

# Determine which platforms to build
if [ "$BUILD_ALL" = "true" ]; then
    PLATFORMS=(linux/amd64 linux/arm64)
elif [ ${#PLATFORMS[@]} -eq 0 ]; then
    # Default to host architecture
    HOST_ARCH=$(uname -m)
    case "$HOST_ARCH" in
        x86_64)  PLATFORMS=(linux/amd64) ;;
        aarch64) PLATFORMS=(linux/arm64) ;;
        *) echo "Unsupported host architecture: $HOST_ARCH"; exit 1 ;;
    esac
fi

# Ensure buildx builder exists for cross-platform builds
if [ ${#PLATFORMS[@]} -gt 1 ] || [ "${PLATFORMS[0]}" != "linux/$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')" ]; then
    if ! docker buildx inspect graph-accel-builder &>/dev/null; then
        echo "Creating buildx builder for cross-platform builds..."
        docker buildx create --name graph-accel-builder --use --bootstrap
    else
        docker buildx use graph-accel-builder
    fi
fi

build_for_platform() {
    local platform="$1"
    local arch="${platform#linux/}"

    echo ""
    echo "=== Building graph_accel for $platform ==="
    echo ""

    # Clean previous artifacts for this arch
    rm -rf "$DIST_DIR/pg17/$arch"
    mkdir -p "$DIST_DIR/pg17/$arch"

    # Build using Docker BuildKit --output to extract just the artifacts
    # The 'artifacts' stage outputs to /pg17/<arch>/ via TARGETARCH
    DOCKER_BUILDKIT=1 docker buildx build \
        -f "$DOCKERFILE" \
        --platform "$platform" \
        --target artifacts \
        --output "type=local,dest=$DIST_DIR" \
        $EXTRA_ARGS \
        "$PROJECT_ROOT"

    # Verify artifacts
    echo ""
    echo "=== Build artifacts ($arch) ==="
    ls -lh "$DIST_DIR/pg17/$arch/"

    # Extract version from control file
    local version
    version=$(grep 'default_version' "$DIST_DIR/pg17/$arch/graph_accel.control" | grep -oP "'\K[^']+")
    echo ""
    echo "  Extension version: $version"
    echo "  Target: PostgreSQL 17 (apache/age) — $arch"

    # Verify all three files exist
    local missing=0
    for f in graph_accel.so graph_accel.control "graph_accel--${version}.sql"; do
        if [ ! -f "$DIST_DIR/pg17/$arch/$f" ]; then
            echo "ERROR: Missing artifact: $f"
            missing=1
        fi
    done

    if [ "$missing" -ne 0 ]; then
        echo "BUILD FAILED for $platform"
        return 1
    fi
}

# Build each platform
FAILED=0
for platform in "${PLATFORMS[@]}"; do
    if ! build_for_platform "$platform"; then
        FAILED=1
    fi
done

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo "BUILD: OK — artifacts ready in graph-accel/dist/pg17/"
    for platform in "${PLATFORMS[@]}"; do
        echo "  ${platform#linux/}/: $(ls "$DIST_DIR/pg17/${platform#linux/}/" | tr '\n' ' ')"
    done
else
    echo "BUILD: FAILED — see errors above"
    exit 1
fi
