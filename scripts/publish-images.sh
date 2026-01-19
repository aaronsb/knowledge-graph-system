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
#   ./scripts/publish-images.sh -m "Description of changes"
#   ./scripts/publish-images.sh api -m "API fixes"
#   ./scripts/publish-images.sh web --dry-run
#   ./scripts/publish-images.sh  # Prompts for description
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
DESCRIPTION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -m|--message)
            DESCRIPTION="$2"
            shift 2
            ;;
        api|web)
            SERVICES+=("$1")
            shift
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            echo "Usage: $0 [api|web] [-m \"description\"] [--dry-run]"
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

# If no description provided and not dry-run, show recent commits and prompt
if [ -z "$DESCRIPTION" ] && [ "$DRY_RUN" = "false" ]; then
    echo -e "${BOLD}Recent commits since last tag:${NC}"
    echo ""
    # Get commits since last tag, or last 5 commits if no tags
    LAST_TAG=$(git -C "$PROJECT_ROOT" describe --tags --abbrev=0 2>/dev/null || echo "")
    if [ -n "$LAST_TAG" ]; then
        git -C "$PROJECT_ROOT" log --oneline "$LAST_TAG"..HEAD | head -10
    else
        git -C "$PROJECT_ROOT" log --oneline -5
    fi
    echo ""
    echo -e "${YELLOW}Tip: Add a description with -m to document this release${NC}"
    echo -e "${YELLOW}Example: $0 -m \"Add update/upgrade lifecycle, fix standalone installs\"${NC}"
    echo ""
    read -p "Enter description (or press Enter to skip): " DESCRIPTION
    echo ""
fi

echo -e "${BOLD}Publishing container images to GHCR${NC}"
echo -e "  Version: ${BLUE}$VERSION${NC}"
echo -e "  Commit:  ${BLUE}$GIT_SHA${NC}"
echo -e "  Services: ${BLUE}${SERVICES[*]}${NC}"
if [ -n "$DESCRIPTION" ]; then
    echo -e "  Description: ${BLUE}$DESCRIPTION${NC}"
fi
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

    # Build with OCI annotations
    local label_args=(
        --label "org.opencontainers.image.version=$VERSION"
        --label "org.opencontainers.image.revision=$GIT_SHA"
        --label "org.opencontainers.image.created=$BUILD_DATE"
        --label "org.opencontainers.image.source=https://github.com/$IMAGE_PREFIX"
    )

    if [ -n "$DESCRIPTION" ]; then
        label_args+=(--label "org.opencontainers.image.description=$DESCRIPTION")
    fi

    docker build \
        --file "$dockerfile" \
        --build-arg GIT_COMMIT="$GIT_SHA" \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        "${label_args[@]}" \
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
