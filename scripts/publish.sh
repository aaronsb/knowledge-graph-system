#!/bin/bash
# ============================================================================
# publish.sh - Unified publishing tool for Knowledge Graph System
#
# Publishes:
#   - Docker images (api, web) → GitHub Container Registry
#   - npm package (CLI/MCP)    → npm registry
#   - Python package (FUSE)    → PyPI
#
# Usage:
#   ./scripts/publish.sh images [api|web]  # Docker images
#   ./scripts/publish.sh cli               # npm package
#   ./scripts/publish.sh fuse              # PyPI package
#   ./scripts/publish.sh all               # Everything
#   ./scripts/publish.sh status            # Show versions and auth status
#
# Options:
#   -m, --message "desc"   Description for release
#   --dry-run              Build/pack without publishing
#   --skip-build           Skip build step (push existing)
#
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Registries
GHCR_REGISTRY="ghcr.io"
IMAGE_PREFIX="aaronsb/knowledge-graph-system"

# ============================================================================
# Parse arguments
# ============================================================================

DRY_RUN=false
SKIP_BUILD=false
DESCRIPTION=""
COMMAND=""
TARGETS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        images|cli|fuse|all|status)
            COMMAND="$1"
            shift
            ;;
        api|web)
            TARGETS+=("$1")
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        -m|--message)
            DESCRIPTION="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 <command> [targets] [options]"
            echo ""
            echo "Commands:"
            echo "  images [api|web]  Publish Docker images to GHCR"
            echo "  cli               Publish npm package (@aaronsb/kg-cli)"
            echo "  fuse              Publish Python package (kg-fuse) to PyPI"
            echo "  all               Publish everything"
            echo "  status            Show versions and authentication status"
            echo ""
            echo "Options:"
            echo "  -m, --message     Description for this release"
            echo "  --dry-run         Build/pack without actually publishing"
            echo "  --skip-build      Skip build (push existing artifacts)"
            echo ""
            echo "Examples:"
            echo "  $0 images -m 'Fix API bug'"
            echo "  $0 images api --dry-run"
            echo "  $0 cli"
            echo "  $0 all -m 'Release v1.2.3'"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            echo "Run '$0 --help' for usage"
            exit 1
            ;;
    esac
done

if [ -z "$COMMAND" ]; then
    echo -e "${RED}No command specified${NC}"
    echo "Run '$0 --help' for usage"
    exit 1
fi

# ============================================================================
# Version information
# ============================================================================

get_versions() {
    VERSION=$(cat "$PROJECT_ROOT/VERSION" 2>/dev/null | tr -d '[:space:]' || echo "0.0.0")
    GIT_SHA=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")
    GIT_BRANCH=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
    BUILD_DATE=$(date -Iseconds)

    CLI_VERSION=$(node -p "require('$PROJECT_ROOT/cli/package.json').version" 2>/dev/null || echo "unknown")
    FUSE_VERSION=$(grep -E "^version" "$PROJECT_ROOT/fuse/pyproject.toml" 2>/dev/null | cut -d'"' -f2 || echo "unknown")
}

# ============================================================================
# Authentication checks
# ============================================================================

check_ghcr_auth() {
    if docker login ghcr.io --get-login &>/dev/null; then
        return 0
    fi

    # Try gh CLI
    if command -v gh &>/dev/null; then
        echo -e "${YELLOW}Logging into GHCR via gh CLI...${NC}"
        if gh auth token | docker login ghcr.io -u "$(gh api user -q .login)" --password-stdin 2>/dev/null; then
            return 0
        fi
    fi

    return 1
}

check_npm_auth() {
    npm whoami &>/dev/null
}

check_pypi_auth() {
    # Check for twine and credentials
    if ! command -v twine &>/dev/null; then
        return 1
    fi
    # PyPI auth is checked at upload time via ~/.pypirc or TWINE_* env vars
    return 0
}

# ============================================================================
# Status command
# ============================================================================

cmd_status() {
    get_versions

    echo -e "${BOLD}Knowledge Graph System - Publish Status${NC}"
    echo ""

    echo -e "${CYAN}Versions:${NC}"
    echo "  Main VERSION:  $VERSION"
    echo "  CLI (npm):     $CLI_VERSION"
    echo "  FUSE (PyPI):   $FUSE_VERSION"
    echo "  Git commit:    $GIT_SHA"
    echo "  Git branch:    $GIT_BRANCH"
    echo ""

    echo -e "${CYAN}Authentication:${NC}"

    # GHCR
    if check_ghcr_auth; then
        echo -e "  GHCR:  ${GREEN}✓ authenticated${NC}"
    else
        echo -e "  GHCR:  ${RED}✗ not logged in${NC} (run: docker login ghcr.io)"
    fi

    # npm
    if check_npm_auth; then
        NPM_USER=$(npm whoami 2>/dev/null)
        echo -e "  npm:   ${GREEN}✓ authenticated${NC} as $NPM_USER"
    else
        echo -e "  npm:   ${RED}✗ not logged in${NC} (run: npm login)"
    fi

    # PyPI
    if check_pypi_auth; then
        echo -e "  PyPI:  ${GREEN}✓ twine available${NC} (credentials checked at upload)"
    else
        echo -e "  PyPI:  ${RED}✗ twine not found${NC} (run: pip install twine)"
    fi

    echo ""

    # Published versions
    echo -e "${CYAN}Published versions:${NC}"

    # Check npm
    NPM_PUBLISHED=$(npm view @aaronsb/kg-cli version 2>/dev/null || echo "not published")
    echo "  npm (@aaronsb/kg-cli): $NPM_PUBLISHED"

    # Check PyPI
    PYPI_PUBLISHED=$(pip index versions kg-fuse 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "not published")
    echo "  PyPI (kg-fuse):        $PYPI_PUBLISHED"

    echo ""
}

# ============================================================================
# Docker images
# ============================================================================

cmd_images() {
    get_versions

    # Default to both if no targets specified
    if [ ${#TARGETS[@]} -eq 0 ]; then
        TARGETS=(api web)
    fi

    echo -e "${BOLD}Publishing Docker images to GHCR${NC}"
    echo -e "  Version: ${BLUE}$VERSION${NC}"
    echo -e "  Commit:  ${BLUE}$GIT_SHA${NC}"
    echo -e "  Targets: ${BLUE}${TARGETS[*]}${NC}"
    [ -n "$DESCRIPTION" ] && echo -e "  Message: ${BLUE}$DESCRIPTION${NC}"
    [ "$DRY_RUN" = "true" ] && echo -e "  Mode:    ${YELLOW}DRY RUN${NC}"
    echo ""

    # Auth check
    if [ "$DRY_RUN" = "false" ] && ! check_ghcr_auth; then
        echo -e "${RED}Not authenticated to GHCR${NC}"
        echo "Run: docker login ghcr.io -u YOUR_USERNAME"
        exit 1
    fi

    cd "$PROJECT_ROOT"

    for target in "${TARGETS[@]}"; do
        local context dockerfile image_name

        case "$target" in
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
            *)
                echo -e "${RED}Unknown target: $target${NC}"
                continue
                ;;
        esac

        local full_image="$GHCR_REGISTRY/$IMAGE_PREFIX/$image_name"

        if [ "$SKIP_BUILD" = "false" ]; then
            echo -e "${BLUE}→ Building $target...${NC}"

            local label_args=(
                --label "org.opencontainers.image.version=$VERSION"
                --label "org.opencontainers.image.revision=$GIT_SHA"
                --label "org.opencontainers.image.created=$BUILD_DATE"
                --label "org.opencontainers.image.source=https://github.com/$IMAGE_PREFIX"
            )
            [ -n "$DESCRIPTION" ] && label_args+=(--label "org.opencontainers.image.description=$DESCRIPTION")

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
        fi

        if [ "$DRY_RUN" = "false" ]; then
            echo -e "${BLUE}→ Pushing $target...${NC}"
            docker push "$full_image:latest"
            docker push "$full_image:$VERSION"
            docker push "$full_image:sha-$GIT_SHA"
            echo -e "${GREEN}✓ Pushed $full_image:$VERSION${NC}"
        fi

        echo ""
    done
}

# ============================================================================
# npm CLI
# ============================================================================

cmd_cli() {
    get_versions

    echo -e "${BOLD}Publishing CLI to npm${NC}"
    echo -e "  Version: ${BLUE}$CLI_VERSION${NC}"
    [ "$DRY_RUN" = "true" ] && echo -e "  Mode:    ${YELLOW}DRY RUN${NC}"
    echo ""

    # Auth check
    if [ "$DRY_RUN" = "false" ] && ! check_npm_auth; then
        echo -e "${RED}Not authenticated to npm${NC}"
        echo "Run: npm login"
        exit 1
    fi

    cd "$PROJECT_ROOT/cli"

    # Check if version already published
    if npm view "@aaronsb/kg-cli@$CLI_VERSION" version &>/dev/null; then
        echo -e "${RED}Version $CLI_VERSION already published${NC}"
        echo "Bump version in cli/package.json first"
        exit 1
    fi

    if [ "$SKIP_BUILD" = "false" ]; then
        echo -e "${BLUE}→ Building CLI...${NC}"
        npm run clean
        npm run build
        echo -e "${GREEN}✓ Build complete${NC}"
    fi

    echo ""
    echo -e "${BLUE}Package contents:${NC}"
    npm pack --dry-run 2>&1 | grep -E "^npm notice [0-9]" | head -15
    echo ""

    if [ "$DRY_RUN" = "false" ]; then
        echo -e "${BLUE}→ Publishing to npm...${NC}"
        npm publish --access public
        echo -e "${GREEN}✓ Published @aaronsb/kg-cli@$CLI_VERSION${NC}"
        echo ""
        echo "Install: npm install -g @aaronsb/kg-cli"
    fi
}

# ============================================================================
# PyPI FUSE
# ============================================================================

cmd_fuse() {
    get_versions

    echo -e "${BOLD}Publishing FUSE driver to PyPI${NC}"
    echo -e "  Version: ${BLUE}$FUSE_VERSION${NC}"
    [ "$DRY_RUN" = "true" ] && echo -e "  Mode:    ${YELLOW}DRY RUN${NC}"
    echo ""

    # Check twine
    if ! command -v twine &>/dev/null; then
        echo -e "${RED}twine not found${NC}"
        echo "Run: pip install twine build"
        exit 1
    fi

    cd "$PROJECT_ROOT/fuse"

    # Check if version already on PyPI
    if pip index versions kg-fuse 2>/dev/null | grep -q "$FUSE_VERSION"; then
        echo -e "${RED}Version $FUSE_VERSION already published${NC}"
        echo "Bump version in fuse/pyproject.toml first"
        exit 1
    fi

    if [ "$SKIP_BUILD" = "false" ]; then
        echo -e "${BLUE}→ Building package...${NC}"

        # Clean previous builds
        rm -rf dist/ build/ *.egg-info/

        # Build with hatch/build
        if command -v python -m build &>/dev/null; then
            python -m build
        else
            echo -e "${YELLOW}python-build not found, installing...${NC}"
            pip install build
            python -m build
        fi

        echo -e "${GREEN}✓ Build complete${NC}"
    fi

    echo ""
    echo -e "${BLUE}Package contents:${NC}"
    ls -la dist/
    echo ""

    if [ "$DRY_RUN" = "false" ]; then
        echo -e "${BLUE}→ Uploading to PyPI...${NC}"
        twine upload dist/*
        echo -e "${GREEN}✓ Published kg-fuse==$FUSE_VERSION${NC}"
        echo ""
        echo "Install: pip install kg-fuse"
    fi
}

# ============================================================================
# All
# ============================================================================

cmd_all() {
    echo -e "${BOLD}Publishing all packages${NC}"
    echo ""

    cmd_images
    cmd_cli
    cmd_fuse

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ All packages published${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ============================================================================
# Main
# ============================================================================

case "$COMMAND" in
    status)
        cmd_status
        ;;
    images)
        cmd_images
        ;;
    cli)
        cmd_cli
        ;;
    fuse)
        cmd_fuse
        ;;
    all)
        cmd_all
        ;;
esac
