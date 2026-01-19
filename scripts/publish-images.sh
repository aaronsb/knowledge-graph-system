#!/bin/bash
# ============================================================================
# publish-images.sh - Build and push container images to GHCR
#
# Builds API and Web containers locally (faster than GitHub runners) and
# pushes to GitHub Container Registry.
#
# Prerequisites:
#   - Docker logged into GHCR: docker login ghcr.io -u USERNAME
#   - Or: gh auth token | docker login ghcr.io -u USERNAME --password-stdin
#
# Usage:
#   ./scripts/publish-images.sh           # Build and push all
#   ./scripts/publish-images.sh api       # Build and push API only
#   ./scripts/publish-images.sh web       # Build and push Web only
#   ./scripts/publish-images.sh --dry-run # Build only, don't push
#
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

REGISTRY="ghcr.io"
IMAGE_PREFIX="aaronsb/knowledge-graph-system"

# Parse arguments
DRY_RUN=false
SERVICES=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        api|web)
            SERVICES+=("$1")
            shift
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            echo "Usage: $0 [api|web] [--dry-run]"
            exit 1
            ;;
    esac
done

# Default to both services if none specified
if [ ${#SERVICES[@]} -eq 0 ]; then
    SERVICES=(api web)
fi

# Get version from VERSION file
VERSION=$(cat "$PROJECT_ROOT/VERSION" | tr -d '[:space:]')
GIT_SHA=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD)
BUILD_DATE=$(date -Iseconds)

echo -e "${BOLD}Publishing container images to GHCR${NC}"
echo -e "  Version: ${BLUE}$VERSION${NC}"
echo -e "  Commit:  ${BLUE}$GIT_SHA${NC}"
echo -e "  Services: ${BLUE}${SERVICES[*]}${NC}"
if [ "$DRY_RUN" = "true" ]; then
    echo -e "  Mode:    ${YELLOW}DRY RUN (build only)${NC}"
fi
echo ""

# Check GHCR authentication
if [ "$DRY_RUN" = "false" ]; then
    if ! docker login ghcr.io --get-login &>/dev/null; then
        echo -e "${YELLOW}Not logged into GHCR. Attempting login via gh CLI...${NC}"
        if command -v gh &>/dev/null; then
            gh auth token | docker login ghcr.io -u "$(gh api user -q .login)" --password-stdin
        else
            echo -e "${RED}Please log in to GHCR first:${NC}"
            echo "  docker login ghcr.io -u YOUR_USERNAME"
            exit 1
        fi
    fi
fi

cd "$PROJECT_ROOT"

build_and_push() {
    local service="$1"
    local context dockerfile image_name

    case "$service" in
        api)
            context="."
            dockerfile="./api/Dockerfile"
            image_name="kg-api"
            ;;
        web)
            context="./web"
            dockerfile="./web/Dockerfile"
            image_name="kg-web"
            ;;
    esac

    local full_image="$REGISTRY/$IMAGE_PREFIX/$image_name"

    echo -e "${BLUE}→ Building $service...${NC}"

    docker build \
        --file "$dockerfile" \
        --build-arg GIT_COMMIT="$GIT_SHA" \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --tag "$full_image:latest" \
        --tag "$full_image:$VERSION" \
        --tag "$full_image:sha-$GIT_SHA" \
        "$context"

    echo -e "${GREEN}✓ Built $full_image${NC}"

    if [ "$DRY_RUN" = "false" ]; then
        echo -e "${BLUE}→ Pushing $service...${NC}"
        docker push "$full_image:latest"
        docker push "$full_image:$VERSION"
        docker push "$full_image:sha-$GIT_SHA"
        echo -e "${GREEN}✓ Pushed $full_image${NC}"
    fi

    echo ""
}

for service in "${SERVICES[@]}"; do
    build_and_push "$service"
done

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ "$DRY_RUN" = "true" ]; then
    echo -e "${GREEN}✅ Build complete (dry run - not pushed)${NC}"
else
    echo -e "${GREEN}✅ Published to GHCR${NC}"
    echo ""
    for service in "${SERVICES[@]}"; do
        echo -e "  $REGISTRY/$IMAGE_PREFIX/kg-$service:$VERSION"
    done
fi
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
